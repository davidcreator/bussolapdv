#!/usr/bin/env python3
"""Transforma o relatório JUnit do pytest em anotações legíveis no GitHub Actions.

Por que isto existe: o workflow do Windows rodava `pytest -q` e, quando falhava,
o único sinal era *"Process completed with exit code 1"* na aba Actions. Sem o
nome do teste, o diagnóstico virava adivinhação — e a suíte é grande.

Uso::

    python -m pytest tests --junitxml=relatorio-testes.xml
    python ferramentas/anotar_falhas.py relatorio-testes.xml

Saída: linhas ``::error``/``::warning`` (formato de anotação do GitHub Actions) e
um resumo em texto. Fora do Actions as linhas aparecem literalmente no terminal —
inofensivo, e continua útil para ler o resumo.

O script só depende da biblioteca padrão: roda antes de qualquer instalação do
projeto e em qualquer Python 3.9+.
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

#: Quantos caracteres da mensagem de falha cabem numa anotação sem virar parede.
LIMITE_MENSAGEM = 400


def _achatar(texto: str) -> str:
    """Anotação é uma linha só: quebras viram espaço, e o resto é cortado."""
    limpo = " ".join((texto or "").split())
    if len(limpo) > LIMITE_MENSAGEM:
        limpo = limpo[: LIMITE_MENSAGEM - 1] + "…"
    return limpo.replace("%", "%25").replace("\r", " ").replace("\n", " ")


def _escapar_propriedade(texto: str) -> str:
    return texto.replace("%", "%25").replace(",", "%2C").replace(":", "%3A")


def ler(arquivo: Path) -> tuple[list[tuple[str, str, str]], list[tuple[str, str]], int, int]:
    """Devolve (falhas, erros, total, pulados) a partir do JUnit XML."""
    # O XML é escrito pelo pytest da mesma execução, no mesmo runner — não é dado
    # externo. `defusedxml` não entraria aqui de propósito: o script roda antes de
    # qualquer instalação do projeto (é o que o torna útil quando a suíte quebra).
    raiz = ET.parse(arquivo).getroot()  # noqa: S314
    suites = [raiz] if raiz.tag == "testsuite" else list(raiz.iter("testsuite"))
    falhas: list[tuple[str, str, str]] = []
    erros: list[tuple[str, str]] = []
    total = 0
    pulados = 0
    for suite in suites:
        for caso in suite.iter("testcase"):
            total += 1
            nome = caso.get("name") or "?"
            classe = caso.get("classname") or ""
            arquivo_fonte = (caso.get("file") or "").replace(".", "/", 0)
            if caso.find("skipped") is not None:
                pulados += 1
            falha = caso.find("failure")
            if falha is not None:
                falhas.append((f"{classe}::{nome}", arquivo_fonte, _mensagem(falha)))
            erro = caso.find("error")
            if erro is not None:
                erros.append((f"{classe}::{nome}", _mensagem(erro)))
    return falhas, erros, total, pulados


def _mensagem(elemento: ET.Element) -> str:
    texto = elemento.get("message") or ""
    if not texto.strip():
        texto = elemento.text or ""
    return _achatar(texto)


def _arquivo_de(classe: str) -> str:
    """`tests.test_ajuda.TestX` → `tests/test_ajuda.py` (para a anotação abrir o arquivo)."""
    partes = classe.split(".")
    if not partes or not partes[0]:
        return ""
    modulo = "/".join(partes[:-1]) if len(partes) > 1 else partes[0]
    return f"{modulo}.py" if modulo else ""


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("uso: python ferramentas/anotar_falhas.py <relatorio.xml>", file=sys.stderr)
        return 2
    arquivo = Path(argv[1])
    if not arquivo.is_file():
        print(f"::warning::Relatório de testes não encontrado: {arquivo}")
        return 0  # não é motivo para derrubar o trabalho: a falha real já apareceu
    try:
        falhas, erros, total, pulados = ler(arquivo)
    except ET.ParseError as exc:
        print(f"::warning::Relatório de testes ilegível ({exc}).")
        return 0

    for nome, _fonte, mensagem in falhas:
        alvo = _arquivo_de(nome.split("::")[0])
        propriedades = f"title={_escapar_propriedade(nome)}"
        if alvo:
            propriedades = f"file={_escapar_propriedade(alvo)}," + propriedades
        print(f"::error {propriedades}::{mensagem or 'falhou'}")

    for nome, mensagem in erros:
        print(
            f"::error title={_escapar_propriedade(nome)}::"
            f"{mensagem or 'erro durante o teste'}"
        )

    resumo = f"{total} testes, {len(falhas)} falha(s), {len(erros)} erro(s), {pulados} pulado(s)"
    print(resumo)
    if falhas or erros:
        print("Testes que falharam:")
        for nome, _fonte, _msg in falhas:
            print(f"  - {nome}")
        for nome, _msg in erros:
            print(f"  - {nome} (erro)")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
