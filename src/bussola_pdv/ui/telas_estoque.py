"""Tela de estoque: saldo, mínimo, ponto de pedido e valor a custo.

Como as demais telas novas, desenha o `Relatorio` do serviço de exportação — a
planilha que o gerente leva e a tela que o repositor mostra são o mesmo dado.
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
from .responsivo import GradeDeIndicadores
from .widgets import CaixaInfo, Cartao, ajustar_colunas, preparar_tabela


class TelaEstoque(QWidget):
    def __init__(self, contexto: Contexto, usuario: Usuario, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = contexto
        self.usuario = usuario
        self.exportacao = ServicoExportacao(contexto)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.kpi_ruptura = CaixaInfo("Em ruptura", "0", "estoque", "claro", "saldo zerado")
        self.kpi_baixo = CaixaInfo("Abaixo do mínimo", "0", "aviso", "claro", "repor agora")
        self.kpi_custo = CaixaInfo("Valor a custo", "R$ 0,00", "dinheiro", "claro", "saldo × custo")
        indicadores = GradeDeIndicadores((self.kpi_ruptura, self.kpi_baixo, self.kpi_custo))
        layout.addWidget(indicadores)

        cartao = Cartao(
            "Saldo por produto",
            "Posição corrente do livro de movimentos; não é contagem física nem inventário",
        )
        self.botao_exportar = BotaoExportar(
            usuario=usuario,
            servico=self.exportacao,
            construir=lambda: self.exportacao.relatorio_estoque(self.campo_busca.text()),
            parent=self,
        )
        cartao.adicionar_ferramenta(self.botao_exportar)

        linha = QHBoxLayout()
        self.campo_busca = QLineEdit()
        self.campo_busca.setPlaceholderText("buscar por código, código de barras ou descrição")
        self.campo_busca.textChanged.connect(self.atualizar)
        self.rotulo_resumo = QLabel()
        self.rotulo_resumo.setObjectName("textoAjuda")
        linha.addWidget(self.campo_busca, 1)
        linha.addWidget(self.rotulo_resumo, 2)

        self.tabela = QTableWidget(0, 8)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setAlternatingRowColors(True)
        preparar_tabela(self.tabela)
        ajustar_colunas(self.tabela, 1)

        cartao.adicionar_layout(linha)
        cartao.adicionar(self.tabela, 1)
        layout.addWidget(cartao, 1)
        self.atualizar()

    def atualizar(self) -> None:
        busca = self.campo_busca.text() if hasattr(self, "campo_busca") else ""
        relatorio = self.exportacao.relatorio_estoque(busca)
        produtos = relatorio.tabelas[0]

        self.tabela.setColumnCount(len(produtos.colunas))
        self.tabela.setHorizontalHeaderLabels([coluna.titulo for coluna in produtos.colunas])
        self.tabela.setRowCount(len(produtos.linhas))
        for numero_linha, valores in enumerate(produtos.linhas):
            for numero_coluna, (valor, coluna) in enumerate(
                zip(valores, produtos.colunas, strict=True)
            ):
                item = QTableWidgetItem(celula(valor, coluna.tipo))
                if coluna.numerica:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self.tabela.setItem(numero_linha, numero_coluna, item)

        valores_kpi = dict(relatorio.indicadores)
        ruptura = valores_kpi.get("Ruptura", "0")
        baixo = valores_kpi.get("Abaixo do mínimo", "0")
        self.kpi_ruptura.definir(
            ruptura, "saldo zerado", "erro" if ruptura != "0" else "claro"
        )
        self.kpi_baixo.definir(baixo, "repor agora", "alerta" if baixo != "0" else "claro")
        self.kpi_custo.definir(valores_kpi.get("Valor a custo", "R$ 0,00"), "saldo × custo", "claro")
        self.rotulo_resumo.setText(
            f"{len(produtos.linhas)} produto(s) · {ruptura} em ruptura · {baixo} abaixo do mínimo · "
            f"{valores_kpi.get('Valor a custo', 'R$ 0,00')} a custo"
        )


__all__ = ["TelaEstoque"]
