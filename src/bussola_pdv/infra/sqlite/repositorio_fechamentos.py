"""Repositório de snapshots de fechamento (imutáveis, versionados)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime

from .base import RepositorioBase


class FechamentoRepositorio(RepositorioBase):
    def proxima_versao(self, data_negocio: str, turno_id: str = "") -> int:
        linha = self.conexao.execute(
            "SELECT COALESCE(MAX(versao), 0) FROM fechamentos WHERE data_negocio = ? AND turno_id = ?",
            (data_negocio, turno_id),
        ).fetchone()
        return int(linha[0]) + 1

    def registrar(
        self,
        *,
        data_negocio: str,
        turno_id: str,
        snapshot: dict,
        criado_em: datetime,
        criado_por: str | None = None,
    ) -> str:
        fechamento_id = str(uuid.uuid4())
        self.conexao.execute(
            """INSERT INTO fechamentos (id, data_negocio, turno_id, versao, criado_em,
                                        criado_por, snapshot_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                fechamento_id,
                data_negocio,
                turno_id,
                self.proxima_versao(data_negocio, turno_id),
                self.iso(criado_em),
                criado_por,
                json.dumps(snapshot, ensure_ascii=False, sort_keys=True),
            ),
        )
        return fechamento_id

    def listar(self, *, data_negocio: str | None = None, limite: int = 50) -> list[dict]:
        if data_negocio:
            linhas = self.conexao.execute(
                "SELECT * FROM fechamentos WHERE data_negocio = ? ORDER BY versao DESC LIMIT ?",
                (data_negocio, limite),
            )
        else:
            linhas = self.conexao.execute(
                "SELECT * FROM fechamentos ORDER BY data_negocio DESC, versao DESC LIMIT ?", (limite,)
            )
        resultado = []
        for linha in linhas:
            dados = dict(linha)
            dados["snapshot"] = json.loads(dados.pop("snapshot_json"))
            resultado.append(dados)
        return resultado
