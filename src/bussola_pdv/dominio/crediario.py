"""Crediário: geração de parcelas, vencimentos de fim de mês e aging.

Encargos (juros/multa) **não** são inventados aqui: o projeto exige política
aprovada pelo responsável. O módulo apenas guarda ``encargos_centavos`` quando
informados explicitamente e calcula saldo e atraso com data de referência.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from .dinheiro import Dinheiro
from .erros import ErroValidacao

MAXIMO_PARCELAS = 48


class StatusTitulo(StrEnum):
    ABERTO = "ABERTO"
    PARCIAL = "PARCIAL"
    PAGO = "PAGO"
    VENCIDO = "VENCIDO"
    CANCELADO = "CANCELADO"


def _ultimo_dia(ano: int, mes: int) -> int:
    return calendar.monthrange(ano, mes)[1]


def vencimento_mensal(base: date, indice: int) -> date:
    """Vencimento do mês ``indice`` após a base, travado no fim do mês.

    Exemplo: compra em 31/01 com 2 parcelas → 28/02 (ou 29 em bissexto) e 31/03.
    Nunca produz data inexistente nem "rola" para o mês seguinte.
    """
    if indice < 1:
        raise ErroValidacao("Índice de parcela deve ser maior que zero.")
    total_meses = base.month - 1 + indice
    ano = base.year + total_meses // 12
    mes = total_meses % 12 + 1
    dia = min(base.day, _ultimo_dia(ano, mes))
    return date(ano, mes, dia)


def dividir_em_parcelas(total: Dinheiro, parcelas: int) -> list[Dinheiro]:
    """Divide o total em parcelas iguais em centavos, com resíduo na primeira.

    A soma das parcelas é exatamente o total financiado (nenhum centavo perdido).
    Como o vencimento é crescente, o resíduo na primeira parcela é a prática mais
    conservadora para o cliente.
    """
    if parcelas < 1:
        raise ErroValidacao("Número de parcelas deve ser ao menos 1.")
    if parcelas > MAXIMO_PARCELAS:
        raise ErroValidacao(f"Máximo de {MAXIMO_PARCELAS} parcelas.")
    if total.negativo:
        raise ErroValidacao("Valor financiado não pode ser negativo.")
    base = total.centavos // parcelas
    resto = total.centavos - base * parcelas
    valores = [base + resto] + [base] * (parcelas - 1)
    return [Dinheiro(v) for v in valores]


@dataclass(frozen=True, slots=True)
class Parcela:
    numero: int
    total_parcelas: int
    vencimento: date
    principal: Dinheiro
    encargos: Dinheiro = Dinheiro(0)

    def __post_init__(self) -> None:
        if self.numero < 1 or self.total_parcelas < 1:
            raise ErroValidacao("Numeração de parcela inválida.")
        if self.numero > self.total_parcelas:
            raise ErroValidacao("Número da parcela excede o total de parcelas.")
        if self.principal.negativo or self.encargos.negativo:
            raise ErroValidacao("Principal e encargos não podem ser negativos.")

    @property
    def total(self) -> Dinheiro:
        return self.principal + self.encargos

    def saldo(self, recebido: Dinheiro) -> Dinheiro:
        if recebido.negativo:
            raise ErroValidacao("Recebimento não pode ser negativo.")
        saldo = self.total - recebido
        return saldo if not saldo.negativo else Dinheiro.zero()

    def excedente(self, recebido: Dinheiro) -> Dinheiro:
        """Valor recebido além do saldo — deve ser tratado, não estornado sozinho."""
        return max(Dinheiro(0), recebido - self.total)

    def status(self, recebido: Dinheiro, referencia: date) -> StatusTitulo:
        saldo = self.saldo(recebido)
        if saldo.centavos == 0:
            return StatusTitulo.PAGO
        if self.vencimento < referencia:
            return StatusTitulo.VENCIDO
        if recebido.centavos > 0:
            return StatusTitulo.PARCIAL
        return StatusTitulo.ABERTO


def gerar_parcelas(
    total: Dinheiro,
    quantidade: int,
    *,
    base: date,
    primeiro_vencimento: date | None = None,
) -> list[Parcela]:
    """Gera parcelas mensais a partir da data da venda (ou vencimento explícito)."""
    valores = dividir_em_parcelas(total, quantidade)
    parcelas: list[Parcela] = []
    for indice, valor in enumerate(valores, start=1):
        if primeiro_vencimento is None:
            vencimento = vencimento_mensal(base, indice)
        elif indice == 1:
            vencimento = primeiro_vencimento
        else:
            vencimento = vencimento_mensal(primeiro_vencimento, indice - 1)
        if vencimento <= base:
            raise ErroValidacao("Vencimento deve ser posterior à data da venda.")
        parcelas.append(
            Parcela(numero=indice, total_parcelas=quantidade, vencimento=vencimento, principal=valor)
        )
    return parcelas


# --- Aging e atraso ------------------------------------------------------------

FAIXAS_AGING: tuple[tuple[str, int, int | None], ...] = (
    ("A_VENCER", -10_000, 0),
    ("1_30", 1, 30),
    ("31_60", 31, 60),
    ("61_90", 61, 90),
    ("ACIMA_90", 91, None),
)


def dias_de_atraso(vencimento: date, referencia: date) -> int:
    """Dias corridos de atraso; negativo quando ainda não venceu."""
    return (referencia - vencimento).days


def faixa_aging(vencimento: date, referencia: date) -> str:
    dias = dias_de_atraso(vencimento, referencia)
    for nome, minimo, maximo in FAIXAS_AGING:
        if dias >= minimo and (maximo is None or dias <= maximo):
            return nome
    return "ACIMA_90"  # pragma: no cover - coberto pelas faixas


@dataclass(frozen=True, slots=True)
class AgingCliente:
    cliente_id: str
    faixas: dict[str, int]
    total_aberto: int
    vencido: int
    atraso_maximo_dias: int
    data_referencia: date


def calcular_aging(
    *,
    cliente_id: str,
    titulos: list[tuple[Parcela, Dinheiro]],  # (parcela, recebido)
    referencia: date,
) -> AgingCliente:
    """Aging por faixa, sempre com data de referência e denominador explícitos.

    Títulos quitados não entram. O total aberto é a soma dos saldos (principal +
    encargos - recebimentos), e ``vencido`` é a soma apenas dos saldos cujo
    vencimento é anterior à data de referência.
    """
    faixas = {nome: 0 for nome, _, _ in FAIXAS_AGING}
    total_aberto = 0
    vencido = 0
    atraso_maximo = 0
    for parcela, recebido in titulos:
        saldo = parcela.saldo(recebido)
        if saldo.centavos == 0:
            continue
        faixas[faixa_aging(parcela.vencimento, referencia)] += saldo.centavos
        total_aberto += saldo.centavos
        atraso = dias_de_atraso(parcela.vencimento, referencia)
        if atraso > 0:
            vencido += saldo.centavos
            atraso_maximo = max(atraso_maximo, atraso)
    return AgingCliente(
        cliente_id=cliente_id,
        faixas=faixas,
        total_aberto=total_aberto,
        vencido=vencido,
        atraso_maximo_dias=atraso_maximo,
        data_referencia=referencia,
    )


def proximo_vencimento(titulos: list[tuple[Parcela, Dinheiro]], referencia: date) -> date | None:
    abertos = [p.vencimento for p, r in titulos if p.saldo(r).centavos > 0]
    return min(abertos) if abertos else None


def vence_em(vencimento: date, referencia: date, dias: int = 7) -> bool:
    """Janela inclusiva de vencimentos (hoje + ``dias``)."""
    return referencia <= vencimento <= referencia + timedelta(days=dias)
