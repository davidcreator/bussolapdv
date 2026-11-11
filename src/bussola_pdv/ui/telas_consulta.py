"""Telas de consulta: produtos, vendas, auditoria e fechamento."""

from __future__ import annotations

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QDateEdit,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..aplicacao.contexto import Contexto
from ..aplicacao.relatorios import ServicoRelatorios
from ..dominio.dinheiro import Dinheiro
from ..dominio.erros import ErroBussola
from ..dominio.produto import Produto, StatusEstoque
from ..dominio.usuario import Acao, Usuario
from .login import DialogoAutorizacao


class TelaProdutos(QWidget):
    def __init__(self, contexto: Contexto, usuario: Usuario, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = contexto
        self.usuario = usuario
        layout = QVBoxLayout(self)

        linha = QHBoxLayout()
        self.campo_busca = QLineEdit()
        self.campo_busca.setPlaceholderText("buscar por código, código de barras ou descrição")
        self.campo_busca.textChanged.connect(self.atualizar)
        self.rotulo_resumo = QLabel()
        linha.addWidget(self.campo_busca, 1)
        linha.addWidget(self.rotulo_resumo)

        self.tabela = QTableWidget(0, 8)
        self.tabela.setHorizontalHeaderLabels(
            ["Código", "Descrição", "Categoria", "Un.", "Custo", "Preço", "Saldo", "Estoque"]
        )
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tabela.setAlternatingRowColors(True)

        layout.addLayout(linha)
        layout.addWidget(self.tabela)
        self.atualizar()

    def atualizar(self) -> None:
        busca = self.campo_busca.text() if hasattr(self, "campo_busca") else ""
        produtos = self.ctx.produtos.listar(busca=busca, apenas_ativos=False, limite=1000)
        saldos = self.ctx.produtos.saldos()
        contagem = dict.fromkeys(StatusEstoque, 0)
        self.tabela.setRowCount(len(produtos))
        for linha, produto in enumerate(produtos):
            saldo = saldos.get(produto.id, 0)
            status = _status(produto, saldo)
            if produto.ativo:
                contagem[status] += 1
            valores = [
                produto.codigo,
                produto.descricao,
                produto.categoria,
                produto.unidade.value,
                Dinheiro(produto.custo).formatado(),
                Dinheiro(produto.preco).formatado(),
                _saldo_texto(saldo, produto.unidade.escala),
                status.value if produto.ativo else "INATIVO",
            ]
            for coluna, texto in enumerate(valores):
                celula = QTableWidgetItem(texto)
                if coluna in (4, 5, 6):
                    celula.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if coluna == 7:
                    if status is StatusEstoque.RUPTURA:
                        celula.setForeground(Qt.GlobalColor.darkRed)
                    elif status is StatusEstoque.BAIXO:
                        celula.setForeground(Qt.GlobalColor.darkYellow)
                self.tabela.setItem(linha, coluna, celula)
        self.rotulo_resumo.setText(
            f"Ruptura: {contagem[StatusEstoque.RUPTURA]} · Baixo: {contagem[StatusEstoque.BAIXO]} · "
            f"Reposição: {contagem[StatusEstoque.REPOSICAO]} · OK: {contagem[StatusEstoque.OK]}"
        )


def _status(produto: Produto, saldo: int) -> StatusEstoque:
    from ..dominio.produto import classificar_estoque

    return classificar_estoque(
        saldo,
        minimo_milesimos=produto.estoque_minimo_milesimos,
        ponto_pedido_milesimos=produto.ponto_pedido_milesimos,
    )


def _saldo_texto(saldo: int, escala: int) -> str:
    if escala == 0:
        return str(saldo // 1000)
    return f"{saldo / 1000:.3f}".replace(".", ",")


class TelaVendas(QWidget):
    def __init__(self, contexto: Contexto, usuario: Usuario, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = contexto
        self.usuario = usuario
        layout = QVBoxLayout(self)

        linha = QHBoxLayout()
        self.data_ini = QDateEdit(QDate.currentDate().addDays(-30))
        self.data_ini.setCalendarPopup(True)
        self.data_fim = QDateEdit(QDate.currentDate())
        self.data_fim.setCalendarPopup(True)
        botao = QPushButton("Filtrar")
        botao.clicked.connect(self.atualizar)
        self.botao_cancelar = QPushButton("Cancelar venda selecionada")
        self.botao_cancelar.setObjectName("perigo")
        self.botao_cancelar.clicked.connect(self._cancelar)
        linha.addWidget(QLabel("De:"))
        linha.addWidget(self.data_ini)
        linha.addWidget(QLabel("Até:"))
        linha.addWidget(self.data_fim)
        linha.addWidget(botao)
        linha.addStretch(1)
        linha.addWidget(self.botao_cancelar)

        self.tabela = QTableWidget(0, 8)
        self.tabela.setHorizontalHeaderLabels(
            ["Cupom", "Data", "Operador", "Cliente", "Itens", "Total", "Aplicado", "Status"]
        )
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.tabela.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.mensagem = QLabel("")

        layout.addLayout(linha)
        layout.addWidget(self.tabela, 1)
        layout.addWidget(self.mensagem)
        self._vendas: list[dict] = []
        self.atualizar()

    def atualizar(self) -> None:
        self._vendas = self.ctx.vendas.listar(
            data_inicial=self.data_ini.date().toString("yyyy-MM-dd"),
            data_final=self.data_fim.date().toString("yyyy-MM-dd"),
            limite=1000,
        )
        self.tabela.setRowCount(len(self._vendas))
        for linha, venda in enumerate(self._vendas):
            valores = [
                f"{venda['serie']}-{venda['numero']:06d}",
                venda["data_negocio"],
                venda["operador"],
                venda["cliente"] or "—",
                str(venda["itens"]),
                Dinheiro(venda["total_centavos"]).formatado(),
                Dinheiro(venda["aplicado_centavos"]).formatado(),
                venda["status"],
            ]
            for coluna, texto in enumerate(valores):
                celula = QTableWidgetItem(texto)
                if coluna in (5, 6):
                    celula.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.tabela.setItem(linha, coluna, celula)

    def _cancelar(self) -> None:
        linha = self.tabela.currentRow()
        if linha < 0 or linha >= len(self._vendas):
            self.mensagem.setText("Selecione uma venda na lista.")
            return
        venda = self._vendas[linha]
        if venda["status"] != "CONCLUIDA":
            self.mensagem.setText("Somente vendas concluídas podem ser canceladas.")
            return
        dialogo = DialogoAutorizacao(
            self.ctx, Acao.VENDA_CANCELAR, "Cancelamento exige gerente e motivo registrado.", self
        )
        if dialogo.exec() != dialogo.DialogCode.Accepted:
            return
        from ..aplicacao.pdv import ServicoPDV
        from ..ui.login import DialogoConfirmacao

        confirmacao = DialogoConfirmacao(
            "Cancelar venda", f"Cancelar a venda {venda['serie']}-{venda['numero']:06d}?", self
        )
        if confirmacao.exec() != confirmacao.DialogCode.Accepted:
            return
        autorizador = dialogo.autorizador
        if autorizador is None:  # diálogo aprovado sem autorizador não deve ocorrer
            return
        try:
            resultado = ServicoPDV(self.ctx).cancelar_venda(
                venda_id=venda["id"],
                motivo=confirmacao.motivo,
                operador=self.usuario,
                autorizador=autorizador,
            )
        except ErroBussola as exc:
            self.mensagem.setText(str(exc))
            return
        QMessageBox.information(
            self,
            "Venda cancelada",
            "Venda mantida no histórico como CANCELADA, com eventos compensatórios.\n"
            "Estoque devolvido: "
            f"{'sim' if resultado['estoque_devolvido'] else 'não'}\n"
            "Reembolso em dinheiro registrado: "
            f"{'sim' if resultado['reembolso_em_dinheiro_registrado'] else 'não'}\n"
            + resultado["aviso"],
        )
        self.atualizar()


class TelaAuditoria(QWidget):
    def __init__(self, contexto: Contexto, usuario: Usuario, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = contexto
        self.usuario = usuario
        layout = QVBoxLayout(self)
        linha = QHBoxLayout()
        self.rotulo = QLabel()
        botao = QPushButton("Verificar cadeia de hashes")
        botao.clicked.connect(self._verificar)
        botao_atualizar = QPushButton("Atualizar")
        botao_atualizar.setObjectName("secundario")
        botao_atualizar.clicked.connect(self.atualizar)
        linha.addWidget(self.rotulo, 1)
        linha.addWidget(botao_atualizar)
        linha.addWidget(botao)

        self.tabela = QTableWidget(0, 6)
        self.tabela.setHorizontalHeaderLabels(["Seq.", "Quando (UTC)", "Ação", "Ator", "Entidade", "Motivo"])
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)

        layout.addLayout(linha)
        layout.addWidget(self.tabela, 1)
        self.atualizar()

    def atualizar(self) -> None:
        eventos = self.ctx.auditoria.listar(limite=500)
        self.tabela.setRowCount(len(eventos))
        for linha, evento in enumerate(eventos):
            valores = [
                str(evento.sequencia),
                evento.criado_em_utc.strftime("%d/%m/%Y %H:%M:%S"),
                evento.acao.value,
                evento.ator_id or "—",
                f"{evento.entidade}:{evento.entidade_id[:8]}" if evento.entidade_id else "—",
                evento.motivo,
            ]
            for coluna, texto in enumerate(valores):
                self.tabela.setItem(linha, coluna, QTableWidgetItem(texto))
        self.rotulo.setText(f"{len(eventos)} evento(s) mais recentes (ordem decrescente).")

    def _verificar(self) -> None:
        resultado = self.ctx.auditoria.verificar()
        QMessageBox.information(self, "Verificação da trilha", resultado.mensagem)


class TelaFechamento(QWidget):
    def __init__(self, contexto: Contexto, usuario: Usuario, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = contexto
        self.usuario = usuario
        self.servico = ServicoRelatorios(contexto)
        layout = QVBoxLayout(self)

        linha = QHBoxLayout()
        self.data = QDateEdit(QDate.currentDate())
        self.data.setCalendarPopup(True)
        botao = QPushButton("Gerar fechamento")
        botao.clicked.connect(self._gerar)
        self.botao_registrar = QPushButton("Registrar snapshot")
        self.botao_registrar.setObjectName("secundario")
        self.botao_registrar.clicked.connect(self._registrar)
        linha.addWidget(QLabel("Data de negócio:"))
        linha.addWidget(self.data)
        linha.addWidget(botao)
        linha.addStretch(1)
        linha.addWidget(self.botao_registrar)

        self.texto = QPlainTextEdit()
        self.texto.setReadOnly(True)
        self.texto.setStyleSheet("font-family: 'DejaVu Sans Mono', monospace; font-size: 9pt;")
        layout.addLayout(linha)
        layout.addWidget(self.texto, 1)
        self._gerar()

    def _data_iso(self) -> str:
        return self.data.date().toString("yyyy-MM-dd")

    def _gerar(self) -> None:
        relatorio = self.servico.fechamento_dia(self._data_iso())
        self.texto.setPlainText(_formatar_relatorio(relatorio))

    def _registrar(self) -> None:
        try:
            resultado = self.servico.registrar_fechamento(
                data_negocio=self._data_iso(), usuario=self.usuario
            )
        except ErroBussola as exc:
            QMessageBox.warning(self, "Fechamento", str(exc))
            return
        QMessageBox.information(
            self, "Fechamento registrado", f"Snapshot gravado: {resultado['fechamento_id']}"
        )
        self._gerar()


def _formatar_relatorio(relatorio: dict) -> str:
    resumo = relatorio["resumo"]
    conciliacao = relatorio["conciliacao"]
    linhas = [
        f"FECHAMENTO · {relatorio['data_negocio']}",
        "=" * 62,
        f"Cupons concluídos ........ {resumo['cupons']}",
        f"Faturamento líquido ...... {Dinheiro(resumo['faturamento_centavos']).formatado()}",
        f"Descontos ................ {Dinheiro(resumo['desconto_centavos']).formatado()}",
        f"Custo dos itens .......... {Dinheiro(resumo['custo_centavos']).formatado()}",
        f"Ticket médio ............. {Dinheiro(resumo['ticket_medio_centavos']).formatado()}",
        "",
        "POR FORMA DE PAGAMENTO",
        "-" * 62,
    ]
    for forma in relatorio["por_forma"]:
        linhas.append(
            f"{forma['rotulo']:<24} {Dinheiro(forma['aplicado_centavos']).formatado():>12}"
            f"  pendente {Dinheiro(forma['pendente_centavos']).formatado():>12}"
        )
    linhas += ["", "CONCILIAÇÃO", "-" * 62]
    linhas.append(
        f"Pagamentos aplicados ..... {Dinheiro(conciliacao['pagamentos_aplicados_centavos']).formatado()}"
    )
    linhas.append(f"Diferença ................ {Dinheiro(conciliacao['diferenca_centavos']).formatado()}")
    linhas.append(f"Situação ................. {'CONCILIADO' if conciliacao['conciliado'] else 'DIVERGENTE'}")
    linhas.append(f"Aviso: {conciliacao['aviso']}")
    linhas += ["", "TURNOS", "-" * 62]
    for turno in relatorio["turnos"]:
        cabeca = (
            f"{turno['turno_id'][:8]} · {turno['status']} · esperado "
            f"{Dinheiro(turno['esperado_centavos']).formatado()}"
        )
        if turno.get("conferido"):
            linhas.append(
                cabeca
                + f" · contado {Dinheiro(turno['contado_centavos']).formatado()}"
                + f" · diferença {Dinheiro(turno['diferenca_centavos']).formatado()}"
                + f" · {turno['classificacao']}"
            )
        elif turno["status"] == "ABERTO":
            linhas.append(cabeca + " · turno em andamento (ainda não conferido)")
        else:
            linhas.append(cabeca + " · sem contagem registrada")
    linhas += ["", "ESTOQUE (posição corrente)", "-" * 62]
    estoque = relatorio["estoque"]
    linhas.append(
        " · ".join(f"{chave}: {valor}" for chave, valor in estoque["por_status"].items())
        + f" · valor a custo {Dinheiro(estoque['valor_custo_centavos']).formatado()}"
    )
    crediario = relatorio["crediario_do_dia"]
    linhas += ["", "CREDIÁRIO (posição corrente)", "-" * 62]
    linhas.append(
        f"Títulos abertos: {crediario['titulos_abertos']} · saldo "
        f"{Dinheiro(crediario['saldo_aberto_centavos']).formatado()} · vencendo hoje "
        f"{Dinheiro(crediario['vencendo_hoje_centavos']).formatado()}"
    )
    divergencias = relatorio["divergencias"]
    if any(divergencias.values()):
        linhas += ["", "ALERTAS", "-" * 62]
        for chave, lista in divergencias.items():
            if lista:
                linhas.append(f"{chave}: {len(lista)} registro(s)")
    if relatorio["pagamentos_pendentes"]:
        linhas += ["", "PAGAMENTOS PENDENTES DE CONFIRMAÇÃO", "-" * 62]
        for pendente in relatorio["pagamentos_pendentes"]:
            linhas.append(
                f"Cupom {pendente['numero']} · {pendente['forma']} · "
                f"{Dinheiro(pendente['valor_aplicado_centavos']).formatado()}"
            )
    linhas += ["", relatorio["escopo"]]
    return "\n".join(linhas)
