"""Formatação de valores para as saídas — uma regra só, para tela e arquivo não divergirem.

Os relatórios carregam centavos inteiros; a conversão para "R$ 1.234,56" mora
aqui, e não espalhada em cada exportador. Datas seguem o padrão brasileiro.
"""

from __future__ import annotations

from datetime import date

from ...dominio.erros import ErroValidacao
from ...dominio.relatorio import TipoColuna


def numero(valor: object) -> float:
    """Converte para float aceitando inteiro, float ou texto numérico pt-BR."""
    if valor is None or valor == "":
        return 0.0
    if isinstance(valor, bool):
        return 1.0 if valor else 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    limpo = str(valor).strip().replace("R$", "").replace(".", "").replace(",", ".")
    try:
        return float(limpo)
    except ValueError as exc:
        raise ErroValidacao(
            f"Valor {valor!r} não é numérico, mas a coluna foi declarada como "
            "MOEDA ou INTEIRO. Corrija o tipo da coluna no relatório."
        ) from exc


def reais(centavos: object) -> float:
    """Centavos → reais com 2 casas, arredondando (e não truncando) o troco."""
    return round(numero(centavos) / 100.0, 2)


def moeda(centavos: object) -> str:
    """`123456` → ``R$ 1.234,56`` (negativo sai como ``-R$ 12,00``)."""
    valor = reais(centavos)
    sinal = "-" if valor < 0 else ""
    inteiro, _, decimal = f"{abs(valor):.2f}".partition(".")
    grupos = f"{int(inteiro):,}".replace(",", ".")
    return f"{sinal}R$ {grupos},{decimal}"


def inteiro(valor: object) -> str:
    return f"{int(numero(valor)):d}"


def data_br(valor: object) -> str:
    """Aceita `date` ou ISO `AAAA-MM-DD`; devolve `DD/MM/AAAA`."""
    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y")
    texto = str(valor or "").strip()
    if len(texto) >= 10:
        try:
            return date.fromisoformat(texto[:10]).strftime("%d/%m/%Y")
        except ValueError:
            pass
    return texto


def texto(valor: object) -> str:
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "Sim" if valor else "Não"
    return str(valor)


def celula(valor: object, tipo: TipoColuna) -> str:
    """Texto final de uma célula, conforme o tipo declarado na coluna."""
    if tipo is TipoColuna.MOEDA:
        return moeda(valor)
    if tipo is TipoColuna.INTEIRO:
        return inteiro(valor)
    if tipo is TipoColuna.DATA:
        return data_br(valor)
    return texto(valor)
