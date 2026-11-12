"""Teste de fumaça da interface (Qt offscreen).

Não substitui teste de usabilidade em estação real: verifica que as telas montam,
que o carrinho calcula e que a venda saiu pela camada de aplicação.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError, reason="PySide6 ou libs do Qt ausentes")

pytestmark = pytest.mark.ui


@pytest.fixture
def app():
    from PySide6.QtWidgets import QApplication

    from bussola_pdv.ui.tema import FOLHA_ESTILO

    aplicacao = QApplication.instance() or QApplication(["teste"])
    aplicacao.setStyleSheet(FOLHA_ESTILO)
    return aplicacao


@pytest.fixture
def janela(app, cenario, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from bussola_pdv.ui.janela import JanelaPrincipal

    mensagens = []
    monkeypatch.setattr(
        QMessageBox, "information", lambda *args, **kwargs: mensagens.append(args[2] if len(args) > 2 else "")
    )
    # O comprovante é uma caixa com botão "Imprimir cupom", aberta sem bloquear.
    monkeypatch.setattr(QMessageBox, "open", lambda self: mensagens.append(self.text()))
    janela = JanelaPrincipal(cenario.ctx, cenario.operador)
    janela.tela_pdv.atualizar()
    janela._mensagens = mensagens
    yield janela
    janela.close()
    janela.deleteLater()


def test_janela_monta_com_todos_os_modulos(janela):
    from bussola_pdv.ui.janela import MODULO_AJUDA, MODULOS

    # O menu mostra os módulos do usuário + Ajuda, que não é página (abre o guia).
    assert MODULO_AJUDA in janela.modulos
    assert janela.navegacao.count() == len(MODULOS) + 1
    assert janela.pilha.count() == len(janela.modulos) - 1
    assert janela.tela_pdv.botao_finalizar.isEnabled()  # turno aberto no cenário


def test_adicionar_item_atualiza_total(janela, cenario):
    tela = janela.tela_pdv
    tela.campo_codigo.setText("A001")
    tela.campo_quantidade.setText("2")
    tela._adicionar_item()
    assert len(tela.carrinho) == 1
    assert tela.rotulo_total.text() == "R$ 31,80"
    assert tela.linhas_pagamento[0][1].text() == "R$ 31,80"


def test_busca_por_codigo_de_barras(janela):
    tela = janela.tela_pdv
    tela.campo_codigo.setText("7891234567895")
    tela._adicionar_item()
    assert tela.carrinho.itens[0].codigo == "A001"


def test_codigo_inexistente_mostra_erro(janela):
    tela = janela.tela_pdv
    tela.campo_codigo.setText("INEXISTENTE")
    tela._adicionar_item()
    assert tela.carrinho.vazio
    assert tela.mensagem.objectName() == "mensagemErro"


def test_finalizar_pela_interface(janela, cenario):
    tela = janela.tela_pdv
    tela.campo_codigo.setText("A001")
    tela.campo_quantidade.setText("1")
    tela._adicionar_item()
    tela._finalizar()

    vendas = cenario.ctx.vendas.listar(limite=10)
    assert len(vendas) == 1
    assert vendas[0]["total_centavos"] == 1590
    assert tela.carrinho.vazio  # cupom limpo após sucesso
    assert janela._mensagens  # comprovante exibido
    assert tela.ultima_venda is not None  # F8 reimprime sem procurar a venda


def test_cancelar_cupom_nao_grava(janela, cenario):
    tela = janela.tela_pdv
    tela.campo_codigo.setText("A001")
    tela._adicionar_item()
    tela._limpar()
    assert tela.carrinho.vazio
    assert cenario.ctx.vendas.listar(limite=10) == []


def test_tela_caixa_mostra_esperado(janela):
    janela.navegacao.setCurrentRow(1)
    janela.tela_caixa.atualizar()
    assert "100,00" in janela.tela_caixa.rotulo_resumo.text()


def test_tela_produtos_lista_cadastro(janela):
    janela.navegacao.setCurrentRow(2)
    tela = janela.pilha.currentWidget()
    assert tela.tabela.rowCount() == 2
    assert "Ruptura" in tela.rotulo_resumo.text()


def test_tela_fechamento_gera_relatorio(janela):
    janela.navegacao.setCurrentRow(4)
    tela = janela.pilha.currentWidget()
    assert "FECHAMENTO" in tela.texto.toPlainText()
    assert "CONCILIAÇÃO" in tela.texto.toPlainText()


def test_modulo_nao_implementado_avisa(janela):
    janela.navegacao.setCurrentRow(9)  # Entradas (Clientes/Crediário/Estoque já são telas)
    rotulos = [w.text() for w in janela.pilha.currentWidget().findChildren(type(janela.rotulo_modulo))]
    assert any("não foi implementado" in texto for texto in rotulos)
    assert janela.cabecalho.titulo.text() == "Entradas"
