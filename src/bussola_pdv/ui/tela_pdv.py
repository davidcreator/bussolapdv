"""Frente de caixa: carrinho, descontos, pagamentos divididos e finalização."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..aplicacao.contexto import Contexto
from ..aplicacao.pdv import ResultadoVenda, ServicoPDV, SolicitacaoVenda
from ..dominio.dinheiro import Dinheiro, Quantidade
from ..dominio.erros import (
    AutorizacaoNegada,
    ErroBussola,
    EstoqueInsuficiente,
    TurnoNaoAberto,
)
from ..dominio.pagamentos import (
    FormaPagamento,
    PlanoPagamento,
    pagamento_a_prazo,
    pagamento_dinheiro,
    pagamento_eletronico,
)
from ..dominio.usuario import Acao, Usuario
from ..dominio.venda import Carrinho, TotaisVenda
from ..infra.sqlite.repositorio_caixa import TurnoRegistrado
from .login import DialogoAutorizacao

COLUNAS = ["Código", "Descrição", "Qtd", "Un.", "Preço", "Desc.", "Total"]
COLUNAS_PAGAMENTO = [
    FormaPagamento.DINHEIRO,
    FormaPagamento.PIX,
    FormaPagamento.DEBITO,
    FormaPagamento.CREDITO,
    FormaPagamento.CREDITO_PARCELADO,
    FormaPagamento.TRANSFERENCIA,
    FormaPagamento.VALE,
    FormaPagamento.CHEQUE,
    FormaPagamento.A_PRAZO,
]


class TelaPDV(QWidget):
    solicitar_caixa = Signal()
    venda_finalizada = Signal()

    def __init__(self, contexto: Contexto, usuario: Usuario, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = contexto
        self.usuario = usuario
        self.servico = ServicoPDV(contexto)
        self.carrinho = Carrinho()
        self._montar_interface()
        self._atalhos()
        self.atualizar()

    # -- interface ----------------------------------------------------------
    def _montar_interface(self) -> None:
        layout = QVBoxLayout(self)

        self.rotulo_turno = QLabel()
        self.rotulo_turno.setObjectName("textoAjuda")
        self.mensagem = QLabel("")
        self.mensagem.setWordWrap(True)

        # 01 — identificação
        grupo_ident = QGroupBox("01 · Identifique a venda")
        linha_ident = QHBoxLayout(grupo_ident)
        self.rotulo_operador = QLabel()
        self.campo_cliente = QLineEdit()
        self.campo_cliente.setPlaceholderText("cliente (opcional; obrigatório no crediário)")
        self.botao_buscar_cliente = QPushButton("Buscar cliente")
        self.botao_buscar_cliente.setObjectName("secundario")
        self.botao_buscar_cliente.clicked.connect(self._buscar_cliente)
        linha_ident.addWidget(self.rotulo_operador)
        linha_ident.addSpacing(12)
        linha_ident.addWidget(self.campo_cliente)
        linha_ident.addWidget(self.botao_buscar_cliente)

        # 02 — itens
        grupo_itens = QGroupBox("02 · Lance produtos (F2 no código · Enter adiciona · Del remove)")
        layout_itens = QVBoxLayout(grupo_itens)
        linha_codigo = QHBoxLayout()
        self.campo_codigo = QLineEdit()
        self.campo_codigo.setPlaceholderText("código interno ou código de barras")
        self.campo_codigo.returnPressed.connect(self._adicionar_item)
        self.campo_quantidade = QLineEdit("1")
        self.campo_quantidade.setFixedWidth(80)
        self.campo_quantidade.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.campo_quantidade.returnPressed.connect(self._adicionar_item)
        self.botao_adicionar = QPushButton("Adicionar")
        self.botao_adicionar.clicked.connect(self._adicionar_item)
        linha_codigo.addWidget(QLabel("Código:"))
        linha_codigo.addWidget(self.campo_codigo, 1)
        linha_codigo.addWidget(QLabel("Qtd:"))
        linha_codigo.addWidget(self.campo_quantidade)
        linha_codigo.addWidget(self.botao_adicionar)

        self.tabela = QTableWidget(0, len(COLUNAS))
        self.tabela.setHorizontalHeaderLabels(COLUNAS)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setAlternatingRowColors(True)
        self.tabela.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabela.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tabela.setMinimumHeight(200)

        layout_itens.addLayout(linha_codigo)
        layout_itens.addWidget(self.tabela)

        # 03 — pagamentos
        grupo_pagamento = QGroupBox("03 · Pagamento (até três formas)")
        layout_pagamento = QVBoxLayout(grupo_pagamento)
        self.linhas_pagamento: list[tuple[QComboBox, QLineEdit]] = []
        self._pagamento_manual = False
        for _ in range(3):
            linha = QHBoxLayout()
            forma = QComboBox()
            for item in COLUNAS_PAGAMENTO:
                forma.addItem(item.rotulo, item)
            valor = QLineEdit()
            valor.setPlaceholderText("valor")
            valor.setAlignment(Qt.AlignmentFlag.AlignRight)
            valor.textChanged.connect(self._atualizar_troco)
            valor.textEdited.connect(self._marcar_edicao_manual)
            linha.addWidget(QLabel("Forma:"))
            linha.addWidget(forma, 1)
            linha.addWidget(QLabel("Valor:"))
            linha.addWidget(valor, 1)
            layout_pagamento.addLayout(linha)
            self.linhas_pagamento.append((forma, valor))

        self.rotulo_troco = QLabel("Troco: R$ 0,00")
        self.rotulo_troco.setObjectName("mensagemAlerta")
        layout_pagamento.addWidget(self.rotulo_troco)

        # 04 — finalização
        grupo_final = QGroupBox("04 · Finalizar")
        layout_final = QHBoxLayout(grupo_final)
        self.rotulo_total = QLabel("R$ 0,00")
        self.rotulo_total.setObjectName("totalCupom")
        self.rotulo_total.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.botao_limpar = QPushButton("Cancelar cupom (F6)")
        self.botao_limpar.setObjectName("secundario")
        self.botao_limpar.clicked.connect(self._limpar)
        self.botao_finalizar = QPushButton("Finalizar venda (F4)")
        self.botao_finalizar.clicked.connect(self._finalizar)
        layout_final.addWidget(self.rotulo_total, 1)
        layout_final.addWidget(self.botao_limpar)
        layout_final.addWidget(self.botao_finalizar)

        layout.addWidget(self.rotulo_turno)
        layout.addWidget(self.mensagem)
        layout.addWidget(grupo_ident)
        layout.addWidget(grupo_itens, 1)
        layout.addWidget(grupo_pagamento)
        layout.addWidget(grupo_final)

    def _atalhos(self) -> None:
        def ligar(tecla: str, alvo: QWidget, funcao: Callable[[], None]) -> None:
            atalho = QShortcut(QKeySequence(tecla), alvo)
            atalho.activated.connect(funcao)

        ligar("F2", self, lambda: self.campo_codigo.setFocus())
        ligar("F4", self, self._finalizar)
        ligar("F6", self, self._limpar)
        ligar("Delete", self.tabela, self._remover_selecionado)
        ligar("Escape", self, lambda: self._mensagem(""))

    # -- estado -------------------------------------------------------------
    def atualizar(self) -> None:
        self.rotulo_operador.setText(
            f"Operador: <b>{self.usuario.nome}</b> ({self.usuario.perfil.rotulo})"
        )
        caixa = self._caixa_e_turno()
        if caixa is None:
            self.rotulo_turno.setText(
                "⚠ Nenhum turno aberto. Abra o caixa antes de vender (módulo Caixa)."
            )
            self.rotulo_turno.setObjectName("mensagemErro")
            self.botao_finalizar.setEnabled(False)
        else:
            _, turno = caixa
            self.rotulo_turno.setText(
                f"Caixa aberto · turno {turno.id[:8]} · fundo {turno.fundo.formatado()} · "
                f"data de negócio {self.ctx.relogio.data_negocio()}"
            )
            self.rotulo_turno.setObjectName("textoAjuda")
            self.botao_finalizar.setEnabled(True)
        self.rotulo_turno.style().unpolish(self.rotulo_turno)
        self.rotulo_turno.style().polish(self.rotulo_turno)

    def _caixa_e_turno(self) -> tuple[str, TurnoRegistrado] | None:
        for caixa in self.ctx.caixas.listar_caixas():
            turno = self.ctx.caixas.turno_aberto(caixa["id"])
            if turno is not None:
                return caixa["id"], turno
        return None

    def _mensagem(self, texto: str, tipo: str = "alerta") -> None:
        self.mensagem.setText(texto)
        nomes = {"alerta": "mensagemAlerta", "erro": "mensagemErro", "ok": "mensagemOk"}
        self.mensagem.setObjectName(nomes[tipo])
        self.mensagem.style().unpolish(self.mensagem)
        self.mensagem.style().polish(self.mensagem)

    # -- carrinho -----------------------------------------------------------
    def _adicionar_item(self) -> None:
        entrada = self.campo_codigo.text().strip()
        if not entrada:
            self.campo_codigo.setFocus()
            return
        try:
            produto = self.ctx.produtos.buscar_leitura(entrada)
            if not produto.ativo:
                raise ErroBussola(f"Produto {produto.codigo} está inativo.")
            quantidade = self.campo_quantidade.text().strip() or "1"
            self.carrinho.adicionar(produto, quantidade)
            saldo = self.ctx.produtos.saldos([produto.id]).get(produto.id, 0)
            saldo_texto = Quantidade(saldo).formatada()
            if saldo <= 0:
                self._mensagem(
                    f"Atenção: {produto.descricao} está em ruptura de estoque.", "alerta"
                )
            else:
                self._mensagem(
                    f"Item incluído: {produto.descricao} · saldo {saldo_texto} {produto.unidade.value}.", "ok"
                )
        except ErroBussola as exc:
            self._mensagem(str(exc), "erro")
            return
        self.campo_codigo.clear()
        self.campo_quantidade.setText("1")
        self.campo_codigo.setFocus()
        self._redesenhar_carrinho()

    def _remover_selecionado(self) -> None:
        linha = self.tabela.currentRow()
        if linha < 0 or linha >= len(self.carrinho.itens):
            return
        item = self.carrinho.itens[linha]
        self.carrinho.remover(item.produto_id)
        self._redesenhar_carrinho()

    def _limpar(self) -> None:
        self.carrinho.limpar()
        self._pagamento_manual = False
        for _, valor in self.linhas_pagamento:
            valor.clear()
        self._redesenhar_carrinho()
        self._mensagem("Cupom limpo. Nada foi gravado.", "ok")

    def _redesenhar_carrinho(self) -> None:
        itens = self.carrinho.itens
        self.tabela.setRowCount(len(itens))
        for linha, item in enumerate(itens):
            valores = [
                item.codigo,
                item.descricao,
                item.quantidade.formatada(),
                item.unidade.value,
                item.preco_unitario.formatado(),
                item.desconto.formatado() if item.desconto.centavos else "—",
                item.total.formatado(),
            ]
            for coluna, texto in enumerate(valores):
                celula = QTableWidgetItem(texto)
                if coluna >= 2:
                    celula.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.tabela.setItem(linha, coluna, celula)
        self._atualizar_totais()

    def _totais(self) -> TotaisVenda | None:
        if self.carrinho.vazio:
            return None
        return self.carrinho.totais()

    def _marcar_edicao_manual(self, _texto: str) -> None:
        self._pagamento_manual = True

    def _atualizar_totais(self) -> None:
        totais = self._totais()
        total = totais.total if totais else Dinheiro.zero()
        self.rotulo_total.setText(total.formatado())
        primeiro = self.linhas_pagamento[0][1]
        if not self.carrinho.vazio and not self._pagamento_manual:
            primeiro.blockSignals(True)
            primeiro.setText(total.formatado())
            primeiro.blockSignals(False)
        self._atualizar_troco()

    def _atualizar_troco(self) -> None:
        totais = self._totais()
        if totais is None:
            self.rotulo_troco.setText("Troco: R$ 0,00")
            return
        try:
            plano, _ = self._montar_plano(totais.total, permitir_incompleto=True)
        except ErroBussola as exc:
            self.rotulo_troco.setText(f"Atenção: {exc}")
            return
        aplicado = plano.total_aplicado if plano else Dinheiro.zero()
        troco = plano.troco if plano else Dinheiro.zero()
        falta = totais.total - aplicado
        if falta.centavos > 0:
            self.rotulo_troco.setText(f"Falta {falta.formatado()}")
        elif troco.centavos > 0:
            self.rotulo_troco.setText(f"Troco {troco.formatado()}")
        else:
            self.rotulo_troco.setText("Pagamento completo")

    def _montar_plano(
        self, total: Dinheiro, *, permitir_incompleto: bool = False
    ) -> tuple[PlanoPagamento | None, str]:
        pagamentos = []
        erros = []
        for combo, campo in self.linhas_pagamento:
            texto = campo.text().strip()
            if not texto:
                continue
            try:
                valor = Dinheiro.de_texto(texto)
            except ErroBussola:
                erros.append(f"Valor inválido: {texto!r}")
                continue
            if valor.centavos == 0:
                continue
            # Qt devolve o StrEnum como str; reconvertemos para o enum tipado.
            forma = FormaPagamento(combo.currentData())
            try:
                if forma is FormaPagamento.DINHEIRO:
                    pagamentos.append(pagamento_dinheiro(valor, valor))
                elif forma is FormaPagamento.A_PRAZO:
                    pagamentos.append(pagamento_a_prazo(valor))
                else:
                    pagamentos.append(pagamento_eletronico(forma, valor))
            except ErroBussola as exc:
                erros.append(str(exc))
        if erros:
            raise ErroBussola("; ".join(erros))
        if not pagamentos:
            return None, ""
        plano = PlanoPagamento(tuple(pagamentos))
        if permitir_incompleto:
            return plano, ""
        plano.validar_contra(total)
        return plano, ""

    # -- finalização --------------------------------------------------------
    def _finalizar(self) -> None:
        if not self.carrinho.itens:
            self._mensagem("Carrinho vazio: lance ao menos um item.", "erro")
            return
        alvo = self._caixa_e_turno()
        if alvo is None:
            self._mensagem("Abra o caixa antes de finalizar a venda.", "erro")
            self.solicitar_caixa.emit()
            return
        caixa_id, _ = alvo
        totais = self.carrinho.totais()

        try:
            plano, _ = self._montar_plano(totais.total)
        except ErroBussola as exc:
            self._mensagem(str(exc), "erro")
            return
        if plano is None:
            self._mensagem("Informe ao menos uma forma de pagamento.", "erro")
            return

        cliente_id = self._cliente_selecionado()
        parcelas = 1
        if any(p.forma is FormaPagamento.A_PRAZO for p in plano.pagamentos):
            if not cliente_id:
                self._mensagem("Venda a prazo exige cliente identificado.", "erro")
                return
            quantidade = self._perguntar_parcelas()
            if quantidade is None:
                return
            parcelas = quantidade

        autorizador = None
        for tentativa in range(2):
            try:
                resultado = self.servico.finalizar_venda(
                    SolicitacaoVenda(
                        operador=self.usuario,
                        caixa_id=caixa_id,
                        carrinho=self.carrinho,
                        plano=plano,
                        cliente_id=cliente_id,
                        autorizador=autorizador,
                        parcelas_crediario=parcelas,
                    )
                )
            except AutorizacaoNegada as exc:
                if tentativa == 1:
                    self._mensagem(str(exc), "erro")
                    return
                dialogo = DialogoAutorizacao(self.ctx, Acao.PDV_DESCONTO_EXCEPCIONAL, str(exc), self)
                if dialogo.exec() != dialogo.DialogCode.Accepted:
                    self._mensagem("Venda não finalizada: autorização cancelada.", "alerta")
                    return
                autorizador = dialogo.autorizador
                continue
            except TurnoNaoAberto as exc:
                self._mensagem(str(exc), "erro")
                self.solicitar_caixa.emit()
                return
            except EstoqueInsuficiente as exc:
                self._mensagem(str(exc), "erro")
                return
            except ErroBussola as exc:
                self._mensagem(str(exc), "erro")
                return
            else:
                self._mostrar_comprovante(resultado)
                self._limpar()
                self._atualizar_totais()
                self.atualizar()
                self.venda_finalizada.emit()
                return

    def _mostrar_comprovante(self, resultado: ResultadoVenda) -> None:
        venda = resultado.venda
        linhas = [
            f"<b>Venda {venda.rotulo}</b>",
            f"Total: <b>{venda.total.formatado()}</b>",
        ]
        if resultado.plano.troco.centavos:
            linhas.append(f"Troco: {resultado.plano.troco.formatado()}")
        if resultado.titulos:
            linhas.append(f"Crediário: {len(resultado.titulos)} título(s) gerado(s)")
        for aviso in resultado.avisos:
            linhas.append(f"⚠ {aviso}")
        linhas.append(
            "<br><span style='color:#5A5A5A'>Comprovante interno. Não é documento fiscal. "
            "Pagamentos eletrônicos pendentes exigem confirmação no procedimento da loja.</span>"
        )
        QMessageBox.information(self, "Venda registrada", "<br>".join(linhas))

    def _perguntar_parcelas(self) -> int | None:
        from PySide6.QtWidgets import QInputDialog

        maximo = self.ctx.parametros.obter_int("crediario.maximo_parcelas")
        quantidade, ok = QInputDialog.getInt(self, "Crediário", "Número de parcelas:", 1, 1, maximo)
        return quantidade if ok else None

    def _buscar_cliente(self) -> None:
        from PySide6.QtWidgets import QInputDialog

        termo, ok = QInputDialog.getText(self, "Buscar cliente", "Nome ou documento:")
        if not ok or not termo.strip():
            return
        encontrados = self.ctx.clientes.listar(busca=termo.strip(), limite=10)
        if not encontrados:
            self._mensagem("Nenhum cliente encontrado.", "alerta")
            return
        cliente = encontrados[0]
        self.campo_cliente.setText(cliente.nome)
        self.campo_cliente.setProperty("cliente_id", cliente.id)
        limite = Dinheiro(cliente.limite_credito).formatado()
        self._mensagem(f"Cliente: {cliente.nome} · limite {limite}", "ok")

    def _cliente_selecionado(self) -> str | None:
        return self.campo_cliente.property("cliente_id")
