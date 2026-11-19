"""Calculadora de encargos: a conta precisa fechar na mão.

A regra ainda **não** é cobrada (pendência P3). O que se prova aqui é a aritmética
que vai ser usada quando for: multa única, juros por dia, carência, e nenhum
centavo perdido em arredondamento.
"""

from __future__ import annotations

from datetime import date

import pytest

from bussola_pdv.dominio.dinheiro import Dinheiro, Percentual
from bussola_pdv.dominio.encargos import PoliticaEncargos, calcular_encargos
from bussola_pdv.dominio.erros import ErroValidacao

VENCIMENTO = date(2026, 10, 1)


class TestCalcularEncargos:
    def test_sem_atraso_nao_cobra_nada(self):
        resultado = calcular_encargos(
            Dinheiro(10_000), vencimento=VENCIMENTO, referencia=date(2026, 10, 1)
        )
        assert resultado.isento
        assert resultado.total.centavos == 0
        assert resultado.dias_cobrados == 0

    def test_antes_do_vencimento_tambem_e_isento(self):
        resultado = calcular_encargos(
            Dinheiro(10_000), vencimento=VENCIMENTO, referencia=date(2026, 9, 20)
        )
        assert resultado.isento
        assert resultado.dias_atraso == 0

    def test_multa_e_juros_de_um_mes(self):
        # R$ 100,00, 30 dias de atraso: 2% de multa (R$ 2,00) + 1% de juros (R$ 1,00).
        resultado = calcular_encargos(
            Dinheiro(10_000), vencimento=VENCIMENTO, referencia=date(2026, 10, 31)
        )
        assert resultado.dias_cobrados == 30
        assert resultado.multa.centavos == 200
        assert resultado.juros.centavos == 100
        assert resultado.total.centavos == 300
        assert resultado.total_com_encargos.centavos == 10_300

    def test_juros_sao_proporcionais_aos_dias(self):
        dez = calcular_encargos(
            Dinheiro(10_000), vencimento=VENCIMENTO, referencia=date(2026, 10, 11)
        )
        vinte = calcular_encargos(
            Dinheiro(10_000), vencimento=VENCIMENTO, referencia=date(2026, 10, 21)
        )
        assert dez.juros.centavos < vinte.juros.centavos
        assert dez.multa == vinte.multa  # multa é uma vez só

    def test_carencia_adia_o_inicio_da_cobranca(self):
        politica = PoliticaEncargos(carencia_dias=5)
        dentro = calcular_encargos(
            Dinheiro(5_000), vencimento=VENCIMENTO, referencia=date(2026, 10, 5), politica=politica
        )
        passou = calcular_encargos(
            Dinheiro(5_000), vencimento=VENCIMENTO, referencia=date(2026, 10, 10), politica=politica
        )
        assert dentro.isento
        assert passou.dias_atraso == 9
        assert passou.dias_cobrados == 4

    def test_memoria_de_conta_mostra_o_calculo(self):
        resultado = calcular_encargos(
            Dinheiro(10_000), vencimento=VENCIMENTO, referencia=date(2026, 10, 31)
        )
        texto = " ".join(resultado.memoria)
        assert "Multa 2,00%" in texto
        assert "Total de encargos" in texto

    def test_principal_negativo_e_recusado(self):
        with pytest.raises(ErroValidacao):
            calcular_encargos(Dinheiro(-1), vencimento=VENCIMENTO, referencia=VENCIMENTO)

    def test_politica_zero_nao_cobra(self):
        politica = PoliticaEncargos(multa=Percentual(0), juros_mes=Percentual(0))
        resultado = calcular_encargos(
            Dinheiro(10_000), vencimento=VENCIMENTO, referencia=date(2026, 11, 11), politica=politica
        )
        assert resultado.isento
        assert resultado.total.centavos == 0
