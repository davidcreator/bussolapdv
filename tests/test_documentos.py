"""CPF, CNPJ (numérico e alfanumérico) e EAN: validação estrutural."""

import pytest

from bussola_pdv.dominio.documentos import (
    formatar_cnpj,
    formatar_cpf,
    gerar_dv_ean13,
    validar_cnpj,
    validar_cpf,
    validar_documento,
    validar_ean,
)
from bussola_pdv.dominio.erros import ErroValidacao


class TestCPF:
    def test_aceita_formatado_e_devolve_digitos(self):
        assert validar_cpf("529.982.247-25") == "52998224725"

    @pytest.mark.parametrize("invalido", ["52998224724", "11111111111", "123", "529982247251"])
    def test_rejeita(self, invalido):
        with pytest.raises(ErroValidacao):
            validar_cpf(invalido)

    def test_formata(self):
        assert formatar_cpf("52998224725") == "529.982.247-25"


class TestCNPJ:
    def test_numerico_valido(self):
        assert validar_cnpj("11.222.333/0001-81") == "11222333000181"
        assert formatar_cnpj("11222333000181") == "11.222.333/0001-81"

    def test_numerico_dv_errado(self):
        with pytest.raises(ErroValidacao):
            validar_cnpj("11222333000182")

    def test_alfanumerico_valido(self):
        # Estrutura da IN RFB 2.229/2024: 12 posições alfanuméricas + 2 DVs.
        assert validar_cnpj("12ABC34501DE35") == "12ABC34501DE35"

    def test_alfanumerico_dv_errado(self):
        with pytest.raises(ErroValidacao):
            validar_cnpj("12ABC34501DE36")

    def test_alfanumerico_rejeita_simbolos(self):
        with pytest.raises(ErroValidacao):
            validar_cnpj("12ABC34501D-35")

    def test_deteccao_automatica(self):
        assert validar_documento("52998224725")[0] == "CPF"
        assert validar_documento("11222333000181")[0] == "CNPJ"
        with pytest.raises(ErroValidacao):
            validar_documento("1234")


class TestEAN:
    def test_ean13_valido(self):
        assert validar_ean("7891234567895") == "7891234567895"

    def test_ean13_dv_errado(self):
        with pytest.raises(ErroValidacao):
            validar_ean("7891234567890")

    def test_gerar_dv(self):
        assert gerar_dv_ean13("789123456789") == "7891234567895"
        assert validar_ean(gerar_dv_ean13("789000000001")) == "7890000000017"

    def test_tamanho_invalido(self):
        with pytest.raises(ErroValidacao):
            validar_ean("12345")
