"""Ícones vetoriais embutidos — nada de arquivo externo, nada de download.

Por que desenhar em vez de importar: o aplicativo é offline e a interface não pode
depender de rede nem de pacote de ícones. Cada ícone é um SVG de 24×24 escrito à
mão neste módulo (traço de 1,8, pontas arredondadas, inspirado no vocabulário
visual do AdminLTE/Bootstrap), colorido em tempo de execução com a cor da paleta.

`icone(nome, cor)` devolve um `QIcon` já rasterizado no tamanho pedido; se o nome
não existir, devolve um ícone vazio — ícone faltando nunca derruba a tela.
"""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

#: Desenhos em `viewBox="0 0 24 24"`. `{cor}` é substituído pelo hexadecimal.
DESENHOS: dict[str, str] = {
    "pdv": (
        '<path d="M3 4h2l2.4 10.2a2 2 0 0 0 2 1.6h7.2a2 2 0 0 0 2-1.6L20 7H6"/>'
        '<circle cx="9.5" cy="19.5" r="1.3"/><circle cx="17" cy="19.5" r="1.3"/>'
    ),
    "caixa": (
        '<rect x="2.5" y="6.5" width="19" height="11.5" rx="1.6"/>'
        '<circle cx="12" cy="12.3" r="2.6"/><path d="M5.6 10.4v3.8M18.4 10.4v3.8"/>'
    ),
    "produtos": (
        '<path d="M12 2.8 3.6 7.2v9.6L12 21.2l8.4-4.4V7.2z"/>'
        '<path d="M3.6 7.2 12 11.6l8.4-4.4M12 11.6v9.6"/>'
    ),
    "vendas": (
        '<path d="M6 2.8h9.5L19 6.3v14.9H6z"/><path d="M9 8h6M9 11.6h6M9 15.2h4"/>'
    ),
    "fechamento": (
        '<rect x="3.2" y="4.6" width="17.6" height="16.2" rx="1.8"/>'
        '<path d="M3.2 9.4h17.6M8 2.8v3.6M16 2.8v3.6M8.6 14.4l2.2 2.2 4.2-4.2"/>'
    ),
    "auditoria": ('<path d="M12 2.8 5 5.6v5.6c0 4.2 2.9 7.4 7 9 4.1-1.6 7-4.8 7-9V5.6z"/>'
                  '<path d="M8.8 11.8l2.3 2.3 4.1-4.3"/>'),
    "clientes": (
        '<circle cx="9" cy="8" r="3.2"/><path d="M3 20c0-3.3 2.7-5.4 6-5.4s6 2.1 6 5.4"/>'
        '<path d="M16.2 5.2a3 3 0 0 1 0 5.8M17.6 14.9c2.2.5 3.6 2.2 3.6 4.5"/>'
    ),
    "crediario": (
        '<path d="M5 3.2h11.6a2 2 0 0 1 2 2v15.6H7a2 2 0 0 1-2-2z"/>'
        '<path d="M5 17.2h13.6M8.6 7.2h6.2M8.6 11h6.2"/>'
    ),
    "estoque": (
        '<rect x="3" y="3.4" width="7.6" height="7.6" rx="1"/>'
        '<rect x="13.4" y="3.4" width="7.6" height="7.6" rx="1"/>'
        '<rect x="3" y="13.4" width="7.6" height="7.6" rx="1"/>'
        '<path d="M13.4 17.2h7.6M17.2 13.4v7.6"/>'
    ),
    "entradas": (
        '<path d="M2.8 16.6V6.4h10.4v10.2"/><path d="M13.2 9.4h4.6l3.4 3.4v3.8h-8z"/>'
        '<circle cx="7" cy="18.4" r="1.5"/><circle cx="17.4" cy="18.4" r="1.5"/>'
    ),
    "parametros": (
        '<path d="M4 6.4h16M4 12h16M4 17.6h16"/>'
        '<circle cx="8.6" cy="6.4" r="2"/><circle cx="15.4" cy="12" r="2"/>'
        '<circle cx="10.6" cy="17.6" r="2"/>'
    ),
    "administracao": (
        '<circle cx="12" cy="12" r="3.1"/>'
        '<path d="M12 2.8v2.4M12 18.8v2.4M4.6 4.6l1.7 1.7M17.7 17.7l1.7 1.7'
        'M2.8 12h2.4M18.8 12h2.4M4.6 19.4l1.7-1.7M17.7 6.3l1.7-1.7"/>'
    ),
    "usuarios": (
        '<circle cx="10" cy="8.2" r="3.3"/><path d="M4 20c0-3.4 2.7-5.6 6-5.6s6 2.2 6 5.6"/>'
        '<path d="M18.6 8.4v4.4M16.4 10.6h4.4"/>'
    ),
    "permissoes": (
        '<circle cx="8" cy="12" r="3.4"/><path d="M11.4 12H21M17.4 12v3.2M14.6 12v2.4"/>'
    ),
    "marca": (
        '<path d="M12 3.2a8.8 8.8 0 1 0 0 17.6c1.6 0 2-1.2 1.2-2.2-1-1.2-.4-2.6 1.2-2.6h1.8'
        'a3.4 3.4 0 0 0 3.4-3.4C19.6 6.6 16.2 3.2 12 3.2z"/>'
        '<circle cx="8.2" cy="9.4" r="1.1"/><circle cx="12" cy="7.6" r="1.1"/>'
    ),
    "manutencao": (
        '<path d="M14.6 3.4a4.6 4.6 0 0 1 5.6 5.9l-8.4 8.4-3.6.9.9-3.6 8.2-8.2"/>'
        '<path d="M5.4 14.6 3.2 16.8a2.6 2.6 0 0 0 3.7 3.7l2.2-2.2"/>'
    ),
    "visao": (
        '<path d="M2.8 12S6.4 5.8 12 5.8 21.2 12 21.2 12 17.6 18.2 12 18.2 2.8 12 2.8 12z"/>'
        '<circle cx="12" cy="12" r="2.8"/>'
    ),
    "menu": '<path d="M4 6.6h16M4 12h16M4 17.4h16"/>',
    "aviso": (
        '<path d="M12 3.4 2.8 20h18.4z"/><path d="M12 9.6v4.2"/><circle cx="12" cy="17" r="0.9"/>'
    ),
    "bloqueio": (
        '<rect x="4.4" y="10.2" width="15.2" height="10.4" rx="1.8"/>'
        '<path d="M8.2 10.2V7.8a3.8 3.8 0 0 1 7.6 0v2.4"/><circle cx="12" cy="15.4" r="1.2"/>'
    ),
    "dinheiro": (
        '<rect x="2.8" y="6.2" width="18.4" height="11.6" rx="1.6"/>'
        '<circle cx="12" cy="12" r="2.6"/><path d="M6.2 12h.2M17.6 12h.2"/>'
    ),
    "seta": '<path d="M9 4.8 16.2 12 9 19.2"/>',
    "saida": (
        '<path d="M14.4 3.6H5.2v16.8h9.2"/><path d="M11.6 12h9M17.8 8.6 21.2 12l-3.4 3.4"/>'
    ),
}

COR_PADRAO = "#6C757D"


def svg(nome: str, cor: str = COR_PADRAO, espessura: float = 1.8) -> str:
    """SVG completo do ícone, pronto para o `QSvgRenderer`."""
    desenho = DESENHOS.get(nome, "")
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{cor}" stroke-width="{espessura}" stroke-linecap="round" '
        f'stroke-linejoin="round">{desenho}</svg>'
    )


@lru_cache(maxsize=256)
def _renderizado(nome: str, cor: str, tamanho: int, espessura: float) -> QPixmap:
    renderizador = QSvgRenderer(QByteArray(svg(nome, cor, espessura).encode("utf-8")))
    pixmap = QPixmap(tamanho, tamanho)
    pixmap.fill(Qt.GlobalColor.transparent)
    pintor = QPainter(pixmap)
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderizador.render(pintor, QRectF(0, 0, tamanho, tamanho))
    pintor.end()
    return pixmap


def pixmap(nome: str, cor: str = COR_PADRAO, tamanho: int = 18, espessura: float = 1.8) -> QPixmap:
    """Pixmap do ícone (cacheado por nome/cor/tamanho). Vazio se o nome não existir."""
    if nome not in DESENHOS:
        return QPixmap()
    return _renderizado(nome, cor.upper(), tamanho, espessura)


def icone(nome: str, cor: str = COR_PADRAO, tamanho: int = 18, espessura: float = 1.8) -> QIcon:
    """`QIcon` do ícone ou ícone vazio se o nome não existir."""
    if nome not in DESENHOS:
        return QIcon()
    return QIcon(pixmap(nome, cor, tamanho, espessura))


def nomes() -> tuple[str, ...]:
    """Nomes disponíveis — usado nos testes para não deixar ícone órfão."""
    return tuple(DESENHOS)
