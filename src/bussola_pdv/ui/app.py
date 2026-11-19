"""Ponto de entrada da interface desktop."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication

from ..aplicacao.contexto import Contexto
from ..aplicacao.remoto import ContextoRemoto, servicos_de
from ..diagnostico import registrar_aviso, resumo_do_erro
from ..dominio.relogio import avisos_de_fuso
from ..infra.api.cliente import ClienteAPI
from ..infra.rede.configuracao_terminal import ErroDeConfiguracao, carregar
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

    try:
        copia = servicos_de(contexto).backup.automatico()
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
    banco: Path,
    *,
    login_automatico: str | None = None,
    modo_admin: bool = False,
    pasta_do_caixa: Path | None = None,
    forcar_local: bool = False,
) -> int:
    """Abre a interface — em modo local ou em modo terminal, conforme a máquina.

    A decisão é **do computador**, não da tela: se existe `terminal.json` na pasta
    de dados, este caixa trabalha contra o servidor da loja e a base local não é
    aberta. Sem o arquivo, tudo funciona como sempre (base na própria máquina).
    """
    app = criar_aplicacao()
    pasta = Path(pasta_do_caixa) if pasta_do_caixa is not None else Path(banco).parent
    try:
        configuracao = None if forcar_local else carregar(pasta)
    except ErroDeConfiguracao as exc:
        print(f"Configuração do caixa inválida: {exc}")
        return 2
    if configuracao is not None:
        return _executar_como_terminal(
            app, pasta, configuracao, login_automatico=login_automatico, modo_admin=modo_admin
        )

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


def _executar_como_terminal(
    app: QApplication,
    pasta: Path,
    configuracao: object,
    *,
    login_automatico: str | None = None,
    modo_admin: bool = False,
) -> int:
    """Abertura do caixa remoto: sem base local, sem backup local, com sessão.

    O que muda em relação ao modo local, e por quê:

    * **não abre banco** — a base é a do servidor; abrir uma local criaria uma
      segunda loja sem ninguém perceber;
    * **não faz backup automático** — quem faz é o servidor, que tem a base
      (no caixa não há o que copiar além da fila de vendas);
    * **login é sessão** — e a marca da loja vem do servidor, para que a tela do
      balcão fique igual à do escritório.
    """
    cliente = ClienteAPI(pasta=pasta, configuracao=configuracao)  # type: ignore[arg-type]
    contexto = ContextoRemoto(cliente, caminho=pasta)
    for aviso in avisos_de_fuso():
        registrar_aviso(aviso, contexto="inicialização: fuso horário")
    aplicar_tema_da_loja(app, contexto)  # type: ignore[arg-type]

    if login_automatico:
        from ..infra.api.cliente import ErroDeComunicacao

        try:
            cliente.abrir_sessao(login_automatico, "")
        except (ErroDeComunicacao, Exception) as exc:  # pragma: no cover - só demonstração
            print(f"Login automático indisponível no modo terminal: {exc}")
    usuario: object | None = None
    if cliente.operador is not None:
        usuario = cliente.operador
    else:
        dialogo = DialogoLogin(contexto)  # type: ignore[arg-type]
        if dialogo.exec() != dialogo.DialogCode.Accepted or dialogo.usuario is None:
            return 0
        usuario = dialogo.usuario

    if modo_admin:
        from .admin.janela import JanelaAdmin

        try:
            JanelaAdmin(contexto, usuario).exec()  # type: ignore[arg-type]
        except Exception as exc:
            print(f"Área administrativa indisponível: {exc}")
        return 0

    _avisar_pendencias(contexto, cliente)
    janela = JanelaPrincipal(contexto, usuario)  # type: ignore[arg-type]
    janela.show()
    return app.exec()


def _avisar_pendencias(contexto: ContextoRemoto, cliente: ClienteAPI) -> None:
    """Se há venda esperando envio, o operador precisa saber antes de vender de novo."""
    from ..aplicacao.fila_offline import NOME_DO_ARQUIVO, FilaDeVendas

    caminho = Path(cliente.pasta) / NOME_DO_ARQUIVO
    if not caminho.is_file():
        return
    fila = FilaDeVendas(caminho)
    total = fila.quantidade()
    fila.fechar()
    if not total:
        return
    from PySide6.QtWidgets import QMessageBox

    QMessageBox.information(
        None,
        "Vendas pendentes",
        f"Há {total} venda(s) guardada(s) neste caixa esperando o servidor. "
        "Use o menu Vendas pendentes para reenviar.",
    )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Bússola Sistema PDV Open Source — interface")
    parser.add_argument("--banco", default="dados/demo.db")
    parser.add_argument("--login", default=None, help="login automático (apenas demonstração)")
    parser.add_argument(
        "--admin", action="store_true", help="abre direto a área administrativa"
    )
    parser.add_argument(
        "--pasta", default=None, help="pasta de dados (onde fica terminal.json)"
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="ignora a configuração de caixa remoto e abre a base local",
    )
    argumentos = parser.parse_args()
    return executar(
        Path(argumentos.banco),
        login_automatico=argumentos.login,
        modo_admin=argumentos.admin,
        pasta_do_caixa=Path(argumentos.pasta) if argumentos.pasta else None,
        forcar_local=argumentos.local,
    )


if __name__ == "__main__":
    sys.exit(main())
