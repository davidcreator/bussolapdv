# -*- mode: python ; coding: utf-8 -*-
"""Receita PyInstaller do Bússola PDV (modo onedir, sem console).

Rodar a partir da raiz do repositório:

    pip install -e ".[empacotamento]"
    pyinstaller --noconfirm --clean empacotamento/bussola.spec

Saída: ``dist/BussolaPDV/`` com ``BussolaPDV.exe`` e ``BussolaPDV-console.exe``.

Por que **onedir** e não ``--onefile``: o onefile descompacta Qt em pasta
temporária a cada execução (abertura de 5–15 s e antivírus reclamando do
executável automático). Onedir abre rápido e o instalador empacota a pasta.
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

RAIZ = Path(SPECPATH).resolve().parent  # noqa: F821 - variável do PyInstaller
EMPACOTAMENTO = RAIZ / "empacotamento"
ICONE = EMPACOTAMENTO / "bussola.ico"
VERSAO = EMPACOTAMENTO / "versao_info.txt"

analise = Analysis(  # noqa: F821
    [str(EMPACOTAMENTO / "entrada.py")],
    pathex=[str(RAIZ / "src")],
    binaries=[],
    # Ícones (SVG) e folha de estilo (QSS) são strings dentro do pacote, mas as
    # migrações do banco são arquivos .sql lidos por caminho relativo a
    # `migrador.py`. Sem esta linha o executável abre e falha em "no such table".
    datas=[
        (
            str(RAIZ / "src" / "bussola_pdv" / "infra" / "sqlite" / "migracoes"),
            "bussola_pdv/infra/sqlite/migracoes",
        ),
        # Fuso horário: o Windows não tem base IANA, `zoneinfo` lê o pacote
        # `tzdata`. Sem estas linhas o executável abre e morre no primeiro uso
        # com `ZoneInfoNotFoundError: America/Sao_Paulo`.
        *collect_data_files("tzdata"),
    ],
    hiddenimports=[
        "bussola_pdv",
        "bussola_pdv.cli",
        "bussola_pdv.caminhos",
        "bussola_pdv.ui.app",
        "bussola_pdv.ui.primeiro_uso",
        # Argon2id é importado indiretamente pelo argon2-cffi.
        *collect_submodules("argon2"),
        "tzdata",
        "zoneinfo",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "unittest",
        "doctest",
        "pydoc",
        "pytest",
        "ruff",
        "mypy",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtMultimedia",
        "PySide6.Qt3DCore",
        "PySide6.QtCharts",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(analise.pure)  # noqa: F821

# Interface: sem janela de console preta atrás do PDV.
exe = EXE(  # noqa: F821
    pyz,
    analise.scripts,
    [],
    exclude_binaries=True,
    name="BussolaPDV",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX + Qt = falso positivo de antivírus
    console=False,
    disable_windowed_traceback=False,
    icon=str(ICONE) if ICONE.exists() else None,
    version=str(VERSAO) if VERSAO.exists() else None,
)

# Diagnóstico: mesmo código, com console, para ver erro de inicialização.
exe_console = EXE(  # noqa: F821
    pyz,
    analise.scripts,
    [],
    exclude_binaries=True,
    name="BussolaPDV-console",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    icon=str(ICONE) if ICONE.exists() else None,
    version=str(VERSAO) if VERSAO.exists() else None,
)

pasta = COLLECT(  # noqa: F821
    exe,
    exe_console,
    analise.binaries,
    analise.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="BussolaPDV",
)
