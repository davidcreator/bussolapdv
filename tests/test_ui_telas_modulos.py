"""Telas de Clientes, Crediário e Estoque + botão Exportar do Caixa.

O ponto central: a tela **desenha o mesmo `Relatorio` que a exportação usa**. Se
alguém mexer no cálculo de um lado, o outro acompanha — e é isso que estes testes
verificam, comparando as células da tabela com as linhas do relatório.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError, reason="Qt ausente")

from bussola_pdv.aplicacao.exportacao import ServicoExportacao
from bussola_pdv.aplicacao.pdv import ServicoPDV, SolicitacaoVenda
from bussola_pdv.dominio.pagamentos import PlanoPagamento, pagamento_a_prazo
from bussola_pdv.dominio.venda import Carrinho
from bussola_pdv.ui.janela import JanelaPrincipal
from bussola_pdv.ui.tela_caixa import TelaCaixa
from bussola_pdv.ui.telas_clientes import TelaClientes
from bussola_pdv.ui.telas_crediario import TelaCrediario
from bussola_pdv.ui.telas_estoque import TelaEstoque

pytestmark = pytest.mark.ui


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication(["teste-modulos"])


def _venda_a_prazo(cenario):
    carrinho = Carrinho()
    carrinho.adicionar(cenario.produto_a, "2")
    total = carrinho.totais().total
    return ServicoPDV(cenario.ctx).finalizar_venda(
        SolicitacaoVenda(
            operador=cenario.operador,
            caixa_id=cenario.caixa_id,
            carrinho=carrinho,
            plano=PlanoPagamento.de_pagamentos(pagamento_a_prazo(total)),
            cliente_id=cenario.cliente.id,
            parcelas_crediario=2,
        )
    )


class TestTelaClientes:
    def test_tabela_espelha_o_relatorio(self, app, cenario):
        tela = TelaClientes(cenario.ctx, cenario.gerente)
        relatorio = ServicoExportacao(cenario.ctx).relatorio_clientes()
        assert tela.tabela.rowCount() == len(relatorio.tabelas[0].linhas)
        assert tela.tabela.columnCount() == 7
        assert tela.tabela.item(0, 0).text() == relatorio.tabelas[0].linhas[0][0]
        tela.deleteLater()

    def test_busca_reduz_linhas(self, app, cenario):
        tela = TelaClientes(cenario.ctx, cenario.gerente)
        tela.campo_busca.setText("zzz-nao-existe")
        assert tela.tabela.rowCount() == 0
        tela.deleteLater()

    def test_kpis_e_botao(self, app, cenario, tmp_path, monkeypatch):
        _venda_a_prazo(cenario)
        tela = TelaClientes(cenario.ctx, cenario.gerente)
        assert tela.kpi_aberto.valor.text() != "R$ 0,00"
        assert tela.botao_exportar.acoes() == [".xlsx", ".pdf"]
        assert not tela.botao_exportar.isHidden()
        destino = str(tmp_path / "clientes.xlsx")
        from PySide6.QtWidgets import QFileDialog

        from bussola_pdv.ui.exportacao import BotaoExportar

        monkeypatch.setattr(
            QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (destino, ""))
        )
        monkeypatch.setattr(BotaoExportar, "_confirmar", lambda self, caminho: None)
        assert tela.botao_exportar.exportar_como(".xlsx") is not None
        tela.deleteLater()

    def test_atendente_nao_ve_exportar(self, app, cenario):
        tela = TelaClientes(cenario.ctx, cenario.operador)
        assert tela.botao_exportar.isHidden()
        assert tela.tabela.rowCount() >= 1  # consulta continua liberada
        tela.deleteLater()


class TestTelaCrediario:
    def test_titulos_aparecem(self, app, cenario):
        _venda_a_prazo(cenario)
        tela = TelaCrediario(cenario.ctx, cenario.gerente)
        relatorio = ServicoExportacao(cenario.ctx).relatorio_crediario()
        assert tela.tabela.rowCount() == len(relatorio.tabelas[0].linhas)
        assert tela.kpi_abertos.valor.text() == dict(relatorio.indicadores)["Em aberto"]
        tela.deleteLater()

    def test_checkbox_inclui_recebidos(self, app, cenario):
        from bussola_pdv.aplicacao.crediario import ServicoCrediario
        from bussola_pdv.dominio.dinheiro import Dinheiro
        from bussola_pdv.dominio.pagamentos import FormaPagamento

        _venda_a_prazo(cenario)
        titulo = cenario.ctx.crediario.listar(cliente_id=cenario.cliente.id)[0]
        ServicoCrediario(cenario.ctx).receber(
            titulo_id=titulo["id"],
            valor=Dinheiro(titulo["saldo_centavos"]),
            forma=FormaPagamento.DINHEIRO,
            operador=cenario.operador,
            caixa_id=cenario.caixa_id,
        )
        tela = TelaCrediario(cenario.ctx, cenario.gerente)
        sem_pagos = tela.tabela.rowCount()
        tela.incluir_pagos.setChecked(True)
        assert tela.tabela.rowCount() > sem_pagos
        tela.deleteLater()


class TestTelaEstoque:
    def test_produtos_e_resumo(self, app, cenario):
        tela = TelaEstoque(cenario.ctx, cenario.gerente)
        assert tela.tabela.rowCount() == 2
        assert tela.tabela.item(0, 0).text() in {"A001", "B002"}
        assert tela.kpi_custo.valor.text() != "R$ 0,00"
        tela.deleteLater()

    def test_busca_por_codigo(self, app, cenario):
        tela = TelaEstoque(cenario.ctx, cenario.gerente)
        tela.campo_busca.setText("B002")
        assert tela.tabela.rowCount() == 1
        assert tela.tabela.item(0, 0).text() == "B002"
        tela.deleteLater()


class TestExportarNoCaixa:
    def test_botao_habilitado_com_turno_aberto(self, app, cenario):
        tela = TelaCaixa(cenario.ctx, cenario.gerente)
        assert tela.botao_exportar.acoes() == [".xlsx", ".pdf"]
        assert tela.botao_exportar.isEnabled()
        assert not tela.botao_exportar.isHidden()
        tela.deleteLater()

    def test_botao_desabilitado_sem_turno(self, app, cenario):
        from bussola_pdv.aplicacao.caixa import ServicoCaixa
        from bussola_pdv.dominio.caixa import ContagemDenominacao

        ServicoCaixa(cenario.ctx).fechar_turno(
            turno_id=cenario.turno_id,
            conferente=cenario.gerente,
            contagens=[ContagemDenominacao(10000, 1)],
        )
        tela = TelaCaixa(cenario.ctx, cenario.gerente)
        assert not tela.botao_exportar.isEnabled()
        tela.deleteLater()

    def test_exporta_o_turno_em_pdf(self, app, cenario, tmp_path, monkeypatch):
        from PySide6.QtWidgets import QFileDialog

        from bussola_pdv.ui.exportacao import BotaoExportar

        destino = str(tmp_path / "turno.pdf")
        monkeypatch.setattr(
            QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (destino, ""))
        )
        monkeypatch.setattr(BotaoExportar, "_confirmar", lambda self, caminho: None)
        tela = TelaCaixa(cenario.ctx, cenario.gerente)
        assert tela.botao_exportar.exportar_como(".pdf") is not None
        tela.deleteLater()


class TestJanela:
    def test_modulos_novos_saem_do_placeholder(self, app, cenario):
        from PySide6.QtWidgets import QLabel

        janela = JanelaPrincipal(cenario.ctx, cenario.gerente)
        for modulo, classe in (
            ("Clientes", TelaClientes),
            ("Crediário", TelaCrediario),
            ("Estoque", TelaEstoque),
        ):
            janela._selecionar(modulo)
            atual = janela.pilha.currentWidget()
            assert isinstance(atual, classe), f"{modulo} ainda é placeholder"
        # Entradas e Parâmetros continuam honestamente marcados como não implementados
        janela._selecionar("Parâmetros")
        avisos = [w.text() for w in janela.pilha.currentWidget().findChildren(QLabel)]
        assert any("não foi" in texto for texto in avisos)
        janela.close()
        janela.deleteLater()
