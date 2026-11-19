"""Tela de entradas de fornecedor: o que já entrou e o botão para lançar a próxima.

A página existia só como promessa no menu ("Entradas · ainda não implementado").
Agora ela mostra o histórico do que foi lançado — fornecedor, documento, data,
itens — e abre o mesmo diálogo usado na tela de Estoque. O histórico é a resposta
para a pergunta que sempre aparece no fechamento: "de onde veio esse saldo?".
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..aplicacao.contexto import Contexto
from ..aplicacao.exportacao import ServicoExportacao
from ..aplicacao.impressao import ServicoImpressao
from ..dominio.dinheiro import Dinheiro, Quantidade
from ..dominio.usuario import Acao, Usuario
from .exportacao import BotaoExportar
from .impressao import botao_para_relatorio
from .responsivo import GradeDeIndicadores
from .widgets import CaixaInfo, Cartao, ajustar_colunas, preparar_tabela


class TelaEntradas(QWidget):
    def __init__(self, contexto: Contexto, usuario: Usuario, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = contexto
        self.usuario = usuario
        self.exportacao = ServicoExportacao(contexto)
        self.impressao = ServicoImpressao(contexto)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.kpi_entradas = CaixaInfo("Entradas", "0", "entradas", "primaria", "registradas")
        self.kpi_itens = CaixaInfo("Itens recebidos", "0", "produtos", "claro", "no histórico")
        self.kpi_frete = CaixaInfo("Frete lançado", "R$ 0,00", "dinheiro", "claro", "rateado no custo")
        indicadores = GradeDeIndicadores((self.kpi_entradas, self.kpi_itens, self.kpi_frete))
        layout.addWidget(indicadores)

        cartao = Cartao(
            "Entradas de fornecedor",
            "Cada linha é uma nota lançada; a chave fornecedor + documento não se repete",
        )
        if usuario.pode(Acao.ESTOQUE_ENTRADA):
            self.botao_nova = QPushButton("Nova entrada")
            self.botao_nova.setObjectName("primario")
            self.botao_nova.clicked.connect(self._nova_entrada)
            cartao.adicionar_ferramenta(self.botao_nova)

        self.rotulo_resumo = QLabel()
        self.rotulo_resumo.setObjectName("textoAjuda")
        cartao.adicionar_ferramenta(self.rotulo_resumo)

        self.botao_exportar = BotaoExportar(
            usuario=usuario,
            servico=self.exportacao,
            construir=self.exportacao.relatorio_entradas,
            parent=self,
        )
        cartao.adicionar_ferramenta(self.botao_exportar)
        self.botao_imprimir = botao_para_relatorio(
            ator=usuario,
            servico=self.impressao,
            construir=self.exportacao.relatorio_entradas,
            rotulo="entradas",
            parent=self,
        )
        cartao.adicionar_ferramenta(self.botao_imprimir)

        self.tabela = QTableWidget(0, 6)
        self.tabela.setHorizontalHeaderLabels(
            ["Data", "Fornecedor", "Documento", "Itens", "Quantidade", "Frete"]
        )
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setAlternatingRowColors(True)
        preparar_tabela(self.tabela)
        ajustar_colunas(self.tabela, 1)

        cartao.adicionar(self.tabela, 1)
        layout.addWidget(cartao, 1)
        self.atualizar()

    def atualizar(self) -> None:
        entradas = self.ctx.entradas.listar(limite=500)
        self.tabela.setRowCount(len(entradas))
        total_itens = 0
        total_frete = 0
        for linha, entrada in enumerate(entradas):
            itens = int(entrada["itens"])
            frete = int(entrada["frete_centavos"])
            total_itens += itens
            total_frete += frete
            valores = [
                str(entrada["data_negocio"]),
                str(entrada["fornecedor"]),
                str(entrada["documento"]) or "—",
                str(itens),
                Quantidade(int(entrada["quantidade"])).formatada(),
                Dinheiro(frete).formatado(),
            ]
            for coluna, texto in enumerate(valores):
                celula = QTableWidgetItem(texto)
                if coluna >= 3:
                    celula.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self.tabela.setItem(linha, coluna, celula)

        self.kpi_entradas.definir(
            str(len(entradas)), "registradas", "primaria" if entradas else "claro"
        )
        self.kpi_itens.definir(str(total_itens), "no histórico", "claro")
        self.kpi_frete.definir(Dinheiro(total_frete).formatado(), "rateado no custo", "claro")
        self.rotulo_resumo.setText(
            f"{len(entradas)} entrada(s) · {total_itens} item(ns) · frete "
            f"{Dinheiro(total_frete).formatado()}"
            if entradas
            else "Nenhuma entrada registrada ainda."
        )

    def _nova_entrada(self) -> None:
        from .cadastros import DialogoEntrada

        dialogo = DialogoEntrada(self.ctx, self.usuario, parent=self)
        if dialogo.exec() == dialogo.DialogCode.Accepted and dialogo.resultado:
            self.atualizar()


__all__ = ["TelaEntradas"]
