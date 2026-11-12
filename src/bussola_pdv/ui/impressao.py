"""Interface de impressão: pré-visualização, escolha de papel e de impressora.

Por que uma pré-visualização existe neste projeto: cupom errado é prejuízo
concreto — sai sem o troco, com o total de outra venda, ou cortado no meio porque a
bobina é de 58 mm e o texto foi montado para 80. Então **nada** vai para o papel sem
o operador ver o que vai sair, no tamanho do papel escolhido, com os mesmos bytes.

O diálogo é o único lugar que conhece Qt de impressão na UI: as telas chamam
`BotaoImprimir` com uma função que devolve o documento, e pronto. Isso mantém
`TelaPDV` e `TelaCaixa` sem saber que existe `QPrinter`.

Regra de responsividade (ADR-021): os botões vão em `FluxoDeAcoes` (quebram em
linha) e o diálogo passa por `ajustar_dialogo()`, para caber em 1024×600 de balcão.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..aplicacao.impressao import (
    ConfiguracaoImpressao,
    MotorImpressao,
    ResultadoImpressao,
    ServicoImpressao,
)
from ..dominio.erros import ErroBussola
from ..dominio.impressao import PERFIS_PAPEL, DocumentoImpresso, Papel
from ..dominio.usuario import Acao, Usuario
from ..infra.impressao import impressoras as infra_impressoras
from ..infra.impressao import papel as renderizador
from .icones import icone
from .responsivo import FluxoDeAcoes, ajustar_dialogo

#: Largura de exibição da prévia: o suficiente para ler 48 colunas sem rolar de lado.
LARGURA_DA_PREVIA = 420


def impressoras_instaladas() -> list[str]:
    """Impressoras do sistema; lista vazia se o Qt não conseguir consultar."""
    try:
        return infra_impressoras.listar()
    except Exception:  # pragma: no cover - ambiente sem spooler
        return []


class SeletorDeImpressoras(QComboBox):
    """Lista as impressoras instaladas e aceita nome digitado (edição livre).

    Edição livre é necessária porque o nome no Windows pode não aparecer na lista
    (impressora de rede offline, driver instalado por outro usuário) e o lojista
    costuma saber o nome exato.
    """

    def __init__(self, valor: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setEditable(True)
        self.addItem("(impressora padrão do sistema)", "")
        for nome in impressoras_instaladas():
            dica = "térmica (provável)" if infra_impressoras.eh_termica(nome) else "comum"
            self.addItem(f"{nome} — {dica}", nome)
        self.definir_valor(valor)

    def definir_valor(self, valor: str) -> None:
        indice = self.findData(valor)
        if indice >= 0:
            self.setCurrentIndex(indice)
        else:
            self.setEditText(valor)

    def valor(self) -> str:
        dado = self.currentData()
        if dado is not None and self.currentText() == self.itemText(self.currentIndex()):
            return str(dado)
        return self.currentText().strip()


class DialogoPreviaImpressao(QDialog):
    """Prévia do documento no papel escolhido, com imprimir e salvar em arquivo."""

    impresso = Signal(object)  # ResultadoImpressao

    def __init__(
        self,
        documento: DocumentoImpresso,
        servico: ServicoImpressao,
        *,
        ator: Usuario | None = None,
        configuracao: ConfiguracaoImpressao | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.servico = servico
        self.ator = ator
        self.config = configuracao or servico.configuracao()
        self.documento = documento
        self.setWindowTitle(f"Prévia de impressão — {documento.titulo}")
        self.setObjectName("dialogoPreviaImpressao")
        ajustar_dialogo(self, largura_preferida=760, altura_preferida=720)

        raiz = QVBoxLayout(self)
        self.rotulo_aviso = QLabel(
            "Confira o conteúdo e o papel antes de imprimir. Documento interno, não fiscal."
        )
        self.rotulo_aviso.setWordWrap(True)
        self.rotulo_aviso.setObjectName("textoAjuda")
        raiz.addWidget(self.rotulo_aviso)

        raiz.addLayout(self._formulario())

        self.area = QScrollArea(self)
        self.area.setWidgetResizable(True)
        self.pagina = QLabel()
        self.pagina.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.pagina.setStyleSheet("background: #F4F6F9;")
        self.area.setWidget(self.pagina)
        raiz.addWidget(self.area, 1)

        self.rotulo_medidas = QLabel()
        self.rotulo_medidas.setObjectName("textoAjuda")
        self.rotulo_medidas.setWordWrap(True)
        raiz.addWidget(self.rotulo_medidas)

        self.mensagem = QLabel("")
        self.mensagem.setWordWrap(True)
        self.mensagem.setObjectName("mensagemErro")
        self.mensagem.setVisible(False)
        raiz.addWidget(self.mensagem)

        acoes = FluxoDeAcoes()
        self.botao_imprimir = QPushButton("Imprimir")
        self.botao_imprimir.clicked.connect(self.imprimir)
        self.botao_pdf = QPushButton("Salvar PDF")
        self.botao_pdf.setObjectName("secundario")
        self.botao_pdf.clicked.connect(lambda: self.salvar("pdf"))
        self.botao_txt = QPushButton("Salvar TXT")
        self.botao_txt.setObjectName("secundario")
        self.botao_txt.clicked.connect(lambda: self.salvar("txt"))
        self.botao_fechar = QPushButton("Fechar")
        self.botao_fechar.setObjectName("secundario")
        self.botao_fechar.clicked.connect(self.reject)
        for botao in (self.botao_imprimir, self.botao_pdf, self.botao_txt, self.botao_fechar):
            acoes.adicionar(botao)
        raiz.addWidget(acoes)

        if ator is not None and not ator.pode(Acao.CUPOM_REIMPRIMIR):
            self.botao_imprimir.setEnabled(False)
            self._avisar("Seu perfil não imprime cupom. Peça ao gerente ou ao admin.")

        self.atualizar_previa()

    # -- formulário ----------------------------------------------------------
    def _formulario(self) -> QFormLayout:
        formulario = QFormLayout()
        self.combo_papel = QComboBox()
        for papel in (Papel.BOBINA_58, Papel.BOBINA_80, Papel.A4):
            self.combo_papel.addItem(PERFIS_PAPEL[papel].rotulo, papel.value)
        indice = self.combo_papel.findData(self.documento.papel.value)
        self.combo_papel.setCurrentIndex(max(0, indice))
        self.combo_papel.currentIndexChanged.connect(self.atualizar_previa)
        formulario.addRow("Papel", self.combo_papel)

        self.combo_impressora = SeletorDeImpressoras(self.config.impressora, self)
        formulario.addRow("Impressora", self.combo_impressora)

        self.spin_copias = QSpinBox()
        self.spin_copias.setRange(1, 5)
        self.spin_copias.setValue(self.config.copias)
        formulario.addRow("Cópias", self.spin_copias)

        linha_motor = QHBoxLayout()
        self.rotulo_motor = QLabel(self.config.motor.rotulo)
        self.rotulo_motor.setWordWrap(True)
        self.rotulo_motor.setObjectName("textoAjuda")
        linha_motor.addWidget(self.rotulo_motor, 1)
        caixa = QWidget()
        caixa.setLayout(linha_motor)
        formulario.addRow("Motor", caixa)
        return formulario

    # -- estado --------------------------------------------------------------
    def papel(self) -> Papel:
        return Papel(str(self.combo_papel.currentData()))

    def documento_atual(self) -> DocumentoImpresso:
        return self.documento.com_papel(self.papel())

    def configuracao_atual(self) -> ConfiguracaoImpressao:
        base = self.config
        return ConfiguracaoImpressao(
            motor=base.motor,
            impressora=self.combo_impressora.valor(),
            papel=self.papel(),
            copias=self.spin_copias.value(),
            cortar_papel=base.cortar_papel,
            abrir_gaveta=base.abrir_gaveta,
            codigo_de_barras=base.codigo_de_barras,
            imprimir_automatico=base.imprimir_automatico,
        )

    def atualizar_previa(self) -> None:
        documento = self.documento_atual()
        try:
            imagem = renderizador.imagem(documento)
        except Exception as exc:  # pragma: no cover - falha de desenho
            self._avisar(f"Não foi possível desenhar a prévia: {exc}")
            return
        pixmap = QPixmap.fromImage(imagem)
        largura = min(LARGURA_DA_PREVIA, pixmap.width() * 2)
        self.pagina.setPixmap(
            pixmap.scaledToWidth(
                largura, Qt.TransformationMode.SmoothTransformation
            )
        )
        perfil = PERFIS_PAPEL[documento.papel]
        self.rotulo_medidas.setText(
            f"{perfil.rotulo}: {perfil.colunas} colunas, "
            f"{len(documento.layout())} linhas, ~{documento.altura_mm():.0f} mm de altura."
        )
        if documento.papel is Papel.A4 and self.config.motor is MotorImpressao.ESCPOS:
            self._avisar(
                "O motor ESC/POS imprime bobina. Para esta folha, troque o motor em "
                "Administração → Parâmetros → Impressão ou use Salvar PDF."
            )
        else:
            self._limpar_aviso()

    # -- ações ---------------------------------------------------------------
    def imprimir(self) -> ResultadoImpressao | None:
        documento = self.documento_atual()
        try:
            resultado = self.servico.despachar(
                documento, ator=self.ator, configuracao=self.configuracao_atual()
            )
        except ErroBussola as exc:
            self._avisar(str(exc))
            return None
        except OSError as exc:  # pragma: no cover - falha de driver
            self._avisar(f"A impressora não respondeu: {exc}")
            return None
        self.impresso.emit(resultado)
        QMessageBox.information(
            self,
            "Impressão enviada",
            f"{resultado.titulo} enviado para {resultado.destino}.\n"
            f"{resultado.linhas} linha(s) em {PERFIS_PAPEL[resultado.papel].rotulo}.",
        )
        return resultado

    def salvar(self, formato: str) -> Path | None:
        documento = self.documento_atual()
        sugestao = Path.home() / f"{documento.rotulo}.{formato}"
        filtro = "Documento PDF (*.pdf)" if formato == "pdf" else "Texto (*.txt)"
        escolhido, _ = QFileDialog.getSaveFileName(self, "Salvar documento", str(sugestao), filtro)
        if not escolhido:
            return None
        destino = Path(escolhido)
        if destino.suffix.lower() != f".{formato}":
            destino = destino.with_suffix(f".{formato}")
        try:
            caminho = self.servico.salvar(documento, destino.parent, formato=formato)
            if caminho != destino:
                caminho.replace(destino)
        except (ErroBussola, OSError) as exc:
            self._avisar(f"Não foi possível salvar: {exc}")
            return None
        QMessageBox.information(self, "Documento salvo", f"Arquivo gravado em:\n{caminho}")
        return caminho

    # -- mensagens -----------------------------------------------------------
    def _avisar(self, texto: str) -> None:
        self.mensagem.setText(texto)
        self.mensagem.setObjectName("mensagemErro")
        self.mensagem.setVisible(True)

    def _limpar_aviso(self) -> None:
        self.mensagem.clear()
        self.mensagem.setVisible(False)


class BotaoImprimir(QPushButton):
    """Botão \"Imprimir\" reutilizável: abre a prévia do documento que a tela montar.

    `construir` é chamado no clique (e não na criação), para refletir o que está na
    tela naquele instante — mesma decisão do `BotaoExportar`.
    """

    impresso = Signal(object)

    def __init__(
        self,
        *,
        ator: Usuario | None,
        servico: ServicoImpressao,
        construir: Callable[[], DocumentoImpresso],
        parent: QWidget | None = None,
        rotulo: str = "Imprimir",
    ) -> None:
        super().__init__(rotulo, parent)
        self.ator = ator
        self.servico = servico
        self.construir = construir
        self.setObjectName("secundario")
        self.setIcon(icone("saida", "#212529", 16))
        self.setToolTip("Pré-visualizar e imprimir (térmica 58/80 mm ou folha A4)")
        self.clicked.connect(self.abrir_previa)
        if ator is not None and not ator.pode(Acao.CUPOM_REIMPRIMIR):
            self.setVisible(False)

    def abrir_previa(self) -> DialogoPreviaImpressao | None:
        try:
            documento = self.construir()
        except ErroBussola as exc:
            QMessageBox.warning(self, "Imprimir", str(exc))
            return None
        dialogo = DialogoPreviaImpressao(documento, self.servico, ator=self.ator, parent=self)
        dialogo.impresso.connect(self.impresso.emit)
        dialogo.exec()
        return dialogo


__all__ = [
    "LARGURA_DA_PREVIA",
    "BotaoImprimir",
    "DialogoPreviaImpressao",
    "SeletorDeImpressoras",
    "impressoras_instaladas",
]
