"""Janela principal: sidebar (AdminLTE), barra superior, conteúdo e rodapé.

A casca é inspirada no AdminLTE: navegação à esquerda, topbar com botão de recolher,
cabeçalho de página com trilha, área de conteúdo rolável e rodapé com versão. Toda
cor vem da paleta da loja; toda a lógica continua nas telas e na camada de aplicação.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QResizeEvent, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..aplicacao.ajuda import TEMA_DO_MODULO, ServicoAjuda
from ..aplicacao.contexto import Contexto
from ..dominio.usuario import Acao, Usuario
from .admin.janela import JanelaAdmin, contexto_marca
from .ajuda import JanelaAjuda
from .mentor import PainelMentor, alvos_da_tela
from .responsivo import CascaResponsiva, abrir_no_tamanho_da_tela
from .tela_caixa import TelaCaixa
from .tela_pdv import TelaPDV
from .telas_clientes import TelaClientes
from .telas_consulta import TelaAuditoria, TelaFechamento, TelaProdutos, TelaVendas
from .telas_crediario import TelaCrediario
from .telas_estoque import TelaEstoque
from .tema import folha_estilo_da_marca
from .widgets import (
    BarraLateral,
    BarraSuperior,
    CabecalhoConteudo,
    EntradaNavegacao,
    PilhaDePaginas,
    Rodape,
)

MODULOS = [
    "PDV",
    "Caixa",
    "Produtos",
    "Vendas",
    "Fechamento",
    "Auditoria",
    "Clientes",
    "Crediário",
    "Estoque",
    # Módulos previstos na especificação, ainda não implementados nesta entrega.
    "Entradas",
    "Parâmetros",
]

MODULO_ADMIN = "Administração"
#: Entrada de menu que **não** é página: abre a janela de Ajuda (F1).
MODULO_AJUDA = "Ajuda"

#: Ícone e descrição de cada módulo (a descrição aparece no cabeçalho da página).
DETALHES_MODULO: dict[str, tuple[str, str]] = {
    "PDV": ("pdv", "Frente de caixa · lance itens, divida o pagamento e finalize"),
    "Caixa": ("caixa", "Turno, sangria, suprimento e conferência de gaveta"),
    "Produtos": ("produtos", "Cadastro e indicadores de estoque"),
    "Vendas": ("vendas", "Histórico do período e cancelamento controlado"),
    "Fechamento": ("fechamento", "Conferência diária e snapshot versionado"),
    "Auditoria": ("auditoria", "Trilha append-only com encadeamento de hash"),
    "Clientes": ("clientes", "Cadastro de clientes"),
    "Crediário": ("crediario", "Títulos, parcelas e recebimentos"),
    "Estoque": ("estoque", "Movimentos e saldos"),
    "Entradas": ("entradas", "Entradas de fornecedor"),
    "Parâmetros": ("parametros", "Configuração da operação"),
    MODULO_ADMIN: ("administracao", "Dependências, marca, usuários, permissões e manutenção"),
    MODULO_AJUDA: ("ajuda", "Guia completo de uso, campo por campo, e o modo guiado"),
}


class JanelaPrincipal(QMainWindow, CascaResponsiva):
    """Janela de operação. A casca se reorganiza pela largura (ver `responsivo`)."""

    def __init__(self, contexto: Contexto, usuario: Usuario) -> None:
        super().__init__()
        self.ctx = contexto
        self.usuario = usuario
        self.marca = contexto_marca(contexto)
        self.modulos = list(MODULOS)
        if usuario.pode(Acao.ADMIN_ACESSAR):
            self.modulos.append(MODULO_ADMIN)
        # Ajuda fecha o menu e nunca vira página: `_selecionar` abre a janela do guia.
        self.modulos.append(MODULO_AJUDA)
        self.ajuda = ServicoAjuda(contexto)
        self._janela_ajuda: JanelaAjuda | None = None

        self.setWindowTitle(f"{self.marca.nome_fantasia} · Bússola PDV")
        # Abaixo disso a operação deixa de ser confortável: a janela não encolhe mais
        # (640×440 cabe em 1366×768 com escala de 150%, cujo espaço lógico é 911×512).
        self.setMinimumSize(640, 440)
        self.tamanho_inicial = abrir_no_tamanho_da_tela(self, 1280, 820)

        self.tela_pdv = TelaPDV(contexto, usuario)
        self.tela_caixa = TelaCaixa(contexto, usuario)
        self.pilha = PilhaDePaginas()
        for tela in (
            self.tela_pdv,
            self.tela_caixa,
            TelaProdutos(contexto, usuario),
            TelaVendas(contexto, usuario),
            TelaFechamento(contexto, usuario),
            TelaAuditoria(contexto, usuario),
            TelaClientes(contexto, usuario),
            TelaCrediario(contexto, usuario),
            TelaEstoque(contexto, usuario),
        ):
            self.pilha.addWidget(tela)
        # Módulos ainda não implementados ganham a página vazia já no índice certo.
        # Antes ela era criada sob demanda e o `setCurrentIndex` apontava para fora
        # do `QStackedWidget`: o clique parecia não fazer nada e a página anterior
        # continuava na tela (o placeholder era inalcançável).
        for modulo in self.modulos[self.pilha.count() :]:
            if modulo == MODULO_AJUDA:
                continue
            self.pilha.addWidget(self._placeholder(modulo))

        self.tela_pdv.solicitar_caixa.connect(lambda: self._selecionar("Caixa"))
        self.tela_caixa.turno_alterado.connect(self.tela_pdv.atualizar)
        self.tela_pdv.venda_finalizada.connect(self.tela_caixa.atualizar)

        self.setCentralWidget(self._montar_casca())
        # F1 abre o guia de qualquer lugar da janela (atalho de aplicação inteira).
        self.atalho_ajuda = QShortcut(QKeySequence("F1"), self)
        self.atalho_ajuda.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.atalho_ajuda.activated.connect(lambda: self._abrir_ajuda())
        self.ajustar_complementos(self.cabecalho, self.rodape)
        self.reorganizar_casca(self.width())
        self.navegacao.setCurrentRow(0)
        self._selecionar(self.modulos[0])  # o sinal não dispara se a linha já era 0

    # -- casca --------------------------------------------------------------
    def _montar_casca(self) -> QWidget:
        self.barra_lateral = BarraLateral(
            nome_loja=self.marca.nome_fantasia,
            usuario=self.usuario.nome,
            perfil=self.usuario.perfil.rotulo,
            paleta=self.marca.paleta,
        )
        self.barra_lateral.definir_modulos(
            [
                EntradaNavegacao(
                    chave=modulo,
                    rotulo=modulo,
                    icone=DETALHES_MODULO.get(modulo, ("menu", ""))[0],
                )
                for modulo in self.modulos
            ]
        )
        self.navegacao = self.barra_lateral.lista  # nome herdado: testes e telas usam
        self.barra_lateral.modulo_escolhido.connect(self._selecionar)

        self.barra_superior = BarraSuperior(
            titulo=self.marca.nome_fantasia,
            usuario=self.usuario.nome,
            perfil=self.usuario.perfil.rotulo,
        )
        self.barra_superior.recolher_pedido.connect(self._alternar_menu)
        self._iniciar_casca(self._definir_margens_do_conteudo)

        self.cabecalho = CabecalhoConteudo()
        self.rotulo_modulo = self.cabecalho.descricao  # nome herdado
        self.rotulo_titulo = self.barra_lateral.rotulo_marca  # nome herdado: marca
        self.rotulo_empresa = self.barra_superior.rotulo_pagina

        # Rolagem vertical própria: em tela baixa (600 px) os formulários do PDV não
        # cabem inteiros e, sem isto, os grupos se sobrepunham em vez de rolar. A
        # pilha reporta a altura da página visível (`PilhaDePaginas`), então páginas
        # que cabem continuam sem barra nenhuma.
        self.moldura = QWidget()
        self.moldura.setObjectName("conteudo")
        layout_moldura = QVBoxLayout(self.moldura)
        layout_moldura.setContentsMargins(18, 4, 18, 14)
        self.rolagem = QScrollArea()
        self.rolagem.setObjectName("rolagemConteudo")
        self.rolagem.setFrameShape(QScrollArea.Shape.NoFrame)
        self.rolagem.setWidgetResizable(True)
        self.rolagem.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.rolagem.setWidget(self.pilha)
        layout_moldura.addWidget(self.rolagem)

        self.rodape = Rodape(
            f"{self.marca.nome_fantasia} · dados locais, sem emissão fiscal",
            f"Bússola PDV v{__version__} · pré-alfa",
        )
        self.barra_lateral.rodape.setText("toda alteração é auditada")

        conteudo = QWidget()
        conteudo.setObjectName("conteudo")
        coluna = QVBoxLayout(conteudo)
        coluna.setContentsMargins(0, 0, 0, 0)
        coluna.setSpacing(0)
        coluna.addWidget(self.barra_superior)
        coluna.addWidget(self.cabecalho)
        coluna.addWidget(self.moldura, 1)
        # Mentor entre o conteúdo e o rodapé: faixa própria, sem cobrir a tela.
        self.mentor = PainelMentor()
        self.mentor.guia_pedido.connect(self._abrir_ajuda)
        self.mentor.encerrado.connect(self._desligar_guiado)
        self.mentor.concluido.connect(self._registrar_conclusao)
        coluna.addWidget(self.mentor)
        coluna.addWidget(self.rodape)

        raiz = QWidget()
        linha = QHBoxLayout(raiz)
        linha.setContentsMargins(0, 0, 0, 0)
        linha.setSpacing(0)
        linha.addWidget(self.barra_lateral)
        linha.addWidget(conteudo, 1)
        return raiz

    def _definir_margens_do_conteudo(self, margem: int) -> None:
        """Em tela pequena a margem de 18 px é luxo: 10 px devolve largura útil."""
        layout = self.moldura.layout()
        if layout is not None:
            layout.setContentsMargins(margem, 4, margem, max(8, margem - 4))

    def _alternar_menu(self) -> None:
        self.alternar_casca_recolhida()

    # -- responsividade -----------------------------------------------------
    def resizeEvent(self, evento: QResizeEvent) -> None:
        super().resizeEvent(evento)
        self.reorganizar_casca(evento.size().width())

    # -- navegação ----------------------------------------------------------
    def _trocar(self, indice: int) -> None:
        """Compatibilidade com o código antigo: repassa ao manipulador por chave."""
        chave = self.barra_lateral.chave_do_indice(indice)
        if chave is not None:
            self._selecionar(chave)

    def _selecionar(self, modulo: str) -> None:
        if modulo not in self.modulos:
            return
        indice = self.modulos.index(modulo)
        if self.barra_lateral.lista.currentRow() != indice:
            self.barra_lateral.lista.blockSignals(True)
            self.barra_lateral.lista.setCurrentRow(indice)
            self.barra_lateral.lista.blockSignals(False)

        if modulo == MODULO_ADMIN:
            self._abrir_admin()
            self._voltar_ao_pdv()
            return

        if modulo == MODULO_AJUDA:
            # Não é página: devolve o menu à página que estava aberta e abre o guia.
            anterior = max(0, self.pilha.currentIndex())
            self.barra_lateral.lista.blockSignals(True)
            self.barra_lateral.lista.setCurrentRow(anterior)
            self.barra_lateral.lista.blockSignals(False)
            self._abrir_ajuda()
            return

        _icone, descricao = DETALHES_MODULO.get(modulo, ("menu", modulo))
        self.cabecalho.definir(
            titulo=modulo,
            descricao=descricao,
            trilha=["Início", modulo],
        )
        self.barra_superior.definir_pagina(f"{self.marca.nome_fantasia} · {modulo}")
        self.pilha.setCurrentIndex(indice)
        tela = self.pilha.currentWidget()
        if tela is not None and hasattr(tela, "atualizar"):
            tela.atualizar()
        self._atualizar_mentor(inicio=True)  # trocou de tela: tour recomeça no passo 1

    def _placeholder(self, modulo: str) -> QWidget:
        from .widgets import Cartao

        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(18, 4, 18, 18)
        cartao = Cartao(f"{modulo} · ainda não implementado", "Sem simulação, sem meia-boca")
        aviso = QLabel(
            f"O módulo <b>{modulo}</b> consta na especificação, mas ainda <b>não foi "
            "implementado</b> nesta entrega.<br><br>"
            "Nada aqui é simulado: telas não prontas ficam identificadas para não confundir "
            "operação com protótipo."
        )
        aviso.setWordWrap(True)
        aviso.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        cartao.adicionar(aviso)
        layout.addWidget(cartao)
        layout.addStretch(1)
        return pagina

    def _voltar_ao_pdv(self) -> None:
        self.barra_lateral.lista.blockSignals(True)
        self.barra_lateral.lista.setCurrentRow(0)
        self.barra_lateral.lista.blockSignals(False)

    def _abrir_admin(self) -> None:
        """Abre a área administrativa; se o usuário perdeu o direito, avisa e volta."""
        self._recarregar_usuario()  # o perfil pode ter mudado desde o login
        try:
            janela = JanelaAdmin(self.ctx, self.usuario, self)
        except Exception as exc:
            self.cabecalho.definir(
                titulo="Administração", descricao=f"Administração indisponível: {exc}"
            )
            self.rotulo_modulo.setText(f"Administração indisponível: {exc}")
            return
        janela.marca_alterada.connect(self._aplicar_marca)
        janela.dados_alterados.connect(self._recarregar_usuario)
        janela.exec()

    # -- ajuda e modo guiado ------------------------------------------------
    def _abrir_ajuda(self, tema: str | None = None) -> None:
        """Abre (ou traz para a frente) o guia. F1, menu Ajuda e mentor caem aqui."""
        if self._janela_ajuda is None:
            self._janela_ajuda = JanelaAjuda(self.ctx, self.usuario, parent=self)
            self._janela_ajuda.guiado_alterado.connect(self._guiado_alterado)
            self._janela_ajuda.reiniciar_pedido.connect(self._reiniciar_mentor)
        janela = self._janela_ajuda
        janela.show()
        janela.raise_()
        janela.activateWindow()
        if tema:
            janela.abrir_tema(tema)
        else:
            atual = self.pilha.currentWidget()
            chave = TEMA_DO_MODULO.get(self.cabecalho.titulo.text()) if atual else None
            if chave:
                janela.abrir_tema(chave)

    def _guiado_alterado(self, ativo: bool) -> None:
        if ativo:
            self._reiniciar_mentor()
        else:
            self.mentor.parar()

    def _desligar_guiado(self) -> None:
        """O operador clicou em 'Parar' no mentor: a escolha vale para as próximas telas."""
        self.ajuda.definir_guiado(False)
        self.mentor.parar()

    def _registrar_conclusao(self) -> None:
        """Tour concluído: marca a versão vista para não repetir a cada abertura."""
        self.ajuda.definir_guiado(True)

    def _reiniciar_mentor(self) -> None:
        self._atualizar_mentor(inicio=True)

    def _atualizar_mentor(self, *, inicio: bool = False) -> None:
        """Liga/desliga e reinicia o mentor conforme o módulo aberto.

        Só há mentor onde há o que explicar (PDV, Caixa, consultas, Administração) e
        só quando o uso orientado está ligado. Ao trocar de tela o tour recomeça do
        primeiro passo daquele módulo, porque a explicação é por tela.
        """
        if not self.ajuda.guiado_ativo():
            self.mentor.parar()
            return
        if getattr(self, "mentor", None) is None:  # pragma: no cover - casca incompleta
            return
        titulo = self.cabecalho.titulo.text()
        tema = self.ajuda.tema_do_modulo(titulo)
        if tema is None or not tema.passos:
            self.mentor.parar()
            return
        tela = self.pilha.currentWidget()
        alvos = alvos_da_tela(tela, tema.passos)
        mesmo_tema = self.mentor.tema is not None and self.mentor.tema.chave == tema.chave
        indice = self.mentor.indice if (mesmo_tema and not inicio) else 0
        self.mentor.iniciar(tema, alvos, indice=indice)

    # -- marca e sessão -----------------------------------------------------
    def _aplicar_marca(self) -> None:
        self.marca = contexto_marca(self.ctx)
        self.setWindowTitle(f"{self.marca.nome_fantasia} · Bússola PDV")
        self.barra_lateral.atualizar_identidade(
            self.marca.nome_fantasia, self.usuario.nome, self.usuario.perfil.rotulo
        )
        self.barra_superior.definir_pagina(
            f"{self.marca.nome_fantasia} · {self.cabecalho.titulo.text() or 'PDV'}"
        )
        self.rodape.esquerda.setText(
            f"{self.marca.nome_fantasia} · dados locais, sem emissão fiscal"
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
        self.barra_lateral.atualizar_identidade(
            self.marca.nome_fantasia, atualizado.nome, atualizado.perfil.rotulo
        )
        self.barra_superior.definir_usuario(atualizado.nome, atualizado.perfil.rotulo)
        for tela in (
            self.tela_pdv,
            self.tela_caixa,
            *(self.pilha.widget(i) for i in range(self.pilha.count())),
        ):
            if tela is not None and getattr(tela, "usuario", None) is not None:
                setattr(tela, "usuario", atualizado)  # noqa: B010 - atributo só existe em algumas telas
        self.tela_pdv.atualizar()


__all__ = [
    "DETALHES_MODULO",
    "MODULOS",
    "MODULO_ADMIN",
    "JanelaPrincipal",
    "QListWidget",
]
