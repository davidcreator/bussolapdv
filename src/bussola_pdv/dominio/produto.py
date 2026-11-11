"""Produto, unidades e indicadores de estoque/margem."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from .dinheiro import Percentual, Quantidade
from .documentos import validar_ean
from .erros import ErroValidacao


class Unidade(StrEnum):
    UN = "UN"
    KG = "KG"
    LT = "LT"
    CX = "CX"
    MT = "MT"
    DZ = "DZ"

    @property
    def escala(self) -> int:
        """Casas decimais aceitas para quantidade: unidade discreta vs. fracionável."""
        return 3 if self in (Unidade.KG, Unidade.LT, Unidade.MT) else 0

    @property
    def fracionavel(self) -> bool:
        return self.escala > 0


@dataclass(frozen=True, slots=True)
class Produto:
    codigo: str
    descricao: str
    preco: int  # centavos
    custo: int  # centavos
    categoria: str = ""
    unidade: Unidade = Unidade.UN
    codigo_barras: str | None = None
    estoque_minimo_milesimos: int = 0
    ponto_pedido_milesimos: int = 0
    fornecedor: str = ""
    ncm: str = ""
    ativo: bool = True
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        codigo = str(self.codigo or "").strip()
        if not codigo:
            raise ErroValidacao("Código do produto é obrigatório.")
        if len(codigo) > 40:
            raise ErroValidacao("Código do produto deve ter no máximo 40 caracteres.")
        if not str(self.descricao or "").strip():
            raise ErroValidacao("Descrição do produto é obrigatória.")
        if self.preco <= 0:
            raise ErroValidacao("Preço de venda deve ser maior que zero.")
        if self.custo < 0:
            raise ErroValidacao("Custo não pode ser negativo.")
        if self.estoque_minimo_milesimos < 0 or self.ponto_pedido_milesimos < 0:
            raise ErroValidacao("Estoque mínimo e ponto de pedido não podem ser negativos.")
        if self.codigo_barras:
            validar_ean(self.codigo_barras)

    # -- indicadores --------------------------------------------------------
    def margem(self) -> Percentual:
        """Margem sobre preço de venda (não é markup)."""
        if self.preco == 0:  # pragma: no cover - preço > 0 garantido no __post_init__
            return Percentual.zero()
        return Percentual((self.preco - self.custo) * Percentual.BASE // self.preco)

    def markup(self) -> Decimal:
        """Markup sobre custo, em Decimal, para exibição (não usar em dinheiro)."""
        if self.custo == 0:
            return Decimal(0)
        return ((Decimal(self.preco) / Decimal(self.custo)) - 1).quantize(Decimal("0.0001"))

    def quantidade(self, valor: str | int | Decimal) -> Quantidade:
        """Converte a quantidade informada respeitando a escala da unidade."""
        return Quantidade.de_unidades(valor, escala=self.unidade.escala)


class StatusEstoque(StrEnum):
    RUPTURA = "RUPTURA"
    BAIXO = "BAIXO"
    REPOSICAO = "REPOSICAO"
    OK = "OK"


def classificar_estoque(
    saldo_milesimos: int, *, minimo_milesimos: int, ponto_pedido_milesimos: int = 0
) -> StatusEstoque:
    """Classificação única usada por produtos, dashboard e relatórios.

    Ruptura inclui saldo negativo (política do projeto: nunca esconder negativo).
    Baixo é saldo positivo menor ou igual ao mínimo. Reposição é saldo acima do
    mínimo, mas menor ou igual ao ponto de pedido, quando configurado.
    """
    if saldo_milesimos <= 0:
        return StatusEstoque.RUPTURA
    if minimo_milesimos > 0 and saldo_milesimos <= minimo_milesimos:
        return StatusEstoque.BAIXO
    if ponto_pedido_milesimos > 0 and saldo_milesimos <= ponto_pedido_milesimos:
        return StatusEstoque.REPOSICAO
    return StatusEstoque.OK
