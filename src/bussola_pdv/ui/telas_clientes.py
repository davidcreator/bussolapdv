"""Tela de clientes: carteira, limite e o que cada um deve no crediário.

A tela **não recalcula nada**: ela desenha o `Relatorio` que
`ServicoExportacao.relatorio_clientes` monta. É o que garante que a planilha
exportada e o que está na tela nunca discordem — mesma consulta, mesmo
arredondamento, mesma data de referência.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..aplicacao.contexto import Contexto
from ..aplicacao.exportacao import ServicoExportacao
from ..aplicacao.impressao import ServicoImpressao
from ..dominio.cliente import Cliente
from ..dominio.usuario import Acao, Usuario
from ..infra.exportacao.formato import celula
from .exportacao import BotaoExportar
from .impressao import botao_para_relatorio
from .responsivo import GradeDeIndicadores
from .widgets import CaixaInfo, Cartao, ajustar_colunas, preparar_tabela


class TelaClientes(QWidget):
    def __init__(self, contexto: Contexto, usuario: Usuario, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = contexto
        self.usuario = usuario
        self.exportacao = ServicoExportacao(contexto)
        self.impressao = ServicoImpressao(contexto)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.kpi_ativos = CaixaInfo("Clientes ativos", "0", "clientes", "primaria", "na carteira")
        self.kpi_limite = CaixaInfo("Limite concedido", "R$ 0,00", "crediario", "claro", "soma dos limites")
        self.kpi_aberto = CaixaInfo("Em aberto", "R$ 0,00", "dinheiro", "alerta", "saldo no crediário")
        self.kpi_vencido = CaixaInfo("Vencido", "R$ 0,00", "aviso", "claro", "títulos em atraso")
        indicadores = GradeDeIndicadores(
            (self.kpi_ativos, self.kpi_limite, self.kpi_aberto, self.kpi_vencido)
        )
        layout.addWidget(indicadores)

        cartao = Cartao(
            "Carteira de clientes",
            "Documento mascarado (LGPD); saldo em aberto é posição corrente do crediário",
        )
        self.botao_exportar = BotaoExportar(
            usuario=usuario,
            servico=self.exportacao,
            construir=lambda: self.exportacao.relatorio_clientes(self.campo_busca.text()),
            parent=self,
        )
        cartao.adicionar_ferramenta(self.botao_exportar)
        self.botao_imprimir = botao_para_relatorio(
            ator=usuario,
            servico=self.impressao,
            construir=lambda: self.exportacao.relatorio_clientes(self.campo_busca.text()),
            rotulo="clientes",
            parent=self,
        )
        cartao.adicionar_ferramenta(self.botao_imprimir)
        if usuario.pode(Acao.CADASTRO_CLIENTE):
            self.botao_novo = QPushButton("Novo cliente")
            self.botao_novo.setObjectName("primario")
            self.botao_novo.clicked.connect(self._novo_cliente)
            cartao.adicionar_ferramenta(self.botao_novo)
            self.botao_editar = QPushButton("Alterar cliente")
            self.botao_editar.setObjectName("secundario")
            self.botao_editar.clicked.connect(self._alterar_cliente)
            cartao.adicionar_ferramenta(self.botao_editar)

        linha = QHBoxLayout()
        self.campo_busca = QLineEdit()
        self.campo_busca.setPlaceholderText("buscar por nome ou documento")
        self.campo_busca.textChanged.connect(self.atualizar)
        self.rotulo_resumo = QLabel()
        self.rotulo_resumo.setObjectName("textoAjuda")
        linha.addWidget(self.campo_busca, 1)
        linha.addWidget(self.rotulo_resumo, 2)

        self.tabela = QTableWidget(0, 7)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setAlternatingRowColors(True)
        preparar_tabela(self.tabela)
        ajustar_colunas(self.tabela, 0)

        cartao.adicionar_layout(linha)
        cartao.adicionar(self.tabela, 1)
        layout.addWidget(cartao, 1)
        self.atualizar()

    def atualizar(self) -> None:
        busca = self.campo_busca.text() if hasattr(self, "campo_busca") else ""
        relatorio = self.exportacao.relatorio_clientes(busca)
        # Mesma consulta e mesma ordem do relatório: a linha selecionada vira o
        # cliente a alterar sem procurar por nome (nome repetido não é chave).
        self._clientes = self.ctx.clientes.listar(busca=busca, limite=5000)
        tabela = relatorio.tabelas[0]

        self.tabela.setColumnCount(len(tabela.colunas))
        self.tabela.setHorizontalHeaderLabels([coluna.titulo for coluna in tabela.colunas])
        self.tabela.setRowCount(len(tabela.linhas))
        for numero_linha, valores in enumerate(tabela.linhas):
            for numero_coluna, (valor, coluna) in enumerate(zip(valores, tabela.colunas, strict=True)):
                item = QTableWidgetItem(celula(valor, coluna.tipo))
                if coluna.numerica:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self.tabela.setItem(numero_linha, numero_coluna, item)

        valores_kpi = dict(relatorio.indicadores)
        self.kpi_ativos.definir(
            valores_kpi.get("Ativos", "0"),
            "na carteira",
            "primaria" if valores_kpi.get("Ativos", "0") != "0" else "claro",
        )
        self.kpi_limite.definir(valores_kpi.get("Limite total", "R$ 0,00"), "soma dos limites", "claro")
        self.kpi_aberto.definir(
            valores_kpi.get("Em aberto", "R$ 0,00"),
            "saldo no crediário",
            "alerta" if valores_kpi.get("Em aberto", "R$ 0,00") != "R$ 0,00" else "claro",
        )
        self.kpi_vencido.definir(
            valores_kpi.get("Vencido", "R$ 0,00"),
            "títulos em atraso",
            "erro" if valores_kpi.get("Vencido", "R$ 0,00") != "R$ 0,00" else "claro",
        )
        self.rotulo_resumo.setText(
            f"{len(tabela.linhas)} cliente(s) na consulta · "
            f"{valores_kpi.get('Em aberto', 'R$ 0,00')} em aberto · "
            f"{valores_kpi.get('Vencido', 'R$ 0,00')} vencido"
        )

    # -- cadastro -----------------------------------------------------------
    def _cliente_selecionado(self) -> Cliente | None:
        linha = self.tabela.currentRow()
        carteira: list[Cliente] = getattr(self, "_clientes", [])
        if 0 <= linha < len(carteira):
            return carteira[linha]
        return None

    def _novo_cliente(self) -> None:
        from .cadastros import DialogoCliente

        dialogo = DialogoCliente(self.ctx, self.usuario, parent=self)
        if dialogo.exec() == dialogo.DialogCode.Accepted and dialogo.cliente is not None:
            self.campo_busca.setText(dialogo.cliente.nome)
            self.atualizar()

    def _alterar_cliente(self) -> None:
        from .cadastros import DialogoCliente

        cliente = self._cliente_selecionado()
        if cliente is None:
            self.rotulo_resumo.setText("Selecione um cliente na lista para alterar limite ou dados.")
            return
        dialogo = DialogoCliente(self.ctx, self.usuario, cliente=cliente, parent=self)
        if dialogo.exec() == dialogo.DialogCode.Accepted:
            self.atualizar()


__all__ = ["TelaClientes"]
