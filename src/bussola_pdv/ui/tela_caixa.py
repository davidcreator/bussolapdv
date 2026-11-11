"""Abertura, movimentações e conferência do turno de caixa."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..aplicacao.caixa import ServicoCaixa
from ..aplicacao.contexto import Contexto
from ..dominio.caixa import (
    DENOMINACOES_BRL,
    ROTULOS_DENOMINACAO,
    ContagemDenominacao,
    TipoMovimentoCaixa,
    total_contagem,
)
from ..dominio.dinheiro import Dinheiro
from ..dominio.erros import ErroBussola
from ..dominio.usuario import Acao, Usuario
from ..infra.sqlite.repositorio_caixa import TurnoRegistrado
from .login import DialogoAutorizacao


class DialogoFechamentoCaixa(QDialog):
    def __init__(self, contexto: Contexto, esperado: Dinheiro, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Conferência e fechamento do turno")
        self.setMinimumWidth(420)
        self.campos: dict[int, QSpinBox] = {}

        tabela = QTableWidget(len(DENOMINACOES_BRL), 2)
        tabela.setHorizontalHeaderLabels(["Denominação", "Quantidade"])
        tabela.verticalHeader().setVisible(False)
        tabela.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for linha, denominacao in enumerate(DENOMINACOES_BRL):
            tabela.setItem(linha, 0, QTableWidgetItem(ROTULOS_DENOMINACAO[denominacao]))
            campo = QSpinBox()
            campo.setRange(0, 9_999)
            campo.valueChanged.connect(self._recalcular)
            self.campos[denominacao] = campo
            tabela.setCellWidget(linha, 1, campo)

        self.rotulo_contado = QLabel()
        self.rotulo_diferenca = QLabel()
        self.rotulo_esperado = QLabel(esperado.formatado())
        self.campo_motivo = QLineEdit()
        self.campo_motivo.setPlaceholderText("motivo da diferença (obrigatório se houver diferença)")
        self.esperado = esperado

        resumo = QFormLayout()
        resumo.addRow("Esperado na gaveta", self.rotulo_esperado)
        resumo.addRow("Contado", self.rotulo_contado)
        resumo.addRow("Diferença", self.rotulo_diferenca)

        botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        botoes.button(QDialogButtonBox.StandardButton.Ok).setText("Fechar turno")
        botoes.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        botoes.accepted.connect(self.accept)
        botoes.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(tabela)
        layout.addLayout(resumo)
        layout.addWidget(QLabel("Observação do conferente:"))
        layout.addWidget(self.campo_motivo)
        layout.addWidget(botoes)
        self._recalcular()

    def contagens(self) -> list[ContagemDenominacao]:
        return [
            ContagemDenominacao(denominacao, campo.value())
            for denominacao, campo in self.campos.items()
            if campo.value() > 0
        ]

    def _recalcular(self) -> None:
        contado = total_contagem(self.contagens())
        diferenenca = contado - self.esperado
        self.rotulo_contado.setText(contado.formatado())
        self.rotulo_diferenca.setText(diferenca_texto(diferenenca))
        self.rotulo_diferenca.setObjectName(
            "mensagemOk" if diferenenca.centavos == 0 else "mensagemAlerta"
        )
        self.rotulo_diferenca.style().unpolish(self.rotulo_diferenca)
        self.rotulo_diferenca.style().polish(self.rotulo_diferenca)

    @property
    def motivo(self) -> str:
        return self.campo_motivo.text().strip()


def diferenca_texto(diferenca: Dinheiro) -> str:
    if diferenca.centavos == 0:
        return "sem diferença"
    sinal = "sobra" if diferenca.centavos > 0 else "falta"
    return f"{diferenca.formatado()} ({sinal})"


class TelaCaixa(QWidget):
    turno_alterado = Signal()

    def __init__(self, contexto: Contexto, usuario: Usuario, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = contexto
        self.usuario = usuario
        self.servico = ServicoCaixa(contexto)
        self._montar()
        self.atualizar()

    def _montar(self) -> None:
        layout = QVBoxLayout(self)
        self.rotulo_status = QLabel()
        self.mensagem = QLabel("")
        self.mensagem.setObjectName("mensagemAlerta")
        self.mensagem.setWordWrap(True)

        grupo_acao = QGroupBox("Turno")
        linha = QHBoxLayout(grupo_acao)
        self.botao_abrir = QPushButton("Abrir turno")
        self.botao_abrir.clicked.connect(self._abrir)
        self.botao_sangria = QPushButton("Sangria")
        self.botao_sangria.setObjectName("secundario")
        self.botao_sangria.clicked.connect(lambda: self._movimentar(TipoMovimentoCaixa.SANGRIA))
        self.botao_suprimento = QPushButton("Suprimento")
        self.botao_suprimento.setObjectName("secundario")
        self.botao_suprimento.clicked.connect(lambda: self._movimentar(TipoMovimentoCaixa.SUPRIMENTO))
        self.botao_fechar = QPushButton("Conferir e fechar")
        self.botao_fechar.setObjectName("perigo")
        self.botao_fechar.clicked.connect(self._fechar)
        for botao in (self.botao_abrir, self.botao_sangria, self.botao_suprimento, self.botao_fechar):
            linha.addWidget(botao)

        grupo_mov = QGroupBox("Movimentos do turno")
        layout_mov = QVBoxLayout(grupo_mov)
        self.tabela = QTableWidget(0, 3)
        self.tabela.setHorizontalHeaderLabels(["Tipo", "Valor", "Motivo"])
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        layout_mov.addWidget(self.tabela)

        self.rotulo_resumo = QLabel()
        self.rotulo_resumo.setObjectName("totalCupom")
        self.rotulo_resumo.setAlignment(Qt.AlignmentFlag.AlignRight)

        layout.addWidget(self.rotulo_status)
        layout.addWidget(self.mensagem)
        layout.addWidget(grupo_acao)
        layout.addWidget(grupo_mov, 1)
        layout.addWidget(self.rotulo_resumo)

    # -- estado -------------------------------------------------------------
    def _turno(self) -> tuple[dict[str, str], TurnoRegistrado | None]:
        for caixa in self.ctx.caixas.listar_caixas():
            turno = self.ctx.caixas.turno_aberto(caixa["id"])
            if turno is not None:
                return caixa, turno
        return {}, None

    def atualizar(self) -> None:
        caixa, turno = self._turno()
        if turno is None:
            self.rotulo_status.setText("Nenhum turno aberto.")
            self.botao_abrir.setEnabled(True)
            for botao in (self.botao_sangria, self.botao_suprimento, self.botao_fechar):
                botao.setEnabled(False)
            self.tabela.setRowCount(0)
            self.rotulo_resumo.setText("Esperado na gaveta: R$ 0,00")
            return
        self.botao_abrir.setEnabled(False)
        for botao in (self.botao_sangria, self.botao_suprimento, self.botao_fechar):
            botao.setEnabled(True)
        self.rotulo_status.setText(
            f"Turno aberto no caixa {caixa['nome']} desde "
            f"{turno.aberto_em.astimezone(self.ctx.relogio.fuso()).strftime('%d/%m/%Y %H:%M')} · "
            f"fundo {turno.fundo.formatado()} · data {turno.data_negocio}"
        )
        movimentos = self.ctx.caixas.movimentos(turno.id)
        self.tabela.setRowCount(len(movimentos))
        for linha, movimento in enumerate(movimentos):
            self.tabela.setItem(linha, 0, QTableWidgetItem(movimento.tipo.rotulo))
            item_valor = QTableWidgetItem(movimento.valor_assinado.formatado())
            item_valor.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.tabela.setItem(linha, 1, item_valor)
            self.tabela.setItem(linha, 2, QTableWidgetItem(movimento.motivo))
        esperado = self.ctx.caixas.carregar_turno(turno.id).esperado
        self.rotulo_resumo.setText(f"Esperado na gaveta: {esperado.formatado()}")

    def _mensagem(self, texto: str) -> None:
        self.mensagem.setText(texto)

    # -- ações --------------------------------------------------------------
    def _abrir(self) -> None:
        from PySide6.QtWidgets import QInputDialog

        texto, ok = QInputDialog.getText(self, "Abrir turno", "Fundo de troco (R$):", text="0,00")
        if not ok:
            return
        try:
            fundo = Dinheiro.de_texto(texto)
            self.servico.abrir_turno(caixa="Caixa 1", operador=self.usuario, fundo=fundo)
        except ErroBussola as exc:
            self._mensagem(str(exc))
            return
        self._mensagem(f"Turno aberto com fundo de {fundo.formatado()}.")
        self.atualizar()
        self.turno_alterado.emit()

    def _movimentar(self, tipo: TipoMovimentoCaixa) -> None:
        from PySide6.QtWidgets import QInputDialog

        texto, ok = QInputDialog.getText(
            self, tipo.rotulo, f"Valor da {tipo.rotulo.lower()} (R$):"
        )
        if not ok:
            return
        motivo, ok = QInputDialog.getText(self, tipo.rotulo, "Motivo (obrigatório):")
        if not ok or not motivo.strip():
            self._mensagem("Operação cancelada: motivo é obrigatório.")
            return
        autorizador = None
        if tipo.exige_autorizacao:
            dialogo = DialogoAutorizacao(
                self.ctx, Acao.CAIXA_SANGRIA, "Sangria exige autorização de gerente.", self
            )
            if dialogo.exec() != dialogo.DialogCode.Accepted:
                self._mensagem("Sangria não registrada: autorização cancelada.")
                return
            autorizador = dialogo.autorizador
        _, turno = self._turno()
        if turno is None:
            self._mensagem("Nenhum turno aberto.")
            return
        try:
            self.servico.movimentar(
                turno_id=turno.id,
                tipo=tipo,
                valor=Dinheiro.de_texto(texto),
                motivo=motivo.strip(),
                operador=self.usuario,
                autorizador=autorizador,
            )
        except ErroBussola as exc:
            self._mensagem(str(exc))
            return
        self._mensagem(f"{tipo.rotulo} registrada.")
        self.atualizar()
        self.turno_alterado.emit()

    def _fechar(self) -> None:
        _, turno = self._turno()
        if turno is None:
            self._mensagem("Nenhum turno aberto.")
            return
        esperado = self.ctx.caixas.carregar_turno(turno.id).esperado
        dialogo = DialogoFechamentoCaixa(self.ctx, esperado, self)
        if dialogo.exec() != dialogo.DialogCode.Accepted:
            return
        try:
            resultado = self.servico.fechar_turno(
                turno_id=turno.id,
                conferente=self.usuario,
                contagens=dialogo.contagens(),
                motivo_diferenca=dialogo.motivo,
            )
        except ErroBussola as exc:
            self._mensagem(str(exc))
            return
        conferencia = resultado.conferencia
        QMessageBox.information(
            self,
            "Turno fechado",
            "Conferência registrada.\n"
            f"Esperado: {Dinheiro(conferencia['esperado_centavos']).formatado()}\n"
            f"Contado: {Dinheiro(conferencia['contado_centavos']).formatado()}\n"
            f"Diferença: {Dinheiro(conferencia['diferenca_centavos']).formatado()} "
            f"({conferencia['classificacao']})\n"
            + ("\n".join(resultado.avisos)),
        )
        self.atualizar()
        self.turno_alterado.emit()
