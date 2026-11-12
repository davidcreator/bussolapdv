"""Seção 'Manutenção': cópias de segurança, verificação e restauração."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...aplicacao.administracao import ServicoAdministracao
from ...aplicacao.contexto import Contexto
from ...caminhos import (
    banco_em,
    definir_diretorio_de_dados,
    diretorio_de_dados,
    origem_do_diretorio,
)
from ...dominio.auditoria import AcaoAuditoria, EventoAuditoria
from ...dominio.usuario import Acao, Usuario
from .comum import Mensagem, descrever_erro

PASTA_PADRAO = Path("copias")


class SecaoManutencao(QWidget):
    def __init__(self, contexto: Contexto, usuario: Usuario, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = contexto
        self.usuario = usuario
        self.servico = ServicoAdministracao(contexto)

        layout = QVBoxLayout(self)
        ajuda = QLabel(
            "A cópia é feita pela API do SQLite, com a base aberta: não é cópia de arquivo em uso. "
            "Restaurar substitui os dados atuais e guarda a base anterior ao lado, "
            "mas é decisão do Admin Master."
        )
        ajuda.setWordWrap(True)
        ajuda.setObjectName("textoAjuda")
        layout.addWidget(ajuda)

        # -- pasta de dados da instalação (a escolha também existe no primeiro uso)
        grupo_dados = QGroupBox("Pasta de dados da instalação")
        layout_dados = QVBoxLayout(grupo_dados)
        self.rotulo_dados = QLabel()
        self.rotulo_dados.setObjectName("textoAjuda")
        self.rotulo_dados.setWordWrap(True)
        linha_dados = QHBoxLayout()
        self.botao_dados = QPushButton("Alterar pasta dos dados…")
        self.botao_dados.setObjectName("secundario")
        self.botao_dados.clicked.connect(self._alterar_pasta_dados)
        self.botao_dados.setEnabled(usuario.eh_master)
        if not usuario.eh_master:
            self.botao_dados.setToolTip(
                "Mudar a pasta de dados afeta todas as estações: só o Admin Master altera."
            )
        linha_dados.addStretch(1)
        linha_dados.addWidget(self.botao_dados)
        layout_dados.addWidget(self.rotulo_dados)
        layout_dados.addLayout(linha_dados)
        layout.addWidget(grupo_dados)
        self._pasta_trocada_agora = False
        self._atualizar_pasta_dados()

        grupo_destino = QGroupBox("Destino das cópias")
        linha_destino = QHBoxLayout(grupo_destino)
        self.campo_destino = QLineEdit(str(PASTA_PADRAO))
        self.botao_pasta = QPushButton("Escolher pasta…")
        self.botao_pasta.setObjectName("secundario")
        self.botao_pasta.clicked.connect(self._escolher_pasta)
        self.botao_backup = QPushButton("Gerar cópia agora")
        self.botao_backup.clicked.connect(self._gerar)
        linha_destino.addWidget(QLabel("Pasta"))
        linha_destino.addWidget(self.campo_destino, 1)
        linha_destino.addWidget(self.botao_pasta)
        linha_destino.addWidget(self.botao_backup)
        layout.addWidget(grupo_destino)

        self.tabela = QTableWidget(0, 3)
        self.tabela.setHorizontalHeaderLabels(["Arquivo", "Tamanho", "Modificado"])
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabela.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        cabecalho = self.tabela.horizontalHeader()
        cabecalho.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        cabecalho.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        cabecalho.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.tabela, 1)

        botoes = QHBoxLayout()
        self.botao_listar = QPushButton("Atualizar lista")
        self.botao_listar.setObjectName("secundario")
        self.botao_listar.clicked.connect(self._listar)
        self.botao_verificar = QPushButton("Verificar cópia selecionada")
        self.botao_verificar.setObjectName("secundario")
        self.botao_verificar.clicked.connect(self._verificar)
        self.botao_abrir = QPushButton("Verificar arquivo…")
        self.botao_abrir.setObjectName("secundario")
        self.botao_abrir.clicked.connect(self._verificar_arquivo)
        self.botao_restaurar = QPushButton("Restaurar selecionada…")
        self.botao_restaurar.setObjectName("perigo")
        self.botao_restaurar.clicked.connect(self._restaurar)
        botoes.addWidget(self.botao_listar)
        botoes.addWidget(self.botao_verificar)
        botoes.addWidget(self.botao_abrir)
        botoes.addStretch(1)
        botoes.addWidget(self.botao_restaurar)
        layout.addLayout(botoes)

        self.mensagem = Mensagem()
        layout.addWidget(self.mensagem)

        pode_backup = usuario.pode(Acao.BACKUP_EXECUTAR)
        pode_restaurar = usuario.pode(Acao.BACKUP_RESTAURAR) and usuario.eh_master
        self.botao_backup.setEnabled(pode_backup)
        self.botao_restaurar.setEnabled(pode_restaurar)
        if not pode_restaurar:
            self.botao_restaurar.setToolTip(
                "Restaurar é exclusivo do Admin Master: substitui todos os dados."
            )
        self._copias: list[dict[str, object]] = []
        self._listar()

    # -- pasta de dados -----------------------------------------------------
    def _atualizar_pasta_dados(self) -> None:
        """Mostra a pasta em uso; o aviso de "reabra" só aparece após uma troca aqui."""
        pasta = diretorio_de_dados()
        origem = {
            "BUSSOLA_DADOS": "definida pela variável de ambiente BUSSOLA_DADOS",
            "configuracao": "escolhida na instalação",
            "padrao": "padrão do sistema",
        }.get(origem_do_diretorio(), origem_do_diretorio())
        aviso = ""
        if self._pasta_trocada_agora:
            aviso = (
                "<br><b>Esta sessão continua na base anterior.</b> Copie a base para "
                "a pasta nova e reabra o programa."
            )
        self.rotulo_dados.setText(
            f"<b>{pasta}</b> ({origem})<br>"
            f"Base: {banco_em(pasta)} · cópias, relatórios e logs ficam em subpastas "
            f"desta mesma pasta.{aviso}"
        )

    def _alterar_pasta_dados(self) -> None:
        atual = diretorio_de_dados()
        escolhida = QFileDialog.getExistingDirectory(
            self, "Escolha a nova pasta de dados", str(atual)
        )
        if not escolhida:
            return
        try:
            nova = definir_diretorio_de_dados(escolhida)
        except Exception as exc:
            self.mensagem.erro(descrever_erro(exc))
            return
        self._registrar_mudanca(atual, nova)
        self._pasta_trocada_agora = True
        self._atualizar_pasta_dados()
        self.mensagem.ok(
            f"Pasta de dados agora é {nova}. Copie a base atual para lá "
            "(ou use `bussola dados --mover`) e reabra o programa — esta sessão "
            "continua na base antiga."
        )

    def _registrar_mudanca(self, anterior: Path, nova: Path) -> None:
        """Mudar onde os dados moram é decisão auditável (ADR-020)."""
        agora = self.ctx.agora()
        try:
            with self.ctx.em_transacao():
                self.ctx.auditoria.registrar(
                    EventoAuditoria(
                        acao=AcaoAuditoria.PARAMETRO_ALTERADO,
                        criado_em_utc=agora,
                        data_negocio=self.ctx.relogio.data_negocio(),
                        ator_id=self.usuario.id,
                        entidade="pasta_de_dados",
                        entidade_id=str(nova),
                        antes={"pasta": str(anterior)},
                        depois={"pasta": str(nova)},
                        motivo="Alteração da pasta de dados da instalação",
                    )
                )
        except Exception as exc:  # auditoria não pode derrubar a tela
            self.mensagem.alerta(f"Pasta alterada, mas o evento não foi auditado: {exc}")

    # -- ações --------------------------------------------------------------
    def _escolher_pasta(self) -> None:
        pasta = QFileDialog.getExistingDirectory(self, "Pasta para cópias", self.campo_destino.text())
        if pasta:
            self.campo_destino.setText(pasta)
            self._listar()

    def _gerar(self) -> None:
        try:
            resultado = self.servico.backup(self.usuario, self.campo_destino.text())
        except Exception as exc:
            self.mensagem.erro(descrever_erro(exc))
            return
        tamanho = int(str(resultado["bytes"])) / 1024
        self.mensagem.ok(
            f"Cópia gravada em {resultado['arquivo']} ({tamanho:.0f} KB) e verificada: "
            f"{'íntegra' if resultado['verificado'] else 'com problemas'}."
        )
        self._listar()

    def _listar(self) -> None:
        self._copias = self.servico.listar_copias(self.campo_destino.text())
        self.tabela.setRowCount(len(self._copias))
        for linha, copia in enumerate(self._copias):
            valores = [
                str(copia["arquivo"]),
                f"{int(str(copia['bytes'])) / 1024:.0f} KB",
                str(copia["modificado"]),
            ]
            for coluna, texto in enumerate(valores):
                self.tabela.setItem(linha, coluna, QTableWidgetItem(texto))
        if not self._copias:
            self.mensagem.alerta(
                "Nenhuma cópia nesta pasta. Uma base sem cópia é uma base sem volta."
            )

    def _caminho_selecionado(self) -> str | None:
        linha = self.tabela.currentRow()
        if linha < 0 or linha >= len(self._copias):
            self.mensagem.alerta("Selecione uma cópia na lista.")
            return None
        return str(self._copias[linha]["caminho"])

    def _verificar(self) -> None:
        caminho = self._caminho_selecionado()
        if caminho is None:
            return
        self._verificar_arquivo(caminho)

    def _verificar_arquivo(self, caminho: str | None = None) -> None:
        if caminho is None:
            caminho, _ = QFileDialog.getOpenFileName(
                self, "Cópia de segurança", self.campo_destino.text(), "Bancos SQLite (*.db)"
            )
            if not caminho:
                return
        try:
            resultado = self.servico.verificar_arquivo(caminho)
        except Exception as exc:
            self.mensagem.erro(descrever_erro(exc))
            return
        if resultado["integro"]:
            self.mensagem.ok(
                f"Cópia íntegra · esquema v{resultado['versao_esquema']} · {resultado['detalhe']}"
            )
        else:
            self.mensagem.erro(f"Cópia inválida: {resultado['detalhe']}")

    def _restaurar(self) -> None:
        caminho = self._caminho_selecionado()
        if caminho is None:
            return
        digitado, ok = QInputDialog.getText(
            self,
            "Restaurar cópia",
            "Isto substitui TODOS os dados atuais (vendas, caixa, usuários).\n"
            "A base atual será copiada ao lado antes.\n\nDigite RESTAURAR para confirmar:",
            QLineEdit.EchoMode.Normal,
        )
        if not ok or digitado.strip().upper() != "RESTAURAR":
            self.mensagem.alerta("Restauração cancelada.")
            return
        try:
            resultado = self.servico.restaurar(self.usuario, caminho)
        except Exception as exc:
            self.mensagem.erro(descrever_erro(exc))
            return
        self.mensagem.ok(
            f"Base restaurada de {resultado['origem']}. Cópia da base anterior em "
            f"{resultado['copia_de_seguranca']}. Reabra a aplicação para recarregar tudo."
        )
