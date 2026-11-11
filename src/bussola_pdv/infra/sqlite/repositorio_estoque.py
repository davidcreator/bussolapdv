"""Repositório de movimentos de estoque e entradas de fornecedor."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime

from ...dominio.dinheiro import Dinheiro
from ...dominio.erros import ErroConflito
from ...dominio.estoque import (
    CriterioRateio,
    EntradaMercadoria,
    MovimentoEstoque,
    TipoMovimentoEstoque,
)
from .base import RepositorioBase


class EstoqueRepositorio(RepositorioBase):
    def inserir_movimento(
        self,
        *,
        produto_id: str,
        tipo: TipoMovimentoEstoque,
        quantidade_milesimos_assinada: int,
        criado_em: datetime,
        origem_tipo: str = "",
        origem_id: str = "",
        motivo: str = "",
        custo_unitario: Dinheiro | None = None,
    ) -> str:
        movimento_id = str(uuid.uuid4())
        self.conexao.execute(
            """INSERT INTO movimentos_estoque (id, produto_id, quantidade_milesimos, tipo,
                                               origem_tipo, origem_id, motivo,
                                               custo_unitario_centavos, criado_em)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                movimento_id,
                produto_id,
                quantidade_milesimos_assinada,
                tipo.value,
                origem_tipo,
                origem_id,
                motivo,
                custo_unitario.centavos if custo_unitario else None,
                self.iso(criado_em),
            ),
        )
        return movimento_id

    def saldo_milesimos(self, produto_id: str) -> int:
        linha = self.conexao.execute(
            "SELECT COALESCE(SUM(quantidade_milesimos), 0) FROM movimentos_estoque WHERE produto_id = ?",
            (produto_id,),
        ).fetchone()
        return int(linha[0])

    def saldos(self) -> dict[str, int]:
        return {
            linha["produto_id"]: int(linha["saldo"])
            for linha in self.conexao.execute(
                "SELECT produto_id, SUM(quantidade_milesimos) AS saldo "
                "FROM movimentos_estoque GROUP BY produto_id"
            )
        }

    def concluir(self, movimentos: list[MovimentoEstoque], *, criado_em: datetime, origem_id: str) -> None:
        """Grava vários movimentos de uma só vez (usado na venda/estorno)."""
        for movimento in movimentos:
            self.inserir_movimento(
                produto_id=movimento.produto_id,
                tipo=movimento.tipo,
                quantidade_milesimos_assinada=movimento.quantidade_assinada,
                criado_em=criado_em,
                origem_tipo="VENDA" if movimento.tipo is TipoMovimentoEstoque.VENDA else "AJUSTE",
                origem_id=origem_id,
                motivo=movimento.motivo,
                custo_unitario=movimento.custo_unitario,
            )

    def historico(self, produto_id: str, *, limite: int = 100) -> list[dict]:
        linhas = self.conexao.execute(
            """SELECT quantidade_milesimos, tipo, origem_tipo, origem_id, motivo, criado_em
               FROM movimentos_estoque WHERE produto_id = ?
               ORDER BY criado_em DESC, rowid DESC LIMIT ?""",
            (produto_id, limite),
        )
        return [dict(linha) for linha in linhas]


class EntradaRepositorio(RepositorioBase):
    def registrar_entrada(
        self,
        *,
        entrada: EntradaMercadoria,
        operador_id: str,
        criado_em: datetime,
        data_negocio: str,
    ) -> str:
        """Grava entrada, itens (com frete rateado) e movimentos de estoque.

        A chave comercial (fornecedor + documento) é única: nota repetida é
        recusada, não somada duas vezes.
        """
        entrada_id = str(uuid.uuid4())
        try:
            self.conexao.execute(
                """INSERT INTO entradas (id, fornecedor, documento, data_negocio, frete_centavos,
                                         criterio_rateio, operador_id, criado_em)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    entrada_id,
                    entrada.fornecedor.strip(),
                    entrada.documento.strip(),
                    data_negocio,
                    entrada.frete.centavos,
                    entrada.criterio.value,
                    operador_id,
                    self.iso(criado_em),
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise ErroConflito(
                "Entrada já registrada para este fornecedor e documento. "
                "Verifique a nota antes de repetir."
            ) from exc

        estoque = EstoqueRepositorio(self.conexao)
        for item in entrada.ratear_frete():
            self.conexao.execute(
                """INSERT INTO entradas_itens (id, entrada_id, produto_id, quantidade_milesimos,
                                               custo_unitario_centavos, frete_rateado_centavos)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4()),
                    entrada_id,
                    item.produto_id,
                    item.quantidade.milesimos,
                    item.custo_unitario.centavos,
                    item.frete_rateado.centavos,
                ),
            )
            estoque.inserir_movimento(
                produto_id=item.produto_id,
                tipo=TipoMovimentoEstoque.ENTRADA,
                quantidade_milesimos_assinada=item.quantidade.milesimos,
                criado_em=criado_em,
                origem_tipo="ENTRADA",
                origem_id=entrada_id,
                motivo=f"Entrada {entrada.fornecedor} doc. {entrada.documento}",
                custo_unitario=entrada.custo_unitario_com_frete(item),
            )
        return entrada_id

    def listar(self, *, limite: int = 200) -> list[dict]:
        linhas = self.conexao.execute(
            """SELECT e.id, e.fornecedor, e.documento, e.data_negocio, e.frete_centavos,
                      COUNT(i.id) AS itens, COALESCE(SUM(i.quantidade_milesimos), 0) AS quantidade
               FROM entradas e LEFT JOIN entradas_itens i ON i.entrada_id = e.id
               GROUP BY e.id ORDER BY e.data_negocio DESC, e.criado_em DESC LIMIT ?""",
            (limite,),
        )
        return [dict(linha) for linha in linhas]


__all__ = ["CriterioRateio", "EntradaRepositorio", "EstoqueRepositorio"]
