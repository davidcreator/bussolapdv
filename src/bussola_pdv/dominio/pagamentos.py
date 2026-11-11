"""Formas de pagamento, split de até três formas e troco.

Princípios aplicados (docs/REGRAS_NEGOCIO.md):

* ``valor_entregue``, ``valor_aplicado`` e ``troco`` são campos distintos;
* troco só existe em dinheiro, nunca pode exceder o dinheiro recebido e nunca
  pode ser gerado por cartão/PIX (excesso eletrônico é erro, não crédito);
* ``soma(aplicado) == total`` da venda, em centavos;
* receber uma referência (NSU/PIX) **não** confirma o pagamento: o estado nasce
  ``PENDENTE`` e a confirmação é ato humano registrado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from .dinheiro import Dinheiro, Percentual
from .erros import PagamentoIncompleto, PagamentoInvalido, TrocoInvalido

MAXIMO_FORMAS_POR_VENDA = 3


class FormaPagamento(StrEnum):
    DINHEIRO = "DINHEIRO"
    PIX = "PIX"
    DEBITO = "DEBITO"
    CREDITO = "CREDITO"
    CREDITO_PARCELADO = "CREDITO_PARCELADO"
    TRANSFERENCIA = "TRANSFERENCIA"
    VALE = "VALE"
    CHEQUE = "CHEQUE"
    A_PRAZO = "A_PRAZO"

    @property
    def rotulo(self) -> str:
        return {
            FormaPagamento.DINHEIRO: "Dinheiro",
            FormaPagamento.PIX: "PIX",
            FormaPagamento.DEBITO: "Débito",
            FormaPagamento.CREDITO: "Crédito à vista",
            FormaPagamento.CREDITO_PARCELADO: "Crédito parcelado",
            FormaPagamento.TRANSFERENCIA: "Transferência",
            FormaPagamento.VALE: "Vale",
            FormaPagamento.CHEQUE: "Cheque",
            FormaPagamento.A_PRAZO: "A prazo (crediário)",
        }[self]

    @property
    def permite_troco(self) -> bool:
        return self is FormaPagamento.DINHEIRO

    @property
    def eletronico(self) -> bool:
        return self in (
            FormaPagamento.PIX,
            FormaPagamento.DEBITO,
            FormaPagamento.CREDITO,
            FormaPagamento.CREDITO_PARCELADO,
            FormaPagamento.TRANSFERENCIA,
        )

    @property
    def gera_titulo(self) -> bool:
        return self is FormaPagamento.A_PRAZO

    @property
    def entra_na_gaveta(self) -> bool:
        """Somente dinheiro físico compõe o esperado da gaveta."""
        return self is FormaPagamento.DINHEIRO


class StatusPagamento(StrEnum):
    PENDENTE = "PENDENTE"
    CONFIRMADO = "CONFIRMADO"
    ESTORNADO = "ESTORNADO"


@dataclass(frozen=True, slots=True)
class ConfiguracaoForma:
    """Configuração comercial da forma: taxa contratual e prazo de recebimento.

    A taxa é informativa para repasse da adquirente; ela **não** altera o valor
    aplicado ao cupom nem a dívida do cliente.
    """

    forma: FormaPagamento
    taxa: Percentual = field(default_factory=Percentual.zero)
    prazo_dias: int = 0
    ativo: bool = True

    def taxa_de(self, valor: Dinheiro) -> Dinheiro:
        return valor.aplicar_percentual(self.taxa)

    def valor_liquido(self, valor: Dinheiro) -> Dinheiro:
        return valor - self.taxa_de(valor)


@dataclass(frozen=True, slots=True)
class Pagamento:
    forma: FormaPagamento
    valor_aplicado: Dinheiro
    valor_entregue: Dinheiro
    status: StatusPagamento = StatusPagamento.PENDENTE
    referencia: str = ""
    bandeira: str = ""
    nsu: str = ""
    parcelas: int = 1
    confirmacao_manual: bool = False

    def __post_init__(self) -> None:
        if self.valor_aplicado.negativo or self.valor_entregue.negativo:
            raise PagamentoInvalido("Valores de pagamento não podem ser negativos.")
        if self.valor_aplicado.centavos == 0 and self.valor_entregue.centavos == 0:
            raise PagamentoInvalido("Linha de pagamento com valor zero não deve ser registrada.")
        if self.forma.permite_troco:
            if self.valor_entregue < self.valor_aplicado:
                raise TrocoInvalido("Dinheiro entregue é menor que o valor aplicado.")
        elif self.valor_entregue != self.valor_aplicado:
            raise TrocoInvalido(
                f"{self.forma.rotulo} não gera troco: valor entregue deve ser igual ao aplicado."
            )
        if self.parcelas < 1:
            raise PagamentoInvalido("Número de parcelas deve ser ao menos 1.")
        if self.forma is FormaPagamento.CREDITO_PARCELADO and self.parcelas < 2:
            raise PagamentoInvalido("Crédito parcelado exige duas ou mais parcelas.")
        if self.forma is not FormaPagamento.CREDITO_PARCELADO and self.parcelas > 1:
            raise PagamentoInvalido("Somente crédito parcelado aceita mais de uma parcela.")

    @property
    def troco(self) -> Dinheiro:
        if not self.forma.permite_troco:
            return Dinheiro.zero()
        return self.valor_entregue - self.valor_aplicado

    @property
    def confirmado(self) -> bool:
        return self.status is StatusPagamento.CONFIRMADO


def pagamento_dinheiro(valor_aplicado: Dinheiro, entregue: Dinheiro | None = None) -> Pagamento:
    """Dinheiro é confirmado no ato; o troco é calculado a partir do entregue."""
    entregue = entregue if entregue is not None else valor_aplicado
    if entregue < valor_aplicado:
        raise TrocoInvalido("Dinheiro entregue é menor que o valor a aplicar.")
    return Pagamento(
        forma=FormaPagamento.DINHEIRO,
        valor_aplicado=valor_aplicado,
        valor_entregue=entregue,
        status=StatusPagamento.CONFIRMADO,
        confirmacao_manual=True,
    )


def pagamento_eletronico(
    forma: FormaPagamento,
    valor: Dinheiro,
    *,
    confirmado: bool = False,
    referencia: str = "",
    bandeira: str = "",
    nsu: str = "",
    parcelas: int = 1,
) -> Pagamento:
    """Registra cartão/PIX. Sem integração validada, nasce PENDENTE."""
    if forma is FormaPagamento.DINHEIRO or forma is FormaPagamento.A_PRAZO:
        raise PagamentoInvalido("Use o construtor adequado para dinheiro ou crediário.")
    return Pagamento(
        forma=forma,
        valor_aplicado=valor,
        valor_entregue=valor,
        status=StatusPagamento.CONFIRMADO if confirmado else StatusPagamento.PENDENTE,
        referencia=referencia,
        bandeira=bandeira,
        nsu=nsu,
        parcelas=parcelas,
        confirmacao_manual=confirmado,
    )


def pagamento_a_prazo(valor: Dinheiro) -> Pagamento:
    """Crediário: gera títulos; não entra na gaveta nem é receita recebida."""
    return Pagamento(
        forma=FormaPagamento.A_PRAZO,
        valor_aplicado=valor,
        valor_entregue=valor,
        status=StatusPagamento.PENDENTE,
    )


@dataclass(frozen=True, slots=True)
class PlanoPagamento:
    """Coleção validada de pagamentos de uma venda (até três formas)."""

    pagamentos: tuple[Pagamento, ...]

    def __post_init__(self) -> None:
        ativos = tuple(p for p in self.pagamentos if p.valor_aplicado.centavos > 0)
        if not ativos:
            raise PagamentoInvalido("Informe ao menos uma forma de pagamento.")
        if len(ativos) > MAXIMO_FORMAS_POR_VENDA:
            raise PagamentoInvalido(f"Máximo de {MAXIMO_FORMAS_POR_VENDA} formas de pagamento por venda.")
        if sum(1 for p in ativos if p.forma.gera_titulo) > 1:
            raise PagamentoInvalido("Somente uma linha de crediário por venda.")
        object.__setattr__(self, "pagamentos", ativos)

    @property
    def total_aplicado(self) -> Dinheiro:
        return sum((p.valor_aplicado for p in self.pagamentos), Dinheiro.zero())

    @property
    def total_entregue(self) -> Dinheiro:
        return sum((p.valor_entregue for p in self.pagamentos), Dinheiro.zero())

    @property
    def troco(self) -> Dinheiro:
        return sum((p.troco for p in self.pagamentos), Dinheiro.zero())

    @property
    def dinheiro_aplicado(self) -> Dinheiro:
        return sum(
            (p.valor_aplicado for p in self.pagamentos if p.forma.entra_na_gaveta), Dinheiro.zero()
        )

    @property
    def tem_pendente_confirmacao(self) -> bool:
        return any(not p.confirmado for p in self.pagamentos)

    def validar_contra(self, total: Dinheiro) -> PlanoPagamento:
        """Confere cobertura integral do total, em centavos."""
        aplicado = self.total_aplicado
        if aplicado < total:
            falta = total - aplicado
            raise PagamentoIncompleto(
                f"Faltam {falta.formatado()} para cobrir o total de {total.formatado()}.",
                falta_centavos=falta.centavos,
            )
        if aplicado > total:
            excedente = aplicado - total
            raise PagamentoInvalido(
                f"Valores aplicados excedem o total em {excedente.formatado()}. "
                "Troco só é permitido em dinheiro, sobre o valor entregue."
            )
        if self.troco > self.dinheiro_entregue:
            raise TrocoInvalido("Troco não pode exceder o dinheiro efetivamente recebido.")
        return self

    @property
    def dinheiro_entregue(self) -> Dinheiro:
        return sum(
            (p.valor_entregue for p in self.pagamentos if p.forma.entra_na_gaveta), Dinheiro.zero()
        )

    @classmethod
    def de_pagamentos(cls, *pagamentos: Pagamento) -> PlanoPagamento:
        return cls(tuple(pagamentos))
