"""Testes da casca visual inspirada no AdminLTE.

O que se verifica aqui é o que a captura não prova: ícones existem e são coloridos,
cartões e indicadores guardam o que recebem, a sidebar recolhe de verdade, a pilha
de páginas assume a altura da página atual e a folha de estilo carrega a paleta.
"""

from __future__ import annotations

import base64
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip(
    "PySide6.QtWidgets", exc_type=ImportError, reason="PySide6 ou libs do Qt ausentes"
)

from bussola_pdv.dominio.marca import Paleta
from bussola_pdv.ui import icones, widgets
from bussola_pdv.ui.tema import cores_tonalidade, folha_estilo, folha_estilo_da_marca

pytestmark = pytest.mark.ui


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication(["teste-adminlte"])


class TestIcones:
    def test_todos_os_modulos_tem_icone(self):
        from bussola_pdv.ui.janela import DETALHES_MODULO

        for icone_modulo, _descricao in DETALHES_MODULO.values():
            assert icone_modulo in icones.DESENHOS, icone_modulo

    def test_svg_recebe_a_cor_pedida(self):
        marcação = icones.svg("pdv", "#123456")
        assert 'stroke="#123456"' in marcação
        assert marcação.startswith("<svg")

    def test_nome_desconhecido_devolve_icone_vazio(self, app):
        assert icones.icone("inexistente").isNull()
        assert icones.pixmap("inexistente").isNull()  # nunca um quadrado invisível

    def test_pixmap_tem_o_tamanho_pedido(self, app):
        pix = icones.pixmap("caixa", "#0D6EFD", 22)
        assert (pix.width(), pix.height()) == (22, 22)
        assert not pix.isNull()

    def test_renderizacao_e_cacheada(self, app):
        assert icones.pixmap("vendas", "#0D6EFD", 18).cacheKey() == icones.pixmap(
            "vendas", "#0D6EFD", 18
        ).cacheKey()


class TestWidgets:
    def test_selo_troca_de_tonalidade(self, app):
        selo = widgets.Selo("ativo", "sucesso")
        assert selo.property("tonalidade") == "sucesso"
        selo.definir("inativo", "claro")
        assert selo.text() == "inativo"
        assert selo.property("tonalidade") == "claro"
        selo.definir_tonalidade("inexistente")
        assert selo.property("tonalidade") == "claro"

    def test_caixa_info_mostra_valor_e_muda_de_cor(self, app):
        caixa = widgets.CaixaInfo("Vendas", "0", "vendas", "claro")
        assert caixa.valor.text() == "0"
        caixa.definir("12", "cupons de hoje", "sucesso")
        assert caixa.valor.text() == "12"
        assert caixa.legenda.text() == "cupons de hoje"
        assert caixa.property("tonalidade") == "sucesso"
        assert not caixa.icone.pixmap().isNull()

    def test_cartao_guarda_titulo_corpo_e_ferramentas(self, app):
        from PySide6.QtWidgets import QLabel

        cartao = widgets.Cartao("Catálogo", "saldo corrente")
        cartao.adicionar(QLabel("conteúdo"))
        cartao.adicionar_ferramenta(widgets.Selo("16"))
        assert cartao.titulo.text() == "Catálogo"
        assert cartao.subtitulo.text() == "saldo corrente"
        assert cartao.corpo.count() == 1
        # `ferramentas` é um fluxo (quebra de linha), não um QHBoxLayout
        assert len(cartao.ferramentas.widgets) == 1

    def test_ferramenta_escondida_continua_escondida_no_fluxo(self, app):
        """`setVisible(False)` não pode ser desfeito ao entrar no cabeçalho.

        As ferramentas do cartão vivem num `FluxoDeAcoes`, que reparenta o widget;
        reparentar esconde o filho e o `show()` do fluxo reexibiria até o botão
        proibido — e os testes de permissão passaram a ver "Exportar" para o
        atendente.
        """
        from PySide6.QtWidgets import QPushButton

        cartao = widgets.Cartao("Clientes")
        proibido = QPushButton("Exportar")
        proibido.setVisible(False)
        cartao.adicionar_ferramenta(proibido)

        assert proibido.isHidden()
        assert cartao.ferramentas.widgets == [proibido]

    def test_ferramentas_quebram_de_linha_em_cartao_estreito(self, app):
        """Duas ferramentas lado a lado não impõem a soma das larguras ao cartão."""
        from PySide6.QtWidgets import QPushButton

        cartao = widgets.Cartao("Vendas")
        for rotulo in ("Exportar Excel/PDF", "Imprimir"):
            cartao.adicionar_ferramenta(QPushButton(rotulo))
        cartao.show()
        fluxo = cartao.ferramentas
        soma = sum(acao.sizeHint().width() for acao in fluxo.widgets)
        assert fluxo.minimumSizeHint().width() < soma
        fluxo.resize(160, 100)
        fluxo._recalcular()

        alturas = {acao.y() for acao in fluxo.widgets}
        assert len(alturas) == 2, alturas
        assert fluxo.minimumSizeHint().width() < 300
        cartao.deleteLater()

    def test_cabecalho_monta_a_trilha(self, app):
        cabecalho = widgets.CabecalhoConteudo("PDV", "frente de caixa")
        cabecalho.definir(trilha=["Início", "Administração", "Usuários"])
        assert cabecalho.titulo.text() == "PDV"
        assert cabecalho.trilha.text() == "Início  ›  Administração  ›  Usuários"

    def test_rodape_tem_dois_lados(self, app):
        rodape = widgets.Rodape("esquerda", "direita")
        assert rodape.esquerda.text() == "esquerda"
        assert rodape.direita.text() == "direita"

    def test_iniciais_resistem_a_nomes_estranhos(self):
        assert widgets.iniciais("Carla Atendente") == "CA"
        assert widgets.iniciais("master") == "MA"
        assert widgets.iniciais("Dora Proprietária") == "DP"
        assert widgets.iniciais("   ") == "?"


class TestBarraLateral:
    def _barra(self) -> widgets.BarraLateral:
        barra = widgets.BarraLateral("Loja Teste", "Carla Atendente", "Atendente")
        barra.definir_modulos(
            [
                widgets.EntradaNavegacao("PDV", "PDV", "pdv"),
                widgets.EntradaNavegacao("Caixa", "Caixa", "caixa"),
                widgets.EntradaNavegacao("Administração", "Administração", "administracao"),
            ]
        )
        return barra

    def test_lista_modulos_com_chave_estavel(self, app):
        barra = self._barra()
        assert barra.rotulos() == ["PDV", "Caixa", "Administração"]
        assert barra.chave_do_indice(1) == "Caixa"
        assert barra.indice_da_chave("Administração") == 2
        assert barra.indice_da_chave("Inexistente") == -1
        assert barra.lista.count() == 3

    def test_emite_o_modulo_escolhido(self, app):
        barra = self._barra()
        recebidos: list[str] = []
        barra.modulo_escolhido.connect(recebidos.append)
        barra.lista.setCurrentRow(1)
        assert recebidos == ["Caixa"]

    def test_recolher_esconde_rotulos_e_encolhe(self, app):
        barra = self._barra()
        largura_aberta = barra.width()
        barra.alternar_recolhida()
        assert barra.recolhida is True
        assert barra.width() == widgets.LARGURA_BARRA_RECOLHIDA < largura_aberta
        assert barra.lista.item(0).text() == ""
        assert not barra.painel_usuario.isVisible()
        barra.alternar_recolhida()
        assert barra.lista.item(0).text() == "PDV"
        assert barra.width() == widgets.LARGURA_BARRA_LATERAL

    def test_identidade_acompanha_a_marca(self, app):
        barra = self._barra()
        barra.atualizar_identidade("Mercado Bom Preço", "Ana Administradora", "Admin")
        assert barra.rotulo_marca.text() == "Mercado Bom Preço"
        assert barra.avatar.text() == "AA"
        assert barra.rotulo_perfil.text() == "Admin"

    def test_monograma_e_o_logo_e_nao_a_inicial(self, app):
        """v0.11.0: o quadrado do menu mostra o logo oficial, não a letra da loja."""
        barra = self._barra()
        barra.atualizar_identidade("Mercado Bom Preço", "Ana Administradora", "Admin")
        pixmap = barra.monograma.pixmap()
        assert not pixmap.isNull()
        assert barra.monograma.text() == ""  # nada de letra desenhada por cima
        # cabe no quadrado de 30 px, com folga
        lado = pixmap.width() / pixmap.devicePixelRatio()
        assert 0 < lado <= widgets.LADO_MONOGRAMA

    def test_simbolo_do_menu_usa_a_cor_primaria(self, app):
        """O quadrado branco do menu fica com o logo na cor da loja (ADR-028)."""
        barra = widgets.BarraLateral(
            "Loja Teste", "Carla Atendente", "Atendente", Paleta(primaria="#B5179E")
        )
        imagem = barra.monograma.pixmap().toImage()
        cores = {
            (imagem.pixelColor(x, y).red(), imagem.pixelColor(x, y).green())
            for y in range(imagem.height())
            for x in range(imagem.width())
            if imagem.pixelColor(x, y).alpha() == 255
        }
        assert cores == {(0xB5, 0x17)}  # exatamente a primária, sem o azul do arquivo

    def test_logo_da_loja_substitui_o_oficial_no_menu(self, app):
        from bussola_pdv.ui.identidade import caminho_do_logo

        barra = self._barra()
        dados = base64.b64encode(caminho_do_logo("logo_comercial.png").read_bytes()).decode()
        barra.definir_logo(f"data:image/png;base64,{dados}")
        assert not barra.monograma.pixmap().isNull()
        assert barra.monograma.toolTip() == "Logo da loja"
        barra.definir_logo("")
        assert barra.monograma.toolTip().startswith("Bússola PDV")


class TestBarraSuperior:
    def test_troca_pagina_e_usuario(self, app):
        barra = widgets.BarraSuperior("Loja · PDV", "Carla", "Atendente")
        barra.definir_pagina("Loja · Caixa")
        barra.definir_usuario("Ana", "Admin")
        assert barra.rotulo_pagina.text() == "Loja · Caixa"
        assert barra.chip_usuario.text() == "Ana · Admin"
        assert not barra.botao_menu.icon().isNull()

    def test_botao_de_menu_emite_o_pedido(self, app):
        barra = widgets.BarraSuperior()
        pedidos: list[bool] = []
        barra.recolher_pedido.connect(lambda: pedidos.append(True))
        barra.botao_menu.click()
        assert len(pedidos) == 1


class TestPilhaDePaginas:
    def test_altura_segue_a_pagina_atual(self, app):
        from PySide6.QtWidgets import QLabel

        pilha = widgets.PilhaDePaginas()
        baixa = QLabel("baixa")
        baixa.setMinimumHeight(40)
        alta = QLabel("alta")
        alta.setMinimumHeight(300)
        pilha.addWidget(baixa)
        pilha.addWidget(alta)

        pilha.setCurrentIndex(0)
        assert pilha.minimumSizeHint().height() <= 60
        pilha.setCurrentIndex(1)
        assert pilha.minimumSizeHint().height() >= 300


class TestTemaAdminLTE:
    def test_folha_traz_a_linguagem_de_cartoes(self):
        css = folha_estilo()
        for marca_css in (
            "#barraLateral",
            "#barraSuperior",
            "#cartao",
            "#caixaInfo",
            "#selo",
            "#rodape",
            "#tituloConteudo",
            "QListWidget#navegacao::item:selected",
        ):
            assert marca_css in css, marca_css

    def test_folha_usa_a_paleta_recebida(self):
        paleta = Paleta(primaria="#0B7285", primaria_escura="#17323A")
        css = folha_estilo(paleta)
        assert paleta.primaria in css
        assert paleta.primaria_escura in css
        assert paleta.fundo in css

    def test_folha_da_marca_mistura_cor_e_fonte(self):
        from bussola_pdv.dominio.marca import Marca

        marca = Marca(nome_fantasia="Loja", fonte="Verdana").com_cores(primaria="#7A1F2B")
        css = folha_estilo_da_marca(marca)
        assert "#7A1F2B" in css
        assert "Verdana" in css

    def test_tonalidades_apontam_para_a_paleta(self):
        paleta = Paleta()
        mapa = cores_tonalidade(paleta)
        assert mapa["primaria"] == paleta.primaria
        assert mapa["sucesso"] == paleta.sucesso
        assert mapa["erro"] == paleta.erro
        assert mapa["info"] == paleta.secundaria

    def test_folha_nunca_deixa_texto_de_botao_ilegivel(self):
        css = folha_estilo(Paleta(primaria="#F0F0F0", texto="#111111"))
        assert "color: #111111" in css


class TestCascaDaJanela:
    def test_topo_lateral_e_rodape_estao_na_janela(self, app, cenario):
        from bussola_pdv.ui.janela import JanelaPrincipal

        janela = JanelaPrincipal(cenario.ctx, cenario.master)
        try:
            assert janela.barra_lateral.isVisibleTo(janela) or janela.barra_lateral.parent() is not None
            assert janela.barra_superior.rotulo_pagina.text().endswith("PDV")
            assert "pré-alfa" in janela.rodape.direita.text()
            assert janela.cabecalho.titulo.text() == "PDV"
            assert janela.cabecalho.trilha.text() == "Início  ›  PDV"
        finally:
            janela.close()

    def test_botao_de_menu_recolhe_a_sidebar(self, app, cenario):
        from bussola_pdv.ui.janela import JanelaPrincipal

        janela = JanelaPrincipal(cenario.ctx, cenario.master)
        try:
            # O tamanho inicial vem da tela (e, no offscreen, ela é pequena: a janela
            # abre na faixa compacta, com a sidebar recolhida). Aqui a intenção é
            # testar o botão, então a janela é colocada numa largura ampla.
            janela.show()
            janela.resize(1400, 900)
            app.processEvents()
            assert janela.classe_da_casca == "ampla"
            assert janela.barra_lateral.recolhida is False
            janela.barra_superior.botao_menu.click()
            assert janela.barra_lateral.recolhida is True
            janela.barra_superior.botao_menu.click()
            assert janela.barra_lateral.recolhida is False
        finally:
            janela.close()

    def test_trocar_de_modulo_atualiza_titulo_e_trilha(self, app, cenario):
        from bussola_pdv.ui.janela import JanelaPrincipal

        janela = JanelaPrincipal(cenario.ctx, cenario.master)
        try:
            janela._selecionar("Produtos")
            assert janela.cabecalho.titulo.text() == "Produtos"
            assert janela.cabecalho.trilha.text() == "Início  ›  Produtos"
            assert "Produtos" in janela.barra_superior.rotulo_pagina.text()
            assert janela.pilha.currentIndex() == janela.modulos.index("Produtos")
        finally:
            janela.close()

    def test_modulo_nao_implementado_vira_cartao(self, app, cenario):
        from bussola_pdv.ui.janela import JanelaPrincipal

        janela = JanelaPrincipal(cenario.ctx, cenario.master)
        try:
            # Clientes virou tela de verdade na v0.6.0; Entradas é o placeholder.
            janela._selecionar("Entradas")
            pagina = janela.pilha.currentWidget()
            assert pagina is not None
            cartoes = list(pagina.findChildren(widgets.Cartao))
            assert len(cartoes) == 1
            assert "não implementado" in cartoes[0].titulo.text()
        finally:
            janela.close()
