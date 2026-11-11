"""Hierarquia de cinco perfis, matriz de permissões e travas de gestão de usuários."""

from __future__ import annotations

import sqlite3

import pytest

from bussola_pdv.aplicacao.permissoes import ServicoPermissoes
from bussola_pdv.aplicacao.usuarios import ServicoUsuarios
from bussola_pdv.dominio.erros import AutorizacaoNegada, ErroBussola, ErroConflito, ErroValidacao
from bussola_pdv.dominio.seguranca import gerar_hash
from bussola_pdv.dominio.usuario import (
    ACOES_SOMENTE_MASTER,
    PERMISSOES_PADRAO,
    Acao,
    Perfil,
    Usuario,
    acoes_por_categoria,
)

pytestmark = pytest.mark.integracao

SENHA_FORTE = "Bussola#2026"
SENHA_CENARIO = "senha-de-teste"  # mesma senha usada pelo fixture conftest


class TestPerfis:
    def test_cinco_perfis_na_ordem_hierarquica(self):
        assert [p.value for p in Perfil] == [
            "ATENDENTE",
            "GERENTE",
            "CONTABILIDADE",
            "ADMIN",
            "ADMIN_MASTER",
        ]

    def test_niveis_crescem_na_hierarquia(self):
        assert (
            Perfil.ATENDENTE.nivel
            < Perfil.CONTABILIDADE.nivel
            < Perfil.GERENTE.nivel
            < Perfil.ADMIN.nivel
            < Perfil.ADMIN_MASTER.nivel
        )

    def test_apenas_master_tem_acesso_integral(self):
        assert PERMISSOES_PADRAO[Perfil.ADMIN_MASTER] == frozenset(Acao)
        for perfil in (Perfil.ATENDENTE, Perfil.GERENTE, Perfil.CONTABILIDADE, Perfil.ADMIN):
            assert PERMISSOES_PADRAO[perfil] < frozenset(Acao)

    def test_aliases_legados_apontam_para_perfis_novos(self):
        assert Perfil.OPERADOR is Perfil.ATENDENTE
        assert Perfil.ADMINISTRADOR is Perfil.ADMIN
        assert Perfil.ATENDENTE.value == "ATENDENTE"

    def test_admin_nao_recebe_permissoes_de_master_por_padrao(self):
        for acao in ACOES_SOMENTE_MASTER:
            assert acao not in PERMISSOES_PADRAO[Perfil.ADMIN]

    def test_contabilidade_nao_opera_pdv_nem_caixa(self):
        padrao = PERMISSOES_PADRAO[Perfil.CONTABILIDADE]
        assert Acao.RELATORIO_CONTABIL in padrao
        for acao in (
            Acao.PDV_VENDER,
            Acao.CAIXA_ABRIR,
            Acao.CAIXA_SANGRIA,
            Acao.VENDA_CANCELAR,
            Acao.ESTOQUE_AJUSTAR,
        ):
            assert acao not in padrao

    def test_atendente_nao_tem_excecoes(self):
        padrao = PERMISSOES_PADRAO[Perfil.ATENDENTE]
        assert Acao.CAIXA_SUPRIMENTO in padrao
        for acao in (
            Acao.PDV_DESCONTO_EXCEPCIONAL,
            Acao.CAIXA_SANGRIA,
            Acao.VENDA_CANCELAR,
            Acao.CADASTRO_PRODUTO,
            Acao.ADMIN_ACESSAR,
            Acao.USUARIO_GERENCIAR,
        ):
            assert acao not in padrao

    def test_toda_acao_tem_categoria_e_rotulo(self):
        for acao in Acao:
            assert acao.categoria is not None
            assert acao.rotulo
        agrupado = acoes_por_categoria()
        assert sum(len(lista) for lista in agrupado.values()) == len(Acao)


class TestUsuario:
    def test_master_tem_tudo_mesmo_com_concessao_vazia(self):
        master = Usuario(
            login="m", nome="M", perfil=Perfil.ADMIN_MASTER, senha_hash="x",
            permissoes_concedidas=frozenset(),
        )
        assert master.permissoes == frozenset(Acao)
        assert master.pode(Acao.PERMISSAO_GERENCIAR)

    def test_concessao_do_banco_sobrepoe_o_padrao(self):
        usuario = Usuario(
            login="a", nome="A", perfil=Perfil.ATENDENTE, senha_hash="x",
            permissoes_concedidas=frozenset({Acao.PDV_VENDER, Acao.CAIXA_SANGRIA}),
        )
        assert usuario.pode(Acao.CAIXA_SANGRIA)
        assert not usuario.pode(Acao.CAIXA_ABRIR)

    def test_inativo_nao_pode_nada(self):
        usuario = Usuario(
            login="a", nome="A", perfil=Perfil.ADMIN, senha_hash="x", ativo=False
        )
        assert not usuario.pode(Acao.ADMIN_ACESSAR)
        with pytest.raises(AutorizacaoNegada):
            usuario.exigir(Acao.PDV_VENDER)

    def test_ninguem_gerencia_a_si_mesmo(self, cenario):
        for usuario in (cenario.master, cenario.admin, cenario.gerente, cenario.operador):
            assert not usuario.pode_gerenciar(usuario)

    def test_hierarquia_de_gestao(self, cenario):
        assert cenario.master.pode_gerenciar(cenario.admin)
        assert cenario.admin.pode_gerenciar(cenario.gerente)
        assert not cenario.admin.pode_gerenciar(cenario.admin)
        # Gerente não gerencia usuários por padrão: só se o master conceder a ação.
        assert not cenario.gerente.pode_gerenciar(cenario.operador)
        assert not cenario.operador.pode_gerenciar(cenario.gerente)

    def test_conceder_gestao_de_usuarios_ao_gerente_respeita_o_nivel(self, cenario):
        ServicoPermissoes(cenario.ctx).definir(
            cenario.master, Perfil.GERENTE, Acao.USUARIO_GERENCIAR, True
        )
        gerente = cenario.ctx.usuarios.por_id(cenario.gerente.id)
        assert gerente.pode_gerenciar(cenario.operador)
        assert not gerente.pode_gerenciar(cenario.admin)

    def test_nao_se_atribui_perfil_igual_ou_superior(self, cenario):
        assert cenario.master.pode_receber_perfil(Perfil.ADMIN)
        assert not cenario.master.pode_receber_perfil(Perfil.ADMIN_MASTER)
        assert cenario.admin.pode_receber_perfil(Perfil.GERENTE)
        assert not cenario.admin.pode_receber_perfil(Perfil.ADMIN)
        assert not cenario.gerente.pode_receber_perfil(Perfil.GERENTE)


class TestMatrizDePermissoes:
    def test_master_altera_matriz_e_efeito_vale_no_banco(self, cenario):
        servico = ServicoPermissoes(cenario.ctx)
        resultado = servico.definir(cenario.master, Perfil.ATENDENTE, Acao.CAIXA_SANGRIA, True)
        assert resultado.alterado
        assert resultado.depois is True
        assert Acao.CAIXA_SANGRIA in servico.efetivas(Perfil.ATENDENTE)
        # usuário recarregado já vem com a concessão
        recarregado = cenario.ctx.usuarios.por_id(cenario.operador.id)
        assert recarregado.pode(Acao.CAIXA_SANGRIA)

    def test_excecao_pode_revogar_permissao_padrao(self, cenario):
        servico = ServicoPermissoes(cenario.ctx)
        servico.definir(cenario.master, Perfil.GERENTE, Acao.VENDA_CANCELAR, False)
        assert not cenario.ctx.usuarios.por_id(cenario.gerente.id).pode(Acao.VENDA_CANCELAR)
        assert len(servico.excecoes()) == 1

    def test_admin_nao_altera_matriz(self, cenario):
        servico = ServicoPermissoes(cenario.ctx)
        with pytest.raises(AutorizacaoNegada):
            servico.definir(cenario.admin, Perfil.ATENDENTE, Acao.CAIXA_SANGRIA, True)

    def test_linha_do_master_nao_e_configuravel(self, cenario):
        servico = ServicoPermissoes(cenario.ctx)
        with pytest.raises(ErroValidacao):
            servico.definir(cenario.master, Perfil.ADMIN_MASTER, Acao.PDV_VENDER, False)

    def test_acoes_de_master_nao_podem_ser_delegadas(self, cenario):
        servico = ServicoPermissoes(cenario.ctx)
        for acao in ACOES_SOMENTE_MASTER:
            with pytest.raises(ErroValidacao):
                servico.definir(cenario.master, Perfil.ADMIN, acao, True)

    def test_repetir_valor_nao_gera_evento(self, cenario):
        servico = ServicoPermissoes(cenario.ctx)
        eventos_antes = len(cenario.ctx.auditoria.listar(limite=500))
        resultado = servico.definir(cenario.master, Perfil.ATENDENTE, Acao.PDV_VENDER, True)
        assert resultado.alterado is False
        assert len(cenario.ctx.auditoria.listar(limite=500)) == eventos_antes

    def test_alteracao_entra_na_auditoria_com_antes_e_depois(self, cenario):
        servico = ServicoPermissoes(cenario.ctx)
        servico.definir(cenario.master, Perfil.CONTABILIDADE, Acao.PDV_VENDER, True)
        evento = cenario.ctx.auditoria.listar(limite=5)[0]
        assert evento.acao.value == "PERMISSAO_ALTERADA"
        assert evento.antes == {"acao": "PDV_VENDER", "permitido": False}
        assert evento.depois == {"acao": "PDV_VENDER", "permitido": True}
        assert cenario.ctx.auditoria.verificar().integro

    def test_aplicar_lote_e_restaurar_padrao(self, cenario):
        servico = ServicoPermissoes(cenario.ctx)
        mudancas = {
            (Perfil.ATENDENTE, Acao.CAIXA_SANGRIA): True,
            (Perfil.GERENTE, Acao.VENDA_CANCELAR): False,
        }
        aplicadas = servico.aplicar(cenario.master, mudancas)
        assert len(aplicadas) == 2
        assert servico.excecoes()
        removidas = servico.restaurar_padrao(cenario.master)
        assert removidas == 2
        assert servico.excecoes() == []
        assert Acao.CAIXA_SANGRIA not in servico.efetivas(Perfil.ATENDENTE)

    def test_resumo_conta_concedidas_por_perfil(self, cenario):
        resumo = ServicoPermissoes(cenario.ctx).resumo()
        assert resumo["ADMIN_MASTER"]["concedidas"] == len(Acao)
        assert resumo["ATENDENTE"]["concedidas"] < resumo["GERENTE"]["concedidas"]


class TestServicoUsuarios:
    def test_listar_ordena_por_hierarquia(self, cenario):
        lista = ServicoUsuarios(cenario.ctx).listar(cenario.master)
        perfis = [resumo.perfil for resumo in lista]
        assert perfis[0] is Perfil.ADMIN_MASTER
        assert perfis[-1] is Perfil.ATENDENTE
        assert {resumo.perfil_rotulo for resumo in lista} >= {"Admin Master", "Contabilidade"}

    def test_atendente_nao_lista_usuarios(self, cenario):
        with pytest.raises(AutorizacaoNegada):
            ServicoUsuarios(cenario.ctx).listar(cenario.operador)

    def test_admin_cria_gerente(self, cenario):
        servico = ServicoUsuarios(cenario.ctx)
        criado = servico.criar(
            cenario.admin,
            login="novo.gerente",
            nome="Novo Gerente",
            perfil=Perfil.GERENTE,
            senha=SENHA_FORTE,
        )
        assert criado.perfil is Perfil.GERENTE
        assert criado.senha_hash.startswith("$argon2id$")

    def test_admin_nao_cria_admin(self, cenario):
        servico = ServicoUsuarios(cenario.ctx)
        with pytest.raises(ErroValidacao):
            servico.criar(
                cenario.admin, login="outro.admin", nome="Outro Admin",
                perfil=Perfil.ADMIN, senha=SENHA_FORTE,
            )

    def test_master_cria_admin_mas_nao_segundo_master(self, cenario):
        servico = ServicoUsuarios(cenario.ctx)
        criado = servico.criar(
            cenario.master, login="admin2", nome="Segundo Admin",
            perfil=Perfil.ADMIN, senha=SENHA_FORTE,
        )
        assert criado.perfil is Perfil.ADMIN
        with pytest.raises(ErroConflito):
            servico.criar(
                cenario.master, login="master2", nome="Outro Master",
                perfil=Perfil.ADMIN_MASTER, senha=SENHA_FORTE,
            )
        with pytest.raises(ErroConflito):
            servico.criar(
                cenario.admin, login="master3", nome="Terceiro Master",
                perfil=Perfil.ADMIN_MASTER, senha=SENHA_FORTE,
            )

    def test_senha_fraca_e_recusada(self, cenario):
        with pytest.raises(ErroBussola):
            ServicoUsuarios(cenario.ctx).criar(
                cenario.master, login="fraco", nome="Fraco",
                perfil=Perfil.ATENDENTE, senha="123",
            )

    def test_perfis_disponiveis_respeitam_hierarquia(self, cenario):
        servico = ServicoUsuarios(cenario.ctx)
        assert Perfil.ADMIN in servico.perfis_disponiveis(cenario.master)
        assert Perfil.ADMIN_MASTER not in servico.perfis_disponiveis(cenario.master)
        assert Perfil.ADMIN not in servico.perfis_disponiveis(cenario.admin)
        assert Perfil.GERENTE in servico.perfis_disponiveis(cenario.admin)
        assert servico.perfis_disponiveis(cenario.operador) == []

    def test_gerente_sem_permissao_nao_gerencia_admin(self, cenario):
        with pytest.raises(AutorizacaoNegada):
            ServicoUsuarios(cenario.ctx).definir_ativo(cenario.gerente, cenario.admin.id, False)

    def test_gerente_com_permissao_nao_alcanca_quem_esta_acima(self, cenario):
        ServicoPermissoes(cenario.ctx).definir(
            cenario.master, Perfil.GERENTE, Acao.USUARIO_GERENCIAR, True
        )
        gerente = cenario.ctx.usuarios.por_id(cenario.gerente.id)
        with pytest.raises(ErroValidacao):
            ServicoUsuarios(cenario.ctx).definir_ativo(gerente, cenario.admin.id, False)

    def test_ninguem_desativa_a_si_mesmo(self, cenario):
        with pytest.raises(ErroValidacao):
            ServicoUsuarios(cenario.ctx).definir_ativo(
                cenario.admin, cenario.admin.id, False
            )

    def test_master_esta_fora_da_hierarquia_de_gestao(self, cenario):
        # Ninguém tem nível acima do master: ele não é alvo de ativação/desativação.
        with pytest.raises(ErroValidacao):
            ServicoUsuarios(cenario.ctx).definir_ativo(cenario.admin, cenario.master.id, False)
        with pytest.raises(ErroValidacao):
            ServicoUsuarios(cenario.ctx).definir_ativo(
                cenario.master, cenario.master.id, False
            )

    def test_desativar_nao_exclui_historico(self, cenario):
        servico = ServicoUsuarios(cenario.ctx)
        servico.definir_ativo(cenario.admin, cenario.operador.id, False)
        recarregado = cenario.ctx.usuarios.por_id(cenario.operador.id)
        assert recarregado.ativo is False
        assert recarregado.login == "operador"

    def test_usuario_nao_pode_ser_excluido_no_banco(self, cenario):
        with pytest.raises(sqlite3.IntegrityError):
            cenario.ctx.conexao.execute(
                "DELETE FROM usuarios WHERE id = ?", (cenario.operador.id,)
            )

    def test_redefinir_senha_gera_evento(self, cenario):
        ServicoUsuarios(cenario.ctx).redefinir_senha(cenario.admin, cenario.operador.id, SENHA_FORTE)
        evento = cenario.ctx.auditoria.listar(limite=3)[0]
        assert evento.acao.value == "SENHA_REDEFINIDA"

    def test_transferencia_de_propriedade(self, cenario):
        servico = ServicoUsuarios(cenario.ctx)
        anterior, novo = servico.transferir_propriedade(
            cenario.master, usuario_id=cenario.admin.id, senha_do_ator=SENHA_CENARIO
        )
        assert novo.perfil is Perfil.ADMIN_MASTER
        assert anterior.perfil is Perfil.ADMIN
        assert novo.pode(Acao.PERMISSAO_GERENCIAR)
        assert not anterior.pode(Acao.PERMISSAO_GERENCIAR)
        assert cenario.ctx.auditoria.listar(limite=3)[0].acao.value == "MASTER_TRANSFERIDO"

    def test_transferencia_exige_senha_correta(self, cenario):
        with pytest.raises(ErroValidacao):
            ServicoUsuarios(cenario.ctx).transferir_propriedade(
                cenario.master, usuario_id=cenario.admin.id, senha_do_ator="senha-errada"
            )

    def test_apenas_um_master_ativo_no_banco(self, cenario):
        with pytest.raises(sqlite3.IntegrityError):
            cenario.ctx.conexao.execute(
                """INSERT INTO usuarios (id, login, nome, perfil, senha_hash, ativo, criado_em)
                   VALUES ('x1', 'outro.master', 'Outro', 'ADMIN_MASTER', ?, 1, '2026-11-11')""",
                (gerar_hash(SENHA_FORTE),),
            )
