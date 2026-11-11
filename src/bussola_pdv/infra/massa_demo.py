"""Massa de demonstração **fictícia** — nenhum dado real de pessoa ou empresa.

Cobre o roteiro de aceite de docs/PLANO_TESTES.md do repositório de origem:
produtos em quatro categorias com estoque normal/baixo/zero, clientes com limite
esgotado e parcela vencida, vendas em três dias, três formas de pagamento, uma
venda cancelada e uma venda a prazo em três parcelas.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from ..aplicacao.caixa import ServicoCaixa
from ..aplicacao.contexto import Contexto
from ..aplicacao.crediario import ServicoCrediario
from ..aplicacao.estoque import ServicoEstoque
from ..aplicacao.pdv import ServicoPDV, SolicitacaoVenda
from ..dominio.caixa import TipoMovimentoCaixa, fracionar_em_denominacoes
from ..dominio.cliente import Cliente
from ..dominio.dinheiro import Dinheiro
from ..dominio.documentos import gerar_dv_ean13
from ..dominio.estoque import CriterioRateio, EntradaMercadoria, ItemEntrada
from ..dominio.pagamentos import (
    FormaPagamento,
    PlanoPagamento,
    pagamento_a_prazo,
    pagamento_dinheiro,
    pagamento_eletronico,
)
from ..dominio.produto import Produto
from ..dominio.relogio import RelogioFixo
from ..dominio.usuario import Perfil, Usuario
from ..dominio.venda import Carrinho
from .sqlite.repositorio_usuarios import UsuarioRepositorio

SENHA_DEMO = "Bussola#2026"
DIA_1 = "2026-11-09"
DIA_2 = "2026-11-10"
DIA_3 = "2026-11-11"
FUSO = "America/Sao_Paulo"


# `ean` é a base de 12 dígitos; o dígito verificador é calculado no cadastro,
# exatamente como aconteceria com um leitor real.
def relogio_demo() -> RelogioFixo:
    # 09/11/2026 08:00 em São Paulo (UTC-3)
    return RelogioFixo(datetime(2026, 11, 9, 11, 0, tzinfo=UTC), fuso=FUSO)


PRODUTOS_DEMO: list[dict[str, Any]] = [
    dict(codigo="P001", descricao="Café Torrado 500 g", categoria="Mercearia", unidade="UN",
         custo=Decimal("10.00"), preco=Decimal("15.90"), minimo=5, ponto=8, ean="789000000001"),
    dict(codigo="P002", descricao="Leite Integral 1 L", categoria="Mercearia", unidade="LT",
         custo=Decimal("4.20"), preco=Decimal("6.49"), minimo=12, ponto=18, ean="789000000002"),
    dict(codigo="P003", descricao="Arroz Tipo 1 5 kg", categoria="Mercearia", unidade="UN",
         custo=Decimal("22.50"), preco=Decimal("29.90"), minimo=4, ponto=6, ean="789000000003"),
    dict(codigo="P004", descricao="Feijão Carioca 1 kg", categoria="Mercearia", unidade="KG",
         custo=Decimal("6.80"), preco=Decimal("9.90"), minimo=6, ponto=10, ean="789000000004"),
    dict(codigo="P005", descricao="Açúcar Refinado 1 kg", categoria="Mercearia", unidade="KG",
         custo=Decimal("3.90"), preco=Decimal("5.90"), minimo=5, ponto=8, ean="789000000005"),
    dict(codigo="P006", descricao="Sabonete Glicerinado", categoria="Higiene", unidade="UN",
         custo=Decimal("1.60"), preco=Decimal("3.29"), minimo=10, ponto=16, ean="789000000006"),
    dict(codigo="P007", descricao="Shampoo 350 ml", categoria="Higiene", unidade="UN",
         custo=Decimal("9.90"), preco=Decimal("16.90"), minimo=6, ponto=10, ean="789000000007"),
    dict(codigo="P008", descricao="Pasta de Dente 90 g", categoria="Higiene", unidade="UN",
         custo=Decimal("3.20"), preco=Decimal("6.49"), minimo=8, ponto=12, ean="789000000008"),
    dict(codigo="P009", descricao="Papel Higiênico 12 rolos", categoria="Higiene", unidade="CX",
         custo=Decimal("17.90"), preco=Decimal("27.90"), minimo=4, ponto=6, ean="789000000009"),
    dict(codigo="P010", descricao="Refrigerante Cola 2 L", categoria="Bebidas", unidade="UN",
         custo=Decimal("6.40"), preco=Decimal("9.99"), minimo=10, ponto=15, ean="789000000010"),
    dict(codigo="P011", descricao="Água Mineral 500 ml", categoria="Bebidas", unidade="UN",
         custo=Decimal("0.90"), preco=Decimal("2.49"), minimo=24, ponto=36, ean="789000000011"),
    dict(codigo="P012", descricao="Suco de Uva 1 L", categoria="Bebidas", unidade="LT",
         custo=Decimal("7.50"), preco=Decimal("12.90"), minimo=6, ponto=9, ean="789000000012"),
    dict(codigo="P013", descricao="Detergente 500 ml", categoria="Limpeza", unidade="UN",
         custo=Decimal("1.85"), preco=Decimal("3.49"), minimo=12, ponto=20, ean="789000000013"),
    dict(codigo="P014", descricao="Sabão em Pó 1 kg", categoria="Limpeza", unidade="KG",
         custo=Decimal("8.90"), preco=Decimal("14.90"), minimo=6, ponto=10, ean="789000000014"),
    dict(codigo="P015", descricao="Desinfetante 2 L", categoria="Limpeza", unidade="LT",
         custo=Decimal("5.40"), preco=Decimal("9.49"), minimo=5, ponto=8, ean="789000000015"),
    dict(codigo="P016", descricao="Vassoura de Piaçava", categoria="Limpeza", unidade="UN",
         custo=Decimal("9.00"), preco=Decimal("17.90"), minimo=3, ponto=5, ean="789000000016"),
]

# Estoque inicial vindo de uma entrada de fornecedor (nunca saldo "solto").
ESTOQUE_INICIAL: dict[str, int] = {
    "P001": 20, "P002": 40, "P003": 10, "P004": 15, "P005": 15,
    "P006": 30, "P007": 12, "P008": 20, "P009": 8, "P010": 24,
    "P011": 60, "P012": 10, "P013": 36, "P014": 8, "P015": 5, "P016": 1,
}


def _criar_usuarios(ctx: Contexto) -> dict[str, Usuario]:
    from ..dominio.seguranca import gerar_hash

    repo = UsuarioRepositorio(ctx.conexao)
    agora = ctx.agora().isoformat()
    usuarios = {}
    # Ordem coerente com a hierarquia: o master é o primeiro e nunca é excluído.
    for login, nome, perfil in (
        ("master", "Dora Proprietária", Perfil.ADMIN_MASTER),
        ("admin", "Ana Administradora", Perfil.ADMIN),
        ("gerente", "Bruno Gerente", Perfil.GERENTE),
        ("contabilidade", "Elias Contador", Perfil.CONTABILIDADE),
        ("operador", "Carla Atendente", Perfil.ATENDENTE),
    ):
        usuario = Usuario(login=login, nome=nome, perfil=perfil, senha_hash=gerar_hash(SENHA_DEMO))
        repo.criar(usuario, criado_em=agora)
        # Recarrega com as permissões efetivas resolvidas (mesma regra da aplicação).
        usuarios[login] = repo.por_login(login)
    return usuarios


def _criar_produtos(ctx: Contexto, admin: Usuario) -> dict[str, Produto]:
    servico = ServicoEstoque(ctx)
    produtos: dict[str, Produto] = {}
    for dados in PRODUTOS_DEMO:
        ean = gerar_dv_ean13(dados["ean"])
        produto = servico.criar_produto(
            operador=admin,
            codigo=dados["codigo"],
            descricao=dados["descricao"],
            preco=Dinheiro.de_reais(dados["preco"]).centavos,
            custo=Dinheiro.de_reais(dados["custo"]).centavos,
            categoria=dados["categoria"],
            unidade=dados["unidade"],
            codigo_barras=ean,
            estoque_minimo=dados["minimo"] * (1000 if dados["unidade"] in ("KG", "LT") else 1),
            ponto_pedido=dados["ponto"] * (1000 if dados["unidade"] in ("KG", "LT") else 1),
            fornecedor="Distribuidora Exemplo Ltda.",
        )
        produtos[dados["codigo"]] = produto
    return produtos


def _entrada_inicial(ctx: Contexto, admin: Usuario, produtos: dict[str, Produto]) -> None:
    servico = ServicoEstoque(ctx)
    itens = []
    for codigo, quantidade in ESTOQUE_INICIAL.items():
        produto = produtos[codigo]
        itens.append(
            ItemEntrada(
                produto_id=produto.id,
                codigo=produto.codigo,
                quantidade=produto.quantidade(quantidade),
                custo_unitario=Dinheiro(produto.custo),
            )
        )
    entrada = EntradaMercadoria(
        fornecedor="Distribuidora Exemplo Ltda.",
        documento="NF-000123",
        itens=tuple(itens),
        frete=Dinheiro(4500),
        criterio=CriterioRateio.VALOR,
    )
    servico.registrar_entrada(operador=admin, entrada=entrada)


def _criar_clientes(ctx: Contexto, admin: Usuario) -> dict[str, Cliente]:
    dados = [
        ("Mariana Souza (fictícia)", "52998224725", 50000),
        ("João Pereira (fictício)", "11144477735", 20000),
        ("Mercadinho do Bairro (fictício)", "11222333000181", 100000),
        ("Cliente Limite Esgotado (fictício)", None, 0),
        ("Cliente com Atraso (fictício)", None, 30000),
    ]
    clientes: dict[str, Cliente] = {}
    for nome, documento, limite in dados:
        cliente = Cliente(nome=nome, documento=documento, limite_credito=limite)
        with ctx.em_transacao():
            ctx.clientes.criar(cliente, criado_em=ctx.agora().isoformat())
        clientes[nome.split(" (")[0]] = cliente
    return clientes


def _avancar_um_dia(ctx: Contexto) -> None:
    """Avança o relógio de demonstração; exige um relógio controlável."""
    relogio = ctx.relogio
    if not isinstance(relogio, RelogioFixo):  # pragma: no cover - configuração inválida
        raise RuntimeError("A massa de demonstração exige relogio_demo() (RelogioFixo).")
    relogio.avancar(days=1)


def popular(ctx: Contexto) -> dict:
    """Cria usuários, produtos, clientes, entrada, vendas de 3 dias e um turno aberto."""
    if ctx.usuarios.listar():
        raise RuntimeError("Banco já possui usuários; a massa demo não é aplicada duas vezes.")

    usuarios = _criar_usuarios(ctx)
    admin, gerente, operador = usuarios["admin"], usuarios["gerente"], usuarios["operador"]
    produtos = _criar_produtos(ctx, admin)
    _entrada_inicial(ctx, admin, produtos)
    clientes = _criar_clientes(ctx, admin)

    caixa_srv = ServicoCaixa(ctx)
    pdv = ServicoPDV(ctx)
    crediario = ServicoCrediario(ctx)
    caixa_nome = "Caixa 1"
    vendas: list[dict[str, Any]] = []

    def vender(
        itens: list[tuple[str, str]],
        montar_plano: Callable[[Dinheiro], PlanoPagamento],
        **kwargs: Any,
    ) -> dict[str, Any]:
        carrinho = Carrinho()
        for codigo, quantidade in itens:
            carrinho.adicionar(produtos[codigo], quantidade)
        total = carrinho.totais().total
        plano = montar_plano(total)
        resultado = pdv.finalizar_venda(
            SolicitacaoVenda(
                operador=operador,
                caixa_id=caixa_id,
                carrinho=carrinho,
                plano=plano,
                chave_idempotencia=f"demo-{len(vendas) + 1:03d}",
                **kwargs,
            )
        )
        vendas.append(
            {
                "numero": resultado.venda.rotulo,
                "total_centavos": resultado.venda.total.centavos,
                "status": resultado.venda.status.value,
            }
        )
        return {"resultado": resultado, "venda": resultado.venda}

    # ---------------- dia 1 ----------------
    turno = caixa_srv.abrir_turno(caixa=caixa_nome, operador=gerente, fundo=Dinheiro(15000))
    caixa_id = turno.caixa_id

    vender(
        [("P001", "2"), ("P002", "3")],
        lambda total: PlanoPagamento.de_pagamentos(pagamento_dinheiro(total, total + Dinheiro(2000))),
    )
    vender(
        [("P010", "2"), ("P011", "4")],
        lambda total: PlanoPagamento.de_pagamentos(
            pagamento_dinheiro(total - Dinheiro(2694)),
            pagamento_eletronico(FormaPagamento.PIX, Dinheiro(2694), referencia="PIX-DEMO-001"),
        ),
    )
    # Venda que será cancelada (com autorização de gerente).
    cancelada = vender(
        [("P006", "2")],
        lambda total: PlanoPagamento.de_pagamentos(pagamento_dinheiro(total, total + Dinheiro(500))),
    )
    # Venda a prazo em 3 parcelas.
    vender(
        [("P003", "1"), ("P005", "2")],
        lambda total: PlanoPagamento.de_pagamentos(pagamento_a_prazo(total)),
        cliente_id=clientes["Mariana Souza"].id,
        parcelas_crediario=3,
        primeiro_vencimento="2026-11-19",
    )
    # Venda a prazo do cliente que ficará em atraso.
    vender(
        [("P012", "1")],
        lambda total: PlanoPagamento.de_pagamentos(pagamento_a_prazo(total)),
        cliente_id=clientes["Cliente com Atraso"].id,
        parcelas_crediario=1,
        primeiro_vencimento="2026-11-10",
    )
    pdv.cancelar_venda(
        venda_id=cancelada["venda"].id,
        motivo="Cliente desistiu da compra antes de sair da loja",
        operador=operador,
        autorizador=gerente,
    )

    caixa_srv.movimentar(
        turno_id=turno.id,
        tipo=TipoMovimentoCaixa.SANGRIA,
        valor=Dinheiro(20000),
        motivo="Retirada para depósito conforme política da loja",
        operador=operador,
        autorizador=gerente,
    )
    caixa_srv.movimentar(
        turno_id=turno.id,
        tipo=TipoMovimentoCaixa.SUPRIMENTO,
        valor=Dinheiro(10000),
        motivo="Reforço de troco",
        operador=operador,
    )

    # Conferência: contagem real e uma diferença declarada de R$ 3,50 a menos.
    esperado = caixa_srv.ctx.caixas.carregar_turno(turno.id).esperado
    contado = esperado - Dinheiro(350)
    caixa_srv.fechar_turno(
        turno_id=turno.id,
        conferente=gerente,
        contagens=fracionar_em_denominacoes(contado),
        motivo_diferenca="Diferença de troco identificada na contagem (R$ 3,50 a menos)",
    )

    # ---------------- dia 2 ----------------
    _avancar_um_dia(ctx)
    turno = caixa_srv.abrir_turno(caixa=caixa_nome, operador=gerente, fundo=Dinheiro(10000))
    caixa_id = turno.caixa_id

    vender(
        [("P007", "1"), ("P008", "2"), ("P013", "3")],
        lambda total: PlanoPagamento.de_pagamentos(
            pagamento_eletronico(FormaPagamento.DEBITO, total, confirmado=True, nsu="000123")
        ),
    )
    vender(
        [("P012", "2")],
        lambda total: PlanoPagamento.de_pagamentos(
            pagamento_dinheiro(total, total + Dinheiro(2420))
        ),
    )
    # Recebimento de parcela do crediário (não é venda nova).
    titulos = crediario.listar(cliente_id=clientes["Mariana Souza"].id)
    if titulos:
        crediario.receber(
            titulo_id=titulos[0]["id"],
            valor=Dinheiro(1357),
            forma=FormaPagamento.DINHEIRO,
            operador=operador,
            caixa_id=caixa_id,
            referencia="Recibo 001",
        )

    roteiro_dia_2 = [
        ([("P001", "1")], "DINHEIRO"),
        ([("P002", "2"), ("P011", "2")], "PIX"),
        ([("P004", "1")], "DEBITO"),
        ([("P013", "2"), ("P014", "1")], "DINHEIRO"),
    ]
    for itens, forma in roteiro_dia_2:
        if forma == "DINHEIRO":
            def plano_com_troco(total: Dinheiro) -> PlanoPagamento:
                return PlanoPagamento.de_pagamentos(
                    pagamento_dinheiro(total, total + Dinheiro(1000))
                )

            vender(itens, plano_com_troco)
        else:
            forma_enum = FormaPagamento.PIX if forma == "PIX" else FormaPagamento.DEBITO
            def plano_eletronico(
                total: Dinheiro, forma: FormaPagamento = forma_enum
            ) -> PlanoPagamento:
                return PlanoPagamento.de_pagamentos(
                    pagamento_eletronico(forma, total, confirmado=True)
                )

            vender(itens, plano_eletronico)

    esperado = caixa_srv.ctx.caixas.carregar_turno(turno.id).esperado
    caixa_srv.fechar_turno(
        turno_id=turno.id,
        conferente=gerente,
        contagens=fracionar_em_denominacoes(esperado),
        motivo_diferenca="",
    )

    # ---------------- dia 3 (turno fica aberto para a demonstração) ---------
    _avancar_um_dia(ctx)
    turno = caixa_srv.abrir_turno(caixa=caixa_nome, operador=gerente, fundo=Dinheiro(20000))
    caixa_id = turno.caixa_id

    roteiro_dia_3 = [
        ([("P014", "1"), ("P015", "1"), ("P016", "1")], "SPLIT"),
        ([("P009", "1")], "CREDITO"),
        ([("P001", "3")], "DINHEIRO"),
        ([("P005", "2"), ("P006", "3")], "PIX"),
        ([("P010", "1"), ("P011", "6")], "DEBITO"),
    ]
    for itens, forma in roteiro_dia_3:
        if forma == "SPLIT":
            def plano_split(total: Dinheiro) -> PlanoPagamento:
                parte = Dinheiro(3000)
                return PlanoPagamento.de_pagamentos(
                    pagamento_dinheiro(parte),
                    pagamento_eletronico(FormaPagamento.PIX, total - parte, referencia="PIX-DEMO-002"),
                )

            vender(itens, plano_split)
        elif forma == "DINHEIRO":
            vender(itens, lambda total: PlanoPagamento.de_pagamentos(
                pagamento_dinheiro(total, total + Dinheiro(5000))))
        else:
            forma_enum = {"PIX": FormaPagamento.PIX, "DEBITO": FormaPagamento.DEBITO,
                          "CREDITO": FormaPagamento.CREDITO}[forma]
            def plano_credito(
                total: Dinheiro, forma: FormaPagamento = forma_enum
            ) -> PlanoPagamento:
                return PlanoPagamento.de_pagamentos(
                    pagamento_eletronico(forma, total, confirmado=True, nsu="DEMO")
                )

            vender(itens, plano_credito)

    return {
        "usuarios": {chave: valor.login for chave, valor in usuarios.items()},
        "senha_demo": SENHA_DEMO,
        "produtos": len(produtos),
        "clientes": len(clientes),
        "vendas": vendas,
        "turno_aberto": turno.id,
        "caixa_id": caixa_id,
    }
