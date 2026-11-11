"""Repositório de caixas, turnos, movimentos de gaveta e contagens."""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime

from ...dominio.caixa import (
    ContagemDenominacao,
    MovimentoCaixa,
    StatusTurno,
    TipoMovimentoCaixa,
    Turno,
)
from ...dominio.dinheiro import Dinheiro
from ...dominio.erros import ErroNaoEncontrado, TurnoJaAberto
from .base import RepositorioBase


@dataclass(frozen=True, slots=True)
class TurnoRegistrado:
    id: str
    caixa_id: str
    operador_id: str
    data_negocio: str
    fundo: Dinheiro
    aberto_em: datetime
    status: StatusTurno
    fechado_em: datetime | None = None
    contado: Dinheiro | None = None
    diferenca: Dinheiro | None = None
    conferente_id: str | None = None
    motivo_diferenca: str | None = None


class CaixaRepositorio(RepositorioBase):
    # -- caixas físicas -----------------------------------------------------
    def garantir_caixa(self, nome: str, *, criado_em: str) -> str:
        existente = self.conexao.execute("SELECT id FROM caixas WHERE nome = ?", (nome,)).fetchone()
        if existente:
            return str(existente["id"])
        novo_id = str(uuid.uuid4())
        self.conexao.execute(
            "INSERT INTO caixas (id, nome, ativo, criado_em) VALUES (?, ?, 1, ?)",
            (novo_id, nome, criado_em),
        )
        return novo_id

    def listar_caixas(self) -> list[dict[str, str]]:
        return [
            dict(linha)
            for linha in self.conexao.execute("SELECT id, nome, ativo FROM caixas ORDER BY nome")
        ]

    # -- turnos -------------------------------------------------------------
    def _para_turno(self, linha: sqlite3.Row) -> TurnoRegistrado:
        return TurnoRegistrado(
            id=linha["id"],
            caixa_id=linha["caixa_id"],
            operador_id=linha["operador_id"],
            data_negocio=linha["data_negocio"],
            fundo=self.dinheiro(linha["fundo_centavos"]),
            aberto_em=datetime.fromisoformat(linha["aberto_em"]),
            status=StatusTurno(linha["status"]),
            fechado_em=self.instante(linha["fechado_em"]),
            contado=None if linha["contado_centavos"] is None else self.dinheiro(linha["contado_centavos"]),
            diferenca=(
                None if linha["diferenca_centavos"] is None
                else self.dinheiro(linha["diferenca_centavos"])
            ),
            conferente_id=linha["conferente_id"],
            motivo_diferenca=linha["motivo_diferenca"],
        )

    def abrir_turno(
        self,
        *,
        caixa_id: str,
        operador_id: str,
        fundo: Dinheiro,
        aberto_em: datetime,
        data_negocio: str,
    ) -> TurnoRegistrado:
        """Abre turno. A unicidade é garantida pelo índice parcial do banco."""
        turno_id = str(uuid.uuid4())
        try:
            self.conexao.execute(
                """INSERT INTO turnos (id, caixa_id, operador_id, data_negocio, fundo_centavos,
                                       aberto_em, status)
                   VALUES (?, ?, ?, ?, ?, ?, 'ABERTO')""",
                (turno_id, caixa_id, operador_id, data_negocio, fundo.centavos, self.iso(aberto_em)),
            )
        except sqlite3.IntegrityError as exc:
            raise TurnoJaAberto("Já existe um turno aberto para este caixa.") from exc
        return self.turno_por_id(turno_id)

    def turno_por_id(self, turno_id: str) -> TurnoRegistrado:
        linha = self.conexao.execute("SELECT * FROM turnos WHERE id = ?", (turno_id,)).fetchone()
        if linha is None:
            raise ErroNaoEncontrado("Turno não encontrado.")
        return self._para_turno(linha)

    def turno_aberto(self, caixa_id: str) -> TurnoRegistrado | None:
        linha = self.conexao.execute(
            "SELECT * FROM turnos WHERE caixa_id = ? AND status = 'ABERTO'", (caixa_id,)
        ).fetchone()
        return self._para_turno(linha) if linha else None

    def turnos_abertos(self) -> list[TurnoRegistrado]:
        return [
            self._para_turno(linha)
            for linha in self.conexao.execute(
                "SELECT * FROM turnos WHERE status = 'ABERTO' ORDER BY aberto_em"
            )
        ]

    def turnos_do_dia(self, data_negocio: str) -> list[TurnoRegistrado]:
        return [
            self._para_turno(linha)
            for linha in self.conexao.execute(
                "SELECT * FROM turnos WHERE data_negocio = ? ORDER BY aberto_em", (data_negocio,)
            )
        ]

    def fechar_turno(
        self,
        *,
        turno_id: str,
        fechado_em: datetime,
        conferente_id: str,
        contado: Dinheiro,
        diferenca: Dinheiro,
        motivo: str = "",
        contagens: list[ContagemDenominacao] | None = None,
    ) -> TurnoRegistrado:
        cursor = self.conexao.execute(
            """UPDATE turnos
                  SET status = 'FECHADO', fechado_em = ?, conferente_id = ?,
                      contado_centavos = ?, diferenca_centavos = ?, motivo_diferenca = ?
                WHERE id = ? AND status = 'ABERTO'""",
            (
                self.iso(fechado_em),
                conferente_id,
                contado.centavos,
                diferenca.centavos,
                motivo.strip(),
                turno_id,
            ),
        )
        if cursor.rowcount == 0:
            raise ErroNaoEncontrado("Turno não está aberto para fechamento.")
        for contagem in contagens or []:
            self.conexao.execute(
                """INSERT INTO contagens_caixa (id, turno_id, denominacao, quantidade, criado_em)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4()),
                    turno_id,
                    contagem.denominacao,
                    contagem.quantidade,
                    self.iso(fechado_em),
                ),
            )
        return self.turno_por_id(turno_id)

    # -- movimentos ---------------------------------------------------------
    def inserir_movimento(
        self,
        *,
        turno_id: str,
        movimento: MovimentoCaixa,
        criado_em: datetime,
        venda_id: str | None = None,
    ) -> str:
        movimento_id = str(uuid.uuid4())
        self.conexao.execute(
            """INSERT INTO movimentos_caixa (id, turno_id, tipo, valor_centavos, venda_id,
                                             titulo_id, motivo, autorizador_id, criado_em)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                movimento_id,
                turno_id,
                movimento.tipo.value,
                movimento.valor.centavos,
                venda_id,
                movimento.origem_id or None,
                movimento.motivo,
                movimento.autorizador_id,
                self.iso(criado_em),
            ),
        )
        return movimento_id

    def movimentos(self, turno_id: str) -> list[MovimentoCaixa]:
        linhas = self.conexao.execute(
            "SELECT tipo, valor_centavos, motivo, titulo_id, autorizador_id "
            "FROM movimentos_caixa WHERE turno_id = ? ORDER BY criado_em, rowid",
            (turno_id,),
        )
        return [
            MovimentoCaixa(
                tipo=TipoMovimentoCaixa(linha["tipo"]),
                valor=self.dinheiro(linha["valor_centavos"]),
                motivo=linha["motivo"],
                origem_id=linha["titulo_id"] or "",
                autorizador_id=linha["autorizador_id"],
            )
            for linha in linhas
        ]

    def carregar_turno(self, turno_id: str) -> Turno:
        """Monta o agregado de domínio usado na conferência e no fechamento."""
        registrado = self.turno_por_id(turno_id)
        return Turno(
            caixa_id=registrado.caixa_id,
            operador_id=registrado.operador_id,
            fundo=registrado.fundo,
            aberto_em=registrado.aberto_em,
            status=registrado.status,
            fechado_em=registrado.fechado_em,
            movimentos=tuple(self.movimentos(turno_id)),
        )

    def contagens(self, turno_id: str) -> list[ContagemDenominacao]:
        return [
            ContagemDenominacao(denominacao=int(linha["denominacao"]), quantidade=int(linha["quantidade"]))
            for linha in self.conexao.execute(
                "SELECT denominacao, quantidade FROM contagens_caixa WHERE turno_id = ?", (turno_id,)
            )
        ]
