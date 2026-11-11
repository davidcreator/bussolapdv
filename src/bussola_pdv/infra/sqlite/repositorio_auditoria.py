"""Repositório da trilha de auditoria append-only."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime

from ...dominio.auditoria import (
    AcaoAuditoria,
    EventoAuditoria,
    ResultadoVerificacao,
    encadear,
    verificar_cadeia,
)
from ...dominio.erros import ErroNaoEncontrado
from .base import RepositorioBase


class AuditoriaRepositorio(RepositorioBase):
    def _ultimo(self) -> EventoAuditoria | None:
        linha = self.conexao.execute("SELECT * FROM auditoria ORDER BY sequencia DESC LIMIT 1").fetchone()
        return self._para_evento(linha) if linha else None

    def _para_evento(self, linha: sqlite3.Row) -> EventoAuditoria:
        return EventoAuditoria(
            acao=AcaoAuditoria(linha["acao"]),
            criado_em_utc=datetime.fromisoformat(linha["criado_em_utc"]),
            data_negocio=linha["data_negocio"],
            ator_id=linha["ator_id"],
            entidade=linha["entidade"],
            entidade_id=linha["entidade_id"],
            antes=json.loads(linha["antes"]) if linha["antes"] else None,
            depois=json.loads(linha["depois"]) if linha["depois"] else None,
            motivo=linha["motivo"],
            autorizador_id=linha["autorizador_id"],
            origem=linha["origem"],
            correlacao_id=linha["correlacao_id"],
            sequencia=int(linha["sequencia"]),
            hash_anterior=linha["hash_anterior"],
            hash=linha["hash"],
        )

    def registrar(self, evento: EventoAuditoria) -> EventoAuditoria:
        """Encadeia o evento ao anterior, calcula o hash e grava.

        Deve ser chamado **dentro** da transação da operação auditada; assim a
        venda e seu evento entram ou saem juntos.
        """
        ultimo = self._ultimo()
        encadeado = encadear([ultimo] if ultimo else [], evento)
        self.conexao.execute(
            """INSERT INTO auditoria (sequencia, id, criado_em_utc, data_negocio, ator_id, acao,
                                      entidade, entidade_id, antes, depois, motivo,
                                      autorizador_id, origem, correlacao_id,
                                      hash_anterior, hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                encadeado.sequencia,
                str(uuid.uuid4()),
                encadeado.criado_em_utc.isoformat(),
                encadeado.data_negocio,
                encadeado.ator_id,
                encadeado.acao.value,
                encadeado.entidade,
                encadeado.entidade_id,
                json.dumps(encadeado.antes, ensure_ascii=False) if encadeado.antes is not None else None,
                json.dumps(encadeado.depois, ensure_ascii=False) if encadeado.depois is not None else None,
                encadeado.motivo,
                encadeado.autorizador_id,
                encadeado.origem,
                encadeado.correlacao_id,
                encadeado.hash_anterior,
                encadeado.hash,
            ),
        )
        return encadeado

    def listar(
        self,
        *,
        limite: int = 200,
        acao: AcaoAuditoria | None = None,
        entidade_id: str | None = None,
        data_negocio: str | None = None,
    ) -> list[EventoAuditoria]:
        condicoes = ["1 = 1"]
        parametros: list[object] = []
        if acao:
            condicoes.append("acao = ?")
            parametros.append(acao.value)
        if entidade_id:
            condicoes.append("entidade_id = ?")
            parametros.append(entidade_id)
        if data_negocio:
            condicoes.append("data_negocio = ?")
            parametros.append(data_negocio)
        sql = f"""SELECT * FROM auditoria WHERE {' AND '.join(condicoes)}
                  ORDER BY sequencia DESC LIMIT ?"""
        parametros.append(limite)
        return [self._para_evento(linha) for linha in self.conexao.execute(sql, parametros)]

    def por_id(self, evento_id: str) -> EventoAuditoria:
        linha = self.conexao.execute("SELECT * FROM auditoria WHERE id = ?", (evento_id,)).fetchone()
        if linha is None:
            raise ErroNaoEncontrado("Evento de auditoria não encontrado.")
        return self._para_evento(linha)

    def ultimo(self) -> EventoAuditoria | None:
        return self._ultimo()

    def verificar(self) -> ResultadoVerificacao:
        eventos = [
            self._para_evento(linha)
            for linha in self.conexao.execute("SELECT * FROM auditoria ORDER BY sequencia")
        ]
        return verificar_cadeia(eventos)
