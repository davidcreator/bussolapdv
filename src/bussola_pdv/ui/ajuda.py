"""Janela de Ajuda: o guia completo, com busca, e o liga/desliga do uso orientado.

Layout em duas colunas (índice + conteúdo), como qualquer manual decente: à esquerda
os temas, à direita o texto do tema escolhido. A busca filtra os dois ao mesmo tempo.

O rodapé é onde mora a resposta ao pedido "poder ativar de novo o uso guiado": um
botão que religa o mentor na hora, sem precisar reinstalar nem reiniciar o programa.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..aplicacao.ajuda import ServicoAjuda, Tema, tema_em_html
from ..aplicacao.contexto import Contexto
from ..dominio.usuario import Usuario
from .icones import icone
from .responsivo import ajustar_dialogo
from .tema import tinta_do_botao


class JanelaAjuda(QDialog):
    """Guia do PDV + controle do modo guiado."""

    #: Emitido quando o operador liga/desliga o uso orientado aqui dentro.
    guiado_alterado = Signal(bool)
    #: Emitido quando o operador pede "começar de novo" (a janela reinicia o mentor).
    reiniciar_pedido = Signal()

    def __init__(
        self,
        contexto: Contexto,
        usuario: Usuario,
        *,
        tema_inicial: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.ctx = contexto
        self.usuario = usuario
        self.servico = ServicoAjuda(contexto)
        self.setWindowTitle("Ajuda · Guia de uso do Bússola PDV")
        self.setModal(False)
        ajustar_dialogo(self, largura_preferida=880, altura_preferida=720)
        self._abrir_em_tamanho_confortavel()

        self.campo_busca = QLineEdit()
        self.campo_busca.setPlaceholderText("buscar no guia: campo, tela, atalho, mensagem de erro…")
        self.campo_busca.setClearButtonEnabled(True)
        self.campo_busca.textChanged.connect(self._filtrar)

        self.lista = QListWidget()
        self.lista.setObjectName("indiceAjuda")
        self.lista.setMinimumWidth(250)
        self.lista.setMaximumWidth(320)
        # Título comprido corta com "…" e mostra o resumo no tooltip: sem isto a
        # lista ganhava rolagem horizontal e o nome do tema sumia à direita.
        self.lista.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.lista.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.lista.currentItemChanged.connect(self._mostrar_item)

        self.rotulo_tema = QLabel()
        self.rotulo_tema.setObjectName("conteudoAjuda")
        self.rotulo_tema.setTextFormat(Qt.TextFormat.RichText)
        self.rotulo_tema.setWordWrap(True)
        self.rotulo_tema.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.rotulo_tema.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.LinksAccessibleByMouse
        )
        self.rolagem = QScrollArea()
        self.rolagem.setObjectName("rolagemAjuda")
        self.rolagem.setWidgetResizable(True)
        self.rolagem.setFrameShape(QScrollArea.Shape.NoFrame)
        self.rolagem.setWidget(self.rotulo_tema)

        colunas = QHBoxLayout()
        colunas.setContentsMargins(0, 0, 0, 0)
        colunas.setSpacing(12)
        colunas.addWidget(self.lista, 0)
        colunas.addWidget(self.rolagem, 1)

        # -- rodapé: modo guiado -------------------------------------------
        self.rotulo_guiado = QLabel()
        self.rotulo_guiado.setObjectName("textoAjuda")
        self.rotulo_guiado.setWordWrap(True)
        self.botao_guiado = QPushButton()
        self.botao_guiado.clicked.connect(self._alternar_guiado)
        self.botao_reiniciar = QPushButton("Começar do primeiro passo")
        self.botao_reiniciar.setObjectName("secundario")
        self.botao_reiniciar.clicked.connect(self._reiniciar)
        self.botao_salvar = QPushButton("Salvar o guia (.md)")
        self.botao_salvar.setObjectName("secundario")
        self.botao_salvar.setToolTip("Grava o guia inteiro em Markdown para imprimir ou compartilhar")
        self.botao_salvar.clicked.connect(self._salvar)
        self.botao_fechar = QPushButton("Fechar")
        self.botao_fechar.setObjectName("secundario")
        self.botao_fechar.clicked.connect(self.accept)

        # Rodapé em duas linhas: o estado do modo guiado ocupa a largura toda (numa
        # linha só ele virava uma coluna de duas palavras) e os botões ficam embaixo.
        linha_botoes = QHBoxLayout()
        linha_botoes.setContentsMargins(0, 0, 0, 0)
        linha_botoes.setSpacing(8)
        linha_botoes.addStretch(1)
        for botao in (
            self.botao_guiado,
            self.botao_reiniciar,
            self.botao_salvar,
            self.botao_fechar,
        ):
            linha_botoes.addWidget(botao, 0)

        titulo = QLabel("Guia de uso")
        titulo.setObjectName("tituloAjuda")
        ajuda_topico = QLabel(
            "Explicação de cada tela e de cada campo, feita a partir das telas deste programa. "
            f"Versão {__version__}."
        )
        ajuda_topico.setObjectName("textoAjuda")
        ajuda_topico.setWordWrap(True)

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(14, 12, 14, 12)
        raiz.setSpacing(9)
        raiz.addWidget(titulo)
        raiz.addWidget(ajuda_topico)
        raiz.addWidget(self.campo_busca)
        raiz.addLayout(colunas, 1)
        raiz.addWidget(self.rotulo_guiado)
        raiz.addLayout(linha_botoes)

        self._preencher(self.servico.temas())
        self._atualizar_guiado()
        self._selecionar(tema_inicial or "inicio")
        self.botao_guiado.setIcon(icone("ajuda", tinta_do_botao(self), 16))

    def _abrir_em_tamanho_confortavel(self) -> None:
        """880×700 quando a tela permite; menor (nunca menor que 520×420) quando não.

        `ajustar_dialogo` já limita o que é obrigatório; aqui o tamanho *inicial* é
        definido, porque guia com duas colunas precisa de largura para não espremer
        o índice nem o texto.
        """
        from PySide6.QtGui import QGuiApplication

        tela = QGuiApplication.primaryScreen()
        area = tela.availableGeometry() if tela is not None else None
        largura = min(880, (area.width() - 60) if area else 880)
        altura = min(700, (area.height() - 60) if area else 700)
        self.resize(max(520, largura), max(420, altura))

    # -- API ----------------------------------------------------------------
    def temas_visiveis(self) -> list[str]:
        return [
            str(self.lista.item(linha).data(Qt.ItemDataRole.UserRole))
            for linha in range(self.lista.count())
        ]

    def tema_atual(self) -> Tema | None:
        item = self.lista.currentItem()
        if item is None:
            return None
        return self.servico.tema(str(item.data(Qt.ItemDataRole.UserRole)))

    def abrir_tema(self, chave: str) -> None:
        self._selecionar(chave)

    # -- interno ------------------------------------------------------------
    def _preencher(self, itens: tuple[Tema, ...]) -> None:
        self.lista.blockSignals(True)
        self.lista.clear()
        for tema in itens:
            item = QListWidgetItem(tema.titulo)
            item.setData(Qt.ItemDataRole.UserRole, tema.chave)
            item.setToolTip(tema.resumo)
            item.setIcon(icone(tema.icone))
            self.lista.addItem(item)
        self.lista.blockSignals(False)

    def _filtrar(self, texto: str) -> None:
        atuais = self.tema_atual()
        self._preencher(self.servico.buscar(texto))
        if self.lista.count() == 0:
            self.rotulo_tema.setText(
                f"<p>Nada encontrado para <b>{texto}</b>. Tente outra palavra — "
                "a busca olha título, passos, campos, atalhos e mensagens de erro.</p>"
            )
            return
        chave = atuais.chave if atuais else "inicio"
        self._selecionar(chave, alternativa=0)

    def _selecionar(self, chave: str, *, alternativa: int | None = None) -> None:
        for linha in range(self.lista.count()):
            if self.lista.item(linha).data(Qt.ItemDataRole.UserRole) == chave:
                self.lista.setCurrentRow(linha)
                return
        if self.lista.count() and alternativa is not None:
            self.lista.setCurrentRow(alternativa)

    def _mostrar_item(
        self, atual: QListWidgetItem | None, _anterior: QListWidgetItem | None = None
    ) -> None:
        if atual is None:
            return
        tema = self.servico.tema(str(atual.data(Qt.ItemDataRole.UserRole)))
        if tema is None:  # pragma: no cover - item sem tema não deveria existir
            return
        self.rotulo_tema.setText(tema_em_html(tema))
        self.rolagem.verticalScrollBar().setValue(0)

    def _alternar_guiado(self) -> None:
        ativo = not self.servico.guiado_ativo()
        self.servico.definir_guiado(ativo)
        self._atualizar_guiado()
        self.guiado_alterado.emit(ativo)

    def _reiniciar(self) -> None:
        """Religa o modo guiado e pede para a janela recomeçar do passo 1."""
        self.servico.reativar()
        self._atualizar_guiado()
        self.guiado_alterado.emit(True)
        self.reiniciar_pedido.emit()

    def _atualizar_guiado(self) -> None:
        ativo = self.servico.guiado_ativo()
        if ativo:
            self.rotulo_guiado.setText(
                "<b>Uso orientado: ligado.</b> A faixa do mentor aparece em cada tela nova."
            )
            self.botao_guiado.setText("Desligar o uso orientado")
            self.botao_guiado.setObjectName("secundario")
        else:
            self.rotulo_guiado.setText(
                "<b>Uso orientado: desligado.</b> Nenhuma explicação aparece na tela."
            )
            self.botao_guiado.setText("Reativar o uso orientado")
            self.botao_guiado.setObjectName("")
        estilo = self.botao_guiado.style()
        if estilo is not None:
            estilo.unpolish(self.botao_guiado)
            estilo.polish(self.botao_guiado)
        self.botao_reiniciar.setEnabled(True)

    def _salvar(self) -> None:
        destino, _filtro = QFileDialog.getSaveFileName(
            self,
            "Salvar o guia",
            "guia-bussola-pdv.md",
            "Markdown (*.md);;Texto (*.txt)",
        )
        if not destino:
            return
        try:
            caminho = self.servico.salvar_markdown(destino)
        except OSError as exc:
            QMessageBox.warning(self, "Não foi possível salvar", str(exc))
            return
        QMessageBox.information(self, "Guia salvo", f"O guia foi gravado em:\n{caminho}")


__all__ = ["JanelaAjuda"]
