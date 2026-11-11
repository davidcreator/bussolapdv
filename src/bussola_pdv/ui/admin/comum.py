"""Peças reutilizadas pelas seções da área administrativa."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QWidget

from ...dominio.erros import ErroBussola


class Mensagem(QLabel):
    """Faixa de retorno padronizada (ok / alerta / erro), sem diálogo modal."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("", parent)
        self.setWordWrap(True)
        self.setObjectName("textoAjuda")

    def ok(self, texto: str) -> None:
        self._mostrar(texto, "mensagemOk")

    def alerta(self, texto: str) -> None:
        self._mostrar(texto, "mensagemAlerta")

    def erro(self, texto: str) -> None:
        self._mostrar(texto, "mensagemErro")

    def limpar(self) -> None:
        self.setText("")
        self.setObjectName("textoAjuda")

    def _mostrar(self, texto: str, estilo: str) -> None:
        self.setText(texto)
        self.setObjectName(estilo)
        self.style().unpolish(self)
        self.style().polish(self)


def descrever_erro(exc: Exception) -> str:
    """Mensagem curta para a tela; detalhes técnicos só quando não há texto de domínio."""
    if isinstance(exc, ErroBussola):
        return str(exc)
    return f"{type(exc).__name__}: {exc}"
