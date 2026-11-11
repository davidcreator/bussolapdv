"""Janela da área administrativa: navegação por seções filtrada por permissão.

O menu é montado a partir das permissões efetivas do usuário — não existe aba
"desabilitada" para quem não pode: a seção simplesmente não aparece. Se o perfil
não tem `ADMIN_ACESSAR`, a janela nem abre.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ...aplicacao.contexto import Contexto
from ...dominio.erros import AutorizacaoNegada
from ...dominio.marca import Marca
from ...dominio.usuario import Acao, Usuario
from ..tema import folha_estilo_da_marca
from .acessos import SecaoPermissoes, SecaoUsuarios
from .dependencias import SecaoDependencias
from .manutencao import SecaoManutencao
from .marca import SecaoMarca
from .parametros import SecaoParametros


@dataclass(frozen=True, slots=True)
class Secao:
    chave: str
    rotulo: str
    descricao: str
    acao: Acao
    fabrica: object  # Callable[[Contexto, Usuario], QWidget]


SECOES: tuple[Secao, ...] = (
    Secao(
        "dependencias",
        "Visão geral",
        "Diagnóstico real de dependências, banco e trilha de auditoria",
        Acao.ADMIN_ACESSAR,
        SecaoDependencias,
    ),
    Secao(
        "marca",
        "Marca e tema",
        "Nome da loja, contato, logo, cores e tipografia",
        Acao.ADMIN_ACESSAR,
        SecaoMarca,
    ),
    Secao(
        "usuarios",
        "Usuários",
        "Criar, ativar, desativar e redefinir senhas conforme a hierarquia",
        Acao.USUARIO_GERENCIAR,
        SecaoUsuarios,
    ),
    Secao(
        "permissoes",
        "Perfis e permissões",
        "Matriz do que cada perfil pode fazer — exclusivo do Admin Master",
        Acao.PERMISSAO_GERENCIAR,
        SecaoPermissoes,
    ),
    Secao(
        "parametros",
        "Parâmetros",
        "Descontos, crediário, caixa e segurança",
        Acao.PARAMETRO_ALTERAR,
        SecaoParametros,
    ),
    Secao(
        "manutencao",
        "Manutenção",
        "Cópias de segurança, verificação e restauração",
        Acao.BACKUP_EXECUTAR,
        SecaoManutencao,
    ),
)


class JanelaAdmin(QDialog):
    """Diálogo modal com as seções permitidas ao usuário."""

    marca_alterada = Signal()
    dados_alterados = Signal()

    def __init__(self, contexto: Contexto, usuario: Usuario, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        if not usuario.pode(Acao.ADMIN_ACESSAR):
            raise AutorizacaoNegada(
                "Seu perfil não tem acesso à área administrativa.",
                detalhe={"perfil": usuario.perfil.value},
            )
        self.ctx = contexto
        self.usuario = usuario
        self.setWindowTitle(f"Administração · {usuario.perfil.rotulo}")
        self.resize(1120, 760)
        self.setStyleSheet(folha_estilo_da_marca(contexto_marca(contexto)))

        self.secoes = [secao for secao in SECOES if usuario.pode(secao.acao)]

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)
        raiz.addWidget(self._cabecalho())

        corpo = QWidget()
        linha = QHBoxLayout(corpo)
        linha.setContentsMargins(0, 0, 0, 0)
        linha.setSpacing(0)

        self.menu = QListWidget()
        self.menu.setObjectName("navegacao")
        self.menu.setFixedWidth(210)
        for secao in self.secoes:
            QListWidgetItem(secao.rotulo, self.menu)
        self.menu.currentRowChanged.connect(self._trocar)
        linha.addWidget(self.menu)

        self.pilha = QStackedWidget()
        self.telas: dict[str, QWidget] = {}
        for secao in self.secoes:
            tela = secao.fabrica(contexto, usuario)  # type: ignore[operator]
            self.telas[secao.chave] = tela
            if isinstance(tela, SecaoMarca):
                tela.marca_salva.connect(self._marca_salva)
            if isinstance(tela, SecaoUsuarios):
                tela.usuarios_alterados.connect(self.dados_alterados.emit)
            if isinstance(tela, SecaoPermissoes):
                tela.permissoes_alteradas.connect(self.dados_alterados.emit)
            self.pilha.addWidget(tela)
        linha.addWidget(self.pilha, 1)
        raiz.addWidget(corpo, 1)

        rodape = QHBoxLayout()
        rodape.setContentsMargins(12, 6, 12, 6)
        self.rotulo_rodape = QLabel(
            f"{len(self.secoes)} seção(ões) liberada(s) para {usuario.perfil.rotulo} · "
            "toda alteração é auditada"
        )
        self.rotulo_rodape.setObjectName("textoAjuda")
        self.botao_fechar = QPushButton("Fechar")
        self.botao_fechar.setObjectName("secundario")
        self.botao_fechar.clicked.connect(self.accept)
        rodape.addWidget(self.rotulo_rodape, 1)
        rodape.addWidget(self.botao_fechar)
        raiz.addLayout(rodape)

        if self.secoes:
            self.menu.setCurrentRow(0)

    def _cabecalho(self) -> QWidget:
        marca = contexto_marca(self.ctx)
        faixa = QWidget()
        faixa.setObjectName("faixaSuperior")
        layout = QVBoxLayout(faixa)
        layout.setContentsMargins(16, 10, 16, 10)
        titulo = QLabel(f"Administração · {marca.nome_fantasia}")
        titulo.setObjectName("tituloApp")
        subtitulo = QLabel(
            f"Sessão de {self.usuario.nome} ({self.usuario.perfil.rotulo}) · "
            "as seções abaixo respeitam o que o Admin Master liberou"
        )
        subtitulo.setObjectName("subtituloApp")
        layout.addWidget(titulo)
        layout.addWidget(subtitulo)
        return faixa

    def _trocar(self, indice: int) -> None:
        if indice < 0 or indice >= len(self.secoes):
            return
        secao = self.secoes[indice]
        self.pilha.setCurrentWidget(self.telas[secao.chave])
        self.rotulo_rodape.setText(f"{secao.descricao} · toda alteração é auditada")
        tela = self.telas[secao.chave]
        if hasattr(tela, "atualizar"):
            tela.atualizar()

    def _marca_salva(self) -> None:
        self.setStyleSheet(folha_estilo_da_marca(contexto_marca(self.ctx)))
        self.marca_alterada.emit()

    def secoes_liberadas(self) -> list[str]:
        return [secao.chave for secao in self.secoes]


def contexto_marca(contexto: Contexto) -> Marca:
    """Leitura da marca com degradação segura (a janela nunca cai por tema corrompido)."""
    try:
        return Marca.de_parametros(contexto.parametros.por_prefixo("marca."))
    except Exception:  # pragma: no cover - banco em estado estranho
        return Marca.padrao()


__all__ = ["SECOES", "JanelaAdmin", "Qt", "Secao", "contexto_marca"]
