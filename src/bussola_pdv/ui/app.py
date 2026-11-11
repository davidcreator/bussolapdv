"""Ponto de entrada da interface desktop."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication

from ..aplicacao.contexto import Contexto
from .admin.janela import contexto_marca
from .janela import JanelaPrincipal
from .login import DialogoLogin
from .tema import FOLHA_ESTILO, folha_estilo_da_marca


def criar_aplicacao(argv: list[str] | None = None) -> QApplication:
    from PySide6.QtWidgets import QApplication

    existente = QApplication.instance()
    app = existente if isinstance(existente, QApplication) else QApplication(argv or sys.argv)
    app.setApplicationName("Bússola Sistema PDV Open Source")
    app.setOrganizationName("Bússola Sistema PDV Open Source")
    app.setStyleSheet(FOLHA_ESTILO)
    return app


def aplicar_tema_da_loja(app: QApplication, contexto: Contexto) -> None:
    """Aplica a marca gravada no banco depois que a base foi aberta."""
    try:
        app.setStyleSheet(folha_estilo_da_marca(contexto_marca(contexto)))
    except Exception:  # pragma: no cover - tema corrompido não impede operar
        app.setStyleSheet(FOLHA_ESTILO)


def executar(
    banco: Path, *, login_automatico: str | None = None, modo_admin: bool = False
) -> int:
    """Abre a interface. `login_automatico` existe apenas para demonstração/captura."""
    app = criar_aplicacao()
    contexto = Contexto.abrir(banco)
    aplicar_tema_da_loja(app, contexto)

    if login_automatico:
        usuario = contexto.usuarios.por_login(login_automatico)
    else:
        dialogo = DialogoLogin(contexto)
        if dialogo.exec() != dialogo.DialogCode.Accepted or dialogo.usuario is None:
            contexto.fechar()
            return 0
        usuario = dialogo.usuario

    if modo_admin:
        from .admin.janela import JanelaAdmin

        try:
            JanelaAdmin(contexto, usuario).exec()
        except Exception as exc:
            print(f"Área administrativa indisponível: {exc}")
        contexto.fechar()
        return 0

    janela = JanelaPrincipal(contexto, usuario)
    janela.show()
    codigo = app.exec()
    contexto.fechar()
    return codigo


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Bússola Sistema PDV Open Source — interface")
    parser.add_argument("--banco", default="dados/demo.db")
    parser.add_argument("--login", default=None, help="login automático (apenas demonstração)")
    parser.add_argument(
        "--admin", action="store_true", help="abre direto a área administrativa"
    )
    argumentos = parser.parse_args()
    return executar(
        Path(argumentos.banco), login_automatico=argumentos.login, modo_admin=argumentos.admin
    )


if __name__ == "__main__":
    sys.exit(main())
