"""Primeiro uso: cria a instalação (Admin Master + caixa + nome da loja) pela tela.

Quem instala pelo `.exe` não tem terminal: o programa precisa resolver sozinho o
que o `bussola init` faz na linha de comando. Este diálogo aparece só quando o
banco ainda não existe (ou existe sem nenhum usuário) e executa exatamente os
mesmos casos de uso — nada é criado "por fora" da camada de aplicação.
"""

from __future__ import annotations

from pathlib import Path

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
from ..aplicacao.marca import ServicoMarca
from ..dominio.erros import ErroBussola
from ..dominio.marca import Marca
from ..dominio.usuario import Perfil, Usuario
from .icones import icone
from .login import _cartao_modal, _faixa, _finalizar_cartao


def precisa_de_configuracao(caminho: Path) -> bool:
    """Verdadeiro quando ainda não há instalação utilizável no caminho informado."""
    if not caminho.exists():
        return True
    try:
        contexto = Contexto.abrir(caminho)
    except Exception:  # base corrompida: o primeiro uso tenta recomeçar
        return True
    try:
        return not contexto.usuarios.listar()
    except ErroBussola:  # pragma: no cover - esquema antigo sem tabela de usuários
        return True
    finally:
        contexto.fechar()


class DialogoPrimeiroUso(QDialog):
    """Coleta o que o `init` pede no terminal: loja, master e senha."""

    def __init__(self, banco: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.banco = banco
        self.usuario: Usuario | None = None
        self.setWindowTitle("Bússola PDV — primeiro uso")
        self.setMinimumWidth(520)

        cartao, corpo = _cartao_modal(
            "Esta é a primeira execução: vamos criar a instalação local. O usuário criado "
            "aqui é o <b>Admin Master</b>, proprietário da instalação — ele define o que cada "
            "perfil pode fazer."
        )

        self.campo_loja = QLineEdit("Minha Loja")
        self.campo_loja.setMaxLength(60)
        self.campo_login = QLineEdit("master")
        self.campo_login.setPlaceholderText("usuário do Admin Master")
        self.campo_nome = QLineEdit()
        self.campo_nome.setPlaceholderText("nome completo do responsável")
        self.campo_senha = QLineEdit()
        self.campo_senha.setEchoMode(QLineEdit.EchoMode.Password)
        self.campo_senha.setPlaceholderText("mínimo 8 caracteres, com letras e números")
        self.campo_senha2 = QLineEdit()
        self.campo_senha2.setEchoMode(QLineEdit.EchoMode.Password)
        self.campo_senha2.setPlaceholderText("repita a senha")

        formulario = QFormLayout()
        formulario.setSpacing(8)
        formulario.addRow("Nome da loja", self.campo_loja)
        formulario.addRow("Usuário", self.campo_login)
        formulario.addRow("Nome do responsável", self.campo_nome)
        formulario.addRow("Senha", self.campo_senha)
        formulario.addRow("Confirmar senha", self.campo_senha2)
        corpo.addLayout(formulario)

        caminho = QLabel(f"Base local: {banco}")
        caminho.setObjectName("textoAjuda")
        caminho.setWordWrap(True)
        corpo.addWidget(caminho)

        self.mensagem = QLabel("")
        self.mensagem.setObjectName("mensagemErro")
        self.mensagem.setWordWrap(True)
        corpo.addWidget(self.mensagem)

        botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.botao_criar = botoes.button(QDialogButtonBox.StandardButton.Ok)
        self.botao_criar.setText("Criar instalação")
        self.botao_criar.setIcon(icone("saida", "#FFFFFF", 16))
        botoes.button(QDialogButtonBox.StandardButton.Cancel).setText("Sair")
        botoes.button(QDialogButtonBox.StandardButton.Cancel).setObjectName("secundario")
        botoes.accepted.connect(self._criar)
        botoes.rejected.connect(self.reject)
        corpo.addWidget(botoes)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        _finalizar_cartao(cartao, corpo, _faixa("Bússola PDV · instalação"), layout)

        self.campo_senha2.returnPressed.connect(self._criar)
        self.campo_nome.setFocus()

    # -- criação -------------------------------------------------------------
    def _validar(self) -> str:
        if not self.campo_loja.text().strip():
            return "Informe o nome da loja."
        if not self.campo_login.text().strip():
            return "Informe o usuário do Admin Master."
        if not self.campo_nome.text().strip():
            return "Informe o nome do responsável."
        if self.campo_senha.text() != self.campo_senha2.text():
            return "As senhas não conferem."
        return ""

    def _criar(self) -> None:
        problema = self._validar()
        if problema:
            self.mensagem.setText(problema)
            return
        self.banco.parent.mkdir(parents=True, exist_ok=True)
        contexto = Contexto.abrir(self.banco)
        try:
            master = ServicoAutenticacao(contexto).criar_usuario(
                login=self.campo_login.text().strip(),
                nome=self.campo_nome.text().strip(),
                senha=self.campo_senha.text(),
                perfil=Perfil.ADMIN_MASTER,
                criar_admin_inicial=True,
            )
            contexto.caixas.garantir_caixa("Caixa 1", criado_em=contexto.agora().isoformat())
            ServicoMarca(contexto).salvar(
                master, Marca(nome_fantasia=self.campo_loja.text().strip())
            )
            self.usuario = contexto.usuarios.por_id(master.id)
        except ErroBussola as exc:
            self.mensagem.setText(str(exc))
            return
        finally:
            contexto.fechar()
        self.accept()


__all__ = ["DialogoPrimeiroUso", "precisa_de_configuracao"]
