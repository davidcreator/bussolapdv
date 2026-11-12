"""Impressão pelo driver do sistema: bobina ou folha, no papel que a loja tem.

Este é o caminho **padrão** (e o que funciona em qualquer impressora instalada):

* a impressora térmica aparece no Windows/Linux com o driver do fabricante, que já
  sabe a largura da bobina;
* a impressora comum (jato/laser) imprime o mesmo cupom em A4 ou o relatório da
  tela em folha cheia;
* o PDF sai do mesmo desenho, então "imprimir" e "salvar PDF" não divergem.

Como o cupom é desenhado: em **grade de caracteres**, não em texto corrido. Cada
caractere é pintado na coluna que lhe cabe (largura útil ÷ colunas). Isso imita o
que a térmica faz e garante que valor alinhado à direita fique exatamente sob o
outro, mesmo com fonte proporcional no sistema — a alternativa (`drawText` da linha
inteira) desalinha porque o avanço da fonte não é o da grade.

O código de barras é desenhado aqui a partir do padrão CODE 39 (retângulo por
módulo), em vez de virar imagem de fora: sem dependência, sem resolução fixa.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ...dominio.erros import ErroImpressao, ImpressoraIndisponivel
from ...dominio.impressao import (
    DocumentoImpresso,
    Enfase,
    LinhaPronta,
    PerfilPapel,
    barras_do_codigo,
    padrao_code39,
)

if TYPE_CHECKING:  # pragma: no cover - só para o verificador de tipos
    from PySide6.QtGui import QFont, QImage, QPainter

#: Resolução do PDF: 300 dpi é o suficiente para bobina e folha sem inflar arquivo.
RESOLUCAO_PDF = 300
#: Resolução da prévia em imagem: leve, só para ver na tela.
RESOLUCAO_PREVIA = 150

#: Teto de largura do código de barras no papel: 60 mm lê em qualquer leitor.
LARGURA_MAXIMA_BARRAS_MM = 60.0

FAMILIAS_MONOESPACADAS = ("DejaVu Sans Mono", "Consolas", "Courier New", "Liberation Mono")


@dataclass(frozen=True, slots=True)
class Medidas:
    """Converte milímetros do perfil em pixels do dispositivo de pintura."""

    dpi: int
    largura_util_px: float
    largura_util_mm: float
    colunas: int
    altura_linha_px: float

    @property
    def largura_coluna_px(self) -> float:
        return self.largura_util_px / self.colunas


def _mm_para_px(milimetros: float, dpi: int) -> float:
    return milimetros / 25.4 * dpi


def medidas(perfil: PerfilPapel, dpi: int) -> Medidas:
    return Medidas(
        dpi=dpi,
        largura_util_px=_mm_para_px(perfil.largura_util_mm, dpi),
        largura_util_mm=perfil.largura_util_mm,
        colunas=perfil.colunas,
        altura_linha_px=_mm_para_px(perfil.altura_linha_mm, dpi),
    )


def _garantir_aplicacao() -> object:
    """Qt precisa de aplicação viva para medir fonte e criar `QPainter`."""
    from PySide6.QtWidgets import QApplication

    existente = QApplication.instance()
    if existente is not None:
        return existente
    if not os.environ.get("DISPLAY") and sys.platform not in ("win32", "darwin"):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication([sys.argv[0] if sys.argv else "bussola-impressao"])


def _fonte(altura_linha_px: float, *, multiplicador: float = 1.0) -> QFont:
    from PySide6.QtGui import QFont

    fonte = QFont()
    for familia in FAMILIAS_MONOESPACADAS:
        fonte.setFamily(familia)
        if QFont(familia).exactMatch():
            break
    fonte.setStyleHint(QFont.StyleHint.Monospace)
    fonte.setFixedPitch(True)
    fonte.setPixelSize(max(5, int(altura_linha_px * multiplicador * 0.78)))
    return fonte


def _pintar_barras(
    pintor: QPainter, linha: LinhaPronta, x0: float, y: float, m: Medidas
) -> float:
    """Desenha o CODE 39 módulo a módulo e devolve a altura consumida (px)."""
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QColor

    padrao = padrao_code39(linha.barras)
    # Em A4 a largura útil é de 186 mm: sem teto, o código vira um borrão de 18 cm.
    # 60 mm é o que cabe confortavelmente e continua legível por leitor de balcão.
    largura_max = min(m.largura_util_px, _mm_para_px(LARGURA_MAXIMA_BARRAS_MM, m.dpi))
    modulo_px = largura_max / len(padrao)
    inicio_x = x0 + (m.largura_util_px - largura_max) / 2
    altura_px = _mm_para_px(linha.altura_barras_mm or 12.0, m.dpi)
    pintor.setPen(QColor("#000000"))
    for inicio, largura in barras_do_codigo(linha.barras):
        pintor.fillRect(
            QRectF(inicio_x + inicio * modulo_px, y, largura * modulo_px, altura_px),
            QColor("#000000"),
        )
    return altura_px


def _pintar_texto(
    pintor: QPainter, linha: LinhaPronta, x0: float, y: float, m: Medidas
) -> None:
    """Uma linha, caractere por caractere, na grade de colunas do papel.

    A grade é intocável: **nenhuma** linha foge dela, nem as de ênfase. Numa
    impressora térmica o "duplo" do título é um comando (`GS !`), e lá cada
    caractere ocupa duas colunas — por isso o documento nunca reserva colunas
    duplas. Aqui, no papel comum, a ênfase vira **negrito** na mesma grade: texto
    dobrado estouraria a bobina de 58 mm e sobreporia as linhas vizinhas (foi o que
    aconteceu na primeira versão deste desenho).
    """
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QColor, QFontMetricsF

    coluna_px = m.largura_coluna_px
    altura_px = m.altura_linha_px
    fonte = _fonte(altura_px)
    if linha.enfase is not Enfase.NORMAL:
        fonte.setBold(True)
    pintor.setFont(fonte)
    pintor.setPen(QColor("#000000"))
    metricas = QFontMetricsF(fonte)
    base = y + (altura_px - metricas.height()) / 2 + metricas.ascent()

    for indice, caractere in enumerate(linha.texto):
        if caractere == " ":
            continue
        pintor.drawText(QPointF(x0 + indice * coluna_px, base), caractere)


def pintar(
    pintor: QPainter,
    documento: DocumentoImpresso,
    *,
    dpi: int,
    largura_px: float,
    altura_px: float,
    margem_px: float,
) -> float:
    """Pinta o documento a partir do topo e devolve a altura usada (px)."""
    perfil = documento.perfil
    m = Medidas(
        dpi=dpi,
        largura_util_px=largura_px - 2 * margem_px,
        largura_util_mm=perfil.largura_util_mm,
        colunas=perfil.colunas,
        altura_linha_px=_mm_para_px(perfil.altura_linha_mm, dpi),
    )
    y = float(margem_px)
    for linha in documento.layout():
        if linha.eh_codigo_de_barras:
            y += _pintar_barras(pintor, linha, margem_px, y, m)
            continue
        _pintar_texto(pintor, linha, margem_px, y, m)
        y += m.altura_linha_px
    return y - margem_px


def escrever_pdf(documento: DocumentoImpresso, destino: Path) -> Path:
    """PDF do cupom no tamanho exato do papel (bobina sai como página contínua)."""
    from PySide6.QtCore import QMarginsF, QSizeF
    from PySide6.QtGui import QPageLayout, QPageSize, QPainter, QPdfWriter

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    _garantir_aplicacao()
    perfil = documento.perfil
    altura_mm = perfil.altura_mm or max(60.0, documento.altura_mm() + 2)

    escritor = QPdfWriter(str(destino))
    escritor.setPageSize(
        QPageSize(QSizeF(perfil.largura_mm, altura_mm), QPageSize.Unit.Millimeter, "BussolaPDV")
    )
    escritor.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Millimeter)
    escritor.setResolution(RESOLUCAO_PDF)
    escritor.setTitle(documento.titulo)
    escritor.setCreator("Bússola Sistema PDV Open Source")

    pintor = QPainter(escritor)
    try:
        pintar(
            pintor,
            documento,
            dpi=RESOLUCAO_PDF,
            largura_px=float(escritor.width()),
            altura_px=float(escritor.height()),
            margem_px=_mm_para_px(perfil.margem_mm, RESOLUCAO_PDF),
        )
    finally:
        pintor.end()
    return destino


def imagem(documento: DocumentoImpresso, *, dpi: int = RESOLUCAO_PREVIA) -> QImage:
    """Prévia em imagem do cupom (usada na tela antes de imprimir)."""
    from PySide6.QtGui import QColor, QImage, QPainter

    _garantir_aplicacao()
    perfil = documento.perfil
    largura = int(_mm_para_px(perfil.largura_mm, dpi))
    altura = int(_mm_para_px(max(documento.altura_mm(), 40.0), dpi))
    imagem_ = QImage(largura, altura, QImage.Format.Format_RGB32)
    imagem_.fill(QColor("#FFFFFF"))
    pintor = QPainter(imagem_)
    try:
        pintar(
            pintor,
            documento,
            dpi=dpi,
            largura_px=float(largura),
            altura_px=float(altura),
            margem_px=_mm_para_px(perfil.margem_mm, dpi),
        )
    finally:
        pintor.end()
    return imagem_


def imprimir(
    documento: DocumentoImpresso,
    nome_impressora: str,
    *,
    copias: int = 1,
    respeitar_papel_da_impressora: bool = True,
) -> None:
    """Manda o documento para a impressora pelo driver do sistema.

    `respeitar_papel_da_impressora=True` (padrão) usa o papel já configurado no
    driver — é o certo para bobina, cujo tamanho de página o driver do fabricante
    define e costuma recusar tamanho inventado. Em `False`, manda o tamanho exato
    do perfil (útil em A4 e em drivers genéricos).
    """
    from PySide6.QtCore import QMarginsF, QSizeF
    from PySide6.QtGui import QPageLayout, QPageSize, QPainter
    from PySide6.QtPrintSupport import QPrinter, QPrinterInfo

    _garantir_aplicacao()
    if not nome_impressora.strip():
        raise ErroImpressao(
            "Nenhuma impressora configurada. Escolha uma em Administração → Parâmetros → Impressão.",
            detalhe={"motivo": "impressora_nao_configurada"},
        )
    disponiveis = {info.printerName() for info in QPrinterInfo.availablePrinters()}
    if disponiveis and nome_impressora not in disponiveis:
        raise ErroImpressao(
            f"Impressora não encontrada: {nome_impressora!r}. "
            f"Instaladas: {', '.join(sorted(disponiveis)) or 'nenhuma'}.",
            detalhe={"impressoras": sorted(disponiveis)},
        )

    impressora = QPrinter(QPrinter.PrinterMode.HighResolution)
    impressora.setPrinterName(nome_impressora)
    perfil = documento.perfil
    if not respeitar_papel_da_impressora:
        impressora.setPageSize(
            QPageSize(
                QSizeF(perfil.largura_mm, perfil.altura_mm or 297.0),
                QPageSize.Unit.Millimeter,
                "BussolaPDV",
            )
        )
        impressora.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Millimeter)
    impressora.setCopyCount(max(1, copias))

    dpi = max(72, impressora.resolution())
    pintor = QPainter(impressora)
    if not pintor.isActive():
        # Driver ausente, impressora pausada ou fila fora do ar: sem pintor ativo o
        # Qt desenharia no vazio e o cupom "sairia" sem sair. Melhor falhar alto.
        raise ImpressoraIndisponivel(
            f"A impressora {nome_impressora!r} não aceitou o trabalho. "
            "Confira se ela está ligada, com papel e sem trabalho travado na fila.",
            detalhe={"impressora": nome_impressora, "estado": impressora.printerState().name},
        )
    try:
        retangulo = impressora.pageLayout().paintRectPixels(dpi)
        margem = _mm_para_px(perfil.margem_mm, dpi)
        usado = pintar(
            pintor,
            documento,
            dpi=dpi,
            largura_px=float(retangulo.width()),
            altura_px=float(retangulo.height()),
            margem_px=margem,
        )
        if usado > retangulo.height():
            # Conteúdo maior que a página: continua na seguinte (bobina contínua).
            impressora.newPage()
    finally:
        pintor.end()
    if not impressora.printerState() == impressora.PrinterState.Idle:  # pragma: no cover
        raise ErroImpressao(
            f"A impressora {nome_impressora!r} recusou o trabalho "
            f"({impressora.printerState().name}). Verifique papel, tampa e fila.",
            detalhe={"estado": impressora.printerState().name},
        )


__all__ = [
    "FAMILIAS_MONOESPACADAS",
    "RESOLUCAO_PDF",
    "RESOLUCAO_PREVIA",
    "Medidas",
    "escrever_pdf",
    "imagem",
    "imprimir",
    "medidas",
    "pintar",
]
