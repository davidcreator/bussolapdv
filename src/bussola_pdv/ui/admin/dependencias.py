"""Seção 'Visão geral e dependências': o retrato técnico da instalação."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...aplicacao.administracao import ServicoAdministracao, StatusDiagnostico
from ...aplicacao.contexto import Contexto
from ...dominio.usuario import Acao, Usuario
from .comum import Mensagem, descrever_erro

_CORES = {
    StatusDiagnostico.OK.value: "#0B7A3B",
    StatusDiagnostico.ATENCAO.value: "#8A5A00",
    StatusDiagnostico.ERRO.value: "#B00020",
    StatusDiagnostico.INFO.value: "#5A5A5A",
}


class SecaoDependencias(QWidget):
    def __init__(self, contexto: Contexto, usuario: Usuario, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = contexto
        self.usuario = usuario
        self.servico = ServicoAdministracao(contexto)

        layout = QVBoxLayout(self)
        titulo = QLabel("Visão geral e dependências")
        titulo.setObjectName("destaqueAdmin")
        layout.addWidget(titulo)
        explicacao = QLabel(
            "Cada linha abaixo é uma checagem executada agora, não um texto fixo. "
            "Vermelho significa impedimento técnico; âmbar, atenção."
        )
        explicacao.setWordWrap(True)
        explicacao.setObjectName("textoAjuda")
        layout.addWidget(explicacao)

        self.tabela = QTableWidget(0, 4)
        self.tabela.setHorizontalHeaderLabels(["Grupo", "Item", "Valor", "Situação"])
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabela.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        cabecalho = self.tabela.horizontalHeader()
        cabecalho.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        cabecalho.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        cabecalho.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        cabecalho.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.tabela, 1)

        botoes = QHBoxLayout()
        self.botao_atualizar = QPushButton("Reexecutar checagens")
        self.botao_atualizar.clicked.connect(self.atualizar)
        self.botao_integridade = QPushButton("Verificar integridade")
        self.botao_integridade.setObjectName("secundario")
        self.botao_integridade.clicked.connect(self._verificar)
        self.botao_otimizar = QPushButton("Otimizar base")
        self.botao_otimizar.setObjectName("secundario")
        self.botao_otimizar.clicked.connect(self._otimizar)
        botoes.addWidget(self.botao_atualizar)
        botoes.addWidget(self.botao_integridade)
        botoes.addWidget(self.botao_otimizar)
        botoes.addStretch(1)
        layout.addLayout(botoes)

        self.mensagem = Mensagem()
        layout.addWidget(self.mensagem)

        pode_manutencao = usuario.pode(Acao.MANUTENCAO_EXECUTAR)
        self.botao_integridade.setEnabled(pode_manutencao)
        self.botao_otimizar.setEnabled(pode_manutencao)
        if not pode_manutencao:
            self.botao_otimizar.setToolTip(
                "Requer permissão de manutenção, liberável pelo Admin Master."
            )
        self.atualizar()

    def atualizar(self) -> None:
        itens = self.servico.diagnostico()
        self.tabela.setRowCount(len(itens))
        for linha, item in enumerate(itens):
            valores = (item.grupo, item.nome, item.valor, item.status.rotulo)
            for coluna, texto in enumerate(valores):
                celula = QTableWidgetItem(texto)
                if coluna == 3:
                    celula.setForeground(Qt.GlobalColor.black)
                    celula.setToolTip(item.status.rotulo)
                    celula.setData(Qt.ItemDataRole.UserRole, _CORES[item.status.value])
                if coluna in (0, 1, 2) and item.detalhe:
                    celula.setToolTip(item.detalhe)
                self.tabela.setItem(linha, coluna, celula)
            if item.status is StatusDiagnostico.ERRO:
                for coluna in range(4):
                    existente = self.tabela.item(linha, coluna)
                    if existente is not None:
                        existente.setToolTip(item.detalhe or "Requer correção antes de operar.")
        problemas = [item for item in itens if item.critico]
        if problemas:
            self.mensagem.erro(
                f"{len(problemas)} impedimento(s): "
                + "; ".join(f"{item.nome} ({item.detalhe})" for item in problemas[:3])
            )
        else:
            self.mensagem.ok("Nenhum impedimento técnico encontrado nesta execução.")

    def _verificar(self) -> None:
        try:
            resultado = self.servico.verificar_integridade(self.usuario)
        except Exception as exc:
            self.mensagem.erro(descrever_erro(exc))
            return
        if resultado["integro"] and resultado["auditoria_integra"]:
            self.mensagem.ok(
                f"Banco íntegro e cadeia de auditoria válida "
                f"({resultado['eventos_auditoria']} eventos)."
            )
        else:
            self.mensagem.erro(
                f"Integridade: {resultado['integro']} · auditoria: "
                f"{resultado['auditoria_integra']} · {resultado['problemas']}"
            )
        self.atualizar()

    def _otimizar(self) -> None:
        try:
            resultado = self.servico.otimizar(self.usuario)
        except Exception as exc:
            self.mensagem.erro(descrever_erro(exc))
            return
        liberado = int(str(resultado["liberado_bytes"])) / 1024
        self.mensagem.ok(f"Base otimizada. Espaço liberado: {liberado:.0f} KB.")
        self.atualizar()
