"""Regras de estoque (rateio), crediário (parcelas/aging) e caixa (conferência)."""

from datetime import UTC, date
from decimal import Decimal

import pytest

from bussola_pdv.dominio.caixa import (
    ClassificacaoDiferenca,
    ContagemDenominacao,
    MovimentoCaixa,
    TipoMovimentoCaixa,
    Turno,
    classificar_diferenca,
    conferir_turno,
    fracionar_em_denominacoes,
    media_por_cupom,
    total_contagem,
)
from bussola_pdv.dominio.crediario import (
    dividir_em_parcelas,
    gerar_parcelas,
    vencimento_mensal,
)
from bussola_pdv.dominio.dinheiro import Dinheiro, Quantidade
from bussola_pdv.dominio.erros import ErroValidacao
from bussola_pdv.dominio.estoque import (
    CriterioRateio,
    EntradaMercadoria,
    ItemEntrada,
    MovimentoEstoque,
    TipoMovimentoEstoque,
    calcular_saldo,
    ratear,
)


class TestEstoque:
    def test_saldo_assinado(self):
        movimentos = [
            MovimentoEstoque("p1", TipoMovimentoEstoque.ENTRADA, Quantidade(10000)),
            MovimentoEstoque("p1", TipoMovimentoEstoque.VENDA, Quantidade(3000)),
            MovimentoEstoque("p1", TipoMovimentoEstoque.AJUSTE, Quantidade(-1000), motivo="Perda"),
        ]
        assert calcular_saldo(0, movimentos) == 6000

    def test_movimento_zero_recusado(self):
        with pytest.raises(ErroValidacao):
            MovimentoEstoque("p1", TipoMovimentoEstoque.VENDA, Quantidade(0))

    def test_ajuste_exige_motivo(self):
        with pytest.raises(ErroValidacao):
            MovimentoEstoque("p1", TipoMovimentoEstoque.AJUSTE, Quantidade(100))


class TestRateio:
    @pytest.mark.parametrize(
        ("total", "pesos"),
        [
            (100, [1, 1, 1]),          # 34/33/33 em centavos
            (7, [1, 1, 1]),
            (1000, [3, 5, 2]),
            (1, [1, 1, 1, 1]),
            (99999, [17, 3, 250, 1]),
        ],
    )
    def test_soma_exata(self, total, pesos):
        partes = ratear(Dinheiro(total), pesos)
        assert sum(p.centavos for p in partes) == total

    def test_distribui_resto_para_maior_resto(self):
        partes = ratear(Dinheiro(100), [1, 1, 1])
        assert [p.centavos for p in partes] == [34, 33, 33]

    def test_pesos_zerados_distribui_igual(self):
        partes = ratear(Dinheiro(3), [0, 0, 0])
        assert sum(p.centavos for p in partes) == 3

    def test_frete_negativo_recusado(self):
        with pytest.raises(ErroValidacao):
            ratear(Dinheiro(-1), [1])

    def test_entrada_rateia_frete_por_valor(self):
        itens = (
            ItemEntrada("p1", "A", Quantidade(1000), Dinheiro(1000)),
            ItemEntrada("p2", "B", Quantidade(2000), Dinheiro(2500)),
        )
        entrada = EntradaMercadoria(
            fornecedor="Fornecedor X",
            documento="NF-1",
            itens=itens,
            frete=Dinheiro(1000),
            criterio=CriterioRateio.VALOR,
        )
        rateados = entrada.ratear_frete()
        assert sum(i.frete_rateado.centavos for i in rateados) == 1000
        # Item de maior valor recebe a maior parcela do frete.
        assert rateados[1].frete_rateado > rateados[0].frete_rateado

    def test_custo_unitario_com_frete(self):
        item = ItemEntrada("p1", "A", Quantidade(2000), Dinheiro(1000), Dinheiro(500))
        entrada = EntradaMercadoria(
            fornecedor="F", documento="NF-2", itens=(item,), frete=Dinheiro(500)
        )
        rateado = entrada.ratear_frete()[0]
        # (2 kg × 10,00 + 5,00) / 2 kg = 12,50 por kg
        assert entrada.custo_unitario_com_frete(rateado).centavos == 1250


class TestParcelas:
    def test_soma_exata_com_residuo(self):
        parcelas = dividir_em_parcelas(Dinheiro(10000), 3)
        assert [p.centavos for p in parcelas] == [3334, 3333, 3333]
        assert sum(p.centavos for p in parcelas) == 10000

    def test_uma_parcela(self):
        assert [p.centavos for p in dividir_em_parcelas(Dinheiro(999), 1)] == [999]

    @pytest.mark.parametrize("quantidade", [0, 49])
    def test_quantidade_invalida(self, quantidade):
        with pytest.raises(ErroValidacao):
            dividir_em_parcelas(Dinheiro(1000), quantidade)

    def test_vencimento_fim_de_mes(self):
        assert vencimento_mensal(date(2026, 1, 31), 1) == date(2026, 2, 28)
        assert vencimento_mensal(date(2028, 1, 31), 1) == date(2028, 2, 29)
        assert vencimento_mensal(date(2026, 1, 31), 2) == date(2026, 3, 31)

    def test_vencimento_vira_ano(self):
        assert vencimento_mensal(date(2026, 12, 15), 1) == date(2027, 1, 15)

    def test_gerar_parcelas_mensais(self):
        parcelas = gerar_parcelas(Dinheiro(12000), 3, base=date(2026, 11, 11))
        assert [p.vencimento for p in parcelas] == [
            date(2026, 12, 11),
            date(2027, 1, 11),
            date(2027, 2, 11),
        ]
        assert [p.numero for p in parcelas] == [1, 2, 3]

    def test_primeiro_vencimento_explicito(self):
        parcelas = gerar_parcelas(
            Dinheiro(2000), 2, base=date(2026, 11, 11), primeiro_vencimento=date(2026, 11, 20)
        )
        assert parcelas[0].vencimento == date(2026, 11, 20)
        assert parcelas[1].vencimento == date(2026, 12, 20)

    def test_vencimento_anterior_a_venda(self):
        with pytest.raises(ErroValidacao):
            gerar_parcelas(
                Dinheiro(2000), 2, base=date(2026, 11, 11), primeiro_vencimento=date(2026, 11, 1)
            )


class TestAging:
    def _parcela(self, vencimento: date, valor: int = 10000):
        from bussola_pdv.dominio.crediario import Parcela

        return Parcela(numero=1, total_parcelas=1, vencimento=vencimento, principal=Dinheiro(valor))

    def test_faixas(self):
        from bussola_pdv.dominio.crediario import calcular_aging

        referencia = date(2026, 11, 11)
        titulos = [
            (self._parcela(date(2026, 12, 1)), Dinheiro.zero()),      # a vencer
            (self._parcela(date(2026, 11, 1)), Dinheiro(0)),          # 10 dias
            (self._parcela(date(2026, 10, 1)), Dinheiro(0)),          # 41 dias
            (self._parcela(date(2026, 8, 1)), Dinheiro(0)),           # 102 dias
            (self._parcela(date(2026, 11, 1)), Dinheiro(10000)),      # quitado: fora
        ]
        aging = calcular_aging(cliente_id="c1", titulos=titulos, referencia=referencia)
        assert aging.faixas["A_VENCER"] == 10000
        assert aging.faixas["1_30"] == 10000
        assert aging.faixas["31_60"] == 10000
        assert aging.faixas["ACIMA_90"] == 10000
        assert aging.total_aberto == 40000
        assert aging.vencido == 30000
        assert aging.atraso_maximo_dias == 102
        assert aging.data_referencia == referencia

    def test_pagamento_parcial_reduz_saldo(self):
        from bussola_pdv.dominio.crediario import calcular_aging

        referencia = date(2026, 11, 11)
        aging = calcular_aging(
            cliente_id="c1",
            titulos=[(self._parcela(date(2026, 11, 1)), Dinheiro(4000))],
            referencia=referencia,
        )
        assert aging.total_aberto == 6000


class TestCredito:
    def test_bloqueia_por_limite(self):
        from bussola_pdv.dominio.cliente import avaliar_credito
        from bussola_pdv.dominio.erros import LimiteCreditoExcedido

        with pytest.raises(LimiteCreditoExcedido):
            avaliar_credito(
                limite=10000,
                saldo_devedor=9000,
                vencido=0,
                atraso_maximo_dias=0,
                dias_bloqueio_atraso=30,
                valor_pretendido=2000,
            )

    def test_autorizacao_de_gerente_libera(self):
        from bussola_pdv.dominio.cliente import avaliar_credito

        situacao = avaliar_credito(
            limite=10000,
            saldo_devedor=9000,
            vencido=0,
            atraso_maximo_dias=0,
            dias_bloqueio_atraso=30,
            valor_pretendido=2000,
            autorizado_por_gerente=True,
        )
        assert situacao.disponivel == 1000

    def test_bloqueia_por_atraso(self):
        from bussola_pdv.dominio.cliente import avaliar_credito
        from bussola_pdv.dominio.erros import ClienteBloqueadoPorAtraso

        with pytest.raises(ClienteBloqueadoPorAtraso):
            avaliar_credito(
                limite=100000,
                saldo_devedor=0,
                vencido=1000,
                atraso_maximo_dias=45,
                dias_bloqueio_atraso=30,
                valor_pretendido=1000,
            )


class TestCaixa:
    def _turno(self, movimentos=()) -> Turno:
        from datetime import datetime

        return Turno(
            caixa_id="cx",
            operador_id="op",
            fundo=Dinheiro(10000),
            aberto_em=datetime(2026, 11, 11, 12, tzinfo=UTC),
            movimentos=tuple(movimentos),
        )

    def test_esperado_com_movimentos(self):
        turno = self._turno(
            [
                MovimentoCaixa(TipoMovimentoCaixa.VENDA_DINHEIRO, Dinheiro(5000)),
                MovimentoCaixa(TipoMovimentoCaixa.RECEBIMENTO_TITULO, Dinheiro(1000)),
                MovimentoCaixa(
                    TipoMovimentoCaixa.SUPRIMENTO, Dinheiro(2000), motivo="Troco"
                ),
                MovimentoCaixa(
                    TipoMovimentoCaixa.SANGRIA, Dinheiro(3000), motivo="Depósito",
                    autorizador_id="gerente",
                ),
            ]
        )
        assert turno.esperado.centavos == 15000

    def test_sangria_exige_motivo_e_autorizador(self):
        with pytest.raises(ErroValidacao):
            MovimentoCaixa(TipoMovimentoCaixa.SANGRIA, Dinheiro(100))
        with pytest.raises(ErroValidacao):
            MovimentoCaixa(TipoMovimentoCaixa.SANGRIA, Dinheiro(100), motivo="Depósito")

    def test_movimento_negativo_recusado(self):
        with pytest.raises(ErroValidacao):
            MovimentoCaixa(TipoMovimentoCaixa.VENDA_DINHEIRO, Dinheiro(-100))

    def test_contagem_por_denominacao(self):
        contagem = [
            ContagemDenominacao(10000, 3),
            ContagemDenominacao(500, 4),
            ContagemDenominacao(5, 2),
        ]
        assert total_contagem(contagem).centavos == 32010

    def test_denominacao_desconhecida(self):
        with pytest.raises(ErroValidacao):
            ContagemDenominacao(3, 1)

    def test_denominacao_repetida(self):
        with pytest.raises(ErroValidacao):
            total_contagem([ContagemDenominacao(100, 1), ContagemDenominacao(100, 2)])

    def test_diferenca_de_dez_reais(self):
        turno = self._turno([MovimentoCaixa(TipoMovimentoCaixa.VENDA_DINHEIRO, Dinheiro(9000))])
        conferencia = conferir_turno(turno, [ContagemDenominacao(10000, 1), ContagemDenominacao(5000, 1)])
        assert conferencia["esperado_centavos"] == 19000
        assert conferencia["contado_centavos"] == 15000
        assert conferencia["diferenca_centavos"] == -4000
        assert conferencia["classificacao"] == ClassificacaoDiferenca.ACIMA_LIMITE.value

    def test_classificacao_diferenca(self):
        assert classificar_diferenca(Dinheiro(0)) is ClassificacaoDiferenca.ZERO
        assert classificar_diferenca(Dinheiro(500)) is ClassificacaoDiferenca.ATE_LIMITE
        assert classificar_diferenca(Dinheiro(-500)) is ClassificacaoDiferenca.ATE_LIMITE
        assert classificar_diferenca(Dinheiro(501)) is ClassificacaoDiferenca.ACIMA_LIMITE

    def test_fracionar_valor(self):
        sugestao = fracionar_em_denominacoes(Dinheiro(12345))
        assert total_contagem(sugestao).centavos == 12345

    def test_ticket_medio(self):
        assert media_por_cupom(Dinheiro(1000), 3).centavos == 333
        assert media_por_cupom(Dinheiro(1000), 0).centavos == 0
        assert Decimal("0") == Decimal(str(0))
