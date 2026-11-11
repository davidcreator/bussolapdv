"""Repositório de títulos, recebimentos e aging do crediário."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from ...dominio.crediario import Parcela, StatusTitulo
from ...dominio.dinheiro import Dinheiro
from ...dominio.erros import ErroNaoEncontrado, RecebimentoInvalido
from ...dominio.pagamentos import FormaPagamento
from .base import RepositorioBase


class CrediarioRepositorio(RepositorioBase):
    def inserir_parcelas(
        self,
        *,
        venda_id: str,
        cliente_id: str,
        parcelas: list[Parcela],
        criado_em: datetime,
    ) -> list[str]:
        ids: list[str] = []
        for parcela in parcelas:
            titulo_id = str(uuid.uuid4())
            self.conexao.execute(
                """INSERT INTO titulos (id, venda_id, cliente_id, numero_parcela, total_parcelas,
                                        vencimento, principal_centavos, encargos_centavos,
                                        status, criado_em)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ABERTO', ?)""",
                (
                    titulo_id,
                    venda_id,
                    cliente_id,
                    parcela.numero,
                    parcela.total_parcelas,
                    parcela.vencimento.isoformat(),
                    parcela.principal.centavos,
                    parcela.encargos.centavos,
                    self.iso(criado_em),
                ),
            )
            ids.append(titulo_id)
        return ids

    def receber(
        self,
        *,
        titulo_id: str,
        valor: Dinheiro,
        forma: FormaPagamento,
        data_negocio: str,
        turno_id: str,
        operador_id: str,
        criado_em: datetime,
        referencia: str = "",
    ) -> str:
        if valor.centavos <= 0:
            raise RecebimentoInvalido("Recebimento deve ter valor positivo.")
        if forma is FormaPagamento.A_PRAZO:
            raise RecebimentoInvalido("Recebimento não pode ser feito 'a prazo'.")
        titulo = self.por_id(titulo_id)
        saldo = Dinheiro(int(titulo["saldo_centavos"]))
        if valor > saldo:
            raise RecebimentoInvalido(
                f"Valor recebido ({valor.formatado()}) excede o saldo do título ({saldo.formatado()}).",
                detalhe={"saldo_centavos": saldo.centavos},
            )
        recebimento_id = str(uuid.uuid4())
        self.conexao.execute(
            """INSERT INTO recebimentos (id, titulo_id, data_negocio, forma, valor_centavos,
                                         turno_id, operador_id, estorno, referencia, criado_em)
               VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)""",
            (
                recebimento_id,
                titulo_id,
                data_negocio,
                forma.value,
                valor.centavos,
                turno_id,
                operador_id,
                referencia,
                self.iso(criado_em),
            ),
        )
        self._atualizar_status(titulo_id, data_negocio)
        return recebimento_id

    def estornar_recebimento(self, *, recebimento_id: str, criado_em: datetime) -> None:
        """Estorno gera evento inverso; o recebimento original permanece no histórico."""
        linha = self.conexao.execute(
            "SELECT titulo_id, data_negocio FROM recebimentos WHERE id = ?", (recebimento_id,)
        ).fetchone()
        if linha is None:
            raise ErroNaoEncontrado("Recebimento não encontrado.")
        self.conexao.execute(
            """INSERT INTO recebimentos (id, titulo_id, data_negocio, forma, valor_centavos,
                                         turno_id, operador_id, estorno, referencia, criado_em)
               SELECT ?, titulo_id, data_negocio, forma, valor_centavos, turno_id, operador_id,
                      1, 'estorno de ' || id, ?
                 FROM recebimentos WHERE id = ?""",
            (str(uuid.uuid4()), self.iso(criado_em), recebimento_id),
        )
        self._atualizar_status(linha["titulo_id"], linha["data_negocio"])

    def _atualizar_status(self, titulo_id: str, data_negocio: str) -> None:
        linha = self.conexao.execute(
            """SELECT t.principal_centavos + t.encargos_centavos AS total,
                      COALESCE(SUM(CASE WHEN r.estorno = 1 THEN -r.valor_centavos
                                        ELSE r.valor_centavos END), 0) AS recebido,
                      t.vencimento
                 FROM titulos t LEFT JOIN recebimentos r ON r.titulo_id = t.id
                WHERE t.id = ? GROUP BY t.id""",
            (titulo_id,),
        ).fetchone()
        if linha is None:
            raise ErroNaoEncontrado("Título não encontrado.")
        total, recebido = int(linha["total"]), int(linha["recebido"])
        if recebido >= total:
            status = StatusTitulo.PAGO
        elif recebido > 0:
            status = StatusTitulo.PARCIAL
        elif date.fromisoformat(linha["vencimento"]) < date.fromisoformat(data_negocio):
            status = StatusTitulo.VENCIDO
        else:
            status = StatusTitulo.ABERTO
        self.conexao.execute("UPDATE titulos SET status = ? WHERE id = ?", (status.value, titulo_id))

    def por_id(self, titulo_id: str) -> dict:
        linha = self.conexao.execute(
            """SELECT t.*, COALESCE(SUM(CASE WHEN r.estorno = 1 THEN -r.valor_centavos
                                             ELSE r.valor_centavos END), 0) AS recebido_centavos
                 FROM titulos t LEFT JOIN recebimentos r ON r.titulo_id = t.id
                WHERE t.id = ? GROUP BY t.id""",
            (titulo_id,),
        ).fetchone()
        if linha is None:
            raise ErroNaoEncontrado("Título não encontrado.")
        dados = dict(linha)
        dados["saldo_centavos"] = (
            int(dados["principal_centavos"])
            + int(dados["encargos_centavos"])
            - int(dados["recebido_centavos"])
        )
        return dados

    def listar(
        self,
        *,
        cliente_id: str | None = None,
        data_inicial: str | None = None,
        data_final: str | None = None,
        incluir_pagos: bool = False,
        referencia: str | None = None,
        limite: int = 500,
    ) -> list[dict]:
        condicoes = ["1 = 1"]
        parametros: list[object] = []
        if cliente_id:
            condicoes.append("t.cliente_id = ?")
            parametros.append(cliente_id)
        if data_inicial:
            condicoes.append("t.vencimento >= ?")
            parametros.append(data_inicial)
        if data_final:
            condicoes.append("t.vencimento <= ?")
            parametros.append(data_final)
        if not incluir_pagos:
            condicoes.append("t.status <> 'PAGO'")
        sql = f"""SELECT t.id, t.venda_id, t.cliente_id, c.nome AS cliente, t.numero_parcela,
                         t.total_parcelas, t.vencimento, t.principal_centavos, t.encargos_centavos,
                         t.status,
                         COALESCE(SUM(CASE WHEN r.estorno = 1 THEN -r.valor_centavos
                                           ELSE r.valor_centavos END), 0) AS recebido_centavos
                    FROM titulos t
                    JOIN clientes c ON c.id = t.cliente_id
                    LEFT JOIN recebimentos r ON r.titulo_id = t.id
                   WHERE {' AND '.join(condicoes)}
                   GROUP BY t.id
                   ORDER BY t.vencimento LIMIT ?"""
        parametros.append(limite)
        resultado = []
        for linha in self.conexao.execute(sql, parametros):
            dados = dict(linha)
            dados["saldo_centavos"] = (
                int(dados["principal_centavos"])
                + int(dados["encargos_centavos"])
                - int(dados["recebido_centavos"])
            )
            dados["atraso_dias"] = (
                max(0, (date.fromisoformat(referencia) - date.fromisoformat(dados["vencimento"])).days)
                if referencia
                else 0
            )
            resultado.append(dados)
        return resultado

    def total_recebido_turno(self, turno_id: str) -> Dinheiro:
        linha = self.conexao.execute(
            """SELECT COALESCE(SUM(CASE WHEN estorno = 1 THEN -valor_centavos
                                       ELSE valor_centavos END), 0)
                 FROM recebimentos WHERE turno_id = ?""",
            (turno_id,),
        ).fetchone()
        return self.dinheiro(linha[0])
