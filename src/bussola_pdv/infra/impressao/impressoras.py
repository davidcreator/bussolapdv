"""Impressoras instaladas e envio de bytes crus (ESC/POS).

Duas coisas diferentes vivem aqui, e a diferença importa para quem dá suporte:

* `listar()` / `padrao()` — só perguntam ao sistema (Qt), valem em qualquer
  impressora instalada, térmica ou não;
* `enviar_bytes()` — manda os bytes ESC/POS **crus** para a fila, sem driver
  interpretar. É o que faz corte de papel, gaveta e código de barras nativo
  funcionarem. No Windows vai por `winspool.drv` (ctypes, sem `pywin32`); no
  Linux/macOS vai por `lp -o raw`, que o CUPS entende.

Quando o envio cru não está disponível (sistema sem `lp`, Windows sem permissão de
spooler, impressora só com driver gráfico), o erro diz o que fazer — e a saída é a
configuração `impressao.motor = SISTEMA`, que passa pelo driver e sempre funciona.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence

from ...dominio.erros import ErroImpressao, ImpressoraIndisponivel


def _qt_app() -> object:
    from PySide6.QtWidgets import QApplication

    existente = QApplication.instance()
    if existente is not None:
        return existente
    import os

    if not os.environ.get("DISPLAY") and sys.platform not in ("win32", "darwin"):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication(["bussola-impressoras"])


def listar() -> list[str]:
    """Nomes das impressoras instaladas no sistema (ordem alfabética)."""
    from PySide6.QtPrintSupport import QPrinterInfo

    _qt_app()
    return sorted(info.printerName() for info in QPrinterInfo.availablePrinters())


def padrao() -> str:
    """Nome da impressora padrão do sistema, ou string vazia se não houver."""
    from PySide6.QtPrintSupport import QPrinterInfo

    _qt_app()
    return QPrinterInfo.defaultPrinterName()


def eh_termica(nome: str) -> bool:
    """Palpite **explícito** pelo nome — só para sugerir na tela, nunca para decidir.

    Nome de impressora não é dado confiável: a mesma Elgin pode estar cadastrada
    como "POS-80" ou "Impressora 2". Por isso isto aqui só pré-seleciona a opção na
    interface; quem manda é a configuração salva.
    """
    alvo = nome.lower()
    pistas = ("thermal", "termic", "pos-", "pos58", "pos80", "tm-", "tm_", "elgin", "bematech", "mp-")
    return any(pista in alvo for pista in pistas)


# -- envio cru ------------------------------------------------------------
def _enviar_windows(nome: str, dados: bytes) -> None:
    """`winspool.drv` via ctypes: `OpenPrinter` + `StartDocPrinter("RAW")`.

    Sem `pywin32` de propósito: uma dependência compilada a menos no instalador.
    """
    import ctypes
    from ctypes import wintypes

    def ultimo_erro() -> int:
        """`ctypes.get_last_error` só existe no Windows; fora dele, zero."""
        return int(getattr(ctypes, "get_last_error", lambda: 0)())

    spooler = ctypes.WinDLL("winspool.drv", use_last_error=True)  # type: ignore[attr-defined]

    class DocInfo1(ctypes.Structure):  # espelha a DOC_INFO_1 do Win32
        _fields_ = [
            ("pDocName", wintypes.LPWSTR),
            ("pOutputFile", wintypes.LPWSTR),
            ("pDatatype", wintypes.LPWSTR),
        ]

    spooler.OpenPrinterW.argtypes = [
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.HANDLE),
        wintypes.LPVOID,
    ]
    spooler.StartDocPrinterW.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(DocInfo1)]
    spooler.StartPagePrinter.argtypes = [wintypes.HANDLE]
    spooler.WritePrinter.argtypes = [
        wintypes.HANDLE,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    spooler.EndPagePrinter.argtypes = [wintypes.HANDLE]
    spooler.EndDocPrinter.argtypes = [wintypes.HANDLE]
    spooler.ClosePrinter.argtypes = [wintypes.HANDLE]

    handle = wintypes.HANDLE()
    if not spooler.OpenPrinterW(nome, ctypes.byref(handle), None):
        raise ImpressoraIndisponivel(
            f"Não foi possível abrir a impressora {nome!r} no spooler do Windows "
            f"(erro {ultimo_erro()}).",
            detalhe={"impressora": nome, "sistema": "windows"},
        )
    try:
        info = DocInfo1("Bússola PDV", None, "RAW")
        if not spooler.StartDocPrinterW(handle, 1, ctypes.byref(info)):
            raise ImpressoraIndisponivel(
                f"A impressora {nome!r} recusou o documento cru (ESC/POS). "
                "Se ela usa driver gráfico, configure o motor SISTEMA.",
                detalhe={"impressora": nome},
            )
        try:
            spooler.StartPagePrinter(handle)
            escritos = wintypes.DWORD()
            buffer = ctypes.create_string_buffer(dados, len(dados))
            if not spooler.WritePrinter(handle, buffer, len(dados), ctypes.byref(escritos)):
                raise ImpressoraIndisponivel(
                    f"Falha ao escrever na impressora {nome!r} (erro {ultimo_erro()}).",
                    detalhe={"impressora": nome},
                )
            spooler.EndPagePrinter(handle)
        finally:
            spooler.EndDocPrinter(handle)
    finally:
        spooler.ClosePrinter(handle)


def _enviar_unix(nome: str, dados: bytes) -> None:
    """`lp -d <nome> -o raw` — o CUPS repassa os bytes sem interpretar."""
    lp = shutil.which("lp")
    if lp is None:
        raise ImpressoraIndisponivel(
            "O comando 'lp' (CUPS) não está disponível neste sistema, então não há como "
            "enviar ESC/POS cru. Instale o CUPS ou use o motor SISTEMA (driver da impressora).",
            detalhe={"sistema": sys.platform},
        )
    processo = subprocess.run(  # noqa: S603 - caminho resolvido por shutil.which
        [lp, "-d", nome, "-o", "raw"],
        input=dados,
        capture_output=True,
        check=False,
        timeout=30,
    )
    if processo.returncode != 0:
        raise ImpressoraIndisponivel(
            f"O CUPS recusou o trabalho para {nome!r}: "
            f"{processo.stderr.decode(errors='replace').strip() or 'sem mensagem'}.",
            detalhe={"impressora": nome, "codigo": processo.returncode},
        )


def enviar_bytes(
    nome: str,
    dados: bytes,
    *,
    executores: dict[str, Callable[[str, bytes], None]] | None = None,
) -> None:
    """Manda `dados` crus para a impressora `nome`.

    `executores` existe para teste: a suíte injeta funções falsas no lugar do
    spooler do Windows e do `lp`, provando que o caminho escolhido e os bytes
    passados são os certos sem precisar de impressora de verdade.
    """
    if not nome.strip():
        raise ErroImpressao(
            "Nenhuma impressora configurada para impressão direta (ESC/POS).",
            detalhe={"motivo": "impressora_nao_configurada"},
        )
    if not dados:
        raise ErroImpressao("Nada para imprimir: o documento está vazio.")
    mapa = executores or {
        "win32": _enviar_windows,
        "posix": _enviar_unix,
    }
    chave = "win32" if sys.platform == "win32" else "posix"
    executor = mapa.get(chave)
    if executor is None:  # pragma: no cover - sistemas exóticos
        raise ImpressoraIndisponivel(
            f"Envio cru (ESC/POS) não implementado em {sys.platform!r}. Use o motor SISTEMA.",
            detalhe={"sistema": sys.platform},
        )
    executor(nome, dados)


def impressoras_para_tela() -> Sequence[tuple[str, str]]:
    """Pares `(nome, dica)` para o seletor da interface."""
    lista = listar()
    return [(nome, "térmica (provável)" if eh_termica(nome) else "comum") for nome in lista]


__all__ = [
    "eh_termica",
    "enviar_bytes",
    "impressoras_para_tela",
    "listar",
    "padrao",
]
