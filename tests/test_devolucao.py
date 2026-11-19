"""Devolução/estorno: domínio, serviço e o caminho da tela.

O que se prova aqui é o que o balcão vai perguntar na frente do cliente:

* devolver **parte** não mexe no resto da venda, e devolver **tudo** não pode
  passar do que foi vendido;
* o **prazo** vem do tipo (7 dias de arrependimento, 90 de defeito) e a garantia
  do produto só aumenta; fora do prazo, alguém responde pelo que autorizou;
* o dinheiro só sai com **caixa aberto** — senão o turno não fecha;
* o **crédito** abate parcela do crediário em aberto, como recebimento em vale;
* a **troca** não movimenta dinheiro;
* a venda original **não é apagada** e o estoque volta como movimento de estorno;
* a devolução é imutável (o banco recusa UPDATE/DELETE).
"""

from __future__ import annotations

import os
from datetime import date

import pytest

from bussola_pdv.aplicacao.devolucao import ItemSolicitado, ServicoDevolucao
from bussola_pdv.aplicacao.pdv import ServicoPDV, SolicitacaoVenda
from bussola_pdv.dominio.devolucao import (
    DestinoDevolucao,
    ItemDevolvido,
    PoliticaDevolucao,
    TipoDevolucao,
    avaliar_prazo,
)
from bussola_pdv.dominio.dinheiro import Dinheiro, Quantidade
from bussola_pdv.dominio.erros import ErroConflito, ErroValidacao, TurnoNaoAberto
from bussola_pdv.dominio.pagamentos import PlanoPagamento, pagamento_a_prazo, pagamento_dinheiro
from bussola_pdv.dominio.venda import Carrinho

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# ---------------------------------------------------------------- utilitários
def _venda(cenario, quantidade: str = "4", *, a_prazo: bool = False) -> str:
    carrinho = Carrinho()
    carrinho.adicionar(cenario.produto_a, quantidade)
    total = carrinho.totais().total
    plano = (
        PlanoPagamento.de_pagamentos(pagamento_a_prazo(total))
        if a_prazo
        else PlanoPagamento.de_pagamentos(pagamento_dinheiro(total))
    )
    resultado = ServicoPDV(cenario.ctx).finalizar_venda(
        SolicitacaoVenda(
            operador=cenario.operador,
            caixa_id=cenario.caixa_id,
            carrinho=carrinho,
            plano=plano,
            cliente_id=cenario.cliente.id if a_prazo else None,
            parcelas_crediario=1,
        )
    )
    return resultado.venda.id


def _primeiro_item(cenario, venda_id: str) -> int:
    return int(cenario.ctx.vendas.itens(venda_id)[0]["sequencia"])


# --------------------------------------------------------------------- domínio
class TestDominioDevolucao:
    def test_total_do_item_respeita_fracao(self):
        item = ItemDevolvido(
            produto_id="p",
            codigo="A001",
            descricao="Café",
            quantidade=Quantidade(1_500),
            valor_unitario=Dinheiro(1000),
        )
        assert item.total.centavos == 1500

    def test_devolucao_sem_motivo_e_sem_item_nao_existe(self):
        with pytest.raises(ErroValidacao, match="maior que zero"):
            ItemDevolvido(
                produto_id="p",
                codigo="A",
                descricao="x",
                quantidade=Quantidade(0),
                valor_unitario=Dinheiro(100),
            )

    def test_arrependimento_tem_sete_dias(self):
        avaliacao = avaliar_prazo(
            TipoDevolucao.ARREPENDIMENTO,
            data_venda=date(2026, 11, 1),
            data_devolucao=date(2026, 11, 8),
            politica=PoliticaDevolucao(),
        )
        assert avaliacao.dentro_do_prazo
        assert avaliacao.limite_dias == 7

    def test_garantia_do_produto_aumenta_o_prazo(self):
        politica = PoliticaDevolucao(defeito_dias=90)
        com_garantia = politica.prazo_do_tipo(TipoDevolucao.GARANTIA, garantia_produto_dias=365)
        sem_garantia = politica.prazo_do_tipo(TipoDevolucao.GARANTIA, garantia_produto_dias=0)
        assert com_garantia == 365
        assert sem_garantia == 0

    def test_erro_operacional_nao_tem_prazo(self):
        avaliacao = avaliar_prazo(
            TipoDevolucao.ERRO_OPERACIONAL,
            data_venda=date(2020, 1, 1),
            data_devolucao=date(2026, 11, 11),
            politica=PoliticaDevolucao(),
        )
        assert avaliacao.dentro_do_prazo
        assert avaliacao.limite_dias == -1


# --------------------------------------------------------------------- serviço
class TestServicoDevolucao:
    def test_devolve_um_item_devolvendo_estoque_e_dinheiro(self, cenario):
        venda_id = _venda(cenario, "4")
        antes = cenario.ctx.estoque.saldo_milesimos(cenario.produto_a.id)
        sequencia = _primeiro_item(cenario, venda_id)
        resultado = ServicoDevolucao(cenario.ctx).registrar(
            operador=cenario.gerente,
            venda_id=venda_id,
            itens=[ItemSolicitado(sequencia, "2")],
            tipo=TipoDevolucao.ARREPENDIMENTO,
            destino=DestinoDevolucao.DINHEIRO,
            motivo="Cliente desistiu",
            autorizador=cenario.admin,
            caixa_id=cenario.caixa_id,
        )
        assert resultado.total.centavos == 2 * cenario.produto_a.preco
        assert resultado.dinheiro_devolvido == resultado.total
        assert resultado.estoque_devolvido
        assert cenario.ctx.estoque.saldo_milesimos(cenario.produto_a.id) == antes + 2_000

    def test_venda_continua_intacta_e_devolucao_fica_na_auditoria(self, cenario):
        venda_id = _venda(cenario, "3")
        sequencia = _primeiro_item(cenario, venda_id)
        devolucao = ServicoDevolucao(cenario.ctx).registrar(
            operador=cenario.gerente,
            venda_id=venda_id,
            itens=[ItemSolicitado(sequencia, "1")],
            tipo=TipoDevolucao.ERRO_OPERACIONAL,
            destino=DestinoDevolucao.TROCA,
            motivo="Item errado no cupom",
        )
        venda = cenario.ctx.vendas.por_id(venda_id)
        assert venda.status.value == "CONCLUIDA"
        assert len(cenario.ctx.vendas.itens(venda_id)) == 1
        eventos = [
            evento
            for evento in cenario.ctx.auditoria.listar(limite=20)
            if evento.acao == "DEVOLUCAO_REGISTRADA"
        ]
        assert eventos
        assert eventos[0].entidade_id == devolucao.devolucao_id
        assert eventos[0].depois["tipo"] == "ERRO_OPERACIONAL"

    def test_nao_devolve_mais_do_que_vendeu(self, cenario):
        venda_id = _venda(cenario, "2")
        sequencia = _primeiro_item(cenario, venda_id)
        servico = ServicoDevolucao(cenario.ctx)
        servico.registrar(
            operador=cenario.gerente,
            venda_id=venda_id,
            itens=[ItemSolicitado(sequencia, "1")],
            tipo=TipoDevolucao.ARREPENDIMENTO,
            destino=DestinoDevolucao.TROCA,
            motivo="Troca de tamanho",
        )
        with pytest.raises(ErroValidacao, match="só resta"):
            servico.registrar(
                operador=cenario.gerente,
                venda_id=venda_id,
                itens=[ItemSolicitado(sequencia, "2")],
                tipo=TipoDevolucao.ARREPENDIMENTO,
                destino=DestinoDevolucao.TROCA,
                motivo="Troca de tamanho",
            )

    def test_dinheiro_exige_autorizacao_e_caixa_aberto(self, cenario):
        venda_id = _venda(cenario, "2")
        sequencia = _primeiro_item(cenario, venda_id)
        servico = ServicoDevolucao(cenario.ctx)
        with pytest.raises(ErroValidacao, match="autorização"):
            servico.registrar(
                operador=cenario.gerente,
                venda_id=venda_id,
                itens=[ItemSolicitado(sequencia, "1")],
                tipo=TipoDevolucao.ARREPENDIMENTO,
                destino=DestinoDevolucao.DINHEIRO,
                motivo="Desistiu",
            )
        with pytest.raises(TurnoNaoAberto):
            servico.registrar(
                operador=cenario.gerente,
                venda_id=venda_id,
                itens=[ItemSolicitado(sequencia, "1")],
                tipo=TipoDevolucao.ARREPENDIMENTO,
                destino=DestinoDevolucao.DINHEIRO,
                motivo="Desistiu",
                autorizador=cenario.admin,
            )

    def test_fora_do_prazo_exige_outro_autorizador(self, cenario):
        venda_id = _venda(cenario, "2")
        sequencia = _primeiro_item(cenario, venda_id)
        servico = ServicoDevolucao(cenario.ctx)
        with pytest.raises(ErroValidacao, match="Fora do prazo"):
            servico.registrar(
                operador=cenario.gerente,
                venda_id=venda_id,
                itens=[ItemSolicitado(sequencia, "1")],
                tipo=TipoDevolucao.ARREPENDIMENTO,
                destino=DestinoDevolucao.TROCA,
                motivo="Desistiu depois",
                data_referencia="2026-12-31",  # 50 dias depois da venda da demo
            )
        resultado = servico.registrar(
            operador=cenario.gerente,
            venda_id=venda_id,
            itens=[ItemSolicitado(sequencia, "1")],
            tipo=TipoDevolucao.ARREPENDIMENTO,
            destino=DestinoDevolucao.TROCA,
            motivo="Desistiu depois",
            autorizador=cenario.admin,
            data_referencia="2026-12-31",
        )
        assert resultado.prazo.exige_autorizacao
        assert any("Fora do prazo" in aviso for aviso in resultado.avisos)

    def test_credito_abate_parcelas_do_crediario(self, cenario):
        venda_id = _venda(cenario, "4", a_prazo=True)
        sequencia = _primeiro_item(cenario, venda_id)
        saldo_antes = int(cenario.ctx.clientes.saldo_devedor(cenario.cliente.id))
        resultado = ServicoDevolucao(cenario.ctx).registrar(
            operador=cenario.gerente,
            venda_id=venda_id,
            itens=[ItemSolicitado(sequencia, "1")],
            tipo=TipoDevolucao.DEFEITO,
            destino=DestinoDevolucao.CREDITO_CREDIARIO,
            motivo="Produto com defeito",
            caixa_id=cenario.caixa_id,
        )
        assert resultado.credito_aplicado.centavos == cenario.produto_a.preco
        assert resultado.titulos_abatidos
        saldo_depois = int(cenario.ctx.clientes.saldo_devedor(cenario.cliente.id))
        assert saldo_depois == saldo_antes - cenario.produto_a.preco

    def test_operador_sem_permissao_nao_devolve(self, cenario):
        venda_id = _venda(cenario, "1")
        sequencia = _primeiro_item(cenario, venda_id)
        with pytest.raises(Exception, match="permiss"):
            ServicoDevolucao(cenario.ctx).registrar(
                operador=cenario.operador,
                venda_id=venda_id,
                itens=[ItemSolicitado(sequencia, "1")],
                tipo=TipoDevolucao.ARREPENDIMENTO,
                destino=DestinoDevolucao.TROCA,
                motivo="x",
            )

    def test_venda_cancelada_nao_recebe_devolucao(self, cenario):
        venda_id = _venda(cenario, "1")
        ServicoPDV(cenario.ctx).cancelar_venda(
            venda_id=venda_id,
            motivo="erro de digitação",
            operador=cenario.gerente,
            autorizador=cenario.admin,
        )
        sequencia = _primeiro_item(cenario, venda_id)
        with pytest.raises(ErroConflito, match="cancelada"):
            ServicoDevolucao(cenario.ctx).registrar(
                operador=cenario.gerente,
                venda_id=venda_id,
                itens=[ItemSolicitado(sequencia, "1")],
                tipo=TipoDevolucao.ARREPENDIMENTO,
                destino=DestinoDevolucao.TROCA,
                motivo="x",
            )

    def test_devolucao_nao_pode_ser_editada_no_banco(self, cenario):
        venda_id = _venda(cenario, "1")
        sequencia = _primeiro_item(cenario, venda_id)
        devolucao = ServicoDevolucao(cenario.ctx).registrar(
            operador=cenario.gerente,
            venda_id=venda_id,
            itens=[ItemSolicitado(sequencia, "1")],
            tipo=TipoDevolucao.ARREPENDIMENTO,
            destino=DestinoDevolucao.TROCA,
            motivo="Troca",
        )
        with pytest.raises(Exception, match="não pode ser alterada"):
            cenario.ctx.conexao.execute(
                "UPDATE devolucoes SET motivo = 'outro' WHERE id = ?", (devolucao.devolucao_id,)
            )


    def test_itens_gravados_conferem_com_o_que_foi_devolvido(self, cenario):
        """`itens()` lê do banco: quantidade, valor líquido e total de cada linha."""
        venda_id = _venda(cenario, "2")
        sequencia = _primeiro_item(cenario, venda_id)
        liquido = next(
            item for item in cenario.ctx.vendas.itens(venda_id) if item["sequencia"] == sequencia
        )
        devolucao = ServicoDevolucao(cenario.ctx).registrar(
            operador=cenario.gerente,
            venda_id=venda_id,
            itens=[ItemSolicitado(sequencia, "1")],
            tipo=TipoDevolucao.ARREPENDIMENTO,
            destino=DestinoDevolucao.TROCA,
            motivo="tamanho errado",
        )
        linhas = ServicoDevolucao(cenario.ctx).itens(devolucao.devolucao_id)
        assert len(linhas) == 1
        assert linhas[0]["quantidade_milesimos"] == 1000
        assert linhas[0]["valor_unitario_centavos"] == (
            liquido["preco_unitario_centavos"] - liquido["desconto_centavos"]
        )
        assert linhas[0]["total_centavos"] == linhas[0]["valor_unitario_centavos"]


# ------------------------------------------------------------------ caminho UI
pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError, reason="PySide6 ausente")


@pytest.fixture
def app():
    from PySide6.QtWidgets import QApplication

    from bussola_pdv.ui.tema import FOLHA_ESTILO

    aplicacao = QApplication.instance() or QApplication(["teste"])
    aplicacao.setStyleSheet(FOLHA_ESTILO)
    return aplicacao


class TestDialogoDevolucao:
    @pytest.mark.ui
    def test_devolve_pela_tela_e_resume_o_resultado(self, app, cenario):
        from bussola_pdv.ui.devolucoes import COLUNA_DEVOLVER, DialogoDevolucao

        venda_id = _venda(cenario, "3")
        venda = cenario.ctx.vendas.por_id(venda_id)
        dialogo = DialogoDevolucao(cenario.ctx, cenario.gerente, venda)
        assert dialogo.tabela.rowCount() == 1
        dialogo.tabela.item(0, COLUNA_DEVOLVER).setText("1")
        dialogo.combo_destino.setCurrentIndex(dialogo.combo_destino.findData("TROCA"))
        dialogo.campo_motivo.setText("Cliente trouxe de volta")
        dialogo._salvar()
        assert dialogo.resultado is not None
        assert "Devolução" in dialogo.resumo()
        dialogo.deleteLater()

    @pytest.mark.ui
    def test_prazo_aparece_na_tela(self, app, cenario):
        from bussola_pdv.ui.devolucoes import DialogoDevolucao

        venda_id = _venda(cenario, "1")
        venda = cenario.ctx.vendas.por_id(venda_id)
        dialogo = DialogoDevolucao(cenario.ctx, cenario.gerente, venda)
        assert "Dentro do prazo" in dialogo.rotulo_prazo.text()
        dialogo.deleteLater()

    @pytest.mark.ui
    def test_sem_itens_marcados_mostra_erro(self, app, cenario):
        from bussola_pdv.ui.devolucoes import DialogoDevolucao

        venda_id = _venda(cenario, "1")
        venda = cenario.ctx.vendas.por_id(venda_id)
        dialogo = DialogoDevolucao(cenario.ctx, cenario.gerente, venda)
        dialogo.campo_motivo.setText("Sem item")
        dialogo._confirmar()
        assert dialogo.resultado is None
        assert dialogo.mensagem.text()
        dialogo.deleteLater()

    @pytest.mark.ui
    def test_botao_aparece_na_tela_de_vendas(self, app, cenario):
        from bussola_pdv.ui.telas_consulta import TelaVendas

        tela = TelaVendas(cenario.ctx, cenario.gerente)
        assert tela.botao_devolver is not None
        assert tela.botao_devolver.text() == "Devolver / estornar itens"
        tela.deleteLater()

    @pytest.mark.ui
    def test_atendente_nao_ve_botao_de_devolucao(self, app, cenario):
        from bussola_pdv.ui.telas_consulta import TelaVendas

        tela = TelaVendas(cenario.ctx, cenario.operador)
        assert tela.botao_devolver is None
        tela.deleteLater()

