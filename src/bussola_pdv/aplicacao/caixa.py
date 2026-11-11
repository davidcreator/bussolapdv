"""Abertura, movimentação e fechamento de turno de caixa."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..dominio.auditoria import AcaoAuditoria, EventoAuditoria
from ..dominio.caixa import (
    ContagemDenominacao,
    MovimentoCaixa,
    TipoMovimentoCaixa,
    classificar_diferenca,
    conferir_turno,
    total_contagem,
)
from ..dominio.dinheiro import Dinheiro
from ..dominio.erros import ErroValidacao, TurnoJaFechado
from ..dominio.usuario import Acao, Usuario, exigir_autorizacao
from ..infra.sqlite.repositorio_caixa import TurnoRegistrado
from .contexto import Contexto


@dataclass(frozen=True, slots=True)
class ResultadoFechamento:
    turno: TurnoRegistrado
    conferencia: dict
    avisos: tuple[str, ...] = ()


class ServicoCaixa:
    def __init__(self, contexto: Contexto) -> None:
        self.ctx = contexto

    # -- abertura -----------------------------------------------------------
    def abrir_turno(
        self,
        *,
        caixa: str,
        operador: Usuario,
        fundo: Dinheiro,
        autorizador: Usuario | None = None,
    ) -> TurnoRegistrado:
        operador.exigir(Acao.CAIXA_ABRIR)
        if autorizador is not None and autorizador.id == operador.id:
            raise ErroValidacao("Autorizador deve ser diferente do operador.")
        agora = self.ctx.agora()
        data_negocio = self.ctx.relogio.data_negocio()
        with self.ctx.em_transacao():
            caixa_id = self.ctx.caixas.garantir_caixa(caixa, criado_em=agora.isoformat())
            turno = self.ctx.caixas.abrir_turno(
                caixa_id=caixa_id,
                operador_id=operador.id,
                fundo=fundo,
                aberto_em=agora,
                data_negocio=data_negocio,
            )
            self._auditar(
                AcaoAuditoria.TURNO_ABERTO,
                agora,
                data_negocio,
                operador,
                turno.id,
                depois={"caixa": caixa, "fundo_centavos": fundo.centavos},
                autorizador=autorizador,
            )
        return turno

    # -- movimentações ------------------------------------------------------
    def movimentar(
        self,
        *,
        turno_id: str,
        tipo: TipoMovimentoCaixa,
        valor: Dinheiro,
        motivo: str,
        operador: Usuario,
        autorizador: Usuario | None = None,
    ) -> str:
        if tipo not in (TipoMovimentoCaixa.SANGRIA, TipoMovimentoCaixa.SUPRIMENTO):
            raise ErroValidacao("Use os casos de uso de venda/crediário para esses movimentos.")
        acao = Acao.CAIXA_SANGRIA if tipo is TipoMovimentoCaixa.SANGRIA else Acao.CAIXA_SUPRIMENTO
        if tipo.exige_autorizacao:
            exigir_autorizacao(operador, acao, autorizador)
        else:
            operador.exigir(acao)

        agora = self.ctx.agora()
        data_negocio = self.ctx.relogio.data_negocio()
        with self.ctx.em_transacao():
            turno = self.ctx.caixas.turno_por_id(turno_id)
            if turno.status.value != "ABERTO":
                raise TurnoJaFechado("Turno já encerrado: não aceita movimentos.")
            movimento = MovimentoCaixa(
                tipo=tipo,
                valor=valor,
                motivo=motivo,
                autorizador_id=autorizador.id if autorizador else None,
            )
            movimento_id = self.ctx.caixas.inserir_movimento(
                turno_id=turno_id, movimento=movimento, criado_em=agora
            )
            self._auditar(
                AcaoAuditoria.SANGRIA if tipo is TipoMovimentoCaixa.SANGRIA else AcaoAuditoria.SUPRIMENTO,
                agora,
                data_negocio,
                operador,
                movimento_id,
                depois={"turno_id": turno_id, "valor_centavos": valor.centavos, "motivo": motivo},
                autorizador=autorizador,
            )
        return movimento_id

    # -- fechamento ---------------------------------------------------------
    def conferir(self, turno_id: str) -> dict:
        turno = self.ctx.caixas.carregar_turno(turno_id)
        contagens = self.ctx.caixas.contagens(turno_id)
        return conferir_turno(turno, contagens) if contagens else turno.resumo(Dinheiro.zero())

    def fechar_turno(
        self,
        *,
        turno_id: str,
        conferente: Usuario,
        contagens: list[ContagemDenominacao],
        motivo_diferenca: str = "",
    ) -> ResultadoFechamento:
        conferente.exigir(Acao.CAIXA_FECHAR)
        agora = self.ctx.agora()
        data_negocio = self.ctx.relogio.data_negocio()
        avisos: list[str] = []

        with self.ctx.em_transacao():
            registrado = self.ctx.caixas.turno_por_id(turno_id)
            if registrado.status.value != "ABERTO":
                raise TurnoJaFechado("Turno já está fechado.")
            turno = self.ctx.caixas.carregar_turno(turno_id)
            contado = total_contagem(contagens)
            diferenca = turno.diferenca(contado)
            limite = Dinheiro(self.ctx.parametros.obter_int("caixa.limite_diferenca_centavos"))
            classificacao = classificar_diferenca(diferenca, limite=limite)

            if diferenca.centavos != 0 and not motivo_diferenca.strip():
                raise ErroValidacao(
                    f"Diferença de {diferenca.formatado()} exige justificativa do conferente."
                )
            if classificacao.value == "ACIMA_LIMITE":
                avisos.append(
                    f"Diferença de {diferenca.formatado()} acima do limite de "
                    f"{limite.formatado()}: registre a ocorrência na auditoria."
                )

            fechado = self.ctx.caixas.fechar_turno(
                turno_id=turno_id,
                fechado_em=agora,
                conferente_id=conferente.id,
                contado=contado,
                diferenca=diferenca,
                motivo=motivo_diferenca,
                contagens=contagens,
            )
            conferencia = conferir_turno(turno, contagens)
            self._auditar(
                AcaoAuditoria.TURNO_FECHADO,
                agora,
                data_negocio,
                conferente,
                turno_id,
                depois={
                    "esperado_centavos": conferencia["esperado_centavos"],
                    "contado_centavos": conferencia["contado_centavos"],
                    "diferenca_centavos": conferencia["diferenca_centavos"],
                    "classificacao": conferencia["classificacao"],
                    "motivo": motivo_diferenca,
                },
            )
        return ResultadoFechamento(turno=fechado, conferencia=conferencia, avisos=tuple(avisos))

    # -- apoio --------------------------------------------------------------
    def _auditar(
        self,
        acao: AcaoAuditoria,
        agora: datetime,
        data_negocio: str,
        operador: Usuario,
        entidade_id: str,
        *,
        depois: dict[str, object] | None = None,
        autorizador: Usuario | None = None,
    ) -> None:
        self.ctx.auditoria.registrar(
            EventoAuditoria(
                acao=acao,
                criado_em_utc=agora,
                data_negocio=data_negocio,
                ator_id=operador.id,
                entidade="turno",
                entidade_id=entidade_id,
                depois=depois,
                autorizador_id=autorizador.id if autorizador else None,
                correlacao_id=entidade_id,
            )
        )
