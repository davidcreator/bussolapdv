"""Permite `python -m bussola_pdv <comando>` sem instalar o script `bussola`."""

from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
