"""Janela da área administrativa: navegação por seções filtrada por permissão.

O menu é montado a partir das permissões efetivas do usuário — não existe aba
"desabilitada" para quem não pode: a seção simplesmente não aparece. Se o perfil
não tem `ADMIN_ACESSAR`, a janela nem abre.

A casca segue a linguagem do AdminLTE (sidebar escura, barra superior, cabeçalho
com trilha e rodapé), a mesma da janela principal, para que a área administrativa
não pareça outro programa.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...aplicacao.contexto import Contexto
from ...dominio.erros import AutorizacaoNegada
from ...dominio.marca import Marca
from ...dominio.usuario import Acao, Usuario
from ..responsivo import CascaResponsiva
from ..tema import folha_estilo_da_marca
from ..widgets import (
    BarraLateral,
    BarraSuperior,
    CabecalhoConteudo,
    EntradaNavegacao,
    PilhaDePaginas,
    Rodape,
)
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
    icone: str = "menu"


SECOES: tuple[Secao, ...] = (
    Secao(
        "dependencias",
        "Visão geral",
        "Diagnóstico real de dependências, banco e trilha de auditoria",
        Acao.ADMIN_ACESSAR,
        SecaoDependencias,
        "visao",
    ),
    Secao(
        "marca",
        "Marca e tema",
        "Nome da loja, contato, logo, cores e tipografia",
        Acao.ADMIN_ACESSAR,
        SecaoMarca,
        "marca",
    ),
    Secao(
        "usuarios",
        "Usuários",
        "Criar, ativar, desativar e redefinir senhas conforme a hierarquia",
        Acao.USUARIO_GERENCIAR,
        SecaoUsuarios,
        "usuarios",
    ),
    Secao(
        "permissoes",
        "Perfis e permissões",
        "Matriz do que cada perfil pode fazer — exclusivo do Admin Master",
        Acao.PERMISSAO_GERENCIAR,
        SecaoPermissoes,
        "permissoes",
    ),
    Secao(
        "parametros",
        "Parâmetros",
        "Descontos, crediário, caixa e segurança",
        Acao.PARAMETRO_ALTERAR,
        SecaoParametros,
        "parametros",
    ),
    Secao(
        "manutencao",
        "Manutenção",
        "Cópias de segurança, verificação e restauração",
        Acao.BACKUP_EXECUTAR,
        SecaoManutencao,
        "manutencao",
    ),
)


class JanelaAdmin(QDialog, CascaResponsiva):
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
        self.marca = contexto_marca(contexto)
        self.setWindowTitle(f"Administração · {usuario.perfil.rotulo}")
        self.resize(1180, 800)
        self.setMinimumSize(700, 460)
        self._iniciar_casca()
        self.setStyleSheet(folha_estilo_da_marca(self.marca))

        self.secoes = [secao for secao in SECOES if usuario.pode(secao.acao)]
        self.telas: dict[str, QWidget] = {}

        # -- sidebar com as seções liberadas ---------------------------------
        self.barra_lateral = BarraLateral(
            nome_loja=self.marca.nome_fantasia,
            usuario=usuario.nome,
            perfil=usuario.perfil.rotulo,
            paleta=self.marca.paleta,
        )
        self.barra_lateral.rotulo_versao_marca.setText("Administração")
        self.barra_lateral.definir_modulos(
            [
                EntradaNavegacao(chave=secao.chave, rotulo=secao.rotulo, icone=secao.icone)
                for secao in self.secoes
            ]
        )
        self.menu = self.barra_lateral.lista  # nome herdado
        self.barra_lateral.modulo_escolhido.connect(self._ir_para)

        # -- topo e conteúdo -------------------------------------------------
        self.barra_superior = BarraSuperior(
            titulo="Administração", usuario=usuario.nome, perfil=usuario.perfil.rotulo
        )
        self.barra_superior.recolher_pedido.connect(self.alternar_casca_recolhida)

        self.cabecalho = CabecalhoConteudo("Administração", "Área restrita · tudo é auditado")
        self.rotulo_rodape = self.cabecalho.descricao  # nome herdado
        # `PilhaDePaginas` (e não `QStackedWidget` puro): a altura e a largura mínimas
        # vêm da seção visível. Com o QStackedWidget, a seção mais larga (856 px) impunha
        # largura mínima a todas — a de Marca era cortada em 800×600.
        self.pilha = PilhaDePaginas()
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

        self.botao_fechar = QPushButton("Voltar ao PDV")
        self.botao_fechar.setObjectName("secundario")
        self.botao_fechar.clicked.connect(self.accept)

        self.rodape = Rodape(
            f"{len(self.secoes)} seção(ões) liberada(s) para {usuario.perfil.rotulo} · "
            "toda alteração é auditada",
            "",
        )
        self.rodape.direita.setText(f"sessão de {usuario.nome}")

        corpo = QWidget()
        corpo.setObjectName("conteudo")
        coluna = QVBoxLayout(corpo)
        coluna.setContentsMargins(0, 0, 0, 0)
        coluna.setSpacing(0)
        coluna.addWidget(self.barra_superior)
        coluna.addWidget(self.cabecalho)
        # Mesma razão da janela principal: em tela baixa a seção rola em vez de cortar.
        self.rolagem = QScrollArea()
        self.rolagem.setObjectName("rolagemConteudo")
        self.rolagem.setFrameShape(QScrollArea.Shape.NoFrame)
        self.rolagem.setWidgetResizable(True)
        self.rolagem.setWidget(self.pilha)
        coluna.addWidget(self.rolagem, 1)
        linha_rodape = QHBoxLayout()
        linha_rodape.setContentsMargins(0, 0, 12, 0)
        linha_rodape.addWidget(self.rodape, 1)
        linha_rodape.addWidget(self.botao_fechar, 0, Qt.AlignmentFlag.AlignVCenter)
        coluna.addLayout(linha_rodape)

        raiz = QHBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)
        raiz.addWidget(self.barra_lateral)
        raiz.addWidget(corpo, 1)

        self.ajustar_complementos(self.cabecalho, self.rodape)
        self.reorganizar_casca(self.width())
        if self.secoes:
            self.menu.setCurrentRow(0)

    def resizeEvent(self, evento: QResizeEvent) -> None:
        super().resizeEvent(evento)
        self.reorganizar_casca(evento.size().width())

    # -- navegação ----------------------------------------------------------
    def secoes_liberadas(self) -> list[str]:
        return [secao.chave for secao in self.secoes]

    def _indice_da_chave(self, chave: str) -> int:
        for indice, secao in enumerate(self.secoes):
            if secao.chave == chave:
                return indice
        return -1

    def _ir_para(self, chave: str) -> None:
        indice = self._indice_da_chave(chave)
        if indice < 0:
            return
        if self.menu.currentRow() != indice:
            self.menu.blockSignals(True)
            self.menu.setCurrentRow(indice)
            self.menu.blockSignals(False)
        self._trocar(indice)

    def _trocar(self, indice: int) -> None:
        if indice < 0 or indice >= len(self.secoes):
            return
        secao = self.secoes[indice]
        self.pilha.setCurrentWidget(self.telas[secao.chave])
        self.cabecalho.definir(
            titulo=secao.rotulo,
            descricao=secao.descricao,
            trilha=["Início", "Administração", secao.rotulo],
        )
        self.rotulo_rodape.setText(f"{secao.descricao} · toda alteração é auditada")
        self.barra_superior.definir_pagina(f"Administração · {secao.rotulo}")
        tela = self.telas[secao.chave]
        if hasattr(tela, "atualizar"):
            tela.atualizar()

    def _marca_salva(self) -> None:
        self.marca = contexto_marca(self.ctx)
        self.setStyleSheet(folha_estilo_da_marca(self.marca))
        self.barra_lateral.atualizar_identidade(
            self.marca.nome_fantasia, self.usuario.nome, self.usuario.perfil.rotulo
        )
        self.marca_alterada.emit()


def contexto_marca(contexto: Contexto) -> Marca:
    """Leitura da marca com degradação segura (a janela nunca cai por tema corrompido)."""
    try:
        return Marca.de_parametros(contexto.parametros.por_prefixo("marca."))
    except Exception:  # pragma: no cover - banco em estado estranho
        return Marca.padrao()
