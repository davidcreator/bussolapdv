"""Gera o ícone da instalação Windows (`bussola.ico`) e o PNG de origem.

Não depende de Pillow: desenha a bússola com QPainter (o mesmo monograma da
interface, em `ui/icones.py`) e monta o `.ico` com a biblioteca padrão — cada
entrada do arquivo é um PNG completo, formato aceito desde o Windows Vista.

Uso (na raiz do repositório):

    QT_QPA_PLATFORM=offscreen PYTHONPATH=src python3 empacotamento/gerar_icone.py

O resultado (`empacotamento/bussola.ico`) é versionado: o build no Windows não
precisa rodar este script de novo, mas ``build_windows.ps1`` roda por garantia.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QGuiApplication,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
)

AQUI = Path(__file__).resolve().parent
TAMANHOS = (16, 24, 32, 48, 64, 128, 256)
FUNDO = "#0D6EFD"
AGULHA = "#FFFFFF"
DETALHE = "#FFC107"


def _garantir_aplicacao() -> None:
    """QPainter precisa de uma instância (mesmo sem janela) para medir fontes."""
    if QGuiApplication.instance() is None:
        QGuiApplication(sys.argv[:1] or ["gerar-icone"])


def _desenhar(tamanho: int) -> QImage:
    imagem = QImage(tamanho, tamanho, QImage.Format.Format_ARGB32_Premultiplied)
    imagem.fill(Qt.GlobalColor.transparent)
    pintor = QPainter(imagem)
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    margem = tamanho * 0.06
    lado = QRectF(margem, margem, tamanho - 2 * margem, tamanho - 2 * margem)

    # Squircle de fundo (o mesmo azul da marca padrão).
    raio = lado.width() * 0.26
    fundo = QPainterPath()
    fundo.addRoundedRect(lado, raio, raio)
    pintor.fillPath(fundo, QColor(FUNDO))

    # Aro da bússola.
    centro = QPointF(tamanho / 2, tamanho / 2)
    raio_aro = lado.width() * 0.33
    pintor.setBrush(Qt.BrushStyle.NoBrush)
    pintor.setPen(QPen(QColor(AGULHA), max(1.0, tamanho * 0.035)))
    pintor.drawEllipse(centro, raio_aro, raio_aro)

    # Agulha: losango vertical, metade branca e metade âmbar.
    largura = lado.width() * 0.15
    altura = lado.height() * 0.29
    norte = QPainterPath()
    norte.moveTo(centro.x(), centro.y() - altura)
    norte.lineTo(centro.x() + largura / 2, centro.y())
    norte.lineTo(centro.x() - largura / 2, centro.y())
    norte.closeSubpath()
    pintor.fillPath(norte, QColor(AGULHA))

    sul = QPainterPath()
    sul.moveTo(centro.x(), centro.y() + altura)
    sul.lineTo(centro.x() + largura / 2, centro.y())
    sul.lineTo(centro.x() - largura / 2, centro.y())
    sul.closeSubpath()
    pintor.fillPath(sul, QColor(DETALHE))

    # Pino central.
    pintor.setBrush(QColor(AGULHA))
    pintor.setPen(Qt.PenStyle.NoPen)
    pintor.drawEllipse(centro, max(0.8, lado.width() * 0.028), max(0.8, lado.width() * 0.028))

    pintor.end()
    return imagem


def _png(imagem: QImage) -> bytes:
    dados = QByteArray()
    buffer = QBuffer(dados)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    imagem.save(buffer, "PNG")
    buffer.close()
    return bytes(dados)


def montar_ico(destino: Path, tamanhos: tuple[int, ...] = TAMANHOS) -> Path:
    """Escreve um `.ico` multi-resolução contendo PNGs."""
    _garantir_aplicacao()
    imagens = [(t, _png(_desenhar(t))) for t in tamanhos]
    cabecalho = struct.pack("<HHH", 0, 1, len(imagens))
    entradas = b""
    corpo = b""
    deslocamento = len(cabecalho) + 16 * len(imagens)
    for tamanho, dados in imagens:
        # 0 significa 256 no campo de largura/altura do formato ICO.
        medida = 0 if tamanho >= 256 else tamanho
        entradas += struct.pack(
            "<BBBBHHII", medida, medida, 0, 0, 1, 32, len(dados), deslocamento
        )
        deslocamento += len(dados)
        corpo += dados
    destino.write_bytes(cabecalho + entradas + corpo)
    return destino


def main() -> int:
    ico = montar_ico(AQUI / "bussola.ico")
    _desenhar(256).save(str(AQUI / "bussola.png"), "PNG")
    print(f"Ícone gerado: {ico} ({ico.stat().st_size / 1024:.1f} kB)")
    print(f"PNG de referência: {AQUI / 'bussola.png'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
