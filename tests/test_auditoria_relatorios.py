"""Trilha append-only, encadeamento de hash e conciliação dos relatórios."""

from __future__ import annotations

import itertools
import sqlite3

import pytest

from bussola_pdv.aplicacao.pdv import ServicoPDV, SolicitacaoVenda
from bussola_pdv.aplicacao.relatorios import ServicoRelatorios
from bussola_pdv.dominio.auditoria import AcaoAuditoria, EventoAuditoria, verificar_cadeia
from bussola_pdv.dominio.dinheiro import Dinheiro
from bussola_pdv.dominio.pagamentos import (
    FormaPagamento,
    PlanoPagamento,
    pagamento_dinheiro,
    pagamento_eletronico,
)
from bussola_pdv.dominio.venda import Carrinho

pytestmark = pytest.mark.integracao


def _vender(cenario, itens, forma="DINHEIRO"):
    carrinho = Carrinho()
    for codigo, quantidade in itens:
        produto = cenario.produto_a if codigo == "A" else cenario.produto_b
        carrinho.adicionar(produto, quantidade)
    total = carrinho.totais().total
    if forma == "DINHEIRO":
        plano = PlanoPagamento.de_pagamentos(pagamento_dinheiro(total, Dinheiro(total.centavos + 500)))
    elif forma == "PIX":
        plano = PlanoPagamento.de_pagamentos(pagamento_eletronico(FormaPagamento.PIX, total))
    else:  # SPLIT
        parte = total.proporcional(1, 2)
        plano = PlanoPagamento.de_pagamentos(
            pagamento_dinheiro(parte),
            pagamento_eletronico(FormaPagamento.PIX, total - parte),
        )
    return ServicoPDV(cenario.ctx).finalizar_venda(
        SolicitacaoVenda(
            operador=cenario.operador,
            caixa_id=cenario.caixa_id,
            carrinho=carrinho,
            plano=plano,
        )
    )


class TestAuditoria:
    def test_update_direto_e_bloqueado(self, cenario):
        with pytest.raises(sqlite3.DatabaseError):
            cenario.ctx.conexao.execute("UPDATE auditoria SET motivo = 'adulterado' WHERE sequencia = 1")

    def test_delete_direto_e_bloqueado(self, cenario):
        with pytest.raises(sqlite3.DatabaseError):
            cenario.ctx.conexao.execute("DELETE FROM auditoria WHERE sequencia = 1")

    def test_cadeia_encadeia_hashes(self, cenario):
        _vender(cenario, [("A", "1")])
        eventos = list(reversed(cenario.ctx.auditoria.listar(limite=100)))
        assert eventos[0].hash_anterior == ""
        for anterior, atual in itertools.pairwise(eventos):
            assert atual.hash_anterior == anterior.hash
            assert atual.sequencia == anterior.sequencia + 1
        assert verificar_cadeia(eventos).integro

    def test_cadeia_detecta_evento_forjado(self, cenario):
        eventos = cenario.ctx.auditoria.listar(limite=10)
        forjado = EventoAuditoria(
            acao=AcaoAuditoria.VENDA_FINALIZADA,
            criado_em_utc=eventos[0].criado_em_utc,
            data_negocio="2026-11-11",
            ator_id="invasor",
            sequencia=eventos[0].sequencia,
            hash_anterior=eventos[0].hash_anterior,
            hash="0" * 64,
        )
        resultado = verificar_cadeia([forjado])
        assert not resultado.integro
        assert resultado.primeira_divergencia == eventos[0].sequencia

    def test_evento_tem_ator_e_correlacao(self, cenario):
        resultado = _vender(cenario, [("A", "1")])
        eventos = cenario.ctx.auditoria.listar(acao=AcaoAuditoria.VENDA_FINALIZADA)
        assert eventos
        evento = eventos[0]
        assert evento.ator_id == cenario.operador.id
        assert evento.correlacao_id == resultado.venda.id
        assert evento.depois["total_centavos"] == resultado.venda.total.centavos


class TestRelatorios:
    def test_fechamento_concilia_split_sem_duplicar(self, cenario):
        _vender(cenario, [("A", "2")], forma="SPLIT")  # 31,80
        relatorio = ServicoRelatorios(cenario.ctx).fechamento_dia(cenario.ctx.relogio.data_negocio())
        assert relatorio["resumo"]["cupons"] == 1
        assert relatorio["resumo"]["faturamento_centavos"] == 3180
        assert relatorio["conciliacao"]["pagamentos_aplicados_centavos"] == 3180
        assert relatorio["conciliacao"]["diferenca_centavos"] == 0
        assert relatorio["conciliacao"]["conciliado"] is True
        formas = {forma["forma"]: forma for forma in relatorio["por_forma"]}
        assert set(formas) == {"DINHEIRO", "PIX"}
        assert sum(f["aplicado_centavos"] for f in formas.values()) == 3180

    def test_venda_cancelada_nao_entra_no_faturamento(self, cenario):
        resultado = _vender(cenario, [("A", "1")])
        ServicoPDV(cenario.ctx).cancelar_venda(
            venda_id=resultado.venda.id,
            motivo="Teste de cancelamento",
            operador=cenario.operador,
            autorizador=cenario.gerente,
        )
        relatorio = ServicoRelatorios(cenario.ctx).fechamento_dia(cenario.ctx.relogio.data_negocio())
        assert relatorio["resumo"]["cupons"] == 0
        assert relatorio["resumo"]["faturamento_centavos"] == 0

    def test_pagamento_pendente_aparece_na_conferencia(self, cenario):
        _vender(cenario, [("A", "1")], forma="PIX")
        relatorio = ServicoRelatorios(cenario.ctx).fechamento_dia(cenario.ctx.relogio.data_negocio())
        assert relatorio["pagamentos_pendentes"]
        pix = next(f for f in relatorio["por_forma"] if f["forma"] == "PIX")
        assert pix["pendente_centavos"] == 1590
        assert "não representa confirmação bancária" in relatorio["conciliacao"]["aviso"].lower()

    def test_estoque_e_crediario_declaram_escopo(self, cenario):
        relatorio = ServicoRelatorios(cenario.ctx).fechamento_dia(cenario.ctx.relogio.data_negocio())
        assert "posição corrente" in relatorio["estoque"]["escopo"].lower()
        assert "posição corrente" in relatorio["crediario_do_dia"]["escopo"].lower()
        assert "filtro" in relatorio["escopo"].lower()

    def test_dashboard_indicadores(self, cenario):
        _vender(cenario, [("A", "2")])  # 31,80, custo 20,00
        dashboard = ServicoRelatorios(cenario.ctx).dashboard("2026-11-01", "2026-11-30")
        assert dashboard["resumo"]["cupons"] == 1
        assert dashboard["lucro_bruto_centavos"] == 1180
        assert dashboard["margem_bruta_bp"] == 3710
        assert dashboard["serie_diaria"][0]["data_negocio"] == "2026-11-11"

    def test_snapshot_e_versionado_e_imutavel(self, cenario):
        relatorios = ServicoRelatorios(cenario.ctx)
        _vender(cenario, [("A", "1")])
        primeiro = relatorios.registrar_fechamento(
            data_negocio="2026-11-11", usuario=cenario.gerente
        )
        segundo = relatorios.registrar_fechamento(
            data_negocio="2026-11-11", usuario=cenario.gerente
        )
        assert primeiro["fechamento_id"] != segundo["fechamento_id"]
        snapshots = cenario.ctx.fechamentos.listar(data_negocio="2026-11-11")
        assert [s["versao"] for s in snapshots] == [2, 1]
        with pytest.raises(sqlite3.DatabaseError):
            cenario.ctx.conexao.execute("UPDATE fechamentos SET versao = 9")
        with pytest.raises(sqlite3.DatabaseError):
            cenario.ctx.conexao.execute("DELETE FROM fechamentos")

    def test_fechamento_exige_permissao(self, cenario):
        from bussola_pdv.dominio.erros import AutorizacaoNegada

        with pytest.raises(AutorizacaoNegada):
            ServicoRelatorios(cenario.ctx).registrar_fechamento(
                data_negocio="2026-11-11", usuario=cenario.operador
            )
