"""Seção 'Parâmetros': regras de operação que o lojista ajusta sem programar."""

from __future__ import annotations

import contextlib

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...aplicacao.contexto import Contexto
from ...aplicacao.parametros import DefinicaoParametro, ServicoParametros, TipoParametro
from ...dominio.usuario import Acao, Usuario
from ..impressao import SeletorDeImpressoras
from ..responsivo import FluxoDeAcoes
from .comum import Mensagem, descrever_erro


class SecaoParametros(QWidget):
    def __init__(self, contexto: Contexto, usuario: Usuario, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = contexto
        self.usuario = usuario
        self.servico = ServicoParametros(contexto)
        self.editavel = usuario.pode(Acao.PARAMETRO_ALTERAR)
        self.campos: dict[str, QComboBox | QSpinBox | QLineEdit] = {}

        area = QScrollArea(self)
        area.setWidgetResizable(True)
        conteudo = QWidget()
        layout = QVBoxLayout(conteudo)
        ajuda = QLabel(
            "Valores que mudam o comportamento do PDV. Faixas mínimas e máximas são validadas "
            "aqui e no serviço; toda alteração entra na auditoria com valor anterior e novo."
        )
        ajuda.setWordWrap(True)
        ajuda.setObjectName("textoAjuda")
        layout.addWidget(ajuda)

        for grupo, itens in self.servico.grupos().items():
            caixa = QGroupBox(grupo)
            formulario = QFormLayout(caixa)
            for definicao, valor in itens:
                campo = self._campo(definicao, valor)
                campo.setEnabled(self.editavel)
                rotulo = definicao.rotulo + (f" ({definicao.unidade})" if definicao.unidade else "")
                formulario.addRow(rotulo, campo)
                if definicao.ajuda:
                    dica = QLabel(definicao.ajuda)
                    dica.setWordWrap(True)
                    dica.setObjectName("textoAjuda")
                    formulario.addRow("", dica)
            layout.addWidget(caixa)

        botoes = FluxoDeAcoes()
        self.botao_salvar = QPushButton("Salvar parâmetros")
        self.botao_salvar.clicked.connect(self._salvar)
        self.botao_recarregar = QPushButton("Descartar alterações")
        self.botao_recarregar.setObjectName("secundario")
        self.botao_recarregar.clicked.connect(self.atualizar)
        botoes.adicionar(self.botao_salvar)
        botoes.adicionar(self.botao_recarregar)
        layout.addWidget(botoes)

        self.mensagem = Mensagem()
        layout.addWidget(self.mensagem)
        layout.addStretch(1)
        area.setWidget(conteudo)

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.addWidget(area)

        if not self.editavel:
            self.botao_salvar.setEnabled(False)
            self.mensagem.alerta(
                "Seu perfil não altera parâmetros. Peça a permissão ao Admin Master."
            )
        self.atualizar()

    def _campo(
        self, definicao: DefinicaoParametro, valor: str
    ) -> QComboBox | QSpinBox | QLineEdit:
        campo: QComboBox | QSpinBox | QLineEdit
        if definicao.tipo is TipoParametro.OPCAO:
            combo_opcoes = QComboBox()
            for opcao in definicao.opcoes:
                combo_opcoes.addItem(opcao, opcao)
            indice = combo_opcoes.findData(valor.strip().upper())
            combo_opcoes.setCurrentIndex(max(0, indice))
            campo = combo_opcoes
        elif definicao.chave.endswith(".impressora"):
            # Nome de impressora não se digita de memória: a lista vem do sistema e
            # continua editável para o caso de a impressora não aparecer instalada.
            campo = SeletorDeImpressoras(valor, self)
        elif definicao.tipo is TipoParametro.BOOLEANO:
            combo = QComboBox()
            combo.addItem("Sim", "1")
            combo.addItem("Não", "0")
            combo.setCurrentIndex(0 if valor.strip() in {"1", "true", "True", "S", "SIM"} else 1)
            campo = combo
        elif definicao.tipo is TipoParametro.INTEIRO and definicao.maximo is not None:
            spin = QSpinBox()
            spin.setRange(definicao.minimo or 0, definicao.maximo)
            with contextlib.suppress(ValueError):
                spin.setValue(int(valor))
            campo = spin
        else:
            linha = QLineEdit()
            if definicao.tipo is TipoParametro.PERCENTUAL:
                try:
                    linha.setText(f"{int(valor) / 100:.2f}".replace(".", ","))
                except ValueError:
                    linha.setText("0,00")
            else:
                linha.setText(valor)
            campo = linha
        self.campos[definicao.chave] = campo
        return campo

    def _texto_do_campo(self, campo: QComboBox | QSpinBox | QLineEdit) -> str:
        if isinstance(campo, SeletorDeImpressoras):
            return campo.valor()
        if isinstance(campo, QComboBox):
            return str(campo.currentData())
        if isinstance(campo, QSpinBox):
            return str(campo.value())
        return campo.text()

    def atualizar(self) -> None:
        self.servico = ServicoParametros(self.ctx)
        for chave, campo in self.campos.items():
            definicao = next(d for d in self.servico.listar() if d[0].chave == chave)[0]
            valor = self.ctx.parametros.obter(chave)
            if isinstance(campo, SeletorDeImpressoras):
                campo.definir_valor(valor)
            elif isinstance(campo, QComboBox) and definicao.tipo is TipoParametro.OPCAO:
                indice = campo.findData(valor.strip().upper())
                if indice >= 0:
                    campo.setCurrentIndex(indice)
            elif isinstance(campo, QComboBox):
                campo.setCurrentIndex(0 if valor.strip() in {"1", "true", "True", "S", "SIM"} else 1)
            elif isinstance(campo, QSpinBox):
                with contextlib.suppress(ValueError):
                    campo.setValue(int(valor))
            elif isinstance(campo, QLineEdit) and definicao.tipo is TipoParametro.PERCENTUAL:
                try:
                    campo.setText(f"{int(valor) / 100:.2f}".replace(".", ","))
                except ValueError:
                    campo.setText("0,00")
            elif isinstance(campo, QLineEdit):
                campo.setText(valor)

    def _salvar(self) -> None:
        alterados = 0
        erros: list[str] = []
        for chave, campo in self.campos.items():
            texto = self._texto_do_campo(campo)
            try:
                resultado = self.servico.definir(self.usuario, chave, texto)
            except Exception as exc:
                erros.append(descrever_erro(exc))
                continue
            alterados += 1 if resultado["alterado"] else 0
        if erros:
            self.mensagem.erro("Não foi possível salvar: " + " | ".join(erros[:3]))
            return
        if alterados:
            self.mensagem.ok(f"{alterados} parâmetro(s) atualizado(s) e auditado(s).")
        else:
            self.mensagem.alerta("Nenhum parâmetro mudou.")
        self.atualizar()
