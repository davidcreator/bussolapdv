"""Ponto de entrada da interface desktop."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication

from ..aplicacao.contexto import Contexto
from ..diagnostico import registrar_aviso, resumo_do_erro
from ..dominio.relogio import avisos_de_fuso
from .admin.janela import contexto_marca
from .janela import JanelaPrincipal
from .login import DialogoLogin
from .tema import FOLHA_ESTILO, folha_estilo_da_marca, paleta_do_tema

logger = logging.getLogger(__name__)


def criar_aplicacao(argv: list[str] | None = None) -> QApplication:
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    existente = QApplication.instance()
    app = existente if isinstance(existente, QApplication) else QApplication(argv or sys.argv)
    app.setApplicationName("Bússola Sistema PDV Open Source")
    app.setOrganizationName("Bússola Sistema PDV Open Source")
    # Ícone oficial em todas as janelas (barra de tarefas, Alt+Tab e diálogos).
    # O `.exe` já carrega o ícone do recurso Windows; isto cobre quem roda do código.
    # Ícone ausente **não** impede o login: vira aviso no log e a interface segue.
    from .identidade import LOGO_MINI, caminho_do_logo

    try:
        caminho_icone = caminho_do_logo(LOGO_MINI)
    except OSError as exc:
        logger.warning("Ícone do programa indisponível (%s); seguindo sem ele.", exc)
    else:
        app.setWindowIcon(QIcon(str(caminho_icone)))
    fixar_aparencia_clara(app)
    app.setStyleSheet(FOLHA_ESTILO)
    return app


def fixar_aparencia_clara(app: QApplication, paleta: object | None = None) -> None:
    """Neutraliza o tema do sistema: a cor da interface é a da loja.

    Windows 11 em modo escuro entrega ao Qt 6.5+ uma paleta escura. Sem fixar
    estilo e paleta, o `QScrollArea` transparente mostrava o preto do sistema
    atrás dos cartões e textos de seção ficavam ilegíveis — foi o relato do
    contraste. `Fusion` desenha a partir da paleta (e não do tema nativo), então
    o resultado é o mesmo em qualquer máquina.
    """
    from PySide6.QtWidgets import QStyleFactory

    disponivel = {str(nome).lower() for nome in QStyleFactory.keys()}  # noqa: SIM118 - QStyleFactory é API Qt
    if "fusion" in disponivel and app.style().objectName().lower() != "fusion":
        app.setStyle(QStyleFactory.create("Fusion"))
    app.setPalette(paleta_do_tema(paleta))  # type: ignore[arg-type]


def aplicar_tema_da_loja(app: QApplication, contexto: Contexto) -> None:
    """Aplica a marca gravada no banco depois que a base foi aberta."""
    try:
        marca = contexto_marca(contexto)
        fixar_aparencia_clara(app, marca.paleta)
        app.setStyleSheet(folha_estilo_da_marca(marca))
    except Exception:  # pragma: no cover - tema corrompido não impede operar
        fixar_aparencia_clara(app)
        app.setStyleSheet(FOLHA_ESTILO)


def _backup_do_dia(contexto: Contexto) -> None:
    """Cópia automática ao abrir: uma por dia, sem clique e sem travar a abertura.

    Falha de backup nunca impede a loja de abrir — vira aviso no log. O que não se
    aceita é o silêncio: quem não tem cópia não tem volta.
    """
    from ..aplicacao.backup import ServicoBackup

    try:
        copia = ServicoBackup(contexto).automatico()
    except Exception as exc:  # disco cheio, pasta sem permissão, base em memória
        registrar_aviso(
            f"cópia automática não foi criada: {resumo_do_erro(exc)}",
            contexto="inicialização: backup automático",
        )
        return
    if copia is not None:
        registrar_aviso(
            f"cópia automática criada em {copia.arquivo} ({copia.bytes} bytes)",
            contexto="inicialização: backup automático",
        )


def executar(
    banco: Path, *, login_automatico: str | None = None, modo_admin: bool = False
) -> int:
    """Abre a interface. `login_automatico` existe apenas para demonstração/captura."""
    app = criar_aplicacao()
    contexto = Contexto.abrir(banco)
    # Se o fuso caiu para deslocamento fixo (Windows sem `tzdata`), isso precisa
    # chegar ao log: a loja continua abrindo, mas a data comercial usa UTC-3 fixo.
    for aviso in avisos_de_fuso():
        registrar_aviso(aviso, contexto="inicialização: fuso horário")
    _backup_do_dia(contexto)
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
