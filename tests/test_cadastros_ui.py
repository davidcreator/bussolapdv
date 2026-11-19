"""Cadastro pela tela: produto, cliente, entrada, ajuste e baixa de crediário.

Estes testes fecham o buraco que o manual apontava: até a v0.11.0 as quatro telas
só consultavam, e cadastrar dependia de alguém com acesso ao serviço. Aqui se
verifica o caminho do usuário — **o diálogo preenche, o serviço grava, a tela
mostra** — e o que o botão não pode fazer: furar permissão, gravar sem motivo,
receber sem caixa aberto ou aceitar documento repetido.
"""

from __future__ import annotations

import os

import pytest

from bussola_pdv.aplicacao.clientes import ServicoClientes
from bussola_pdv.aplicacao.estoque import ServicoEstoque
from bussola_pdv.dominio.dinheiro import Dinheiro, Quantidade
from bussola_pdv.dominio.erros import ErroValidacao
from bussola_pdv.dominio.estoque import EntradaMercadoria, ItemEntrada

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# ------------------------------------------------------------------ serviços
class TestServicoClientes:
    def test_cria_cliente_com_documento_e_limite(self, cenario):
        criado = ServicoClientes(cenario.ctx).criar_cliente(
            operador=cenario.gerente,
            nome="Bazar Amigo",
            documento="390.533.447-05",
            limite_credito=15000,
        )
        assert criado.nome == "Bazar Amigo"
        assert criado.limite_credito == 15000
        assert criado.documento == "39053344705"

    def test_operador_sem_permissao_nao_cadastra(self, cenario):
        with pytest.raises(Exception, match="permiss"):
            ServicoClientes(cenario.ctx).criar_cliente(
                operador=cenario.operador, nome="Sem permissão"
            )

    def test_documento_repetido_e_recusado_com_nome(self, cenario):
        from bussola_pdv.dominio.cliente import Cliente

        with cenario.ctx.em_transacao():
            cenario.ctx.clientes.criar(
                Cliente(nome="Já existe", documento="39053344705"),
                criado_em=cenario.ctx.agora().isoformat(),
            )
        with pytest.raises(ErroValidacao, match="Já existe cliente"):
            ServicoClientes(cenario.ctx).criar_cliente(
                operador=cenario.gerente, nome="Outro", documento="39053344705"
            )

    def test_alterar_limite_fica_na_auditoria(self, cenario):
        servico = ServicoClientes(cenario.ctx)
        cliente = servico.criar_cliente(operador=cenario.gerente, nome="Limite Baixo")
        servico.alterar_cliente(
            operador=cenario.gerente, cliente_id=cliente.id, limite_credito=25000
        )
        assert cenario.ctx.clientes.por_id(cliente.id).limite_credito == 25000
        eventos = cenario.ctx.auditoria.listar(limite=50, entidade_id=cliente.id)
        assert eventos, "alteração de limite precisa aparecer na auditoria"
        assert eventos[0].depois["limite_centavos"] == 25000
        assert eventos[0].motivo


class TestServicoEstoque:
    def test_alterar_produto_muda_preco_e_audita(self, cenario):
        servico = ServicoEstoque(cenario.ctx)
        alterado = servico.alterar_produto(
            operador=cenario.admin, produto_id=cenario.produto_a.id, preco=1790
        )
        assert alterado.preco == 1790
        assert cenario.ctx.produtos.por_id(cenario.produto_a.id).preco == 1790
        eventos = cenario.ctx.auditoria.listar(limite=50, entidade_id=cenario.produto_a.id)
        assert eventos[0].depois["preco_centavos"] == 1790
        assert eventos[0].antes["preco_centavos"] == cenario.produto_a.preco

    def test_alterar_produto_recusa_campo_desconhecido(self, cenario):
        with pytest.raises(ErroValidacao, match="não alterável"):
            ServicoEstoque(cenario.ctx).alterar_produto(
                operador=cenario.admin, produto_id=cenario.produto_a.id, saldo=10
            )

    def test_entrada_soma_estoque_e_recusa_documento_repetido(self, cenario):
        servico = ServicoEstoque(cenario.ctx)
        antes = cenario.ctx.estoque.saldo_milesimos(cenario.produto_a.id)
        entrada = EntradaMercadoria(
            fornecedor="Atacado Central",
            documento="NF-1001",
            itens=(
                ItemEntrada(
                    produto_id=cenario.produto_a.id,
                    codigo=cenario.produto_a.codigo,
                    quantidade=Quantidade.de_unidades("4"),
                    custo_unitario=Dinheiro(1000),
                ),
            ),
            frete=Dinheiro(500),
        )
        servico.registrar_entrada(operador=cenario.gerente, entrada=entrada)
        assert cenario.ctx.estoque.saldo_milesimos(cenario.produto_a.id) == antes + 4_000
        with pytest.raises(Exception, match="já registrada"):
            servico.registrar_entrada(operador=cenario.gerente, entrada=entrada)

    def test_ajuste_negativo_baixa_o_saldo(self, cenario):
        servico = ServicoEstoque(cenario.ctx)
        antes = cenario.ctx.estoque.saldo_milesimos(cenario.produto_a.id)
        novo = servico.ajustar(
            operador=cenario.gerente,
            autorizador=cenario.admin,
            produto_id=cenario.produto_a.id,
            quantidade="-2",
            motivo="Contagem encontrou falta",
        )
        assert novo == antes - 2_000

    def test_ajuste_exige_motivo_e_outro_autorizador(self, cenario):
        servico = ServicoEstoque(cenario.ctx)
        with pytest.raises(ErroValidacao, match="autorizador diferente"):
            servico.ajustar(
                operador=cenario.gerente,
                autorizador=cenario.gerente,
                produto_id=cenario.produto_a.id,
                quantidade="1",
                motivo="x",
            )
        with pytest.raises(ErroValidacao, match="motivo"):
            servico.ajustar(
                operador=cenario.gerente,
                autorizador=cenario.admin,
                produto_id=cenario.produto_a.id,
                quantidade="1",
                motivo="   ",
            )


# --------------------------------------------------------------------- telas
pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError, reason="PySide6 ausente")

pytestmark_ui = pytest.mark.ui


@pytest.fixture
def app():
    from PySide6.QtWidgets import QApplication

    from bussola_pdv.ui.tema import FOLHA_ESTILO

    aplicacao = QApplication.instance() or QApplication(["teste"])
    aplicacao.setStyleSheet(FOLHA_ESTILO)
    return aplicacao


class TestBotoesPorPermissao:
    @pytest.mark.ui
    def test_admin_ve_os_botoes_de_cadastro(self, app, cenario):
        from bussola_pdv.ui.telas_clientes import TelaClientes
        from bussola_pdv.ui.telas_consulta import TelaProdutos
        from bussola_pdv.ui.telas_crediario import TelaCrediario
        from bussola_pdv.ui.telas_estoque import TelaEstoque

        produtos = TelaProdutos(cenario.ctx, cenario.admin)
        assert produtos.botao_novo.text() == "Novo produto"
        clientes = TelaClientes(cenario.ctx, cenario.admin)
        assert clientes.botao_novo.text() == "Novo cliente"
        estoque = TelaEstoque(cenario.ctx, cenario.admin)
        assert estoque.botao_entrada.isEnabled()
        crediario = TelaCrediario(cenario.ctx, cenario.admin)
        assert crediario.botao_receber.isEnabled()
        for tela in (produtos, clientes, estoque, crediario):
            tela.deleteLater()

    @pytest.mark.ui
    def test_atendente_nao_ve_cadastro_de_produto(self, app, cenario):
        from bussola_pdv.ui.telas_consulta import TelaProdutos

        tela = TelaProdutos(cenario.ctx, cenario.operador)
        assert not hasattr(tela, "botao_novo"), "botão de cadastro não pode aparecer sem permissão"
        tela.deleteLater()


class TestDialogoProduto:
    @pytest.mark.ui
    def test_cadastra_produto_pela_tela(self, app, cenario):
        from bussola_pdv.ui.cadastros import DialogoProduto

        dialogo = DialogoProduto(cenario.ctx, cenario.admin)
        dialogo.campo_codigo.setText("C003")
        dialogo.campo_descricao.setText("Açúcar 1 kg")
        dialogo.campo_categoria.setText("Mercearia")
        dialogo.campo_custo.setText("4,20")
        dialogo.campo_preco.setText("6,90")
        dialogo.campo_minimo.setText("3")
        dialogo._salvar()
        assert dialogo.produto is not None
        gravado = cenario.ctx.produtos.por_codigo("C003")
        assert gravado.preco == 690
        assert gravado.estoque_minimo_milesimos == 3_000
        dialogo.deleteLater()

    @pytest.mark.ui
    def test_erro_aparece_na_tela_e_nao_fecha(self, app, cenario):
        from bussola_pdv.ui.cadastros import DialogoProduto

        dialogo = DialogoProduto(cenario.ctx, cenario.admin)
        dialogo.campo_codigo.setText("A001")  # já existe
        dialogo.campo_descricao.setText("Duplicado")
        dialogo.campo_preco.setText("10,00")
        dialogo._confirmar()
        assert dialogo.isVisible() is False  # não foi aceito
        assert "A001" in dialogo.mensagem.text() or "existe" in dialogo.mensagem.text().lower()
        dialogo.deleteLater()

    @pytest.mark.ui
    def test_altera_preco_do_produto_existente(self, app, cenario):
        from bussola_pdv.ui.cadastros import DialogoProduto

        dialogo = DialogoProduto(cenario.ctx, cenario.admin, produto=cenario.produto_a)
        assert dialogo.campo_codigo.text() == "A001"
        dialogo.campo_preco.setText("17,90")
        dialogo._salvar()
        assert cenario.ctx.produtos.por_id(cenario.produto_a.id).preco == 1790
        dialogo.deleteLater()


class TestDialogoCliente:
    @pytest.mark.ui
    def test_cadastra_cliente_pela_tela(self, app, cenario):
        from bussola_pdv.ui.cadastros import DialogoCliente

        dialogo = DialogoCliente(cenario.ctx, cenario.gerente)
        dialogo.campo_nome.setText("Dona Zulmira")
        dialogo.campo_documento.setText("390.533.447-05")
        dialogo.campo_limite.setText("80,00")
        dialogo._salvar()
        assert dialogo.cliente is not None
        assert dialogo.cliente.limite_credito == 8000
        dialogo.deleteLater()

    @pytest.mark.ui
    def test_documento_invalido_mostra_o_motivo(self, app, cenario):
        from bussola_pdv.ui.cadastros import DialogoCliente

        dialogo = DialogoCliente(cenario.ctx, cenario.gerente)
        dialogo.campo_nome.setText("Documento errado")
        dialogo.campo_documento.setText("111.111.111-11")
        dialogo._confirmar()
        assert dialogo.mensagem.text()
        assert dialogo.cliente is None
        dialogo.deleteLater()


class TestDialogoEntrada:
    @pytest.mark.ui
    def test_lanca_item_e_registra_entrada(self, app, cenario):
        from bussola_pdv.ui.cadastros import DialogoEntrada

        antes = cenario.ctx.estoque.saldo_milesimos(cenario.produto_a.id)
        dialogo = DialogoEntrada(cenario.ctx, cenario.gerente)
        dialogo.campo_fornecedor.setText("Atacado Central")
        dialogo.campo_documento.setText("NF-2002")
        dialogo.campo_codigo.setText("A001")
        dialogo.campo_quantidade.setText("5")
        dialogo.campo_custo.setText("10,50")
        dialogo._adicionar_item()
        assert len(dialogo.itens) == 1
        dialogo.campo_frete.setText("2,00")
        dialogo._salvar()
        assert dialogo.resultado is not None
        assert cenario.ctx.estoque.saldo_milesimos(cenario.produto_a.id) == antes + 5_000
        dialogo.deleteLater()

    @pytest.mark.ui
    def test_entrada_sem_item_nao_grava(self, app, cenario):
        from bussola_pdv.ui.cadastros import DialogoEntrada

        dialogo = DialogoEntrada(cenario.ctx, cenario.gerente)
        dialogo.campo_fornecedor.setText("Atacado Central")
        dialogo._confirmar()
        assert dialogo.resultado is None
        assert "item" in dialogo.mensagem.text().lower()
        dialogo.deleteLater()


class TestDialogoAjuste:
    @pytest.mark.ui
    def test_ajuste_pela_tela_pede_autorizacao(self, app, cenario, hash_senha):
        from bussola_pdv.ui.cadastros import DialogoAjusteEstoque

        pytest.importorskip("argon2")
        antes = cenario.ctx.estoque.saldo_milesimos(cenario.produto_a.id)
        dialogo = DialogoAjusteEstoque(cenario.ctx, cenario.gerente)
        dialogo.campo_codigo.setText("A001")
        dialogo.campo_quantidade.setText("-1")
        dialogo.campo_motivo.setText("Avaria")
        dialogo.campo_login.setText("admin")
        dialogo.campo_senha.setText("senha-de-teste")
        dialogo._salvar()
        assert dialogo.novo_saldo == antes - 1_000
        dialogo.deleteLater()

    @pytest.mark.ui
    def test_senha_errada_nao_grava(self, app, cenario):
        from bussola_pdv.ui.cadastros import DialogoAjusteEstoque

        pytest.importorskip("argon2")
        antes = cenario.ctx.estoque.saldo_milesimos(cenario.produto_a.id)
        dialogo = DialogoAjusteEstoque(cenario.ctx, cenario.gerente)
        dialogo.campo_codigo.setText("A001")
        dialogo.campo_quantidade.setText("1")
        dialogo.campo_motivo.setText("Contagem")
        dialogo.campo_login.setText("admin")
        dialogo.campo_senha.setText("senha-errada")
        dialogo._confirmar()
        assert cenario.ctx.estoque.saldo_milesimos(cenario.produto_a.id) == antes
        assert dialogo.mensagem.text()
        dialogo.deleteLater()


class TestDialogoRecebimento:
    @pytest.mark.ui
    def test_recebe_parcela_do_crediario(self, app, cenario):
        from bussola_pdv.aplicacao.crediario import ServicoCrediario
        from bussola_pdv.aplicacao.pdv import ServicoPDV, SolicitacaoVenda
        from bussola_pdv.dominio.pagamentos import PlanoPagamento, pagamento_a_prazo
        from bussola_pdv.dominio.venda import Carrinho
        from bussola_pdv.ui.cadastros import DialogoRecebimento

        carrinho = Carrinho()
        carrinho.adicionar(cenario.produto_a, "4")
        total = carrinho.totais().total
        ServicoPDV(cenario.ctx).finalizar_venda(
            SolicitacaoVenda(
                operador=cenario.operador,
                caixa_id=cenario.caixa_id,
                carrinho=carrinho,
                plano=PlanoPagamento.de_pagamentos(pagamento_a_prazo(total)),
                cliente_id=cenario.cliente.id,
                parcelas_crediario=2,
            )
        )
        dialogo = DialogoRecebimento(cenario.ctx, cenario.gerente)
        assert dialogo.titulos, "a venda a prazo precisa gerar título em aberto"
        dialogo.campo_valor.setText("5,00")
        dialogo._salvar()
        assert dialogo.resultado is not None
        assert dialogo.resultado.entrou_no_caixa is True
        assert dialogo.resultado.saldo_restante.centavos > 0
        restantes = ServicoCrediario(cenario.ctx).listar(incluir_pagos=False)
        assert any(int(titulo["recebido_centavos"]) == 500 for titulo in restantes)
        dialogo.deleteLater()

    @pytest.mark.ui
    def test_sem_turno_aberto_avisa_em_vez_de_gravar(self, app, cenario, monkeypatch):
        from bussola_pdv.aplicacao.pdv import ServicoPDV, SolicitacaoVenda
        from bussola_pdv.dominio.pagamentos import PlanoPagamento, pagamento_a_prazo
        from bussola_pdv.dominio.venda import Carrinho
        from bussola_pdv.ui.cadastros import DialogoRecebimento

        carrinho = Carrinho()
        carrinho.adicionar(cenario.produto_a, "2")
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
        # ninguém abriu o caixa nesta sessão: receber em dinheiro não tem onde entrar
        monkeypatch.setattr(
            type(cenario.ctx.caixas), "turno_aberto", lambda self, caixa_id: None
        )

        dialogo = DialogoRecebimento(cenario.ctx, cenario.gerente)
        dialogo.campo_valor.setText("1,00")
        dialogo._confirmar()
        assert dialogo.resultado is None
        assert dialogo.mensagem.text()
        dialogo.deleteLater()


class TestTelaEntradas:
    @pytest.mark.ui
    def test_mostra_o_historico_e_exporta(self, app, cenario):
        from bussola_pdv.aplicacao.estoque import ServicoEstoque
        from bussola_pdv.dominio.dinheiro import Quantidade
        from bussola_pdv.dominio.estoque import EntradaMercadoria, ItemEntrada
        from bussola_pdv.ui.telas_entradas import TelaEntradas

        ServicoEstoque(cenario.ctx).registrar_entrada(
            operador=cenario.gerente,
            entrada=EntradaMercadoria(
                fornecedor="Atacado Central",
                documento="NF-3003",
                itens=(
                    ItemEntrada(
                        produto_id=cenario.produto_a.id,
                        codigo=cenario.produto_a.codigo,
                        quantidade=Quantidade.de_unidades("6"),
                        custo_unitario=Dinheiro(1000),
                    ),
                ),
                frete=Dinheiro(300),
            ),
        )
        tela = TelaEntradas(cenario.ctx, cenario.gerente)
        assert tela.tabela.rowCount() == 1
        assert tela.tabela.item(0, 1).text() == "Atacado Central"
        assert tela.kpi_entradas.valor.text() == "1"

        relatorio = cenario.ctx and tela.exportacao.relatorio_entradas()
        assert relatorio.tabelas[0].linhas[0][1] == "Atacado Central"
        assert relatorio.indicadores[1][1] == "1"
        tela.deleteLater()
