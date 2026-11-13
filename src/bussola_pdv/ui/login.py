"""Diálogos de login, autorização e confirmação.

Visual no padrão "login-box" do AdminLTE: cartão centrado com faixa da marca no
topo, formulário curto e aviso de segurança em texto discreto. As regras — Argon2id,
nunca revelar se o login existe, autorização nominal na auditoria — continuam na
camada de aplicação; aqui só se coleta credencial e se mostra o erro.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..aplicacao.autenticacao import ServicoAutenticacao
from ..aplicacao.contexto import Contexto
from ..aplicacao.marca import ServicoMarca
from ..dominio.erros import ErroBussola
from ..dominio.marca import Marca, tinta_sobre
from ..dominio.usuario import Acao, Usuario
from .icones import icone
from .identidade import logo_comercial
from .responsivo import ajustar_dialogo, envolver_em_rolagem
from .tema import tinta_do_botao
from .widgets import Rodape

#: Altura do logo na faixa do cartão quando há título ao lado (px lógicos).
ALTURA_LOGO_FAIXA = 34

#: Altura quando o logo é o **único** conteúdo da faixa: a assinatura comercial
#: traz o nome "Bússola PDV" e o slogan em corpo pequeno, que só é legível a
#: partir de ~44 px. A faixa cresce 14 px e o formulário continua cabendo em
#: 640×440 (medido por `make responsivo`).
ALTURA_LOGO_FAIXA_SOZINHO = 48


def marca_do_contexto(contexto: Contexto) -> Marca | None:
    """Marca da loja para o logo da faixa; `None` quando ainda não há base.

    A tela de primeiro uso roda **antes** de existir banco: ali não há o que ler e
    o logo oficial do Bússola é o certo. Leitura com degradação segura — logo é
    identidade, não pode impedir ninguém de fazer login.
    """
    try:
        return ServicoMarca(contexto).obter()
    except Exception:  # pragma: no cover - base em estado estranho
        return None


def _cartao_modal(subtitulo: str = "") -> tuple[QFrame, QVBoxLayout]:
    """Cartão branco com cabeçalho, usado pelos três diálogos."""
    cartao = QFrame()
    cartao.setObjectName("cartaoLogin")
    corpo = QVBoxLayout()
    corpo.setContentsMargins(20, 14, 20, 16)
    corpo.setSpacing(9)
    if subtitulo:
        ajuda = QLabel(subtitulo)
        ajuda.setObjectName("loginSubtitulo")
        ajuda.setWordWrap(True)
        corpo.addWidget(ajuda)
    return cartao, corpo


def _finalizar_cartao(
    cartao: QFrame, corpo: QVBoxLayout, faixa: QWidget, corpo_janela: QVBoxLayout
) -> None:
    interno = QVBoxLayout(cartao)
    interno.setContentsMargins(0, 0, 0, 0)
    interno.setSpacing(0)
    interno.addWidget(faixa)
    interno.addLayout(corpo)
    cartao.setMaximumWidth(430)
    # O cartão fica dentro de uma rolagem centralizada: em tela baixa (notebook
    # 1366×768 a 150% = 512 px lógicos) o formulário de primeiro uso passava da
    # tela e era cortado em cima e embaixo, sem barra para chegar ao resto.
    conteudo = QWidget()
    interno_rolagem = QVBoxLayout(conteudo)
    interno_rolagem.setContentsMargins(0, 0, 0, 0)
    interno_rolagem.addStretch(1)
    linha = QHBoxLayout()
    linha.addStretch(1)
    linha.addWidget(cartao, 0)
    linha.addStretch(1)
    interno_rolagem.addLayout(linha)
    interno_rolagem.addStretch(1)
    rolagem = envolver_em_rolagem(conteudo)
    # Nada de `rolagem.setStyleSheet(...)`: folha definida num widget vale também
    # para os filhos, e "background: transparent" apagava o fundo da faixa do
    # título e dos botões — o "Entrar" ficava branco sobre branco. O fundo do
    # diálogo vem da folha global por `objectName` (ver `tema.folha_estilo`).
    corpo_janela.addWidget(rolagem, 1)


def _faixa(titulo: str = "", *, marca: Marca | None = None) -> QWidget:
    """Faixa colorida do topo do cartão: logo comercial e, às vezes, título.

    `titulo` vazio quer dizer "o logo já diz tudo" — é o caso do login, em que a
    faixa mostra a assinatura comercial grande e centrada. Nos diálogos de ação
    (*Confirmar ação*, *Ação excepcional*) o título é a informação que importa e
    fica ao lado do logo, menor.

    O logo é tingido com a tinta legível sobre a primária (`tinta_sobre`, a mesma
    régua da ADR-024). Sem logo da loja, entra o do Bússola; com logo enviado em
    *Marca e tema*, é ele que aparece (ADR-028) — e aí ele **não** é tingido, sai
    como a loja enviou.
    """
    faixa = QFrame()
    faixa.setObjectName("loginMarca")
    linha = QHBoxLayout(faixa)
    # O recuo vem do `padding` de `#loginMarca` na folha de estilo: um lugar só.
    linha.setContentsMargins(0, 0, 0, 0)
    linha.setSpacing(12)

    tinta = tinta_sobre((marca or Marca()).paleta.primaria)
    altura = ALTURA_LOGO_FAIXA if titulo else ALTURA_LOGO_FAIXA_SOZINHO
    logotipo = QLabel()
    logotipo.setObjectName("loginMarcaLogo")
    desenhado = logo_comercial(marca, altura=altura, cor=tinta)
    logotipo.setPixmap(desenhado)
    logotipo.setFixedSize(
        max(1, int(desenhado.width() / desenhado.devicePixelRatio())),
        max(1, int(desenhado.height() / desenhado.devicePixelRatio())),
    )
    logotipo.setToolTip("")

    if not titulo:
        # Só o logo: centralizado, para a faixa não ficar pesada de um lado.
        linha.addStretch(1)
        linha.addWidget(logotipo, 0, Qt.AlignmentFlag.AlignVCenter)
        linha.addStretch(1)
        return faixa

    linha.addWidget(logotipo, 0, Qt.AlignmentFlag.AlignVCenter)

    rotulo = QLabel(titulo)
    rotulo.setObjectName("loginMarcaTitulo")
    rotulo.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    rotulo.setWordWrap(True)
    linha.addWidget(rotulo, 1)
    return faixa


class DialogoLogin(QDialog):
    """Login por usuário e senha. Nunca exibe se o login existe."""

    def __init__(self, contexto: Contexto, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = contexto
        self.usuario: Usuario | None = None
        self.setWindowTitle("Bússola Sistema PDV Open Source — Entrar")
        ajustar_dialogo(self, largura_preferida=460)

        cartao, corpo = _cartao_modal(
            "Acesso local. Senhas são verificadas com Argon2id; nenhuma senha é gravada "
            "em texto.",
        )

        self.campo_login = QLineEdit()
        self.campo_login.setPlaceholderText("usuário")
        self.campo_login.setClearButtonEnabled(True)
        self.campo_senha = QLineEdit()
        self.campo_senha.setEchoMode(QLineEdit.EchoMode.Password)
        self.campo_senha.setPlaceholderText("senha")

        formulario = QFormLayout()
        formulario.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        formulario.setSpacing(8)
        formulario.addRow("Usuário", self.campo_login)
        formulario.addRow("Senha", self.campo_senha)
        corpo.addLayout(formulario)

        self.mensagem = QLabel("")
        self.mensagem.setObjectName("mensagemErro")
        self.mensagem.setWordWrap(True)
        corpo.addWidget(self.mensagem)

        botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        botoes.button(QDialogButtonBox.StandardButton.Ok).setText("Entrar")
        botoes.button(QDialogButtonBox.StandardButton.Ok).setIcon(
            icone("saida", tinta_do_botao(self), 16)
        )
        botoes.button(QDialogButtonBox.StandardButton.Cancel).setText("Sair")
        botoes.button(QDialogButtonBox.StandardButton.Cancel).setObjectName("secundario")
        botoes.accepted.connect(self._entrar)
        botoes.rejected.connect(self.reject)
        corpo.addWidget(botoes)

        rodape = Rodape(
            "Bússola Sistema PDV Open Source · offline", f"v{__version__} · pré-alfa"
        )
        self.rodape = rodape

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        _finalizar_cartao(
            cartao, corpo, _faixa(marca=marca_do_contexto(contexto)), layout
        )
        layout.addWidget(rodape)

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
        ajustar_dialogo(self, largura_preferida=460)

        cartao, corpo = _cartao_modal()
        explicacao = QLabel(
            f"A ação <b>{acao.value}</b> exige autorização.<br>{motivo}<br><br>"
            "Informe as credenciais de um gerente ou administrador presente. "
            "A autorização é registrada na auditoria com o usuário autenticado."
        )
        explicacao.setWordWrap(True)
        corpo.addWidget(explicacao)

        self.campo_login = QLineEdit()
        self.campo_login.setPlaceholderText("autorizador")
        self.campo_senha = QLineEdit()
        self.campo_senha.setEchoMode(QLineEdit.EchoMode.Password)
        self.campo_senha.setPlaceholderText("senha do autorizador")
        formulario = QFormLayout()
        formulario.setSpacing(8)
        formulario.addRow("Usuário", self.campo_login)
        formulario.addRow("Senha", self.campo_senha)
        corpo.addLayout(formulario)

        self.mensagem = QLabel("")
        self.mensagem.setObjectName("mensagemErro")
        self.mensagem.setWordWrap(True)
        corpo.addWidget(self.mensagem)

        botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        botoes.button(QDialogButtonBox.StandardButton.Ok).setText("Autorizar")
        botoes.button(QDialogButtonBox.StandardButton.Ok).setObjectName("aviso")
        botoes.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        botoes.button(QDialogButtonBox.StandardButton.Cancel).setObjectName("secundario")
        botoes.accepted.connect(self._autorizar)
        botoes.rejected.connect(self.reject)
        corpo.addWidget(botoes)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        _finalizar_cartao(
            cartao, corpo, _faixa("Ação excepcional", marca=marca_do_contexto(self.ctx)), layout
        )
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
        marca: Marca | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(titulo)
        ajustar_dialogo(self, largura_preferida=460)

        cartao, corpo = _cartao_modal()
        texto = QLabel(pergunta)
        texto.setWordWrap(True)
        corpo.addWidget(texto)

        self.campo_motivo = QLineEdit()
        self.campo_motivo.setPlaceholderText("motivo (obrigatório)")
        corpo.addWidget(self.campo_motivo)

        botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        botoes.button(QDialogButtonBox.StandardButton.Ok).setText("Confirmar")
        botoes.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        botoes.button(QDialogButtonBox.StandardButton.Cancel).setObjectName("secundario")
        botoes.accepted.connect(self._confirmar)
        botoes.rejected.connect(self.reject)
        corpo.addWidget(botoes)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        _finalizar_cartao(cartao, corpo, _faixa("Confirmar ação", marca=marca), layout)
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
