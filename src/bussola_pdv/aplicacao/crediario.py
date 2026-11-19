"""Recebimento de títulos do crediário e consulta de aging."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ..dominio.auditoria import AcaoAuditoria, EventoAuditoria
from ..dominio.caixa import MovimentoCaixa, TipoMovimentoCaixa
from ..dominio.dinheiro import Dinheiro, Percentual
from ..dominio.encargos import EncargosDevidos, PoliticaEncargos, calcular_encargos
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
    #: Multa + juros cobrados junto (zero quando não havia atraso ou a loja não cobra).
    encargo: Dinheiro = Dinheiro.zero()
    multa: Dinheiro = Dinheiro.zero()
    juros: Dinheiro = Dinheiro.zero()
    dias_atraso: int = 0
    #: Havia encargo devido e a loja perdoou, com autorizador e motivo.
    encargos_dispensados: bool = False

    @property
    def total_pago(self) -> Dinheiro:
        return Dinheiro(self.valor.centavos + self.encargo.centavos)


class ServicoCrediario:
    def __init__(self, contexto: Contexto) -> None:
        self.ctx = contexto

    # -- encargos -----------------------------------------------------------
    def politica(self) -> PoliticaEncargos:
        """Política de encargos lida dos parâmetros (nunca número solto no código)."""
        return PoliticaEncargos(
            multa=Percentual(self.ctx.parametros.obter_int("encargos.multa_bp")),
            juros_mes=Percentual(self.ctx.parametros.obter_int("encargos.juros_mes_bp")),
            carencia_dias=self.ctx.parametros.obter_int("encargos.carencia_dias"),
        )

    def cobranca_ligada(self) -> bool:
        return bool(self.ctx.parametros.obter_int("encargos.cobrar"))

    def encargos_do_titulo(
        self, titulo_id: str, *, data_referencia: str | None = None
    ) -> EncargosDevidos:
        """Encargos devidos hoje (multa + juros) sobre o saldo do título.

        Calcula sempre — mesmo com a cobrança desligada — porque a tela precisa
        mostrar quanto seria cobrado antes de a loja decidir ligar.
        """
        titulo = self.ctx.crediario.por_id(titulo_id)
        referencia = date.fromisoformat(data_referencia or self.ctx.relogio.data_negocio())
        return calcular_encargos(
            Dinheiro(int(titulo["saldo_centavos"])),
            vencimento=date.fromisoformat(str(titulo["vencimento"])),
            referencia=referencia,
            politica=self.politica(),
        )

    # -- recebimento --------------------------------------------------------
    def receber(
        self,
        *,
        titulo_id: str,
        valor: Dinheiro,
        forma: FormaPagamento,
        operador: Usuario,
        caixa_id: str,
        referencia: str = "",
        cobrar_encargos: bool = True,
        motivo_dispensa: str = "",
        autorizador: Usuario | None = None,
    ) -> ResultadoRecebimento:
        """Recebe título (parcial ou total). Recebimento **não** é faturamento novo.

        Multa e juros do atraso são cobrados junto com a parcela, mas **fora** do
        principal: o título continua com o valor original e o encargo vira receita
        identificada (`recebimentos.encargo_centavos` + movimento de caixa próprio).

        Perdoar o encargo é operação sensível: exige `autorizador` com a permissão
        `TITULO_ENCARGO_DISPENSAR` e motivo escrito.
        """
        operador.exigir(Acao.TITULO_RECEBER)
        if forma is FormaPagamento.A_PRAZO:
            raise ErroValidacao("Recebimento não pode ser a prazo.")
        agora = self.ctx.agora()
        data_negocio = self.ctx.relogio.data_negocio()

        devidos = self.encargos_do_titulo(titulo_id, data_referencia=data_negocio)
        # Três situações distintas, de propósito:
        # 1. a loja não cobra encargos (parâmetro desligado) → nada a cobrar e nada
        #    a perdoar: o recebimento é o mesmo de antes desta versão;
        # 2. cobra e o operador cobra → multa e juros entram como receita separada;
        # 3. cobra e o operador perdoa → exige autorizador com permissão e motivo.
        if not self.cobranca_ligada() or devidos.total.centavos == 0:
            cobrar = False
            dispensados = False
        elif cobrar_encargos:
            cobrar = True
            dispensados = False
        else:
            if autorizador is None:
                raise ErroValidacao(
                    f"Perdoar {devidos.total.formatado()} de encargos exige a senha de um "
                    "gerente (autorizador)."
                )
            autorizador.exigir(Acao.TITULO_ENCARGO_DISPENSAR)
            if not motivo_dispensa.strip():
                raise ErroValidacao("Perdoar encargo exige motivo escrito.")
            cobrar = False
            dispensados = True
        encargo = devidos.total if cobrar else Dinheiro.zero()

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
                multa_centavos=devidos.multa.centavos if cobrar else 0,
                juros_centavos=devidos.juros.centavos if cobrar else 0,
                dias_atraso=devidos.dias_atraso if cobrar else 0,
                encargos_dispensados=dispensados,
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
                if encargo.centavos > 0:
                    # O dinheiro do encargo entra na gaveta e precisa aparecer no
                    # fechamento como receita própria — não misturado com a parcela.
                    self.ctx.caixas.inserir_movimento(
                        turno_id=turno.id,
                        movimento=MovimentoCaixa(
                            tipo=TipoMovimentoCaixa.RECEBIMENTO_ENCARGOS,
                            valor=encargo,
                            motivo=(
                                f"Encargos do título {titulo_id}: multa "
                                f"{devidos.multa.formatado()} + juros "
                                f"{devidos.juros.formatado()} ({devidos.dias_atraso} dia(s))"
                            ),
                            origem_id=titulo_id,
                        ),
                        criado_em=agora,
                    )

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
                        "multa_centavos": devidos.multa.centavos if cobrar else 0,
                        "juros_centavos": devidos.juros.centavos if cobrar else 0,
                        "dias_atraso": devidos.dias_atraso if cobrar else 0,
                        "encargos_dispensados_centavos": (
                            devidos.total.centavos if dispensados else 0
                        ),
                        "autorizador_id": autorizador.id if dispensados and autorizador else None,
                        "motivo_dispensa": motivo_dispensa.strip() if dispensados else "",
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
            encargo=encargo,
            multa=devidos.multa if cobrar else Dinheiro.zero(),
            juros=devidos.juros if cobrar else Dinheiro.zero(),
            dias_atraso=devidos.dias_atraso if cobrar else 0,
            encargos_dispensados=dispensados,
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
