"""Carrinho, consolidação de itens, descontos e política de desconto."""

import pytest

from bussola_pdv.dominio.dinheiro import Dinheiro, Percentual
from bussola_pdv.dominio.erros import CarrinhoVazio, ErroValidacao, EstoqueInsuficiente
from bussola_pdv.dominio.produto import Produto, StatusEstoque, Unidade, classificar_estoque
from bussola_pdv.dominio.venda import (
    Carrinho,
    ExigenciaDesconto,
    ItemCarrinho,
    PoliticaDesconto,
)


def produto(codigo="A001", preco=1590, custo=1000, unidade=Unidade.UN) -> Produto:
    return Produto(codigo=codigo, descricao=f"Produto {codigo}", preco=preco, custo=custo, unidade=unidade)


class TestItem:
    def test_total_do_item(self):
        item = ItemCarrinho.do_produto(produto(), "2")
        assert item.bruto.centavos == 3180
        assert item.total.centavos == 3180
        assert item.custo_total.centavos == 2000

    def test_desconto_do_item(self):
        item = ItemCarrinho.do_produto(produto(), "2", desconto=Dinheiro(180))
        assert item.total.centavos == 3000

    def test_desconto_maior_que_bruto(self):
        with pytest.raises(ErroValidacao):
            ItemCarrinho.do_produto(produto(), "1", desconto=Dinheiro(9999))

    def test_quantidade_fracionada_respeita_unidade(self):
        item = ItemCarrinho.do_produto(produto(unidade=Unidade.KG, preco=990), "1,5")
        assert item.quantidade.milesimos == 1500
        assert item.bruto.centavos == 1485

    def test_unidade_discreta_rejeita_fracao(self):
        with pytest.raises(ErroValidacao):
            ItemCarrinho.do_produto(produto(unidade=Unidade.UN), "1,5")


class TestCarrinho:
    def test_consolida_mesmo_produto(self):
        carrinho = Carrinho()
        p = produto()
        carrinho.adicionar(p, "1")
        carrinho.adicionar(p, "2")
        assert len(carrinho) == 1
        assert carrinho.itens[0].quantidade.milesimos == 3000

    def test_remove(self):
        carrinho = Carrinho()
        p = produto()
        carrinho.adicionar(p, "1")
        carrinho.remover(p.id)
        assert carrinho.vazio

    def test_totais_com_desconto_e_acrescimo(self):
        carrinho = Carrinho()
        carrinho.adicionar(produto(), "2")  # 31,80
        totais = carrinho.totais(desconto_cupom=Dinheiro(300), acrescimo=Dinheiro(100))
        assert totais.subtotal.centavos == 3180
        assert totais.desconto_total.centavos == 300
        assert totais.total.centavos == 2980

    def test_carrinho_vazio_nao_calcula(self):
        with pytest.raises(CarrinhoVazio):
            Carrinho().totais()

    def test_desconto_maior_que_total(self):
        carrinho = Carrinho()
        carrinho.adicionar(produto(), "1")
        with pytest.raises(ErroValidacao):
            carrinho.totais(desconto_cupom=Dinheiro(2000))

    def test_percentual_efetivo(self):
        carrinho = Carrinho()
        carrinho.adicionar(produto(preco=10000), "1")
        totais = carrinho.totais(desconto_cupom=Dinheiro(1500))
        assert carrinho.percentual_desconto(totais) == Percentual(1500)

    def test_estoque_suficiente(self):
        carrinho = Carrinho()
        p = produto()
        carrinho.adicionar(p, "2")
        carrinho.verificar_estoque({p.id: 2000})

    def test_estoque_insuficiente(self):
        carrinho = Carrinho()
        p = produto()
        carrinho.adicionar(p, "3")
        with pytest.raises(EstoqueInsuficiente) as erro:
            carrinho.verificar_estoque({p.id: 2000})
        assert "A001" in str(erro.value)

    def test_estoque_insuficiente_autorizado(self):
        carrinho = Carrinho()
        p = produto()
        carrinho.adicionar(p, "3")
        carrinho.verificar_estoque({p.id: 2000}, permitir_negativo=True)


class TestPoliticaDesconto:
    def test_classificacao(self):
        politica = PoliticaDesconto(
            limite_operador=Percentual(500), limite_gerente=Percentual(1500)
        )
        assert politica.classificar(Percentual(0)) is ExigenciaDesconto.PERMITIDO
        assert politica.classificar(Percentual(500)) is ExigenciaDesconto.PERMITIDO
        assert politica.classificar(Percentual(501)) is ExigenciaDesconto.REQUER_GERENTE
        assert politica.classificar(Percentual(1500)) is ExigenciaDesconto.REQUER_GERENTE
        assert politica.classificar(Percentual(1501)) is ExigenciaDesconto.PROIBIDO


class TestStatusEstoque:
    @pytest.mark.parametrize(
        ("saldo", "status"),
        [
            (-1, StatusEstoque.RUPTURA),
            (0, StatusEstoque.RUPTURA),
            (1, StatusEstoque.BAIXO),
            (2000, StatusEstoque.BAIXO),
            (2500, StatusEstoque.REPOSICAO),
            (5000, StatusEstoque.OK),
        ],
    )
    def test_classificacao(self, saldo, status):
        assert (
            classificar_estoque(saldo, minimo_milesimos=2000, ponto_pedido_milesimos=3000) is status
        )


class TestProduto:
    def test_preco_zero_invalido(self):
        with pytest.raises(ErroValidacao):
            Produto(codigo="X", descricao="X", preco=0, custo=0)

    def test_margem_e_markup(self):
        p = Produto(codigo="X", descricao="X", preco=1500, custo=1000)
        assert p.margem().bp == 3333  # 33,33% sobre a venda
        assert round(float(p.markup()), 4) == 0.5  # 50% sobre o custo

    def test_ean_invalido_no_cadastro(self):
        with pytest.raises(ErroValidacao):
            Produto(codigo="X", descricao="X", preco=100, custo=50, codigo_barras="1234567890123")
