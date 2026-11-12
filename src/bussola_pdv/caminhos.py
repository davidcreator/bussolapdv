"""Onde a instalação guarda dados no disco, por sistema operacional.

Regra: **dado de loja não mora dentro da pasta de instalação**. Programa pode ser
atualizado ou desinstalado; a base do PDV, as cópias de segurança e os relatórios
não. Por isso o banco fica no diretório de dados do usuário:

* Windows  → ``%LOCALAPPDATA%\\BussolaPDV``
* Linux    → ``$XDG_DATA_HOME/bussola-pdv`` (ou ``~/.local/share/bussola-pdv``)
* macOS    → ``~/Library/Application Support/BussolaPDV``

**A pasta de dados é escolhível.** Quem instala pode querer a base em outra
unidade (``D:\\PDV``, um SSD separado, uma pasta sincronizada). A escolha fica
gravada em um arquivo pequeno — ``instalacao.json`` — no diretório de
configuração do usuário (``%APPDATA%\\BussolaPDV`` no Windows,
``~/.config/bussola-pdv`` no Linux), **fora** da pasta de dados: se o ponteiro
morasse dentro dela, mudar de pasta perderia o ponteiro.

Precedência: ``BUSSOLA_DADOS`` (ambiente) > pasta escolhida na instalação >
padrão do sistema. A variável de ambiente ganha porque é o que permite rodar
duas instalações lado a lado, uma demo em pendrive ou um teste isolado.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

from .dominio.erros import ErroBussola

NOME_PASTA = "BussolaPDV"
NOME_BANCO = "pdv.db"
NOME_COPIAS = "copias"
NOME_CONFIG = "instalacao.json"

CHAVE_DADOS = "dados"


# -- configuração (ponteiro para a pasta de dados) ------------------------------
def diretorio_de_configuracao() -> Path:
    """Onde fica o ``instalacao.json`` — nunca dentro da pasta de dados."""
    caminho = os.environ.get("BUSSOLA_CONFIG", "").strip()
    if caminho:
        return Path(caminho).expanduser()
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / NOME_PASTA
        return Path.home() / "AppData" / "Roaming" / NOME_PASTA
    if sys.platform == "darwin":  # pragma: no cover - não testado em macOS
        return Path.home() / "Library" / "Application Support" / NOME_PASTA / "config"
    base = os.environ.get("XDG_CONFIG_HOME")
    return (Path(base) if base else Path.home() / ".config") / "bussola-pdv"


def arquivo_de_configuracao() -> Path:
    return diretorio_de_configuracao() / NOME_CONFIG


def ler_configuracao() -> dict[str, str]:
    """Conteúdo do ``instalacao.json``; arquivo ausente ou inválido vira ``{}``.

    Configuração ilegível não pode impedir o programa de abrir: nesse caso a
    instalação volta ao padrão do sistema em vez de morrer na inicialização.
    """
    arquivo = arquivo_de_configuracao()
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(dados, dict):
        return {}
    return {str(chave): str(valor) for chave, valor in dados.items()}


def salvar_configuracao(**valores: str) -> Path:
    """Grava o JSON de forma atômica (temporário + ``replace``)."""
    pasta = diretorio_de_configuracao()
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = pasta / NOME_CONFIG
    atual = ler_configuracao()
    atual.update({chave: str(valor) for chave, valor in valores.items()})
    descritor, temporario = tempfile.mkstemp(dir=pasta, prefix=".instalacao-", suffix=".json")
    try:
        with os.fdopen(descritor, "w", encoding="utf-8") as manipulador:
            json.dump(atual, manipulador, ensure_ascii=False, indent=2, sort_keys=True)
        Path(temporario).replace(arquivo)
    except BaseException:
        Path(temporario).unlink(missing_ok=True)
        raise
    return arquivo


# -- diretório de dados ---------------------------------------------------------
def _padrao() -> Path:
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / NOME_PASTA
        return Path.home() / "AppData" / "Local" / NOME_PASTA
    if sys.platform == "darwin":  # pragma: no cover - não testado em macOS
        return Path.home() / "Library" / "Application Support" / NOME_PASTA
    base = os.environ.get("XDG_DATA_HOME")
    return (Path(base) if base else Path.home() / ".local" / "share") / "bussola-pdv"


def diretorio_de_dados_padrao() -> Path:
    """Pasta que o sistema sugere (``%LOCALAPPDATA%\\BussolaPDV`` no Windows)."""
    return _padrao()


def origem_do_diretorio() -> str:
    """De onde veio a pasta em uso: ``BUSSOLA_DADOS``, ``configuracao`` ou ``padrao``.

    Serve para a tela e o ``bussola dados`` explicarem *por que* a base está onde
    está — sem isso, quem definiu a variável meses atrás não entende por que a
    escolha da instalação "não pega".
    """
    if os.environ.get("BUSSOLA_DADOS", "").strip():
        return "BUSSOLA_DADOS"
    if ler_configuracao().get(CHAVE_DADOS, "").strip():
        return "configuracao"
    return "padrao"


def diretorio_de_dados() -> Path:
    """Diretório base de dados em uso (criado se não existir)."""
    caminho = os.environ.get("BUSSOLA_DADOS", "").strip()
    escolhido = caminho or ler_configuracao().get(CHAVE_DADOS, "").strip()
    pasta = Path(escolhido).expanduser() if escolhido else _padrao()
    try:
        pasta.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ErroBussola(
            f"Não foi possível usar a pasta de dados {pasta}: {exc}. "
            "Escolha outra pasta ou libere a permissão de escrita."
        ) from exc
    return pasta


def definir_diretorio_de_dados(destino: str | Path) -> Path:
    """Grava a pasta de dados escolhida e devolve o caminho normalizado.

    A pasta é criada e testada com uma gravação real antes de ser adotada: escolher
    um pendrive desconectado ou uma pasta somente-leitura precisa falhar **aqui**,
    com mensagem, e não na primeira venda.
    """
    pasta = Path(destino).expanduser()
    if not str(pasta).strip() or str(pasta) in {".", ""}:
        raise ErroBussola("Informe a pasta onde os dados devem ficar.")
    pasta = pasta.resolve()
    try:
        pasta.mkdir(parents=True, exist_ok=True)
        teste = pasta / ".escrita-ok"
        teste.write_text("ok", encoding="utf-8")
        teste.unlink()
    except OSError as exc:
        raise ErroBussola(
            f"Não é possível gravar em {pasta}: {exc}. "
            "Escolha uma pasta do usuário, de preferência fora de Program Files."
        ) from exc
    salvar_configuracao(**{CHAVE_DADOS: str(pasta)})
    return pasta


def voltar_ao_diretorio_padrao() -> Path:
    """Esquece a pasta escolhida (volta ao padrão do sistema)."""
    arquivo = arquivo_de_configuracao()
    dados = ler_configuracao()
    dados.pop(CHAVE_DADOS, None)
    pasta = diretorio_de_configuracao()
    if not dados:
        arquivo.unlink(missing_ok=True)
        return _padrao()
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )
    return _padrao()


# -- caminhos derivados ---------------------------------------------------------
def banco_padrao() -> Path:
    """Caminho do banco da instalação (``pdv.db`` dentro do diretório de dados)."""
    return diretorio_de_dados() / NOME_BANCO


def banco_em(pasta: str | Path) -> Path:
    """Caminho do banco dentro de uma pasta de dados arbitrária (pré-visualização)."""
    return Path(pasta).expanduser() / NOME_BANCO


def pasta_de_relatorios() -> Path:
    """Pasta sugerida para relatórios exportados (Excel/PDF)."""
    pasta = diretorio_de_dados() / "relatorios"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def pasta_de_copias() -> Path:
    """Pasta sugerida para cópias de segurança."""
    pasta = diretorio_de_dados() / NOME_COPIAS
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def pasta_de_logs() -> Path:
    """Logs de erro da instalação (o app empacotado não tem terminal)."""
    pasta = diretorio_de_dados() / "logs"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta
