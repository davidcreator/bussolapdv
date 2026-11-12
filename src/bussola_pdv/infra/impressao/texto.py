"""Renderização em texto puro: prévia na tela, `.txt` e `.bin` inspecionável.

Texto puro serve a três coisas concretas neste projeto:

1. **prévia barata** — a tela mostra exatamente as colunas do papel (32/48), então
   quem confere o cupom vê o mesmo que sai na bobina, sem abrir PDF;
2. **arquivo `.txt`** — suporte pede "me manda o cupom" e recebe algo que abre em
   qualquer lugar, inclusive no Bloco de Notas do Windows com acentuação;
3. **depuração do ESC/POS** — com `ascii=True` o texto mostra o que a térmica
   imprimiria depois da transliteração, o que resolve a dúvida "saiu `Ã©` no papel".
"""

from __future__ import annotations

from ...dominio.impressao import DocumentoImpresso
from .escpos import transliterar


def linhas(documento: DocumentoImpresso, *, ascii: bool = False) -> list[str]:
    """Linhas do documento, opcionalmente sem acento (como a térmica imprime)."""
    saida: list[str] = []
    for linha in documento.layout():
        texto = linha.barras if linha.eh_codigo_de_barras else linha.texto
        saida.append(transliterar(texto) if ascii else texto)
    return saida


def renderizar(documento: DocumentoImpresso, *, ascii: bool = False) -> str:
    """Documento inteiro como texto, terminando com uma linha em branco."""
    return "\n".join(linhas(documento, ascii=ascii)) + "\n"


__all__ = ["linhas", "renderizar"]
