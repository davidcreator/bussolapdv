"""Dinheiro, percentuais e quantidades — sem `float`, nunca.

Convenções fixadas para todo o projeto (ver docs/DECISOES.md, ADR-001):

* dinheiro é sempre ``int`` de centavos, encapsulado em :class:`Dinheiro`;
* percentual é sempre ``int`` de pontos-base (1% = 100 bp) em :class:`Percentual`;
* quantidade é sempre ``int`` escalonado (milésimos) em :class:`Quantidade`;
* todo arredondamento é explícito, meio-para-cima (ROUND_HALF_UP), feito em
  inteiros. Não há `float` em nenhum ponto deste módulo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from .erros import ErroValidacao

_ESPACOS = str.maketrans("", "", " \u00a0\u202f")


def arredondar_divisao(numerador: int, denominador: int) -> int:
    """Divide inteiros arredondando meio-para-cima, inclusive para negativos.

    >>> arredondar_divisao(5, 2)
    3
    >>> arredondar_divisao(2499, 1000)
    2
    >>> arredondar_divisao(-5, 2)
    -3
    """
    if denominador == 0:
        raise ZeroDivisionError("denominador zero")
    if denominador < 0:
        numerador, denominador = -numerador, -denominador
    if numerador >= 0:
        return (numerador * 2 + denominador) // (denominador * 2)
    return -((-numerador * 2 + denominador) // (denominador * 2))


@dataclass(frozen=True, order=True, slots=True)
class Dinheiro:
    """Valor monetário imutável em centavos."""

    centavos: int

    def __post_init__(self) -> None:
        if not isinstance(self.centavos, int) or isinstance(self.centavos, bool):
            raise ErroValidacao("Dinheiro exige centavos inteiros (sem float).")

    # -- construção ---------------------------------------------------------
    @classmethod
    def zero(cls) -> Dinheiro:
        return cls(0)

    @classmethod
    def de_reais(cls, reais: int | str | Decimal) -> Dinheiro:
        """Converte reais para centavos com arredondamento meio-para-cima.

        Aceita ``Decimal`` (preferido) ou texto. ``float`` é recusado de
        propósito: a conversão binária introduz erros de centavo.
        """
        if isinstance(reais, float):
            raise ErroValidacao("Use Decimal ou texto para valores monetários; float não é aceito.")
        try:
            valor = Decimal(reais) if not isinstance(reais, Decimal) else reais
        except (InvalidOperation, ValueError) as exc:  # pragma: no cover - defensivo
            raise ErroValidacao(f"Valor monetário inválido: {reais!r}") from exc
        return cls(int((valor * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)))

    @classmethod
    def de_texto(cls, texto: str) -> Dinheiro:
        """Interpreta texto do operador em pt-BR: ``"1.234,56"``, ``"27"``, ``"R$ 0,05"``."""
        if texto is None or str(texto).strip() == "":
            raise ErroValidacao("Informe um valor monetário.")
        bruto = str(texto).translate(_ESPACOS).strip()
        bruto = re.sub(r"(?i)^r\$", "", bruto)
        negativo = bruto.startswith("-")
        bruto = bruto.lstrip("+-")
        if "," in bruto:
            bruto = bruto.replace(".", "").replace(",", ".")
        elif bruto.count(".") == 1 and len(bruto.split(".")[1]) == 3:
            # "1.234" no padrão pt-BR é milhar, não decimal.
            bruto = bruto.replace(".", "")
        if not re.fullmatch(r"\d+(\.\d+)?", bruto):
            raise ErroValidacao(f"Valor monetário inválido: {texto!r}")
        valor = cls.de_reais(Decimal(bruto))
        return -valor if negativo else valor

    # -- conversões ---------------------------------------------------------
    def reais(self) -> Decimal:
        return (Decimal(self.centavos) / 100).quantize(Decimal("0.01"))

    @property
    def negativo(self) -> bool:
        return self.centavos < 0

    def absoluto(self) -> Dinheiro:
        return Dinheiro(abs(self.centavos))

    # -- formatação ---------------------------------------------------------
    def formatado(self) -> str:
        """Formata em pt-BR: ``R$ 1.234,56`` (com sinal para negativos)."""
        inteiro, _, decimal = f"{abs(self.centavos) / 100:.2f}".partition(".")
        grupos = f"{int(inteiro):,}".replace(",", ".")
        sinal = "-" if self.centavos < 0 else ""
        return f"{sinal}R$ {grupos},{decimal}"

    def __str__(self) -> str:
        return self.formatado()

    # -- aritmética ---------------------------------------------------------
    def __add__(self, outro: Dinheiro) -> Dinheiro:
        if not isinstance(outro, Dinheiro):
            return NotImplemented
        return Dinheiro(self.centavos + outro.centavos)

    def __sub__(self, outro: Dinheiro) -> Dinheiro:
        if not isinstance(outro, Dinheiro):
            return NotImplemented
        return Dinheiro(self.centavos - outro.centavos)

    def __neg__(self) -> Dinheiro:
        return Dinheiro(-self.centavos)

    def __mul__(self, fator: int) -> Dinheiro:
        if not isinstance(fator, int) or isinstance(fator, bool):
            return NotImplemented
        return Dinheiro(self.centavos * fator)

    __rmul__ = __mul__

    def vezes_quantidade(self, quantidade: Quantidade) -> Dinheiro:
        """Preço unitário × quantidade escalonada, arredondando meio-para-cima."""
        return Dinheiro(arredondar_divisao(self.centavos * quantidade.milesimos, quantidade.ESCALA))

    def aplicar_percentual(self, percentual: Percentual) -> Dinheiro:
        """Aplica percentual exato (pontos-base) com arredondamento meio-para-cima."""
        return Dinheiro(arredondar_divisao(self.centavos * percentual.bp, Percentual.BASE))

    def limitado_a(self, piso: Dinheiro, teto: Dinheiro) -> Dinheiro:
        return max(piso, min(teto, self))

    def proporcional(self, parte: int, total: int) -> Dinheiro:
        """Fatia deste valor na proporção ``parte/total`` (rateios)."""
        if total <= 0:
            raise ErroValidacao("Denominador de rateio deve ser positivo.")
        return Dinheiro(arredondar_divisao(self.centavos * parte, total))


@dataclass(frozen=True, order=True, slots=True)
class Percentual:
    """Percentual exato em pontos-base: 1% = 100 bp, 0,01% = 1 bp."""

    bp: int
    BASE = 10_000

    def __post_init__(self) -> None:
        if not isinstance(self.bp, int) or isinstance(self.bp, bool):
            raise ErroValidacao("Percentual exige pontos-base inteiros.")
        if self.bp < 0:
            raise ErroValidacao("Percentual não pode ser negativo.")

    @classmethod
    def de_porcento(cls, valor: int | str | Decimal) -> Percentual:
        """``"5%"``, ``"5"``, ``"5,5"`` e ``Decimal("5.5")`` viram 500/550 bp."""
        if isinstance(valor, float):
            raise ErroValidacao("Percentual não aceita float.")
        bruto = str(valor).translate(_ESPACOS).strip().replace("%", "").replace(",", ".")
        try:
            decimal = Decimal(bruto)
        except InvalidOperation as exc:
            raise ErroValidacao(f"Percentual inválido: {valor!r}") from exc
        if decimal < 0:
            raise ErroValidacao("Percentual não pode ser negativo.")
        if decimal > 100:
            raise ErroValidacao("Percentual não pode exceder 100%.")
        return cls(int((decimal * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)))

    @classmethod
    def zero(cls) -> Percentual:
        return cls(0)

    def formatado(self) -> str:
        return f"{(Decimal(self.bp) / 100).quantize(Decimal('0.01'))}%".replace(".", ",")

    def __str__(self) -> str:
        return self.formatado()


@dataclass(frozen=True, order=True, slots=True)
class Quantidade:
    """Quantidade escalonada em milésimos (1 unidade = 1000)."""

    milesimos: int
    ESCALA = 1000

    def __post_init__(self) -> None:
        if not isinstance(self.milesimos, int) or isinstance(self.milesimos, bool):
            raise ErroValidacao("Quantidade exige inteiro escalonado.")

    @classmethod
    def de_unidades(cls, valor: int | str | Decimal, *, escala: int = 3) -> Quantidade:
        """Converte 2, 0.5, "1,250" em milésimos, respeitando a escala do produto."""
        if isinstance(valor, float):
            raise ErroValidacao("Quantidade não aceita float; use Decimal ou texto.")
        texto = str(valor).translate(_ESPACOS).strip().replace(",", ".")
        try:
            decimal = Decimal(texto)
        except InvalidOperation as exc:
            raise ErroValidacao(f"Quantidade inválida: {valor!r}") from exc
        if decimal < 0:
            raise ErroValidacao("Quantidade não pode ser negativa.")
        expoente = decimal.as_tuple().exponent
        casas = -expoente if isinstance(expoente, int) and expoente < 0 else 0
        if casas > escala:
            raise ErroValidacao(
                f"Quantidade com {casas} casas decimais excede a precisão de {escala} do produto."
            )
        return cls(int((decimal * cls.ESCALA).quantize(Decimal("1"), rounding=ROUND_HALF_UP)))

    @classmethod
    def zero(cls) -> Quantidade:
        return cls(0)

    def formatada(self) -> str:
        texto = f"{Decimal(self.milesimos) / self.ESCALA:.3f}".rstrip("0").rstrip(".")
        return texto.replace(".", ",")

    def __str__(self) -> str:
        return self.formatada()

    def __add__(self, outro: Quantidade) -> Quantidade:
        return Quantidade(self.milesimos + outro.milesimos)

    def __sub__(self, outro: Quantidade) -> Quantidade:
        return Quantidade(self.milesimos - outro.milesimos)

    def __neg__(self) -> Quantidade:
        return Quantidade(-self.milesimos)

    def positivo(self) -> bool:
        return self.milesimos > 0
