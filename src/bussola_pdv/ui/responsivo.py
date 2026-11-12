"""Responsividade: a interface se reorganiza pela largura disponível.

O Bússola PDV é usado em balcão de loja — monitor pequeno, notebook 1366×768,
às vezes um segundo monitor 4K. Um layout fixo de 1280 px não serve para os três.

O que existe aqui:

* **pontos de quebra** (`PONTO_COMPACTO`, `PONTO_MEDIO`) e `classe_de_largura()`,
  para que qualquer peça saiba em que faixa está sem repetir números;
* `GradeDeIndicadores`, que reflui os `CaixaInfo` (4 → 2 → 1 por linha) em vez de
  espremer quatro cartões em 300 px;
* `ajustar_dialogo()`, que impede um diálogo de nascer maior que a tela.

Regra do projeto (ADR-021): **não existe tamanho mágico espalhado pelo código**.
Quem precisa reagir à largura lê a faixa daqui; quem tem número fixo justifica no
comentário por que aquele número não pode variar (ícone, altura de linha, etc.).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, ClassVar

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QDialog, QGridLayout, QScrollArea, QSizePolicy, QWidget

if TYPE_CHECKING:  # evita ciclo: widgets não conhece a camada responsiva
    from .widgets import BarraLateral, BarraSuperior, CabecalhoConteudo, Rodape

#: Abaixo disto a janela é "compacta": sidebar recolhida, indicadores 2 por linha.
PONTO_COMPACTO = 900
#: Entre compacto e este valor: "média". Acima: "ampla" (4 indicadores por linha).
PONTO_MEDIO = 1180

CLASSE_COMPACTA = "compacta"
CLASSE_MEDIA = "media"
CLASSE_AMPLA = "ampla"

#: Margem externa do conteúdo: 18 px é confortável, 10 px devolve largura útil.
MARGEM_NORMAL = 18
MARGEM_COMPACTA = 10

ESPACO_ENTRE_INDICADORES = 10
#: Teto de colunas por faixa quando nada mais é dito: 2 no compacto, 3 no médio.
MAXIMOS_POR_FAIXA_PADRAO: dict[str, int] = {CLASSE_COMPACTA: 2, CLASSE_MEDIA: 3}
#: Largura mínima confortável de um `CaixaInfo` (rótulo + número + ícone).
LARGURA_MINIMA_INDICADOR = 210


def classe_de_largura(largura: int) -> str:
    """Faixa de layout para uma largura em pixels (lógica pura, testável)."""
    if largura < PONTO_COMPACTO:
        return CLASSE_COMPACTA
    if largura < PONTO_MEDIO:
        return CLASSE_MEDIA
    return CLASSE_AMPLA


def colunas_para(
    largura: int,
    quantidade: int,
    *,
    largura_minima: int = LARGURA_MINIMA_INDICADOR,
    maximo_por_linha: int = 4,
    maximos_por_faixa: dict[str, int] | None = MAXIMOS_POR_FAIXA_PADRAO,
) -> int:
    """Quantas colunas cabem sem espremer os itens.

    Nunca devolve mais colunas do que itens, e nunca menos que 1 — em tela muito
    estreita os itens empilham, que é o comportamento correto. `maximos_por_faixa`
    aplica um teto por faixa (os indicadores usam 2/3/4).
    """
    cabem = max(1, (largura + ESPACO_ENTRE_INDICADORES) // (
        largura_minima + ESPACO_ENTRE_INDICADORES
    ))
    maximo = maximo_por_linha
    if maximos_por_faixa:
        maximo = min(maximo, maximos_por_faixa.get(classe_de_largura(largura), maximo))
    return max(1, min(quantidade, cabem, maximo))


class GradeQueReflui(QWidget):
    """Widgets lado a lado que viram linhas quando a largura não dá.

    Uso::

        self.indicadores = GradeDeIndicadores([self.kpi_a, self.kpi_b, self.kpi_c])
        layout.addWidget(self.indicadores)

    Quem adicionar/remover item depois chama `definir_indicadores()` — a grade
    recalcula colunas e reposiciona sem recriar widget.
    """

    #: Teto de colunas por faixa de largura (o padrão é o mesmo de `colunas_para`).
    MAXIMOS_POR_FAIXA: ClassVar[dict[str, int] | None] = MAXIMOS_POR_FAIXA_PADRAO
    LARGURA_MINIMA_ITEM: ClassVar[int] = LARGURA_MINIMA_INDICADOR
    MAXIMO_POR_LINHA: ClassVar[int] = 4

    def __init__(
        self,
        indicadores: Sequence[QWidget] = (),
        parent: QWidget | None = None,
        *,
        largura_minima: int | None = None,
        maximo_por_linha: int | None = None,
    ) -> None:
        super().__init__(parent)
        self._largura_minima_item = largura_minima or self.LARGURA_MINIMA_ITEM
        self._maximo_por_linha = maximo_por_linha or self.MAXIMO_POR_LINHA
        self._maximos_por_faixa = self.MAXIMOS_POR_FAIXA
        self._grade = QGridLayout(self)
        self._grade.setContentsMargins(0, 0, 0, 0)
        self._grade.setHorizontalSpacing(ESPACO_ENTRE_INDICADORES)
        self._grade.setVerticalSpacing(ESPACO_ENTRE_INDICADORES)
        self._indicadores: list[QWidget] = []
        self._colunas = 0
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.definir_indicadores(indicadores)

    # -- API ----------------------------------------------------------------
    @property
    def indicadores(self) -> list[QWidget]:
        return list(self._indicadores)

    @property
    def colunas(self) -> int:
        return self._colunas

    def definir_indicadores(self, indicadores: Sequence[QWidget]) -> None:
        for antigo in self._indicadores:
            self._grade.removeWidget(antigo)
        self._indicadores = list(indicadores)
        for indicador in self._indicadores:
            indicador.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
            )
        self._colunas = 0  # força o próximo layout
        self._reorganizar(max(self.width(), self.sizeHint().width()))

    def reorganizar_para(self, largura: int) -> None:
        """Reposiciona para uma largura qualquer (usado por testes e pelo resize)."""
        self._reorganizar(largura)

    # -- Qt -----------------------------------------------------------------
    def resizeEvent(self, evento: QResizeEvent) -> None:
        super().resizeEvent(evento)
        self._reorganizar(evento.size().width())

    def sizeHint(self) -> QSize:
        """Altura acompanha as linhas em uso: 4 cartões em 1 linha ocupam menos."""
        dica = super().sizeHint()
        colunas = self._colunas or 1
        linhas = self._linhas(colunas)
        altura = 0
        for indice in range(linhas):
            faixa = self._indicadores[indice * colunas : (indice + 1) * colunas]
            if faixa:
                altura += max(indicador.sizeHint().height() for indicador in faixa)
        altura += max(0, linhas - 1) * ESPACO_ENTRE_INDICADORES
        return QSize(dica.width(), max(dica.height(), altura))

    # -- interno ------------------------------------------------------------
    def _linhas(self, colunas: int) -> int:
        if not self._indicadores:
            return 0
        return (len(self._indicadores) + colunas - 1) // colunas

    def _reorganizar(self, largura: int) -> None:
        if not self._indicadores:
            self._colunas = 0
            return
        colunas = colunas_para(
            max(largura, 1),
            len(self._indicadores),
            largura_minima=self._largura_minima_item,
            maximo_por_linha=self._maximo_por_linha,
            maximos_por_faixa=self._maximos_por_faixa,
        )
        if colunas == self._colunas and self._grade.count():
            return
        self._colunas = colunas
        for indicador in self._indicadores:
            self._grade.removeWidget(indicador)
        for indice, indicador in enumerate(self._indicadores):
            self._grade.addWidget(indicador, indice // colunas, indice % colunas)
        # colunas que sobraram não devem reservar espaço
        for coluna in range(colunas):
            self._grade.setColumnStretch(coluna, 1)
        for coluna in range(colunas, 12):
            self._grade.setColumnStretch(coluna, 0)
        # A altura mínima precisa acompanhar as linhas: com 3 cartões em 2 colunas
        # são 2 linhas, e sem isto o segundo cartão fica por cima do primeiro.
        self.setMinimumHeight(self.sizeHint().height())
        self.updateGeometry()


class GradeDeIndicadores(GradeQueReflui):
    """Grade de `CaixaInfo`: 4 cartões por linha em tela ampla, 2 no compacto."""

    MAXIMOS_POR_FAIXA: ClassVar[dict[str, int]] = {
        CLASSE_COMPACTA: 2,
        CLASSE_MEDIA: 3,
    }
    LARGURA_MINIMA_ITEM: ClassVar[int] = LARGURA_MINIMA_INDICADOR
    MAXIMO_POR_LINHA: ClassVar[int] = 4


class GradeDeCartoes(GradeQueReflui):
    """Dois blocos de conteúdo lado a lado que empilham em janela estreita."""

    LARGURA_MINIMA_ITEM: ClassVar[int] = 360
    MAXIMO_POR_LINHA: ClassVar[int] = 2


def abrir_no_tamanho_da_tela(
    janela: QWidget,
    largura_preferida: int,
    altura_preferida: int,
    *,
    fracao: float = 0.92,
    area: QRect | None = None,
) -> QSize:
    """Abre a janela **dentro da tela** — o pedido é um teto, não uma promessa.

    `resize(1280, 820)` ignora a tela: num notebook 1366×768 com escala de 125%
    (1093×614 px lógicos) ou 150% (911×512) a janela nasce maior do que o monitor
    e o Windows a corta — o operador perde o rodapé e os botões da direita. Aqui o
    tamanho pedido é reduzido até caber na área disponível (descontando a barra de
    tarefas) e a janela é centralizada. Nunca abaixo do mínimo declarado.
    """
    from PySide6.QtGui import QGuiApplication

    alvo = QSize(max(320, largura_preferida), max(240, altura_preferida))
    if area is None:
        tela = QGuiApplication.primaryScreen()
        area = tela.availableGeometry() if tela is not None else None
    if area is not None:
        alvo = QSize(
            min(alvo.width(), max(320, int(area.width() * fracao))),
            min(alvo.height(), max(240, int(area.height() * fracao))),
        )
        minimo = janela.minimumSize()
        alvo = QSize(max(alvo.width(), minimo.width()), max(alvo.height(), minimo.height()))
        janela.resize(alvo)
        janela.move(
            area.x() + max(0, (area.width() - alvo.width()) // 2),
            area.y() + max(0, (area.height() - alvo.height()) // 2),
        )
        return alvo
    janela.resize(alvo)  # pragma: no cover - sem servidor gráfico
    return alvo


def ajustar_dialogo(
    dialogo: QDialog,
    *,
    largura_preferida: int = 460,
    altura_preferida: int | None = None,
    margem: int = 32,
) -> QDialog:
    """Impede que um diálogo nasça maior do que a tela disponível.

    Em tela pequena (1024×600 de balcão) um diálogo de 560 px de largura mínima
    empurra botões para fora da área visível. Aqui o mínimo desce até caber, e a
    altura é limitada quando o conteúdo passaria da tela.
    """
    from PySide6.QtGui import QGuiApplication

    tela = QGuiApplication.primaryScreen()
    if tela is None:  # pragma: no cover - sem servidor gráfico
        dialogo.setMinimumWidth(largura_preferida)
        return dialogo
    area = tela.availableGeometry()
    dialogo.setMinimumWidth(max(280, min(largura_preferida, area.width() - margem)))
    # Altura: o diálogo não pode passar da tela, mas também não pode fixar um
    # mínimo que estoure em tela baixa (600 px de balcão, 512 lógicos a 150%).
    dialogo.setMinimumHeight(min(240, max(180, area.height() - margem)))
    if altura_preferida is not None:
        dialogo.setMaximumHeight(max(240, min(altura_preferida, area.height() - margem)))
    else:
        dialogo.setMaximumHeight(max(240, area.height() - margem))
    dialogo.setSizeGripEnabled(True)
    return dialogo


class RolagemDeCartao(QScrollArea):
    """Rolagem que **pede** a altura do cartão e aceita ser encolhida.

    `QScrollArea` devolve um `sizeHint` miúdo (o do visor): com o cartão de login
    dentro dela o diálogo abria com 286 px e o formulário aparecia cortado, com
    barra, mesmo sobrando tela. Aqui o tamanho natural é o do conteúdo; quando a
    tela é menor, o teto de `ajustar_dialogo` manda e a barra entra em ação.
    """

    def sizeHint(self) -> QSize:
        dica = super().sizeHint()
        interno = self.widget()
        if interno is None:
            return dica
        return QSize(
            max(dica.width(), interno.sizeHint().width()),
            max(dica.height(), interno.sizeHint().height()),
        )


def envolver_em_rolagem(cartao: QWidget) -> QWidget:
    """Põe um cartão de diálogo dentro de uma rolagem, centralizado.

    Diálogos de login, primeiro uso e autorização têm altura de formulário (600 px
    ou mais). Em tela baixa — notebook 1366×768 com escala de 150%, cujo espaço
    lógico é 911×512 — o cartão era cortado em cima e embaixo, sem barra nenhuma.
    Com a rolagem o conteúdo continua inteiro; quando cabe, não aparece barra.
    """
    area = RolagemDeCartao()
    area.setObjectName("rolagemDialogo")
    area.setFrameShape(QScrollArea.Shape.NoFrame)
    area.setWidgetResizable(True)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.setWidget(cartao)
    return area


class CascaResponsiva:
    """Comportamento comum às janelas com sidebar + barra superior.

    Herdado por `JanelaPrincipal` (QMainWindow) e `JanelaAdmin` (QDialog) — os dois
    têm a mesma casca e por isso reagem igual à largura:

    * **compacta** (< 900 px): sidebar recolhida, chip do usuário, trilha e lado
      direito do rodapé escondidos, margens menores;
    * **média** (< 1180 px): sidebar normal, chip ainda visível;
    * **ampla**: tudo visível.

    O botão do menu continua mandando: quando o operador recolhe/expande na mão, a
    escolha vale até a janela mudar de faixa (aí a régua automática volta a valer,
    que é como o AdminLTE se comporta).
    """

    barra_lateral: BarraLateral
    barra_superior: BarraSuperior

    def _iniciar_casca(self, definir_margens: Callable[[int], None] | None = None) -> None:
        self._classe_da_casca = ""
        self._escolha_manual: bool | None = None
        self._definir_margens = definir_margens
        self._cabecalho: CabecalhoConteudo | None = None
        self._rodape: Rodape | None = None

    # -- API ----------------------------------------------------------------
    @property
    def classe_da_casca(self) -> str:
        return self._classe_da_casca

    def alternar_casca_recolhida(self) -> None:
        """Recolhe/expande a sidebar a pedido do operador e fixa essa escolha."""
        recolhida = not self.barra_lateral.recolhida
        self._escolha_manual = recolhida
        self.barra_lateral.definir_recolhida(recolhida)

    def reorganizar_casca(self, largura: int) -> str:
        """Aplica a faixa de largura à casca. Devolve a faixa em uso."""
        classe = classe_de_largura(largura)
        if classe != self._classe_da_casca:
            self._classe_da_casca = classe
            self._escolha_manual = None  # trocou de faixa: volta à régua automática
            if self._definir_margens is not None:
                self._definir_margens(MARGEM_COMPACTA if classe == CLASSE_COMPACTA else MARGEM_NORMAL)
        compacta = classe == CLASSE_COMPACTA
        if self._escolha_manual is None:
            self.barra_lateral.definir_recolhida(compacta)
        self.barra_superior.chip_usuario.setVisible(not compacta)
        self._aplicar_complementos(compacta)
        return classe

    def ajustar_complementos(
        self, cabecalho: CabecalhoConteudo | None = None, rodape: Rodape | None = None
    ) -> None:
        """Guarda as peças que se escondem na faixa compacta (trilha e rodapé)."""
        self._cabecalho = cabecalho
        self._rodape = rodape
        self._aplicar_complementos(self._classe_da_casca == CLASSE_COMPACTA)

    def _aplicar_complementos(self, compacta: bool) -> None:
        if self._cabecalho is not None:
            self._cabecalho.trilha.setVisible(not compacta)
        if self._rodape is not None:
            self._rodape.direita.setVisible(not compacta)


__all__ = [
    "CLASSE_AMPLA",
    "CLASSE_COMPACTA",
    "CLASSE_MEDIA",
    "ESPACO_ENTRE_INDICADORES",
    "LARGURA_MINIMA_INDICADOR",
    "MARGEM_COMPACTA",
    "MARGEM_NORMAL",
    "PONTO_COMPACTO",
    "PONTO_MEDIO",
    "CascaResponsiva",
    "FluxoDeAcoes",
    "GradeDeCartoes",
    "GradeDeIndicadores",
    "GradeQueReflui",
    "RolagemDeCartao",
    "abrir_no_tamanho_da_tela",
    "ajustar_dialogo",
    "classe_de_largura",
    "colunas_para",
    "envolver_em_rolagem",
]


class FluxoDeAcoes(QWidget):
    """Fileira de ações que quebra em linhas em vez de sair pela borda.

    `QHBoxLayout` não quebra: uma fileira de sete botões ("Aplicar perfil", "Ativar",
    "Desativar", "Redefinir senha", "Transferir propriedade…") ficava cortada na borda
    em 800 px de janela. Aqui os filhos são posicionados em linhas sucessivas.

    A geometria é calculada à mão de propósito: usar um `QLayout` próprio exigiria
    guardar `QLayoutItem` em Python, e o PySide não garante a vida desses itens —
    a alternativa produzia *segmentation fault* quando a janela era destruída.

    Uso::

        acoes = FluxoDeAcoes()
        for botao in botoes:
            acoes.adicionar(botao)
        grupo.addWidget(acoes)
    """

    def __init__(self, parent: QWidget | None = None, *, espaco: int = 6) -> None:
        super().__init__(parent)
        self._acoes: list[QWidget] = []
        self._espaco = espaco
        self._altura = 0
        politica = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        politica.setHeightForWidth(True)
        self.setSizePolicy(politica)

    # -- API ----------------------------------------------------------------
    @property
    def widgets(self) -> list[QWidget]:
        return list(self._acoes)

    def adicionar(self, widget: QWidget) -> QWidget:
        # `setParent` esconde o filho; só o reexibimos se ele não estava
        # explicitamente escondido. Sem esta checagem, `widget.show()` desfazia o
        # `setVisible(False)` de botões sem permissão (Exportar/Imprimir).
        visivel = not widget.isHidden()
        widget.setParent(self)
        if visivel:
            widget.show()
        self._acoes.append(widget)
        self._recalcular()
        return widget

    def adicionar_espaco(self, largura: int = 0) -> None:
        """Compatível com o `addStretch` de antes: no fluxo o alinhamento já é à esquerda."""
        if largura > 0:
            vazio = QWidget(self)
            vazio.setFixedWidth(largura)
            self.adicionar(vazio)

    # -- geometria ----------------------------------------------------------
    def _visiveis(self) -> list[QWidget]:
        return [acao for acao in self._acoes if acao.isVisibleTo(self) or not acao.isHidden()]

    def _organizar(self, largura: int, *, aplicar: bool) -> int:
        x = y = altura_da_linha = 0
        for acao in self._acoes:
            if acao.isHidden():
                continue
            dica = acao.sizeHint()
            if x and x + dica.width() > largura:
                x = 0
                y += altura_da_linha + self._espaco
                altura_da_linha = 0
            if aplicar:
                acao.setGeometry(QRect(x, y, dica.width(), dica.height()))
            x += dica.width() + self._espaco
            altura_da_linha = max(altura_da_linha, dica.height())
        return y + altura_da_linha

    def _recalcular(self) -> None:
        altura = self._organizar(max(self.width(), 1), aplicar=True)
        if altura != self._altura:
            self._altura = altura
            self.updateGeometry()

    # -- Qt -----------------------------------------------------------------
    def resizeEvent(self, evento: QResizeEvent) -> None:
        super().resizeEvent(evento)
        self._recalcular()

    def sizeHint(self) -> QSize:
        largura = sum(acao.sizeHint().width() + self._espaco for acao in self._acoes)
        return QSize(largura, self._altura or max(
            (acao.sizeHint().height() for acao in self._acoes), default=0
        ))

    def minimumSizeHint(self) -> QSize:
        altura = max((acao.sizeHint().height() for acao in self._acoes), default=0)
        return QSize(
            max((acao.minimumSizeHint().width() for acao in self._acoes), default=0), altura
        )

    def heightForWidth(self, largura: int) -> int:
        return self._organizar(max(largura, 1), aplicar=False)

    def hasHeightForWidth(self) -> bool:
        return True


