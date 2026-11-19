"""Encargos de atraso cobrados no recebimento: receita separada do principal (ADR-033).

O que estes testes protegem:

* o título **não** muda de valor — multa e juros não inflam o principal;
* o dinheiro do encargo entra na gaveta num movimento de tipo próprio;
* perdoar encargo é operação sensível: sem autorizador com permissão e motivo, recusa;
* com a cobrança desligada (padrão de fábrica), nada muda em relação à v0.13.0;
* a memória de cálculo chega à tela, para o operador explicar o número.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

from bussola_pdv.aplicacao.crediario import ServicoCrediario
from bussola_pdv.aplicacao.parametros import ServicoParametros
from bussola_pdv.aplicacao.pdv import ServicoPDV, SolicitacaoVenda
from bussola_pdv.dominio.caixa import TipoMovimentoCaixa
from bussola_pdv.dominio.dinheiro import Dinheiro
from bussola_pdv.dominio.erros import AutorizacaoNegada, ErroValidacao
from bussola_pdv.dominio.pagamentos import (
    FormaPagamento,
    PlanoPagamento,
    pagamento_a_prazo,
)
from bussola_pdv.dominio.venda import Carrinho

pytestmark = pytest.mark.integracao


def _venda_a_prazo(cenario, *, atraso_dias: int = 10) -> dict:
    """Venda a prazo com 1 parcela, vencida `atraso_dias` atrás da data de negócio."""
    carrinho = Carrinho()
    carrinho.adicionar(cenario.produto_a, "1")
    total = carrinho.totais().total
    ServicoPDV(cenario.ctx).finalizar_venda(
        SolicitacaoVenda(
            operador=cenario.operador,
            caixa_id=cenario.caixa_id,
            carrinho=carrinho,
            plano=PlanoPagamento.de_pagamentos(pagamento_a_prazo(total)),
            cliente_id=cenario.cliente.id,
            parcelas_crediario=1,
        )
    )
    titulo = next(t for t in cenario.ctx.crediario.listar() if int(t["saldo_centavos"]) > 0)
    referencia = date.fromisoformat(cenario.ctx.relogio.data_negocio())
    vencimento = (referencia - timedelta(days=atraso_dias)).isoformat()
    cenario.ctx.conexao.execute(
        "UPDATE titulos SET vencimento = ? WHERE id = ?", (vencimento, titulo["id"])
    )
    return cenario.ctx.crediario.por_id(titulo["id"])


def _ligar_cobranca(cenario) -> None:
    """Quem liga a cobrança é o admin: gerente não altera parâmetro."""
    ServicoParametros(cenario.ctx).definir(cenario.admin, "encargos.cobrar", "1")


def _receber(cenario, titulo: dict, **extra):
    return ServicoCrediario(cenario.ctx).receber(
        titulo_id=str(titulo["id"]),
        valor=Dinheiro(int(titulo["saldo_centavos"])),
        forma=extra.pop("forma", FormaPagamento.DINHEIRO),
        operador=extra.pop("operador", cenario.gerente),
        caixa_id=cenario.caixa_id,
        **extra,
    )


class TestCalculo:
    def test_atraso_de_10_dias_cobra_multa_cheia_e_juros_proporcionais(self, cenario):
        titulo = _venda_a_prazo(cenario, atraso_dias=10)
        devidos = ServicoCrediario(cenario.ctx).encargos_do_titulo(str(titulo["id"]))
        assert devidos.dias_atraso == 10
        # 2% de multa sobre o saldo; 1% ao mês em 10 de 30 dias = 1/3 da taxa mensal
        saldo = int(titulo["saldo_centavos"])
        assert devidos.multa.centavos == round(saldo * 200 / 10000)
        assert devidos.juros.centavos == round(saldo * 100 * 10 / (10000 * 30))
        assert devidos.total.centavos == devidos.multa.centavos + devidos.juros.centavos

    def test_titulo_no_prazo_nao_gera_encargo(self, cenario):
        titulo = _venda_a_prazo(cenario, atraso_dias=0)
        devidos = ServicoCrediario(cenario.ctx).encargos_do_titulo(str(titulo["id"]))
        assert devidos.isento
        assert devidos.dias_atraso == 0

    def test_carencia_parametrizada_zera_o_encargo_ate_o_limite(self, cenario):
        ServicoParametros(cenario.ctx).definir(cenario.admin, "encargos.carencia_dias", "15")
        titulo = _venda_a_prazo(cenario, atraso_dias=10)
        devidos = ServicoCrediario(cenario.ctx).encargos_do_titulo(str(titulo["id"]))
        assert devidos.isento

    def test_memoria_de_calculo_explica_o_numero(self, cenario):
        titulo = _venda_a_prazo(cenario)
        devidos = ServicoCrediario(cenario.ctx).encargos_do_titulo(str(titulo["id"]))
        texto = " ".join(devidos.memoria)
        assert "Multa" in texto
        assert "Juros" in texto
        assert "Total de encargos" in texto


class TestCobranca:
    def test_cobranca_desligada_mantem_o_comportamento_antigo(self, cenario):
        titulo = _venda_a_prazo(cenario)
        resultado = _receber(cenario, titulo)
        assert resultado.encargo.centavos == 0
        assert resultado.encargos_dispensados is False
        assert cenario.ctx.crediario.por_id(str(titulo["id"]))["saldo_centavos"] == 0

    def test_cobranca_ligada_cobra_sem_inflar_o_titulo(self, cenario):
        titulo = _venda_a_prazo(cenario)
        principal = int(titulo["saldo_centavos"])
        _ligar_cobranca(cenario)

        resultado = _receber(cenario, titulo)

        assert resultado.encargo.centavos > 0
        assert resultado.total_pago.centavos == principal + resultado.encargo.centavos
        # o título quita pelo principal: o encargo não virou dívida dentro dele
        assert cenario.ctx.crediario.por_id(str(titulo["id"]))["saldo_centavos"] == 0

        linha = cenario.ctx.conexao.execute(
            "SELECT valor_centavos, multa_centavos, juros_centavos, encargo_centavos,"
            " dias_atraso FROM recebimentos WHERE id = ?",
            (resultado.recebimento_id,),
        ).fetchone()
        assert linha["valor_centavos"] == principal
        assert linha["multa_centavos"] == resultado.multa.centavos
        assert linha["juros_centavos"] == resultado.juros.centavos
        assert linha["encargo_centavos"] == resultado.encargo.centavos
        assert linha["dias_atraso"] == 10

    def test_encargo_em_dinheiro_entra_na_gaveta_em_movimento_proprio(self, cenario):
        titulo = _venda_a_prazo(cenario)
        principal = int(titulo["saldo_centavos"])
        _ligar_cobranca(cenario)

        resultado = _receber(cenario, titulo)

        turno = cenario.ctx.caixas.carregar_turno(cenario.turno_id)
        resumo = turno.resumo(Dinheiro.zero())
        assert resumo["recebimentos_centavos"] == principal
        assert resumo["encargos_centavos"] == resultado.encargo.centavos
        assert resumo["esperado_centavos"] == 10000 + principal + resultado.encargo.centavos

    def test_encargo_fora_do_dinheiro_nao_entra_na_gaveta(self, cenario):
        titulo = _venda_a_prazo(cenario)
        _ligar_cobranca(cenario)

        resultado = _receber(cenario, titulo, forma=FormaPagamento.PIX)

        turno = cenario.ctx.caixas.carregar_turno(cenario.turno_id)
        assert resultado.encargo.centavos > 0
        assert turno.total_por_tipo(TipoMovimentoCaixa.RECEBIMENTO_ENCARGOS).centavos == 0

    def test_perdoar_sem_autorizador_e_recusado(self, cenario):
        titulo = _venda_a_prazo(cenario)
        _ligar_cobranca(cenario)
        with pytest.raises(ErroValidacao, match="gerente"):
            _receber(cenario, titulo, cobrar_encargos=False)

    def test_perdoar_sem_motivo_e_recusado(self, cenario):
        titulo = _venda_a_prazo(cenario)
        _ligar_cobranca(cenario)
        with pytest.raises(ErroValidacao, match="motivo"):
            _receber(
                cenario,
                titulo,
                operador=cenario.operador,
                cobrar_encargos=False,
                autorizador=cenario.gerente,
            )

    def test_atendente_nao_perdoa_mesmo_autorizando_a_si_proprio(self, cenario):
        titulo = _venda_a_prazo(cenario)
        _ligar_cobranca(cenario)
        with pytest.raises(AutorizacaoNegada):
            _receber(
                cenario,
                titulo,
                operador=cenario.operador,
                cobrar_encargos=False,
                motivo_dispensa="teste",
                autorizador=cenario.operador,
            )

    def test_perdoar_com_autorizacao_registra_na_auditoria(self, cenario):
        titulo = _venda_a_prazo(cenario)
        _ligar_cobranca(cenario)

        resultado = _receber(
            cenario,
            titulo,
            operador=cenario.operador,
            cobrar_encargos=False,
            motivo_dispensa="Cliente avisou que ia atrasar",
            autorizador=cenario.gerente,
        )
        assert resultado.encargo.centavos == 0
        assert resultado.encargos_dispensados is True

        linha = cenario.ctx.conexao.execute(
            "SELECT encargos_dispensados FROM recebimentos WHERE id = ?",
            (resultado.recebimento_id,),
        ).fetchone()
        assert linha["encargos_dispensados"] == 1

        evento = cenario.ctx.conexao.execute(
            "SELECT depois FROM auditoria WHERE acao = 'TITULO_RECEBIDO'"
            " ORDER BY sequencia DESC LIMIT 1"
        ).fetchone()
        depois = json.loads(evento["depois"])
        assert depois["encargos_dispensados_centavos"] > 0
        assert depois["autorizador_id"] == cenario.gerente.id
        assert "avisou" in depois["motivo_dispensa"]
        assert depois["multa_centavos"] == 0
        assert depois["juros_centavos"] == 0
