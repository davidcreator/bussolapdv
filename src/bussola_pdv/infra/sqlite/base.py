"""Apoio comum aos repositórios SQLite."""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime

from ...dominio.dinheiro import Dinheiro


class RepositorioBase:
    def __init__(self, conexao: sqlite3.Connection) -> None:
        self.conexao = conexao

    # -- conversões ---------------------------------------------------------
    @staticmethod
    def dinheiro(centavos: int | None) -> Dinheiro:
        return Dinheiro(int(centavos or 0))

    @staticmethod
    def booleano(valor: object) -> bool:
        if isinstance(valor, str):  # coluna TEXT legada: "0"/"1"
            return valor.strip() not in {"", "0", "false", "False"}
        return bool(valor or 0)

    @staticmethod
    def iso(instante: datetime) -> str:
        if instante.tzinfo is None:
            raise ValueError("Datas gravadas exigem timezone.")
        return instante.astimezone(UTC).isoformat()

    @staticmethod
    def instante(texto: str | None) -> datetime | None:
        if not texto:
            return None
        return datetime.fromisoformat(texto)

    @staticmethod
    def data(texto: str | None) -> date | None:
        if not texto:
            return None
        return date.fromisoformat(texto)
