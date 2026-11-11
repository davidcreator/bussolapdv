"""Carrinho, itens, descontos e totais da venda.

Nenhum widget, nenhum banco: o cálculo do cupom é uma função pura do carrinho e
das políticas. A gravação atômica fica em ``aplicacao.pdv``.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum

from .dinheiro import Dinheiro, Percentual, Quantidade, arredondar_divisao
from .erros import CarrinhoVazio, ErroValidacao, EstoqueInsuficiente
from .produto import Produto, Unidade


class StatusVenda(StrEnum):
    CONCLUIDA = "CONCLUIDA"
    CANCELADA = "CANCELADA"


class ExigenciaDesconto(StrEnum):
    PERMITIDO = "PERMITIDO"
    REQUER_GERENTE = "REQUER_GERENTE"
    PROIBIDO = "PROIBIDO"


@dataclass(frozen=True, slots=True)
class PoliticaDesconto:
    """Limites de desconto por perfil, em percentual sobre o subtotal bruto."""

    limite_operador: Percentual = Percentual(500)  # 5%
    limite_gerente: Percentual = Percentual(1500)  # 15%
    desconto_maximo: Percentual = Percentual(10000)  # 100%

    def classificar(self, percentual: Percentual) -> ExigenciaDesconto:
        if percentual > self.desconto_maximo:
            return ExigenciaDesconto.PROIBIDO
        if percentual <= self.limite_operador:
            return ExigenciaDesconto.PERMITIDO
        if percentual <= self.limite_gerente:
            return ExigenciaDesconto.REQUER_GERENTE
        return ExigenciaDesconto.PROIBIDO


@dataclass(frozen=True, slots=True)
class ItemCarrinho:
    produto_id: str
    codigo: str
    descricao: str
    unidade: Unidade
    quantidade: Quantidade
    preco_unitario: Dinheiro
    custo_unitario: Dinheiro
    desconto: Dinheiro = field(default_factory=Dinheiro.zero)

    def __post_init__(self) -> None:
        if not self.quantidade.positivo():
            raise ErroValidacao("Quantidade do item deve ser maior que zero.")
        if self.preco_unitario.centavos < 0 or self.custo_unitario.centavos < 0:
            raise ErroValidacao("Preço e custo não podem ser negativos.")
        if self.desconto.centavos < 0:
            raise ErroValidacao("Desconto do item não pode ser negativo.")
        if self.desconto > self.bruto:
            raise ErroValidacao("Desconto do item não pode exceder o valor bruto do item.")

    @classmethod
    def do_produto(
        cls,
        produto: Produto,
        quantidade: str | int,
        *,
        desconto: Dinheiro | None = None,
    ) -> ItemCarrinho:
        return cls(
            produto_id=produto.id,
            codigo=produto.codigo,
            descricao=produto.descricao,
            unidade=produto.unidade,
            quantidade=produto.quantidade(quantidade),
            preco_unitario=Dinheiro(produto.preco),
            custo_unitario=Dinheiro(produto.custo),
            desconto=desconto or Dinheiro.zero(),
        )

    @property
    def bruto(self) -> Dinheiro:
        return self.preco_unitario.vezes_quantidade(self.quantidade)

    @property
    def total(self) -> Dinheiro:
        return self.bruto - self.desconto

    @property
    def custo_total(self) -> Dinheiro:
        return self.custo_unitario.vezes_quantidade(self.quantidade)


@dataclass(frozen=True, slots=True)
class TotaisVenda:
    subtotal: Dinheiro
    desconto_itens: Dinheiro
    desconto_cupom: Dinheiro
    acrescimo: Dinheiro
    total: Dinheiro
    custo_total: Dinheiro

    @property
    def desconto_total(self) -> Dinheiro:
        return self.desconto_itens + self.desconto_cupom


class Carrinho:
    """Carrinho de compras com consolidação por produto.

    Consolidar por produto evita a dupla baixa de estoque quando o operador
    passa o mesmo item duas vezes — um dos defeitos do protótipo em planilha.
    """

    def __init__(self) -> None:
        self._itens: list[ItemCarrinho] = []

    def __len__(self) -> int:
        return len(self._itens)

    def __iter__(self) -> Iterator[ItemCarrinho]:
        return iter(self._itens)

    @property
    def itens(self) -> tuple[ItemCarrinho, ...]:
        return tuple(self._itens)

    @property
    def vazio(self) -> bool:
        return not self._itens

    def adicionar(self, produto: Produto, quantidade: str | int, *, desconto: Dinheiro | None = None) -> None:
        nova = ItemCarrinho.do_produto(produto, quantidade, desconto=desconto)
        for indice, item in enumerate(self._itens):
            if item.produto_id == nova.produto_id:
                consolidado = ItemCarrinho(
                    produto_id=item.produto_id,
                    codigo=item.codigo,
                    descricao=item.descricao,
                    unidade=item.unidade,
                    quantidade=item.quantidade + nova.quantidade,
                    preco_unitario=nova.preco_unitario,  # preço vigente prevalece
                    custo_unitario=item.custo_unitario,
                    desconto=item.desconto + nova.desconto,
                )
                self._itens[indice] = consolidado
                return
        self._itens.append(nova)

    def remover(self, produto_id: str) -> None:
        self._itens = [item for item in self._itens if item.produto_id != produto_id]

    def limpar(self) -> None:
        self._itens.clear()

    def totais(
        self, *, desconto_cupom: Dinheiro | None = None, acrescimo: Dinheiro | None = None
    ) -> TotaisVenda:
        if self.vazio:
            raise CarrinhoVazio("Carrinho vazio: lance ao menos um item para calcular o total.")
        cupom = desconto_cupom or Dinheiro.zero()
        extra = acrescimo or Dinheiro.zero()
        if cupom.centavos < 0 or extra.centavos < 0:
            raise ErroValidacao("Desconto e acréscimo não podem ser negativos.")
        subtotal = sum((item.bruto for item in self._itens), Dinheiro.zero())
        desconto_itens = sum((item.desconto for item in self._itens), Dinheiro.zero())
        total = subtotal - desconto_itens - cupom + extra
        if total.negativo:
            raise ErroValidacao("Desconto maior que o valor da venda.")
        return TotaisVenda(
            subtotal=subtotal,
            desconto_itens=desconto_itens,
            desconto_cupom=cupom,
            acrescimo=extra,
            total=total,
            custo_total=sum((item.custo_total for item in self._itens), Dinheiro.zero()),
        )

    def percentual_desconto(self, totais: TotaisVenda) -> Percentual:
        """Percentual efetivo de desconto sobre o subtotal bruto (base da política)."""
        if totais.subtotal.centavos <= 0:
            return Percentual.zero()
        return Percentual(
            arredondar_divisao(
                totais.desconto_total.centavos * Percentual.BASE, totais.subtotal.centavos
            )
        )

    def verificar_estoque(self, saldos: dict[str, int], *, permitir_negativo: bool = False) -> None:
        """Confere saldo disponível (em milésimos) por produto.

        A checagem aqui é a mesma repetida dentro da transação de finalização;
        esta serve para avisar o operador antes de ele confirmar.
        """
        faltantes: list[dict] = []
        for item in self._itens:
            saldo = saldos.get(item.produto_id)
            if saldo is None:
                saldo = 0
            if item.quantidade.milesimos > saldo:
                faltantes.append(
                    {
                        "produto_id": item.produto_id,
                        "codigo": item.codigo,
                        "descricao": item.descricao,
                        "pedido_milesimos": item.quantidade.milesimos,
                        "saldo_milesimos": saldo,
                    }
                )
        if faltantes and not permitir_negativo:
            nomes = ", ".join(f"{f['codigo']} ({f['descricao']})" for f in faltantes)
            raise EstoqueInsuficiente(f"Estoque insuficiente para: {nomes}.", detalhe={"itens": faltantes})
