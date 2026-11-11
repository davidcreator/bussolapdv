"""Dinheiro, percentual e quantidade: precisão exata e arredondamento explícito."""

from decimal import Decimal

import pytest

from bussola_pdv.dominio.dinheiro import (
    Dinheiro,
    Percentual,
    Quantidade,
    arredondar_divisao,
)
from bussola_pdv.dominio.erros import ErroValidacao


class TestDinheiro:
    def test_formata_em_pt_br(self):
        assert Dinheiro(123456).formatado() == "R$ 1.234,56"
        assert Dinheiro(5).formatado() == "R$ 0,05"
        assert Dinheiro(-350).formatado() == "-R$ 3,50"
        assert str(Dinheiro.zero()) == "R$ 0,00"

    @pytest.mark.parametrize(
        ("texto", "centavos"),
        [
            ("27", 2700),
            ("27,00", 2700),
            ("1.234,56", 123456),
            ("R$ 0,05", 5),
            (" 12,5 ", 1250),
            ("-3,50", -350),
            ("1.234", 123400),
        ],
    )
    def test_le_texto_do_operador(self, texto, centavos):
        assert Dinheiro.de_texto(texto).centavos == centavos

    @pytest.mark.parametrize("texto", ["", "abc", "12,3,4", "R$", None])
    def test_rejeita_texto_invalido(self, texto):
        with pytest.raises(ErroValidacao):
            Dinheiro.de_texto(texto)

    def test_float_e_recusado(self):
        with pytest.raises(ErroValidacao):
            Dinheiro.de_reais(10.10)

    def test_soma_e_subtracao_sem_deriva(self):
        total = Dinheiro.zero()
        for _ in range(10):
            total = total + Dinheiro(10)
        assert total.centavos == 100
        assert (Dinheiro(1000) - Dinheiro(1)).centavos == 999

    def test_multiplicacao_por_quantidade_arredonda_meio_para_cima(self):
        preco = Dinheiro(3333)  # R$ 33,33
        assert preco.vezes_quantidade(Quantidade(1500)).centavos == 5000  # 49,995 -> 50,00
        assert preco.vezes_quantidade(Quantidade(1000)).centavos == 3333

    def test_percentual_exato(self):
        assert Dinheiro(1590).aplicar_percentual(Percentual.de_porcento("10")).centavos == 159
        # 5% de 33,33 = 1,6665 -> 1,67 (meio para cima)
        assert Dinheiro(3333).aplicar_percentual(Percentual(500)).centavos == 167

    def test_proporcional(self):
        assert Dinheiro(100).proporcional(1, 3).centavos == 33


class TestPercentual:
    @pytest.mark.parametrize(
        ("entrada", "bp"),
        [("5", 500), ("5%", 500), ("5,5", 550), ("0,01", 1), (Decimal("12.25"), 1225)],
    )
    def test_converte(self, entrada, bp):
        assert Percentual.de_porcento(entrada).bp == bp

    @pytest.mark.parametrize("entrada", ["-1", "101", "abc", 5.5])
    def test_rejeita(self, entrada):
        with pytest.raises(ErroValidacao):
            Percentual.de_porcento(entrada)


class TestQuantidade:
    def test_escala_e_conversao(self):
        assert Quantidade.de_unidades("2").milesimos == 2000
        assert Quantidade.de_unidades("1,250", escala=3).milesimos == 1250
        assert Quantidade.de_unidades(Decimal("0.5"), escala=3).milesimos == 500

    def test_rejeita_casas_alem_da_escala(self):
        with pytest.raises(ErroValidacao):
            Quantidade.de_unidades("1,25", escala=0)

    def test_rejeita_negativo_e_float(self):
        with pytest.raises(ErroValidacao):
            Quantidade.de_unidades("-1")
        with pytest.raises(ErroValidacao):
            Quantidade.de_unidades(1.5)

    def test_formatacao(self):
        assert Quantidade(2500).formatada() == "2,5"
        assert Quantidade(6000).formatada() == "6"


class TestArredondamento:
    @pytest.mark.parametrize(
        ("num", "den", "esperado"),
        [(5, 2, 3), (4, 2, 2), (1, 3, 0), (2, 3, 1), (-5, 2, -3), (2499, 1000, 2), (2500, 1000, 3)],
    )
    def test_divisao(self, num, den, esperado):
        assert arredondar_divisao(num, den) == esperado

    def test_divisao_por_zero(self):
        with pytest.raises(ZeroDivisionError):
            arredondar_divisao(1, 0)
