"""Botão "Exportar" reutilizável: um menu com Excel e PDF, em qualquer tela.

Regras que este widget garante para toda tela que o usa:

* **o dado é montado na hora do clique** (`construir()`), refletindo os filtros
  que estão na tela naquele instante — não um retrato velho da abertura;
* **a permissão é conferida no serviço**, não na tela: se o perfil não tem
  `EXPORTAR_DADOS`, o botão nem aparece e o serviço recusaria de todo jeito;
* **o nome sugerido** já vem pronto (`fechamento-do-caixa-2026-11-11.xlsx`) na
  pasta de relatórios do usuário, então quem só quer salvar dá um Enter;
* **depois de salvar**, oferece abrir a pasta — sem isso, em Windows, o arquivo
  "some" em `%LOCALAPPDATA%`.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog, QMenu, QMessageBox, QPushButton, QWidget

from ..aplicacao.exportacao import ServicoExportacao
from ..caminhos import pasta_de_relatorios
from ..dominio.erros import ErroBussola
from ..dominio.relatorio import Relatorio
from ..dominio.usuario import Acao, Usuario
from ..infra.exportacao import FORMATOS
from .icones import icone

FILTROS_DE_ARQUIVO = {
    ".xlsx": "Planilha do Excel (*.xlsx)",
    ".pdf": "Documento PDF (*.pdf)",
}


def pasta_sugerida() -> Path:
    """Pasta de relatórios do usuário; se não der para criar, usa a pasta atual."""
    try:
        return pasta_de_relatorios()
    except OSError:  # pragma: no cover - disco somente leitura
        return Path.cwd()


class BotaoExportar(QPushButton):
    """Botão com menu de formatos. Emite `exportado` com o caminho gravado."""

    exportado = Signal(str)

    def __init__(
        self,
        *,
        usuario: Usuario,
        servico: ServicoExportacao,
        construir: Callable[[], Relatorio],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("Exportar", parent)
        self.usuario = usuario
        self.servico = servico
        self.construir = construir
        self.setObjectName("secundario")
        self.setIcon(icone("saida", "#212529", 16))
        self.setToolTip("Exportar este relatório em Excel (.xlsx) ou PDF")
        menu = self.menu() or self._criar_menu()
        self.setMenu(menu)
        self.setVisible(usuario.pode(Acao.EXPORTAR_DADOS))

    # -- menu ----------------------------------------------------------------
    def _criar_menu(self) -> QMenu:
        menu = QMenu(self)
        for extensao, rotulo in FORMATOS.items():
            acao = menu.addAction(icone(extensao_para_icone(extensao), "#212529", 16), rotulo)
            acao.setData(extensao)
            acao.triggered.connect(
                lambda _marcado=False, ext=extensao: self.exportar_como(ext)
            )
        return menu

    def acoes(self) -> list[str]:
        """Extensões disponíveis no menu (usado nos testes e na documentação)."""
        return [acao.data() for acao in self.menu().actions()]

    # -- exportação ----------------------------------------------------------
    def exportar_como(self, extensao: str) -> Path | None:
        extensao = extensao if extensao.startswith(".") else f".{extensao}"
        try:
            relatorio = self.construir()
        except ErroBussola as exc:
            QMessageBox.warning(self, "Exportar", str(exc))
            return None

        nome = relatorio.nome_de_arquivo(extensao)
        inicial = pasta_sugerida() / nome
        escolhido, _filtro = QFileDialog.getSaveFileName(
            self,
            "Exportar relatório",
            str(inicial),
            FILTROS_DE_ARQUIVO.get(extensao, "Todos os arquivos (*)"),
        )
        if not escolhido:
            return None
        destino = Path(escolhido)
        if destino.suffix.lower() != extensao:
            destino = destino.with_suffix(extensao)
        try:
            caminho = self.servico.exportar(self.usuario, relatorio, destino)
        except ErroBussola as exc:
            QMessageBox.warning(self, "Exportar", str(exc))
            return None
        except OSError as exc:
            QMessageBox.warning(
                self,
                "Exportar",
                f"Não foi possível gravar em {destino}:\n{exc}\n\n"
                "Feche o arquivo se ele estiver aberto no Excel e tente de novo.",
            )
            return None
        self.exportado.emit(str(caminho))
        self._confirmar(caminho)
        return caminho

    def _confirmar(self, caminho: Path) -> None:
        caixa = QMessageBox(self)
        caixa.setWindowTitle("Relatório exportado")
        caixa.setIcon(QMessageBox.Icon.Information)
        caixa.setText(f"Arquivo salvo em:<br><b>{caminho}</b>")
        caixa.setInformativeText(
            "Documento interno de conferência — não é documento fiscal.\n"
            "A exportação ficou registrada na trilha de auditoria."
        )
        abrir = caixa.addButton("Abrir pasta", QMessageBox.ButtonRole.ActionRole)
        caixa.addButton(QMessageBox.StandardButton.Ok)
        caixa.exec()
        if caixa.clickedButton() is abrir:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(caminho.parent)))


def extensao_para_icone(extensao: str) -> str:
    """Ícone do formato: grade para `.xlsx`, documento para `.pdf`."""
    return "documento" if extensao == ".pdf" else "planilha"


__all__ = ["BotaoExportar", "pasta_sugerida"]
