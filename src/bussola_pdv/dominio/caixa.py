"""Turno de caixa, movimentos de gaveta e conferência por denominação.

Fórmula única (docs/REGRAS_NEGOCIO.md)::

    esperado = fundo
             + vendas em dinheiro (valor aplicado)
             + recebimentos de títulos em dinheiro
             + suprimentos
             - sangrias
             - estornos em dinheiro

Cartão, PIX e crediário **não** entram no esperado da gaveta.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from .dinheiro import Dinheiro, arredondar_divisao
from .erros import ErroValidacao


class TipoMovimentoCaixa(StrEnum):
    VENDA_DINHEIRO = "VENDA_DINHEIRO"
    RECEBIMENTO_TITULO = "RECEBIMENTO_TITULO"
    SUPRIMENTO = "SUPRIMENTO"
    SANGRIA = "SANGRIA"
    ESTORNO_DINHEIRO = "ESTORNO_DINHEIRO"

    @property
    def sinal(self) -> int:
        return -1 if self in (TipoMovimentoCaixa.SANGRIA, TipoMovimentoCaixa.ESTORNO_DINHEIRO) else 1

    @property
    def rotulo(self) -> str:
        return {
            TipoMovimentoCaixa.VENDA_DINHEIRO: "Venda em dinheiro",
            TipoMovimentoCaixa.RECEBIMENTO_TITULO: "Recebimento de título",
            TipoMovimentoCaixa.SUPRIMENTO: "Suprimento",
            TipoMovimentoCaixa.SANGRIA: "Sangria",
            TipoMovimentoCaixa.ESTORNO_DINHEIRO: "Estorno em dinheiro",
        }[self]

    @property
    def exige_motivo(self) -> bool:
        return self in (
            TipoMovimentoCaixa.SANGRIA,
            TipoMovimentoCaixa.SUPRIMENTO,
            TipoMovimentoCaixa.ESTORNO_DINHEIRO,
        )

    @property
    def exige_autorizacao(self) -> bool:
        return self in (TipoMovimentoCaixa.SANGRIA, TipoMovimentoCaixa.ESTORNO_DINHEIRO)


@dataclass(frozen=True, slots=True)
class MovimentoCaixa:
    tipo: TipoMovimentoCaixa
    valor: Dinheiro
    motivo: str = ""
    origem_id: str = ""
    autorizador_id: str | None = None

    def __post_init__(self) -> None:
        if self.valor.negativo:
            raise ErroValidacao("Movimento de caixa usa valor positivo; o sinal vem do tipo.")
        if self.valor.centavos == 0:
            raise ErroValidacao("Movimento de caixa com valor zero não deve ser registrado.")
        if self.tipo.exige_motivo and not self.motivo.strip():
            raise ErroValidacao(f"{self.tipo.rotulo} exige motivo.")
        if self.tipo.exige_autorizacao and not self.autorizador_id:
            raise ErroValidacao(f"{self.tipo.rotulo} exige autorizador identificado.")

    @property
    def valor_assinado(self) -> Dinheiro:
        return self.valor * self.tipo.sinal


class StatusTurno(StrEnum):
    ABERTO = "ABERTO"
    FECHADO = "FECHADO"


@dataclass(frozen=True, slots=True)
class Turno:
    caixa_id: str
    operador_id: str
    fundo: Dinheiro
    aberto_em: datetime
    status: StatusTurno = StatusTurno.ABERTO
    fechado_em: datetime | None = None
    movimentos: tuple[MovimentoCaixa, ...] = ()

    def __post_init__(self) -> None:
        if self.fundo.negativo:
            raise ErroValidacao("Fundo de troco não pode ser negativo.")

    @property
    def aberto(self) -> bool:
        return self.status is StatusTurno.ABERTO

    def total_por_tipo(self, tipo: TipoMovimentoCaixa) -> Dinheiro:
        return sum((m.valor for m in self.movimentos if m.tipo is tipo), Dinheiro.zero())

    @property
    def esperado(self) -> Dinheiro:
        total = self.fundo
        for movimento in self.movimentos:
            total = total + movimento.valor_assinado
        return total

    def diferenca(self, contado: Dinheiro) -> Dinheiro:
        return contado - self.esperado

    def resumo(self, contado: Dinheiro) -> dict[str, object]:
        return {
            "fundo_centavos": self.fundo.centavos,
            "vendas_dinheiro_centavos": self.total_por_tipo(TipoMovimentoCaixa.VENDA_DINHEIRO).centavos,
            "recebimentos_centavos": self.total_por_tipo(TipoMovimentoCaixa.RECEBIMENTO_TITULO).centavos,
            "suprimentos_centavos": self.total_por_tipo(TipoMovimentoCaixa.SUPRIMENTO).centavos,
            "sangrias_centavos": self.total_por_tipo(TipoMovimentoCaixa.SANGRIA).centavos,
            "estornos_centavos": self.total_por_tipo(TipoMovimentoCaixa.ESTORNO_DINHEIRO).centavos,
            "esperado_centavos": self.esperado.centavos,
            "contado_centavos": contado.centavos,
            "diferenca_centavos": self.diferenca(contado).centavos,
        }


# --- Contagem por denominação --------------------------------------------------

DENOMINACOES_BRL: tuple[int, ...] = (
    20000, 10000, 5000, 2000, 1000,      # notas
    500, 200, 100, 50, 25, 10, 5, 1,      # moedas
)

ROTULOS_DENOMINACAO: dict[int, str] = {
    20000: "R$ 200,00",
    10000: "R$ 100,00",
    5000: "R$ 50,00",
    2000: "R$ 20,00",
    1000: "R$ 10,00",
    500: "R$ 5,00",
    200: "R$ 2,00",
    100: "R$ 1,00",
    50: "R$ 0,50",
    25: "R$ 0,25",
    10: "R$ 0,10",
    5: "R$ 0,05",
    1: "R$ 0,01",
}


@dataclass(frozen=True, slots=True)
class ContagemDenominacao:
    denominacao: int
    quantidade: int

    def __post_init__(self) -> None:
        if self.denominacao not in DENOMINACOES_BRL:
            raise ErroValidacao(f"Denominação desconhecida: {self.denominacao} centavos.")
        if self.quantidade < 0:
            raise ErroValidacao("Quantidade de cédulas/moedas não pode ser negativa.")

    @property
    def subtotal(self) -> Dinheiro:
        return Dinheiro(self.denominacao * self.quantidade)


def total_contagem(contagens: list[ContagemDenominacao]) -> Dinheiro:
    """Soma a contagem. Denominação repetida é erro de operação, não soma dupla."""
    vistas: set[int] = set()
    for contagem in contagens:
        if contagem.denominacao in vistas:
            raise ErroValidacao(
                ROTULOS_DENOMINACAO.get(contagem.denominacao, str(contagem.denominacao))
                + " aparece mais de uma vez na contagem."
            )
        vistas.add(contagem.denominacao)
    return sum((c.subtotal for c in contagens), Dinheiro.zero())


class ClassificacaoDiferenca(StrEnum):
    ZERO = "ZERO"
    ATE_LIMITE = "ATE_LIMITE"
    ACIMA_LIMITE = "ACIMA_LIMITE"


def classificar_diferenca(diferenca: Dinheiro, *, limite: Dinheiro = Dinheiro(500)) -> ClassificacaoDiferenca:
    """Política configurável de sinalização: zero, até R$ 5, acima de R$ 5."""
    if diferenca.centavos == 0:
        return ClassificacaoDiferenca.ZERO
    if diferenca.absoluto() <= limite:
        return ClassificacaoDiferenca.ATE_LIMITE
    return ClassificacaoDiferenca.ACIMA_LIMITE


def conferir_turno(turno: Turno, contagens: list[ContagemDenominacao]) -> dict[str, object]:
    """Conferência completa: contagem, esperado, diferença e sinalização."""
    contado = total_contagem(contagens)
    diferenca = turno.diferenca(contado)
    detalhe = turno.resumo(contado)
    detalhe["classificacao"] = classificar_diferenca(diferenca).value
    detalhe["contagens"] = [
        {
            "denominacao": c.denominacao,
            "rotulo": ROTULOS_DENOMINACAO[c.denominacao],
            "quantidade": c.quantidade,
            "subtotal_centavos": c.subtotal.centavos,
        }
        for c in sorted(contagens, key=lambda c: -c.denominacao)
    ]
    return detalhe


def fracionar_em_denominacoes(valor: Dinheiro) -> list[ContagemDenominacao]:
    """Converte um valor em sugestão de cédulas (usado em conferência assistida)."""
    restante = valor.centavos
    sugestao: list[ContagemDenominacao] = []
    for denominacao in DENOMINACOES_BRL:
        quantidade, restante = divmod(restante, denominacao)
        if quantidade:
            sugestao.append(ContagemDenominacao(denominacao, quantidade))
    return sugestao


def media_por_cupom(total: Dinheiro, cupons: int) -> Dinheiro:
    """Ticket médio com arredondamento meio-para-cima (evita divisão por zero)."""
    if cupons <= 0:
        return Dinheiro.zero()
    return Dinheiro(arredondar_divisao(total.centavos, cupons))
