"""Caixa (turno único, sangria, fechamento) e crediário (recebimento parcial)."""

from __future__ import annotations

from datetime import date

import pytest

from bussola_pdv.aplicacao.caixa import ServicoCaixa
from bussola_pdv.aplicacao.crediario import ServicoCrediario
from bussola_pdv.aplicacao.pdv import ServicoPDV, SolicitacaoVenda
from bussola_pdv.dominio.caixa import ContagemDenominacao, TipoMovimentoCaixa
from bussola_pdv.dominio.dinheiro import Dinheiro
from bussola_pdv.dominio.erros import (
    AutorizacaoNegada,
    ErroBussola,
    RecebimentoInvalido,
    TurnoJaAberto,
    TurnoJaFechado,
    TurnoNaoAberto,
)
from bussola_pdv.dominio.pagamentos import (
    FormaPagamento,
    PlanoPagamento,
    pagamento_a_prazo,
)
from bussola_pdv.dominio.venda import Carrinho

pytestmark = pytest.mark.integracao


# -- caixa ----------------------------------------------------------------------
def test_apenas_um_turno_aberto_por_caixa(cenario):
    servico = ServicoCaixa(cenario.ctx)
    with pytest.raises(TurnoJaAberto):
        servico.abrir_turno(caixa="Caixa Teste", operador=cenario.gerente, fundo=Dinheiro(1000))


def test_sangria_exige_autorizacao(cenario):
    servico = ServicoCaixa(cenario.ctx)
    with pytest.raises(AutorizacaoNegada):
        servico.movimentar(
            turno_id=cenario.turno_id,
            tipo=TipoMovimentoCaixa.SANGRIA,
            valor=Dinheiro(5000),
            motivo="Depósito",
            operador=cenario.operador,
        )
    servico.movimentar(
        turno_id=cenario.turno_id,
        tipo=TipoMovimentoCaixa.SANGRIA,
        valor=Dinheiro(5000),
        motivo="Depósito",
        operador=cenario.operador,
        autorizador=cenario.gerente,
    )
    turno = cenario.ctx.caixas.carregar_turno(cenario.turno_id)
    assert turno.esperado.centavos == 5000  # 100,00 de fundo − 50,00 de sangria


def test_suprimento_nao_exige_autorizacao(cenario):
    ServicoCaixa(cenario.ctx).movimentar(
        turno_id=cenario.turno_id,
        tipo=TipoMovimentoCaixa.SUPRIMENTO,
        valor=Dinheiro(2000),
        motivo="Reforço",
        operador=cenario.operador,
    )
    assert cenario.ctx.caixas.carregar_turno(cenario.turno_id).esperado.centavos == 12000


def test_fechamento_com_diferenca_exige_motivo(cenario):
    servico = ServicoCaixa(cenario.ctx)
    contagem = [ContagemDenominacao(5000, 1), ContagemDenominacao(2000, 2)]  # contado 90,00
    with pytest.raises(ErroBussola):
        servico.fechar_turno(
            turno_id=cenario.turno_id, conferente=cenario.gerente, contagens=contagem
        )
    resultado = servico.fechar_turno(
        turno_id=cenario.turno_id,
        conferente=cenario.gerente,
        contagens=contagem,
        motivo_diferenca="Faltou troco",
    )
    assert resultado.conferencia["diferenca_centavos"] == -1000
    assert resultado.conferencia["classificacao"] == "ACIMA_LIMITE"
    assert resultado.avisos
    turno = cenario.ctx.caixas.turno_por_id(cenario.turno_id)
    assert turno.status.value == "FECHADO"
    assert turno.diferenca.centavos == -1000
    assert len(cenario.ctx.caixas.contagens(cenario.turno_id)) == 2  # duas denominações


def test_fechamento_sem_diferenca(cenario):
    servico = ServicoCaixa(cenario.ctx)
    resultado = servico.fechar_turno(
        turno_id=cenario.turno_id,
        conferente=cenario.gerente,
        contagens=[ContagemDenominacao(10000, 1)],
    )
    assert resultado.conferencia["diferenca_centavos"] == 0
    assert resultado.conferencia["classificacao"] == "ZERO"
    assert not resultado.avisos


def test_movimento_apos_fechamento_falha(cenario):
    servico = ServicoCaixa(cenario.ctx)
    servico.fechar_turno(
        turno_id=cenario.turno_id,
        conferente=cenario.gerente,
        contagens=[ContagemDenominacao(10000, 1)],
    )
    with pytest.raises(TurnoJaFechado):
        servico.movimentar(
            turno_id=cenario.turno_id,
            tipo=TipoMovimentoCaixa.SUPRIMENTO,
            valor=Dinheiro(1000),
            motivo="Tarde demais",
            operador=cenario.operador,
        )


def test_fechamento_duplicado_falha(cenario):
    servico = ServicoCaixa(cenario.ctx)
    contagem = [ContagemDenominacao(10000, 1)]
    servico.fechar_turno(turno_id=cenario.turno_id, conferente=cenario.gerente, contagens=contagem)
    with pytest.raises(ErroBussola):
        servico.fechar_turno(
            turno_id=cenario.turno_id, conferente=cenario.gerente, contagens=contagem
        )


# -- crediário ------------------------------------------------------------------
def _venda_a_prazo(cenario, quantidade="4", parcelas=2):
    carrinho = Carrinho()
    carrinho.adicionar(cenario.produto_a, quantidade)
    total = carrinho.totais().total
    resultado = ServicoPDV(cenario.ctx).finalizar_venda(
        SolicitacaoVenda(
            operador=cenario.operador,
            caixa_id=cenario.caixa_id,
            carrinho=carrinho,
            plano=PlanoPagamento.de_pagamentos(pagamento_a_prazo(total)),
            cliente_id=cenario.cliente.id,
            parcelas_crediario=parcelas,
        )
    )
    return resultado


def test_recebimento_parcial_atualiza_saldo_e_status(cenario):
    _venda_a_prazo(cenario)  # 4 × 15,90 = 63,60 em 2 parcelas de 31,80
    titulos = cenario.ctx.crediario.listar(cliente_id=cenario.cliente.id, incluir_pagos=True)
    titulo = sorted(titulos, key=lambda t: t["numero_parcela"])[0]

    servico = ServicoCrediario(cenario.ctx)
    resultado = servico.receber(
        titulo_id=titulo["id"],
        valor=Dinheiro(1000),
        forma=FormaPagamento.DINHEIRO,
        operador=cenario.operador,
        caixa_id=cenario.caixa_id,
    )
    assert resultado.saldo_restante.centavos == 2180
    assert resultado.entrou_no_caixa is True

    atualizado = cenario.ctx.crediario.por_id(titulo["id"])
    assert atualizado["status"] == "PARCIAL"
    # Recebimento entrou como movimento de caixa e NÃO gerou nova venda.
    assert cenario.ctx.vendas.listar(limite=100).__len__() == 1
    movimentos = cenario.ctx.caixas.movimentos(cenario.turno_id)
    assert any(m.tipo is TipoMovimentoCaixa.RECEBIMENTO_TITULO for m in movimentos)


def test_recebimento_total_quita(cenario):
    _venda_a_prazo(cenario)
    titulo = cenario.ctx.crediario.listar(cliente_id=cenario.cliente.id)[0]
    ServicoCrediario(cenario.ctx).receber(
        titulo_id=titulo["id"],
        valor=Dinheiro(titulo["saldo_centavos"]),
        forma=FormaPagamento.PIX,
        operador=cenario.operador,
        caixa_id=cenario.caixa_id,
    )
    assert cenario.ctx.crediario.por_id(titulo["id"])["status"] == "PAGO"
    # Restou a segunda parcela de 31,80.
    assert cenario.ctx.clientes.saldo_devedor(cenario.cliente.id) == 3180


def test_recebimento_acima_do_saldo_falha(cenario):
    _venda_a_prazo(cenario)
    titulo = cenario.ctx.crediario.listar(cliente_id=cenario.cliente.id)[0]
    with pytest.raises(RecebimentoInvalido):
        ServicoCrediario(cenario.ctx).receber(
            titulo_id=titulo["id"],
            valor=Dinheiro(titulo["saldo_centavos"] + 100),
            forma=FormaPagamento.DINHEIRO,
            operador=cenario.operador,
            caixa_id=cenario.caixa_id,
        )


def test_recebimento_sem_turno_aberto(cenario):
    _venda_a_prazo(cenario)
    titulo = cenario.ctx.crediario.listar(cliente_id=cenario.cliente.id)[0]
    ServicoCaixa(cenario.ctx).fechar_turno(
        turno_id=cenario.turno_id,
        conferente=cenario.gerente,
        contagens=[ContagemDenominacao(10000, 1)],
    )
    with pytest.raises(TurnoNaoAberto):
        ServicoCrediario(cenario.ctx).receber(
            titulo_id=titulo["id"],
            valor=Dinheiro(1000),
            forma=FormaPagamento.DINHEIRO,
            operador=cenario.operador,
            caixa_id=cenario.caixa_id,
        )


def test_aging_apos_vencimento(cenario):
    _venda_a_prazo(cenario, quantidade="2", parcelas=2)
    # Avança 40 dias: primeira parcela vence em D+30.
    cenario.ctx.relogio.avancar(days=41)
    servico = ServicoCrediario(cenario.ctx)
    aging = servico.aging(cenario.cliente.id)
    assert aging["vencido_centavos"] > 0
    assert aging["atraso_maximo_dias"] >= 1
    assert aging["data_referencia"] == cenario.ctx.relogio.data_negocio()
    assert aging["faixas_centavos"]["1_30"] > 0


def test_venda_a_prazo_nao_entra_na_gaveta(cenario):
    _venda_a_prazo(cenario)
    turno = cenario.ctx.caixas.carregar_turno(cenario.turno_id)
    assert turno.esperado.centavos == 10000  # apenas o fundo
    assert all(
        m.tipo is not TipoMovimentoCaixa.VENDA_DINHEIRO for m in turno.movimentos
    )


def test_vencimento_de_referencia_do_aging_e_a_data_de_negocio(cenario):
    _venda_a_prazo(cenario)
    servico = ServicoCrediario(cenario.ctx)
    assert servico.aging(cenario.cliente.id)["data_referencia"] == date(2026, 11, 11).isoformat()
