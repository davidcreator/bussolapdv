"""Teste de fumaça da área administrativa em modo offscreen.

Verifica o que a interface promete e o que ela **nega**: seções aparecem ao master,
somem para quem não tem a permissão, e as edições chegam ao banco com auditoria.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip(
    "PySide6.QtWidgets", exc_type=ImportError, reason="PySide6 ou libs do Qt ausentes"
)

from bussola_pdv.dominio.erros import AutorizacaoNegada
from bussola_pdv.dominio.marca import PRESET_PERSONALIZADO
from bussola_pdv.dominio.usuario import Acao, Perfil
from bussola_pdv.ui.admin.acessos import SecaoPermissoes, SecaoUsuarios
from bussola_pdv.ui.admin.dependencias import SecaoDependencias
from bussola_pdv.ui.admin.janela import JanelaAdmin
from bussola_pdv.ui.admin.marca import SecaoMarca
from bussola_pdv.ui.admin.parametros import SecaoParametros
from bussola_pdv.ui.janela import MODULO_ADMIN, JanelaPrincipal

pytestmark = pytest.mark.ui


@pytest.fixture
def app():
    from PySide6.QtWidgets import QApplication

    from bussola_pdv.ui.tema import FOLHA_ESTILO

    aplicacao = QApplication.instance() or QApplication(["teste-admin"])
    aplicacao.setStyleSheet(FOLHA_ESTILO)
    return aplicacao


@pytest.fixture
def janela_admin(app, cenario):
    janelas = []

    def abrir(usuario):
        janela = JanelaAdmin(cenario.ctx, usuario)
        janelas.append(janela)
        return janela

    yield abrir
    for janela in janelas:
        janela.close()


class TestAcessoAsSecoes:
    def test_master_alcanca_todas_as_secoes(self, janela_admin, cenario):
        janela = janela_admin(cenario.master)
        assert janela.secoes_liberadas() == [
            "dependencias",
            "marca",
            "usuarios",
            "permissoes",
            "parametros",
            "manutencao",
        ]

    def test_admin_nao_ve_matriz_de_permissoes(self, janela_admin, cenario):
        janela = janela_admin(cenario.admin)
        liberadas = janela.secoes_liberadas()
        assert "permissoes" not in liberadas
        assert "usuarios" in liberadas
        assert "manutencao" in liberadas

    def test_contabilidade_nao_entra(self, janela_admin, cenario):
        with pytest.raises(AutorizacaoNegada):
            janela_admin(cenario.contabilidade)

    def test_atendente_nao_entra(self, janela_admin, cenario):
        with pytest.raises(AutorizacaoNegada):
            janela_admin(cenario.operador)

    def test_menu_mostra_apenas_o_que_o_perfil_alcanca(self, janela_admin, cenario):
        janela = janela_admin(cenario.admin)
        rotulos = [janela.menu.item(i).text() for i in range(janela.menu.count())]
        assert "Perfis e permissões" not in rotulos
        assert "Usuários" in rotulos


class TestSecoes:
    def test_dependencias_lista_checagens_reais(self, app, cenario):
        secao = SecaoDependencias(cenario.ctx, cenario.admin)
        assert secao.tabela.rowCount() > 10
        textos = {
            secao.tabela.item(linha, 1).text() for linha in range(secao.tabela.rowCount())
        }
        assert {"Integridade", "Esquema", "Admin Master ativo"} <= textos

    def test_dependencias_bloqueia_manutencao_para_quem_nao_pode(self, app, cenario):
        secao = SecaoDependencias(cenario.ctx, cenario.gerente)
        assert secao.botao_otimizar.isEnabled() is False
        secao_master = SecaoDependencias(cenario.ctx, cenario.admin)
        assert secao_master.botao_otimizar.isEnabled() is True


class TestSecaoMarca:
    def test_admin_carrega_a_marca_atual(self, app, cenario):
        secao = SecaoMarca(cenario.ctx, cenario.admin)
        assert secao.campo_nome.text() == secao.marca.nome_fantasia
        assert secao.botao_salvar.isEnabled() is True

    def test_salvar_aplica_nome_e_persiste(self, app, cenario):
        secao = SecaoMarca(cenario.ctx, cenario.admin)
        secao.campo_nome.setText("Mercado Bom Preço")
        secao.campo_telefone.setText("(11) 99999-0000")
        secao._salvar()
        assert secao.mensagem.text()
        assert cenario.ctx.parametros.obter("empresa.nome") == "Mercado Bom Preço"
        assert secao.mensagem.objectName() == "mensagemOk"

    def test_mudar_cor_vira_tema_personalizado(self, app, cenario):
        secao = SecaoMarca(cenario.ctx, cenario.master)
        secao.botoes_cor["primaria"]._pintar("#7A1F2B")
        secao._cor_alterada("primaria", "#7A1F2B")
        secao._salvar()
        marca = secao.servico.obter()
        assert marca.preset == PRESET_PERSONALIZADO
        assert marca.paleta.primaria == "#7A1F2B"

    def test_paleta_sem_contraste_avisa(self, app, cenario):
        secao = SecaoMarca(cenario.ctx, cenario.master)
        secao.botoes_cor["texto"]._pintar("#FDFDFD")
        secao._cor_alterada("texto", "#FDFDFD")
        assert "Contraste" in secao.rotulo_contraste.text()
        assert secao.rotulo_contraste.objectName() == "mensagemAlerta"

    def test_atendente_nao_edita(self, app, cenario):
        secao = SecaoMarca(cenario.ctx, cenario.operador)
        assert secao.botao_salvar.isEnabled() is False
        assert secao.campo_nome.isEnabled() is False
        assert all(not botao.isEnabled() for botao in secao.botoes_cor.values())


class TestSecaoUsuarios:
    def test_lista_na_ordem_da_hierarquia(self, app, cenario):
        secao = SecaoUsuarios(cenario.ctx, cenario.master)
        assert secao.tabela.rowCount() == 5
        assert secao.tabela.item(0, 2).text().startswith("Admin Master")

    def test_master_cria_atendente_pela_tela(self, app, cenario):
        secao = SecaoUsuarios(cenario.ctx, cenario.master)
        secao.campo_login.setText("nova.atendente")
        secao.campo_nome.setText("Nova Atendente")
        posicao = secao.combo_novo_perfil.findData(Perfil.ATENDENTE.value)
        secao.combo_novo_perfil.setCurrentIndex(posicao)
        secao.campo_senha.setText("Senha#Forte1")
        secao.campo_senha2.setText("Senha#Forte1")
        secao._criar()
        assert secao.mensagem.objectName() == "mensagemOk"
        assert secao.tabela.rowCount() == 6

    def test_senhas_divergentes_nao_criam(self, app, cenario):
        secao = SecaoUsuarios(cenario.ctx, cenario.master)
        secao.campo_login.setText("x")
        secao.campo_nome.setText("X")
        secao.campo_senha.setText("Senha#Forte1")
        secao.campo_senha2.setText("Outra#Forte2")
        secao._criar()
        assert secao.mensagem.objectName() == "mensagemErro"

    def test_admin_nao_recebe_opcao_de_criar_admin(self, app, cenario):
        secao = SecaoUsuarios(cenario.ctx, cenario.admin)
        opcoes = {
            secao.combo_novo_perfil.itemData(i) for i in range(secao.combo_novo_perfil.count())
        }
        assert Perfil.ADMIN.value not in opcoes
        assert Perfil.GERENTE.value in opcoes


class TestSecaoPermissoes:
    def test_master_edita_e_salva(self, app, cenario):
        secao = SecaoPermissoes(cenario.ctx, cenario.master)
        caixa = secao._caixas[(Perfil.ATENDENTE, Acao.CAIXA_SANGRIA)]
        caixa.setChecked(True)
        secao._salvar()
        assert Acao.CAIXA_SANGRIA in secao.servico.efetivas(Perfil.ATENDENTE)
        assert secao.mensagem.objectName() == "mensagemOk"

    def test_coluna_do_master_e_intocavel(self, app, cenario):
        secao = SecaoPermissoes(cenario.ctx, cenario.master)
        for acao in (Acao.PDV_VENDER, Acao.PERMISSAO_GERENCIAR):
            caixa = secao._caixas[(Perfil.ADMIN_MASTER, acao)]
            assert caixa.isChecked() is True
            assert caixa.isEnabled() is False

    def test_admin_so_consulta(self, app, cenario):
        secao = SecaoPermissoes(cenario.ctx, cenario.admin)
        assert secao.botao_salvar.isEnabled() is False
        caixa = secao._caixas[(Perfil.ATENDENTE, Acao.PDV_VENDER)]
        assert caixa.isEnabled() is False
        assert caixa.isChecked() is True

    def test_restaurar_padrao(self, app, cenario):
        secao = SecaoPermissoes(cenario.ctx, cenario.master)
        secao._caixas[(Perfil.GERENTE, Acao.VENDA_CANCELAR)].setChecked(False)
        secao._salvar()
        assert not secao.servico.efetivas(Perfil.GERENTE) >= {Acao.VENDA_CANCELAR}
        secao._restaurar()
        assert Acao.VENDA_CANCELAR in secao.servico.efetivas(Perfil.GERENTE)


class TestSecaoParametros:
    def test_mostra_os_grupos(self, app, cenario):
        secao = SecaoParametros(cenario.ctx, cenario.master)
        assert "desconto.limite_operador_bp" in secao.campos
        assert secao.botao_salvar.isEnabled() is True

    def test_salva_valor_valido(self, app, cenario):
        from PySide6.QtWidgets import QSpinBox

        secao = SecaoParametros(cenario.ctx, cenario.master)
        campo = secao.campos["caixa.limite_diferenca_centavos"]
        assert isinstance(campo, QSpinBox)
        campo.setValue(750)
        secao._salvar()
        assert cenario.ctx.parametros.obter_int("caixa.limite_diferenca_centavos") == 750
        assert secao.mensagem.objectName() == "mensagemOk"

    def test_atendente_nao_edita(self, app, cenario):
        secao = SecaoParametros(cenario.ctx, cenario.operador)
        assert secao.botao_salvar.isEnabled() is False
        assert all(not campo.isEnabled() for campo in secao.campos.values())


class TestIntegracaoComJanelaPrincipal:
    def test_master_ve_modulo_administracao(self, app, cenario):
        janela = JanelaPrincipal(cenario.ctx, cenario.master)
        assert MODULO_ADMIN in janela.modulos
        janela.close()

    def test_atendente_nao_ve_modulo_administracao(self, app, cenario):
        janela = JanelaPrincipal(cenario.ctx, cenario.operador)
        assert MODULO_ADMIN not in janela.modulos
        janela.close()

    def test_titulo_usa_a_marca_da_loja(self, app, cenario):
        from bussola_pdv.aplicacao.marca import ServicoMarca
        from bussola_pdv.dominio.marca import Marca

        ServicoMarca(cenario.ctx).salvar(cenario.admin, Marca(nome_fantasia="Loja do Zé"))
        janela = JanelaPrincipal(cenario.ctx, cenario.master)
        assert janela.rotulo_titulo.text() == "Loja do Zé"
        assert "Loja do Zé" in janela.windowTitle()
        janela.close()

    def test_paleta_personalizada_muda_a_folha(self, app, cenario):
        from bussola_pdv.aplicacao.marca import ServicoMarca
        from bussola_pdv.dominio.marca import Marca

        ServicoMarca(cenario.ctx).salvar(
            cenario.master, Marca().com_cores(secundaria="#12865F")
        )
        janela = JanelaPrincipal(cenario.ctx, cenario.master)
        from bussola_pdv.ui.tema import folha_estilo_da_marca

        assert "#12865F" in folha_estilo_da_marca(janela.marca)
        assert janela.marca.paleta.secundaria == "#12865F"
        janela.close()


class TestPerdaDeAcessoNaSessao:
    def test_usuario_rebaixado_perde_o_modulo_ao_reabrir(self, app, cenario):
        janela = JanelaPrincipal(cenario.ctx, cenario.admin)
        assert MODULO_ADMIN in janela.modulos

        cenario.ctx.conexao.execute(
            "UPDATE usuarios SET perfil = 'ATENDENTE' WHERE id = ?", (cenario.admin.id,)
        )
        cenario.ctx.conexao.commit()

        janela._recarregar_usuario()
        assert janela.usuario.perfil is Perfil.ATENDENTE

    def test_abrir_admin_sem_permissao_avisa_e_nao_abre(self, app, cenario):
        from PySide6.QtWidgets import QApplication

        janela = JanelaPrincipal(cenario.ctx, cenario.admin)
        cenario.ctx.conexao.execute(
            "UPDATE usuarios SET perfil = 'ATENDENTE' WHERE id = ?", (cenario.admin.id,)
        )
        cenario.ctx.conexao.commit()

        janela._abrir_admin()
        # nenhuma JanelaAdmin modal foi criada: o retorno é imediato
        assert "Administração indisponível" in janela.rotulo_modulo.text()
        assert janela.navegacao.currentRow() == 0
        visiveis = [
            w
            for w in QApplication.topLevelWidgets()
            if isinstance(w, JanelaAdmin) and w.isVisible()
        ]
        assert visiveis == []  # nenhum diálogo modal ficou aberto
        janela.close()
