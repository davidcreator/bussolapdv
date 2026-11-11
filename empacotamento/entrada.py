"""Ponto de entrada do executável empacotado (PyInstaller).

A lógica mora em `bussola_pdv.ui.entrada` — que é também o script `bussola-pdv`
instalado pelo pip. Este arquivo só acrescenta o que o congelamento exige:
`multiprocessing.freeze_support()` e o AppUserModelID do Windows.
"""

from __future__ import annotations

import multiprocessing
import sys


def _habilitar_app_id() -> None:  # pragma: no cover - só faz sentido no Windows
    """Sem isto o Windows agrupa a janela do PDV como "python.exe" na barra."""
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Bussola.PDV")
    except Exception as exc:  # pragma: no cover - falhar aqui não impede abrir
        print(f"aviso: AppUserModelID não aplicado ({exc})", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    from bussola_pdv.ui.entrada import main as entrada

    _habilitar_app_id()
    return entrada(argv)


if __name__ == "__main__":  # pragma: no cover - execução direta do script
    multiprocessing.freeze_support()
    raise SystemExit(main())
