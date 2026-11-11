"""Repositório de produtos e consulta de saldos de estoque."""

from __future__ import annotations

import sqlite3

from ...dominio.erros import ErroConflito, ErroNaoEncontrado, ErroValidacao
from ...dominio.produto import Produto, StatusEstoque, Unidade, classificar_estoque
from .base import RepositorioBase

COLUNAS = """id, codigo, codigo_barras, descricao, categoria, unidade, custo_centavos,
             preco_centavos, estoque_minimo_milesimos, ponto_pedido_milesimos, fornecedor,
             ncm, ativo"""


class ProdutoRepositorio(RepositorioBase):
    # -- escrita ------------------------------------------------------------
    def criar(self, produto: Produto, *, criado_em: str) -> Produto:
        try:
            self.conexao.execute(
                f"""INSERT INTO produtos ({COLUNAS}, criado_em, atualizado_em)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    produto.id,
                    produto.codigo,
                    produto.codigo_barras,
                    produto.descricao,
                    produto.categoria,
                    produto.unidade.value,
                    produto.custo,
                    produto.preco,
                    produto.estoque_minimo_milesimos,
                    produto.ponto_pedido_milesimos,
                    produto.fornecedor,
                    produto.ncm,
                    int(produto.ativo),
                    criado_em,
                    criado_em,
                ),
            )
        except Exception as exc:  # sqlite3.IntegrityError
            if "UNIQUE" in str(exc).upper():
                raise ErroConflito("Já existe produto com este código ou código de barras.") from exc
            raise
        return produto

    def atualizar(self, produto: Produto, *, atualizado_em: str) -> Produto:
        try:
            cursor = self.conexao.execute(
                """UPDATE produtos SET codigo = ?, codigo_barras = ?, descricao = ?, categoria = ?,
                       unidade = ?, custo_centavos = ?, preco_centavos = ?,
                       estoque_minimo_milesimos = ?, ponto_pedido_milesimos = ?, fornecedor = ?,
                       ncm = ?, ativo = ?, atualizado_em = ?
                   WHERE id = ?""",
                (
                    produto.codigo,
                    produto.codigo_barras,
                    produto.descricao,
                    produto.categoria,
                    produto.unidade.value,
                    produto.custo,
                    produto.preco,
                    produto.estoque_minimo_milesimos,
                    produto.ponto_pedido_milesimos,
                    produto.fornecedor,
                    produto.ncm,
                    int(produto.ativo),
                    atualizado_em,
                    produto.id,
                ),
            )
        except Exception as exc:
            if "UNIQUE" in str(exc).upper():
                raise ErroConflito("Já existe produto com este código ou código de barras.") from exc
            raise
        if cursor.rowcount == 0:
            raise ErroNaoEncontrado("Produto não encontrado para atualização.")
        return produto

    # -- leitura ------------------------------------------------------------
    def _para_produto(self, linha: sqlite3.Row) -> Produto:
        return Produto(
            id=linha["id"],
            codigo=linha["codigo"],
            codigo_barras=linha["codigo_barras"],
            descricao=linha["descricao"],
            categoria=linha["categoria"],
            unidade=Unidade(linha["unidade"]),
            custo=int(linha["custo_centavos"]),
            preco=int(linha["preco_centavos"]),
            estoque_minimo_milesimos=int(linha["estoque_minimo_milesimos"]),
            ponto_pedido_milesimos=int(linha["ponto_pedido_milesimos"]),
            fornecedor=linha["fornecedor"],
            ncm=linha["ncm"],
            ativo=bool(linha["ativo"]),
        )

    def por_id(self, produto_id: str) -> Produto:
        linha = self.conexao.execute(f"SELECT {COLUNAS} FROM produtos WHERE id = ?", (produto_id,)).fetchone()
        if linha is None:
            raise ErroNaoEncontrado("Produto não encontrado.")
        return self._para_produto(linha)

    def por_codigo(self, codigo: str) -> Produto:
        linha = self.conexao.execute(
            f"SELECT {COLUNAS} FROM produtos WHERE codigo = ?", (str(codigo).strip(),)
        ).fetchone()
        if linha is None:
            raise ErroNaoEncontrado(f"Produto com código {codigo!r} não encontrado.")
        return self._para_produto(linha)

    def buscar_leitura(self, entrada: str) -> Produto:
        """Busca do PDV: código interno primeiro, depois código de barras.

        Colisão entre domínios é erro explícito — nunca "adivinha" o produto.
        """
        termo = str(entrada or "").strip()
        if not termo:
            raise ErroValidacao("Informe o código ou leia o código de barras.")
        por_codigo = self.conexao.execute(
            f"SELECT {COLUNAS} FROM produtos WHERE codigo = ?", (termo,)
        ).fetchone()
        por_barras = self.conexao.execute(
            f"SELECT {COLUNAS} FROM produtos WHERE codigo_barras = ?", (termo,)
        ).fetchone()
        if por_codigo is not None and por_barras is not None and por_codigo["id"] != por_barras["id"]:
            raise ErroConflito(
                f"Colisão de códigos: {termo!r} é código interno de um produto e código de barras de outro."
            )
        linha = por_codigo or por_barras
        if linha is None:
            raise ErroNaoEncontrado(f"Nenhum produto com código ou código de barras {termo!r}.")
        return self._para_produto(linha)

    def listar(
        self,
        *,
        busca: str = "",
        categoria: str = "",
        apenas_ativos: bool = True,
        limite: int = 500,
    ) -> list[Produto]:
        condicoes = ["1 = 1"]
        parametros: list[object] = []
        if apenas_ativos:
            condicoes.append("ativo = 1")
        if busca.strip():
            condicoes.append("(codigo LIKE ? OR codigo_barras LIKE ? OR descricao LIKE ?)")
            termo = f"%{busca.strip()}%"
            parametros.extend([termo, termo, termo])
        if categoria.strip():
            condicoes.append("categoria = ?")
            parametros.append(categoria.strip())
        sql = f"""SELECT {COLUNAS} FROM produtos
                  WHERE {' AND '.join(condicoes)}
                  ORDER BY descricao COLLATE NOCASE LIMIT ?"""
        parametros.append(int(limite))
        return [self._para_produto(linha) for linha in self.conexao.execute(sql, parametros)]

    def categorias(self) -> list[str]:
        linhas = self.conexao.execute(
            "SELECT DISTINCT categoria FROM produtos WHERE categoria <> '' ORDER BY categoria COLLATE NOCASE"
        )
        return [linha[0] for linha in linhas]

    # -- estoque ------------------------------------------------------------
    def saldo_milesimos(self, produto_id: str) -> int:
        linha = self.conexao.execute(
            "SELECT COALESCE(SUM(quantidade_milesimos), 0) FROM movimentos_estoque WHERE produto_id = ?",
            (produto_id,),
        ).fetchone()
        return int(linha[0])

    def saldos(self, produtos_ids: list[str] | None = None) -> dict[str, int]:
        if produtos_ids:
            marcadores = ",".join("?" for _ in produtos_ids)
            sql = f"""SELECT produto_id, COALESCE(SUM(quantidade_milesimos), 0) AS saldo
                      FROM movimentos_estoque WHERE produto_id IN ({marcadores})
                      GROUP BY produto_id"""
            linhas = self.conexao.execute(sql, produtos_ids)
        else:
            linhas = self.conexao.execute(
                "SELECT produto_id, COALESCE(SUM(quantidade_milesimos), 0) AS saldo "
                "FROM movimentos_estoque GROUP BY produto_id"
            )
        return {linha["produto_id"]: int(linha["saldo"]) for linha in linhas}

    def indicadores_estoque(self) -> list[dict]:
        """Produtos com saldo e status calculados pela regra única do domínio."""
        saldos = self.saldos()
        resultado = []
        for produto in self.listar(apenas_ativos=False, limite=100_000):
            saldo = saldos.get(produto.id, 0)
            status = classificar_estoque(
                saldo,
                minimo_milesimos=produto.estoque_minimo_milesimos,
                ponto_pedido_milesimos=produto.ponto_pedido_milesimos,
            )
            resultado.append(
                {
                    "produto": produto,
                    "saldo_milesimos": saldo,
                    "status": status,
                    "valor_custo_centavos": saldo * produto.custo // 1000,
                }
            )
        return resultado

    def contar_por_status(self) -> dict[StatusEstoque, int]:
        contagem = dict.fromkeys(StatusEstoque, 0)
        for item in self.indicadores_estoque():
            if item["produto"].ativo:
                contagem[item["status"]] += 1
        return contagem
