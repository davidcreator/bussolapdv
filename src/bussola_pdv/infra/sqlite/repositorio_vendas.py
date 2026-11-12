"""Repositório de vendas, itens, pagamentos e consultas de conciliação."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime

from ...dominio.dinheiro import Dinheiro
from ...dominio.erros import ErroNaoEncontrado
from ...dominio.pagamentos import FormaPagamento, PlanoPagamento, StatusPagamento
from ...dominio.venda import ItemCarrinho, StatusVenda
from .base import RepositorioBase


@dataclass(frozen=True, slots=True)
class VendaRegistrada:
    id: str
    numero: int
    serie: str
    data_negocio: str
    criado_em: datetime
    operador_id: str
    turno_id: str
    status: StatusVenda
    subtotal: Dinheiro
    desconto: Dinheiro
    acrescimo: Dinheiro
    total: Dinheiro
    custo_total: Dinheiro
    cliente_id: str | None = None
    cancelada_em: datetime | None = None
    motivo_cancelamento: str = ""
    autorizador_id: str | None = None

    @property
    def rotulo(self) -> str:
        return f"{self.serie}-{self.numero:06d}"


class VendaRepositorio(RepositorioBase):
    # -- escrita ------------------------------------------------------------
    def proximo_numero(self) -> int:
        """Número sequencial de cupom gerado dentro da transação (sem buraco por corrida)."""
        linha = self.conexao.execute(
            "UPDATE sequencias SET valor = valor + 1 WHERE nome = 'venda' RETURNING valor"
        ).fetchone()
        if linha is None:  # pragma: no cover - sequência criada na migração
            self.conexao.execute("INSERT INTO sequencias (nome, valor) VALUES ('venda', 1)")
            return 1
        return int(linha[0])

    def inserir(
        self,
        *,
        venda_id: str,
        data_negocio: str,
        criado_em: datetime,
        operador_id: str,
        turno_id: str,
        subtotal: Dinheiro,
        desconto: Dinheiro,
        acrescimo: Dinheiro,
        total: Dinheiro,
        custo_total: Dinheiro,
        chave_idempotencia: str,
        cliente_id: str | None = None,
        serie: str = "1",
    ) -> VendaRegistrada:
        numero = self.proximo_numero()
        self.conexao.execute(
            """INSERT INTO vendas (id, numero, serie, data_negocio, criado_em, operador_id,
                                   cliente_id, turno_id, status, subtotal_centavos,
                                   desconto_centavos, acrescimo_centavos, total_centavos,
                                   custo_total_centavos, chave_idempotencia)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'CONCLUIDA', ?, ?, ?, ?, ?, ?)""",
            (
                venda_id,
                numero,
                serie,
                data_negocio,
                self.iso(criado_em),
                operador_id,
                cliente_id,
                turno_id,
                subtotal.centavos,
                desconto.centavos,
                acrescimo.centavos,
                total.centavos,
                custo_total.centavos,
                chave_idempotencia,
            ),
        )
        return self.por_id(venda_id)

    def inserir_itens(self, venda_id: str, itens: tuple[ItemCarrinho, ...]) -> None:
        from uuid import uuid4

        for sequencia, item in enumerate(itens, start=1):
            self.conexao.execute(
                """INSERT INTO itens_venda (id, venda_id, sequencia, produto_id, codigo_produto,
                                            descricao, unidade, quantidade_milesimos,
                                            preco_unitario_centavos, desconto_centavos,
                                            total_centavos, custo_unitario_centavos)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid4()),
                    venda_id,
                    sequencia,
                    item.produto_id,
                    item.codigo,
                    item.descricao,
                    item.unidade.value,
                    item.quantidade.milesimos,
                    item.preco_unitario.centavos,
                    item.desconto.centavos,
                    item.total.centavos,
                    item.custo_unitario.centavos,
                ),
            )

    def inserir_pagamentos(self, venda_id: str, plano: PlanoPagamento, *, criado_em: datetime) -> None:
        from uuid import uuid4

        for sequencia, pagamento in enumerate(plano.pagamentos, start=1):
            self.conexao.execute(
                """INSERT INTO pagamentos (id, venda_id, sequencia, forma, valor_entregue_centavos,
                                           valor_aplicado_centavos, troco_centavos, status,
                                           confirmacao_manual, referencia, bandeira, nsu,
                                           parcelas, criado_em)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid4()),
                    venda_id,
                    sequencia,
                    pagamento.forma.value,
                    pagamento.valor_entregue.centavos,
                    pagamento.valor_aplicado.centavos,
                    pagamento.troco.centavos,
                    pagamento.status.value,
                    int(pagamento.confirmacao_manual),
                    pagamento.referencia,
                    pagamento.bandeira,
                    pagamento.nsu,
                    pagamento.parcelas,
                    self.iso(criado_em),
                ),
            )

    def cancelar(
        self,
        venda_id: str,
        *,
        cancelada_em: datetime,
        motivo: str,
        autorizador_id: str,
    ) -> None:
        cursor = self.conexao.execute(
            """UPDATE vendas SET status = 'CANCELADA', cancelada_em = ?, motivo_cancelamento = ?,
                                 autorizador_id = ?
               WHERE id = ? AND status = 'CONCLUIDA'""",
            (self.iso(cancelada_em), motivo.strip(), autorizador_id, venda_id),
        )
        if cursor.rowcount == 0:
            raise ErroNaoEncontrado("Venda não encontrada ou já cancelada.")

    # -- leitura ------------------------------------------------------------
    def _para_venda(self, linha: sqlite3.Row) -> VendaRegistrada:
        return VendaRegistrada(
            id=linha["id"],
            numero=int(linha["numero"]),
            serie=linha["serie"],
            data_negocio=linha["data_negocio"],
            criado_em=datetime.fromisoformat(linha["criado_em"]),
            operador_id=linha["operador_id"],
            cliente_id=linha["cliente_id"],
            turno_id=linha["turno_id"],
            status=StatusVenda(linha["status"]),
            subtotal=self.dinheiro(linha["subtotal_centavos"]),
            desconto=self.dinheiro(linha["desconto_centavos"]),
            acrescimo=self.dinheiro(linha["acrescimo_centavos"]),
            total=self.dinheiro(linha["total_centavos"]),
            custo_total=self.dinheiro(linha["custo_total_centavos"]),
            cancelada_em=self.instante(linha["cancelada_em"]),
            motivo_cancelamento=linha["motivo_cancelamento"] or "",
            autorizador_id=linha["autorizador_id"],
        )

    def por_id(self, venda_id: str) -> VendaRegistrada:
        linha = self.conexao.execute("SELECT * FROM vendas WHERE id = ?", (venda_id,)).fetchone()
        if linha is None:
            raise ErroNaoEncontrado("Venda não encontrada.")
        return self._para_venda(linha)

    def por_rotulo(self, rotulo: str) -> VendaRegistrada:
        """Busca pelo rótulo do cupom (`1-000012`), que é o número que o cliente tem.

        É o que o suporte precisa: "o cupom 1-000012 saiu errado" — e não um UUID.
        Aceita também o número puro (`12`), assumindo a série única da instalação.
        """
        texto = str(rotulo).strip()
        serie, _, numero = texto.partition("-")
        if numero:
            try:
                numero_int = int(numero)
            except ValueError as exc:
                raise ErroNaoEncontrado(
                    f"Cupom não encontrado: {rotulo}. Use o formato série-número (1-000012)."
                ) from exc
            linha = self.conexao.execute(
                "SELECT * FROM vendas WHERE serie = ? AND numero = ?",
                (serie, numero_int),
            ).fetchone()
        else:
            try:
                numero_int = int(texto)
            except ValueError as exc:
                raise ErroNaoEncontrado(
                    f"Rótulo de cupom inválido: {rotulo!r}. Use o formato série-número (1-000012)."
                ) from exc
            linha = self.conexao.execute(
                "SELECT * FROM vendas WHERE numero = ? ORDER BY criado_em DESC LIMIT 1",
                (numero_int,),
            ).fetchone()
        if linha is None:
            raise ErroNaoEncontrado(f"Cupom não encontrado: {rotulo}.")
        return self._para_venda(linha)

    def por_chave_idempotencia(self, chave: str) -> VendaRegistrada | None:
        linha = self.conexao.execute("SELECT * FROM vendas WHERE chave_idempotencia = ?", (chave,)).fetchone()
        return self._para_venda(linha) if linha else None

    def listar(
        self,
        *,
        data_inicial: str | None = None,
        data_final: str | None = None,
        operador_id: str | None = None,
        status: StatusVenda | None = None,
        turno_id: str | None = None,
        limite: int = 500,
    ) -> list[dict]:
        condicoes = ["1 = 1"]
        parametros: list[object] = []
        if data_inicial:
            condicoes.append("v.data_negocio >= ?")
            parametros.append(data_inicial)
        if data_final:
            condicoes.append("v.data_negocio <= ?")
            parametros.append(data_final)
        if operador_id:
            condicoes.append("v.operador_id = ?")
            parametros.append(operador_id)
        if turno_id:
            condicoes.append("v.turno_id = ?")
            parametros.append(turno_id)
        if status:
            condicoes.append("v.status = ?")
            parametros.append(getattr(status, "value", status))
        sql = f"""SELECT v.id, v.numero, v.serie, v.data_negocio, v.criado_em, v.status,
                         v.total_centavos, v.desconto_centavos, v.turno_id, v.operador_id,
                         u.nome AS operador, c.nome AS cliente,
                         (SELECT COUNT(*) FROM itens_venda i WHERE i.venda_id = v.id) AS itens,
                         (SELECT COALESCE(SUM(p.valor_aplicado_centavos), 0) FROM pagamentos p
                           WHERE p.venda_id = v.id) AS aplicado_centavos,
                         (SELECT COALESCE(SUM(p.troco_centavos), 0) FROM pagamentos p
                           WHERE p.venda_id = v.id) AS troco_centavos
                  FROM vendas v
                  JOIN usuarios u ON u.id = v.operador_id
                  LEFT JOIN clientes c ON c.id = v.cliente_id
                  WHERE {' AND '.join(condicoes)}
                  ORDER BY v.criado_em DESC LIMIT ?"""
        parametros.append(limite)
        return [dict(linha) for linha in self.conexao.execute(sql, parametros)]

    def itens(self, venda_id: str) -> list[dict]:
        linhas = self.conexao.execute(
            """SELECT sequencia, produto_id, codigo_produto, descricao, unidade, quantidade_milesimos,
                      preco_unitario_centavos, desconto_centavos, total_centavos,
                      custo_unitario_centavos
               FROM itens_venda WHERE venda_id = ? ORDER BY sequencia""",
            (venda_id,),
        )
        return [dict(linha) for linha in linhas]

    def pagamentos(self, venda_id: str) -> list[dict]:
        linhas = self.conexao.execute(
            """SELECT sequencia, forma, valor_entregue_centavos, valor_aplicado_centavos,
                      troco_centavos, status, confirmacao_manual, referencia, nsu, bandeira,
                      parcelas
               FROM pagamentos WHERE venda_id = ? ORDER BY sequencia""",
            (venda_id,),
        )
        return [dict(linha) for linha in linhas]

    # -- conciliação --------------------------------------------------------
    def resumo_periodo(
        self,
        data_inicial: str,
        data_final: str,
        *,
        operador_id: str | None = None,
        turno_id: str | None = None,
    ) -> dict:
        filtro_extra = ""
        parametros: list[object] = [data_inicial, data_final]
        if operador_id:
            filtro_extra += " AND v.operador_id = ?"
            parametros.append(operador_id)
        if turno_id:
            filtro_extra += " AND v.turno_id = ?"
            parametros.append(turno_id)
        linha = self.conexao.execute(
            f"""SELECT COUNT(*) AS cupons,
                       COALESCE(SUM(v.subtotal_centavos), 0) AS subtotal_centavos,
                       COALESCE(SUM(v.desconto_centavos), 0) AS desconto_centavos,
                       COALESCE(SUM(v.total_centavos), 0) AS faturamento_centavos,
                       COALESCE(SUM(v.custo_total_centavos), 0) AS custo_centavos,
                       (SELECT COALESCE(SUM(i.quantidade_milesimos), 0) FROM itens_venda i
                          JOIN vendas iv ON iv.id = i.venda_id
                         WHERE iv.status = 'CONCLUIDA'
                           AND iv.data_negocio BETWEEN ? AND ?) AS quantidade_milesimos
                FROM vendas v
                WHERE v.status = 'CONCLUIDA' AND v.data_negocio BETWEEN ? AND ?{filtro_extra}""",
            [data_inicial, data_final, *parametros],
        ).fetchone()
        dados = dict(linha)
        cupons = int(dados["cupons"])
        dados["ticket_medio_centavos"] = (
            round(dados["faturamento_centavos"] / cupons) if cupons else 0
        )
        # Quantidade considera o mesmo filtro de operador/turno quando informado.
        if operador_id or turno_id:
            filtro_itens = " AND v.operador_id = ?" if operador_id else ""
            params_itens: list[object] = [data_inicial, data_final]
            if operador_id:
                params_itens.append(operador_id)
            if turno_id:
                filtro_itens += " AND v.turno_id = ?"
                params_itens.append(turno_id)
            dados["quantidade_milesimos"] = int(
                self.conexao.execute(
                    f"""SELECT COALESCE(SUM(i.quantidade_milesimos), 0) FROM itens_venda i
                        JOIN vendas v ON v.id = i.venda_id
                        WHERE v.status = 'CONCLUIDA' AND v.data_negocio BETWEEN ? AND ?{filtro_itens}""",
                    params_itens,
                ).fetchone()[0]
            )
        return dados

    def por_forma(
        self,
        data_inicial: str,
        data_final: str,
        *,
        operador_id: str | None = None,
        turno_id: str | None = None,
    ) -> list[dict]:
        filtro = ""
        parametros: list[object] = [data_inicial, data_final]
        if operador_id:
            filtro += " AND v.operador_id = ?"
            parametros.append(operador_id)
        if turno_id:
            filtro += " AND v.turno_id = ?"
            parametros.append(turno_id)
        linhas = self.conexao.execute(
            f"""SELECT p.forma,
                       COUNT(*) AS linhas,
                       COALESCE(SUM(p.valor_aplicado_centavos), 0) AS aplicado_centavos,
                       COALESCE(SUM(p.valor_entregue_centavos), 0) AS entregue_centavos,
                       COALESCE(SUM(p.troco_centavos), 0) AS troco_centavos,
                       COALESCE(SUM(CASE WHEN p.status = 'PENDENTE' THEN 1 ELSE 0 END), 0) AS pendentes,
                       COALESCE(SUM(CASE WHEN p.status = 'PENDENTE'
                                         THEN p.valor_aplicado_centavos ELSE 0 END), 0) AS pendente_centavos
                FROM pagamentos p
                JOIN vendas v ON v.id = p.venda_id
                WHERE v.status = 'CONCLUIDA' AND v.data_negocio BETWEEN ? AND ?{filtro}
                GROUP BY p.forma
                ORDER BY aplicado_centavos DESC""",
            parametros,
        )
        resultado = []
        for linha in linhas:
            dados = dict(linha)
            dados["rotulo"] = FormaPagamento(dados["forma"]).rotulo
            resultado.append(dados)
        return resultado

    def divergencias(self, data_inicial: str, data_final: str) -> dict[str, list[dict]]:
        """Aponta vendas cujo aplicado difere do total e pagamentos fora de venda válida."""
        vendas = [
            dict(linha)
            for linha in self.conexao.execute(
                """SELECT v.id, v.numero, v.serie, v.status, v.total_centavos,
                          COALESCE(SUM(p.valor_aplicado_centavos), 0) AS aplicado_centavos
                     FROM vendas v LEFT JOIN pagamentos p ON p.venda_id = v.id
                    WHERE v.data_negocio BETWEEN ? AND ?
                    GROUP BY v.id
                   HAVING aplicado_centavos <> v.total_centavos""",
                (data_inicial, data_final),
            )
        ]
        orfaos = [
            dict(linha)
            for linha in self.conexao.execute(
                """SELECT p.id, p.venda_id, p.valor_aplicado_centavos
                     FROM pagamentos p LEFT JOIN vendas v ON v.id = p.venda_id
                    WHERE v.id IS NULL"""
            )
        ]
        sem_itens = [
            dict(linha)
            for linha in self.conexao.execute(
                """SELECT v.id, v.numero FROM vendas v
                    WHERE v.data_negocio BETWEEN ? AND ?
                      AND NOT EXISTS (SELECT 1 FROM itens_venda i WHERE i.venda_id = v.id)""",
                (data_inicial, data_final),
            )
        ]
        return {"vendas_divergentes": vendas, "pagamentos_orfaos": orfaos, "vendas_sem_itens": sem_itens}

    def pendentes_confirmacao(self, data_inicial: str, data_final: str) -> list[dict]:
        return [
            dict(linha)
            for linha in self.conexao.execute(
                """SELECT v.numero, p.forma, p.valor_aplicado_centavos
                     FROM pagamentos p JOIN vendas v ON v.id = p.venda_id
                    WHERE p.status = 'PENDENTE' AND v.status = 'CONCLUIDA'
                      AND v.data_negocio BETWEEN ? AND ?
                    ORDER BY v.numero""",
                (data_inicial, data_final),
            )
        ]

    def confirmar_pagamento(self, venda_id: str, sequencia: int, *, confirmado: bool = True) -> None:
        """Confirmação manual do recebimento (não substitui conciliação bancária)."""
        self.conexao.execute(
            """UPDATE pagamentos SET status = ?, confirmacao_manual = 1
                WHERE venda_id = ? AND sequencia = ? AND status = 'PENDENTE'""",
            (StatusPagamento.CONFIRMADO.value if confirmado else StatusPagamento.PENDENTE.value,
             venda_id, sequencia),
        )


__all__ = ["VendaRegistrada", "VendaRepositorio"]
