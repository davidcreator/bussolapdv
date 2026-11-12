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
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..aplicacao.contexto import Contexto
from ..aplicacao.exportacao import ServicoExportacao
from ..dominio.usuario import Usuario
from ..infra.exportacao.formato import celula
from .exportacao import BotaoExportar
from .widgets import CaixaInfo, Cartao, ajustar_colunas, preparar_tabela


class TelaClientes(QWidget):
    def __init__(self, contexto: Contexto, usuario: Usuario, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = contexto
        self.usuario = usuario
        self.exportacao = ServicoExportacao(contexto)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.kpi_ativos = CaixaInfo("Clientes ativos", "0", "clientes", "primaria", "na carteira")
        self.kpi_limite = CaixaInfo("Limite concedido", "R$ 0,00", "crediario", "claro", "soma dos limites")
        self.kpi_aberto = CaixaInfo("Em aberto", "R$ 0,00", "dinheiro", "alerta", "saldo no crediário")
        self.kpi_vencido = CaixaInfo("Vencido", "R$ 0,00", "aviso", "claro", "títulos em atraso")
        indicadores = QHBoxLayout()
        indicadores.setSpacing(10)
        for caixa_info in (self.kpi_ativos, self.kpi_limite, self.kpi_aberto, self.kpi_vencido):
            indicadores.addWidget(caixa_info, 1)
        layout.addLayout(indicadores)

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


__all__ = ["TelaClientes"]
