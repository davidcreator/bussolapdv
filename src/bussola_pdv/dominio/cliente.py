"""Cliente e política de crédito (somente o que é cálculo, não o que é jurídico)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from .documentos import validar_documento
from .erros import ErroValidacao


@dataclass(frozen=True, slots=True)
class Cliente:
    nome: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    documento: str | None = None
    tipo_documento: str | None = None
    limite_credito: int = 0  # centavos
    ativo: bool = True
    observacoes: str = ""

    def __post_init__(self) -> None:
        if not str(self.nome or "").strip():
            raise ErroValidacao("Nome do cliente é obrigatório.")
        if self.limite_credito < 0:
            raise ErroValidacao("Limite de crédito não pode ser negativo.")
        if self.documento:
            tipo, normalizado = validar_documento(self.documento, self.tipo_documento)
            object.__setattr__(self, "tipo_documento", tipo)
            object.__setattr__(self, "documento", normalizado)

    def documento_mascarado(self) -> str:
        """Exibição minimizada (LGPD): mostra apenas os últimos 4 caracteres."""
        if not self.documento:
            return ""
        return "*" * (len(self.documento) - 4) + self.documento[-4:]


@dataclass(frozen=True, slots=True)
class SituacaoCredito:
    """Resultado do cálculo de limite. Nunca confirma identidade, só aritMética."""

    limite: int
    saldo_devedor: int
    vencido: int
    atraso_maximo_dias: int

    @property
    def disponivel(self) -> int:
        return max(0, self.limite - self.saldo_devedor)

    def permite(self, valor: int) -> bool:
        return valor <= self.disponivel


def avaliar_credito(
    *,
    limite: int,
    saldo_devedor: int,
    vencido: int,
    atraso_maximo_dias: int,
    dias_bloqueio_atraso: int,
    valor_pretendido: int,
    autorizado_por_gerente: bool = False,
) -> SituacaoCredito:
    """Aplica a política de crédito parametrizada.

    Bloqueia quando há atraso acima do limite configurado ou quando o saldo
    devedor somado ao novo valor supera o limite, salvo autorização explícita
    de gerente (que fica registrada em auditoria pelo caso de uso).
    """
    if valor_pretendido < 0:
        raise ErroValidacao("Valor pretendido não pode ser negativo.")
    situacao = SituacaoCredito(
        limite=limite,
        saldo_devedor=saldo_devedor,
        vencido=vencido,
        atraso_maximo_dias=atraso_maximo_dias,
    )
    from .erros import ClienteBloqueadoPorAtraso, LimiteCreditoExcedido

    if dias_bloqueio_atraso > 0 and atraso_maximo_dias > dias_bloqueio_atraso and not autorizado_por_gerente:
        raise ClienteBloqueadoPorAtraso(
            f"Cliente com atraso de {atraso_maximo_dias} dias (limite {dias_bloqueio_atraso}).",
            detalhe={"atraso_maximo_dias": atraso_maximo_dias},
        )
    if not situacao.permite(valor_pretendido) and not autorizado_por_gerente:
        raise LimiteCreditoExcedido(
            "Venda a prazo excede o limite disponível do cliente.",
            detalhe={"disponivel_centavos": situacao.disponivel, "pretendido_centavos": valor_pretendido},
        )
    return situacao
