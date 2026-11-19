"""Devolução pela tela: escolher itens, dizer o motivo e para onde vai o valor.

O desenho segue o que o balcão precisa responder na frente do cliente:

1. **o que voltou** — a tabela mostra cada item da venda, quanto já voltou e
   quanto ainda pode voltar; a coluna "A devolver" é a única editável;
2. **por quê** — arrependimento, defeito, garantia ou erro de operação. O prazo
   do tipo aparece ao lado, com os dias restantes; fora do prazo, o diálogo pede
   a senha de outro usuário;
3. **o que fazer com o dinheiro** — gaveta (caixa aberto), abater o crediário ou
   troca. Troca avisa que a nova venda é registrada separadamente.

Nada é calculado aqui: quantidade, prazo, estoque e caixa são decididos pelo
`ServicoDevolucao`; a tela só mostra o resultado.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from ..aplicacao.contexto import Contexto
from ..aplicacao.devolucao import ItemSolicitado, ResultadoDevolucao
from ..aplicacao.remoto import servicos_de
from ..dominio.devolucao import DestinoDevolucao, TipoDevolucao
from ..dominio.dinheiro import Quantidade
from ..dominio.usuario import Acao, Usuario
from ..infra.sqlite.repositorio_vendas import VendaRegistrada
from .cadastros import _DialogoBase, _moeda, caixa_aberto
from .widgets import ajustar_colunas, preparar_tabela

#: Índice da coluna editável na tabela de itens.
COLUNA_DEVOLVER = 5


class DialogoDevolucao(_DialogoBase):
    """Registra devolução parcial ou total, com tipo, prazo e destino do valor."""

    def __init__(
        self,
        contexto: Contexto,
        usuario: Usuario,
        venda: VendaRegistrada,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            contexto,
            titulo="Devolver itens da venda",
            subtitulo=f"Venda {venda.rotulo} · {venda.data_negocio} · {_moeda(venda.total.centavos)}",
            rotulo_confirmar="Registrar devolução",
            parent=parent,
            largura=720,
        )
        self.usuario = usuario
        self.venda = venda
        self.servico = servicos_de(contexto).devolucao
        self.resultado: ResultadoDevolucao | None = None

        self.combo_tipo = QComboBox()
        for tipo in TipoDevolucao:
            self.combo_tipo.addItem(tipo.rotulo, tipo.value)
        self._campo("Motivo", self.combo_tipo)
        self.combo_tipo.currentIndexChanged.connect(self._atualizar_prazo)

        self.rotulo_prazo = QLabel()
        self.rotulo_prazo.setObjectName("textoAjuda")
        self.rotulo_prazo.setWordWrap(True)
        self._campo("Prazo", self.rotulo_prazo)

        self.combo_destino = QComboBox()
        for destino in DestinoDevolucao:
            self.combo_destino.addItem(destino.rotulo, destino.value)
        self._campo("Destino do valor", self.combo_destino)

        self.campo_motivo = self._texto(
            "Descrição", dica="o que aconteceu (ex.: cliente trocou de tamanho)"
        )
        self.campo_observacoes = self._texto("Observações", dica="opcional")
        self.marcar_estoque = QCheckBox("itens voltam para o estoque")
        self.marcar_estoque.setChecked(True)
        self.corpo.addWidget(self.marcar_estoque)

        self.tabela = QTableWidget(0, 7)
        self.tabela.setHorizontalHeaderLabels(
            ["Item", "Código", "Descrição", "Vendido", "Já devolvido", "A devolver", "Valor unit."]
        )
        self.tabela.verticalHeader().setVisible(False)
        preparar_tabela(self.tabela)
        ajustar_colunas(self.tabela, 2)
        self.corpo.addWidget(self.tabela)

        self.campo_login = self._texto("Autorizador (login)", dica="só se estiver fora do prazo")
        self.campo_senha = self._texto("Senha do autorizador")
        self.campo_senha.setEchoMode(QLineEdit.EchoMode.Password)

        self._carregar_itens()
        self._atualizar_prazo()

    # -- montagem -----------------------------------------------------------
    def _carregar_itens(self) -> None:
        itens = self.servico.itens_devolviveis(self.venda.id)
        self.tabela.setRowCount(len(itens))
        for linha, item in enumerate(itens):
            valores = [
                str(item["sequencia"]),
                str(item["codigo_produto"]),
                str(item["descricao"]),
                Quantidade(int(item["quantidade_milesimos"])).formatada(),
                Quantidade(int(item["devolvido_milesimos"])).formatada(),
                "",
                _moeda(int(item["preco_unitario_centavos"])),
            ]
            for coluna, texto in enumerate(valores):
                celula = QTableWidgetItem(texto)
                if coluna in (0, 3, 4, 5, 6):
                    celula.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                if coluna == COLUNA_DEVOLVER:
                    if int(item["devolvivel_milesimos"]) <= 0:
                        celula.setFlags(celula.flags() & ~Qt.ItemFlag.ItemIsEditable)
                        celula.setToolTip("Este item já foi devolvido por inteiro.")
                else:
                    celula.setFlags(celula.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.tabela.setItem(linha, coluna, celula)

    def _atualizar_prazo(self) -> None:
        tipo = TipoDevolucao(str(self.combo_tipo.currentData()))
        avaliacao = self.servico.avaliar(venda_id=self.venda.id, tipo=tipo)
        self.rotulo_prazo.setText(avaliacao.motivo)
        self.rotulo_prazo.setObjectName(
            "textoAjuda" if avaliacao.dentro_do_prazo else "textoAlerta"
        )

    # -- gravação -----------------------------------------------------------
    def _itens_marcados(self) -> list[ItemSolicitado]:
        pedidos: list[ItemSolicitado] = []
        for linha in range(self.tabela.rowCount()):
            celula = self.tabela.item(linha, COLUNA_DEVOLVER)
            if celula is None or not celula.text().strip():
                continue
            primeira = self.tabela.item(linha, 0)
            sequencia = int(primeira.text()) if primeira is not None else 0
            pedidos.append(
                ItemSolicitado(venda_item_sequencia=sequencia, quantidade=celula.text().strip())
            )
        return pedidos

    def _salvar(self) -> None:
        tipo = TipoDevolucao(str(self.combo_tipo.currentData()))
        destino = DestinoDevolucao(str(self.combo_destino.currentData()))
        autorizador = None
        if self.campo_login.text().strip():
            autorizador = servicos_de(self.ctx).autenticacao.autorizar(
                self.campo_login.text().strip(),
                self.campo_senha.text(),
                Acao.VENDA_DEVOLVER,
            )
        self.resultado = self.servico.registrar(
            operador=self.usuario,
            venda_id=self.venda.id,
            itens=self._itens_marcados(),
            tipo=tipo,
            destino=destino,
            motivo=self.campo_motivo.text().strip(),
            autorizador=autorizador,
            caixa_id=caixa_aberto(self.ctx) if destino is DestinoDevolucao.DINHEIRO else None,
            devolver_estoque=self.marcar_estoque.isChecked(),
            observacoes=self.campo_observacoes.text().strip(),
        )

    # -- texto de retorno ---------------------------------------------------
    def resumo(self) -> str:
        """Frase pronta para a tela de vendas mostrar depois de registrar."""
        if self.resultado is None:
            return ""
        partes = [f"Devolução {self.resultado.total.formatado()} registrada."]
        if self.resultado.dinheiro_devolvido.centavos:
            partes.append(f"Devolvido em dinheiro: {self.resultado.dinheiro_devolvido.formatado()}.")
        if self.resultado.credito_aplicado.centavos:
            partes.append(
                f"Abatido no crediário: {self.resultado.credito_aplicado.formatado()} "
                f"em {len(self.resultado.titulos_abatidos)} parcela(s)."
            )
        if self.resultado.estoque_devolvido:
            partes.append("Itens voltaram ao estoque.")
        partes.extend(self.resultado.avisos)
        return " ".join(partes)


__all__ = ["DialogoDevolucao"]
