"""Caso de uso central: finalizar venda de forma atômica e idempotente.

Toda validação crítica é refeita **dentro** da transação: turno aberto, permissão,
desconto, estoque, cobertura de pagamento e crédito. Se qualquer etapa falhar,
nada é gravado — não existe meia venda.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from uuid import uuid4

from ..dominio.auditoria import AcaoAuditoria, EventoAuditoria
from ..dominio.caixa import MovimentoCaixa, TipoMovimentoCaixa
from ..dominio.cliente import avaliar_credito
from ..dominio.crediario import Parcela, gerar_parcelas
from ..dominio.dinheiro import Dinheiro, Percentual
from ..dominio.erros import (
    CarrinhoVazio,
    ErroConflito,
    ErroValidacao,
    EstoqueInsuficiente,
    PagamentoIncompleto,
    TurnoNaoAberto,
)
from ..dominio.estoque import TipoMovimentoEstoque
from ..dominio.pagamentos import FormaPagamento, PlanoPagamento
from ..dominio.usuario import Acao, Usuario, exigir_autorizacao
from ..dominio.venda import Carrinho, ExigenciaDesconto, PoliticaDesconto, StatusVenda, TotaisVenda
from ..infra.sqlite.repositorio_vendas import VendaRegistrada
from .contexto import Contexto


@dataclass(frozen=True, slots=True)
class SolicitacaoVenda:
    operador: Usuario
    caixa_id: str
    carrinho: Carrinho
    plano: PlanoPagamento
    chave_idempotencia: str = field(default_factory=lambda: str(uuid4()))
    cliente_id: str | None = None
    desconto_cupom: Dinheiro = field(default_factory=Dinheiro.zero)
    acrescimo: Dinheiro = field(default_factory=Dinheiro.zero)
    autorizador: Usuario | None = None
    parcelas_crediario: int = 1
    primeiro_vencimento: str | None = None  # ISO; vazio = mensal a partir da data da venda


@dataclass(frozen=True, slots=True)
class ResultadoVenda:
    venda: VendaRegistrada
    totais: TotaisVenda
    plano: PlanoPagamento
    titulos: list[str]
    ja_existia: bool = False
    avisos: tuple[str, ...] = ()


class ServicoPDV:
    def __init__(self, contexto: Contexto) -> None:
        self.ctx = contexto

    # -- políticas ----------------------------------------------------------
    def politica_desconto(self) -> PoliticaDesconto:
        return PoliticaDesconto(
            limite_operador=Percentual(self.ctx.parametros.obter_int("desconto.limite_operador_bp")),
            limite_gerente=Percentual(self.ctx.parametros.obter_int("desconto.limite_gerente_bp")),
            desconto_maximo=Percentual(self.ctx.parametros.obter_int("desconto.limite_maximo_bp")),
        )

    # -- venda --------------------------------------------------------------
    def finalizar_venda(self, solicitacao: SolicitacaoVenda) -> ResultadoVenda:
        if solicitacao.carrinho.vazio:
            raise CarrinhoVazio("Não há itens no carrinho.")

        existente = self.ctx.vendas.por_chave_idempotencia(solicitacao.chave_idempotencia)
        if existente is not None:
            # Repetição de duplo clique/retentativa: devolve o resultado original.
            return ResultadoVenda(
                venda=existente,
                totais=self._totais_do_registro(existente),
                plano=solicitacao.plano,
                titulos=[],
                ja_existia=True,
                avisos=("Venda já registrada com esta chave de idempotência.",),
            )

        agora = self.ctx.agora()
        data_negocio = self.ctx.relogio.data_negocio()
        avisos: list[str] = []
        venda_id = str(uuid4())
        correlacao = venda_id

        with self.ctx.em_transacao():
            solicitacao.operador.exigir(Acao.PDV_VENDER)

            turno = self.ctx.caixas.turno_aberto(solicitacao.caixa_id)
            if turno is None:
                raise TurnoNaoAberto(
                    "Não existe turno aberto para este caixa. Abra o caixa antes de vender."
                )

            totais = solicitacao.carrinho.totais(
                desconto_cupom=solicitacao.desconto_cupom, acrescimo=solicitacao.acrescimo
            )

            # 1) Desconto conforme política e autorização autenticada.
            percentual = solicitacao.carrinho.percentual_desconto(totais)
            exigencia = self.politica_desconto().classificar(percentual)
            if exigencia is ExigenciaDesconto.PROIBIDO:
                raise ErroValidacao(
                    f"Desconto de {percentual.formatado()} excede o máximo permitido."
                )
            if exigencia is ExigenciaDesconto.REQUER_GERENTE:
                exigir_autorizacao(
                    solicitacao.operador, Acao.PDV_DESCONTO_EXCEPCIONAL, solicitacao.autorizador
                )
                self._auditar_desconto(
                    solicitacao, percentual, totais, agora, data_negocio, turno.id, venda_id
                )
                avisos.append(
                    f"Desconto de {percentual.formatado()} autorizado por "
                    f"{solicitacao.autorizador.nome if solicitacao.autorizador else '-'}."
                )

            # 2) Estoque (sempre relido dentro da transação).
            saldos = self.ctx.produtos.saldos([item.produto_id for item in solicitacao.carrinho])
            permitir_negativo = False
            try:
                solicitacao.carrinho.verificar_estoque(saldos)
            except EstoqueInsuficiente:
                exigir_autorizacao(
                    solicitacao.operador, Acao.PDV_VENDA_ESTOQUE_NEGATIVO, solicitacao.autorizador
                )
                permitir_negativo = True
                avisos.append("Venda com estoque insuficiente autorizada por gerente.")

            # 3) Pagamentos cobrem exatamente o total.
            solicitacao.plano.validar_contra(totais.total)
            if (
                self.ctx.parametros.obter_bool("venda.exigir_confirmacao_eletronica")
                and solicitacao.plano.tem_pendente_confirmacao
            ):
                raise PagamentoIncompleto(
                    "Há pagamento eletrônico pendente de confirmação. "
                    "Confirme o recebimento antes de finalizar."
                )

            # 4) Crediário: cliente, limite e atraso.
            cliente = None
            a_prazo = [p for p in solicitacao.plano.pagamentos if p.forma is FormaPagamento.A_PRAZO]
            parcelas: list[Parcela] = []
            if a_prazo:
                cliente_id = solicitacao.cliente_id
                if cliente_id is None:
                    raise ErroValidacao("Venda a prazo exige cliente identificado.")
                cliente = self.ctx.clientes.por_id(cliente_id)
                if not cliente.ativo:
                    raise ErroValidacao("Cliente inativo não pode comprar a prazo.")
                valor_prazo = a_prazo[0].valor_aplicado
                situacao = self._situacao_credito(cliente.id, data_negocio)
                autorizado = False
                if solicitacao.autorizador is not None:
                    autorizado = solicitacao.autorizador.pode(Acao.PDV_VENDA_A_PRAZO) and (
                        solicitacao.autorizador.id != solicitacao.operador.id
                    )
                avaliar_credito(
                    limite=cliente.limite_credito,
                    saldo_devedor=situacao["saldo_devedor"],
                    vencido=situacao["vencido"],
                    atraso_maximo_dias=situacao["atraso_maximo"],
                    dias_bloqueio_atraso=self.ctx.parametros.obter_int("crediario.dias_bloqueio_atraso"),
                    valor_pretendido=valor_prazo.centavos,
                    autorizado_por_gerente=autorizado,
                )
                if solicitacao.parcelas_crediario > self.ctx.parametros.obter_int(
                    "crediario.maximo_parcelas"
                ):
                    raise ErroValidacao("Número de parcelas acima do máximo configurado.")
                parcelas = gerar_parcelas(
                    valor_prazo,
                    solicitacao.parcelas_crediario,
                    base=date.fromisoformat(data_negocio),
                    primeiro_vencimento=(
                        date.fromisoformat(solicitacao.primeiro_vencimento)
                        if solicitacao.primeiro_vencimento
                        else None
                    ),
                )

            # 5) Gravação atômica de tudo.
            registrada = self.ctx.vendas.inserir(
                venda_id=venda_id,
                data_negocio=data_negocio,
                criado_em=agora,
                operador_id=solicitacao.operador.id,
                turno_id=turno.id,
                cliente_id=solicitacao.cliente_id,
                subtotal=totais.subtotal,
                desconto=totais.desconto_total,
                acrescimo=totais.acrescimo,
                total=totais.total,
                custo_total=totais.custo_total,
                chave_idempotencia=solicitacao.chave_idempotencia,
            )
            self.ctx.vendas.inserir_itens(venda_id, solicitacao.carrinho.itens)
            self.ctx.vendas.inserir_pagamentos(venda_id, solicitacao.plano, criado_em=agora)

            for item in solicitacao.carrinho.itens:
                self.ctx.estoque.inserir_movimento(
                    produto_id=item.produto_id,
                    tipo=TipoMovimentoEstoque.VENDA,
                    quantidade_milesimos_assinada=-item.quantidade.milesimos,
                    criado_em=agora,
                    origem_tipo="VENDA",
                    origem_id=venda_id,
                    motivo=f"Venda {registrada.rotulo}",
                    custo_unitario=item.custo_unitario,
                )

            if solicitacao.plano.dinheiro_aplicado.centavos > 0:
                self.ctx.caixas.inserir_movimento(
                    turno_id=turno.id,
                    movimento=MovimentoCaixa(
                        tipo=TipoMovimentoCaixa.VENDA_DINHEIRO,
                        valor=solicitacao.plano.dinheiro_aplicado,
                        motivo=f"Venda {registrada.rotulo}",
                    ),
                    criado_em=agora,
                    venda_id=venda_id,
                )

            titulos: list[str] = []
            if parcelas:
                titulos = self.ctx.crediario.inserir_parcelas(
                    venda_id=venda_id,
                    cliente_id=solicitacao.cliente_id,  # type: ignore[arg-type]
                    parcelas=parcelas,
                    criado_em=agora,
                )

            if permitir_negativo:
                self._auditar(
                    AcaoAuditoria.ESTOQUE_NEGATIVO_AUTORIZADO,
                    agora,
                    data_negocio,
                    solicitacao.operador.id,
                    entidade="venda",
                    entidade_id=venda_id,
                    motivo="Venda autorizada com saldo insuficiente",
                    autorizador_id=solicitacao.autorizador.id if solicitacao.autorizador else None,
                    depois={
                        "venda": registrada.rotulo,
                        "itens": [
                            {"produto": i.codigo, "quantidade": i.quantidade.milesimos}
                            for i in solicitacao.carrinho.itens
                        ],
                    },
                    correlacao=correlacao,
                )

            self._auditar(
                AcaoAuditoria.VENDA_FINALIZADA,
                agora,
                data_negocio,
                solicitacao.operador.id,
                entidade="venda",
                entidade_id=venda_id,
                motivo="Finalização de venda",
                autorizador_id=solicitacao.autorizador.id if solicitacao.autorizador else None,
                depois={
                    "numero": registrada.rotulo,
                    "total_centavos": registrada.total.centavos,
                    "desconto_centavos": registrada.desconto.centavos,
                    "formas": [p.forma.value for p in solicitacao.plano.pagamentos],
                    "cliente_id": solicitacao.cliente_id,
                    "turno_id": turno.id,
                },
                correlacao=correlacao,
            )

        if solicitacao.plano.tem_pendente_confirmacao:
            avisos.append(
                "Pagamento eletrônico registrado como PENDENTE: confirme o recebimento "
                "conforme o procedimento da loja. Registro não comprova liquidação."
            )
        return ResultadoVenda(
            venda=registrada,
            totais=totais,
            plano=solicitacao.plano,
            titulos=titulos,
            avisos=tuple(avisos),
        )

    # -- cancelamento -------------------------------------------------------
    def cancelar_venda(
        self,
        *,
        venda_id: str,
        motivo: str,
        operador: Usuario,
        autorizador: Usuario,
        devolver_estoque: bool = True,
    ) -> dict:
        """Cancela com eventos compensatórios: nunca apaga nem sobrescreve histórico."""
        if not motivo.strip():
            raise ErroValidacao("Cancelamento exige motivo.")
        agora = self.ctx.agora()
        data_negocio = self.ctx.relogio.data_negocio()

        with self.ctx.em_transacao():
            venda = self.ctx.vendas.por_id(venda_id)
            if venda.status is not StatusVenda.CONCLUIDA:
                raise ErroConflito("Venda já cancelada.")
            autorizador.exigir(Acao.VENDA_CANCELAR)

            titulos = self.ctx.crediario.listar(
                cliente_id=venda.cliente_id, incluir_pagos=True, limite=1000
            )
            titulos_da_venda = [t for t in titulos if t["venda_id"] == venda_id]
            if any(int(t["recebido_centavos"]) > 0 for t in titulos_da_venda):
                raise ErroConflito(
                    "Título desta venda já tem recebimento. Trate o estorno do crediário "
                    "manualmente antes de cancelar a venda."
                )

            itens = self.ctx.vendas.itens(venda_id)
            if devolver_estoque:
                for item in itens:
                    self.ctx.estoque.inserir_movimento(
                        produto_id=item["produto_id"],
                        tipo=TipoMovimentoEstoque.ESTORNO,
                        quantidade_milesimos_assinada=int(item["quantidade_milesimos"]),
                        criado_em=agora,
                        origem_tipo="CANCELAMENTO",
                        origem_id=venda_id,
                        motivo=f"Cancelamento da venda {venda.rotulo}",
                    )

            # Devolução do dinheiro só ocorre se o turno original ainda estiver aberto.
            turno = self.ctx.caixas.turno_por_id(venda.turno_id)
            dinheiro = sum(
                p["valor_aplicado_centavos"]
                for p in self.ctx.vendas.pagamentos(venda_id)
                if p["forma"] == FormaPagamento.DINHEIRO.value
            )
            reembolso_registrado = False
            if dinheiro and turno.status.value == "ABERTO":
                self.ctx.caixas.inserir_movimento(
                    turno_id=turno.id,
                    movimento=MovimentoCaixa(
                        tipo=TipoMovimentoCaixa.ESTORNO_DINHEIRO,
                        valor=Dinheiro(dinheiro),
                        motivo=f"Cancelamento da venda {venda.rotulo}: {motivo}",
                        autorizador_id=autorizador.id,
                    ),
                    criado_em=agora,
                    venda_id=venda_id,
                )
                reembolso_registrado = True

            for titulo in titulos_da_venda:
                self.ctx.conexao.execute(
                    "UPDATE titulos SET status = 'CANCELADO' WHERE id = ?", (titulo["id"],)
                )

            self.ctx.vendas.cancelar(
                venda_id, cancelada_em=agora, motivo=motivo, autorizador_id=autorizador.id
            )
            self._auditar(
                AcaoAuditoria.VENDA_CANCELADA,
                agora,
                data_negocio,
                operador.id,
                entidade="venda",
                entidade_id=venda_id,
                motivo=motivo,
                autorizador_id=autorizador.id,
                antes={"status": "CONCLUIDA", "total_centavos": venda.total.centavos},
                depois={
                    "status": "CANCELADA",
                    "estoque_devolvido": devolver_estoque,
                    "reembolso_em_dinheiro": reembolso_registrado,
                },
                correlacao=venda_id,
            )

        return {
            "venda_id": venda_id,
            "estoque_devolvido": devolver_estoque,
            "reembolso_em_dinheiro_registrado": reembolso_registrado,
            "aviso": (
                ""
                if reembolso_registrado or not dinheiro
                else "Turno original fechado: reembolso em dinheiro deve ser feito no turno atual."
            ),
        }

    # -- apoio --------------------------------------------------------------
    def _situacao_credito(self, cliente_id: str, data_negocio: str) -> dict:
        referencia = date.fromisoformat(data_negocio)
        saldo = self.ctx.clientes.saldo_devedor(cliente_id)
        vencido, atraso = self.ctx.clientes.vencido_e_atraso(cliente_id, referencia)
        return {"saldo_devedor": saldo, "vencido": vencido, "atraso_maximo": atraso}

    def _totais_do_registro(self, venda: VendaRegistrada) -> TotaisVenda:
        return TotaisVenda(
            subtotal=venda.subtotal,
            desconto_itens=Dinheiro.zero(),
            desconto_cupom=venda.desconto,
            acrescimo=venda.acrescimo,
            total=venda.total,
            custo_total=venda.custo_total,
        )

    def _auditar(
        self,
        acao: AcaoAuditoria,
        agora: datetime,
        data_negocio: str,
        ator_id: str | None,
        *,
        entidade: str,
        entidade_id: str,
        motivo: str = "",
        autorizador_id: str | None = None,
        antes: dict[str, object] | None = None,
        depois: dict[str, object] | None = None,
        correlacao: str = "",
    ) -> None:
        self.ctx.auditoria.registrar(
            EventoAuditoria(
                acao=acao,
                criado_em_utc=agora,
                data_negocio=data_negocio,
                ator_id=ator_id,
                entidade=entidade,
                entidade_id=entidade_id,
                antes=antes,
                depois=depois,
                motivo=motivo,
                autorizador_id=autorizador_id,
                correlacao_id=correlacao,
            )
        )

    def _auditar_desconto(
        self,
        solicitacao: SolicitacaoVenda,
        percentual: Percentual,
        totais: TotaisVenda,
        agora: datetime,
        data_negocio: str,
        turno_id: str,
        venda_id: str,
    ) -> None:
        self._auditar(
            AcaoAuditoria.DESCONTO_AUTORIZADO,
            agora,
            data_negocio,
            solicitacao.operador.id,
            entidade="venda",
            entidade_id=venda_id,
            motivo=f"Desconto de {percentual.formatado()} acima do limite do operador",
            autorizador_id=solicitacao.autorizador.id if solicitacao.autorizador else None,
            depois={
                "percentual_bp": percentual.bp,
                "desconto_centavos": totais.desconto_total.centavos,
                "total_centavos": totais.total.centavos,
                "turno_id": turno_id,
            },
            correlacao=solicitacao.chave_idempotencia,
        )
