"""Identidade visual: o logo oficial do Bússola e o logo que a loja enviar.

Duas regras, e as duas existem por um defeito que já apareceu:

1. **O logo é imagem do pacote, não texto.** Antes, o canto do menu lateral
   desenhava a inicial do nome da loja num quadrado branco. Funcionava, mas não
   era o logo de ninguém. Agora sai o arquivo `recursos/logo_mini.png`, com a
   mesma moldura branca, tingido com a cor primária da paleta — de modo que
   continua legível em qualquer tema, claro ou escuro (ADR-024: contraste
   medido, não escolhido a olho).
2. **O logo da loja ganha do oficial.** Quando o Admin Master envia um PNG em
   *Marca e tema*, ele passa a valer em todo lugar do programa **do usuário** —
   login, primeiro uso, telas e menu. Sem logo enviado, volta o do Bússola. A
   **área administrativa é a exceção**: ali a identidade é a do Bússola e não
   troca (decisão do responsável, registrada em ADR-028).

Sobre tingir: os dois logos oficiais são de tinta única sobre transparência, então
pintar preserva exatamente o desenho. O logo **da loja** nunca é tingido — pode
ser colorido, e a escolha da cor é de quem enviou.
"""

from __future__ import annotations

import base64
import binascii
import sys
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QLabel, QWidget

from ..dominio.marca import Marca, garantir_contraste

#: Contraste mínimo de elemento gráfico (WCAG 2.2, 1.4.11) sobre o quadrado branco.
CONTRASTE_DO_SIMBOLO = 3.0


def tinta_do_simbolo(primaria: str) -> str:
    """Cor do símbolo no quadrado branco: a primária da loja, se ela aparecer.

    A decisão do responsável é que o logo acompanhe a cor primária do tema
    (ADR-028). Só que uma loja pode escolher primária quase branca — e aí o
    desenho sumiria no quadrado. Nesse caso a tinta é escurecida **o mínimo**
    necessário para passar de 3:1, como já se faz com texto secundário.
    """
    return garantir_contraste(primaria, "#FFFFFF", alvo=CONTRASTE_DO_SIMBOLO)


#: Nome dos arquivos empacotados em `bussola_pdv/recursos/`.
LOGO_MINI = "logo_mini.png"
LOGO_COMERCIAL = "logo_comercial.png"

#: Proporção da assinatura horizontal (296×132). Serve para dimensionar sem
#: perguntar à imagem toda vez.
PROPORCAO_COMERCIAL = 296 / 132

#: Folga em volta do símbolo dentro do quadrado branco do menu (px lógicos).
FOLGA_MONOGRAMA = 4


def pasta_de_recursos() -> Path:
    """Caminho da pasta de recursos, com o executável empacotado em conta.

    No PyInstaller (onedir) os módulos Python vivem dentro do arquivo compactado:
    `__file__` aponta para um caminho que não existe no disco. Os *datas* ficam em
    `sys._MEIPASS`, então é lá que o logo é procurado primeiro.
    """
    congelado = getattr(sys, "_MEIPASS", None)
    if congelado:
        candidato = Path(str(congelado)) / "bussola_pdv" / "recursos"
        if candidato.is_dir():
            return candidato
    return Path(__file__).resolve().parents[1] / "recursos"


def caminho_do_logo(nome: str) -> Path:
    """Caminho de um arquivo de logo; levanta erro claro se ele não estiver lá."""
    caminho = pasta_de_recursos() / nome
    if not caminho.is_file():
        raise FileNotFoundError(
            f"Logo ausente do pacote: {caminho}. Os logos são versionados em "
            "src/bussola_pdv/recursos/ e copiados no build por empacotamento/bussola.spec."
        )
    return caminho


def _pintar(pixmap: QPixmap, cor: str) -> QPixmap:
    """Troca a tinta do logo mantendo o canal alfa (source-in)."""
    pintado = QPixmap(pixmap.size())
    pintado.setDevicePixelRatio(pixmap.devicePixelRatio())
    pintado.fill(Qt.GlobalColor.transparent)
    pintor = QPainter(pintado)
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pintor.drawPixmap(0, 0, pixmap)
    pintor.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    pintor.fillRect(pintado.rect(), QColor(cor))
    pintor.end()
    return pintado


def pixmap_do_logo(
    nome: str,
    *,
    altura: int | None = None,
    largura: int | None = None,
    cor: str | None = None,
    proporcao: float = 1.0,
) -> QPixmap:
    """Carrega um logo do pacote, escala e (opcionalmente) tinge.

    `proporcao` é a densidade de tela (2.0 em monitor HiDPI): a imagem é gerada
    com o dobro de pixels e marcada com `devicePixelRatio`, para não sair borrada
    no Windows a 150% — o mesmo problema de escala que a P5/P12 registram.
    """
    origem = QPixmap(str(caminho_do_logo(nome)))
    if origem.isNull():
        return origem
    densidade = max(1.0, float(proporcao))
    alvo_altura = int(altura * densidade) if altura else None
    alvo_largura = int(largura * densidade) if largura else None
    escalado = origem.scaled(
        alvo_largura or origem.width() * 8,
        alvo_altura or origem.height() * 8,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    escalado.setDevicePixelRatio(densidade)
    if cor:
        escalado = _pintar(escalado, cor)
    return escalado


def pixmap_de_data_uri(dados: str, *, altura: int, proporcao: float = 1.0) -> QPixmap | None:
    """Logo enviado pela loja (PNG em base64) → pixmap escalado."""
    if not dados.startswith("data:image/png;base64,"):
        return None
    try:
        conteudo = base64.b64decode(dados.split(",", 1)[1], validate=True)
    except (ValueError, binascii.Error):
        return None
    imagem = QImage.fromData(conteudo)  # o formato vem no cabeçalho do PNG
    if imagem.isNull():
        return None
    densidade = max(1.0, float(proporcao))
    escalada = imagem.scaledToHeight(
        int(altura * densidade), Qt.TransformationMode.SmoothTransformation
    )
    pixmap = QPixmap.fromImage(escalada)
    pixmap.setDevicePixelRatio(densidade)
    return pixmap


def logo_da_loja(marca: Marca | None, *, altura: int, proporcao: float = 1.0) -> QPixmap | None:
    """Logo enviado pela loja, se houver."""
    if marca is None or not marca.logo_data_uri:
        return None
    return pixmap_de_data_uri(marca.logo_data_uri, altura=altura, proporcao=proporcao)


def logo_comercial(
    marca: Marca | None = None,
    *,
    altura: int,
    cor: str | None = None,
    proporcao: float = 1.0,
) -> QPixmap:
    """Assinatura horizontal: a da loja, se existir; senão a oficial do Bússola.

    `cor` só se aplica ao logo oficial — o da loja é exibido como foi enviado.
    """
    da_loja = logo_da_loja(marca, altura=altura, proporcao=proporcao)
    if da_loja is not None:
        return da_loja
    return pixmap_do_logo(LOGO_COMERCIAL, altura=altura, cor=cor, proporcao=proporcao)


def simbolo(
    marca: Marca | None = None,
    *,
    lado: int,
    cor: str | None = None,
    proporcao: float = 1.0,
    oficial: bool = False,
) -> QPixmap:
    """Símbolo quadrado (o do menu lateral): o da loja ou o do Bússola.

    `oficial=True` ignora o logo da loja — é o que a área administrativa usa para
    manter a identidade do Bússola ali.
    """
    if not oficial:
        da_loja = logo_da_loja(marca, altura=lado, proporcao=proporcao)
        if da_loja is not None:
            quadrado = QPixmap(lado * int(proporcao), lado * int(proporcao))
            quadrado.fill(Qt.GlobalColor.transparent)
            pintor = QPainter(quadrado)
            pintor.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            # Centraliza sem esticar: logo retangular continua retangular.
            x = (quadrado.width() - da_loja.width()) / 2
            y = (quadrado.height() - da_loja.height()) / 2
            pintor.drawPixmap(int(x), int(y), da_loja)
            pintor.end()
            quadrado.setDevicePixelRatio(proporcao)
            return quadrado
    return pixmap_do_logo(LOGO_MINI, altura=lado, cor=cor, proporcao=proporcao)


class RotuloLogo(QLabel):
    """`QLabel` que guarda o logo em tamanho lógico e sobrevive a mudança de tela.

    A altura é fixa (o layout da casca depende dela) e a imagem é regerada quando
    a densidade de pixels muda — arrastar a janela de um monitor 100% para outro
    150% é comum em balcão com dois monitores.
    """

    def __init__(
        self,
        nome: str,
        *,
        altura: int,
        cor: str | None = None,
        align: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignCenter,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("logoOficial")
        self.setAlignment(align)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self._nome = nome
        self._altura = altura
        self._cor = cor
        self._marca: Marca | None = None
        self._oficial = True
        self.setFixedHeight(altura)
        self._atualizar()

    def definir_cor(self, cor: str | None) -> None:
        if cor != self._cor:
            self._cor = cor
            self._atualizar()

    def definir_marca(self, marca: Marca | None) -> None:
        if marca is not self._marca:
            self._marca = marca
            self._atualizar()

    def _densidade(self) -> float:
        janela = self.window()
        tela = janela.screen() if janela is not None else None
        return float(tela.devicePixelRatio()) if tela is not None else 1.0

    def _atualizar(self) -> None:
        densidade = self._densidade()
        pixmap = logo_comercial(
            self._marca, altura=self._altura, cor=self._cor, proporcao=densidade
        )
        self.setPixmap(pixmap)
        largura = int(pixmap.width() / pixmap.devicePixelRatio())
        self.setMinimumWidth(max(largura, 1))
        self.setMaximumWidth(max(largura, 1))
        self.setToolTip("")

    def sizeHint(self) -> QSize:
        pixmap = self.pixmap()
        if pixmap is None or pixmap.isNull():
            return QSize(0, self._altura)
        return QSize(
            int(pixmap.width() / pixmap.devicePixelRatio()),
            int(pixmap.height() / pixmap.devicePixelRatio()),
        )


__all__ = [
    "CONTRASTE_DO_SIMBOLO",
    "FOLGA_MONOGRAMA",
    "LOGO_COMERCIAL",
    "LOGO_MINI",
    "PROPORCAO_COMERCIAL",
    "RotuloLogo",
    "caminho_do_logo",
    "logo_comercial",
    "logo_da_loja",
    "pasta_de_recursos",
    "pixmap_de_data_uri",
    "pixmap_do_logo",
    "simbolo",
    "tinta_do_simbolo",
]
