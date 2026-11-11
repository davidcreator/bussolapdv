"""Diálogo de login e de autorização de gerente."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from ..aplicacao.autenticacao import ServicoAutenticacao
from ..aplicacao.contexto import Contexto
from ..dominio.erros import ErroBussola
from ..dominio.usuario import Acao, Usuario


class DialogoLogin(QDialog):
    """Login por usuário e senha. Nunca exibe se o login existe."""

    def __init__(self, contexto: Contexto, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = contexto
        self.usuario: Usuario | None = None
        self.setWindowTitle("Bússola Sistema PDV Open Source — Entrar")
        self.setMinimumWidth(380)

        titulo = QLabel("Bússola Sistema PDV Open Source")
        titulo.setObjectName("tituloApp")
        aviso = QLabel("Acesso local. Senhas são verificadas com Argon2id; nenhuma senha é gravada em texto.")
        aviso.setWordWrap(True)
        aviso.setObjectName("textoAjuda")

        self.campo_login = QLineEdit()
        self.campo_login.setPlaceholderText("usuário")
        self.campo_senha = QLineEdit()
        self.campo_senha.setEchoMode(QLineEdit.EchoMode.Password)
        self.campo_senha.setPlaceholderText("senha")

        formulario = QFormLayout()
        formulario.addRow("Usuário", self.campo_login)
        formulario.addRow("Senha", self.campo_senha)

        self.mensagem = QLabel("")
        self.mensagem.setObjectName("mensagemErro")
        self.mensagem.setWordWrap(True)

        botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        botoes.button(QDialogButtonBox.StandardButton.Ok).setText("Entrar")
        botoes.button(QDialogButtonBox.StandardButton.Cancel).setText("Sair")
        botoes.accepted.connect(self._entrar)
        botoes.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(titulo)
        layout.addWidget(aviso)
        layout.addSpacing(8)
        layout.addLayout(formulario)
        layout.addWidget(self.mensagem)
        layout.addWidget(botoes)

        self.campo_senha.returnPressed.connect(self._entrar)
        self.campo_login.setFocus()

    def _entrar(self) -> None:
        servico = ServicoAutenticacao(self.ctx)
        try:
            resultado = servico.entrar(self.campo_login.text().strip(), self.campo_senha.text())
        except ErroBussola as exc:
            self.mensagem.setText(str(exc))
            self.campo_senha.clear()
            self.campo_senha.setFocus()
            return
        self.usuario = resultado.usuario
        self.accept()


class DialogoAutorizacao(QDialog):
    """Autenticação do autorizador (gerente/admin) para ação excepcional."""

    def __init__(self, contexto: Contexto, acao: Acao, motivo: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = contexto
        self.acao = acao
        self.autorizador: Usuario | None = None
        self.setWindowTitle("Autorização necessária")
        self.setMinimumWidth(400)

        explicacao = QLabel(
            f"A ação <b>{acao.value}</b> exige autorização.<br>{motivo}<br><br>"
            "Informe as credenciais de um gerente ou administrador presente. "
            "A autorização é registrada na auditoria com o usuário autenticado."
        )
        explicacao.setWordWrap(True)

        self.campo_login = QLineEdit()
        self.campo_login.setPlaceholderText("autorizador")
        self.campo_senha = QLineEdit()
        self.campo_senha.setEchoMode(QLineEdit.EchoMode.Password)
        self.campo_senha.setPlaceholderText("senha do autorizador")

        formulario = QFormLayout()
        formulario.addRow("Usuário", self.campo_login)
        formulario.addRow("Senha", self.campo_senha)

        self.mensagem = QLabel("")
        self.mensagem.setObjectName("mensagemErro")
        self.mensagem.setWordWrap(True)

        botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        botoes.button(QDialogButtonBox.StandardButton.Ok).setText("Autorizar")
        botoes.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        botoes.accepted.connect(self._autorizar)
        botoes.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(explicacao)
        layout.addLayout(formulario)
        layout.addWidget(self.mensagem)
        layout.addWidget(botoes)
        self.campo_senha.returnPressed.connect(self._autorizar)
        self.campo_login.setFocus()

    def _autorizar(self) -> None:
        servico = ServicoAutenticacao(self.ctx)
        try:
            self.autorizador = servico.autorizar(
                self.campo_login.text().strip(), self.campo_senha.text(), self.acao
            )
        except ErroBussola as exc:
            self.mensagem.setText(str(exc))
            self.campo_senha.clear()
            self.campo_senha.setFocus()
            return
        self.accept()


class DialogoConfirmacao(QDialog):
    """Confirmação com campo de motivo obrigatório (cancelamento, ajuste)."""

    def __init__(
        self,
        titulo: str,
        pergunta: str,
        parent: QWidget | None = None,
        *,
        exige_motivo: bool = True,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.setMinimumWidth(420)
        self.campo_motivo = QLineEdit()
        self.campo_motivo.setPlaceholderText("motivo (obrigatório)")
        botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        botoes.button(QDialogButtonBox.StandardButton.Ok).setText("Confirmar")
        botoes.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        botoes.accepted.connect(self._confirmar)
        botoes.rejected.connect(self.reject)
        texto = QLabel(pergunta)
        texto.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addWidget(texto)
        if exige_motivo:
            layout.addWidget(self.campo_motivo)
        layout.addWidget(botoes)
        self._exige_motivo = exige_motivo

    def _confirmar(self) -> None:
        if self._exige_motivo and not self.campo_motivo.text().strip():
            self.campo_motivo.setPlaceholderText("informe o motivo para continuar")
            self.campo_motivo.setFocus()
            return
        self.accept()

    @property
    def motivo(self) -> str:
        return self.campo_motivo.text().strip()


__all__ = ["DialogoAutorizacao", "DialogoConfirmacao", "DialogoLogin", "Qt"]
