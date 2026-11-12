"""Primeiro uso: cria a instalação (Admin Master + caixa + nome da loja) pela tela.

Quem instala pelo `.exe` não tem terminal: o programa precisa resolver sozinho o
que o `bussola init` faz na linha de comando. Este diálogo aparece só quando o
banco ainda não existe (ou existe sem nenhum usuário) e executa exatamente os
mesmos casos de uso — nada é criado "por fora" da camada de aplicação.
"""

from __future__ import annotations

import sqlite3
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..aplicacao.autenticacao import ServicoAutenticacao
from ..aplicacao.contexto import Contexto
from ..aplicacao.marca import ServicoMarca
from ..caminhos import (
    NOME_BANCO,
    banco_em,
    definir_diretorio_de_dados,
    diretorio_de_dados_padrao,
)
from ..diagnostico import registrar_erro, resumo_do_erro
from ..dominio.erros import ErroBussola, EsquemaAusente
from ..dominio.marca import Marca
from ..dominio.usuario import Perfil, Usuario
from .icones import icone
from .login import _cartao_modal, _faixa, _finalizar_cartao
from .responsivo import ajustar_dialogo
from .tema import tinta_do_botao


def precisa_de_configuracao(caminho: Path) -> bool:
    """Verdadeiro quando ainda não há instalação utilizável no caminho informado."""
    if not caminho.exists():
        return True
    try:
        contexto = Contexto.abrir(caminho)
    except Exception:  # base corrompida: o primeiro uso tenta recomeçar
        return True
    try:
        return not contexto.usuarios.listar()
    except ErroBussola:  # pragma: no cover - esquema antigo sem tabela de usuários
        return True
    finally:
        contexto.fechar()


class DialogoPrimeiroUso(QDialog):
    """Coleta o que o `init` pede no terminal: loja, master e senha."""

    def __init__(
        self, banco: Path, parent: QWidget | None = None, *, pasta_inicial: Path | None = None
    ) -> None:
        super().__init__(parent)
        self.banco = Path(banco)
        self.pasta_inicial = Path(pasta_inicial or self.banco.parent)
        self.usuario: Usuario | None = None
        self.setWindowTitle("Bússola PDV — primeiro uso")
        ajustar_dialogo(self, largura_preferida=560, altura_preferida=760)

        cartao, corpo = _cartao_modal(
            "Esta é a primeira execução: vamos criar a instalação local. O usuário criado "
            "aqui é o <b>Admin Master</b>, proprietário da instalação — ele define o que cada "
            "perfil pode fazer."
        )

        self.campo_loja = QLineEdit("Minha Loja")
        self.campo_loja.setMaxLength(60)
        self.campo_login = QLineEdit("master")
        self.campo_login.setPlaceholderText("usuário do Admin Master")
        self.campo_nome = QLineEdit()
        self.campo_nome.setPlaceholderText("nome completo do responsável")
        self.campo_senha = QLineEdit()
        self.campo_senha.setEchoMode(QLineEdit.EchoMode.Password)
        self.campo_senha.setPlaceholderText("mínimo 8 caracteres, com letras e números")
        self.campo_senha2 = QLineEdit()
        self.campo_senha2.setEchoMode(QLineEdit.EchoMode.Password)
        self.campo_senha2.setPlaceholderText("repita a senha")

        formulario = QFormLayout()
        formulario.setSpacing(8)
        formulario.addRow("Nome da loja", self.campo_loja)
        formulario.addRow("Usuário", self.campo_login)
        formulario.addRow("Nome do responsável", self.campo_nome)
        formulario.addRow("Senha", self.campo_senha)
        formulario.addRow("Confirmar senha", self.campo_senha2)
        corpo.addLayout(formulario)

        self.campo_pasta = QLineEdit(str(self.pasta_inicial))
        self.campo_pasta.setMinimumWidth(240)  # cabe um caminho de unidade inteiro
        self.campo_pasta.setToolTip(
            "Pasta onde ficam a base do PDV, as cópias de segurança, os relatórios e os logs."
        )
        self.campo_pasta.textChanged.connect(self._pasta_alterada)
        self.botao_pasta = QPushButton("Procurar…")
        self.botao_pasta.setObjectName("secundario")
        self.botao_pasta.clicked.connect(self._escolher_pasta)
        linha_pasta = QHBoxLayout()
        linha_pasta.setSpacing(6)
        linha_pasta.addWidget(self.campo_pasta, 1)
        linha_pasta.addWidget(self.botao_pasta)

        formulario.addRow("Pasta dos dados", linha_pasta)
        self.rotulo_padrao = QLabel()
        self.rotulo_padrao.setObjectName("textoAjuda")
        self.rotulo_padrao.setWordWrap(True)
        self.rotulo_padrao.setTextInteractionFlags(
            self.rotulo_padrao.textInteractionFlags()
        )
        self.rotulo_padrao.setOpenExternalLinks(False)
        self.rotulo_padrao.linkActivated.connect(self._voltar_ao_padrao)
        self.pode_voltar_ao_padrao = self.pasta_inicial != diretorio_de_dados_padrao()
        corpo.addWidget(self.rotulo_padrao)

        self.caminho = QLabel()
        self.caminho.setObjectName("textoAjuda")
        self.caminho.setWordWrap(True)
        corpo.addWidget(self.caminho)
        self.campo_pasta.setCursorPosition(0)  # mostra o começo do caminho, não o fim
        self._pasta_alterada()  # prévia do banco, agora que o rótulo existe

        self.mensagem = QLabel("")
        self.mensagem.setObjectName("mensagemErro")
        self.mensagem.setWordWrap(True)
        corpo.addWidget(self.mensagem)

        botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.botao_criar = botoes.button(QDialogButtonBox.StandardButton.Ok)
        self.botao_criar.setText("Criar instalação")
        self.botao_criar.setIcon(icone("saida", tinta_do_botao(self), 16))
        botoes.button(QDialogButtonBox.StandardButton.Cancel).setText("Sair")
        botoes.button(QDialogButtonBox.StandardButton.Cancel).setObjectName("secundario")
        botoes.accepted.connect(self._criar)
        botoes.rejected.connect(self.reject)
        corpo.addWidget(botoes)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        _finalizar_cartao(cartao, corpo, _faixa("Bússola PDV · instalação"), layout)

        self.campo_senha2.returnPressed.connect(self._criar)
        self.campo_nome.setFocus()

    # -- pasta dos dados -----------------------------------------------------
    def pasta_escolhida(self) -> Path:
        """Pasta digitada/escolhida, normalizada (sem criar nada ainda)."""
        texto = self.campo_pasta.text().strip() or str(self.pasta_inicial)
        return Path(texto).expanduser()

    def _pasta_alterada(self) -> None:
        """Atualiza a prévia do banco e a explicação da pasta."""
        if not hasattr(self, "rotulo_padrao"):
            return
        padrao = diretorio_de_dados_padrao()
        escolhida = self.pasta_escolhida()
        if escolhida.resolve() == padrao.resolve():
            self.rotulo_padrao.setText(
                "Pasta padrão do sistema. Pode escolher outra unidade, "
                "por exemplo D:\\PDV ou uma pasta sincronizada."
            )
        else:
            self.rotulo_padrao.setText(
                f"Padrão do sistema: {padrao} — a pasta escolhida acima será gravada "
                "para as próximas execuções."
                + (
                    ' <a href="padrao">usar a pasta padrão</a>'
                    if getattr(self, "pode_voltar_ao_padrao", False)
                    else ""
                )
            )
        self.caminho.setText(
            f"Base do PDV: {escolhida / NOME_BANCO}\n"
            "Cópias, relatórios e logs ficam nas subpastas desta mesma pasta."
        )

    def _escolher_pasta(self) -> None:
        escolhida = QFileDialog.getExistingDirectory(
            self, "Escolha a pasta dos dados do PDV", str(self.pasta_escolhida())
        )
        if escolhida:
            self.campo_pasta.setText(escolhida)

    def _voltar_ao_padrao(self, _link: str = "") -> None:
        self.campo_pasta.setText(str(diretorio_de_dados_padrao()))
        self.campo_pasta.setCursorPosition(0)

    # -- criação -------------------------------------------------------------
    def _validar(self) -> str:
        if not self.campo_loja.text().strip():
            return "Informe o nome da loja."
        if not self.campo_login.text().strip():
            return "Informe o usuário do Admin Master."
        if not self.campo_nome.text().strip():
            return "Informe o nome do responsável."
        if self.campo_senha.text() != self.campo_senha2.text():
            return "As senhas não conferem."
        if not str(self.campo_pasta.text()).strip():
            return "Informe a pasta onde os dados devem ficar."
        return ""

    def _criar(self) -> None:
        """Cria a instalação. **Nunca** falha em silêncio.

        A versão anterior só tratava `ErroBussola`: um `sqlite3.OperationalError`
        (pasta sem permissão, arquivo travado por antivírus, migração ausente em
        instalação incompleta) escapava do slot, o PySide6 imprimia o traceback no
        `stderr` — que o executável do Windows não tem — e o botão parecia morto.
        Agora qualquer erro aparece na tela, com o tipo, e vai para `logs/erros.log`.
        """
        problema = self._validar()
        if problema:
            self.mensagem.setText(problema)
            return

        self.mensagem.setText("")
        self._ocupado(True)
        try:
            pasta = self._preparar_pasta()
            self.banco = banco_em(pasta)
            contexto, recomeco = self._abrir_ou_recomecar(self.banco)
            try:
                master = ServicoAutenticacao(contexto).criar_usuario(
                    login=self.campo_login.text().strip(),
                    nome=self.campo_nome.text().strip(),
                    senha=self.campo_senha.text(),
                    perfil=Perfil.ADMIN_MASTER,
                    criar_admin_inicial=True,
                )
                contexto.caixas.garantir_caixa("Caixa 1", criado_em=contexto.agora().isoformat())
                ServicoMarca(contexto).salvar(
                    master, Marca(nome_fantasia=self.campo_loja.text().strip())
                )
                self.usuario = contexto.usuarios.por_id(master.id)
            finally:
                contexto.fechar()
            if recomeco:
                self.mensagem.setText(recomeco)
        except ErroBussola as exc:
            self.mensagem.setText(str(exc))
            self._ocupado(False)
            return
        except Exception as exc:  # a tela é a última linha de defesa
            log = registrar_erro(exc, contexto="primeiro uso: criar instalação")
            self.mensagem.setText(
                f"Não foi possível criar a instalação: {resumo_do_erro(exc)}\n"
                f"Detalhes em: {log}\n"
                "Tente outra pasta de dados ou avise o suporte."
            )
            self._ocupado(False)
            return
        self._ocupado(False)
        self.accept()

    # -- apoio ---------------------------------------------------------------
    def _ocupado(self, estado: bool) -> None:
        """Feedback visível: criar usuário com Argon2 leva ~1 s e não pode parecer travado."""
        self.botao_criar.setEnabled(not estado)
        self.botao_criar.setText("Criando instalação…" if estado else "Criar instalação")
        if QApplication.instance() is not None:
            QApplication.processEvents()  # o rótulo tem de aparecer ANTES do trabalho

    @classmethod
    def _abrir_ou_recomecar(cls, banco: Path) -> tuple[Contexto, str]:
        """Abre a base; se ela existe mas é inutilizável, guarda de lado e recomeça.

        É o caso de quem tentou instalar e o programa morreu no meio: sobra um
        arquivo `pdv.db` vazio ou corrompido, e todo novo clique falharia no mesmo
        ponto. O arquivo antigo **não** é apagado — vira `pdv.db.antigo-<data>`,
        ao lado, para quem for investigar.

        Só a base em si autoriza o recomeço (`sqlite3.DatabaseError` ou esquema
        ausente). Qualquer outro erro sobe: na v0.8.1 um `ZoneInfoNotFoundError`
        (Windows sem `tzdata`) era tratado como "banco corrompido", a base boa era
        arrastada para `pdv.db.antigo-…` e o operador via `WinError 32` em vez do
        motivo real.
        """
        try:
            contexto = Contexto.abrir(banco)
        except sqlite3.DatabaseError as exc:  # arquivo não é base, está truncado…
            return cls._recomecar(banco, exc)
        try:
            cls._conferir_esquema(contexto)
        except EsquemaAusente as exc:
            contexto.fechar()
            return cls._recomecar(banco, exc)
        except BaseException:
            contexto.fechar()
            raise
        return contexto, ""

    @classmethod
    def _recomecar(cls, banco: Path, motivo: Exception) -> tuple[Contexto, str]:
        if not banco.exists():
            raise motivo
        guardado = banco.with_name(
            f"{banco.name}.antigo-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        )
        cls._guardar_de_lado(banco, guardado)
        contexto = Contexto.abrir(banco)
        cls._conferir_esquema(contexto)
        return contexto, (
            f"A base anterior não estava utilizável ({resumo_do_erro(motivo)}) e foi "
            f"guardada como {guardado.name}."
        )

    @staticmethod
    def _guardar_de_lado(banco: Path, guardado: Path) -> None:
        """Move a base antiga; no Windows o arquivo pode estar preso por um instante.

        Antivírus e o `-wal`/`-shm` recém-fechados seguram o `rename` por alguns
        milissegundos. Três tentativas resolvem o caso comum; se não resolver, a
        mensagem diz o que fazer em vez de mostrar `[WinError 32]` cru.
        """
        for tentativa in range(3):
            try:
                banco.replace(guardado)
                return
            except PermissionError as exc:
                if tentativa == 2:
                    raise ErroBussola(
                        "A base de dados está aberta em outro programa e não pôde ser "
                        f"movida ({exc}). Feche as outras janelas do Bússola PDV e "
                        "tente de novo."
                    ) from exc
                time.sleep(0.25)

    def _preparar_pasta(self) -> Path:
        """Valida escrita **sempre** e grava a escolha quando ela mudou.

        Testar a gravação antes de abrir o banco transforma o erro seco do SQLite
        ("unable to open database file") em uma frase que o operador entende:
        a pasta não aceita escrita, escolha outra.
        """
        escolhida = self.pasta_escolhida()
        if escolhida.resolve() != self.pasta_inicial.resolve():
            # escolha explícita: `definir_diretorio_de_dados` já testa a escrita
            # e grava o ponteiro para as próximas execuções
            return definir_diretorio_de_dados(escolhida)
        try:
            escolhida.mkdir(parents=True, exist_ok=True)
            teste = escolhida / ".escrita-ok"
            teste.write_text("ok", encoding="utf-8")
            teste.unlink()
        except OSError as exc:
            raise ErroBussola(
                f"Não é possível gravar na pasta {escolhida}: {exc}. "
                "Escolha outra pasta (de preferência fora de Program Files)."
            ) from exc
        return escolhida

    @staticmethod
    def _conferir_esquema(contexto: Contexto) -> None:
        """Base sem as tabelas do projeto = instalação incompleta, não "primeiro uso"."""
        linha = contexto.conexao.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='usuarios'"
        ).fetchone()
        if linha is None:
            raise EsquemaAusente(
                "A base foi aberta, mas o esquema do PDV não foi criado. "
                "Isso costuma indicar instalação incompleta (arquivos de migração "
                "ausentes). Reinstale o programa ou avise o suporte."
            )


__all__ = ["DialogoPrimeiroUso", "precisa_de_configuracao"]
