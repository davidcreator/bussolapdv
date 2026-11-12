"""Tela do crediário: títulos por vencimento, saldo e atraso.

Leitura apenas nesta entrega — receber título continua no serviço de aplicação
(`ServicoCrediario.receber`, já testado) e ainda não tem botão aqui. O que a tela
faz é mostrar e exportar; nada é simulado: se não há título, aparece vazio.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..aplicacao.contexto import Contexto
from ..aplicacao.exportacao import ServicoExportacao
from ..aplicacao.impressao import ServicoImpressao
from ..dominio.usuario import Usuario
from ..infra.exportacao.formato import celula
from .exportacao import BotaoExportar
from .impressao import botao_para_relatorio
from .responsivo import GradeDeIndicadores
from .widgets import CaixaInfo, Cartao, ajustar_colunas, preparar_tabela

COR_ATRASO = "#B02A37"


class TelaCrediario(QWidget):
    def __init__(self, contexto: Contexto, usuario: Usuario, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = contexto
        self.usuario = usuario
        self.exportacao = ServicoExportacao(contexto)
        self.impressao = ServicoImpressao(contexto)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.kpi_abertos = CaixaInfo("Títulos em aberto", "0", "crediario", "primaria", "com saldo")
        self.kpi_saldo = CaixaInfo("Saldo aberto", "R$ 0,00", "dinheiro", "claro", "a receber")
        self.kpi_atraso = CaixaInfo("Em atraso", "0", "aviso", "claro", "títulos vencidos")
        self.kpi_vencido = CaixaInfo("Saldo vencido", "R$ 0,00", "bloqueio", "claro", "cobrança")
        indicadores = GradeDeIndicadores(
            (self.kpi_abertos, self.kpi_saldo, self.kpi_atraso, self.kpi_vencido)
        )
        layout.addWidget(indicadores)

        cartao = Cartao(
            "Títulos",
            "Atraso calculado na data de negócio do sistema; recebimento é registrado no serviço",
        )
        self.botao_exportar = BotaoExportar(
            usuario=usuario,
            servico=self.exportacao,
            construir=lambda: self.exportacao.relatorio_crediario(
                incluir_pagos=self.incluir_pagos.isChecked()
            ),
            parent=self,
        )
        cartao.adicionar_ferramenta(self.botao_exportar)
        self.botao_imprimir = botao_para_relatorio(
            ator=usuario,
            servico=self.impressao,
            construir=lambda: self.exportacao.relatorio_crediario(
                incluir_pagos=self.incluir_pagos.isChecked()
            ),
            rotulo="crediario",
            parent=self,
        )
        cartao.adicionar_ferramenta(self.botao_imprimir)

        linha = QHBoxLayout()
        self.incluir_pagos = QCheckBox("incluir títulos já recebidos")
        self.incluir_pagos.stateChanged.connect(self.atualizar)
        self.rotulo_resumo = QLabel()
        self.rotulo_resumo.setObjectName("textoAjuda")
        linha.addWidget(self.incluir_pagos)
        linha.addWidget(self.rotulo_resumo, 1)

        self.tabela = QTableWidget(0, 8)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setAlternatingRowColors(True)
        preparar_tabela(self.tabela)
        ajustar_colunas(self.tabela, 0)

        cartao.adicionar_layout(linha)
        cartao.adicionar(self.tabela, 1)
        layout.addWidget(cartao, 1)
        self.atualizar()

    def atualizar(self) -> None:
        incluir_pagos = self.incluir_pagos.isChecked() if hasattr(self, "incluir_pagos") else False
        relatorio = self.exportacao.relatorio_crediario(incluir_pagos=incluir_pagos)
        tabela = relatorio.tabelas[0]

        self.tabela.setColumnCount(len(tabela.colunas))
        self.tabela.setHorizontalHeaderLabels([coluna.titulo for coluna in tabela.colunas])
        self.tabela.setRowCount(len(tabela.linhas))
        indice_atraso = next(
            (
                posicao
                for posicao, coluna in enumerate(tabela.colunas)
                if coluna.titulo.startswith("Atraso")
            ),
            None,
        )
        from PySide6.QtGui import QColor

        for numero_linha, valores in enumerate(tabela.linhas):
            atraso = int(str(valores[indice_atraso])) if indice_atraso is not None else 0
            for numero_coluna, (valor, coluna) in enumerate(zip(valores, tabela.colunas, strict=True)):
                item = QTableWidgetItem(celula(valor, coluna.tipo))
                if coluna.numerica:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                if atraso > 0:
                    item.setForeground(QColor(COR_ATRASO))
                self.tabela.setItem(numero_linha, numero_coluna, item)

        valores_kpi = dict(relatorio.indicadores)
        self.kpi_abertos.definir(
            valores_kpi.get("Em aberto", "0"),
            "com saldo",
            "primaria" if valores_kpi.get("Em aberto", "0") != "0" else "claro",
        )
        self.kpi_saldo.definir(valores_kpi.get("Saldo aberto", "R$ 0,00"), "a receber", "claro")
        atrasados = valores_kpi.get("Em atraso", "0")
        self.kpi_atraso.definir(
            atrasados, "títulos vencidos", "alerta" if atrasados != "0" else "claro"
        )
        self.kpi_vencido.definir(
            valores_kpi.get("Saldo vencido", "R$ 0,00"),
            "cobrança",
            "erro" if valores_kpi.get("Saldo vencido", "R$ 0,00") != "R$ 0,00" else "claro",
        )
        self.rotulo_resumo.setText(
            f"{len(tabela.linhas)} título(s) · {valores_kpi.get('Saldo aberto', 'R$ 0,00')} "
            f"em aberto · {valores_kpi.get('Saldo vencido', 'R$ 0,00')} vencido"
        )


__all__ = ["TelaCrediario"]
