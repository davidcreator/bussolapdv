"""Diagnóstico: o que fazer quando algo falha e não há terminal para ler.

O programa empacotado no Windows roda **sem console**: um `raise` que escape de um
slot do Qt desaparece — o PySide6 imprime o traceback em `stderr`, que ninguém vê.
O sintoma para o operador é o pior possível: "clico no botão e nada acontece".

Este módulo existe para que isso não aconteça:

* `registrar_erro()` grava o traceback completo em `logs/erros.log` na pasta de
  dados (com data, versão e o contexto da ação);
* `instalar_captura_de_erros()` troca o `sys.excepthook` — qualquer exceção não
  tratada passa a virar uma caixa de diálogo com mensagem curta, o caminho do log
  e um botão para copiar os detalhes;
* `mostrar_erro()` é o mesmo, para ser usado dentro de `try/except` local.

Nada aqui inventa causa: se o programa não sabe o que houve, ele mostra o erro
original e diz onde está o log.
"""

from __future__ import annotations

import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType

LIMITE_LOG_BYTES = 512 * 1024  # 512 kB: ao passar disso, o arquivo roda para .1


def _pasta_de_logs() -> Path:
    from .caminhos import pasta_de_logs

    try:
        return pasta_de_logs()
    except Exception:  # pasta indisponível: cai para o temporário do sistema
        import tempfile

        pasta = Path(tempfile.gettempdir()) / "BussolaPDV" / "logs"
        pasta.mkdir(parents=True, exist_ok=True)
        return pasta


def arquivo_de_log() -> Path:
    return _pasta_de_logs() / "erros.log"


def _rotacionar(arquivo: Path) -> None:
    try:
        if arquivo.exists() and arquivo.stat().st_size > LIMITE_LOG_BYTES:
            arquivo.replace(arquivo.with_suffix(".log.1"))
    except OSError:  # pragma: no cover - rotação é conveniência, não requisito
        pass


def registrar_erro(exc: BaseException, *, contexto: str = "") -> Path:
    """Grava `exc` com traceback no log e devolve o caminho do arquivo."""
    from . import __version__

    arquivo = arquivo_de_log()
    _rotacionar(arquivo)
    carimbo = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    try:
        with arquivo.open("a", encoding="utf-8") as manipulador:
            manipulador.write(f"\n=== {carimbo} · Bússola PDV {__version__} ===\n")
            if contexto:
                manipulador.write(f"ação: {contexto}\n")
            manipulador.write(
                "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            )
    except OSError:  # pragma: no cover - se nem o log abre, resta o stderr
        traceback.print_exception(type(exc), exc, exc.__traceback__)
    return arquivo


def registrar_aviso(mensagem: str, *, contexto: str = "") -> Path:
    """Grava um aviso (não é erro) no mesmo log: o suporte precisa do ambiente.

    Exemplo: fuso horário aproximado por falta do pacote `tzdata` no Windows.
    """
    from . import __version__

    arquivo = arquivo_de_log()
    _rotacionar(arquivo)
    carimbo = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    try:
        with arquivo.open("a", encoding="utf-8") as manipulador:
            manipulador.write(f"\n=== {carimbo} · Bússola PDV {__version__} ===\n")
            if contexto:
                manipulador.write(f"ação: {contexto}\n")
            manipulador.write(f"AVISO: {mensagem}\n")
    except OSError:  # pragma: no cover - sem log, resta o stderr
        print(f"AVISO: {mensagem}", file=sys.stderr)
    return arquivo


def resumo_do_erro(exc: BaseException) -> str:
    """Primeira linha útil: mensagem do erro ou o tipo, quando não houver texto."""
    mensagem = str(exc).strip().splitlines()[0] if str(exc).strip() else ""
    tipo = type(exc).__name__
    return f"{tipo}: {mensagem}" if mensagem else tipo


def mostrar_erro(exc: BaseException, *, contexto: str = "", titulo: str = "Erro") -> Path:
    """Registra `exc` e avisa o operador em caixa de diálogo (quando há Qt)."""
    arquivo = registrar_erro(exc, contexto=contexto)
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
    except ImportError:  # pragma: no cover - sem Qt, o log é a única saída
        print(resumo_do_erro(exc), file=sys.stderr)
        return arquivo
    if QApplication.instance() is None:  # pragma: no cover - antes da app existir
        print(resumo_do_erro(exc), file=sys.stderr)
        return arquivo
    caixa = QMessageBox()
    caixa.setIcon(QMessageBox.Icon.Critical)
    caixa.setWindowTitle(titulo)
    caixa.setText(f"Não foi possível concluir a operação.\n\n{resumo_do_erro(exc)}")
    caixa.setInformativeText(
        f"Os detalhes técnicos foram gravados em:\n{arquivo}\n\n"
        "Se o problema continuar, envie esse arquivo junto com a descrição do que "
        "estava fazendo."
    )
    caixa.setDetailedText(
        "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    )
    caixa.exec()
    return arquivo


def instalar_captura_de_erros() -> None:
    """Troca o `sys.excepthook` para logar e mostrar exceções não tratadas.

    Idempotente: chamar duas vezes não empilha hooks.
    """
    if getattr(sys.excepthook, "_bussola", False):
        return

    def _hook(
        tipo: type[BaseException],
        valor: BaseException,
        rastro: TracebackType | None,
    ) -> None:
        registrar_erro(valor, contexto="exceção não tratada")
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox

            if QApplication.instance() is not None:
                caixa = QMessageBox()
                caixa.setIcon(QMessageBox.Icon.Critical)
                caixa.setWindowTitle("Erro inesperado")
                caixa.setText(
                    "Ocorreu um erro inesperado.\n\n"
                    f"{resumo_do_erro(valor)}\n\nO programa continua aberto; "
                    "a operação interrompida não foi concluída."
                )
                caixa.setInformativeText(f"Detalhes em: {arquivo_de_log()}")
                caixa.exec()
                return
        except ImportError:  # pragma: no cover
            pass
        sys.__excepthook__(tipo, valor, rastro)

    _hook._bussola = True  # type: ignore[attr-defined]
    sys.excepthook = _hook


__all__ = [
    "arquivo_de_log",
    "instalar_captura_de_erros",
    "mostrar_erro",
    "registrar_erro",
    "resumo_do_erro",
]
