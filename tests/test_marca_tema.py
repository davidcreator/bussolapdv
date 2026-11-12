"""Marca da loja, paleta, contraste e persistência do tema."""

from __future__ import annotations

import base64

import pytest

from bussola_pdv.aplicacao.marca import ServicoMarca
from bussola_pdv.dominio.erros import AutorizacaoNegada, ErroValidacao
from bussola_pdv.dominio.marca import (
    PALETAS_PADRAO,
    PRESET_PERSONALIZADO,
    Marca,
    Paleta,
    garantir_contraste,
    razao_contraste,
    tinta_sobre,
)
from bussola_pdv.ui.tema import folha_estilo, folha_estilo_da_marca

pytestmark = pytest.mark.integracao


class TestPaleta:
    def test_paleta_padrao_tem_contraste_adequado(self):
        assert Paleta().avisos() == []
        assert Paleta().contraste_texto_superficie >= 4.5

    def test_cor_invalida_e_recusada(self):
        for valor in ("vermelho", "#12345", "#GGGGGG", "rgb(0,0,0)"):
            with pytest.raises(ErroValidacao):
                Paleta(primaria=valor)

    def test_cores_sao_normalizadas_em_maiuscula(self):
        assert Paleta(primaria="#0f7c86").primaria == "#0F7C86"

    def test_paleta_sem_contraste_gera_aviso(self):
        ruim = Paleta(texto="#EEEEEE", superficie="#FFFFFF")
        avisos = ruim.avisos()
        assert any("Contraste texto/superfície" in aviso for aviso in avisos)
        assert ruim.contraste_texto_superficie < 4.5

    def test_razao_de_contraste_conhecida(self):
        assert razao_contraste("#FFFFFF", "#000000") == 21.0
        assert razao_contraste("#FFFFFF", "#FFFFFF") == 1.0

    def test_com_troca_apenas_o_token_informado(self):
        base = Paleta()
        nova = base.com(secundaria="#123456")
        assert nova.secundaria == "#123456"
        assert nova.primaria == base.primaria

    def test_presets_disponiveis_e_validos(self):
        assert {"BUSSOLA", "GRAFITE", "ESMERALDA", "NOTURNO"} <= set(PALETAS_PADRAO)
        for paleta in PALETAS_PADRAO.values():
            assert paleta.contraste_texto_superficie >= 4.5, paleta


class TestMarca:
    def test_marca_padrao_e_valida(self):
        marca = Marca.padrao()
        assert marca.nome_fantasia
        assert marca.preset == "BUSSOLA"
        assert marca.avisos == []

    def test_nome_obrigatorio(self):
        with pytest.raises(ErroValidacao):
            Marca(nome_fantasia="   ")

    def test_nome_recusa_caracteres_de_controle(self):
        for nome in ("Loja<script>", "Loja; QWidget{background:red}", "Loja\x00"):
            with pytest.raises(ErroValidacao):
                Marca(nome_fantasia=nome)

    def test_fonte_recusa_injecao_de_qss(self):
        with pytest.raises(ErroValidacao):
            Marca(fonte='Arial; } QWidget { background: red')

    def test_preset_desconhecido_e_recusado(self):
        with pytest.raises(ErroValidacao):
            Marca(preset="ARCO-IRIS")

    def test_preset_personalizado_e_aceito(self):
        marca = Marca().com(preset=PRESET_PERSONALIZADO)
        assert marca.preset == PRESET_PERSONALIZADO

    def test_com_cores_marca_como_personalizado(self):
        marca = Marca().com_cores(primaria="#7A1F2B")
        assert marca.preset == PRESET_PERSONALIZADO
        assert marca.paleta.primaria == "#7A1F2B"

    def test_troca_de_preset_troca_a_paleta(self):
        marca = Marca().com_preset("NOTURNO")
        assert marca.paleta == PALETAS_PADRAO["NOTURNO"]
        assert marca.paleta.fundo != PALETAS_PADRAO["BUSSOLA"].fundo

    def test_ida_e_volta_pelos_parametros(self):
        original = Marca(
            nome_fantasia="Mercado São João",
            razao_social="São João Comércio LTDA",
            cnpj="11222333000181",
            telefone="(11) 4002-8922",
            endereco="Rua das Flores, 100",
            preset="ESMERALDA",
            paleta=PALETAS_PADRAO["ESMERALDA"].com(erro="#AA2233"),
        )
        voltou = Marca.de_parametros(original.a_parametros())
        assert voltou.nome_fantasia == original.nome_fantasia
        assert voltou.paleta.erro == "#AA2233"
        assert voltou.preset == "ESMERALDA"

    def test_parametros_corrompidos_nao_derrubam_a_aplicacao(self):
        valores = {
            "marca.nome_fantasia": "",  # inválido
            "marca.fonte": "; } QWidget { color: red }",  # inválido
            "tema.primaria": "roxo",  # inválido
            "marca.preset": "INEXISTENTE",
        }
        marca = Marca.de_parametros(valores)
        assert marca.nome_fantasia == Marca.padrao().nome_fantasia
        assert marca.paleta.primaria == Paleta().primaria

    def test_logo_precisa_ser_png_real(self):
        falso = "data:image/png;base64," + base64.b64encode(b"GIF89a...").decode()
        with pytest.raises(ErroValidacao):
            Marca(logo_data_uri=falso)

    def test_logo_png_valido_e_aceito(self):
        png = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64).decode()
        marca = Marca(logo_data_uri=f"data:image/png;base64,{png}")
        assert marca.logo_data_uri.startswith("data:image/png;base64,")


class TestServicoMarca:
    def test_leitura_publica_vem_do_banco(self, cenario):
        servico = ServicoMarca(cenario.ctx)
        assert servico.obter().nome_fantasia == Marca.padrao().nome_fantasia
        assert servico.obter().paleta == Paleta()

    def test_salvar_exige_permissao(self, cenario):
        servico = ServicoMarca(cenario.ctx)
        with pytest.raises(AutorizacaoNegada):
            servico.salvar(cenario.operador, Marca(nome_fantasia="Invasão"))

    def test_admin_altera_marca_e_tema(self, cenario):
        servico = ServicoMarca(cenario.ctx)
        nova = Marca(nome_fantasia="Mercado Bom Preço").com_preset("ESMERALDA")
        salva = servico.salvar(cenario.admin, nova)
        assert salva.nome_fantasia == "Mercado Bom Preço"
        assert salva.preset == "ESMERALDA"
        assert servico.obter().paleta.primaria == PALETAS_PADRAO["ESMERALDA"].primaria

    def test_nome_sincroniza_parametro_legado(self, cenario):
        ServicoMarca(cenario.ctx).salvar(cenario.admin, Marca(nome_fantasia="Loja Nova"))
        assert cenario.ctx.parametros.obter("empresa.nome") == "Loja Nova"

    def test_alteracoes_entram_na_auditoria(self, cenario):
        servico = ServicoMarca(cenario.ctx)
        servico.salvar(cenario.admin, Marca(nome_fantasia="Loja Auditada").com_preset("GRAFITE"))
        eventos = [evento.acao.value for evento in cenario.ctx.auditoria.listar(limite=5)]
        assert "MARCA_ALTERADA" in eventos
        assert "TEMA_ALTERADO" in eventos
        assert cenario.ctx.auditoria.verificar().integro

    def test_trocar_so_o_nome_nao_gera_evento_de_tema(self, cenario):
        servico = ServicoMarca(cenario.ctx)
        servico.salvar(cenario.admin, Marca(nome_fantasia="Só o Nome"))
        eventos = [evento.acao.value for evento in cenario.ctx.auditoria.listar(limite=5)]
        assert "MARCA_ALTERADA" in eventos
        assert "TEMA_ALTERADO" not in eventos

    def test_sem_mudanca_nao_gera_evento(self, cenario):
        servico = ServicoMarca(cenario.ctx)
        antes = len(cenario.ctx.auditoria.listar(limite=500))
        servico.salvar(cenario.admin, servico.obter())
        assert len(cenario.ctx.auditoria.listar(limite=500)) == antes

    def test_permissao_de_tema_pode_ser_separada_da_de_marca(self, cenario):
        from bussola_pdv.aplicacao.permissoes import ServicoPermissoes
        from bussola_pdv.dominio.usuario import Acao, Perfil

        servico_permissoes = ServicoPermissoes(cenario.ctx)
        servico_permissoes.definir(cenario.master, Perfil.GERENTE, Acao.MARCA_GERENCIAR, True)
        gerente = cenario.ctx.usuarios.por_id(cenario.gerente.id)
        servico = ServicoMarca(cenario.ctx)
        assert servico.salvar(gerente, Marca(nome_fantasia="Nome pelo Gerente")).nome_fantasia
        with pytest.raises(AutorizacaoNegada):  # tema segue restrito
            servico.salvar(gerente, servico.obter().com_preset("NOTURNO"))

    def test_restaurar_padrao(self, cenario):
        servico = ServicoMarca(cenario.ctx)
        servico.salvar(cenario.admin, Marca(nome_fantasia="Temporária").com_preset("NOTURNO"))
        restaurada = servico.restaurar_padrao(cenario.admin)
        assert restaurada.nome_fantasia == Marca.padrao().nome_fantasia
        assert restaurada.preset == "BUSSOLA"


class TestContrasteDasCores:
    """Relato de campo: áreas com texto ilegível (Windows em modo escuro e
    amostras de cor com tinta branca sobre amarelo)."""

    def test_tinta_sobre_amarelo_e_escura(self):
        # #FFC107 com branco dava 1,63:1 — na prática, texto invisível.
        assert razao_contraste("#FFFFFF", "#FFC107") < 2.0
        assert tinta_sobre("#FFC107") == "#1F1F1F"
        assert razao_contraste(tinta_sobre("#FFC107"), "#FFC107") >= 4.5

    def test_tinta_sobre_azul_escuro_e_branca(self):
        assert tinta_sobre("#0D6EFD") == "#FFFFFF"
        assert tinta_sobre("#343A40") == "#FFFFFF"

    def test_tinta_sobre_verde_agua_escurece_o_texto(self):
        assert tinta_sobre("#17A2B8") == "#1F1F1F"  # branco dava 3,04:1

    @pytest.mark.parametrize(
        "cor",
        ["#6C757D", "#9AA0A6", "#B0B0B0", "#FFC107", "#ADB5BD"],
    )
    def test_texto_suave_claro_e_corrigido_ate_a_legibilidade(self, cor):
        ajustada = garantir_contraste(cor, "#F4F6F9")
        assert razao_contraste(ajustada, "#F4F6F9") >= 4.5

    def test_garantir_contraste_nao_mexe_no_que_ja_passa(self):
        assert garantir_contraste("#212529", "#F4F6F9") == "#212529"

    def test_fundo_escuro_clareia_o_texto(self):
        assert razao_contraste(garantir_contraste("#555555", "#101010"), "#101010") >= 4.5

    def test_folha_usa_o_texto_suave_corrigido(self):
        escura = folha_estilo(Paleta(texto_suave="#B0B0B0"))
        assert "#B0B0B0" not in escura  # a tinta fraca não vai para a tela
        assert f"color: {Paleta().texto_suave}" in folha_estilo()  # ≥ 4,5:1 no fundo

    def test_folha_pinta_o_fundo_da_rolagem(self):
        """Sem isto, o Windows em modo escuro deixava preto atrás dos cartões."""
        css = folha_estilo()
        assert "QScrollArea > QWidget > QWidget { background: #F4F6F9; }" in css
        assert "#pagina, #paginaRolavel { background: #F4F6F9; }" in css

    def test_aviso_quando_o_texto_secundario_ficaria_ilegivel(self):
        paleta = Paleta(texto_suave="#B0B0B0")
        assert any("secundário" in aviso for aviso in paleta.avisos())


class TestPaletaDoQt:
    """A paleta do Qt é fixada pela marca — o tema do Windows não manda."""

    def test_paleta_do_tema_usa_as_cores_da_loja(self):
        from bussola_pdv.ui.tema import paleta_do_tema

        pytest.importorskip("PySide6.QtGui", reason="Qt ausente")
        from PySide6.QtGui import QPalette

        paleta = Paleta(primaria="#0057B7", fundo="#FAFAFA", texto="#101010")
        qt = paleta_do_tema(paleta)
        assert qt.color(QPalette.ColorRole.Window).name().lower() == "#fafafa"
        assert qt.color(QPalette.ColorRole.WindowText).name().lower() == "#101010"
        assert qt.color(QPalette.ColorRole.Highlight).name().lower() == "#0057b7"

    def test_criar_aplicacao_ignora_o_tema_escuro_do_sistema(self):
        pytest.importorskip("PySide6.QtWidgets", reason="Qt ausente")
        import os

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtGui import QColor, QPalette
        from PySide6.QtWidgets import QApplication

        from bussola_pdv.ui.app import criar_aplicacao

        app = criar_aplicacao()
        assert isinstance(app, QApplication)
        # simula o Windows entregando a paleta escura DEPOIS da criação
        escura = QPalette()
        escura.setColor(QPalette.ColorRole.Window, QColor("#202020"))
        escura.setColor(QPalette.ColorRole.Base, QColor("#2B2B2B"))
        app.setPalette(escura)

        from bussola_pdv.ui.app import fixar_aparencia_clara

        fixar_aparencia_clara(app)
        assert app.palette().color(QPalette.ColorRole.Window).name().lower() == "#f4f6f9"
        assert app.palette().color(QPalette.ColorRole.Base).name().lower() == "#ffffff"


class TestFolhaDeEstilo:
    def test_folha_padrao_usa_a_paleta_padrao(self):
        css = folha_estilo()
        assert Paleta().primaria in css
        assert Paleta().secundaria in css

    def test_folha_da_marca_aplica_cor_e_fonte(self):
        marca = Marca(nome_fantasia="Loja", fonte="Verdana").com_preset("NOTURNO")
        css = folha_estilo_da_marca(marca)
        assert marca.paleta.primaria in css
        assert "Verdana" in css

    def test_paleta_clara_mantem_texto_legivel_nos_botoes(self):
        escura = folha_estilo(Paleta(primaria="#F0F0F0", texto="#111111"))
        assert "color: #111111" in escura  # texto escuro sobre botão claro
