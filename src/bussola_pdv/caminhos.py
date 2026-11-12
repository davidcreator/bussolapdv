"""Onde a instalação guarda dados no disco, por sistema operacional.

Regra: **dado de loja não mora dentro da pasta de instalação**. Programa pode ser
atualizado ou desinstalado; a base do PDV, as cópias de segurança e os relatórios
não. Por isso o banco fica no diretório de dados do usuário:

* Windows  → ``%LOCALAPPDATA%\\BussolaPDV``
* Linux    → ``$XDG_DATA_HOME/bussola-pdv`` (ou ``~/.local/share/bussola-pdv``)
* macOS    → ``~/Library/Application Support/BussolaPDV``

A variável de ambiente ``BUSSOLA_DADOS`` sobrepõe tudo — é o que permite rodar
duas instalações lado a lado ou apontar para um pendrive de demonstração.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

NOME_PASTA = "BussolaPDV"
NOME_BANCO = "pdv.db"
NOME_COPIAS = "copias"


def diretorio_de_dados() -> Path:
    """Diretório base de dados do usuário (criado se não existir)."""
    caminho = os.environ.get("BUSSOLA_DADOS", "").strip()
    pasta = Path(caminho).expanduser() if caminho else _padrao()
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def _padrao() -> Path:
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / NOME_PASTA
        return Path.home() / "AppData" / "Local" / NOME_PASTA
    if sys.platform == "darwin":  # pragma: no cover - não testado em macOS
        return Path.home() / "Library" / "Application Support" / NOME_PASTA
    base = os.environ.get("XDG_DATA_HOME")
    return (Path(base) if base else Path.home() / ".local" / "share") / "bussola-pdv"


def banco_padrao() -> Path:
    """Caminho do banco da instalação (``pdv.db`` dentro do diretório de dados)."""
    return diretorio_de_dados() / NOME_BANCO


def pasta_de_relatorios() -> Path:
    """Pasta sugerida para relatórios exportados (Excel/PDF)."""
    pasta = diretorio_de_dados() / "relatorios"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def pasta_de_copias() -> Path:
    """Pasta sugerida para cópias de segurança."""
    pasta = diretorio_de_dados() / NOME_COPIAS
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta
