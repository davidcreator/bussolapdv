"""Migrações versionadas e ordenadas, aplicadas em transação.

Cada arquivo ``NNNN_descricao.sql`` é uma versão. A versão aplicada é registrada
em ``esquema_versao``; uma migração que falhe é revertida por completo, de modo
que o banco nunca fica em estado intermediário.

Diretiva opcional na primeira linha do arquivo::

    -- sem-foreign-keys

Reconstrói tabelas referenciadas por chaves estrangeiras (caso de um CHECK que
precise mudar). A migração roda com ``PRAGMA foreign_keys=OFF`` e, antes do
COMMIT, executa ``PRAGMA foreign_key_check``: se qualquer referência ficar
órfã, a migração é revertida e o erro é propagado.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

DIR_MIGRACOES = Path(__file__).parent / "migracoes"
_PADRAO = re.compile(r"^(\d{4})_(.+)\.sql$")


class ErroMigracao(RuntimeError):
    pass


def migracoes_disponiveis(diretorio: Path | None = None) -> list[tuple[int, str, Path]]:
    diretorio = diretorio or DIR_MIGRACOES
    encontradas: list[tuple[int, str, Path]] = []
    for arquivo in sorted(diretorio.glob("*.sql")):
        casamento = _PADRAO.match(arquivo.name)
        if not casamento:
            raise ErroMigracao(f"Nome de migração inválido: {arquivo.name}")
        encontradas.append((int(casamento.group(1)), casamento.group(2).replace("_", " "), arquivo))
    versoes = [v for v, _, _ in encontradas]
    if len(set(versoes)) != len(versoes):
        raise ErroMigracao(f"Versões duplicadas em {diretorio}")
    return encontradas


def versao_atual(conexao: sqlite3.Connection) -> int:
    existe = conexao.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='esquema_versao'"
    ).fetchone()
    if not existe:
        return 0
    linha = conexao.execute("SELECT COALESCE(MAX(versao), 0) FROM esquema_versao").fetchone()
    return int(linha[0])


def migrar(
    conexao: sqlite3.Connection,
    *,
    ate: int | None = None,
    diretorio: Path | None = None,
) -> list[int]:
    """Aplica as migrações pendentes e devolve as versões aplicadas nesta chamada."""
    atual = versao_atual(conexao)
    aplicadas: list[int] = []
    for versao, descricao, arquivo in migracoes_disponiveis(diretorio):
        if versao <= atual or (ate is not None and versao > ate):
            continue
        sql = arquivo.read_text(encoding="utf-8")
        sem_fk = _exige_foreign_keys_off(sql)
        if sem_fk:
            conexao.execute("PRAGMA foreign_keys = OFF")
        conexao.execute("BEGIN IMMEDIATE")
        try:
            # `executescript` faz COMMIT implícito; por isso dividimos e executamos
            # comando a comando dentro da nossa própria transação.
            for comando in _dividir_comandos(sql):
                conexao.execute(comando)
            if sem_fk:
                orfas = conexao.execute("PRAGMA foreign_key_check").fetchall()
                if orfas:
                    raise ErroMigracao(
                        f"A migração {arquivo.name} deixaria {len(orfas)} referência(s) órfã(s)."
                    )
            conexao.execute(
                "INSERT INTO esquema_versao (versao, descricao, aplicado_em) VALUES (?, ?, ?)",
                (versao, descricao, datetime.now(UTC).isoformat()),
            )
        except Exception as exc:
            conexao.execute("ROLLBACK")
            raise ErroMigracao(f"Falha ao aplicar a migração {arquivo.name}: {exc}") from exc
        else:
            conexao.execute("COMMIT")
            aplicadas.append(versao)
        finally:
            if sem_fk:
                conexao.execute("PRAGMA foreign_keys = ON")
    return aplicadas


def _exige_foreign_keys_off(sql: str) -> bool:
    """Diretiva declarada na primeira linha não vazia do arquivo."""
    for linha in sql.splitlines():
        if linha.strip():
            return "sem-foreign-keys" in linha
    return False


def _dividir_comandos(sql: str) -> list[str]:
    """Divide um script em comandos respeitando ``BEGIN ... END`` dos triggers."""
    comandos: list[str] = []
    buffer: list[str] = []
    dentro_trigger = False
    for linha in sql.splitlines():
        sem_comentario = linha.split("--", 1)[0]
        if not sem_comentario.strip() and not dentro_trigger:
            continue
        buffer.append(linha)
        maiuscula = sem_comentario.upper()
        if "CREATE TRIGGER" in maiuscula:
            dentro_trigger = True
        if dentro_trigger:
            if "END;" in maiuscula:
                comandos.append("\n".join(buffer).strip())
                buffer = []
                dentro_trigger = False
            continue
        if sem_comentario.rstrip().endswith(";"):
            comandos.append("\n".join(buffer).strip())
            buffer = []
    resto = "\n".join(buffer).strip()
    if resto:
        comandos.append(resto)
    return comandos
