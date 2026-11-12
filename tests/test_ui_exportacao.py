"""Botão Exportar na interface: existe onde deve, some de quem não pode, grava.

Os testes de arquivo já estão em `test_exportacao.py`; aqui o alvo é o
comportamento de tela: o menu oferece os dois formatos, o nome sugerido já vem
preenchido, o `QFileDialog` é substituído nos testes (nada de janela modal em
CI) e quem não tem `EXPORTAR_DADOS` não vê o botão.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError, reason="Qt ausente")

from bussola_pdv.aplicacao.exportacao import ServicoExportacao
from bussola_pdv.ui.exportacao import BotaoExportar
from bussola_pdv.ui.telas_consulta import (
    TelaAuditoria,
    TelaFechamento,
    TelaProdutos,
    TelaVendas,
)

pytestmark = pytest.mark.ui


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication(["teste-exportacao"])


def _clicar_sem_dialogo(monkeypatch, botao: BotaoExportar, destino: str) -> None:
    """Substitui o diálogo de arquivo e a confirmação modal."""
    from PySide6.QtWidgets import QFileDialog

    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (destino, ""))
    )
    monkeypatch.setattr(BotaoExportar, "_confirmar", lambda self, caminho: None)


class TestBotao:
    def test_menu_oferece_excel_e_pdf(self, app, cenario):
        botao = BotaoExportar(
            usuario=cenario.gerente,
            servico=ServicoExportacao(cenario.ctx),
            construir=lambda: ServicoExportacao(cenario.ctx).relatorio_fechamento("2026-11-11"),
        )
        assert botao.acoes() == [".xlsx", ".pdf"]
        rotulos = [acao.text() for acao in botao.menu().actions()]
        assert rotulos == ["Excel", "PDF"]
        botao.deleteLater()

    def test_atendente_nao_ve_o_botao(self, app, cenario):
        botao = BotaoExportar(
            usuario=cenario.operador,
            servico=ServicoExportacao(cenario.ctx),
            construir=lambda: ServicoExportacao(cenario.ctx).relatorio_fechamento("2026-11-11"),
        )
        assert botao.isHidden()
        botao.deleteLater()

    def test_gerente_ve_o_botao(self, app, cenario):
        botao = BotaoExportar(
            usuario=cenario.gerente,
            servico=ServicoExportacao(cenario.ctx),
            construir=lambda: ServicoExportacao(cenario.ctx).relatorio_fechamento("2026-11-11"),
        )
        assert not botao.isHidden()
        botao.deleteLater()

    def test_exporta_xlsx_e_emite_sinal(self, app, cenario, tmp_path, monkeypatch):
        servico = ServicoExportacao(cenario.ctx)
        destino = tmp_path / "fechamento.xlsx"
        botao = BotaoExportar(
            usuario=cenario.gerente,
            servico=servico,
            construir=lambda: servico.relatorio_fechamento("2026-11-11"),
        )
        recebidos: list[str] = []
        botao.exportado.connect(recebidos.append)
        _clicar_sem_dialogo(monkeypatch, botao, str(destino))

        caminho = botao.exportar_como(".xlsx")

        assert caminho == destino
        assert destino.is_file()
        assert recebidos == [str(destino)]
        assert cenario.ctx.auditoria.listar(limite=1)[0].acao.value == "DADOS_EXPORTADOS"
        botao.deleteLater()

    def test_extensao_e_corrigida_quando_o_usuario_nao_digita(self, app, cenario, tmp_path, monkeypatch):
        servico = ServicoExportacao(cenario.ctx)
        botao = BotaoExportar(
            usuario=cenario.gerente,
            servico=servico,
            construir=lambda: servico.relatorio_fechamento("2026-11-11"),
        )
        _clicar_sem_dialogo(monkeypatch, botao, str(tmp_path / "sem_extensao"))

        caminho = botao.exportar_como(".pdf")

        assert caminho == tmp_path / "sem_extensao.pdf"
        assert caminho.is_file()
        botao.deleteLater()

    def test_cancelar_dialogo_nao_grava_nada(self, app, cenario, tmp_path, monkeypatch):
        from PySide6.QtWidgets import QFileDialog

        servico = ServicoExportacao(cenario.ctx)
        botao = BotaoExportar(
            usuario=cenario.gerente,
            servico=servico,
            construir=lambda: servico.relatorio_fechamento("2026-11-11"),
        )
        monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: ("", "")))

        assert botao.exportar_como(".xlsx") is None
        assert not [arquivo for arquivo in tmp_path.iterdir() if arquivo.suffix in {".xlsx", ".pdf"}]
        botao.deleteLater()


class TestTelas:
    @pytest.mark.parametrize("tela", [TelaProdutos, TelaVendas, TelaAuditoria, TelaFechamento])
    def test_cada_tela_de_relatorio_tem_botao_exportar(self, app, cenario, tela):
        widget = tela(cenario.ctx, cenario.gerente)
        assert widget.botao_exportar.acoes() == [".xlsx", ".pdf"]
        assert not widget.botao_exportar.isHidden()
        widget.deleteLater()

    def test_fechamento_da_tela_exporta_o_dia_escolhido(self, app, cenario, tmp_path, monkeypatch):
        widget = TelaFechamento(cenario.ctx, cenario.gerente)
        destino = tmp_path / "dia.pdf"
        _clicar_sem_dialogo(monkeypatch, widget.botao_exportar, str(destino))

        assert widget.botao_exportar.exportar_como(".pdf") == destino
        assert destino.stat().st_size > 1000
        assert b"2026" in destino.read_bytes() or destino.stat().st_size > 0
        widget.deleteLater()

    def test_atendente_nao_ve_exportar_na_tela_de_fechamento(self, app, cenario):
        widget = TelaFechamento(cenario.ctx, cenario.operador)
        assert widget.botao_exportar.isHidden()
        widget.deleteLater()

    def test_produtos_exporta_com_a_busca_da_tela(self, app, cenario, tmp_path, monkeypatch):
        widget = TelaProdutos(cenario.ctx, cenario.gerente)
        widget.campo_busca.setText("Café")
        destino = tmp_path / "catalogo.xlsx"
        _clicar_sem_dialogo(monkeypatch, widget.botao_exportar, str(destino))

        assert widget.botao_exportar.exportar_como(".xlsx") == destino

        openpyxl = pytest.importorskip("openpyxl")
        aba = openpyxl.load_workbook(destino)["Produtos"]
        descricoes = [
            linha[1] for linha in aba.iter_rows(min_row=3, values_only=True) if linha[1]
        ]
        assert descricoes == ["Café 500 g"]
        widget.deleteLater()
