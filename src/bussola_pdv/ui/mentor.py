"""Mentor na tela: o balão que conduz o operador passo a passo.

Como funciona, e por que assim:

* **não cobre a tela.** Nada de máscara escura em cima do conteúdo — o operador
  precisa ver o que está fazendo. O mentor é uma faixa no rodapé do conteúdo e o
  destaque é a **borda** do campo do passo (propriedade `destaqueMentor`), aplicada
  pela folha de estilo. Sem sobreposição, sem geometria calculada à mão, sem
  `QGraphicsEffect` que pesa no Windows.
* **o alvo é por nome.** Cada passo traz o nome do atributo do widget na tela
  (`campo_codigo`, `botao_finalizar`) e o painel resolve com `getattr`. Se o campo
  sumir, o passo continua aparecendo como texto — o mentor explica, nunca quebra.
* **quem manda é o operador.** Anterior/Próximo/Concluir, e "Parar" desliga o modo
  guiado (fica desligado até alguém religar na Ajuda).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QResizeEvent, QShowEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..aplicacao.ajuda import Passo, Tema
from .responsivo import FluxoDeAcoes

#: Propriedade dinâmica que liga a borda de destaque na folha de estilo.
PROPRIEDADE_DESTAQUE = "destaqueMentor"


def _aplicar_destaque(widget: QWidget | None, *, ativo: bool) -> None:
    """Marca/desmarca o widget na folha de estilo e repinta só ele."""
    if widget is None:
        return
    widget.setProperty(PROPRIEDADE_DESTAQUE, "true" if ativo else "false")
    estilo = widget.style()
    if estilo is not None:
        estilo.unpolish(widget)
        estilo.polish(widget)
    widget.update()


class PainelMentor(QFrame):
    """Faixa de condução: título, texto do passo, contador e navegação."""

    #: O operador pediu para abrir o guia completo.
    guia_pedido = Signal()
    #: O operador desligou o modo guiado (a janela grava a preferência).
    encerrado = Signal()
    #: O tour terminou (todos os passos vistos).
    concluido = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("painelMentor")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self._passos: tuple[Passo, ...] = ()
        self._alvos: dict[str, QWidget] = {}
        self._indice = 0
        self._tema: Tema | None = None
        self._destacado: QWidget | None = None

        self.rotulo_titulo = QLabel()
        self.rotulo_titulo.setObjectName("mentorTitulo")
        self.rotulo_titulo.setWordWrap(True)
        self.rotulo_texto = QLabel()
        self.rotulo_texto.setObjectName("mentorTexto")
        self.rotulo_texto.setWordWrap(True)
        self.rotulo_contador = QLabel()
        self.rotulo_contador.setObjectName("mentorContador")

        textos = QVBoxLayout()
        textos.setContentsMargins(0, 0, 0, 0)
        textos.setSpacing(2)
        textos.addWidget(self.rotulo_titulo)
        textos.addWidget(self.rotulo_texto)

        self.botao_anterior = QPushButton("Anterior")
        self.botao_anterior.setObjectName("secundario")
        self.botao_anterior.clicked.connect(self.anterior)
        self.botao_proximo = QPushButton("Próximo")
        self.botao_proximo.clicked.connect(self.proximo)
        self.botao_concluir = QPushButton("Concluir")
        self.botao_concluir.clicked.connect(self._concluir)
        self.botao_guia = QPushButton("Guia completo (F1)")
        self.botao_guia.setObjectName("secundario")
        self.botao_guia.clicked.connect(self.guia_pedido.emit)
        self.botao_parar = QPushButton("Parar")
        self.botao_parar.setObjectName("link")
        self.botao_parar.setToolTip("Desliga o uso orientado; religue na Ajuda quando quiser")
        self.botao_parar.clicked.connect(self._parar)

        # `FluxoDeAcoes` em vez de `QHBoxLayout`: em 640 px de janela a fileira de
        # cinco botões não caberia e seria cortada na borda; assim ela quebra linha.
        self.acoes = FluxoDeAcoes(espaco=6)
        for botao in (
            self.botao_anterior,
            self.botao_proximo,
            self.botao_concluir,
            self.botao_guia,
            self.botao_parar,
        ):
            self.acoes.adicionar(botao)

        topo = QHBoxLayout()
        topo.setContentsMargins(0, 0, 0, 0)
        topo.setSpacing(10)
        topo.addLayout(textos, 1)
        topo.addWidget(self.rotulo_contador, 0, Qt.AlignmentFlag.AlignTop)

        linha = QVBoxLayout(self)
        linha.setContentsMargins(14, 8, 12, 8)
        linha.setSpacing(6)
        linha.addLayout(topo)
        linha.addWidget(self.acoes)
        self.setVisible(False)

    # -- eventos ------------------------------------------------------------
    def showEvent(self, evento: QShowEvent) -> None:
        super().showEvent(evento)
        self._reaplicar()

    def resizeEvent(self, evento: QResizeEvent) -> None:
        super().resizeEvent(evento)
        self._reaplicar()

    def _reaplicar(self) -> None:
        """Redestaca o passo atual depois que o layout assentou.

        O mentor nasce enquanto a janela ainda está sendo montada: aí a geometria dos
        campos ainda é provisória e `ensureWidgetVisible` não rola para lugar nenhum.
        Reaplicar no `resizeEvent`/`showEvent` resolve sem depender de tempo fixo — e
        um único `singleShot(0)` cobre o caso em que nada mais redimensiona.
        """
        if not self._passos:
            return
        QTimer.singleShot(0, self._reaplicar_agora)

    def _reaplicar_agora(self) -> None:
        if self._passos and self.isVisible():
            self._destacar(self._passos[self._indice].alvo)

    # -- API ----------------------------------------------------------------
    @property
    def tema(self) -> Tema | None:
        return self._tema

    @property
    def indice(self) -> int:
        return self._indice

    @property
    def passos(self) -> tuple[Passo, ...]:
        return self._passos

    def visivel(self) -> bool:
        return bool(self._passos) and self.isVisible()

    def iniciar(self, tema: Tema | None, alvos: dict[str, QWidget], *, indice: int = 0) -> None:
        """Começa (ou reinicia) a condução de um tema."""
        self._limpar_destaque()
        self._tema = tema
        self._passos = tuple(tema.passos) if tema else ()
        self._alvos = dict(alvos)
        self._indice = max(0, min(indice, max(0, len(self._passos) - 1)))
        if not self._passos:
            self.setVisible(False)
            return
        self.setVisible(True)
        self._mostrar()

    def parar(self) -> None:
        self._limpar_destaque()
        self._passos = ()
        self._tema = None
        self.setVisible(False)

    def proximo(self) -> None:
        if not self._passos:
            return
        if self._indice >= len(self._passos) - 1:
            self._concluir()
            return
        self._indice += 1
        self._mostrar()

    def anterior(self) -> None:
        if not self._passos:
            return
        self._indice = max(0, self._indice - 1)
        self._mostrar()

    # -- interno ------------------------------------------------------------
    def _mostrar(self) -> None:
        passo = self._passos[self._indice]
        if self._tema is not None:
            self.rotulo_titulo.setText(f"{self._tema.titulo} · {passo.titulo}")
        else:  # pragma: no cover - sempre há tema quando há passos
            self.rotulo_titulo.setText(passo.titulo)
        self.rotulo_texto.setText(passo.texto)
        self.rotulo_contador.setText(f"passo {self._indice + 1} de {len(self._passos)}")
        ultimo = self._indice == len(self._passos) - 1
        self.botao_proximo.setVisible(not ultimo)
        self.botao_concluir.setVisible(ultimo)
        self.botao_anterior.setEnabled(self._indice > 0)
        self._destacar(passo.alvo)

    def _destacar(self, alvo: str | None) -> None:
        self._limpar_destaque()
        if not alvo:
            return
        widget = self._alvos.get(alvo)
        if widget is None or not widget.isVisibleTo(self.window()):
            return
        self._destacado = widget
        _aplicar_destaque(widget, ativo=True)
        self._rolar_ate(widget)

    def _rolar_ate(self, widget: QWidget) -> None:
        """Traz o campo do passo para dentro da área visível (rolando o mínimo).

        O conteúdo da janela vive dentro de `QScrollArea`s; sem isto, em tela pequena
        o mentor explicava um campo que estava abaixo da dobra. Ancestrais são
        percorridos de dentro para fora porque pode haver rolagem aninhada.
        """
        pai = widget.parentWidget()
        while pai is not None:
            if isinstance(pai, QScrollArea):
                visor = pai.widget()
                if visor is not None and visor.isAncestorOf(widget):
                    pai.ensureWidgetVisible(widget, 24, 24)
            pai = pai.parentWidget()

    def _limpar_destaque(self) -> None:
        if self._destacado is not None:
            _aplicar_destaque(self._destacado, ativo=False)
            self._destacado = None

    def _concluir(self) -> None:
        self._limpar_destaque()
        self._passos = ()
        self.setVisible(False)
        self.concluido.emit()

    def _parar(self) -> None:
        self._concluir()
        self.encerrado.emit()


def alvos_da_tela(tela: QWidget | None, passos: tuple[Passo, ...]) -> dict[str, QWidget]:
    """Resolve nome → widget para os passos que pedem destaque.

    Só devolve o que existe: passo com alvo inexistente vira texto puro em vez de
    erro. É o que permite renomear um campo sem derrubar o mentor (o teste acusa a
    divergência antes, no repositório).
    """
    if tela is None:
        return {}
    encontrados: dict[str, QWidget] = {}
    for passo in passos:
        if not passo.alvo or passo.alvo in encontrados:
            continue
        alvo = getattr(tela, passo.alvo, None)
        if isinstance(alvo, QWidget):
            encontrados[passo.alvo] = alvo
    return encontrados


__all__ = ["PROPRIEDADE_DESTAQUE", "PainelMentor", "alvos_da_tela"]
