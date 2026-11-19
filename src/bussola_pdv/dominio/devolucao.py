"""Devolução e estorno de venda: o que voltou, por quê e para onde vai o dinheiro.

A devolução **não apaga a venda**: ela é um documento novo que aponta para a venda
original, com os itens que voltaram, o tipo de devolução (arrependimento, defeito,
garantia, erro de operação), o prazo aplicado e o destino do valor (dinheiro,
crédito no crediário ou troca). O caixa, o estoque e o crediário recebem
**movimentos compensatórios**, do mesmo jeito que o cancelamento — nunca há
sobrescrita de histórico.

Prazos: os números abaixo são o chão legal e a política da loja, não uma escolha do
programa. Arrependimento (CDC art. 49) e vício aparente (CDC art. 26) são mínimos
de lei; a garantia contratual do produto é cadastrada por produto (`garantia_dias`)
e só pode **aumentar** o prazo. Fora do prazo, a devolução continua possível, mas
exige autorização nominal de quem responde pela loja.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from uuid import uuid4

from .dinheiro import Dinheiro, Quantidade
from .erros import ErroValidacao


class TipoDevolucao(StrEnum):
    """Motivo da devolução — muda o prazo e o que se exige na hora."""

    ARREPENDIMENTO = "ARREPENDIMENTO"
    DEFEITO = "DEFEITO"
    GARANTIA = "GARANTIA"
    ERRO_OPERACIONAL = "ERRO_OPERACIONAL"

    @property
    def rotulo(self) -> str:
        return {
            TipoDevolucao.ARREPENDIMENTO: "Arrependimento (desistiu da compra)",
            TipoDevolucao.DEFEITO: "Defeito ou vício do produto",
            TipoDevolucao.GARANTIA: "Garantia do produto",
            TipoDevolucao.ERRO_OPERACIONAL: "Erro de operação (item ou cobrança errada)",
        }[self]

    @property
    def ajuda(self) -> str:
        return {
            TipoDevolucao.ARREPENDIMENTO: "Prazo legal de 7 dias para compra fora do balcão.",
            TipoDevolucao.DEFEITO: "Vício aparente: prazo legal de 90 dias.",
            TipoDevolucao.GARANTIA: "Prazo do cadastro do produto; o que for maior prevalece.",
            TipoDevolucao.ERRO_OPERACIONAL: "Sem prazo: cobrança ou item errado se corrige sempre.",
        }[self]


class DestinoDevolucao(StrEnum):
    """Para onde vai o valor devolvido."""

    DINHEIRO = "DINHEIRO"
    CREDITO_CREDIARIO = "CREDITO_CREDIARIO"
    TROCA = "TROCA"

    @property
    def rotulo(self) -> str:
        return {
            DestinoDevolucao.DINHEIRO: "Dinheiro na gaveta (exige caixa aberto)",
            DestinoDevolucao.CREDITO_CREDIARIO: "Abater parcelas do crediário",
            DestinoDevolucao.TROCA: "Troca de mercadoria (o valor fica na nova venda)",
        }[self]


@dataclass(frozen=True, slots=True)
class ItemDevolvido:
    """Item que volta, com o valor unitário praticado na venda original."""

    produto_id: str
    codigo: str
    descricao: str
    quantidade: Quantidade
    valor_unitario: Dinheiro
    venda_item_sequencia: int = 0

    def __post_init__(self) -> None:
        if self.quantidade.milesimos <= 0:
            raise ErroValidacao("Quantidade devolvida deve ser maior que zero.")
        if self.valor_unitario.centavos < 0:
            raise ErroValidacao("Valor unitário devolvido não pode ser negativo.")

    @property
    def total(self) -> Dinheiro:
        """Valor devolvido do item, arredondado ao centavo (meio para cima)."""
        bruto = self.valor_unitario.centavos * self.quantidade.milesimos
        return Dinheiro((bruto + 500) // 1000)


def total_devolvido(itens: tuple[ItemDevolvido, ...] | list[ItemDevolvido]) -> Dinheiro:
    return Dinheiro(sum(item.total.centavos for item in itens))


# --------------------------------------------------------------------- prazos
@dataclass(frozen=True, slots=True)
class PoliticaDevolucao:
    """Prazos que a loja aceita sem discussão. Fora disso, autorização.

    Os padrões seguem o CDC (7 dias de arrependimento, 90 dias de vício) e podem
    ser configurados para menos, nunca para menos que a lei — a tela avisa quando
    o parâmetro fica abaixo do mínimo legal.
    """

    arrependimento_dias: int = 7
    defeito_dias: int = 90
    garantia_padrao_dias: int = 0

    def prazo_do_tipo(self, tipo: TipoDevolucao, *, garantia_produto_dias: int = 0) -> int:
        """Dias permitidos para este tipo, considerando a garantia do produto."""
        if tipo is TipoDevolucao.ARREPENDIMENTO:
            return max(0, self.arrependimento_dias)
        if tipo is TipoDevolucao.DEFEITO:
            return max(0, self.defeito_dias)
        if tipo is TipoDevolucao.GARANTIA:
            return max(self.garantia_padrao_dias, garantia_produto_dias, 0)
        return -1  # ERRO_OPERACIONAL: sem prazo (sempre cabe corrigir)


@dataclass(frozen=True, slots=True)
class AvaliacaoDePrazo:
    dentro_do_prazo: bool
    dias_desde_venda: int
    limite_dias: int
    motivo: str

    @property
    def exige_autorizacao(self) -> bool:
        return not self.dentro_do_prazo


def avaliar_prazo(
    tipo: TipoDevolucao,
    *,
    data_venda: date,
    data_devolucao: date,
    politica: PoliticaDevolucao,
    garantia_produto_dias: int = 0,
) -> AvaliacaoDePrazo:
    """Diz se a devolução cabe no prazo do tipo — e por quê quando não cabe."""
    dias = max(0, (data_devolucao - data_venda).days)
    limite = politica.prazo_do_tipo(tipo, garantia_produto_dias=garantia_produto_dias)
    if limite < 0:
        return AvaliacaoDePrazo(
            dentro_do_prazo=True,
            dias_desde_venda=dias,
            limite_dias=-1,
            motivo="Erro de operação não tem prazo: corrigir é sempre possível.",
        )
    if dias <= limite:
        restantes = limite - dias
        return AvaliacaoDePrazo(
            dentro_do_prazo=True,
            dias_desde_venda=dias,
            limite_dias=limite,
            motivo=f"Dentro do prazo: faltam {restantes} dia(s) dos {limite} do tipo.",
        )
    return AvaliacaoDePrazo(
        dentro_do_prazo=False,
        dias_desde_venda=dias,
        limite_dias=limite,
        motivo=(
            f"Fora do prazo: {dias} dia(s) desde a venda, limite de {limite} para "
            f"{tipo.rotulo}. Exige autorização de quem responde pela loja."
        ),
    )


# ------------------------------------------------------------------ documento
@dataclass(frozen=True, slots=True)
class Devolucao:
    """Documento de devolução já validado, pronto para gravação."""

    venda_id: str
    tipo: TipoDevolucao
    destino: DestinoDevolucao
    motivo: str
    itens: tuple[ItemDevolvido, ...]
    operador_id: str
    dias_desde_venda: int = 0
    fora_do_prazo: bool = False
    estoque_devolvido: bool = True
    autorizador_id: str | None = None
    turno_id: str | None = None
    observacoes: str = ""
    dinheiro_centavos: int = 0
    credito_centavos: int = 0
    chave_idempotencia: str = field(default_factory=lambda: str(uuid4()))
    id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        if not self.itens:
            raise ErroValidacao("Devolução precisa de pelo menos um item.")
        if not str(self.motivo or "").strip():
            raise ErroValidacao("Devolução exige motivo: é o que explica o estorno depois.")
        if self.fora_do_prazo and not self.autorizador_id:
            raise ErroValidacao("Devolução fora do prazo exige autorizador identificado.")
        if self.destino is DestinoDevolucao.DINHEIRO and self.dinheiro_centavos < 0:
            raise ErroValidacao("Valor devolvido em dinheiro não pode ser negativo.")
        if self.destino is DestinoDevolucao.CREDITO_CREDIARIO and self.credito_centavos < 0:
            raise ErroValidacao("Valor abatido no crediário não pode ser negativo.")

    @property
    def total(self) -> Dinheiro:
        return total_devolvido(self.itens)

    @property
    def rotulo(self) -> str:
        return f"DEV-{self.id[:8].upper()}"


__all__ = [
    "AvaliacaoDePrazo",
    "DestinoDevolucao",
    "Devolucao",
    "ItemDevolvido",
    "PoliticaDevolucao",
    "TipoDevolucao",
    "avaliar_prazo",
    "total_devolvido",
]
