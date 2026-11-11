"""Peças de interface no vocabulário do AdminLTE (sidebar, cartões, small-box).

O AdminLTE é uma referência **de layout e de linguagem visual** (sidebar escura com
marca no topo, painel do usuário, navegação com ícones, barra superior, cabeçalho
de conteúdo com trilha, cartões e caixas de indicador). Nenhum arquivo, folha de
estilo ou ícone do projeto é copiado: aqui tudo é reconstruído em PySide6 e
pintado com a paleta da loja, para que a personalização de cores continue valendo.

Regra de ouro herdada do resto do projeto: **widget não calcula**. Estas peças só
mostram o que recebem e emitem sinais de intenção.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractScrollArea,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from ..dominio.marca import Paleta
from .icones import icone

ALTURA_BARRA_SUPERIOR = 52
ALTURA_ITEM_NAVEGACAO = 40
LARGURA_BARRA_LATERAL = 226
LARGURA_BARRA_RECOLHIDA = 62


def iniciais(nome: str) -> str:
    """Duas iniciais para o avatar (nunca mais que dois caracteres)."""
    partes = [parte for parte in nome.replace(".", " ").split() if parte]
    if not partes:
        return "?"
    if len(partes) == 1:
        return partes[0][:2].upper()
    return (partes[0][0] + partes[-1][0]).upper()


def sombra(widget: QWidget, raio: int = 12, opacidade: int = 28) -> None:
    """Sombra suave de cartão (o AdminLTE usa 0 1px 3px rgba(0,0,0,.12))."""
    efeito = QGraphicsDropShadowEffect(widget)
    efeito.setBlurRadius(raio)
    efeito.setOffset(0, 1)
    efeito.setColor(QColor(0, 0, 0, opacidade))
    widget.setGraphicsEffect(efeito)


class Selo(QLabel):
    """Etiqueta compacta de status (`badge` do Bootstrap)."""

    TONALIDADES = ("primaria", "sucesso", "alerta", "erro", "info", "claro")

    def __init__(
        self, texto: str = "", tonalidade: str = "claro", parent: QWidget | None = None
    ) -> None:
        super().__init__(texto, parent)
        self.setObjectName("selo")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.definir_tonalidade(tonalidade)

    def definir_tonalidade(self, tonalidade: str) -> None:
        self.setProperty("tonalidade", tonalidade if tonalidade in self.TONALIDADES else "claro")
        self.style().unpolish(self)
        self.style().polish(self)

    def definir(self, texto: str, tonalidade: str | None = None) -> None:
        self.setText(texto)
        if tonalidade:
            self.definir_tonalidade(tonalidade)


class CaixaInfo(QFrame):
    """`small-box` do AdminLTE: número grande, rótulo e ícone d'água à direita."""

    def __init__(
        self,
        rotulo: str,
        valor: str = "—",
        icone_nome: str = "dinheiro",
        tonalidade: str = "primaria",
        legenda: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("caixaInfo")
        self.setProperty("tonalidade", tonalidade)
        self.setMinimumHeight(56)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.rotulo = QLabel(rotulo)
        self.rotulo.setObjectName("caixaInfoRotulo")
        self.valor = QLabel(valor)
        self.valor.setObjectName("caixaInfoValor")
        self.legenda = QLabel(legenda)
        self.legenda.setObjectName("caixaInfoLegenda")
        self.legenda.setWordWrap(True)

        self.icone = QLabel()
        self.icone.setObjectName("caixaInfoIcone")
        self.icone.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icone.setFixedSize(40, 40)

        textos = QVBoxLayout()
        textos.setContentsMargins(0, 0, 0, 0)
        textos.setSpacing(1)
        textos.addWidget(self.rotulo)
        textos.addWidget(self.valor)
        textos.addWidget(self.legenda)

        linha = QHBoxLayout(self)
        linha.setContentsMargins(13, 7, 10, 7)
        linha.setSpacing(6)
        linha.addLayout(textos, 1)
        linha.addWidget(self.icone, 0, Qt.AlignmentFlag.AlignVCenter)

        self._icone_nome = icone_nome
        self._pintar_icone()

    def _pintar_icone(self) -> None:
        from .tema import cor_da_tonalidade

        cor = cor_da_tonalidade(str(self.property("tonalidade")))
        self.icone.setPixmap(icone(self._icone_nome, cor, 26).pixmap(26, 26))

    def definir(
        self, valor: str | None = None, legenda: str | None = None, tonalidade: str | None = None
    ) -> None:
        if valor is not None:
            self.valor.setText(valor)
        if legenda is not None:
            self.legenda.setText(legenda)
        if tonalidade is not None and tonalidade != self.property("tonalidade"):
            self.setProperty("tonalidade", tonalidade)
            self.style().unpolish(self)
            self.style().polish(self)
            self._pintar_icone()


class Cartao(QFrame):
    """`card` do AdminLTE: cabeçalho com título/ferramentas e corpo com conteúdo."""

    def __init__(
        self,
        titulo: str = "",
        subtitulo: str = "",
        parent: QWidget | None = None,
        *,
        sombreado: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("cartao")
        self.titulo = QLabel(titulo)
        self.titulo.setObjectName("cartaoTitulo")
        self.subtitulo = QLabel(subtitulo)
        self.subtitulo.setObjectName("cartaoSubtitulo")
        self.subtitulo.setVisible(bool(subtitulo))
        self.ferramentas = QHBoxLayout()
        self.ferramentas.setContentsMargins(0, 0, 0, 0)
        self.ferramentas.setSpacing(6)

        cabecalho = QWidget()
        cabecalho.setObjectName("cartaoCabecalho")
        linha_cabecalho = QHBoxLayout(cabecalho)
        linha_cabecalho.setContentsMargins(14, 9, 12, 9)
        linha_cabecalho.setSpacing(8)
        textos = QVBoxLayout()
        textos.setContentsMargins(0, 0, 0, 0)
        textos.setSpacing(0)
        textos.addWidget(self.titulo)
        textos.addWidget(self.subtitulo)
        linha_cabecalho.addLayout(textos, 1)
        linha_cabecalho.addLayout(self.ferramentas)

        self.corpo = QVBoxLayout()
        self.corpo.setContentsMargins(14, 12, 14, 12)
        self.corpo.setSpacing(8)

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)
        raiz.addWidget(cabecalho)
        raiz.addLayout(self.corpo, 1)
        if sombreado:
            sombra(self)

    def adicionar(self, widget: QWidget, esticar: int = 0) -> QWidget:
        self.corpo.addWidget(widget, esticar)
        return widget

    def adicionar_layout(self, layout: QVBoxLayout | QHBoxLayout, esticar: int = 0) -> None:
        self.corpo.addLayout(layout, esticar)

    def adicionar_ferramenta(self, widget: QWidget) -> QWidget:
        self.ferramentas.addWidget(widget)
        return widget


class CabecalhoConteudo(QWidget):
    """`content-header`: título da página e trilha de navegação."""

    def __init__(
        self, titulo: str = "", descricao: str = "", parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("cabecalhoConteudo")
        self.titulo = QLabel(titulo)
        self.titulo.setObjectName("tituloConteudo")
        self.descricao = QLabel(descricao)
        self.descricao.setObjectName("descricaoConteudo")
        self.descricao.setWordWrap(True)
        self.trilha = QLabel("")
        self.trilha.setObjectName("trilhaConteudo")
        self.trilha.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        textos = QVBoxLayout()
        textos.setContentsMargins(0, 0, 0, 0)
        textos.setSpacing(1)
        textos.addWidget(self.titulo)
        textos.addWidget(self.descricao)

        linha = QHBoxLayout(self)
        linha.setContentsMargins(18, 12, 18, 8)
        linha.addLayout(textos, 1)
        linha.addWidget(self.trilha, 0, Qt.AlignmentFlag.AlignTop)

    def definir(
        self, titulo: str | None = None, descricao: str | None = None, trilha: list[str] | None = None
    ) -> None:
        if titulo is not None:
            self.titulo.setText(titulo)
        if descricao is not None:
            self.descricao.setText(descricao)
        if trilha is not None:
            self.trilha.setText("  ›  ".join(trilha))


class Rodape(QWidget):
    """Rodapé discreto com o que precisa estar sempre visível."""

    def __init__(self, esquerda: str = "", direita: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("rodape")
        self.esquerda = QLabel(esquerda)
        self.esquerda.setObjectName("rodapeTexto")
        self.direita = QLabel(direita)
        self.direita.setObjectName("rodapeTexto")
        self.direita.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 6, 16, 6)
        layout.addWidget(self.esquerda, 1)
        layout.addWidget(self.direita)


@dataclass(slots=True)
class EntradaNavegacao:
    """Um item de menu: rótulo visível, chave estável e ícone."""

    chave: str
    rotulo: str
    icone: str


class BarraLateral(QFrame):
    """Sidebar do AdminLTE: marca, painel do usuário, menu com ícones e rodapé."""

    modulo_escolhido = Signal(str)

    def __init__(
        self,
        nome_loja: str,
        usuario: str,
        perfil: str,
        paleta: Paleta | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("barraLateral")
        self.setFixedWidth(LARGURA_BARRA_LATERAL)
        self._paleta = paleta or Paleta()
        self._recolhida = False
        self._entradas: list[EntradaNavegacao] = []

        # -- marca -----------------------------------------------------------
        self.marca = QFrame()
        self.marca.setObjectName("marcaBarra")
        self.marca.setFixedHeight(58)
        linha_marca = QHBoxLayout(self.marca)
        linha_marca.setContentsMargins(14, 8, 10, 8)
        linha_marca.setSpacing(9)
        self.monograma = QLabel(nome_loja[:1].upper())
        self.monograma.setObjectName("monograma")
        self.monograma.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.monograma.setFixedSize(30, 30)
        self.rotulo_marca = QLabel(nome_loja)
        self.rotulo_marca.setObjectName("marcaNome")
        self.rotulo_marca.setWordWrap(False)
        self.rotulo_versao_marca = QLabel("PDV · pré-alfa")
        self.rotulo_versao_marca.setObjectName("marcaVersao")
        textos_marca = QVBoxLayout()
        textos_marca.setContentsMargins(0, 0, 0, 0)
        textos_marca.setSpacing(0)
        textos_marca.addWidget(self.rotulo_marca)
        textos_marca.addWidget(self.rotulo_versao_marca)
        linha_marca.addWidget(self.monograma, 0)
        linha_marca.addLayout(textos_marca, 1)

        # -- usuário ---------------------------------------------------------
        self.painel_usuario = QFrame()
        self.painel_usuario.setObjectName("painelUsuario")
        linha_usuario = QHBoxLayout(self.painel_usuario)
        linha_usuario.setContentsMargins(12, 8, 10, 8)
        linha_usuario.setSpacing(9)
        self.avatar = QLabel(iniciais(usuario))
        self.avatar.setObjectName("avatar")
        self.avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar.setFixedSize(32, 32)
        self.rotulo_usuario = QLabel(usuario)
        self.rotulo_usuario.setObjectName("usuarioNome")
        self.rotulo_perfil = QLabel(perfil)
        self.rotulo_perfil.setObjectName("usuarioPerfil")
        textos_usuario = QVBoxLayout()
        textos_usuario.setContentsMargins(0, 0, 0, 0)
        textos_usuario.setSpacing(0)
        textos_usuario.addWidget(self.rotulo_usuario)
        textos_usuario.addWidget(self.rotulo_perfil)
        linha_usuario.addWidget(self.avatar, 0)
        linha_usuario.addLayout(textos_usuario, 1)

        # -- navegação -------------------------------------------------------
        self.lista = QListWidget()
        self.lista.setObjectName("navegacao")
        self.lista.setFrameShape(QFrame.Shape.NoFrame)
        self.lista.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.lista.currentRowChanged.connect(self._escolher)

        self.rodape = QLabel("toda alteração é auditada")
        self.rodape.setObjectName("barraLateralRodape")
        self.rodape.setContentsMargins(14, 6, 14, 8)

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)
        raiz.addWidget(self.marca)
        raiz.addWidget(self.painel_usuario)
        raiz.addWidget(self.lista, 1)
        raiz.addWidget(self.rodape)

    # -- API -----------------------------------------------------------------
    def definir_modulos(self, entradas: list[EntradaNavegacao], selecionado: int = 0) -> None:
        self._entradas = list(entradas)
        self.lista.blockSignals(True)
        self.lista.clear()
        from .tema import misturar

        cor = misturar(self._paleta.primaria_escura, "#FFFFFF", 0.78)
        for entrada in self._entradas:
            item = QListWidgetItem(entrada.rotulo)
            item.setIcon(icone(entrada.icone, cor, 18))
            item.setToolTip(entrada.rotulo)
            item.setSizeHint(QSize(0, ALTURA_ITEM_NAVEGACAO))
            item.setData(Qt.ItemDataRole.UserRole, entrada.chave)
            self.lista.addItem(item)
        self.lista.blockSignals(False)
        if self._entradas:
            self.lista.setCurrentRow(selecionado)

    def chave_atual(self) -> str | None:
        item = self.lista.currentItem()
        return None if item is None else str(item.data(Qt.ItemDataRole.UserRole))

    def chave_do_indice(self, indice: int) -> str | None:
        if 0 <= indice < len(self._entradas):
            return self._entradas[indice].chave
        return None

    def indice_da_chave(self, chave: str) -> int:
        for indice, entrada in enumerate(self._entradas):
            if entrada.chave == chave:
                return indice
        return -1

    def rotulos(self) -> list[str]:
        return [entrada.rotulo for entrada in self._entradas]

    def atualizar_identidade(self, nome_loja: str, usuario: str, perfil: str) -> None:
        self.rotulo_marca.setText(nome_loja)
        self.monograma.setText(nome_loja[:1].upper())
        self.rotulo_usuario.setText(usuario)
        self.rotulo_perfil.setText(perfil)
        self.avatar.setText(iniciais(usuario))

    @property
    def recolhida(self) -> bool:
        return self._recolhida

    def alternar_recolhida(self) -> None:
        self.definir_recolhida(not self._recolhida)

    def definir_recolhida(self, recolhida: bool) -> None:
        self._recolhida = recolhida
        self.setFixedWidth(LARGURA_BARRA_RECOLHIDA if recolhida else LARGURA_BARRA_LATERAL)
        self.rotulo_marca.setVisible(not recolhida)
        self.rotulo_versao_marca.setVisible(not recolhida)
        self.painel_usuario.setVisible(not recolhida)
        self.monograma.setVisible(True)
        self.rodape.setVisible(not recolhida)
        for indice, entrada in enumerate(self._entradas):
            item = self.lista.item(indice)
            item.setText("" if recolhida else entrada.rotulo)
            item.setSizeHint(QSize(0, ALTURA_ITEM_NAVEGACAO))

    def _escolher(self, indice: int) -> None:
        chave = self.chave_do_indice(indice)
        if chave is not None:
            self.modulo_escolhido.emit(chave)


class BarraSuperior(QFrame):
    """Topbar: botão de recolher a sidebar, título da página e chip do usuário."""

    recolher_pedido = Signal()

    def __init__(
        self, titulo: str = "", usuario: str = "", perfil: str = "", parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("barraSuperior")
        self.setFixedHeight(ALTURA_BARRA_SUPERIOR)
        self.botao_menu = QPushButton()
        self.botao_menu.setObjectName("botaoMenu")
        self.botao_menu.setToolTip("Recolher ou expandir o menu")
        self.botao_menu.setCursor(Qt.CursorShape.PointingHandCursor)
        self.botao_menu.setFixedSize(34, 34)
        self.botao_menu.setIconSize(QSize(20, 20))
        self.botao_menu.clicked.connect(self.recolher_pedido.emit)
        self.definir_cor_icone(Paleta().texto_suave)

        self.rotulo_pagina = QLabel(titulo)
        self.rotulo_pagina.setObjectName("barraSuperiorTitulo")
        self.chip_usuario = QLabel(f"{usuario} · {perfil}")
        self.chip_usuario.setObjectName("chipUsuario")
        self.chip_usuario.setAlignment(Qt.AlignmentFlag.AlignCenter)

        linha = QHBoxLayout(self)
        linha.setContentsMargins(8, 0, 14, 0)
        linha.setSpacing(10)
        linha.addWidget(self.botao_menu, 0, Qt.AlignmentFlag.AlignVCenter)
        linha.addWidget(self.rotulo_pagina, 1)
        linha.addWidget(self.chip_usuario, 0, Qt.AlignmentFlag.AlignVCenter)

    def definir_cor_icone(self, cor: str) -> None:
        self.botao_menu.setIcon(icone("menu", cor, 20))

    def definir_usuario(self, usuario: str, perfil: str) -> None:
        self.chip_usuario.setText(f"{usuario} · {perfil}")

    def definir_pagina(self, titulo: str) -> None:
        self.rotulo_pagina.setText(titulo)


def preparar_tabela(tabela: QTableWidget) -> QTableWidget:
    """Tabela que não infla o layout: a altura vem do espaço, não do número de linhas.

    Sem `AdjustIgnored`, cada linha acrescentada aumenta o tamanho mínimo da página
    e a tela inteira passa a rolar — o oposto do que se quer num painel.
    """
    tabela.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored)
    tabela.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    tabela.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    return tabela


def titulo_de_secao(texto: str) -> QLabel:
    """Rótulo em caixa alta usado como divisor dentro de cartões."""
    rotulo = QLabel(texto.upper())
    rotulo.setObjectName("tituloSecao")
    fonte = QFont(rotulo.font())
    fonte.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.6)
    rotulo.setFont(fonte)
    return rotulo


class PilhaDePaginas(QStackedWidget):
    """`QStackedWidget` que se ajusta à página visível.

    O padrão do Qt é reservar a altura da **maior** página; dentro de uma área
    rolável isso faz a tela pequena rolar mesmo quando a página atual caberia
    inteira. Aqui a altura vem da página corrente, e a geometria é recalculada a
    cada troca.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.currentChanged.connect(lambda _indice: self.updateGeometry())

    def sizeHint(self) -> QSize:
        atual = self.currentWidget()
        return atual.sizeHint() if atual is not None else super().sizeHint()

    def minimumSizeHint(self) -> QSize:
        atual = self.currentWidget()
        return atual.minimumSizeHint() if atual is not None else super().minimumSizeHint()
