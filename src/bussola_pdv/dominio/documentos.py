"""Validação **estrutural** de documentos brasileiros.

Aviso explícito exigido pelo prompt mestre: estas funções verificam formato e
dígitos verificadores. Elas **não** comprovam titularidade, situação cadastral
nem existência do documento na base da Receita Federal. O sistema trata o
documento como dado informado pelo operador.

Referências:
* CPF: 11 dígitos, dois DVs módulo 11.
* CNPJ numérico: 14 dígitos, dois DVs módulo 11 com pesos 5..2 / 6..2.
* CNPJ alfanumérico (IN RFB nº 2.229/2024, válido a partir de julho/2026):
  12 primeiras posições alfanuméricas (0-9, A-Z) e 2 DVs numéricos. O valor de
  cada caractere é ``ord(c) - 48`` e o módulo 11 é preservado.
"""

from __future__ import annotations

import re

from .erros import ErroValidacao

_SO_DIGITOS = re.compile(r"\D")
_CNPJ_ALFA = re.compile(r"^[0-9A-Z]{12}\d{2}$")


def _somente_alfanumerico(texto: str) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", str(texto)).upper()


def _dv_mod11(valores: list[int], pesos: list[int]) -> int:
    soma = sum(v * p for v, p in zip(valores, pesos, strict=True))
    resto = soma % 11
    return 0 if resto < 2 else 11 - resto


def validar_cpf(cpf: str) -> str:
    """Valida o CPF e devolve os 11 dígitos normalizados."""
    digitos = _SO_DIGITOS.sub("", str(cpf))
    if len(digitos) != 11:
        raise ErroValidacao("CPF deve ter 11 dígitos.")
    if len(set(digitos)) == 1:
        raise ErroValidacao("CPF inválido: sequência repetida.")
    numeros = [int(d) for d in digitos]
    dv1 = _dv_mod11(numeros[:9], list(range(10, 1, -1)))
    dv2 = _dv_mod11(numeros[:10], list(range(11, 1, -1)))
    if (dv1, dv2) != (numeros[9], numeros[10]):
        raise ErroValidacao("CPF inválido: dígito verificador não confere.")
    return digitos


def validar_cnpj(cnpj: str) -> str:
    """Valida CNPJ numérico ou alfanumérico e devolve a forma normalizada."""
    documento = _somente_alfanumerico(cnpj)
    if len(documento) != 14:
        raise ErroValidacao("CNPJ deve ter 14 posições.")
    if not _CNPJ_ALFA.match(documento):
        raise ErroValidacao("CNPJ inválido: use 0-9 e A-Z nas 12 primeiras posições e 2 dígitos no fim.")
    if len(set(documento)) == 1:
        raise ErroValidacao("CNPJ inválido: sequência repetida.")
    valores = [ord(c) - 48 for c in documento]
    if not all(0 <= v <= 42 for v in valores):
        raise ErroValidacao("CNPJ inválido: caractere fora da faixa permitida.")
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    dv1 = _dv_mod11(valores[:12], pesos1)
    dv2 = _dv_mod11(valores[:13], pesos2)
    if (dv1, dv2) != (valores[12], valores[13]):
        raise ErroValidacao("CNPJ inválido: dígito verificador não confere.")
    return documento


def formatar_cpf(cpf: str) -> str:
    d = validar_cpf(cpf)
    return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"


def formatar_cnpj(cnpj: str) -> str:
    d = validar_cnpj(cnpj)
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"


def validar_documento(documento: str, tipo: str | None = None) -> tuple[str, str]:
    """Detecta CPF/CNPJ pelo tamanho e valida. Devolve ``(tipo, normalizado)``."""
    normalizado = _somente_alfanumerico(documento)
    if tipo == "CPF" or (tipo is None and len(normalizado) == 11):
        return "CPF", validar_cpf(normalizado)
    if tipo == "CNPJ" or (tipo is None and len(normalizado) == 14):
        return "CNPJ", validar_cnpj(normalizado)
    raise ErroValidacao("Documento deve ser CPF (11) ou CNPJ (14 posições).")


def validar_ean(codigo: str) -> str:
    """Valida dígito verificador de EAN-8/EAN-13 (e GTIN-14). Não consulta cadastro."""
    digitos = _SO_DIGITOS.sub("", str(codigo))
    if len(digitos) not in (8, 12, 13, 14):
        raise ErroValidacao("Código de barras deve ter 8, 12, 13 ou 14 dígitos.")
    corpo, dv = digitos[:-1], int(digitos[-1])
    soma = 0
    for indice, digito in enumerate(reversed(corpo)):
        peso = 3 if indice % 2 == 0 else 1
        soma += int(digito) * peso
    if (10 - soma % 10) % 10 != dv:
        raise ErroValidacao("Código de barras inválido: dígito verificador não confere.")
    return digitos


def gerar_dv_ean13(corpo12: str) -> str:
    """Gera o dígito verificador de um EAN-13 (útil para massa fictícia)."""
    digitos = _SO_DIGITOS.sub("", str(corpo12))
    if len(digitos) != 12:
        raise ErroValidacao("Informe 12 dígitos para gerar o DV do EAN-13.")
    soma = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(digitos))
    return digitos + str((10 - soma % 10) % 10)
