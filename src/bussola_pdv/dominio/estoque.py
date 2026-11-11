"""Movimentos de estoque, saldo e rateio de frete sem perder centavos."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .dinheiro import Dinheiro, Quantidade, arredondar_divisao
from .erros import ErroValidacao


class TipoMovimentoEstoque(StrEnum):
    ENTRADA = "ENTRADA"
    VENDA = "VENDA"
    DEVOLUCAO = "DEVOLUCAO"
    PERDA = "PERDA"
    AJUSTE = "AJUSTE"
    TRANSFERENCIA = "TRANSFERENCIA"
    ESTORNO = "ESTORNO"

    @property
    def sinal(self) -> int:
        """+1 entrada, -1 saída, 0 movimento de sinal livre (ajuste/transferência)."""
        if self in (
            TipoMovimentoEstoque.ENTRADA,
            TipoMovimentoEstoque.DEVOLUCAO,
            TipoMovimentoEstoque.ESTORNO,
        ):
            return 1
        if self in (TipoMovimentoEstoque.VENDA, TipoMovimentoEstoque.PERDA):
            return -1
        return 0

    @property
    def rotulo(self) -> str:
        return {
            TipoMovimentoEstoque.ENTRADA: "Entrada",
            TipoMovimentoEstoque.VENDA: "Venda",
            TipoMovimentoEstoque.DEVOLUCAO: "Devolução",
            TipoMovimentoEstoque.PERDA: "Perda",
            TipoMovimentoEstoque.AJUSTE: "Ajuste",
            TipoMovimentoEstoque.TRANSFERENCIA: "Transferência",
            TipoMovimentoEstoque.ESTORNO: "Estorno",
        }[self]


@dataclass(frozen=True, slots=True)
class MovimentoEstoque:
    produto_id: str
    tipo: TipoMovimentoEstoque
    quantidade: Quantidade
    origem_id: str = ""
    motivo: str = ""
    custo_unitario: Dinheiro | None = None

    def __post_init__(self) -> None:
        if self.quantidade.milesimos == 0:
            raise ErroValidacao("Movimento de estoque com quantidade zero não deve ser registrado.")
        if self.tipo.sinal == 0 and self.motivo.strip() == "":
            raise ErroValidacao("Ajuste e transferência exigem motivo.")

    @property
    def quantidade_assinada(self) -> int:
        """Quantidade em milésimos com sinal aplicado (positiva entra, negativa sai)."""
        if self.tipo.sinal == 0:
            return self.quantidade.milesimos
        return abs(self.quantidade.milesimos) * self.tipo.sinal


def calcular_saldo(inicial_milesimos: int, movimentos: list[MovimentoEstoque]) -> int:
    """Saldo = inicial + soma dos movimentos assinados. Sem dupla contagem."""
    return inicial_milesimos + sum(m.quantidade_assinada for m in movimentos)


# --- Rateio de frete -----------------------------------------------------------


class CriterioRateio(StrEnum):
    VALOR = "VALOR"
    QUANTIDADE = "QUANTIDADE"


def ratear(total: Dinheiro, pesos: list[int]) -> list[Dinheiro]:
    """Distribui ``total`` proporcionalmente aos pesos, com soma exata.

    Usa o método do maior resto: cada item recebe a parte inteira do rateio e os
    centavos restantes vão para os maiores restos (empate: menor índice). Assim a
    soma das parcelas é sempre igual ao total — requisito do prompt mestre.
    """
    if total.negativo:
        raise ErroValidacao("Frete a ratear não pode ser negativo; use estorno explícito.")
    if not pesos:
        raise ErroValidacao("Informe ao menos um item para ratear o frete.")
    if any(p < 0 for p in pesos):
        raise ErroValidacao("Pesos de rateio não podem ser negativos.")
    soma_pesos = sum(pesos)
    if soma_pesos == 0:
        # Sem base de valor/quantidade: distribui por igual, resto nos primeiros.
        base = [1] * len(pesos)
        soma_pesos = len(pesos)
    else:
        base = pesos
    partes: list[int] = []
    restos: list[tuple[int, int]] = []
    for indice, peso in enumerate(base):
        numerador = total.centavos * peso
        partes.append(numerador // soma_pesos)
        restos.append((numerador % soma_pesos, indice))
    distribuido = sum(partes)
    sobra = total.centavos - distribuido
    for _, indice in sorted(restos, key=lambda par: (-par[0], par[1]))[:sobra]:
        partes[indice] += 1
    return [Dinheiro(valor) for valor in partes]


@dataclass(frozen=True, slots=True)
class ItemEntrada:
    produto_id: str
    codigo: str
    quantidade: Quantidade
    custo_unitario: Dinheiro
    frete_rateado: Dinheiro = Dinheiro(0)

    @property
    def custo_total(self) -> Dinheiro:
        return self.custo_unitario.vezes_quantidade(self.quantidade) + self.frete_rateado


@dataclass(frozen=True, slots=True)
class EntradaMercadoria:
    """Compra de fornecedor com frete rateado e custo histórico por item."""

    fornecedor: str
    documento: str
    itens: tuple[ItemEntrada, ...]
    frete: Dinheiro = Dinheiro(0)
    criterio: CriterioRateio = CriterioRateio.VALOR

    def __post_init__(self) -> None:
        if not self.fornecedor.strip():
            raise ErroValidacao("Fornecedor é obrigatório na entrada.")
        if not self.itens:
            raise ErroValidacao("Entrada sem itens.")
        if self.frete.negativo:
            raise ErroValidacao("Frete não pode ser negativo.")

    def ratear_frete(self) -> tuple[ItemEntrada, ...]:
        """Devolve os itens com o frete alocado; soma alocada == frete total."""
        if self.frete.centavos == 0:
            return self.itens
        if self.criterio is CriterioRateio.VALOR:
            pesos = [item.quantidade.milesimos * item.custo_unitario.centavos for item in self.itens]
        else:
            pesos = [item.quantidade.milesimos for item in self.itens]
        partes = ratear(self.frete, pesos)
        return tuple(
            ItemEntrada(
                produto_id=item.produto_id,
                codigo=item.codigo,
                quantidade=item.quantidade,
                custo_unitario=item.custo_unitario,
                frete_rateado=parte,
            )
            for item, parte in zip(self.itens, partes, strict=True)
        )

    def custo_unitario_com_frete(self, item: ItemEntrada) -> Dinheiro:
        """Custo unitário histórico incluindo frete (base para margem futura)."""
        total = item.custo_total
        return Dinheiro(arredondar_divisao(total.centavos * Quantidade.ESCALA, item.quantidade.milesimos))

    @property
    def valor_total(self) -> Dinheiro:
        return sum((item.custo_total for item in self.ratear_frete()), Dinheiro.zero())
