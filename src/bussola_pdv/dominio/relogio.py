"""Relógio injetável: instantes em UTC, data comercial no fuso da loja."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol
from zoneinfo import ZoneInfo

FUSO_PADRAO = "America/Sao_Paulo"


class Relogio(Protocol):
    def agora_utc(self) -> datetime: ...

    def fuso(self) -> ZoneInfo: ...

    def hoje(self) -> datetime:
        """Data/hora local (fuso da loja)."""
        ...

    def data_negocio(self) -> str:
        """Data comercial (AAAA-MM-DD) usada em relatórios e fechamento."""
        ...


class RelogioSistema:
    """Implementação real. ``agora_utc`` é sempre timezone-aware."""

    def __init__(self, fuso: str = FUSO_PADRAO) -> None:
        self._fuso = ZoneInfo(fuso)

    def agora_utc(self) -> datetime:
        return datetime.now(tz=UTC)

    def fuso(self) -> ZoneInfo:
        return self._fuso

    def hoje(self) -> datetime:
        return self.agora_utc().astimezone(self._fuso)

    def data_negocio(self) -> str:
        return self.hoje().date().isoformat()


class RelogioFixo:
    """Relógio determinístico para testes: o tempo não anda sozinho."""

    def __init__(self, instante: datetime, fuso: str = FUSO_PADRAO) -> None:
        if instante.tzinfo is None:
            raise ValueError("RelogioFixo exige datetime com timezone.")
        self._instante = instante.astimezone(UTC)
        self._fuso = ZoneInfo(fuso)

    def agora_utc(self) -> datetime:
        return self._instante

    def fuso(self) -> ZoneInfo:
        return self._fuso

    def hoje(self) -> datetime:
        return self._instante.astimezone(self._fuso)

    def data_negocio(self) -> str:
        return self.hoje().date().isoformat()

    def avancar(self, **delta: int) -> None:
        """Avança o relógio fixo (``avancar(days=1)``) para simular turnos/dias."""
        from datetime import timedelta

        self._instante = self._instante + timedelta(**delta)


def formatar_local(instante_utc: datetime, fuso: str = FUSO_PADRAO) -> str:
    """Formata para exibição no fuso da loja (não altera o dado gravado)."""
    if instante_utc.tzinfo is None:
        raise ValueError("Instante deve ser timezone-aware (UTC).")
    return instante_utc.astimezone(ZoneInfo(fuso)).strftime("%d/%m/%Y %H:%M")
