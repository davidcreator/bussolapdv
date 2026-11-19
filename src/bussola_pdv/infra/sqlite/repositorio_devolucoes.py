"""Persistência das devoluções: documento, itens e quanto já voltou por item."""

from __future__ import annotations

from ...dominio.devolucao import Devolucao
from .base import RepositorioBase

COLUNAS = """id, venda_id, data_negocio, criado_em, operador_id, autorizador_id, tipo, destino,
             motivo, observacoes, total_centavos, dinheiro_centavos, credito_centavos,
             estoque_devolvido, dias_desde_venda, fora_do_prazo, turno_id"""


class DevolucaoRepositorio(RepositorioBase):
    def inserir(self, devolucao: Devolucao, *, data_negocio: str, criado_em: str) -> Devolucao:
        self.conexao.execute(
            f"""INSERT INTO devolucoes ({COLUNAS}, chave_idempotencia)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                devolucao.id,
                devolucao.venda_id,
                data_negocio,
                criado_em,
                devolucao.operador_id,
                devolucao.autorizador_id,
                devolucao.tipo.value,
                devolucao.destino.value,
                devolucao.motivo,
                devolucao.observacoes,
                devolucao.total.centavos,
                devolucao.dinheiro_centavos,
                devolucao.credito_centavos,
                int(devolucao.estoque_devolvido),
                devolucao.dias_desde_venda,
                int(devolucao.fora_do_prazo),
                devolucao.turno_id,
                devolucao.chave_idempotencia,
            ),
        )
        for item in devolucao.itens:
            self.conexao.execute(
                """INSERT INTO devolucao_itens (
                       id, devolucao_id, venda_item_sequencia, produto_id, codigo, descricao,
                       quantidade_milesimos, valor_unitario_centavos, total_centavos
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    f"{devolucao.id}-{item.venda_item_sequencia}",
                    devolucao.id,
                    item.venda_item_sequencia,
                    item.produto_id,
                    item.codigo,
                    item.descricao,
                    item.quantidade.milesimos,
                    item.valor_unitario.centavos,
                    item.total.centavos,
                ),
            )
        return devolucao

    # -- leitura ------------------------------------------------------------
    def devolvido_por_item(self, venda_id: str) -> dict[int, int]:
        """Milésimos já devolvidos por sequência de item da venda."""
        linhas = self.conexao.execute(
            """SELECT i.venda_item_sequencia AS sequencia,
                      COALESCE(SUM(i.quantidade_milesimos), 0) AS devolvido
                 FROM devolucao_itens i
                 JOIN devolucoes d ON d.id = i.devolucao_id
                WHERE d.venda_id = ?
                GROUP BY i.venda_item_sequencia""",
            (venda_id,),
        )
        return {int(linha["sequencia"]): int(linha["devolvido"]) for linha in linhas}

    def total_devolvido(self, venda_id: str) -> int:
        linha = self.conexao.execute(
            "SELECT COALESCE(SUM(total_centavos), 0) FROM devolucoes WHERE venda_id = ?",
            (venda_id,),
        ).fetchone()
        return int(linha[0])

    def por_id(self, devolucao_id: str) -> dict:
        linha = self.conexao.execute(
            f"SELECT {COLUNAS} FROM devolucoes WHERE id = ?", (devolucao_id,)
        ).fetchone()
        if linha is None:
            raise KeyError(f"Devolução {devolucao_id!r} não encontrada.")
        registro = dict(linha)
        registro["itens"] = self.itens(devolucao_id)
        return registro

    def itens(self, devolucao_id: str) -> list[dict]:
        linhas = self.conexao.execute(
            """SELECT venda_item_sequencia AS sequencia, produto_id, codigo, descricao,
                      quantidade_milesimos, valor_unitario_centavos, total_centavos
                 FROM devolucao_itens WHERE devolucao_id = ?
                ORDER BY venda_item_sequencia""",
            (devolucao_id,),
        )
        return [dict(linha) for linha in linhas]

    def listar(self, *, limite: int = 500, venda_id: str | None = None) -> list[dict]:
        condicoes = ["1 = 1"]
        parametros: list[object] = []
        if venda_id:
            condicoes.append("d.venda_id = ?")
            parametros.append(venda_id)
        sql = f"""SELECT d.id, d.venda_id, d.data_negocio, d.tipo, d.destino, d.motivo,
                         d.total_centavos, d.dinheiro_centavos, d.credito_centavos,
                         d.fora_do_prazo, d.estoque_devolvido,
                         v.serie || '-' || printf('%06d', v.numero) AS venda_rotulo,
                         u.nome AS operador
                    FROM devolucoes d
                    JOIN vendas v ON v.id = d.venda_id
                    JOIN usuarios u ON u.id = d.operador_id
                   WHERE {' AND '.join(condicoes)}
                   ORDER BY d.criado_em DESC LIMIT ?"""
        parametros.append(int(limite))
        return [dict(linha) for linha in self.conexao.execute(sql, parametros)]

__all__ = ["DevolucaoRepositorio"]
