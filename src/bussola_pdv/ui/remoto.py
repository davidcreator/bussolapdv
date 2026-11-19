"""Telas do modo terminal: primeiro uso do caixa e vendas pendentes (ADR-036).

Duas telas, dois momentos em que o caixa remoto precisa de gente:

* **primeiro uso** — o operador digita endereço, token e nome do caixa, vê a
  impressão digital do certificado do servidor e confirma. É o único momento em
  que o programa aceita um servidor novo; depois disso o certificado guardado é
  a única raiz aceita (trocar de servidor exige passar por aqui de novo);
* **vendas pendentes** — lista o que ficou na fila quando a rede caiu, com o
  motivo de cada recusa, e deixa reenviar ou descartar. Nada é descartado
  sozinho: venda sem cupom é dinheiro que ninguém sabe de onde veio.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..aplicacao.fila_offline import FilaDeVendas, ResultadoDoReenvio, reenviar
from ..infra.api.cliente import ClienteAPI, ErroDeComunicacao, inspecionar_certificado
from ..infra.rede.configuracao_terminal import (
    NOME_DO_CERTIFICADO,
    ConfiguracaoRemota,
    ErroDeConfiguracao,
    InspecaoDeCertificado,
    guardar_certificado,
    remover,
    salvar,
)
from .widgets import titulo_de_secao


class DialogoConfiguracaoDoCaixa(QDialog):
    """Liga este computador a um servidor da loja (modo terminal)."""

    def __init__(self, pasta_de_dados: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.pasta = Path(pasta_de_dados)
        self.configuracao: ConfiguracaoRemota | None = None
        self._inspecao: InspecaoDeCertificado | None = None
        self.setWindowTitle("Este caixa trabalha em rede")
        self.setObjectName("dialogo_configuracao_caixa")
        self.setMinimumWidth(520)

        campo_endereco = QLineEdit("https://")
        campo_endereco.setPlaceholderText("https://192.168.0.10:8765")
        campo_token = QLineEdit()
        campo_token.setEchoMode(QLineEdit.EchoMode.Password)
        campo_token.setPlaceholderText("token da API (o mesmo do servidor)")
        campo_nome = QLineEdit("CAIXA-02")
        for campo, object_name in (
            (campo_endereco, "campo_endereco_servidor"),
            (campo_token, "campo_token_servidor"),
            (campo_nome, "campo_nome_do_caixa"),
        ):
            campo.setObjectName(object_name)
        self.campo_endereco = campo_endereco
        self.campo_token = campo_token
        self.campo_nome = campo_nome

        self.rotulo_digital = QLabel("—")
        self.rotulo_digital.setObjectName("digital_do_servidor")
        self.rotulo_digital.setWordWrap(True)
        self.rotulo_digital.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.botao_verificar = QPushButton("Verificar servidor")
        self.botao_verificar.setObjectName("verificar_servidor")
        self.botao_verificar.clicked.connect(self._verificar)

        formulario = QFormLayout()
        formulario.addRow("Endereço do servidor", campo_endereco)
        formulario.addRow("Token da API", campo_token)
        formulario.addRow("Nome deste caixa", campo_nome)
        formulario.addRow(self.botao_verificar, self.rotulo_digital)

        botoes = QDialogButtonBox()
        self.botao_salvar = botoes.addButton("Confiar e usar", QDialogButtonBox.ButtonRole.AcceptRole)
        self.botao_salvar.setObjectName("salvar_configuracao")
        self.botao_salvar.setEnabled(False)
        botoes.addButton("Cancelar", QDialogButtonBox.ButtonRole.RejectRole)
        botoes.accepted.connect(self._salvar)
        botoes.rejected.connect(self.reject)

        aviso = QLabel(
            "O sertificado deste servidor é gerado pelo próprio programa, não por uma "
            "autoridade da internet. Confira a impressão digital com quem instalou o "
            "servidor antes de confiar: é a única coisa que impede um computador "
            "falso na rede de receber as senhas da loja."
        )
        aviso.setWordWrap(True)
        aviso.setObjectName("aviso_certificado")

        layout = QVBoxLayout(self)
        layout.addWidget(titulo_de_secao("Ligar este caixa ao servidor"))
        layout.addLayout(formulario)
        layout.addWidget(aviso)
        layout.addWidget(botoes)

    # -- passos -------------------------------------------------------------
    def _verificar(self) -> None:
        endereco = self.campo_endereco.text().strip()
        try:
            inspecao = inspecionar_certificado(endereco)
        except (ErroDeComunicacao, ErroDeConfiguracao) as exc:
            self.botao_salvar.setEnabled(False)
            self.rotulo_digital.setText(f"Não foi possível verificar: {exc}")
            return
        self._inspecao = inspecao
        self.rotulo_digital.setText(
            f"Impressão digital SHA-256 do servidor:\n{inspecao.digital}\n\n"
            "Confira com o valor que aparece quando o servidor sobe. "
            "Se for o mesmo, clique em “Confiar e usar”."
        )
        self.botao_salvar.setEnabled(True)

    def _salvar(self) -> None:
        if self._inspecao is None:
            return
        try:
            configuracao = ConfiguracaoRemota(
                endereco=self.campo_endereco.text().strip(),
                token=self.campo_token.text().strip(),
                terminal=self.campo_nome.text().strip() or "CAIXA-01",
                digital=self._inspecao.digital,
                certificado=NOME_DO_CERTIFICADO,
            )
        except ErroDeConfiguracao as exc:
            QMessageBox.warning(self, "Configuração incompleta", str(exc))
            return
        guardar_certificado(self.pasta, self._inspecao.der, configuracao=configuracao)
        salvar(self.pasta, configuracao)
        self.configuracao = configuracao
        self.accept()


class DialogoPendencias(QDialog):
    """Vendas que ficaram na fila quando a rede caiu."""

    COLUNAS = ("Quando", "Operador", "Terminal", "Situação", "Motivo")

    def __init__(
        self,
        fila: FilaDeVendas,
        cliente: ClienteAPI | None = None,
        *,
        solicitacao_tipo: Any = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.fila = fila
        self.cliente = cliente
        self.solicitacao_tipo = solicitacao_tipo
        self.setWindowTitle("Vendas pendentes deste caixa")
        self.setObjectName("dialogo_pendencias")
        self.setMinimumSize(720, 380)

        self.tabela = QTableWidget(0, len(self.COLUNAS))
        self.tabela.setObjectName("tabela_pendencias")
        self.tabela.setHorizontalHeaderLabels(self.COLUNAS)
        self.tabela.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabela.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        self.botao_reenviar = QPushButton("Reenviar agora")
        self.botao_reenviar.setObjectName("reenviar_pendencias")
        self.botao_reenviar.clicked.connect(self._reenviar)
        self.botao_descartar = QPushButton("Descartar selecionada")
        self.botao_descartar.setObjectName("descartar_pendencia")
        self.botao_descartar.clicked.connect(self._descartar)
        self.rotulo_resultado = QLabel("")
        self.rotulo_resultado.setWordWrap(True)
        self.rotulo_resultado.setObjectName("resultado_reenvio")

        rodape = QHBoxLayout()
        rodape.addWidget(self.botao_reenviar)
        rodape.addWidget(self.botao_descartar)
        rodape.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(titulo_de_secao("Vendas guardadas neste caixa"))
        explicacao = QLabel(
            "Estas vendas aconteceram com o servidor fora do ar. Reenviar é seguro: "
            "cada uma tem chave própria e o servidor não registra duas vezes. Venda "
            "recusada por regra (estoque, limite) fica aqui com o motivo — quem "
            "decide o que fazer é a loja."
        )
        explicacao.setWordWrap(True)
        layout.addWidget(explicacao)
        layout.addWidget(self.tabela, 1)
        layout.addLayout(rodape)
        layout.addWidget(self.rotulo_resultado)
        fechar = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        fechar.rejected.connect(self.reject)
        fechar.clicked.connect(self.accept)
        layout.addWidget(fechar)
        self.atualizar()

    def atualizar(self) -> None:
        registros = self.fila.pendentes()
        self.tabela.setRowCount(len(registros))
        for linha, registro in enumerate(registros):
            valores = (
                registro.criada_em.replace("T", " ")[:16],
                registro.operador_login,
                registro.terminal,
                "recusada" if registro.precisa_de_atencao else "aguardando envio",
                registro.motivo or f"{registro.tentativas} tentativa(s)",
            )
            for coluna, valor in enumerate(valores):
                item = QTableWidgetItem(str(valor))
                self.tabela.setItem(linha, coluna, item)
        self.tabela.resizeColumnsToContents()
        self.botao_reenviar.setEnabled(bool(registros) and self.cliente is not None)

    def _reenviar(self) -> None:
        if self.cliente is None or self.cliente.operador is None:
            self.rotulo_resultado.setText("Entre no caixa antes de reenviar.")
            return
        resultado = reenviar(
            self.fila,
            self.cliente,
            solicitacao_tipo=self.solicitacao_tipo,
            operador_id=self.cliente.operador.id,
        )
        self.rotulo_resultado.setText(self._resumo(resultado))
        self.atualizar()

    @staticmethod
    def _resumo(resultado: ResultadoDoReenvio) -> str:
        partes = [
            f"{resultado.enviadas} enviada(s)",
            f"{resultado.recusadas} recusada(s)",
            f"{resultado.continuam_pendentes} ainda pendente(s)",
        ]
        texto = ", ".join(partes) + "."
        if resultado.mensagens:
            texto += " " + " ".join(resultado.mensagens[:5])
        return texto

    def _descartar(self) -> None:
        linha = self.tabela.currentRow()
        registros = self.fila.pendentes()
        if linha < 0 or linha >= len(registros):
            return
        registro = registros[linha]
        resposta = QMessageBox.question(
            self,
            "Descartar venda pendente",
            "Descartar esta venda definitivamente? O dinheiro não vai aparecer em "
            "relatório nenhum — só faça isso se a venda já foi registrada por outro "
            "caminho.",
        )
        if resposta != QMessageBox.StandardButton.Yes:
            return
        self.fila.descartar(registro.chave)
        self.rotulo_resultado.setText(f"Venda {registro.chave[:8]} descartada.")
        self.atualizar()


def caixa_configurado(pasta: Path) -> bool:
    """Há configuração de rede nesta máquina? (usado pela abertura do programa)"""
    return (Path(pasta) / "terminal.json").is_file()


def voltar_ao_modo_local(pasta: Path) -> bool:
    return remover(pasta)


__all__ = [
    "DialogoConfiguracaoDoCaixa",
    "DialogoPendencias",
    "caixa_configurado",
    "voltar_ao_modo_local",
]
