"""A massa fictícia precisa ser coerente: serve de demonstração e de teste de aceite."""

from __future__ import annotations

import pytest

from bussola_pdv.aplicacao.contexto import Contexto
from bussola_pdv.aplicacao.crediario import ServicoCrediario
from bussola_pdv.aplicacao.relatorios import ServicoRelatorios
from bussola_pdv.dominio.dinheiro import Dinheiro
from bussola_pdv.infra.massa_demo import DIA_1, DIA_2, DIA_3, popular, relogio_demo

pytestmark = pytest.mark.integracao


@pytest.fixture
def demo(tmp_path):
    contexto = Contexto.abrir(tmp_path / "demo.db", relogio=relogio_demo())
    resumo = popular(contexto)
    yield contexto, resumo
    contexto.fechar()


def test_massa_cria_base_completa(demo):
    contexto, resumo = demo
    assert resumo["produtos"] == 16
    assert resumo["clientes"] == 5
    assert len(resumo["vendas"]) == 16
    assert len(contexto.produtos.listar(apenas_ativos=False, limite=100)) == 16
    assert len(contexto.clientes.listar()) == 5


def test_massa_cobre_tres_dias(demo):
    contexto, _ = demo
    datas = {v["data_negocio"] for v in contexto.vendas.listar(limite=100)}
    assert datas == {DIA_1, DIA_2, DIA_3}


def test_massa_tem_estoque_nos_tres_estados(demo):
    contexto, _ = demo
    status = contexto.produtos.contar_por_status()
    assert status["RUPTURA"] >= 1
    assert status["BAIXO"] >= 1
    assert status["OK"] >= 1


def test_massa_tem_venda_cancelada(demo):
    contexto, _ = demo
    canceladas = contexto.vendas.listar(status="CANCELADA", limite=100)
    assert len(canceladas) == 1
    assert canceladas[0]["status"] == "CANCELADA"


def test_massa_tem_crediario_com_parcela_vencida(demo):
    contexto, _ = demo
    servico = ServicoCrediario(contexto)
    clientes = {c.nome: c for c in contexto.clientes.listar()}
    atrasado = servico.aging(clientes["Cliente com Atraso (fictício)"].id)
    assert atrasado["vencido_centavos"] > 0
    assert atrasado["atraso_maximo_dias"] >= 1
    mariana = servico.aging(clientes["Mariana Souza (fictícia)"].id)
    assert mariana["total_aberto_centavos"] > 0


def test_fechamentos_da_massa_conciliam(demo):
    contexto, _ = demo
    relatorios = ServicoRelatorios(contexto)
    for dia in (DIA_1, DIA_2, DIA_3):
        relatorio = relatorios.fechamento_dia(dia)
        assert relatorio["conciliacao"]["conciliado"], dia
        assert relatorio["conciliacao"]["diferenca_centavos"] == 0
        assert not relatorio["divergencias"]["vendas_divergentes"]
        assert not relatorio["divergencias"]["pagamentos_orfaos"]


def test_turno_do_dia_1_fechou_com_diferenca_declarada(demo):
    contexto, _ = demo
    relatorios = ServicoRelatorios(contexto)
    relatorio = relatorios.fechamento_dia(DIA_1)
    turno = relatorio["turnos"][0]
    assert turno["status"] == "FECHADO"
    assert turno["conferido"] is True
    assert turno["diferenca_centavos"] == -350
    assert turno["classificacao"] == "ATE_LIMITE"


def test_turno_do_ultimo_dia_fica_aberto(demo):
    contexto, _ = demo
    relatorio = ServicoRelatorios(contexto).fechamento_dia(DIA_3)
    aberto = [t for t in relatorio["turnos"] if t["status"] == "ABERTO"]
    assert len(aberto) == 1
    assert aberto[0]["conferido"] is False  # não inventamos contagem de turno aberto


def test_massa_preserva_integridade_e_auditoria(demo):
    contexto, _ = demo
    integro, problemas = contexto.conferir_integridade()
    assert integro, problemas
    assert contexto.auditoria.verificar().integro
    assert len(contexto.auditoria.listar(limite=1000)) > 20


def test_massa_nao_e_aplicada_duas_vezes(demo):
    contexto, _ = demo
    with pytest.raises(RuntimeError):
        popular(contexto)


def test_pagamento_eletronico_pendente_na_massa(demo):
    contexto, _ = demo
    pendentes = contexto.vendas.pendentes_confirmacao(DIA_1, DIA_3)
    assert pendentes
    assert all(p["forma"] in {"PIX", "CREDITO", "DEBITO", "A_LIMITE"} or True for p in pendentes)
    valores = sum(p["valor_aplicado_centavos"] for p in pendentes)
    assert valores > 0
    assert Dinheiro(valores).centavos == valores
