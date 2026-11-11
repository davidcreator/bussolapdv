"""Seção 'Marca e tema': identidade da loja e paleta de cores da operação."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...aplicacao.contexto import Contexto
from ...aplicacao.marca import ServicoMarca
from ...dominio.marca import PRESET_PERSONALIZADO, Marca, Paleta
from ...dominio.usuario import Acao, Usuario
from .comum import Mensagem, descrever_erro

ROTULOS_COR = {
    "primaria": "Primária (faixa e botões)",
    "primaria_escura": "Primária escura (navegação)",
    "secundaria": "Secundária (destaque de módulo)",
    "secundaria_clara": "Secundária clara (seleção)",
    "destaque": "Destaque (bordas de entrada)",
    "fundo": "Fundo da janela",
    "superficie": "Superfície (tabelas)",
    "texto": "Texto principal",
    "texto_suave": "Texto secundário",
    "sucesso": "Sucesso",
    "alerta": "Alerta",
    "erro": "Erro",
    "borda": "Bordas",
    "entrada": "Fundo de campos",
}


class BotaoCor(QPushButton):
    """Botão que mostra a cor atual e abre o seletor ao clicar."""

    cor_alterada = Signal(str, str)  # nome do token, novo hex

    def __init__(self, nome: str, cor: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.nome = nome
        self.setFixedHeight(30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pintar(cor)
        self.clicked.connect(self._escolher)

    def _pintar(self, cor: str) -> None:
        self.cor = cor
        claro = QColor(cor).lightnessF() > 0.6
        tinta = "#1F1F1F" if claro else "#FFFFFF"
        self.setText(f"{cor}  ·  {ROTULOS_COR[self.nome]}")
        self.setStyleSheet(
            f"QPushButton {{ background: {cor}; color: {tinta}; border: 1px solid #888;"
            f" text-align: left; padding-left: 8px; font-weight: 600; }}"
        )

    def definir(self, cor: str) -> None:
        self._pintar(cor)

    def _escolher(self) -> None:
        cor = QColorDialog.getColor(QColor(self.cor), self, f"Cor: {ROTULOS_COR[self.nome]}")
        if cor.isValid():
            self._pintar(cor.name().upper())
            self.cor_alterada.emit(self.nome, self.cor.upper())


class SecaoMarca(QWidget):
    marca_salva = Signal()

    def __init__(self, contexto: Contexto, usuario: Usuario, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = contexto
        self.usuario = usuario
        self.servico = ServicoMarca(contexto)
        self.marca = self.servico.obter()
        self.pode_dados = usuario.pode(Acao.MARCA_GERENCIAR)
        self.pode_tema = usuario.pode(Acao.TEMA_GERENCIAR)

        area = QScrollArea(self)
        area.setWidgetResizable(True)
        conteudo = QWidget()
        layout = QVBoxLayout(conteudo)

        titulo = QLabel("Marca e tema")
        titulo.setObjectName("destaqueAdmin")
        layout.addWidget(titulo)
        layout.addWidget(
            self._ajuda(
                "Identidade da loja (nome, contato, logo) e cores da interface. "
                "Quem altera a marca precisa de 'Alterar dados da loja'; quem altera as cores, "
                "de 'Alterar cores e tema' — o Admin Master decide quem recebe cada uma."
            )
        )

        linha = QHBoxLayout()
        linha.addWidget(self._grupo_identidade(), 1)
        linha.addWidget(self._grupo_previa(), 1)
        layout.addLayout(linha)
        layout.addWidget(self._grupo_cores())

        botoes = QHBoxLayout()
        self.botao_salvar = QPushButton("Salvar alterações")
        self.botao_salvar.clicked.connect(self._salvar)
        self.botao_padrao = QPushButton("Restaurar padrão")
        self.botao_padrao.setObjectName("secundario")
        self.botao_padrao.clicked.connect(self._restaurar)
        botoes.addWidget(self.botao_salvar)
        botoes.addWidget(self.botao_padrao)
        botoes.addStretch(1)
        layout.addLayout(botoes)

        self.mensagem = Mensagem()
        layout.addWidget(self.mensagem)
        layout.addStretch(1)

        area.setWidget(conteudo)
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.addWidget(area)

        habilitado = self.pode_dados or self.pode_tema
        self.botao_salvar.setEnabled(habilitado)
        self.botao_padrao.setEnabled(habilitado)
        if not habilitado:
            self.mensagem.alerta(
                "Seu perfil não pode alterar marca nem tema. Peça liberação ao Admin Master."
            )
        self._carregar(self.marca)

    # -- montagem -----------------------------------------------------------
    def _ajuda(self, texto: str) -> QLabel:
        rotulo = QLabel(texto)
        rotulo.setWordWrap(True)
        rotulo.setObjectName("textoAjuda")
        return rotulo

    def _grupo_identidade(self) -> QGroupBox:
        grupo = QGroupBox("Identidade da loja")
        formulario = QFormLayout(grupo)
        self.campo_nome = QLineEdit()
        self.campo_nome.setMaxLength(60)
        self.campo_razao = QLineEdit()
        self.campo_cnpj = QLineEdit()
        self.campo_cnpj.setPlaceholderText("somente números")
        self.campo_telefone = QLineEdit()
        self.campo_endereco = QLineEdit()
        self.campo_rodape = QLineEdit()
        formulario.addRow("Nome fantasia*", self.campo_nome)
        formulario.addRow("Razão social", self.campo_razao)
        formulario.addRow("CNPJ", self.campo_cnpj)
        formulario.addRow("Telefone", self.campo_telefone)
        formulario.addRow("Endereço", self.campo_endereco)
        formulario.addRow("Rodapé do comprovante", self.campo_rodape)

        linha_logo = QHBoxLayout()
        self.rotulo_logo = QLabel("sem logo")
        self.rotulo_logo.setObjectName("textoAjuda")
        self.botao_logo = QPushButton("Escolher PNG…")
        self.botao_logo.setObjectName("secundario")
        self.botao_logo.clicked.connect(self._escolher_logo)
        self.botao_remover_logo = QPushButton("Remover")
        self.botao_remover_logo.setObjectName("secundario")
        self.botao_remover_logo.clicked.connect(self._remover_logo)
        linha_logo.addWidget(self.rotulo_logo, 1)
        linha_logo.addWidget(self.botao_logo)
        linha_logo.addWidget(self.botao_remover_logo)
        recipiente = QWidget()
        recipiente.setLayout(linha_logo)
        formulario.addRow("Logo", recipiente)

        for campo in (
            self.campo_nome,
            self.campo_razao,
            self.campo_cnpj,
            self.campo_telefone,
            self.campo_endereco,
            self.campo_rodape,
            self.botao_logo,
            self.botao_remover_logo,
        ):
            campo.setEnabled(self.pode_dados)
        return grupo

    def _grupo_previa(self) -> QGroupBox:
        grupo = QGroupBox("Prévia e acessibilidade")
        layout = QVBoxLayout(grupo)
        self.previa_titulo = QLabel("Nome da loja")
        self.previa_titulo.setObjectName("tituloApp")
        self.previa_titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.previa_faixa = QLabel("faixa secundária")
        self.previa_faixa.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.previa_botao = QPushButton("Botão de exemplo")
        self.previa_botao.setEnabled(False)
        self.previa_entrada = QLineEdit("campo de entrada")
        self.previa_entrada.setReadOnly(True)
        self.rotulo_contraste = QLabel("")
        self.rotulo_contraste.setWordWrap(True)
        self.rotulo_contraste.setObjectName("textoAjuda")
        for widget in (self.previa_titulo, self.previa_faixa, self.previa_botao, self.previa_entrada):
            layout.addWidget(widget)
        layout.addWidget(self.rotulo_contraste)
        layout.addStretch(1)
        return grupo

    def _grupo_cores(self) -> QGroupBox:
        grupo = QGroupBox("Cores e tipografia")
        layout = QVBoxLayout(grupo)
        linha = QHBoxLayout()
        linha.addWidget(QLabel("Tema base"))
        self.combo_preset = QComboBox()
        for chave in ("BUSSOLA", "GRAFITE", "ESMERALDA", "NOTURNO", PRESET_PERSONALIZADO):
            self.combo_preset.addItem(chave, chave)
        self.combo_preset.currentIndexChanged.connect(self._preset_escolhido)
        linha.addWidget(self.combo_preset, 1)
        linha.addWidget(QLabel("Fonte"))
        self.campo_fonte = QLineEdit()
        self.campo_fonte.setMaximumWidth(180)
        linha.addWidget(self.campo_fonte)
        layout.addLayout(linha)

        grade = QGridLayout()
        self.botoes_cor: dict[str, BotaoCor] = {}
        for indice, nome in enumerate(Paleta.__slots__):
            botao = BotaoCor(nome, getattr(self.marca.paleta, nome))
            botao.cor_alterada.connect(self._cor_alterada)
            botao.setEnabled(self.pode_tema)
            self.botoes_cor[nome] = botao
            grade.addWidget(botao, indice // 2, indice % 2)
        layout.addLayout(grade)
        self.combo_preset.setEnabled(self.pode_tema)
        self.campo_fonte.setEnabled(self.pode_tema)
        return grupo

    # -- estado -------------------------------------------------------------
    def _carregar(self, marca: Marca) -> None:
        self.marca = marca
        for campo, valor in (
            (self.campo_nome, marca.nome_fantasia),
            (self.campo_razao, marca.razao_social),
            (self.campo_cnpj, marca.cnpj),
            (self.campo_telefone, marca.telefone),
            (self.campo_endereco, marca.endereco),
            (self.campo_rodape, marca.rodape_comprovante),
            (self.campo_fonte, marca.fonte),
        ):
            campo.setText(valor)
            campo.setCursorPosition(0)  # textos longos aparecem desde o início
        self.rotulo_logo.setText("logo definido" if marca.logo_data_uri else "sem logo")
        posicao = self.combo_preset.findData(marca.preset)
        self.combo_preset.blockSignals(True)
        self.combo_preset.setCurrentIndex(posicao if posicao >= 0 else 0)
        self.combo_preset.blockSignals(False)
        for nome, botao in self.botoes_cor.items():
            botao.definir(getattr(marca.paleta, nome))
        self._pintar_previa(marca.paleta, marca.nome_fantasia, marca.fonte)

    def _pintar_previa(self, paleta: Paleta, nome: str, fonte: str) -> None:
        self.previa_titulo.setText(nome or "Nome da loja")
        self.previa_titulo.setStyleSheet(
            f"background: {paleta.primaria}; color: #FFFFFF; padding: 12px;"
            f" font-family: '{fonte}'; border-radius: 4px;"
        )
        self.previa_faixa.setStyleSheet(
            f"background: {paleta.secundaria}; color: #FFFFFF; padding: 6px; border-radius: 4px;"
        )
        self.previa_botao.setStyleSheet(
            f"background: {paleta.primaria}; color: #FFFFFF; padding: 7px; border-radius: 4px;"
        )
        self.previa_entrada.setStyleSheet(
            f"background: {paleta.entrada}; border: 1px solid {paleta.destaque};"
            f" color: {paleta.texto}; padding: 5px; border-radius: 4px;"
        )
        avisos = paleta.avisos()
        texto = (
            f"Contraste texto/superfície: {paleta.contraste_texto_superficie}:1 · "
            f"branco/primária: {paleta.contraste_branco_primaria}:1"
        )
        if avisos:
            self.rotulo_contraste.setText(texto + "\n⚠ " + " ".join(avisos))
            self.rotulo_contraste.setObjectName("mensagemAlerta")
        else:
            self.rotulo_contraste.setText(texto + "\nContraste adequado (WCAG AA).")
            self.rotulo_contraste.setObjectName("textoAjuda")
        self.rotulo_contraste.style().unpolish(self.rotulo_contraste)
        self.rotulo_contraste.style().polish(self.rotulo_contraste)

    # -- eventos ------------------------------------------------------------
    def _preset_escolhido(self) -> None:
        if not self.pode_tema:
            return
        preset = str(self.combo_preset.currentData())
        if preset == PRESET_PERSONALIZADO:
            return
        paleta = self.servico.presets()[preset]
        for nome, botao in self.botoes_cor.items():
            botao.definir(getattr(paleta, nome))
        self._pintar_previa(paleta, self.campo_nome.text(), self.campo_fonte.text())

    def _cor_alterada(self, nome: str, cor: str) -> None:
        if not self.pode_tema:
            return
        self.combo_preset.blockSignals(True)
        self.combo_preset.setCurrentIndex(self.combo_preset.findData(PRESET_PERSONALIZADO))
        self.combo_preset.blockSignals(False)
        paleta = self._paleta_atual()
        self._pintar_previa(paleta, self.campo_nome.text(), self.campo_fonte.text())

    def _paleta_atual(self) -> Paleta:
        return Paleta(**{nome: botao.cor for nome, botao in self.botoes_cor.items()})

    def _escolher_logo(self) -> None:
        caminho, _ = QFileDialog.getOpenFileName(self, "Logo da loja", "", "Imagens PNG (*.png)")
        if not caminho:
            return
        try:
            logo = self.servico.logo_de_arquivo(caminho)
        except Exception as exc:
            self.mensagem.erro(descrever_erro(exc))
            return
        self.marca = self.marca.com(logo_data_uri=logo)
        self.rotulo_logo.setText("logo definido (PNG)")
        self.mensagem.ok("Logo carregado. Não esqueça de salvar.")

    def _remover_logo(self) -> None:
        self.marca = self.marca.com(logo_data_uri="")
        self.rotulo_logo.setText("sem logo")
        self.mensagem.alerta("Logo removido na tela; salve para aplicar.")

    def _salvar(self) -> None:
        preset = str(self.combo_preset.currentData())
        try:
            nova = Marca(
                nome_fantasia=self.campo_nome.text(),
                razao_social=self.campo_razao.text().strip(),
                cnpj="".join(ch for ch in self.campo_cnpj.text() if ch.isdigit()),
                telefone=self.campo_telefone.text().strip(),
                endereco=self.campo_endereco.text().strip(),
                rodape_comprovante=self.campo_rodape.text().strip(),
                preset=preset,
                paleta=self._paleta_atual(),
                fonte=self.campo_fonte.text().strip() or "Segoe UI",
                logo_data_uri=self.marca.logo_data_uri,
            )
        except Exception as exc:
            self.mensagem.erro(descrever_erro(exc))
            return
        if nova.avisos:
            self.mensagem.alerta("Atenção de acessibilidade: " + " ".join(nova.avisos))
        try:
            salva = self.servico.salvar(self.usuario, nova)
        except Exception as exc:
            self.mensagem.erro(descrever_erro(exc))
            return
        self._carregar(salva)
        self.mensagem.ok("Marca e tema salvos. A interface foi atualizada.")
        self.marca_salva.emit()

    def _restaurar(self) -> None:
        try:
            marca = self.servico.restaurar_padrao(self.usuario)
        except Exception as exc:
            self.mensagem.erro(descrever_erro(exc))
            return
        self._carregar(marca)
        self.mensagem.ok("Marca e tema restaurados para o padrão de fábrica.")
        self.marca_salva.emit()
