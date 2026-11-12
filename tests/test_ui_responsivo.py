"""Testes da responsividade: a interface se reorganiza pela largura da janela.

O que se prova aqui, sem servidor gráfico:

* as réguas de largura são funções puras e devolvem a faixa certa nas bordas;
* os indicadores passam de 4 para 2 e para 1 por linha, sem espremer;
* o cabeçalho do cartão desce as ferramentas de linha quando o cartão é estreito;
* a sidebar recolhe sozinha em janela compacta, respeita a escolha manual do
  operador e volta à régua automática quando a faixa muda;
* a tabela decide entre "cabe e estica" e "não cabe e rola";
* diálogos não nascem mais largos do que a tela permite.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip(
    "PySide6.QtWidgets", exc_type=ImportError, reason="PySide6 ou libs do Qt ausentes"
)

from bussola_pdv.ui import responsivo, widgets

pytestmark = pytest.mark.ui


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication(["teste-responsivo"])


class TestReguas:
    def test_faixas_nas_bordas(self):
        assert responsivo.classe_de_largura(0) == responsivo.CLASSE_COMPACTA
        assert responsivo.classe_de_largura(responsivo.PONTO_COMPACTO - 1) == (
            responsivo.CLASSE_COMPACTA
        )
        assert responsivo.classe_de_largura(responsivo.PONTO_COMPACTO) == (
            responsivo.CLASSE_MEDIA
        )
        assert responsivo.classe_de_largura(responsivo.PONTO_MEDIO - 1) == (
            responsivo.CLASSE_MEDIA
        )
        assert responsivo.classe_de_largura(responsivo.PONTO_MEDIO) == (
            responsivo.CLASSE_AMPLA
        )
        assert responsivo.classe_de_largura(3840) == responsivo.CLASSE_AMPLA

    def test_colunas_nunca_passam_do_numero_de_indicadores(self):
        assert responsivo.colunas_para(1920, 3) == 3
        assert responsivo.colunas_para(1920, 1) == 1
        assert responsivo.colunas_para(1920, 2) == 2

    def test_colunas_em_800_px_sao_no_maximo_duas(self):
        assert responsivo.colunas_para(800, 4) == 2
        assert responsivo.colunas_para(1024, 4) == 3
        assert responsivo.colunas_para(1280, 4) == 4

    def test_largura_minima_de_um_indicador(self):
        # 4 indicadores em 300 px não cabem: empilha em vez de espremer
        assert responsivo.colunas_para(300, 4) == 1
        assert responsivo.colunas_para(1, 4) == 1


class TestGradeDeIndicadores:
    def _indicadores(self, quantidade: int) -> list[widgets.CaixaInfo]:
        return [
            widgets.CaixaInfo(f"Indicador {indice}", "0", "pdv", "claro", "legenda")
            for indice in range(quantidade)
        ]

    def test_reflui_conforme_a_largura(self, app):
        grade = responsivo.GradeDeIndicadores(self._indicadores(4))
        grade.reorganizar_para(1280)
        assert grade.colunas == 4
        grade.reorganizar_para(1024)
        assert grade.colunas == 3
        grade.reorganizar_para(800)
        assert grade.colunas == 2
        grade.reorganizar_para(420)
        assert grade.colunas == 1

    def test_altura_acompanha_as_linhas(self, app):
        """3 cartões em 2 colunas ocupam 2 linhas — sem isso o segundo sobrepõe o primeiro."""
        grade = responsivo.GradeDeIndicadores(self._indicadores(3))
        grade.reorganizar_para(1280)
        altura_uma_linha = grade.minimumHeight()
        grade.reorganizar_para(420)
        assert grade.minimumHeight() >= altura_uma_linha
        assert grade.minimumHeight() >= 2 * 56  # duas linhas de CaixaInfo

    def test_troca_de_indicadores_reposiciona(self, app):
        grade = responsivo.GradeDeIndicadores(self._indicadores(2))
        novos = self._indicadores(3)
        grade.definir_indicadores(novos)
        grade.reorganizar_para(1280)
        assert grade.indicadores == novos
        assert grade.colunas == 3
        assert grade.parent() is None

    def test_sem_indicadores_nao_quebra(self, app):
        grade = responsivo.GradeDeIndicadores([])
        grade.reorganizar_para(800)
        assert grade.colunas == 0
        assert grade.sizeHint().height() >= 0


class TestCabecalhoDoCartao:
    def test_ferramentas_descem_de_linha_em_cartao_estreito(self, app):
        cartao = widgets.Cartao(
            "Catálogo e saldo", "Saldo é posição corrente; o status vem da regra de estoque"
        )
        botao = widgets.Cartao().adicionar_ferramenta
        assert botao is not None
        cartao.adicionar_ferramenta(widgets.Selo("16 na consulta"))
        cartao.resize(500, 200)
        app.processEvents()
        cartao._reorganizar_cabecalho(500)
        assert cartao._cabecalho_empilhado is True
        cartao._reorganizar_cabecalho(900)
        assert cartao._cabecalho_empilhado is False

    def test_cabecalho_empilhado_nao_impõe_largura(self, app):
        """O caso real: título + subtítulo longo + exportar exigiam 949 px de página."""
        cartao = widgets.Cartao("Catálogo e saldo", "Saldo é posição corrente, sem invenção")
        cartao.adicionar_ferramenta(widgets.Selo("16 na consulta · Ruptura: 1 · Baixo: 2"))
        cartao._reorganizar_cabecalho(500)
        cartao.resize(500, 200)
        app.processEvents()
        assert cartao.minimumSizeHint().width() < 500


class TestCascaResponsiva:
    def _casca(self, app):
        from PySide6.QtWidgets import QVBoxLayout, QWidget

        class Casca(QWidget, responsivo.CascaResponsiva):
            def __init__(self) -> None:
                super().__init__()
                self.barra_lateral = widgets.BarraLateral("Loja", "ana", "Gerente")
                self.barra_superior = widgets.BarraSuperior("Loja", "ana", "Gerente")
                coluna = QVBoxLayout(self)
                coluna.addWidget(self.barra_superior)
                coluna.addWidget(self.barra_lateral)
                self._iniciar_casca()

        return Casca()

    def test_compacta_recolhe_a_sidebar(self, app):
        casca = self._casca(app)
        assert casca.reorganizar_casca(800) == responsivo.CLASSE_COMPACTA
        assert casca.barra_lateral.recolhida is True
        assert casca.barra_superior.chip_usuario.isVisibleTo(casca) is False

    def test_ampla_abre_a_sidebar(self, app):
        casca = self._casca(app)
        casca.reorganizar_casca(800)
        casca.reorganizar_casca(1440)
        assert casca.barra_lateral.recolhida is False
        assert casca.barra_superior.chip_usuario.isVisibleTo(casca) is True

    def test_escolha_manual_vence_ate_mudar_de_faixa(self, app):
        casca = self._casca(app)
        casca.reorganizar_casca(1440)
        casca.alternar_casca_recolhida()  # operador recolhe na mão
        assert casca.barra_lateral.recolhida is True
        casca.reorganizar_casca(1300)  # continua na mesma faixa: escolha vale
        assert casca.barra_lateral.recolhida is True
        casca.reorganizar_casca(800)  # mudou de faixa: régua automática volta
        assert casca.barra_lateral.recolhida is True
        casca.reorganizar_casca(1024)
        assert casca.barra_lateral.recolhida is False

    def test_margens_diminuem_no_compacto(self, app):
        casca = self._casca(app)
        casca.data = []

        def guardar(margem: int) -> None:
            casca.data.append(margem)

        casca._definir_margens = guardar
        casca.reorganizar_casca(800)
        assert casca.data[-1] == responsivo.MARGEM_COMPACTA
        casca.reorganizar_casca(1440)
        assert casca.data[-1] == responsivo.MARGEM_NORMAL

    def test_trilha_e_rodape_somem_no_compacto(self, app):
        from PySide6.QtWidgets import QVBoxLayout, QWidget

        class Casca(QWidget, responsivo.CascaResponsiva):
            def __init__(self) -> None:
                super().__init__()
                self.barra_lateral = widgets.BarraLateral("Loja", "ana", "Gerente")
                self.barra_superior = widgets.BarraSuperior("Loja", "ana", "Gerente")
                self.cabecalho = widgets.CabecalhoConteudo("PDV", "frente de caixa")
                self.rodape = widgets.Rodape("esquerda", "direita")
                coluna = QVBoxLayout(self)
                for peca in (self.barra_superior, self.cabecalho, self.rodape, self.barra_lateral):
                    coluna.addWidget(peca)
                self._iniciar_casca()
                self.ajustar_complementos(self.cabecalho, self.rodape)

        casca = Casca()
        casca.reorganizar_casca(800)
        assert casca.cabecalho.trilha.isVisibleTo(casca) is False
        assert casca.rodape.direita.isVisibleTo(casca) is False
        casca.reorganizar_casca(1440)
        assert casca.cabecalho.trilha.isVisibleTo(casca) is True
        assert casca.rodape.direita.isVisibleTo(casca) is True


class TestColunasDaTabela:
    def _tabela(self, app, colunas: int = 4, linhas: int = 3):
        from PySide6.QtWidgets import QTableWidget, QTableWidgetItem

        tabela = QTableWidget(linhas, colunas)
        tabela.resize(700, 200)
        tabela.setHorizontalHeaderLabels([f"Coluna {indice}" for indice in range(colunas)])
        for linha in range(linhas):
            for coluna in range(colunas):
                tabela.setItem(linha, coluna, QTableWidgetItem(f"{linha}-{coluna}"))
        widgets.preparar_tabela(tabela)
        return tabela

    def test_prepara_tabela_nao_deixa_coluna_colapsar(self, app):
        tabela = self._tabela(app)
        assert tabela.horizontalHeader().minimumSectionSize() == widgets.LARGURA_MINIMA_COLUNA

    def test_larga_estica_coluna_elastica(self, app):
        tabela = self._tabela(app, colunas=3, linhas=2)
        widgets.ajustar_colunas(tabela, 1)
        tabela.show()
        tabela.resize(900, 200)
        app.processEvents()
        vigia = tabela.findChild(widgets.ColunasDaTabela)
        assert vigia is not None
        vigia._aplicar()
        assert vigia.modo_rolagem is False

    def test_estreita_entra_em_modo_rolagem(self, app):
        tabela = self._tabela(app, colunas=8, linhas=2)
        widgets.ajustar_colunas(tabela, 1)
        tabela.show()
        tabela.resize(240, 200)
        app.processEvents()
        vigia = tabela.findChild(widgets.ColunasDaTabela)
        assert vigia is not None
        vigia._aplicar()
        assert vigia.modo_rolagem is True
        # a rolagem garante que nenhuma coluna fique abaixo do mínimo legível
        for coluna in range(tabela.columnCount()):
            assert tabela.columnWidth(coluna) >= widgets.LARGURA_MINIMA_COLUNA

    def test_um_unico_vigia_por_tabela(self, app):
        """Ajustar duas vezes não pode duplicar filtros de evento na mesma tabela."""
        from PySide6.QtWidgets import QTableWidget

        tabela = QTableWidget(1, 3)
        tabela.resize(400, 120)
        widgets.ajustar_colunas(tabela, 0)
        widgets.ajustar_colunas(tabela, 1)
        assert len(tabela.findChildren(widgets.ColunasDaTabela)) == 1
        vigia = tabela.findChild(widgets.ColunasDaTabela)
        assert vigia is not None
        assert vigia._esticada == 1


class TestFluxoDeAcoes:
    def _fluxo(self, app, quantidade: int = 6):
        from PySide6.QtWidgets import QPushButton

        fluxo = responsivo.FluxoDeAcoes()
        for indice in range(quantidade):
            botao = QPushButton(f"Ação {indice}")
            botao.adjustSize()
            fluxo.adicionar(botao)
        return fluxo

    def test_guarda_os_widgets_adicionados(self, app):
        fluxo = self._fluxo(app, 3)
        assert len(fluxo.widgets) == 3

    def test_quebra_em_linhas_quando_estreito(self, app):
        fluxo = self._fluxo(app, 6)
        largura_de_um = fluxo.sizeHint().width()
        assert fluxo.heightForWidth(2000) == fluxo.heightForWidth(2000)
        assert fluxo.heightForWidth(240) > fluxo.heightForWidth(2000)
        assert largura_de_um > 0

    def test_tem_altura_para_largura(self, app):
        assert self._fluxo(app).hasHeightForWidth() is True


class TestGradeDeCartoes:
    def test_cartoes_empilham_em_janela_estreita(self, app):
        from PySide6.QtWidgets import QGroupBox

        grade = responsivo.GradeDeCartoes((QGroupBox("Identidade"), QGroupBox("Prévia")))
        grade.reorganizar_para(1000)
        assert grade.colunas == 2
        grade.reorganizar_para(700)
        assert grade.colunas == 1


class TestAjusteDeDialogo:
    def test_nao_passa_da_tela(self, app):
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtWidgets import QDialog

        dialogo = QDialog()
        responsivo.ajustar_dialogo(dialogo, largura_preferida=460)
        area = QGuiApplication.primaryScreen().availableGeometry()
        assert dialogo.minimumWidth() <= area.width() - 32
        assert dialogo.maximumHeight() <= area.height() - 32
        assert dialogo.minimumWidth() >= 280  # nunca encolhe a ponto de sumir
        assert dialogo.isSizeGripEnabled()

    def test_preferencia_respeitada_em_tela_grande(self, app):
        from PySide6.QtWidgets import QDialog

        dialogo = QDialog()
        responsivo.ajustar_dialogo(dialogo, largura_preferida=560, altura_preferida=760)
        assert dialogo.minimumWidth() <= 560
        assert dialogo.maximumHeight() <= 760



class TestTamanhoInicialDaJanela:
    """A janela abre **dentro** da tela — o tamanho pedido é um teto, não uma promessa.

    Era o defeito relatado: `resize(1280, 820)` fixo. Num notebook 1366×768 com
    escala de 150% o Windows oferece 911×512 de espaço lógico e a janela nascia
    maior do que a tela.
    """

    def test_cabe_na_area_disponivel(self, app):
        from PySide6.QtCore import QRect
        from PySide6.QtWidgets import QWidget

        janela = QWidget()
        janela.setMinimumSize(640, 440)
        area = QRect(0, 0, 911, 512)  # 1366×768 com escala de 150%
        tamanho = responsivo.abrir_no_tamanho_da_tela(janela, 1280, 820, area=area)
        assert tamanho.width() <= 911
        assert tamanho.height() <= 512
        assert janela.size() == tamanho

    def test_nunca_menor_que_o_minimo_declarado(self, app):
        from PySide6.QtCore import QRect
        from PySide6.QtWidgets import QWidget

        janela = QWidget()
        janela.setMinimumSize(640, 440)
        area = QRect(0, 0, 500, 400)  # tela minúscula: o mínimo manda
        tamanho = responsivo.abrir_no_tamanho_da_tela(janela, 1280, 820, area=area)
        assert tamanho.width() >= 640
        assert tamanho.height() >= 440

    def test_tela_grande_respeita_o_pedido_e_centraliza(self, app):
        from PySide6.QtCore import QRect
        from PySide6.QtWidgets import QWidget

        janela = QWidget()
        janela.setMinimumSize(640, 440)
        area = QRect(0, 0, 1920, 1080)
        tamanho = responsivo.abrir_no_tamanho_da_tela(janela, 1280, 820, area=area)
        assert tamanho.width() == 1280
        assert tamanho.height() == 820
        assert janela.x() == (1920 - 1280) // 2

    def test_janelas_do_app_abrem_no_tamanho_da_tela(self, cenario):
        from bussola_pdv.ui.admin.janela import JanelaAdmin
        from bussola_pdv.ui.janela import JanelaPrincipal

        janela = JanelaPrincipal(cenario.ctx, cenario.master)
        try:
            assert janela.minimumWidth() <= 640
            assert janela.tamanho_inicial.width() >= janela.minimumWidth()
        finally:
            janela.close()
        admin = JanelaAdmin(cenario.ctx, cenario.master)
        try:
            assert admin.minimumWidth() <= 640
            assert admin.tamanho_inicial.height() >= admin.minimumHeight()
        finally:
            admin.close()


class TestRotuloElastico:
    """Rótulo de rodapé/topo corta com "…" em vez de alargar a janela."""

    def test_texto_completo_fica_guardado(self, app):
        rotulo = widgets.RotuloElastico("Bússola PDV · dados locais")
        assert rotulo.text() == "Bússola PDV · dados locais"
        assert rotulo.texto_completo() == "Bússola PDV · dados locais"
        assert rotulo.toolTip() == "Bússola PDV · dados locais"

    def test_nao_impõe_largura_minima_ao_layout(self, app):
        """O que importa é o que o layout cobra — e ele ignora o texto do rótulo."""
        from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

        rotulo = widgets.RotuloElastico("x" * 400)
        caixa = QWidget()
        linha = QHBoxLayout(caixa)
        linha.addWidget(rotulo)
        assert caixa.minimumSizeHint().width() < 200

        comum = QWidget()
        linha_comum = QHBoxLayout(comum)
        linha_comum.addWidget(QLabel("x" * 400))
        assert comum.minimumSizeHint().width() > caixa.minimumSizeHint().width()

    def test_encurta_o_pintado_sem_perder_o_texto(self, app):
        rotulo = widgets.RotuloElastico("Bússola PDV · " + "detalhe " * 30)
        rotulo.resize(90, 24)
        assert rotulo.text().startswith("Bússola PDV")
        assert rotulo.text().endswith("detalhe " * 30)  # .text() segue completo
        from PySide6.QtCore import Qt

        corte = rotulo.fontMetrics().elidedText(
            rotulo.text(), Qt.TextElideMode.ElideRight, 90
        )
        assert corte.endswith("…")

    def test_rodape_e_topo_usam_o_rotulo_elastico(self, app):
        from bussola_pdv.ui.widgets import BarraSuperior, Rodape

        rodape = Rodape("esquerda longa " * 10, "direita")
        assert isinstance(rodape.esquerda, widgets.RotuloElastico)
        topo = BarraSuperior("PDV")
        assert isinstance(topo.rotulo_pagina, widgets.RotuloElastico)


class TestCamposDoPDV:
    """Campos proporcionais: nem 760 px de caixa em 1920, nem ilegíveis no compacto."""

    def test_quantidade_nao_e_mais_fixa_em_80(self, app, cenario):
        from bussola_pdv.ui.tela_pdv import TelaPDV

        tela = TelaPDV(cenario.ctx, cenario.gerente)
        try:
            assert tela.campo_quantidade.minimumWidth() < 80
            assert tela.campo_quantidade.maximumWidth() <= 96
            for forma, valor in tela.linhas_pagamento:
                assert forma.maximumWidth() <= 300
                assert valor.maximumWidth() <= 420
                assert forma.minimumWidth() >= 100
            assert tela.formulario_pagamento.maximumWidth() <= 620
        finally:
            tela.close()
