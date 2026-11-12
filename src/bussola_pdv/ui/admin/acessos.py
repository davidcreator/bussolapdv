"""Seções 'Usuários' e 'Perfis e permissões'."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
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

from ...aplicacao.contexto import Contexto
from ...aplicacao.permissoes import ServicoPermissoes
from ...aplicacao.usuarios import ServicoUsuarios, UsuarioResumo
from ...dominio.usuario import Acao, Perfil, Usuario, acoes_por_categoria
from ..responsivo import FluxoDeAcoes
from .comum import Mensagem, descrever_erro


class SecaoUsuarios(QWidget):
    usuarios_alterados = Signal()

    def __init__(self, contexto: Contexto, usuario: Usuario, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = contexto
        self.usuario = usuario
        self.servico = ServicoUsuarios(contexto)

        layout = QVBoxLayout(self)
        ajuda = QLabel(
            "Cada usuário tem um perfil, e o perfil define o que ele alcança. "
            "Você só gerencia quem está abaixo do seu nível; ninguém altera o próprio acesso."
        )
        ajuda.setWordWrap(True)
        ajuda.setObjectName("textoAjuda")
        layout.addWidget(ajuda)

        self.tabela = QTableWidget(0, 6)
        self.tabela.setHorizontalHeaderLabels(
            ["Nome", "Login", "Perfil", "Situação", "Permissões", "Criado em"]
        )
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabela.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabela.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        cabecalho = self.tabela.horizontalHeader()
        cabecalho.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for coluna in range(1, 6):
            cabecalho.setSectionResizeMode(coluna, QHeaderView.ResizeMode.ResizeToContents)
        self.tabela.itemSelectionChanged.connect(self._selecionado)
        layout.addWidget(self.tabela, 1)

        linha_acoes = FluxoDeAcoes()  # quebra em linhas em janela estreita
        self.combo_perfil = QComboBox()
        self.botao_perfil = QPushButton("Aplicar perfil")
        self.botao_perfil.setObjectName("secundario")
        self.botao_perfil.clicked.connect(self._aplicar_perfil)
        self.botao_ativar = QPushButton("Ativar")
        self.botao_ativar.setObjectName("secundario")
        self.botao_ativar.clicked.connect(self._ativar)
        self.botao_desativar = QPushButton("Desativar")
        self.botao_desativar.setObjectName("perigo")
        self.botao_desativar.clicked.connect(self._desativar)
        self.botao_senha = QPushButton("Redefinir senha")
        self.botao_senha.setObjectName("secundario")
        self.botao_senha.clicked.connect(self._redefinir_senha)
        self.botao_master = QPushButton("Transferir propriedade…")
        self.botao_master.setObjectName("secundario")
        self.botao_master.clicked.connect(self._transferir)
        self.botao_master.setVisible(usuario.eh_master)
        self.combo_perfil.setMinimumWidth(190)
        for acao in (
            self.combo_perfil,
            self.botao_perfil,
            self.botao_ativar,
            self.botao_desativar,
            self.botao_senha,
            self.botao_master,
        ):
            linha_acoes.adicionar(acao)
        layout.addWidget(linha_acoes)

        grupo = QGroupBox("Novo usuário")
        formulario = QFormLayout(grupo)
        self.campo_login = QLineEdit()
        self.campo_login.setPlaceholderText("ex.: maria.silva")
        self.campo_nome = QLineEdit()
        self.campo_nome.setPlaceholderText("nome completo")
        self.combo_novo_perfil = QComboBox()
        self.campo_senha = QLineEdit()
        self.campo_senha.setEchoMode(QLineEdit.EchoMode.Password)
        self.campo_senha.setPlaceholderText("mínimo e variedade conforme a política")
        self.campo_senha2 = QLineEdit()
        self.campo_senha2.setEchoMode(QLineEdit.EchoMode.Password)
        self.botao_criar = QPushButton("Criar usuário")
        self.botao_criar.clicked.connect(self._criar)
        formulario.addRow("Login", self.campo_login)
        formulario.addRow("Nome", self.campo_nome)
        formulario.addRow("Perfil", self.combo_novo_perfil)
        formulario.addRow("Senha inicial", self.campo_senha)
        formulario.addRow("Confirmar senha", self.campo_senha2)
        formulario.addRow("", self.botao_criar)
        layout.addWidget(grupo)

        self.mensagem = Mensagem()
        layout.addWidget(self.mensagem)

        self._preencher_perfis()
        self.atualizar()

    def _preencher_perfis(self) -> None:
        self.combo_novo_perfil.clear()
        self.combo_perfil.clear()
        for perfil in self.servico.perfis_disponiveis(self.usuario):
            self.combo_novo_perfil.addItem(f"{perfil.rotulo} (nível {perfil.nivel})", perfil.value)
            self.combo_perfil.addItem(f"{perfil.rotulo} (nível {perfil.nivel})", perfil.value)
        if self.combo_novo_perfil.count() == 0:
            self.botao_criar.setEnabled(False)
            self.combo_perfil.setEnabled(False)
            self.botao_perfil.setEnabled(False)

    def atualizar(self) -> None:
        try:
            usuarios = self.servico.listar(self.usuario)
        except Exception as exc:
            self.mensagem.erro(descrever_erro(exc))
            return
        self._usuarios: list[UsuarioResumo] = usuarios
        self.tabela.setRowCount(len(usuarios))
        for linha, resumo in enumerate(usuarios):
            valores = [
                resumo.nome,
                resumo.login,
                f"{resumo.perfil_rotulo} (nível {resumo.perfil.nivel})",
                "ativo" if resumo.ativo else "desativado",
                f"{resumo.permissoes} ações",
                resumo.criado_em[:10],
            ]
            for coluna, texto in enumerate(valores):
                celula = QTableWidgetItem(texto)
                if coluna == 3:
                    celula.setForeground(
                        Qt.GlobalColor.darkGreen if resumo.ativo else Qt.GlobalColor.darkRed
                    )
                self.tabela.setItem(linha, coluna, celula)
        if usuarios:
            self.tabela.selectRow(0)
        self._selecionado()

    def _selecionado(self) -> None:
        resumo = self._resumo_selecionado()
        ativo = resumo is not None
        for botao in (self.botao_ativar, self.botao_desativar, self.botao_senha):
            botao.setEnabled(ativo)
        if resumo is not None:
            posicao = self.combo_perfil.findData(resumo.perfil.value)
            if posicao >= 0:
                self.combo_perfil.setCurrentIndex(posicao)

    def _resumo_selecionado(self) -> UsuarioResumo | None:
        linha = self.tabela.currentRow()
        if linha < 0 or linha >= len(self._usuarios):
            return None
        return self._usuarios[linha]

    # -- ações --------------------------------------------------------------
    def _criar(self) -> None:
        if self.campo_senha.text() != self.campo_senha2.text():
            self.mensagem.erro("As senhas não conferem.")
            return
        perfil = Perfil(str(self.combo_novo_perfil.currentData()))
        try:
            criado = self.servico.criar(
                self.usuario,
                login=self.campo_login.text(),
                nome=self.campo_nome.text(),
                perfil=perfil,
                senha=self.campo_senha.text(),
            )
        except Exception as exc:
            self.mensagem.erro(descrever_erro(exc))
            return
        for campo in (self.campo_login, self.campo_nome, self.campo_senha, self.campo_senha2):
            campo.clear()
        self.mensagem.ok(
            f"Usuário {criado.login} criado como {criado.perfil.rotulo}. "
            "Entregue a senha inicial e peça a troca no primeiro acesso."
        )
        self.atualizar()
        self.usuarios_alterados.emit()

    def _aplicar_perfil(self) -> None:
        resumo = self._resumo_selecionado()
        if resumo is None:
            return
        perfil = Perfil(str(self.combo_perfil.currentData()))
        try:
            self.servico.alterar_perfil(self.usuario, resumo.id, perfil)
        except Exception as exc:
            self.mensagem.erro(descrever_erro(exc))
            return
        self.mensagem.ok(f"Perfil de {resumo.nome} agora é {perfil.rotulo}.")
        self.atualizar()
        self.usuarios_alterados.emit()

    def _ativar(self) -> None:
        self._mudar_ativo(True)

    def _desativar(self) -> None:
        self._mudar_ativo(False)

    def _mudar_ativo(self, ativo: bool) -> None:
        resumo = self._resumo_selecionado()
        if resumo is None:
            return
        try:
            self.servico.definir_ativo(self.usuario, resumo.id, ativo)
        except Exception as exc:
            self.mensagem.erro(descrever_erro(exc))
            return
        self.mensagem.ok(
            f"{resumo.nome} {'reativado' if ativo else 'desativado'}. "
            "O histórico do usuário permanece intacto."
        )
        self.atualizar()
        self.usuarios_alterados.emit()

    def _redefinir_senha(self) -> None:
        resumo = self._resumo_selecionado()
        if resumo is None:
            return
        senha, ok = QInputDialog.getText(
            self,
            "Redefinir senha",
            f"Nova senha para {resumo.nome}:",
            QLineEdit.EchoMode.Password,
        )
        if not ok or not senha:
            return
        try:
            self.servico.redefinir_senha(self.usuario, resumo.id, senha)
        except Exception as exc:
            self.mensagem.erro(descrever_erro(exc))
            return
        self.mensagem.ok(
            f"Senha de {resumo.nome} redefinida. Informe a nova senha e exija a troca."
        )

    def _transferir(self) -> None:
        resumo = self._resumo_selecionado()
        if resumo is None:
            self.mensagem.alerta("Selecione quem receberá a propriedade da instalação.")
            return
        senha, ok = QInputDialog.getText(
            self,
            "Transferir propriedade",
            f"Confirme SUA senha de Admin Master para passar a propriedade a {resumo.nome}:",
            QLineEdit.EchoMode.Password,
        )
        if not ok or not senha:
            return
        try:
            anterior, novo = self.servico.transferir_propriedade(
                self.usuario, usuario_id=resumo.id, senha_do_ator=senha
            )
        except Exception as exc:
            self.mensagem.erro(descrever_erro(exc))
            return
        self.mensagem.alerta(
            f"Propriedade transferida: {novo.login} é o novo Admin Master e "
            f"{anterior.login} passou a Admin. Feche e reabra a sessão."
        )
        self.atualizar()
        self.usuarios_alterados.emit()


class SecaoPermissoes(QWidget):
    permissoes_alteradas = Signal()

    def __init__(self, contexto: Contexto, usuario: Usuario, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = contexto
        self.usuario = usuario
        self.servico = ServicoPermissoes(contexto)
        self.editavel = usuario.pode(Acao.PERMISSAO_GERENCIAR)

        layout = QVBoxLayout(self)
        ajuda = QLabel(
            "Marque o que cada perfil pode fazer. O Admin Master tem acesso integral e não "
            "aparece como opção — é garantia de código, não configuração. "
            "Conceder/revogar permissão é exclusivo do master."
        )
        ajuda.setWordWrap(True)
        ajuda.setObjectName("textoAjuda")
        layout.addWidget(ajuda)

        self.tabela = QTableWidget(0, 1 + len(Perfil))
        cabecalhos = ["Permissão"] + [
            f"{perfil.rotulo}\nnível {perfil.nivel}" for perfil in Perfil
        ]
        self.tabela.setHorizontalHeaderLabels(cabecalhos)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        cabecalho = self.tabela.horizontalHeader()
        cabecalho.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for coluna in range(1, 1 + len(Perfil)):
            cabecalho.setSectionResizeMode(coluna, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.tabela, 1)

        botoes = FluxoDeAcoes()
        self.botao_salvar = QPushButton("Salvar matriz")
        self.botao_salvar.clicked.connect(self._salvar)
        self.botao_padrao = QPushButton("Restaurar padrão")
        self.botao_padrao.setObjectName("secundario")
        self.botao_padrao.clicked.connect(self._restaurar)
        self.rotulo_excecoes = QLabel("")
        self.rotulo_excecoes.setObjectName("textoAjuda")
        botoes.adicionar(self.botao_salvar)
        botoes.adicionar(self.botao_padrao)
        botoes.adicionar(self.rotulo_excecoes)
        layout.addWidget(botoes)

        self.mensagem = Mensagem()
        layout.addWidget(self.mensagem)

        if not self.editavel:
            self.botao_salvar.setEnabled(False)
            self.botao_padrao.setEnabled(False)
            self.mensagem.alerta(
                "Somente o Admin Master altera a matriz. Você pode consultá-la."
            )
        self.atualizar()

    def atualizar(self) -> None:
        matriz = self.servico.matriz()
        linhas: list[tuple[str, Acao | None]] = []
        for categoria, acoes in acoes_por_categoria().items():
            linhas.append((categoria.rotulo, None))
            linhas.extend((acao.rotulo, acao) for acao in acoes)
        self.tabela.setRowCount(len(linhas))
        self._caixas: dict[tuple[Perfil, Acao], QCheckBox] = {}
        for indice, (rotulo, acao) in enumerate(linhas):
            celula = QTableWidgetItem(rotulo)
            if acao is None:
                celula.setText(f"— {rotulo} —")
                fonte = celula.font()
                fonte.setBold(True)
                celula.setFont(fonte)
                celula.setBackground(Qt.GlobalColor.lightGray)
            else:
                celula.setToolTip(acao.value)
            self.tabela.setItem(indice, 0, celula)
            for coluna, perfil in enumerate(Perfil, start=1):
                if acao is None:
                    vazio = QTableWidgetItem("")
                    vazio.setBackground(Qt.GlobalColor.lightGray)
                    self.tabela.setItem(indice, coluna, vazio)
                    continue
                caixa = QCheckBox()
                concedida = matriz[perfil][acao]
                caixa.setChecked(concedida)
                if perfil.eh_master:
                    caixa.setEnabled(False)
                    caixa.setToolTip("Acesso integral por definição; não é configurável.")
                else:
                    caixa.setEnabled(self.editavel)
                self.tabela.setCellWidget(indice, coluna, caixa)
                self._caixas[(perfil, acao)] = caixa
        excecoes = self.servico.excecoes()
        self.rotulo_excecoes.setText(
            "Sem exceções: a matriz em uso é a de fábrica."
            if not excecoes
            else f"{len(excecoes)} exceção(ões) em vigor (auditadas)."
        )

    def _mudancas(self) -> dict[tuple[Perfil, Acao], bool]:
        matriz = self.servico.matriz()
        mudancas: dict[tuple[Perfil, Acao], bool] = {}
        for (perfil, acao), caixa in self._caixas.items():
            if perfil.eh_master:
                continue
            if caixa.isChecked() != matriz[perfil][acao]:
                mudancas[(perfil, acao)] = caixa.isChecked()
        return mudancas

    def _salvar(self) -> None:
        mudancas = self._mudancas()
        if not mudancas:
            self.mensagem.alerta("Nada mudou na matriz.")
            return
        try:
            aplicadas = self.servico.aplicar(self.usuario, mudancas)
        except Exception as exc:
            self.mensagem.erro(descrever_erro(exc))
            return
        self.mensagem.ok(
            f"{len(aplicadas)} permissão(ões) atualizada(s) e registrada(s) na auditoria. "
            "O efeito vale já no próximo login do usuário afetado."
        )
        self.atualizar()
        self.permissoes_alteradas.emit()

    def _restaurar(self) -> None:
        try:
            removidas = self.servico.restaurar_padrao(self.usuario)
        except Exception as exc:
            self.mensagem.erro(descrever_erro(exc))
            return
        self.mensagem.ok(f"Matriz padrão restaurada ({removidas} exceção(ões) removida(s)).")
        self.atualizar()
        self.permissoes_alteradas.emit()
