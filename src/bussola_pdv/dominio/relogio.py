"""Relógio injetável: instantes em UTC, data comercial no fuso da loja.

O fuso depende da base IANA (`zoneinfo`). No **Windows não existe base IANA no
sistema**: `ZoneInfo("America/Sao_Paulo")` só funciona com o pacote `tzdata`
instalado. Sem ele o programa morria no primeiro uso com
`ZoneInfoNotFoundError` — e, pior, a falha aparecia embrulhada num erro de
arquivo ocupado (`WinError 32`), porque a exceção nascia depois de a base já
estar aberta. Ver `resolver_fuso` e `docs/INSTALACAO_WINDOWS.md`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone, tzinfo
from typing import Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

FUSO_PADRAO = "America/Sao_Paulo"

# Reserva para quando a base IANA não estiver disponível (Windows sem `tzdata`).
# Guarda o deslocamento fixo em horas: não reproduz histórico de horário de verão,
# mas o Brasil não tem horário de verão desde 2019 e o PDV só precisa da data
# comercial do dia. O aviso fica registrado em `avisos_de_fuso()`.
FUSOS_FIXOS: dict[str, int] = {
    "America/Noronha": -2,
    "America/Sao_Paulo": -3,
    "America/Fortaleza": -3,
    "America/Recife": -3,
    "America/Bahia": -3,
    "America/Belem": -3,
    "America/Araguaina": -3,
    "America/Cuiaba": -4,
    "America/Manaus": -4,
    "America/Porto_Velho": -4,
    "America/Rio_Branco": -5,
    "UTC": 0,
}

_avisos: list[str] = []


def avisos_de_fuso() -> list[str]:
    """Avisos acumulados sobre fuso aproximado (para log e `bussola relogio`)."""
    return list(_avisos)


def limpar_avisos_de_fuso() -> None:
    """Só para testes: esquece os avisos acumulados."""
    _avisos.clear()


def resolver_fuso(nome: str = FUSO_PADRAO) -> tzinfo:
    """Devolve o fuso pedido, caindo para deslocamento fixo se faltar `tzdata`.

    Levanta `ValueError` só quando o nome é desconhecido **e** não há base IANA:
    aí o erro é do nome, não da instalação, e precisa ser dito assim.
    """
    try:
        return ZoneInfo(nome)
    except (ZoneInfoNotFoundError, KeyError, ValueError, OSError):
        horas = FUSOS_FIXOS.get(nome)
        if horas is None:
            raise ValueError(
                f"Fuso desconhecido: {nome}. Instale o pacote `tzdata` ou use um "
                f"dos fusos conhecidos: {', '.join(sorted(FUSOS_FIXOS))}."
            ) from None
        sinal = f"{horas:+03d}:00"
        aviso = (
            f"Fuso {nome} indisponível neste sistema (falta o pacote `tzdata`); "
            f"usando UTC{sinal} fixo. Datas e horários ficam corretos para hoje, "
            f"mas o histórico de horário de verão não é considerado."
        )
        if aviso not in _avisos:
            _avisos.append(aviso)
        return timezone(timedelta(hours=horas), nome)


class Relogio(Protocol):
    def agora_utc(self) -> datetime: ...

    def fuso(self) -> tzinfo: ...

    def hoje(self) -> datetime:
        """Data/hora local (fuso da loja)."""
        ...

    def data_negocio(self) -> str:
        """Data comercial (AAAA-MM-DD) usada em relatórios e fechamento."""
        ...


class RelogioSistema:
    """Implementação real. ``agora_utc`` é sempre timezone-aware."""

    def __init__(self, fuso: str = FUSO_PADRAO) -> None:
        self._fuso = resolver_fuso(fuso)

    def agora_utc(self) -> datetime:
        return datetime.now(tz=UTC)

    def fuso(self) -> tzinfo:
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
        self._fuso = resolver_fuso(fuso)

    def agora_utc(self) -> datetime:
        return self._instante

    def fuso(self) -> tzinfo:
        return self._fuso

    def hoje(self) -> datetime:
        return self._instante.astimezone(self._fuso)

    def data_negocio(self) -> str:
        return self.hoje().date().isoformat()

    def avancar(self, **delta: int) -> None:
        """Avança o relógio fixo (``avancar(days=1)``) para simular turnos/dias."""
        self._instante = self._instante + timedelta(**delta)


def formatar_local(instante_utc: datetime, fuso: str = FUSO_PADRAO) -> str:
    """Formata para exibição no fuso da loja (não altera o dado gravado)."""
    if instante_utc.tzinfo is None:
        raise ValueError("Instante deve ser timezone-aware (UTC).")
    return instante_utc.astimezone(resolver_fuso(fuso)).strftime("%d/%m/%Y %H:%M")
