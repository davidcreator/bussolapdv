"""Exportação de relatórios: Excel (`.xlsx`) e PDF, a partir do mesmo `Relatorio`."""

from __future__ import annotations

from pathlib import Path

from ...dominio.erros import ErroValidacao
from ...dominio.relatorio import Relatorio
from . import xlsx

FORMATOS = {".xlsx": "Excel", ".pdf": "PDF"}


def escrever(relatorio: Relatorio, destino: Path) -> Path:
    """Grava no formato indicado pela extensão do arquivo."""
    destino = Path(destino)
    extensao = destino.suffix.lower()
    if extensao == ".xlsx":
        return xlsx.escrever(relatorio, destino)
    if extensao == ".pdf":
        from . import pdf  # import tardio: só precisa do Qt quando há PDF

        return pdf.escrever(relatorio, destino)
    raise ErroValidacao(
        f"Formato {extensao or '(sem extensão)'} não suportado. "
        f"Use {', '.join(sorted(FORMATOS))}."
    )


def nome_sugerido(relatorio: Relatorio, extensao: str) -> str:
    return relatorio.nome_de_arquivo(extensao)


__all__ = ["FORMATOS", "escrever", "nome_sugerido", "xlsx"]
