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
    razao_contraste,
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
