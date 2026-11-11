"""Split de pagamentos, troco e limites de três formas."""

import pytest

from bussola_pdv.dominio.dinheiro import Dinheiro
from bussola_pdv.dominio.erros import PagamentoIncompleto, PagamentoInvalido, TrocoInvalido
from bussola_pdv.dominio.pagamentos import (
    FormaPagamento,
    Pagamento,
    PlanoPagamento,
    StatusPagamento,
    pagamento_a_prazo,
    pagamento_dinheiro,
    pagamento_eletronico,
)


class TestTroco:
    def test_dinheiro_com_troco(self):
        pagamento = pagamento_dinheiro(Dinheiro(2700), Dinheiro(5000))
        assert pagamento.troco.centavos == 2300
        assert pagamento.status is StatusPagamento.CONFIRMADO

    def test_entregue_menor_que_aplicado(self):
        with pytest.raises(TrocoInvalido):
            pagamento_dinheiro(Dinheiro(2700), Dinheiro(1000))

    def test_cartao_nao_gera_troco(self):
        pagamento = pagamento_eletronico(FormaPagamento.DEBITO, Dinheiro(2700))
        assert pagamento.troco.centavos == 0

    def test_excesso_eletronico_e_erro(self):
        with pytest.raises(TrocoInvalido):
            Pagamento(
                forma=FormaPagamento.PIX,
                valor_aplicado=Dinheiro(2700),
                valor_entregue=Dinheiro(3000),
            )

    def test_valor_zero_recusado(self):
        with pytest.raises(PagamentoInvalido):
            Pagamento(
                forma=FormaPagamento.DINHEIRO,
                valor_aplicado=Dinheiro(0),
                valor_entregue=Dinheiro(0),
            )


class TestPlano:
    def test_dinheiro_exato(self):
        plano = PlanoPagamento.de_pagamentos(pagamento_dinheiro(Dinheiro(2700)))
        plano.validar_contra(Dinheiro(2700))
        assert plano.troco.centavos == 0

    def test_split_dinheiro_mais_pix(self):
        plano = PlanoPagamento.de_pagamentos(
            pagamento_dinheiro(Dinheiro(1000)),
            pagamento_eletronico(FormaPagamento.PIX, Dinheiro(1700)),
        )
        plano.validar_contra(Dinheiro(2700))
        assert plano.total_aplicado.centavos == 2700
        assert plano.dinheiro_aplicado.centavos == 1000
        assert plano.tem_pendente_confirmacao  # PIX sem confirmação registrada

    def test_falta_pagamento(self):
        plano = PlanoPagamento.de_pagamentos(pagamento_dinheiro(Dinheiro(1000)))
        with pytest.raises(PagamentoIncompleto) as erro:
            plano.validar_contra(Dinheiro(2700))
        assert erro.value.falta_centavos == 1700

    def test_excesso_de_pagamento(self):
        plano = PlanoPagamento.de_pagamentos(pagamento_dinheiro(Dinheiro(3000)))
        with pytest.raises(PagamentoInvalido):
            plano.validar_contra(Dinheiro(2700))

    def test_maximo_tres_formas(self):
        with pytest.raises(PagamentoInvalido):
            PlanoPagamento.de_pagamentos(
                pagamento_dinheiro(Dinheiro(100)),
                pagamento_eletronico(FormaPagamento.PIX, Dinheiro(100)),
                pagamento_eletronico(FormaPagamento.DEBITO, Dinheiro(100)),
                pagamento_eletronico(FormaPagamento.CREDITO, Dinheiro(100)),
            )

    def test_plano_vazio(self):
        with pytest.raises(PagamentoInvalido):
            PlanoPagamento(())

    def test_pix_nasce_pendente_e_confirmacao_e_manual(self):
        pix = pagamento_eletronico(FormaPagamento.PIX, Dinheiro(500))
        assert pix.status is StatusPagamento.PENDENTE
        assert not pix.confirmado
        confirmado = pagamento_eletronico(FormaPagamento.PIX, Dinheiro(500), confirmado=True)
        assert confirmado.confirmado

    def test_crediario_nao_entra_na_gaveta(self):
        plano = PlanoPagamento.de_pagamentos(pagamento_a_prazo(Dinheiro(2700)))
        plano.validar_contra(Dinheiro(2700))
        assert plano.dinheiro_aplicado.centavos == 0

    def test_so_um_crediario_por_venda(self):
        with pytest.raises(PagamentoInvalido):
            PlanoPagamento.de_pagamentos(
                pagamento_a_prazo(Dinheiro(1000)), pagamento_a_prazo(Dinheiro(1700))
            )

    def test_credito_parcelado_exige_parcelas(self):
        with pytest.raises(PagamentoInvalido):
            pagamento_eletronico(FormaPagamento.CREDITO_PARCELADO, Dinheiro(1000), parcelas=1)


class TestConfiguracaoForma:
    def test_taxa_e_liquido(self):
        from bussola_pdv.dominio.dinheiro import Percentual
        from bussola_pdv.dominio.pagamentos import ConfiguracaoForma

        config = ConfiguracaoForma(forma=FormaPagamento.DEBITO, taxa=Percentual(200), prazo_dias=1)
        assert config.taxa_de(Dinheiro(10000)).centavos == 200
        assert config.valor_liquido(Dinheiro(10000)).centavos == 9800
