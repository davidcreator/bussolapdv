"""Diálogos de cadastro e de operação que faltavam na interface.

Quatro coisas que o bazar precisa fazer todo dia não tinham tela: cadastrar e
alterar **produto**, cadastrar e alterar **cliente**, **lançar entrada de
mercadoriae ajustar saldo de estoque**, e **receber parcela do crediário**. O
serviço de aplicação já existia e estava testado — o que faltava era o caminho do
usuário até ele.

Regras que valem para todos os diálogos daqui:

- **a permissão é conferida no serviço**, não no botão: botão desabilitado é
  cortesia, não segurança;
- **o erro aparece na tela** com o texto do domínio ("já existe cliente com este
  documento"), não com um `TypeError`;
- **nada é gravado em duas etapas**: ou a janela confirma e a transação fecha, ou
  nada mudou;
- campos de dinheiro aceitam o que a pessoa digita (``10``, ``10,50``,
  ``R$ 10,50``) e a conversão é a do domínio, não `float`.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..aplicacao.autenticacao import ServicoAutenticacao
from ..aplicacao.clientes import ServicoClientes
from ..aplicacao.contexto import Contexto
from ..aplicacao.crediario import ResultadoRecebimento, ServicoCrediario
from ..aplicacao.estoque import ServicoEstoque
from ..dominio.cliente import Cliente
from ..dominio.dinheiro import Dinheiro, Quantidade
from ..dominio.erros import ErroBussola
from ..dominio.estoque import CriterioRateio, EntradaMercadoria, ItemEntrada
from ..dominio.pagamentos import FormaPagamento
from ..dominio.produto import Produto, Unidade
from ..dominio.usuario import Acao, Usuario
from .admin.comum import Mensagem, descrever_erro
from .login import _cartao_modal, _faixa, _finalizar_cartao
from .responsivo import FluxoDeAcoes, ajustar_dialogo
from .widgets import ajustar_colunas, preparar_tabela

#: Formas aceitas no recebimento de crediário (a prazo viraria dívida da dívida).
FORMAS_RECEBIMENTO = (
    FormaPagamento.DINHEIRO,
    FormaPagamento.PIX,
    FormaPagamento.DEBITO,
    FormaPagamento.CREDITO,
    FormaPagamento.TRANSFERENCIA,
)


def _centavos(texto: str) -> int:
    """Texto do operador em centavos. Vazio é zero; o resto é validado no domínio."""
    if not str(texto).strip():
        return 0
    return Dinheiro.de_texto(texto).centavos


def _moeda(centavos: int) -> str:
    return Dinheiro(centavos).formatado()


def caixa_aberto(contexto: Contexto) -> str:
    """Id do caixa com turno aberto — devolução em dinheiro e recebimento precisam dele."""
    for caixa in contexto.caixas.listar_caixas():
        if contexto.caixas.turno_aberto(caixa["id"]) is not None:
            return str(caixa["id"])
    raise ErroBussola("Abra o caixa antes: sem turno aberto o dinheiro não tem para onde ir.")


class _DialogoBase(QDialog):
    """Casca comum: cartão modal com marca, formulário, faixa de mensagem e botões."""

    def __init__(
        self,
        contexto: Contexto,
        *,
        titulo: str,
        subtitulo: str,
        rotulo_confirmar: str,
        parent: QWidget | None = None,
        largura: int = 560,
    ) -> None:
        super().__init__(parent)
        self.ctx = contexto
        self.setWindowTitle(titulo)
        ajustar_dialogo(self, largura_preferida=largura)

        self.cartao, self.corpo = _cartao_modal(subtitulo)
        self.formulario = QFormLayout()
        self.formulario.setSpacing(8)
        self.corpo.addLayout(self.formulario)

        self.mensagem = Mensagem()
        self.corpo.addWidget(self.mensagem)

        self.botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.botoes.button(QDialogButtonBox.StandardButton.Ok).setText(rotulo_confirmar)
        self.botoes.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        self.botoes.button(QDialogButtonBox.StandardButton.Cancel).setObjectName("secundario")
        self.botoes.accepted.connect(self._confirmar)
        self.botoes.rejected.connect(self.reject)
        self.corpo.addWidget(self.botoes)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        _finalizar_cartao(self.cartao, self.corpo, _faixa(titulo), layout)

    # -- API para as subclasses -------------------------------------------
    def _campo(self, rotulo: str, widget: QWidget) -> QWidget:
        self.formulario.addRow(rotulo, widget)
        return widget

    def _texto(self, rotulo: str, *, dica: str = "", valor: str = "") -> QLineEdit:
        campo = QLineEdit(valor)
        if dica:
            campo.setPlaceholderText(dica)
        self._campo(rotulo, campo)
        return campo

    def _salvar(self) -> None:  # pragma: no cover - sobrescrito
        raise NotImplementedError

    def _confirmar(self) -> None:
        self.mensagem.limpar()
        try:
            self._salvar()
        except ErroBussola as exc:
            self.mensagem.erro(str(exc))
            return
        except Exception as exc:
            self.mensagem.erro(descrever_erro(exc))
            return
        self.accept()


# --------------------------------------------------------------------- produto
class DialogoProduto(_DialogoBase):
    """Novo produto ou alteração de cadastro (preço, custo, mínimo, ponto de pedido)."""

    def __init__(
        self,
        contexto: Contexto,
        usuario: Usuario,
        produto: Produto | None = None,
        parent: QWidget | None = None,
    ) -> None:
        novo = produto is None
        if produto is None:
            subtitulo = "Código curto para digitar no PDV; código de barras é opcional"
        else:
            subtitulo = f"{produto.codigo} · {produto.descricao}"
        super().__init__(
            contexto,
            titulo="Novo produto" if novo else "Alterar produto",
            subtitulo=subtitulo,
            rotulo_confirmar="Cadastrar" if novo else "Salvar",
            parent=parent,
            largura=520,
        )
        self.usuario = usuario
        self.servico = ServicoEstoque(contexto)
        self.produto: Produto | None = None
        self._original = produto

        valor = produto
        self.campo_codigo = self._texto(
            "Código", dica="ex.: A001", valor=valor.codigo if valor else ""
        )
        self.campo_barras = self._texto(
            "Código de barras",
            dica="opcional (EAN)",
            valor=(valor.codigo_barras or "") if valor else "",
        )
        self.campo_descricao = self._texto(
            "Descrição", dica="ex.: Café 500 g", valor=valor.descricao if valor else ""
        )
        self.campo_categoria = self._texto(
            "Categoria", dica="ex.: Mercearia", valor=valor.categoria if valor else ""
        )
        self.combo_unidade = QComboBox()
        for unidade in Unidade:
            self.combo_unidade.addItem(unidade.value, unidade.value)
        if valor is not None:
            self.combo_unidade.setCurrentIndex(self.combo_unidade.findData(valor.unidade.value))
        self._campo("Unidade", self.combo_unidade)

        self.campo_custo = self._texto(
            "Custo", dica="0,00", valor=_moeda(valor.custo) if valor else ""
        )
        self.campo_preco = self._texto(
            "Preço de venda", dica="0,00", valor=_moeda(valor.preco) if valor else ""
        )
        self.campo_minimo = self._texto(
            "Estoque mínimo",
            dica="0",
            valor=Quantidade(valor.estoque_minimo_milesimos).formatada() if valor else "",
        )
        self.campo_ponto = self._texto(
            "Ponto de pedido",
            dica="0",
            valor=Quantidade(valor.ponto_pedido_milesimos).formatada() if valor else "",
        )
        self.campo_fornecedor = self._texto(
            "Fornecedor", dica="opcional", valor=valor.fornecedor if valor else ""
        )
        self.marcar_ativo = QCheckBox("produto ativo (aparece no PDV)")
        self.marcar_ativo.setChecked(valor.ativo if valor else True)
        self.corpo.addWidget(self.marcar_ativo)

        aviso = QLabel(
            "Mínimo e ponto de pedido são <b>em unidades do produto</b> — em quilo, "
            "vale a fração (0,5 = meio quilo)."
        )
        aviso.setObjectName("textoAjuda")
        aviso.setWordWrap(True)
        self.corpo.addWidget(aviso)

    def _quantidade(self, campo: QLineEdit, unidade: Unidade) -> int:
        texto = campo.text().strip()
        if not texto:
            return 0
        return Quantidade.de_unidades(texto, escala=unidade.escala).milesimos

    def _salvar(self) -> None:
        unidade = Unidade(str(self.combo_unidade.currentData()))
        codigo = self.campo_codigo.text().strip()
        descricao = self.campo_descricao.text().strip()
        preco = _centavos(self.campo_preco.text())
        custo = _centavos(self.campo_custo.text())
        categoria = self.campo_categoria.text().strip()
        barras = self.campo_barras.text().strip() or None
        minimo = self._quantidade(self.campo_minimo, unidade)
        ponto = self._quantidade(self.campo_ponto, unidade)
        fornecedor = self.campo_fornecedor.text().strip()
        ativo = self.marcar_ativo.isChecked()

        if self._original is None:
            self.produto = self.servico.criar_produto(
                operador=self.usuario,
                codigo=codigo,
                descricao=descricao,
                preco=preco,
                custo=custo,
                categoria=categoria,
                unidade=unidade.value,
                codigo_barras=barras,
                estoque_minimo=minimo,
                ponto_pedido=ponto,
                fornecedor=fornecedor,
            )
            return
        self.produto = self.servico.alterar_produto(
            operador=self.usuario,
            produto_id=self._original.id,
            codigo=codigo,
            descricao=descricao,
            preco=preco,
            custo=custo,
            categoria=categoria,
            unidade=unidade,
            codigo_barras=barras,
            estoque_minimo_milesimos=minimo,
            ponto_pedido_milesimos=ponto,
            fornecedor=fornecedor,
            ativo=ativo,
        )


# --------------------------------------------------------------------- cliente
class DialogoCliente(_DialogoBase):
    """Novo cliente ou alteração de cadastro, documento e limite de crédito."""

    def __init__(
        self,
        contexto: Contexto,
        usuario: Usuario,
        cliente: Cliente | None = None,
        parent: QWidget | None = None,
    ) -> None:
        novo = cliente is None
        if cliente is None:
            subtitulo = "Nome é obrigatório; documento e limite são opcionais"
        else:
            subtitulo = cliente.nome
        super().__init__(
            contexto,
            titulo="Novo cliente" if novo else "Alterar cliente",
            subtitulo=subtitulo,
            rotulo_confirmar="Cadastrar" if novo else "Salvar",
            parent=parent,
            largura=520,
        )
        self.usuario = usuario
        self.servico = ServicoClientes(contexto)
        self.cliente: Cliente | None = None
        self._original = cliente

        valor = cliente
        self.campo_nome = self._texto(
            "Nome", dica="como você chama essa pessoa", valor=valor.nome if valor else ""
        )
        self.campo_documento = self._texto(
            "CPF ou CNPJ",
            dica="opcional",
            valor=(valor.documento or "") if valor else "",
        )
        self.campo_limite = self._texto(
            "Limite de crédito",
            dica="0,00",
            valor=_moeda(valor.limite_credito) if valor else "",
        )
        self.campo_observacoes = self._texto(
            "Observações", dica="opcional", valor=valor.observacoes if valor else ""
        )
        self.marcar_ativo = QCheckBox("cliente ativo (pode comprar a prazo)")
        self.marcar_ativo.setChecked(valor.ativo if valor else True)
        self.corpo.addWidget(self.marcar_ativo)

    def _salvar(self) -> None:
        limite = _centavos(self.campo_limite.text())
        if self._original is None:
            self.cliente = self.servico.criar_cliente(
                operador=self.usuario,
                nome=self.campo_nome.text(),
                documento=self.campo_documento.text(),
                limite_credito=limite,
                observacoes=self.campo_observacoes.text().strip(),
            )
            return
        self.cliente = self.servico.alterar_cliente(
            operador=self.usuario,
            cliente_id=self._original.id,
            nome=self.campo_nome.text(),
            documento=self.campo_documento.text(),
            limite_credito=limite,
            ativo=self.marcar_ativo.isChecked(),
            observacoes=self.campo_observacoes.text().strip(),
        )


# ------------------------------------------------------------ entrada/estoque
class DialogoEntrada(_DialogoBase):
    """Entrada de mercadoria de fornecedor: uma nota, vários itens, frete rateado."""

    def __init__(self, contexto: Contexto, usuario: Usuario, parent: QWidget | None = None) -> None:
        super().__init__(
            contexto,
            titulo="Entrada de mercadoria",
            subtitulo="Soma ao estoque e atualiza o custo do produto",
            rotulo_confirmar="Registrar entrada",
            parent=parent,
            largura=720,
        )
        self.usuario = usuario
        self.servico = ServicoEstoque(contexto)
        self.itens: list[ItemEntrada] = []
        self.resultado: dict | None = None

        self.campo_fornecedor = self._texto("Fornecedor", dica="nome do fornecedor")
        self.campo_documento = self._texto("Documento", dica="nota, recibo ou romaneio")
        self.campo_frete = self._texto("Frete", dica="0,00")
        self.combo_criterio = QComboBox()
        self.combo_criterio.addItem("Ratear por valor", CriterioRateio.VALOR.value)
        self.combo_criterio.addItem("Ratear por quantidade", CriterioRateio.QUANTIDADE.value)
        self._campo("Rateio do frete", self.combo_criterio)

        # -- item a item ----------------------------------------------------
        self.campo_codigo = self._texto("Produto (código)", dica="código ou código de barras")
        self.campo_quantidade = self._texto("Quantidade", dica="1")
        self.campo_custo = self._texto("Custo unitário", dica="0,00")
        self.botao_adicionar = QPushButton("Adicionar item")
        self.botao_adicionar.setObjectName("secundario")
        self.botao_adicionar.clicked.connect(self._adicionar_item)
        self.corpo.addWidget(self.botao_adicionar)

        self.tabela = QTableWidget(0, 5)
        self.tabela.setHorizontalHeaderLabels(["Código", "Descrição", "Qtd", "Custo", "Subtotal"])
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setMinimumHeight(150)
        preparar_tabela(self.tabela)
        ajustar_colunas(self.tabela, 1)
        self.corpo.addWidget(self.tabela)

        self.rotulo_total = QLabel("Nenhum item lançado")
        self.rotulo_total.setObjectName("cartaoSubtitulo")
        self.corpo.addWidget(self.rotulo_total)

    # -- itens --------------------------------------------------------------
    def _produto(self) -> Produto:
        codigo = self.campo_codigo.text().strip()
        if not codigo:
            raise ErroBussola("Informe o código do produto.")
        return self.ctx.produtos.buscar_leitura(codigo)

    def _adicionar_item(self) -> None:
        self.mensagem.limpar()
        try:
            produto = self._produto()
            quantidade = Quantidade.de_unidades(
                self.campo_quantidade.text().strip() or "1", escala=produto.unidade.escala
            )
            if quantidade.milesimos == 0:
                raise ErroBussola("Quantidade da entrada deve ser maior que zero.")
            custo = _centavos(self.campo_custo.text()) or produto.custo
            item = ItemEntrada(
                produto_id=produto.id,
                codigo=produto.codigo,
                quantidade=quantidade,
                custo_unitario=Dinheiro(custo),
            )
        except ErroBussola as exc:
            self.mensagem.erro(str(exc))
            return
        self.itens.append(item)
        self._pintar_itens()
        for campo in (self.campo_codigo, self.campo_quantidade, self.campo_custo):
            campo.clear()
        self.campo_codigo.setFocus()

    def _pintar_itens(self) -> None:
        self.tabela.setRowCount(len(self.itens))
        total = 0
        for linha, item in enumerate(self.itens):
            subtotal = item.custo_total
            total += subtotal.centavos
            valores = [
                item.codigo,
                self.ctx.produtos.por_id(item.produto_id).descricao,
                item.quantidade.formatada(),
                item.custo_unitario.formatado(),
                subtotal.formatado(),
            ]
            for coluna, texto in enumerate(valores):
                celula = QTableWidgetItem(texto)
                if coluna >= 2:
                    celula.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self.tabela.setItem(linha, coluna, celula)
        self.rotulo_total.setText(
            f"{len(self.itens)} item(ns) · mercadoria {_moeda(total)}"
            if self.itens
            else "Nenhum item lançado"
        )

    def _salvar(self) -> None:
        if not self.itens:
            raise ErroBussola("Adicione ao menos um item antes de registrar a entrada.")
        entrada = EntradaMercadoria(
            fornecedor=self.campo_fornecedor.text().strip(),
            documento=self.campo_documento.text().strip(),
            itens=tuple(self.itens),
            frete=Dinheiro(_centavos(self.campo_frete.text())),
            criterio=CriterioRateio(str(self.combo_criterio.currentData())),
        )
        self.resultado = self.servico.registrar_entrada(operador=self.usuario, entrada=entrada)


class DialogoAjusteEstoque(_DialogoBase):
    """Ajuste de saldo (contagem, perda, correção) com motivo e autorizador."""

    def __init__(self, contexto: Contexto, usuario: Usuario, parent: QWidget | None = None) -> None:
        super().__init__(
            contexto,
            titulo="Ajustar estoque",
            subtitulo="Contagem, perda ou correção — sempre com motivo e autorização",
            rotulo_confirmar="Registrar ajuste",
            parent=parent,
            largura=560,
        )
        self.usuario = usuario
        self.servico = ServicoEstoque(contexto)
        self.novo_saldo: int | None = None

        self.campo_codigo = self._texto("Produto (código)", dica="código ou código de barras")
        self.campo_quantidade = self._texto(
            "Quantidade", dica="use negativo para baixar (ex.: -2)"
        )
        self.campo_motivo = self._texto("Motivo", dica="contagem, avaria, perda…")
        self.campo_login = self._texto("Autorizador (login)", dica="quem autoriza o ajuste")
        self.campo_senha = self._texto("Senha do autorizador")
        self.campo_senha.setEchoMode(QLineEdit.EchoMode.Password)

    def _salvar(self) -> None:
        produto = self.ctx.produtos.buscar_leitura(self.campo_codigo.text().strip())
        servico_auth = ServicoAutenticacao(self.ctx)
        autorizador = servico_auth.autorizar(
            self.campo_login.text().strip(), self.campo_senha.text(), Acao.ESTOQUE_AJUSTAR
        )
        self.novo_saldo = self.servico.ajustar(
            operador=self.usuario,
            autorizador=autorizador,
            produto_id=produto.id,
            quantidade=self.campo_quantidade.text().strip(),
            motivo=self.campo_motivo.text().strip(),
        )


# ------------------------------------------------------------------ crediário
class DialogoRecebimento(_DialogoBase):
    """Recebe parcela do crediário (total ou parcial), exigindo turno aberto."""

    def __init__(
        self,
        contexto: Contexto,
        usuario: Usuario,
        titulo_id: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            contexto,
            titulo="Receber parcela",
            subtitulo="Baixa no crediário; dinheiro entra no turno aberto",
            rotulo_confirmar="Receber",
            parent=parent,
            largura=560,
        )
        self.usuario = usuario
        self.servico = ServicoCrediario(contexto)
        self.resultado: ResultadoRecebimento | None = None

        self.titulos = [
            titulo
            for titulo in self.servico.listar(incluir_pagos=False)
            if int(titulo["saldo_centavos"]) > 0
        ]
        self.combo_titulo = QComboBox()
        for titulo in self.titulos:
            self.combo_titulo.addItem(
                f"{titulo['cliente']} · parcela {titulo['numero_parcela']}/"
                f"{titulo['total_parcelas']} · saldo {_moeda(int(titulo['saldo_centavos']))}",
                titulo["id"],
            )
        self._campo("Título", self.combo_titulo)
        if titulo_id:
            posicao = self.combo_titulo.findData(titulo_id)
            if posicao >= 0:
                self.combo_titulo.setCurrentIndex(posicao)

        self.campo_valor = self._texto("Valor recebido", dica="0,00")
        self.combo_forma = QComboBox()
        for forma in FORMAS_RECEBIMENTO:
            self.combo_forma.addItem(forma.rotulo, forma.value)
        self._campo("Forma", self.combo_forma)
        self.campo_referencia = self._texto(
            "Referência", dica="opcional (comprovante, PIX…)"
        )

        self.combo_titulo.currentIndexChanged.connect(self._preencher_saldo)
        self._preencher_saldo()
        if not self.titulos:
            self.mensagem.alerta("Nenhum título em aberto para receber.")
            self.botoes.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)

    def _titulo_atual(self) -> dict | None:
        posicao = self.combo_titulo.currentIndex()
        return self.titulos[posicao] if 0 <= posicao < len(self.titulos) else None

    def _preencher_saldo(self) -> None:
        titulo = self._titulo_atual()
        if titulo is not None and not self.campo_valor.text().strip():
            self.campo_valor.setText(_moeda(int(titulo["saldo_centavos"])))

    def _caixa_aberto(self) -> str:
        return caixa_aberto(self.ctx)

    def _salvar(self) -> None:
        titulo = self._titulo_atual()
        if titulo is None:
            raise ErroBussola("Selecione um título em aberto.")
        valor = Dinheiro(_centavos(self.campo_valor.text()))
        if valor.centavos <= 0:
            raise ErroBussola("Informe o valor recebido.")
        self.resultado = self.servico.receber(
            titulo_id=str(titulo["id"]),
            valor=valor,
            forma=FormaPagamento(str(self.combo_forma.currentData())),
            operador=self.usuario,
            caixa_id=self._caixa_aberto(),
            referencia=self.campo_referencia.text().strip(),
        )


# ------------------------------------------------------------------- fábrica
def botoes_de_cadastro(rotulos: list[tuple[str, bool]]) -> tuple[QWidget, dict[str, QPushButton]]:
    """Fileira de botões que quebra em linha; devolve o mapa rótulo → botão."""
    fluxo = FluxoDeAcoes()
    botoes: dict[str, QPushButton] = {}
    for rotulo, habilitado in rotulos:
        botao = QPushButton(rotulo)
        botao.setEnabled(habilitado)
        fluxo.adicionar(botao)
        botoes[rotulo] = botao
    return fluxo, botoes


__all__ = [
    "FORMAS_RECEBIMENTO",
    "DialogoAjusteEstoque",
    "DialogoCliente",
    "DialogoEntrada",
    "DialogoProduto",
    "DialogoRecebimento",
    "botoes_de_cadastro",
]
