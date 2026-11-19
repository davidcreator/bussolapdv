"""Devolução e estorno: cancela itens, devolve estoque e acerta caixa ou crediário.

Regras que este serviço garante (e que os testes cobrem):

* **nada é apagado** — a venda original continua concluída; a devolução é um
  documento novo, com itens, motivo, prazo e destino do valor;
* **não se devolve o que não foi vendido nem o que já voltou**: a quantidade é
  conferida contra a venda menos as devoluções anteriores;
* **prazo** conta da data de negócio da venda; fora do prazo exige autorização
  nominal (o autorizador fica na auditoria);
* **dinheiro só sai com caixa aberto**, senão o turno do dia não fecha;
* **crédito no crediário** abate as parcelas em aberto do cliente na ordem de
  vencimento, aparecendo como recebimento na forma `VALE`;
* **troca** não movimenta dinheiro: o valor fica na venda nova que o operador faz.

Cancelamento integral continua em `ServicoPDV.cancelar_venda` (é o caso "a venda
inteira não valeu"); este serviço é para devolver **parte** e para dizer **por quê**.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from uuid import uuid4

from ..dominio.auditoria import AcaoAuditoria, EventoAuditoria
from ..dominio.caixa import MovimentoCaixa, TipoMovimentoCaixa
from ..dominio.devolucao import (
    AvaliacaoDePrazo,
    DestinoDevolucao,
    Devolucao,
    ItemDevolvido,
    PoliticaDevolucao,
    TipoDevolucao,
    avaliar_prazo,
)
from ..dominio.dinheiro import Dinheiro, Quantidade
from ..dominio.erros import (
    ErroConflito,
    ErroNaoEncontrado,
    ErroValidacao,
    TurnoNaoAberto,
)
from ..dominio.estoque import TipoMovimentoEstoque
from ..dominio.pagamentos import FormaPagamento
from ..dominio.usuario import Acao, Usuario
from ..dominio.venda import StatusVenda
from .contexto import Contexto


@dataclass(frozen=True, slots=True)
class ItemSolicitado:
    """Uma linha que o operador quer devolver: sequência do item + quantidade."""

    venda_item_sequencia: int
    quantidade: str


@dataclass(frozen=True, slots=True)
class ResultadoDevolucao:
    devolucao_id: str
    total: Dinheiro
    itens: tuple[ItemDevolvido, ...]
    prazo: AvaliacaoDePrazo
    estoque_devolvido: bool
    dinheiro_devolvido: Dinheiro = field(default_factory=Dinheiro.zero)
    credito_aplicado: Dinheiro = field(default_factory=Dinheiro.zero)
    titulos_abatidos: tuple[str, ...] = ()
    avisos: tuple[str, ...] = ()


class ServicoDevolucao:
    def __init__(self, contexto: Contexto) -> None:
        self.ctx = contexto

    # -- política -----------------------------------------------------------
    def politica(self) -> PoliticaDevolucao:
        return PoliticaDevolucao(
            arrependimento_dias=self.ctx.parametros.obter_int("devolucao.prazo_arrependimento_dias"),
            defeito_dias=self.ctx.parametros.obter_int("devolucao.prazo_defeito_dias"),
        )

    # -- consulta -----------------------------------------------------------
    def itens_devolviveis(self, venda_id: str) -> list[dict]:
        """Itens da venda com o que ainda pode voltar (venda − devolvido)."""
        vendidos = self.ctx.vendas.itens(venda_id)
        devolvidos = self.ctx.devolucoes.devolvido_por_item(venda_id)
        resultado: list[dict] = []
        for item in vendidos:
            sequencia = int(item["sequencia"])
            vendido = int(item["quantidade_milesimos"])
            devolvido = int(devolvidos.get(sequencia, 0))
            restante = vendido - devolvido
            resultado.append(
                {
                    **item,
                    "sequencia": sequencia,
                    "devolvido_milesimos": devolvido,
                    "devolvivel_milesimos": max(0, restante),
                    "quantidade_texto": Quantidade(max(0, restante)).formatada(),
                    "total_devolvivel_centavos": self._valor_proporcional(item, max(0, restante)),
                }
            )
        return resultado

    def avaliar(
        self,
        *,
        venda_id: str,
        tipo: TipoDevolucao,
        data_referencia: str | None = None,
    ) -> AvaliacaoDePrazo:
        venda = self.ctx.vendas.por_id(venda_id)
        referencia = date.fromisoformat(data_referencia or self.ctx.relogio.data_negocio())
        return avaliar_prazo(
            tipo,
            data_venda=date.fromisoformat(venda.data_negocio),
            data_devolucao=referencia,
            politica=self.politica(),
        )

    def listar(self, *, limite: int = 500, venda_id: str | None = None) -> list[dict]:
        return self.ctx.devolucoes.listar(limite=limite, venda_id=venda_id)

    def itens(self, devolucao_id: str) -> list[dict]:
        """O que ficou gravado numa devolução — a fonte da 2ª via e da conferência.

        Lê do banco, não da tela: é o que prova, depois, item por item, o que
        voltou e por quanto.
        """
        return self.ctx.devolucoes.itens(devolucao_id)

    # -- registro -----------------------------------------------------------
    def registrar(
        self,
        *,
        operador: Usuario,
        venda_id: str,
        itens: tuple[ItemSolicitado, ...] | list[ItemSolicitado],
        tipo: TipoDevolucao,
        destino: DestinoDevolucao,
        motivo: str,
        autorizador: Usuario | None = None,
        caixa_id: str | None = None,
        devolver_estoque: bool = True,
        observacoes: str = "",
        chave_idempotencia: str | None = None,
        data_referencia: str | None = None,
    ) -> ResultadoDevolucao:
        operador.exigir(Acao.VENDA_DEVOLVER)
        if not str(motivo or "").strip():
            raise ErroValidacao("Devolução exige motivo.")
        if not itens:
            raise ErroValidacao("Selecione ao menos um item para devolver.")

        venda = self.ctx.vendas.por_id(venda_id)
        if venda.status is not StatusVenda.CONCLUIDA:
            raise ErroConflito("Venda cancelada não recebe devolução: o cancelamento já estornou tudo.")

        agora = self.ctx.agora()
        data_negocio = self.ctx.relogio.data_negocio()
        referencia = date.fromisoformat(data_referencia or data_negocio)
        prazo = avaliar_prazo(
            tipo,
            data_venda=date.fromisoformat(venda.data_negocio),
            data_devolucao=referencia,
            politica=self.politica(),
        )
        if prazo.exige_autorizacao:
            if autorizador is None:
                raise ErroValidacao(prazo.motivo)
            autorizador.exigir(Acao.VENDA_DEVOLVER)
            if autorizador.id == operador.id:
                raise ErroValidacao(
                    "Devolução fora do prazo precisa de autorização de OUTRO usuário."
                )

        avisos: list[str] = []
        chave = chave_idempotencia or str(uuid4())
        if chave:
            existente = self._por_chave(chave)
            if existente is not None:  # pragma: no cover - retentativa de duplo clique
                avisos.append("Devolução já registrada com esta chave de idempotência.")

        with self.ctx.em_transacao():
            vendidos = {int(item["sequencia"]): item for item in self.ctx.vendas.itens(venda_id)}
            devolvidos = self.ctx.devolucoes.devolvido_por_item(venda_id)
            itens_devolvidos = self._montar_itens(itens, vendidos, devolvidos, venda_id)
            total = Dinheiro(sum(item.total.centavos for item in itens_devolvidos))

            if total.centavos > venda.total.centavos - self.ctx.devolucoes.total_devolvido(venda_id):
                raise ErroValidacao(
                    "O valor devolvido passaria do total da venda. Confira as quantidades."
                )

            turno_id: str | None = None
            dinheiro = 0
            credito = 0
            titulos: tuple[str, ...] = ()
            if destino is DestinoDevolucao.DINHEIRO:
                if autorizador is None:
                    raise ErroValidacao(
                        "Devolver em dinheiro exige autorização de OUTRO usuário: "
                        "o dinheiro sai da gaveta e precisa de responsável."
                    )
                if caixa_id is None:
                    raise TurnoNaoAberto(
                        "Devolver em dinheiro exige caixa aberto: informe o caixa do turno."
                    )
                turno = self.ctx.caixas.turno_aberto(caixa_id)
                if turno is None:
                    raise TurnoNaoAberto(
                        "Não há turno aberto neste caixa: abra o caixa ou devolva como crédito/troca."
                    )
                turno_id = turno.id
                dinheiro = total.centavos
            elif destino is DestinoDevolucao.CREDITO_CREDIARIO:
                turno = self.ctx.caixas.turno_aberto(caixa_id) if caixa_id else None
                if turno is not None:
                    turno_id = turno.id
                credito, titulos = self._abater_crediario(
                    venda.cliente_id, total, agora, data_negocio, operador, turno_id, venda.rotulo
                )
            else:  # TROCA
                avisos.append(
                    "Troca: o valor não sai da gaveta. Registre a nova venda com os itens que o "
                    "cliente levar."
                )

            devolucao = Devolucao(
                venda_id=venda_id,
                tipo=tipo,
                destino=destino,
                motivo=motivo.strip(),
                itens=tuple(itens_devolvidos),
                operador_id=operador.id,
                dias_desde_venda=prazo.dias_desde_venda,
                fora_do_prazo=prazo.exige_autorizacao,
                estoque_devolvido=devolver_estoque,
                autorizador_id=autorizador.id if autorizador else None,
                turno_id=turno_id,
                observacoes=observacoes.strip(),
                dinheiro_centavos=dinheiro,
                credito_centavos=credito,
                chave_idempotencia=chave,
            )
            self.ctx.devolucoes.inserir(
                devolucao, data_negocio=data_negocio, criado_em=agora.isoformat()
            )

            if devolver_estoque:
                for item in itens_devolvidos:
                    self.ctx.estoque.inserir_movimento(
                        produto_id=item.produto_id,
                        tipo=TipoMovimentoEstoque.ESTORNO,
                        quantidade_milesimos_assinada=item.quantidade.milesimos,
                        criado_em=agora,
                        origem_tipo="DEVOLUCAO",
                        origem_id=devolucao.id,
                        motivo=f"Devolução {devolucao.rotulo} da venda {venda.rotulo}: {motivo}",
                        custo_unitario=item.valor_unitario,
                    )

            if dinheiro:
                self.ctx.caixas.inserir_movimento(
                    turno_id=str(turno_id),
                    movimento=MovimentoCaixa(
                        tipo=TipoMovimentoCaixa.ESTORNO_DINHEIRO,
                        valor=Dinheiro(dinheiro),
                        motivo=f"Devolução {devolucao.rotulo} da venda {venda.rotulo}",
                        autorizador_id=autorizador.id if autorizador else None,
                    ),
                    criado_em=agora,
                    venda_id=venda_id,
                )

            self.ctx.auditoria.registrar(
                EventoAuditoria(
                    acao=AcaoAuditoria.DEVOLUCAO_REGISTRADA,
                    criado_em_utc=agora,
                    data_negocio=data_negocio,
                    ator_id=operador.id,
                    entidade="devolucao",
                    entidade_id=devolucao.id,
                    motivo=f"{tipo.value}: {motivo.strip()}",
                    autorizador_id=autorizador.id if autorizador else None,
                    depois={
                        "venda": venda.rotulo,
                        "tipo": tipo.value,
                        "destino": destino.value,
                        "total_centavos": total.centavos,
                        "dinheiro_centavos": dinheiro,
                        "credito_centavos": credito,
                        "estoque_devolvido": devolver_estoque,
                        "dias_desde_venda": prazo.dias_desde_venda,
                        "fora_do_prazo": prazo.exige_autorizacao,
                        "itens": [
                            {
                                "codigo": item.codigo,
                                "quantidade_milesimos": item.quantidade.milesimos,
                                "total_centavos": item.total.centavos,
                            }
                            for item in itens_devolvidos
                        ],
                    },
                    correlacao_id=venda_id,
                )
            )

        if prazo.exige_autorizacao:
            avisos.append(prazo.motivo)
        return ResultadoDevolucao(
            devolucao_id=devolucao.id,
            total=total,
            itens=tuple(itens_devolvidos),
            prazo=prazo,
            estoque_devolvido=devolver_estoque,
            dinheiro_devolvido=Dinheiro(dinheiro),
            credito_aplicado=Dinheiro(credito),
            titulos_abatidos=titulos,
            avisos=tuple(avisos),
        )

    # -- apoio --------------------------------------------------------------
    def _por_chave(self, chave: str) -> dict | None:
        linha = self.ctx.conexao.execute(
            "SELECT id FROM devolucoes WHERE chave_idempotencia = ?", (chave,)
        ).fetchone()
        return dict(linha) if linha is not None else None

    def _montar_itens(
        self,
        pedidos: tuple[ItemSolicitado, ...] | list[ItemSolicitado],
        vendidos: dict[int, dict],
        devolvidos: dict[int, int],
        venda_id: str,
    ) -> list[ItemDevolvido]:
        montados: list[ItemDevolvido] = []
        vistos: set[int] = set()
        for pedido in pedidos:
            sequencia = int(pedido.venda_item_sequencia)
            if sequencia in vistos:
                raise ErroValidacao("O mesmo item apareceu duas vezes na devolução.")
            vistos.add(sequencia)
            item = vendidos.get(sequencia)
            if item is None:
                raise ErroNaoEncontrado(
                    f"Item {sequencia} não pertence à venda {venda_id}."
                )
            quantidade = Quantidade.de_unidades(pedido.quantidade)
            restante = int(item["quantidade_milesimos"]) - int(devolvidos.get(sequencia, 0))
            if quantidade.milesimos > restante:
                raise ErroValidacao(
                    f"{item['descricao']}: só resta {Quantidade(restante).formatada()} para "
                    f"devolver (vendido {Quantidade(int(item['quantidade_milesimos'])).formatada()}, "
                    f"já devolvido {Quantidade(int(devolvidos.get(sequencia, 0))).formatada()})."
                )
            montados.append(
                ItemDevolvido(
                    produto_id=str(item["produto_id"]),
                    codigo=str(item["codigo_produto"]),
                    descricao=str(item["descricao"]),
                    quantidade=quantidade,
                    valor_unitario=Dinheiro(self._valor_unitario(item)),
                    venda_item_sequencia=sequencia,
                )
            )
        return montados

    def _valor_unitario(self, item: dict) -> int:
        """Valor unitário já com o desconto do item rateado (o que o cliente pagou)."""
        preco = int(item["preco_unitario_centavos"])
        desconto = int(item["desconto_centavos"])
        quantidade = max(1, int(item["quantidade_milesimos"]))
        if desconto <= 0:
            return preco
        return max(0, preco - (desconto * 1000 + quantidade // 2) // quantidade)

    def _valor_proporcional(self, item: dict, quantidade_milesimos: int) -> int:
        unitario = self._valor_unitario(item)
        return (unitario * quantidade_milesimos + 500) // 1000

    def _abater_crediario(
        self,
        cliente_id: str | None,
        total: Dinheiro,
        agora: object,
        data_negocio: str,
        operador: Usuario,
        turno_id: str | None,
        venda_rotulo: str,
    ) -> tuple[int, tuple[str, ...]]:
        """Abate as parcelas em aberto do cliente, das mais antigas para as novas."""
        if cliente_id is None:
            raise ErroValidacao(
                "Devolução como crédito no crediário exige venda de cliente identificado."
            )
        if turno_id is None:
            raise TurnoNaoAberto(
                "Crédito no crediário é registrado como recebimento: abra o caixa primeiro."
            )
        titulos = [
            titulo
            for titulo in self.ctx.crediario.listar(
                cliente_id=cliente_id, incluir_pagos=False, referencia=data_negocio
            )
            if int(titulo["saldo_centavos"]) > 0
        ]
        titulos.sort(key=lambda titulo: str(titulo["vencimento"]))
        restante = total.centavos
        abatidos: list[str] = []
        aplicado = 0
        if not titulos:
            raise ErroValidacao(
                "Cliente sem parcela em aberto: devolva em dinheiro ou como troca."
            )
        for titulo in titulos:
            if restante <= 0:
                break
            saldo = int(titulo["saldo_centavos"])
            valor = Dinheiro(min(saldo, restante))
            self.ctx.crediario.receber(
                titulo_id=str(titulo["id"]),
                valor=valor,
                forma=FormaPagamento.VALE,
                data_negocio=data_negocio,
                turno_id=turno_id,
                operador_id=operador.id,
                criado_em=agora,  # type: ignore[arg-type]
                referencia=f"Devolução da venda {venda_rotulo}",
            )
            abatidos.append(str(titulo["id"]))
            aplicado += valor.centavos
            restante -= valor.centavos
        if restante > 0:
            raise ErroValidacao(
                f"O crédito de {total.formatado()} passa do saldo em aberto do cliente "
                f"({Dinheiro(aplicado).formatado()}). Devolva a diferença em dinheiro ou troca."
            )
        return aplicado, tuple(abatidos)


__all__ = ["ItemSolicitado", "ResultadoDevolucao", "ServicoDevolucao"]
