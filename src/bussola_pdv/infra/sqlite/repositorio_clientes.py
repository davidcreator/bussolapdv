"""Repositório de clientes e cálculo de crédito/aging."""

from __future__ import annotations

import sqlite3
from datetime import date

from ...dominio.cliente import Cliente
from ...dominio.crediario import AgingCliente, Parcela, calcular_aging, dias_de_atraso
from ...dominio.dinheiro import Dinheiro
from ...dominio.erros import ErroConflito, ErroNaoEncontrado
from .base import RepositorioBase

COLUNAS = "id, nome, documento, tipo_documento, limite_credito_centavos, ativo, observacoes"


class ClienteRepositorio(RepositorioBase):
    def criar(self, cliente: Cliente, *, criado_em: str) -> Cliente:
        try:
            self.conexao.execute(
                """INSERT INTO clientes (id, nome, documento, tipo_documento,
                                         limite_credito_centavos, ativo, observacoes, criado_em)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    cliente.id,
                    cliente.nome,
                    cliente.documento,
                    cliente.tipo_documento,
                    cliente.limite_credito,
                    int(cliente.ativo),
                    cliente.observacoes,
                    criado_em,
                ),
            )
        except Exception as exc:
            if "UNIQUE" in str(exc).upper():
                raise ErroConflito("Já existe cliente com este documento.") from exc
            raise
        return cliente

    def atualizar(self, cliente: Cliente) -> Cliente:
        cursor = self.conexao.execute(
            """UPDATE clientes SET nome = ?, documento = ?, tipo_documento = ?,
                   limite_credito_centavos = ?, ativo = ?, observacoes = ?
               WHERE id = ?""",
            (
                cliente.nome,
                cliente.documento,
                cliente.tipo_documento,
                cliente.limite_credito,
                int(cliente.ativo),
                cliente.observacoes,
                cliente.id,
            ),
        )
        if cursor.rowcount == 0:
            raise ErroNaoEncontrado("Cliente não encontrado para atualização.")
        return cliente

    def _para_cliente(self, linha: sqlite3.Row) -> Cliente:
        return Cliente(
            id=linha["id"],
            nome=linha["nome"],
            documento=linha["documento"],
            tipo_documento=linha["tipo_documento"],
            limite_credito=int(linha["limite_credito_centavos"]),
            ativo=bool(linha["ativo"]),
            observacoes=linha["observacoes"],
        )

    def por_id(self, cliente_id: str) -> Cliente:
        linha = self.conexao.execute(
            f"SELECT {COLUNAS} FROM clientes WHERE id = ?", (cliente_id,)
        ).fetchone()
        if linha is None:
            raise ErroNaoEncontrado("Cliente não encontrado.")
        return self._para_cliente(linha)

    def por_documento(self, documento: str) -> Cliente:
        linha = self.conexao.execute(
            f"SELECT {COLUNAS} FROM clientes WHERE documento = ?", (documento,)
        ).fetchone()
        if linha is None:
            raise ErroNaoEncontrado("Cliente não encontrado por documento.")
        return self._para_cliente(linha)

    def listar(self, *, busca: str = "", limite: int = 500) -> list[Cliente]:
        if busca.strip():
            termo = f"%{busca.strip()}%"
            linhas = self.conexao.execute(
                f"""SELECT {COLUNAS} FROM clientes
                    WHERE nome LIKE ? OR documento LIKE ?
                    ORDER BY nome COLLATE NOCASE LIMIT ?""",
                (termo, termo, limite),
            )
        else:
            linhas = self.conexao.execute(
                f"SELECT {COLUNAS} FROM clientes ORDER BY nome COLLATE NOCASE LIMIT ?",
                (limite,),
            )
        return [self._para_cliente(linha) for linha in linhas]

    # -- crédito ------------------------------------------------------------
    def _titulos_abertos(self, cliente_id: str) -> list[tuple[Parcela, Dinheiro]]:
        linhas = self.conexao.execute(
            """SELECT t.id, t.numero_parcela, t.total_parcelas, t.vencimento,
                      t.principal_centavos, t.encargos_centavos,
                      COALESCE(SUM(CASE WHEN r.estorno = 1 THEN -r.valor_centavos
                                        ELSE r.valor_centavos END), 0) AS recebido
               FROM titulos t
               LEFT JOIN recebimentos r ON r.titulo_id = t.id
               WHERE t.cliente_id = ? AND t.status <> 'CANCELADO'
               GROUP BY t.id""",
            (cliente_id,),
        ).fetchall()
        resultado = []
        for linha in linhas:
            parcela = Parcela(
                numero=int(linha["numero_parcela"]),
                total_parcelas=int(linha["total_parcelas"]),
                vencimento=date.fromisoformat(linha["vencimento"]),
                principal=self.dinheiro(linha["principal_centavos"]),
                encargos=self.dinheiro(linha["encargos_centavos"]),
            )
            resultado.append((parcela, self.dinheiro(linha["recebido"])))
        return resultado

    def saldo_devedor(self, cliente_id: str) -> int:
        total = 0
        for parcela, recebido in self._titulos_abertos(cliente_id):
            total += parcela.saldo(recebido).centavos
        return total

    def vencido_e_atraso(self, cliente_id: str, referencia: date) -> tuple[int, int]:
        vencido = 0
        atraso_maximo = 0
        for parcela, recebido in self._titulos_abertos(cliente_id):
            saldo = parcela.saldo(recebido)
            if saldo.centavos == 0:
                continue
            atraso = dias_de_atraso(parcela.vencimento, referencia)
            if atraso > 0:
                vencido += saldo.centavos
                atraso_maximo = max(atraso_maximo, atraso)
        return vencido, atraso_maximo

    def aging(self, cliente_id: str, referencia: date) -> AgingCliente:
        return calcular_aging(
            cliente_id=cliente_id, titulos=self._titulos_abertos(cliente_id), referencia=referencia
        )
