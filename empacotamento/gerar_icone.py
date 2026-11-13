"""Gera o ícone da instalação Windows a partir do **logo oficial** do programa.

Antes (até a v0.10.1) este script desenhava uma bússola genérica com `QPainter`
porque não havia logo. Agora existe: `src/bussola_pdv/recursos/logo_mini.png`
(a bússola com o "B"). O script **não redesenha nada** — escala o arquivo oficial,
que é a única forma de o ícone do executável e o do menu lateral serem o mesmo
desenho (ADR-028).

O que é produzido:

======================================  ======================================
`empacotamento/bussola.ico`             ícone do `.exe` e do atalho, 7 tamanhos
`empacotamento/bussola.png`             PNG 256 para documentação/loja
`empacotamento/instalador_pequeno.bmp`  55×55 do assistente de instalação (Inno)
`empacotamento/instalador_lateral.bmp`  164×314 do assistente de instalação
======================================  ======================================

O `.ico` é montado com a biblioteca padrão (cada entrada é um PNG completo,
aceito desde o Windows Vista); não há dependência de Pillow.

Uso (na raiz do repositório)::

    QT_QPA_PLATFORM=offscreen PYTHONPATH=src python3 empacotamento/gerar_icone.py

Os arquivos gerados são versionados: o build no Windows não precisa rodar este
script de novo, mas `build_windows.ps1` roda por garantia.

Limite conhecido: abaixo de 32 px o desenho da bússola fica apertado (16 px tem
16×16 pixels para tudo). O ícone continua legível como silhueta — e por isso o
menu lateral usa 22 px e o executável usa a lista completa de tamanhos, deixando
o Windows escolher.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
TAMANHOS = (16, 24, 32, 48, 64, 128, 256)

#: Fundo das imagens do assistente de instalação. O Inno Setup desenha BMP sem
#: transparência; fundo branco é o do próprio assistente.
FUNDO_INSTALADOR = "#FFFFFF"
#: Medidas do assistente (Inno Setup, WizardStyle=modern).
LADO_PEQUENO = 55
LATERAL = (164, 314)


def _recursos():
    """Importa o pacote só depois de resolver o caminho (roda sem `pip install`)."""
    raiz_src = RAIZ / "src"
    if str(raiz_src) not in sys.path:
        sys.path.insert(0, str(raiz_src))
    from bussola_pdv.ui.identidade import LOGO_MINI, pasta_de_recursos

    return pasta_de_recursos() / LOGO_MINI, LOGO_MINI


def _garantir_aplicacao() -> None:
    """QPainter/QPixmap precisam de QGuiApplication (mesmo sem janela)."""
    from PySide6.QtGui import QGuiApplication

    if QGuiApplication.instance() is None:
        QGuiApplication(sys.argv[:1] or ["gerar-icone"])


def _imagem(tamanho: int):
    """Logo oficial escalado para um quadrado `tamanho`×`tamanho`, sem tocar o desenho."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage, QPainter, QPixmap

    origem, _nome = _recursos()
    fonte = QPixmap(str(origem))
    if fonte.isNull():  # pragma: no cover - arquivo corrompido no repositório
        raise SystemExit(f"Logo do programa ilegível: {origem}")

    # O arquivo é quadrado (450×450) com folga transparente em volta: escalar
    # direto para o quadro mantém a mesma margem em todos os tamanhos.
    escalado = fonte.scaled(
        tamanho,
        tamanho,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    imagem = QImage(tamanho, tamanho, QImage.Format.Format_ARGB32_Premultiplied)
    imagem.fill(Qt.GlobalColor.transparent)
    pintor = QPainter(imagem)
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pintor.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    pintor.drawPixmap(
        (tamanho - escalado.width()) // 2, (tamanho - escalado.height()) // 2, escalado
    )
    pintor.end()
    return imagem


def _png(imagem) -> bytes:
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice

    dados = QByteArray()
    buffer = QBuffer(dados)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    imagem.save(buffer, "PNG")
    buffer.close()
    return bytes(dados)


def montar_ico(destino: Path, tamanhos: tuple[int, ...] = TAMANHOS) -> Path:
    """Escreve um `.ico` multi-resolução contendo PNGs."""
    _garantir_aplicacao()
    imagens = [(t, _png(_imagem(t))) for t in tamanhos]
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


def desenhar_bmp(destino: Path, largura: int, altura: int, *, altura_do_logo: int) -> Path:
    """Imagem do assistente de instalação: logo centralizado sobre fundo branco.

    O Inno Setup **não aceita PNG transparente** em `WizardImageFile`; ele quer
    BMP. Então o fundo é pintado de branco e o logo entra por cima, preservando o
    canal alfa no desenho.
    """
    from PySide6.QtGui import QColor, QImage, QPainter

    _garantir_aplicacao()
    imagem = QImage(largura, altura, QImage.Format.Format_RGB32)
    imagem.fill(QColor(FUNDO_INSTALADOR))
    pintor = QPainter(imagem)
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pintor.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    logo = _imagem(altura_do_logo)
    pintor.drawImage((largura - altura_do_logo) // 2, (altura - altura_do_logo) // 2, logo)
    pintor.end()
    if not imagem.save(str(destino), "BMP"):  # pragma: no cover - falha de escrita
        raise SystemExit(f"Não foi possível gravar {destino}")
    return destino


def main() -> int:
    ico = montar_ico(AQUI / "bussola.ico")
    _imagem(256).save(str(AQUI / "bussola.png"), "PNG")
    pequeno = desenhar_bmp(
        AQUI / "instalador_pequeno.bmp", LADO_PEQUENO, LADO_PEQUENO, altura_do_logo=44
    )
    lateral = desenhar_bmp(
        AQUI / "instalador_lateral.bmp", LATERAL[0], LATERAL[1], altura_do_logo=120
    )
    _, nome = _recursos()
    print(f"Origem: {nome}")
    print(f"Ícone gerado: {ico} ({ico.stat().st_size / 1024:.1f} kB, {len(TAMANHOS)} tamanhos)")
    print(f"PNG de referência: {AQUI / 'bussola.png'}")
    print(f"Assistente (pequeno): {pequeno}")
    print(f"Assistente (lateral): {lateral}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
