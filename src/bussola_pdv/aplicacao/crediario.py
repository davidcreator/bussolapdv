"""Recebimento de títulos do crediário e consulta de aging."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ..dominio.auditoria import AcaoAuditoria, EventoAuditoria
from ..dominio.caixa import MovimentoCaixa, TipoMovimentoCaixa
from ..dominio.dinheiro import Dinheiro
from ..dominio.erros import ErroValidacao, TurnoNaoAberto
from ..dominio.pagamentos import FormaPagamento
from ..dominio.usuario import Acao, Usuario
from .contexto import Contexto


@dataclass(frozen=True, slots=True)
class ResultadoRecebimento:
    recebimento_id: str
    titulo_id: str
    valor: Dinheiro
    saldo_restante: Dinheiro
    entrou_no_caixa: bool


class ServicoCrediario:
    def __init__(self, contexto: Contexto) -> None:
        self.ctx = contexto

    def receber(
        self,
        *,
        titulo_id: str,
        valor: Dinheiro,
        forma: FormaPagamento,
        operador: Usuario,
        caixa_id: str,
        referencia: str = "",
    ) -> ResultadoRecebimento:
        """Recebe título (parcial ou total). Recebimento **não** é faturamento novo."""
        operador.exigir(Acao.TITULO_RECEBER)
        if forma is FormaPagamento.A_PRAZO:
            raise ErroValidacao("Recebimento não pode ser a prazo.")
        agora = self.ctx.agora()
        data_negocio = self.ctx.relogio.data_negocio()

        with self.ctx.em_transacao():
            turno = self.ctx.caixas.turno_aberto(caixa_id)
            if turno is None:
                raise TurnoNaoAberto("Recebimento em dinheiro/cartão exige turno aberto no caixa.")
            recebimento_id = self.ctx.crediario.receber(
                titulo_id=titulo_id,
                valor=valor,
                forma=forma,
                data_negocio=data_negocio,
                turno_id=turno.id,
                operador_id=operador.id,
                criado_em=agora,
                referencia=referencia,
            )
            entrou_no_caixa = False
            if forma is FormaPagamento.DINHEIRO:
                self.ctx.caixas.inserir_movimento(
                    turno_id=turno.id,
                    movimento=MovimentoCaixa(
                        tipo=TipoMovimentoCaixa.RECEBIMENTO_TITULO,
                        valor=valor,
                        motivo=f"Recebimento de título {titulo_id}",
                        origem_id=titulo_id,
                    ),
                    criado_em=agora,
                )
                entrou_no_caixa = True

            titulo = self.ctx.crediario.por_id(titulo_id)
            self.ctx.auditoria.registrar(
                EventoAuditoria(
                    acao=AcaoAuditoria.TITULO_RECEBIDO,
                    criado_em_utc=agora,
                    data_negocio=data_negocio,
                    ator_id=operador.id,
                    entidade="titulo",
                    entidade_id=titulo_id,
                    depois={
                        "valor_centavos": valor.centavos,
                        "forma": forma.value,
                        "turno_id": turno.id,
                        "saldo_restante_centavos": titulo["saldo_centavos"],
                    },
                    correlacao_id=titulo["venda_id"],
                )
            )
        return ResultadoRecebimento(
            recebimento_id=recebimento_id,
            titulo_id=titulo_id,
            valor=valor,
            saldo_restante=Dinheiro(int(titulo["saldo_centavos"])),
            entrou_no_caixa=entrou_no_caixa,
        )

    # -- consultas ----------------------------------------------------------
    def listar(self, *, cliente_id: str | None = None, incluir_pagos: bool = False) -> list[dict]:
        return self.ctx.crediario.listar(
            cliente_id=cliente_id,
            incluir_pagos=incluir_pagos,
            referencia=self.ctx.relogio.data_negocio(),
        )

    def aging(self, cliente_id: str) -> dict[str, object]:
        referencia = date.fromisoformat(self.ctx.relogio.data_negocio())
        resultado = self.ctx.clientes.aging(cliente_id, referencia)
        cliente = self.ctx.clientes.por_id(cliente_id)
        return {
            "cliente": cliente.nome,
            "cliente_id": cliente_id,
            "data_referencia": resultado.data_referencia.isoformat(),
            "faixas_centavos": resultado.faixas,
            "total_aberto_centavos": resultado.total_aberto,
            "vencido_centavos": resultado.vencido,
            "atraso_maximo_dias": resultado.atraso_maximo_dias,
            "limite_centavos": cliente.limite_credito,
            "disponivel_centavos": max(0, cliente.limite_credito - resultado.total_aberto),
        }
