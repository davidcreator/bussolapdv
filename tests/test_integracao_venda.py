"""Venda ponta a ponta contra SQLite real: atomicidade, idempotência e autorização."""

from __future__ import annotations

import sqlite3

import pytest

from bussola_pdv.aplicacao.pdv import ServicoPDV, SolicitacaoVenda
from bussola_pdv.dominio.dinheiro import Dinheiro
from bussola_pdv.dominio.erros import (
    AutorizacaoNegada,
    CarrinhoVazio,
    ErroBussola,
    LimiteCreditoExcedido,
    PagamentoIncompleto,
    TurnoNaoAberto,
)
from bussola_pdv.dominio.pagamentos import (
    FormaPagamento,
    PlanoPagamento,
    StatusPagamento,
    pagamento_a_prazo,
    pagamento_dinheiro,
    pagamento_eletronico,
)
from bussola_pdv.dominio.venda import Carrinho

pytestmark = pytest.mark.integracao


def carrinho_a(cenario, quantidade="2") -> Carrinho:
    carrinho = Carrinho()
    carrinho.adicionar(cenario.produto_a, quantidade)
    return carrinho


def dinheiro_exato(carrinho: Carrinho, entregue: Dinheiro | None = None) -> PlanoPagamento:
    total = carrinho.totais().total
    return PlanoPagamento.de_pagamentos(pagamento_dinheiro(total, entregue or total))


def test_venda_em_dinheiro_grava_tudo_em_uma_transacao(cenario):
    servico = ServicoPDV(cenario.ctx)
    carrinho = carrinho_a(cenario, "2")  # 2 × 15,90 = 31,80
    plano = PlanoPagamento.de_pagamentos(pagamento_dinheiro(Dinheiro(3180), Dinheiro(10000)))

    resultado = servico.finalizar_venda(
        SolicitacaoVenda(
            operador=cenario.operador,
            caixa_id=cenario.caixa_id,
            carrinho=carrinho,
            plano=plano,
        )
    )

    venda = resultado.venda
    assert venda.total.centavos == 3180
    assert venda.numero == 1
    assert venda.status.value == "CONCLUIDA"

    ctx = cenario.ctx
    assert len(ctx.vendas.itens(venda.id)) == 1
    pagamentos = ctx.vendas.pagamentos(venda.id)
    assert pagamentos[0]["valor_aplicado_centavos"] == 3180
    assert pagamentos[0]["valor_entregue_centavos"] == 10000
    assert pagamentos[0]["troco_centavos"] == 6820
    assert pagamentos[0]["status"] == StatusPagamento.CONFIRMADO.value

    # Estoque baixou exatamente a quantidade vendida.
    assert ctx.produtos.saldo_milesimos(cenario.produto_a.id) == 8000
    # Movimento de caixa com o valor aplicado (não o entregue).
    movimentos = ctx.caixas.movimentos(cenario.turno_id)
    assert sum(m.valor_assinado.centavos for m in movimentos) == 3180
    # Auditoria registrada e cadeia íntegra.
    eventos = ctx.auditoria.listar(acao=None, limite=100)
    assert any(e.acao.value == "VENDA_FINALIZADA" for e in eventos)
    assert ctx.auditoria.verificar().integro


def test_venda_de_tres_itens_com_troco_para_cem_reais(cenario):
    """Critério de aceite do plano de testes do repositório de origem."""
    carrinho = Carrinho()
    carrinho.adicionar(cenario.produto_a, "1")   # 15,90
    carrinho.adicionar(cenario.produto_b, "2")   # 19,80 (2 kg × 9,90)
    carrinho.adicionar(cenario.produto_a, "1")   # consolida em 2 unidades
    total = carrinho.totais().total
    assert total.centavos == 5160

    plano = PlanoPagamento.de_pagamentos(pagamento_dinheiro(total, Dinheiro(10000)))
    resultado = ServicoPDV(cenario.ctx).finalizar_venda(
        SolicitacaoVenda(
            operador=cenario.operador,
            caixa_id=cenario.caixa_id,
            carrinho=carrinho,
            plano=plano,
        )
    )
    assert resultado.plano.troco.centavos == 4840
    assert len(cenario.ctx.vendas.itens(resultado.venda.id)) == 2  # item consolidado


def test_idempotencia_nao_duplica_venda(cenario):
    servico = ServicoPDV(cenario.ctx)
    carrinho = carrinho_a(cenario)
    plano = dinheiro_exato(carrinho)
    solicitacao = SolicitacaoVenda(
        operador=cenario.operador,
        caixa_id=cenario.caixa_id,
        carrinho=carrinho,
        plano=plano,
        chave_idempotencia="chave-fixa-1",
    )
    primeira = servico.finalizar_venda(solicitacao)
    segunda = servico.finalizar_venda(solicitacao)

    assert segunda.ja_existia
    assert segunda.venda.id == primeira.venda.id
    total_vendas = cenario.ctx.conexao.execute("SELECT COUNT(*) FROM vendas").fetchone()[0]
    assert total_vendas == 1
    # Estoque baixou uma única vez.
    assert cenario.ctx.produtos.saldo_milesimos(cenario.produto_a.id) == 8000


def test_estoque_insuficiente_bloqueia(cenario):
    carrinho = Carrinho()
    carrinho.adicionar(cenario.produto_a, "11")  # saldo 10
    plano = dinheiro_exato(carrinho)
    # Sem autorizador, a venda é barrada pelo controle de autorização.
    with pytest.raises(AutorizacaoNegada):
        ServicoPDV(cenario.ctx).finalizar_venda(
            SolicitacaoVenda(
                operador=cenario.operador,
                caixa_id=cenario.caixa_id,
                carrinho=carrinho,
                plano=plano,
            )
        )
    assert cenario.ctx.produtos.saldo_milesimos(cenario.produto_a.id) == 10000


def test_estoque_insuficiente_com_autorizacao_gera_evento(cenario):
    carrinho = Carrinho()
    carrinho.adicionar(cenario.produto_a, "11")
    plano = dinheiro_exato(carrinho)
    resultado = ServicoPDV(cenario.ctx).finalizar_venda(
        SolicitacaoVenda(
            operador=cenario.operador,
            caixa_id=cenario.caixa_id,
            carrinho=carrinho,
            plano=plano,
            autorizador=cenario.gerente,
        )
    )
    assert cenario.ctx.produtos.saldo_milesimos(cenario.produto_a.id) == -1000
    eventos = [e.acao.value for e in cenario.ctx.auditoria.listar(limite=50)]
    assert "ESTOQUE_NEGATIVO_AUTORIZADO" in eventos
    assert resultado.avisos


def test_desconto_acima_do_limite_exige_autorizacao(cenario):
    carrinho = Carrinho()
    carrinho.adicionar(cenario.produto_a, "10")  # 159,00
    total = carrinho.totais().total
    plano = PlanoPagamento.de_pagamentos(pagamento_dinheiro(Dinheiro(total.centavos - 2000)))
    solicitacao = SolicitacaoVenda(
        operador=cenario.operador,
        caixa_id=cenario.caixa_id,
        carrinho=carrinho,
        plano=plano,
        desconto_cupom=Dinheiro(2000),  # 12,58% > 5% do operador
    )
    with pytest.raises(AutorizacaoNegada):
        ServicoPDV(cenario.ctx).finalizar_venda(solicitacao)

    resultado = ServicoPDV(cenario.ctx).finalizar_venda(
        SolicitacaoVenda(
            operador=cenario.operador,
            caixa_id=cenario.caixa_id,
            carrinho=carrinho,
            plano=plano,
            desconto_cupom=Dinheiro(2000),
            autorizador=cenario.gerente,
            chave_idempotencia="desconto-autorizado",
        )
    )
    assert resultado.venda.desconto.centavos == 2000
    eventos = [e.acao.value for e in cenario.ctx.auditoria.listar(limite=50)]
    assert "DESCONTO_AUTORIZADO" in eventos


def test_autorizador_igual_ao_operador_e_recusado(cenario):
    carrinho = Carrinho()
    carrinho.adicionar(cenario.produto_a, "10")
    total = carrinho.totais().total
    plano = PlanoPagamento.de_pagamentos(pagamento_dinheiro(Dinheiro(total.centavos - 2000)))
    with pytest.raises(AutorizacaoNegada):
        ServicoPDV(cenario.ctx).finalizar_venda(
            SolicitacaoVenda(
                operador=cenario.operador,
                caixa_id=cenario.caixa_id,
                carrinho=carrinho,
                plano=plano,
                desconto_cupom=Dinheiro(2000),
                autorizador=cenario.operador,
            )
        )


def test_pagamento_incompleto_bloqueia(cenario):
    carrinho = carrinho_a(cenario)
    total = carrinho.totais().total
    plano = PlanoPagamento.de_pagamentos(pagamento_dinheiro(total - Dinheiro(100)))
    with pytest.raises(PagamentoIncompleto):
        ServicoPDV(cenario.ctx).finalizar_venda(
            SolicitacaoVenda(
                operador=cenario.operador,
                caixa_id=cenario.caixa_id,
                carrinho=carrinho,
                plano=plano,
            )
        )


def test_venda_sem_turno_aberto_falha(cenario):
    cenario.ctx.caixas.fechar_turno(
        turno_id=cenario.turno_id,
        fechado_em=cenario.ctx.agora(),
        conferente_id=cenario.gerente.id,
        contado=Dinheiro(10000),
        diferenca=Dinheiro.zero(),
    )
    carrinho = carrinho_a(cenario)
    with pytest.raises(TurnoNaoAberto):
        ServicoPDV(cenario.ctx).finalizar_venda(
            SolicitacaoVenda(
                operador=cenario.operador,
                caixa_id=cenario.caixa_id,
                carrinho=carrinho,
                plano=dinheiro_exato(carrinho),
            )
        )


def test_carrinho_vazio(cenario):
    with pytest.raises(CarrinhoVazio):
        ServicoPDV(cenario.ctx).finalizar_venda(
            SolicitacaoVenda(
                operador=cenario.operador,
                caixa_id=cenario.caixa_id,
                carrinho=Carrinho(),
                plano=PlanoPagamento.de_pagamentos(pagamento_dinheiro(Dinheiro(100))),
            )
        )


def test_pix_fica_pendente_e_aparece_no_relatorio(cenario):
    carrinho = carrinho_a(cenario)
    total = carrinho.totais().total
    plano = PlanoPagamento.de_pagamentos(pagamento_eletronico(FormaPagamento.PIX, total))
    resultado = ServicoPDV(cenario.ctx).finalizar_venda(
        SolicitacaoVenda(
            operador=cenario.operador,
            caixa_id=cenario.caixa_id,
            carrinho=carrinho,
            plano=plano,
        )
    )
    pagamento = cenario.ctx.vendas.pagamentos(resultado.venda.id)[0]
    assert pagamento["status"] == StatusPagamento.PENDENTE.value
    assert pagamento["confirmacao_manual"] == 0
    assert any("PENDENTE" in aviso for aviso in resultado.avisos)


def test_venda_a_prazo_gera_tres_titulos(cenario):
    carrinho = Carrinho()
    carrinho.adicionar(cenario.produto_a, "6")  # 95,40
    total = carrinho.totais().total
    plano = PlanoPagamento.de_pagamentos(pagamento_a_prazo(total))
    resultado = ServicoPDV(cenario.ctx).finalizar_venda(
        SolicitacaoVenda(
            operador=cenario.operador,
            caixa_id=cenario.caixa_id,
            carrinho=carrinho,
            plano=plano,
            cliente_id=cenario.cliente.id,
            parcelas_crediario=3,
        )
    )
    titulos = cenario.ctx.crediario.listar(cliente_id=cenario.cliente.id)
    assert len(resultado.titulos) == 3
    assert sum(t["principal_centavos"] for t in titulos) == total.centavos
    assert cenario.ctx.clientes.saldo_devedor(cenario.cliente.id) == total.centavos


def test_limite_de_credito_bloqueia_venda_a_prazo(cenario):
    carrinho = Carrinho()
    carrinho.adicionar(cenario.produto_a, "10")  # 159,00 > limite de 100,00
    total = carrinho.totais().total
    with pytest.raises(LimiteCreditoExcedido):
        ServicoPDV(cenario.ctx).finalizar_venda(
            SolicitacaoVenda(
                operador=cenario.operador,
                caixa_id=cenario.caixa_id,
                carrinho=carrinho,
                plano=PlanoPagamento.de_pagamentos(pagamento_a_prazo(total)),
                cliente_id=cenario.cliente.id,
            )
        )


def test_venda_a_prazo_sem_cliente(cenario):
    carrinho = carrinho_a(cenario)
    total = carrinho.totais().total
    with pytest.raises(ErroBussola):
        ServicoPDV(cenario.ctx).finalizar_venda(
            SolicitacaoVenda(
                operador=cenario.operador,
                caixa_id=cenario.caixa_id,
                carrinho=carrinho,
                plano=PlanoPagamento.de_pagamentos(pagamento_a_prazo(total)),
            )
        )


def test_falha_no_meio_nao_deixa_venda_parcial(cenario, monkeypatch):
    """Injeta erro após gravar a venda: tudo deve sofrer rollback."""

    def explodir(*args, **kwargs):
        raise sqlite3.OperationalError("falha simulada de disco")

    monkeypatch.setattr(cenario.ctx.vendas, "inserir_pagamentos", explodir)

    antes = {
        tabela: cenario.ctx.conexao.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
        for tabela in ("vendas", "itens_venda", "pagamentos", "movimentos_estoque", "movimentos_caixa")
    }
    antes_eventos = len(cenario.ctx.auditoria.listar(limite=200))
    carrinho = carrinho_a(cenario)
    with pytest.raises(sqlite3.OperationalError):
        ServicoPDV(cenario.ctx).finalizar_venda(
            SolicitacaoVenda(
                operador=cenario.operador,
                caixa_id=cenario.caixa_id,
                carrinho=carrinho,
                plano=dinheiro_exato(carrinho),
            )
        )
    cenario.ctx.conferir_integridade()
    for tabela, quantidade in antes.items():
        depois = cenario.ctx.conexao.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
        assert depois == quantidade, f"{tabela} deveria voltar ao estado anterior ao rollback"
    assert len(cenario.ctx.auditoria.listar(limite=50)) == antes_eventos
    assert cenario.ctx.produtos.saldo_milesimos(cenario.produto_a.id) == 10000
    # Sequência de cupom não é consumida de forma visível? É consumida, mas o
    # número não reaproveita: o próximo cupom apenas segue adiante.
    assert cenario.ctx.conexao.execute("SELECT COUNT(*) FROM vendas").fetchone()[0] == 0


def test_cancelamento_preserva_historico_e_reverte_estoque(cenario):
    servico = ServicoPDV(cenario.ctx)
    carrinho = carrinho_a(cenario, "2")
    resultado = servico.finalizar_venda(
        SolicitacaoVenda(
            operador=cenario.operador,
            caixa_id=cenario.caixa_id,
            carrinho=carrinho,
            plano=dinheiro_exato(carrinho),
        )
    )
    assert cenario.ctx.produtos.saldo_milesimos(cenario.produto_a.id) == 8000

    cancelamento = servico.cancelar_venda(
        venda_id=resultado.venda.id,
        motivo="Cliente desistiu",
        operador=cenario.operador,
        autorizador=cenario.gerente,
    )
    assert cancelamento["estoque_devolvido"] is True
    assert cenario.ctx.produtos.saldo_milesimos(cenario.produto_a.id) == 10000
    venda = cenario.ctx.vendas.por_id(resultado.venda.id)
    assert venda.status.value == "CANCELADA"
    assert venda.motivo_cancelamento == "Cliente desistiu"
    # Pagamentos permanecem; nada foi apagado.
    assert len(cenario.ctx.vendas.pagamentos(venda.id)) == 1
    assert cancelamento["reembolso_em_dinheiro_registrado"] is True
    movimentos = cenario.ctx.caixas.movimentos(cenario.turno_id)
    assert sum(m.valor_assinado.centavos for m in movimentos) == 0  # venda + estorno

    eventos = [e.acao.value for e in cenario.ctx.auditoria.listar(limite=50)]
    assert "VENDA_CANCELADA" in eventos


def test_cancelamento_exige_autorizacao(cenario):
    servico = ServicoPDV(cenario.ctx)
    carrinho = carrinho_a(cenario)
    resultado = servico.finalizar_venda(
        SolicitacaoVenda(
            operador=cenario.operador,
            caixa_id=cenario.caixa_id,
            carrinho=carrinho,
            plano=dinheiro_exato(carrinho),
        )
    )
    with pytest.raises(AutorizacaoNegada):
        servico.cancelar_venda(
            venda_id=resultado.venda.id,
            motivo="teste",
            operador=cenario.operador,
            autorizador=cenario.operador,
        )


def test_banco_continua_integro_apos_a_operacao(cenario):
    carrinho = carrinho_a(cenario)
    ServicoPDV(cenario.ctx).finalizar_venda(
        SolicitacaoVenda(
            operador=cenario.operador,
            caixa_id=cenario.caixa_id,
            carrinho=carrinho,
            plano=dinheiro_exato(carrinho),
        )
    )
    integro, problemas = cenario.ctx.conferir_integridade()
    assert integro, problemas
