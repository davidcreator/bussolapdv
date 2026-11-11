"""Conexão SQLite com as salvaguardas exigidas pelo projeto.

* ``foreign_keys=ON`` em toda conexão (o SQLite desliga por padrão);
* ``journal_mode=WAL`` para leitura concorrente e gravação atômica;
* ``synchronous=FULL`` porque queda de energia não pode gravar meia venda;
* ``busy_timeout`` evita erro imediato em concorrência curta;
* transações explícitas com ``BEGIN IMMEDIATE`` (serializa escritores e evita
  *upgrade* de lock no meio da transação).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

PRAGMAS_OBRIGATORIOS = {
    "foreign_keys": "ON",
    "journal_mode": "WAL",
    "synchronous": "FULL",
    "busy_timeout": "5000",
    "temp_store": "MEMORY",
}


def abrir_conexao(caminho: str | Path, *, somente_leitura: bool = False) -> sqlite3.Connection:
    """Abre (ou cria) o banco aplicando os PRAGMAs do projeto."""
    destino = str(caminho)
    if destino != ":memory:":
        Path(destino).parent.mkdir(parents=True, exist_ok=True)
    conexao = sqlite3.connect(
        destino,
        isolation_level=None,  # controle manual de transação
        check_same_thread=True,
        timeout=5.0,
    )
    conexao.row_factory = sqlite3.Row
    for pragma, valor in PRAGMAS_OBRIGATORIOS.items():
        if somente_leitura and pragma in {"journal_mode", "synchronous"}:
            continue
        conexao.execute(f"PRAGMA {pragma} = {valor}")
    if somente_leitura:
        conexao.execute("PRAGMA query_only = ON")
    return conexao


@contextmanager
def transacao(conexao: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Transação atômica. Qualquer exceção provoca ROLLBACK integral.

    ``BEGIN IMMEDIATE`` pega o lock de escrita na entrada; assim a validação de
    estoque/limite feita dentro do bloco não pode ser invalidada por outro
    processo entre a leitura e a gravação.
    """
    if conexao.in_transaction:
        # Transação aninhada não é suportada: quem chamou deve controlar o escopo.
        raise RuntimeError("Já existe transação aberta nesta conexão.")
    conexao.execute("BEGIN IMMEDIATE")
    try:
        yield conexao
    except BaseException:
        conexao.execute("ROLLBACK")
        raise
    else:
        conexao.execute("COMMIT")


def verificar_integridade(conexao: sqlite3.Connection) -> tuple[bool, list[str]]:
    """``PRAGMA integrity_check`` + ``foreign_key_check``."""
    problemas: list[str] = []
    resultado = conexao.execute("PRAGMA integrity_check").fetchall()
    textos = [linha[0] for linha in resultado]
    if textos != ["ok"]:
        problemas.extend(textos)
    for linha in conexao.execute("PRAGMA foreign_key_check").fetchall():
        problemas.append(f"FK órfã: tabela={linha[0]} rowid={linha[1]} pai={linha[2]}")
    return (not problemas, problemas)


def fazer_backup(
    origem: sqlite3.Connection,
    destino: str | Path,
    *,
    verificar: bool = True,
) -> Path:
    """Backup consistente usando a API de backup do SQLite (seguro com WAL ativo).

    Copiar o arquivo ``.db`` com o banco em uso pode produzir uma cópia sem as
    últimas transações do WAL. A API ``Connection.backup`` resolve isso.
    """
    caminho = Path(destino)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(caminho)) as copia:
        origem.backup(copia)
        copia.execute("PRAGMA foreign_keys = ON")
        if verificar:
            resultado = copia.execute("PRAGMA integrity_check").fetchone()[0]
            if resultado != "ok":
                raise RuntimeError(f"Backup gerado não passou na verificação: {resultado}")
    return caminho
