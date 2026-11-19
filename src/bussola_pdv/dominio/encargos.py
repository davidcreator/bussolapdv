"""Calculadora de encargos por atraso — **base**, ainda não aplicada na cobrança.

Existe porque cobrar juros "de cabeça" é o que a caderneta fazia. A regra mora
aqui, em função pura e testável, e o dia em que a loja decidir cobrar basta ligar
o resultado ao título — sem espalhar aritmética de dinheiro pela tela.

Modelo (o mais comum no varejo brasileiro e o mais fácil de explicar ao cliente):

* **multa** de mora, uma vez, em percentual sobre o principal em atraso;
* **juros** de mora proporcionais aos dias de atraso, a partir do dia seguinte ao
  vencimento, calculados sobre o principal (juros simples);
* **carência** de dias antes de qualquer encargo;
* tudo em inteiros (centavos e pontos-base), com arredondamento meio-para-cima no
  fim de cada parcela do cálculo — nunca float.

O que **não** está aqui, de propósito: correção monetária por índice, IOF, multa
contratual punitiva e negociação de dívida. São decisões comerciais/jurídicas
(pendência P3) e entram como parâmetro novo quando alguém decidir — não como
número inventado pelo programa.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .dinheiro import Dinheiro, Percentual
from .erros import ErroValidacao


@dataclass(frozen=True, slots=True)
class PoliticaEncargos:
    """Padrões conservadores: 2% de multa e 1% ao mês de juros de mora.

    Ambos são configuráveis; a política existe separada do cálculo para que o
    teste possa provar a fórmula sem depender de parâmetro de banco.
    """

    multa: Percentual = Percentual(200)  # 2,00%
    juros_mes: Percentual = Percentual(100)  # 1,00% ao mês
    carencia_dias: int = 0

    def __post_init__(self) -> None:
        if self.multa.bp < 0 or self.juros_mes.bp < 0:
            raise ErroValidacao("Multa e juros não podem ser negativos.")
        if self.carencia_dias < 0:
            raise ErroValidacao("Carência não pode ser negativa.")

    #: Mês comercial usado na proporção dos juros (Padrão do varejo: 30 dias).
    DIAS_NO_MES = 30


@dataclass(frozen=True, slots=True)
class EncargosDevidos:
    """Resultado do cálculo, com a memória de conta que a tela pode mostrar."""

    principal: Dinheiro
    dias_atraso: int
    dias_cobrados: int
    multa: Dinheiro
    juros: Dinheiro
    total: Dinheiro
    memoria: tuple[str, ...] = field(default_factory=tuple)

    @property
    def total_com_encargos(self) -> Dinheiro:
        return Dinheiro(self.principal.centavos + self.total.centavos)

    @property
    def isento(self) -> bool:
        return self.total.centavos == 0


def calcular_encargos(
    principal: Dinheiro,
    *,
    vencimento: date,
    referencia: date,
    politica: PoliticaEncargos | None = None,
) -> EncargosDevidos:
    """Encargos de um título em atraso na data de referência.

    Devolve zeros quando não há atraso (ou quando está dentro da carência) e
    sempre traz a memória de conta, para o operador poder explicar o número.
    """
    politica = politica or PoliticaEncargos()
    if principal.centavos < 0:
        raise ErroValidacao("Principal não pode ser negativo.")
    dias = (referencia - vencimento).days
    memoria = [
        f"Principal: {principal.formatado()}",
        f"Vencimento: {vencimento.isoformat()} · referência: {referencia.isoformat()}",
        f"Atraso: {max(0, dias)} dia(s); carência de {politica.carencia_dias} dia(s)",
    ]
    if dias <= politica.carencia_dias or principal.centavos == 0:
        memoria.append("Sem atraso cobrável: nenhum encargo.")
        return EncargosDevidos(
            principal=principal,
            dias_atraso=max(0, dias),
            dias_cobrados=0,
            multa=Dinheiro.zero(),
            juros=Dinheiro.zero(),
            total=Dinheiro.zero(),
            memoria=tuple(memoria),
        )

    dias_cobrados = dias - politica.carencia_dias
    multa = Dinheiro(_meio_para_cima(principal.centavos * politica.multa.bp, Percentual.BASE))
    # Juros simples proporcionais: principal × taxa mensal × dias ÷ (30 × base).
    # A divisão é feita uma vez só, no fim, para não perder centavo por dia.
    juros = Dinheiro(
        _meio_para_cima(
            principal.centavos * politica.juros_mes.bp * dias_cobrados,
            Percentual.BASE * politica.DIAS_NO_MES,
        )
    )
    memoria.append(
        f"Multa {politica.multa.formatado()} sobre {principal.formatado()} = {multa.formatado()}"
    )
    memoria.append(
        f"Juros {politica.juros_mes.formatado()} ao mês, proporcionais a {dias_cobrados} dia(s) "
        f"(mês de {politica.DIAS_NO_MES} dias) = {juros.formatado()}"
    )
    total = Dinheiro(multa.centavos + juros.centavos)
    memoria.append(f"Total de encargos: {total.formatado()}")
    return EncargosDevidos(
        principal=principal,
        dias_atraso=max(0, dias),
        dias_cobrados=dias_cobrados,
        multa=multa,
        juros=juros,
        total=total,
        memoria=tuple(memoria),
    )


def _meio_para_cima(numerador: int, denominador: int) -> int:
    return (numerador + denominador // 2) // denominador


__all__ = ["EncargosDevidos", "PoliticaEncargos", "calcular_encargos"]
