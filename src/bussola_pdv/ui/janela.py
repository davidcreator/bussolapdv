"""Janela principal com navegação por módulos e acesso à área administrativa."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..aplicacao.contexto import Contexto
from ..dominio.usuario import Acao, Usuario
from .admin.janela import JanelaAdmin, contexto_marca
from .tela_caixa import TelaCaixa
from .tela_pdv import TelaPDV
from .telas_consulta import TelaAuditoria, TelaFechamento, TelaProdutos, TelaVendas
from .tema import folha_estilo_da_marca

MODULOS = [
    "PDV",
    "Caixa",
    "Produtos",
    "Vendas",
    "Fechamento",
    "Auditoria",
    # Módulos previstos na especificação, ainda não implementados nesta entrega.
    "Clientes",
    "Crediário",
    "Estoque",
    "Entradas",
    "Parâmetros",
]

MODULO_ADMIN = "Administração"


class JanelaPrincipal(QMainWindow):
    def __init__(self, contexto: Contexto, usuario: Usuario) -> None:
        super().__init__()
        self.ctx = contexto
        self.usuario = usuario
        self.marca = contexto_marca(contexto)
        self.modulos = list(MODULOS)
        if usuario.pode(Acao.ADMIN_ACESSAR):
            self.modulos.append(MODULO_ADMIN)

        self.setWindowTitle(f"{self.marca.nome_fantasia} · Bússola PDV")
        self.resize(1180, 760)

        self.tela_pdv = TelaPDV(contexto, usuario)
        self.tela_caixa = TelaCaixa(contexto, usuario)
        self.pilha = QStackedWidget()
        for tela in (
            self.tela_pdv,
            self.tela_caixa,
            TelaProdutos(contexto, usuario),
            TelaVendas(contexto, usuario),
            TelaFechamento(contexto, usuario),
            TelaAuditoria(contexto, usuario),
        ):
            self.pilha.addWidget(tela)

        self.tela_pdv.solicitar_caixa.connect(lambda: self._selecionar("Caixa"))
        self.tela_caixa.turno_alterado.connect(self.tela_pdv.atualizar)
        self.tela_pdv.venda_finalizada.connect(self.tela_caixa.atualizar)

        self.navegacao = QListWidget()
        self.navegacao.setObjectName("navegacao")
        self.navegacao.setFixedWidth(170)
        for modulo in self.modulos:
            QListWidgetItem(modulo, self.navegacao)
        self.navegacao.currentRowChanged.connect(self._trocar)

        corpo = QWidget()
        layout_corpo = QHBoxLayout(corpo)
        layout_corpo.setContentsMargins(0, 0, 0, 0)
        layout_corpo.addWidget(self.navegacao)
        layout_corpo.addWidget(self.pilha, 1)

        raiz = QWidget()
        layout = QVBoxLayout(raiz)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._cabecalho())
        layout.addWidget(self._faixa_secundaria())
        layout.addWidget(corpo, 1)
        self.setCentralWidget(raiz)

        self.statusBar().addWidget(
            QLabel(
                f"Usuário: {usuario.nome} ({usuario.perfil.rotulo})  ·  "
                f"Data de negócio: {contexto.relogio.data_negocio()}  ·  Base local SQLite"
            )
        )
        self.statusBar().addPermanentWidget(QLabel(f"v{__version__} · pré-alfa"))
        self.navegacao.setCurrentRow(0)

    # -- cabeçalho ----------------------------------------------------------
    def _cabecalho(self) -> QWidget:
        faixa = QFrame()
        faixa.setObjectName("faixaSuperior")
        layout = QVBoxLayout(faixa)
        layout.setContentsMargins(16, 10, 16, 10)
        self.rotulo_titulo = QLabel(self.marca.nome_fantasia)
        self.rotulo_titulo.setObjectName("tituloApp")
        self.rotulo_subtitulo = QLabel(
            f"Bússola Sistema PDV Open Source v{__version__} · dados locais · sem emissão fiscal · "
            "não homologado para operação real"
        )
        self.rotulo_subtitulo.setObjectName("subtituloApp")
        layout.addWidget(self.rotulo_titulo)
        layout.addWidget(self.rotulo_subtitulo)
        return faixa

    def _faixa_secundaria(self) -> QWidget:
        faixa = QFrame()
        faixa.setObjectName("faixaSecundaria")
        layout = QHBoxLayout(faixa)
        layout.setContentsMargins(16, 6, 16, 6)
        self.rotulo_modulo = QLabel("Frente de caixa")
        layout.addWidget(self.rotulo_modulo)
        layout.addStretch(1)
        self.rotulo_empresa = QLabel(
            f"{self.marca.nome_fantasia} · modo {self.ctx.parametros.obter('operacao.modo')}"
        )
        layout.addWidget(self.rotulo_empresa)
        return faixa

    # -- navegação ----------------------------------------------------------
    def _trocar(self, indice: int) -> None:
        if indice < 0 or indice >= len(self.modulos):
            return
        modulo = self.modulos[indice]
        if modulo == MODULO_ADMIN:
            self._abrir_admin()
            return
        descricoes = {
            "PDV": "Frente de caixa",
            "Caixa": "Turno e conferência de gaveta",
            "Produtos": "Cadastro e indicadores de estoque",
            "Vendas": "Histórico e cancelamento controlado",
            "Fechamento": "Conferência diária e snapshot",
            "Auditoria": "Trilha append-only com encadeamento de hash",
        }
        self.rotulo_modulo.setText(descricoes.get(modulo, modulo))
        if indice < self.pilha.count():
            self.pilha.setCurrentIndex(indice)
            tela = self.pilha.currentWidget()
            if tela is not None and hasattr(tela, "atualizar"):
                tela.atualizar()
        else:
            placeholder = QWidget()
            layout = QVBoxLayout(placeholder)
            aviso = QLabel(
                f"O módulo <b>{modulo}</b> consta na especificação, mas ainda <b>não foi "
                "implementado</b> nesta entrega.\n\n"
                "Nada aqui é simulado: telas não prontas ficam identificadas para não "
                "confundir operação com protótipo."
            )
            aviso.setWordWrap(True)
            aviso.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(aviso)
            self.pilha.addWidget(placeholder)
            self.pilha.setCurrentIndex(indice)

    def _abrir_admin(self) -> None:
        """Abre a área administrativa; se o usuário perdeu o direito, avisa e volta."""
        self._recarregar_usuario()  # o perfil pode ter mudado desde o login
        try:
            janela = JanelaAdmin(self.ctx, self.usuario, self)
        except Exception as exc:
            self.rotulo_modulo.setText(f"Administração indisponível: {exc}")
            self.navegacao.blockSignals(True)
            self.navegacao.setCurrentRow(0)
            self.navegacao.blockSignals(False)
            return
        janela.marca_alterada.connect(self._aplicar_marca)
        janela.dados_alterados.connect(self._recarregar_usuario)
        janela.exec()
        self.navegacao.blockSignals(True)
        self.navegacao.setCurrentRow(0)
        self.navegacao.blockSignals(False)

    def _aplicar_marca(self) -> None:
        self.marca = contexto_marca(self.ctx)
        self.setWindowTitle(f"{self.marca.nome_fantasia} · Bússola PDV")
        self.rotulo_titulo.setText(self.marca.nome_fantasia)
        self.rotulo_empresa.setText(
            f"{self.marca.nome_fantasia} · modo {self.ctx.parametros.obter('operacao.modo')}"
        )
        aplicacao = QApplication.instance()
        if isinstance(aplicacao, QApplication):
            aplicacao.setStyleSheet(folha_estilo_da_marca(self.marca))

    def _recarregar_usuario(self) -> None:
        """Recarrega o usuário da sessão (perfil/permissões podem ter mudado)."""
        from ..dominio.erros import ErroNaoEncontrado

        try:
            atualizado = self.ctx.usuarios.por_id(self.usuario.id)
        except ErroNaoEncontrado:
            return
        self.usuario = atualizado
        for tela in (
            self.tela_pdv,
            self.tela_caixa,
            *(self.pilha.widget(i) for i in range(self.pilha.count())),
        ):
            if tela is not None and getattr(tela, "usuario", None) is not None:
                tela.usuario = atualizado  # type: ignore[attr-defined]
        self.tela_pdv.atualizar()

    def _selecionar(self, modulo: str) -> None:
        self.navegacao.setCurrentRow(self.modulos.index(modulo))
