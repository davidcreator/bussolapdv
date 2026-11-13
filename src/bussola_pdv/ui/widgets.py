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

from PySide6.QtCore import QEvent, QObject, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QResizeEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractScrollArea,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
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

from ..dominio.marca import Marca, Paleta
from .icones import icone
from .identidade import FOLGA_MONOGRAMA, simbolo, tinta_do_simbolo
from .responsivo import FluxoDeAcoes

ALTURA_BARRA_SUPERIOR = 52
ALTURA_ITEM_NAVEGACAO = 40
LARGURA_BARRA_LATERAL = 226
LARGURA_BARRA_RECOLHIDA = 62
#: Nenhuma coluna fica mais estreita que isto: cabeçalho cortado não é informação.
LARGURA_MINIMA_COLUNA = 84
#: Abaixo desta largura as ferramentas do cartão (exportar, resumo) descem de linha.
LARGURA_CABECALHO_LADO_A_LADO = 640


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


#: Altura mínima de um `CaixaInfo`: rótulo + valor (corpo grande) + legenda + margens.
ALTURA_CAIXA_INFO = 74


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
        # 74 px, não 56: o valor em corpo grande vem do QSS, e o `sizeHint` do
        # `QLabel` é medido antes de a folha de estilo ser aplicada — com 56 o
        # número ficava cortado embaixo na grade de duas colunas (janela compacta).
        self.setMinimumHeight(ALTURA_CAIXA_INFO)
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

    def sizeHint(self) -> QSize:
        dica = super().sizeHint()
        return QSize(dica.width(), max(dica.height(), ALTURA_CAIXA_INFO))

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
        # `FluxoDeAcoes` (e não `QHBoxLayout`) porque ferramenta de cartão cresce:
        # "Exportar" + "Imprimir" + resumo do filtro não cabiam lado a lado e
        # impunham largura mínima à página inteira. No fluxo, quebram de linha.
        self.ferramentas = FluxoDeAcoes()

        self.titulo.setWordWrap(True)
        self.subtitulo.setWordWrap(True)  # em tela estreita o texto quebra em vez de alargar

        self.cabecalho = QWidget()
        self.cabecalho.setObjectName("cartaoCabecalho")
        # Grade (e não HBox) porque o cabeçalho tem duas formas: título e
        # ferramentas lado a lado, ou ferramentas numa segunda linha quando o
        # cartão é estreito. Ver `_reorganizar_cabecalho`.
        self._grade_cabecalho = QGridLayout(self.cabecalho)
        self._grade_cabecalho.setContentsMargins(14, 9, 12, 9)
        self._grade_cabecalho.setSpacing(8)
        textos = QVBoxLayout()
        textos.setContentsMargins(0, 0, 0, 0)
        textos.setSpacing(0)
        textos.addWidget(self.titulo)
        textos.addWidget(self.subtitulo)
        self._moldura_ferramentas = self.ferramentas
        self._grade_cabecalho.addLayout(textos, 0, 0)
        # sem alinhamento fixo: a célula entrega a largura disponível e o fluxo
        # decide quantas ferramentas cabem por linha
        self._grade_cabecalho.addWidget(
            self._moldura_ferramentas,
            0,
            1,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        self._grade_cabecalho.setColumnStretch(0, 1)
        self._cabecalho_empilhado = False

        self.corpo = QVBoxLayout()
        self.corpo.setContentsMargins(14, 12, 14, 12)
        self.corpo.setSpacing(8)

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)
        raiz.addWidget(self.cabecalho)
        raiz.addLayout(self.corpo, 1)
        if sombreado:
            sombra(self)

    def adicionar(self, widget: QWidget, esticar: int = 0) -> QWidget:
        self.corpo.addWidget(widget, esticar)
        return widget

    def adicionar_layout(self, layout: QVBoxLayout | QHBoxLayout, esticar: int = 0) -> None:
        self.corpo.addLayout(layout, esticar)

    def adicionar_ferramenta(self, widget: QWidget) -> QWidget:
        self.ferramentas.adicionar(widget)
        return widget

    # -- responsividade -----------------------------------------------------
    def minimumSizeHint(self) -> QSize:
        """O cabeçalho **sempre** cabe em uma coluna, então ele não dita o mínimo.

        Antes da primeira exibição o cabeçalho ainda está lado a lado e o mínimo do
        cartão virava a soma título + ferramentas (614 px na Auditoria, 522 px em
        Parâmetros). Isso virava o piso da janela inteira — mais larga do que a tela
        de um notebook com escala. Aqui vale a maior peça isolada: título largo ou
        a ferramenta mais larga, nunca as duas somadas.
        """
        dica = super().minimumSizeHint()
        ferramentas = self.ferramentas.minimumSizeHint().width()
        largura = max(ferramentas, self.titulo.minimumSizeHint().width(), 240) + 34
        return QSize(min(dica.width(), largura), dica.height())

    def resizeEvent(self, evento: QResizeEvent) -> None:
        super().resizeEvent(evento)
        self._reorganizar_cabecalho(evento.size().width())

    def _reorganizar_cabecalho(self, largura: int) -> None:
        """Ferramentas do cabeçalho descem de linha quando não cabem ao lado do título.

        Sem isto, um cartão com "Exportar Excel/PDF" ao lado de um subtítulo longo
        impunha 949 px de largura mínima à página inteira — e a página era cortada
        em monitor de 1024.
        """
        if not hasattr(self, "_grade_cabecalho"):
            return
        empilhado = largura < LARGURA_CABECALHO_LADO_A_LADO
        if empilhado == self._cabecalho_empilhado and self._grade_cabecalho.count():
            return
        self._cabecalho_empilhado = empilhado
        self._grade_cabecalho.removeWidget(self._moldura_ferramentas)
        if empilhado:
            alinhamento = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            self._grade_cabecalho.addWidget(self._moldura_ferramentas, 1, 0, alinhamento)
        else:
            alinhamento = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            self._grade_cabecalho.addWidget(self._moldura_ferramentas, 0, 1, alinhamento)
        self.updateGeometry()


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


#: Folga em pixels antes de cortar um rótulo com "…".
TOLERANCIA_DE_ELIPSE = 4


class RotuloElastico(QLabel):
    """Rótulo que **encolhe** com reticências em vez de empurrar o layout.

    Um `QLabel` comum exige a largura do texto no mínimo: o rodapé
    ("Loja · dados locais, sem emissão fiscal" + "Bússola PDV · pré-alfa") somava
    585 px e virava o piso da janela administrativa inteira — 946 px, mais do que
    a tela de um notebook com escala de 125%. Aqui o texto completo fica guardado
    (`texto_completo`) e o pintado é a versão cortada com "…".
    """

    def __init__(self, texto: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._completo = ""
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setText(texto)

    def setText(self, texto: str) -> None:
        self._completo = texto
        self.setToolTip(texto)
        super().setText(texto)
        self._ajustar_elipse()

    def text(self) -> str:
        return self._completo

    def texto_completo(self) -> str:
        return self._completo

    def resizeEvent(self, evento: QResizeEvent) -> None:
        super().resizeEvent(evento)
        self._ajustar_elipse()

    def _ajustar_elipse(self) -> None:
        disponivel = self.width()
        if disponivel <= 0 or not self._completo:
            return
        # Tolerância de 4 px: `elidedText` reserva a largura do "…" e cortava nomes
        # que cabiam por um fio (o da loja na sidebar virava "Loja de Demonstr…").
        cortado = self.fontMetrics().elidedText(
            self._completo, Qt.TextElideMode.ElideRight, disponivel + TOLERANCIA_DE_ELIPSE
        )
        if cortado != super().text():
            super().setText(cortado)


class Rodape(QWidget):
    """Rodapé discreto com o que precisa estar sempre visível."""

    def __init__(self, esquerda: str = "", direita: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("rodape")
        self.esquerda = RotuloElastico(esquerda)
        self.esquerda.setObjectName("rodapeTexto")
        self.direita = RotuloElastico(direita)
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


#: Lado do quadrado do símbolo no canto do menu (px lógicos).
LADO_MONOGRAMA = 34


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
        # O quadrado branco continua (é ele que garante contraste em qualquer
        # paleta); dentro dele agora vai o **logo**, não a inicial da loja.
        self.monograma = QLabel()
        self.monograma.setObjectName("monograma")
        self.monograma.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.monograma.setFixedSize(LADO_MONOGRAMA, LADO_MONOGRAMA)
        self._logo_loja: str = ""
        self._definir_simbolo()
        # Nome da loja e do operador comem a largura da sidebar (240 px) e o nome
        # comprido saía cortado na borda: com o rótulo elástico vira "Loja de Demo…".
        self.rotulo_marca = RotuloElastico(nome_loja)
        self.rotulo_marca.setObjectName("marcaNome")
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
        self.rotulo_usuario = RotuloElastico(usuario)
        self.rotulo_usuario.setObjectName("usuarioNome")
        self.rotulo_perfil = RotuloElastico(perfil)
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

    def atualizar_identidade(
        self,
        nome_loja: str,
        usuario: str,
        perfil: str,
        *,
        logo: str = "",
    ) -> None:
        """Nome da loja, operador e o logo do canto do menu.

        `logo` é o PNG em data URI enviado pela loja (ADR-028). Vem vazio na
        maioria dos casos, e aí o símbolo do Bússola aparece — a área
        administrativa passa `oficial=True` em `definir_logo_oficial`.
        """
        self.rotulo_marca.setText(nome_loja)
        self.rotulo_usuario.setText(usuario)
        self.rotulo_perfil.setText(perfil)
        self.avatar.setText(iniciais(usuario))
        self.definir_logo(logo)

    def definir_logo(self, logo: str) -> None:
        """Troca o símbolo do menu pelo logo da loja (string vazia = oficial)."""
        self._logo_loja = logo
        self.monograma.setToolTip(
            "Logo da loja" if logo else "Bússola PDV (marca oficial)"
        )
        self._definir_simbolo()

    def _definir_simbolo(self) -> None:
        """Desenha o logo dentro do quadrado, tingido com a cor primária.

        Tingir não é capricho: o arquivo oficial é azul-marinho e a loja pode ter
        escolhido um tema escuro, ou azul, no qual o traço desapareceria. Como o
        logo é de tinta única, pintar preserva o desenho e o `#monograma` branco
        garante o contraste (ADR-024).
        """
        janela = self.window()
        tela = janela.screen() if janela is not None else None
        densidade = float(tela.devicePixelRatio()) if tela is not None else 1.0
        lado = LADO_MONOGRAMA - 2 * FOLGA_MONOGRAMA
        marca = None
        if self._logo_loja:
            marca = Marca(nome_fantasia="Loja", logo_data_uri=self._logo_loja)
        desenhado = simbolo(
            marca,
            lado=lado,
            cor=tinta_do_simbolo(self._paleta.primaria),
            proporcao=densidade,
        )
        self.monograma.setPixmap(desenhado)

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

        self.rotulo_pagina = RotuloElastico(titulo)
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
        self._linha = linha

    def definir_marca(self, widget: QWidget | None) -> None:
        """Põe (ou tira) uma marca à direita do título, antes do chip do usuário.

        É o que a área administrativa usa para deixar a assinatura oficial do
        Bússola sempre visível: o logo da loja não entra ali (ADR-028). O lugar
        escolhido é a barra superior — dentro do conteúdo o logo caía sobre a
        trilha e ficava ilegível.
        """
        if widget is None:
            return
        self._linha.insertWidget(self._linha.count() - 1, widget, 0, Qt.AlignmentFlag.AlignVCenter)

    def definir_cor_icone(self, cor: str) -> None:
        self.botao_menu.setIcon(icone("menu", cor, 20))

    def definir_usuario(self, usuario: str, perfil: str) -> None:
        self.chip_usuario.setText(f"{usuario} · {perfil}")

    def definir_pagina(self, titulo: str) -> None:
        self.rotulo_pagina.setText(titulo)


def preparar_tabela(tabela: QTableWidget) -> QTableWidget:
    """Tabela que não infla o layout: a altura vem do espaço, não do número de linhas.

    Sem `AdjustIgnored`, cada linha acrescentada aumenta o tamanho mínimo da página
    e a tela inteira passa a rolar — o oposto do que se quer num painel. A largura
    mínima de coluna impede que a coluna elástica colapse numa tela estreita: em vez
    de cortar o cabeçalho, a tabela ganha rolagem horizontal própria.
    """
    tabela.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored)
    tabela.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    tabela.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    tabela.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    tabela.horizontalHeader().setMinimumSectionSize(LARGURA_MINIMA_COLUNA)
    return tabela


class ColunasDaTabela(QObject):
    """Colunas que preenchem a largura quando sobra e rolam quando falta.

    Duas formas, escolhidas pela largura do momento:

    * **cabe** — colunas com a largura do conteúdo e a coluna *elástica* esticada
      (o visual de painel, sem espaço vazio à direita);
    * **não cabe** — todas com a largura do conteúdo e a última esticada; o total
      passa da área visível e a tabela ganha rolagem horizontal **própria**, com
      todas as colunas legíveis.

    A alternativa era deixar o `Stretch` espremer a coluna elástica: em 800 px de
    janela o cabeçalho "Descrição" virava "›escriçã" e "Saldo" ficava fora da tela.
    A medição custa ~45 ms em 1000 linhas, então só roda quando a largura muda
    (com espera de 150 ms), nunca a cada tecla digitada na busca.
    """

    ATRASO_MS = 150

    def __init__(self, tabela: QTableWidget, esticada: int = 0) -> None:
        super().__init__(tabela)
        self._tabela = tabela
        self._esticada = esticada
        self._modo_rolagem = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._aplicar)
        tabela.viewport().installEventFilter(self)
        self._aplicar()

    @property
    def modo_rolagem(self) -> bool:
        return self._modo_rolagem

    def reconfigurar(self, esticada: int) -> None:
        """Nova coluna elástica (a tabela foi montada de novo com outras colunas)."""
        self._esticada = esticada
        self._modo_rolagem = False
        self._aplicar()

    def eventFilter(self, objeto: QObject, evento: QEvent) -> bool:
        if evento.type() == QEvent.Type.Resize:
            self._timer.start(self.ATRASO_MS)
        return False

    def _necessario(self) -> int:
        """Largura que a tabela precisa para mostrar todas as colunas legíveis."""
        tabela = self._tabela
        minimo = tabela.horizontalHeader().minimumSectionSize()
        total = sum(
            max(tabela.sizeHintForColumn(coluna), minimo)
            for coluna in range(tabela.columnCount())
        )
        return total + 2 * tabela.frameWidth()

    def _aplicar(self) -> None:
        self._timer.stop()
        tabela = self._tabela
        if tabela.columnCount() == 0:
            return
        cabecalho = tabela.horizontalHeader()
        disponivel = tabela.viewport().width()
        if disponivel <= 0:
            return
        rolagem = self._necessario() > disponivel
        if rolagem == self._modo_rolagem and cabecalho.count():
            return
        self._modo_rolagem = rolagem
        cabecalho.setStretchLastSection(rolagem)
        for coluna in range(tabela.columnCount()):
            modo = QHeaderView.ResizeMode.ResizeToContents
            if not rolagem and coluna == self._esticada:
                modo = QHeaderView.ResizeMode.Stretch
            cabecalho.setSectionResizeMode(coluna, modo)


def ajustar_colunas(tabela: QTableWidget, esticada: int = 0) -> QTableWidget:
    """Colunas com a largura do conteúdo; a `esticada` fica com o espaço que sobra.

    Sem isso, `Stretch` puro espremia "Ponto de pedido" e "Valor a custo" a ponto
    de cortar o cabeçalho e o `R$` do valor. Quem decide se cabe é
    `ColunasDaTabela`, que também instala a rolagem quando não cabe.
    """
    cabecalho = tabela.horizontalHeader()
    for indice in range(tabela.columnCount()):
        modo = (
            QHeaderView.ResizeMode.Stretch
            if indice == esticada
            else QHeaderView.ResizeMode.ResizeToContents
        )
        cabecalho.setSectionResizeMode(indice, modo)
    vigia = tabela.findChild(ColunasDaTabela)
    if vigia is None:
        # O pai (a tabela) mantém o vigia vivo; sem um registro paralelo não há
        # ciclo Python e nada vaza quando a tabela é destruída.
        vigia = ColunasDaTabela(tabela, esticada)
    else:
        vigia.reconfigurar(esticada)
    tabela.viewport().installEventFilter(vigia)
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
