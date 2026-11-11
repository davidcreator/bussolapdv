"""Cadastro de produtos, entradas de fornecedor e ajustes de estoque."""

from __future__ import annotations

from ..dominio.auditoria import AcaoAuditoria, EventoAuditoria
from ..dominio.dinheiro import Quantidade
from ..dominio.erros import ErroValidacao
from ..dominio.estoque import EntradaMercadoria, TipoMovimentoEstoque
from ..dominio.produto import Produto
from ..dominio.usuario import Acao, Usuario
from .contexto import Contexto


class ServicoEstoque:
    def __init__(self, contexto: Contexto) -> None:
        self.ctx = contexto

    # -- produtos -----------------------------------------------------------
    def criar_produto(
        self,
        *,
        operador: Usuario,
        codigo: str,
        descricao: str,
        preco: int,
        custo: int,
        categoria: str = "",
        unidade: str = "UN",
        codigo_barras: str | None = None,
        estoque_minimo: int = 0,
        ponto_pedido: int = 0,
        fornecedor: str = "",
    ) -> Produto:
        operador.exigir(Acao.CADASTRO_PRODUTO)
        from ..dominio.produto import Unidade

        produto = Produto(
            codigo=codigo,
            descricao=descricao,
            preco=preco,
            custo=custo,
            categoria=categoria,
            unidade=Unidade(unidade),
            codigo_barras=codigo_barras or None,
            estoque_minimo_milesimos=estoque_minimo,
            ponto_pedido_milesimos=ponto_pedido,
            fornecedor=fornecedor,
        )
        agora = self.ctx.agora()
        with self.ctx.em_transacao():
            criado = self.ctx.produtos.criar(produto, criado_em=agora.isoformat())
            self.ctx.auditoria.registrar(
                EventoAuditoria(
                    acao=AcaoAuditoria.PRODUTO_ALTERADO,
                    criado_em_utc=agora,
                    data_negocio=self.ctx.relogio.data_negocio(),
                    ator_id=operador.id,
                    entidade="produto",
                    entidade_id=criado.id,
                    depois={"codigo": criado.codigo, "preco_centavos": criado.preco},
                    motivo="Cadastro de produto",
                )
            )
        return criado

    # -- entrada de fornecedor ---------------------------------------------
    def registrar_entrada(self, *, operador: Usuario, entrada: EntradaMercadoria) -> dict:
        operador.exigir(Acao.ESTOQUE_ENTRADA)
        agora = self.ctx.agora()
        data_negocio = self.ctx.relogio.data_negocio()
        with self.ctx.em_transacao():
            entrada_id = self.ctx.entradas.registrar_entrada(
                entrada=entrada,
                operador_id=operador.id,
                criado_em=agora,
                data_negocio=data_negocio,
            )
            self.ctx.auditoria.registrar(
                EventoAuditoria(
                    acao=AcaoAuditoria.ENTRADA_REGISTRADA,
                    criado_em_utc=agora,
                    data_negocio=data_negocio,
                    ator_id=operador.id,
                    entidade="entrada",
                    entidade_id=entrada_id,
                    depois={
                        "fornecedor": entrada.fornecedor,
                        "documento": entrada.documento,
                        "frete_centavos": entrada.frete.centavos,
                        "criterio": entrada.criterio.value,
                        "itens": len(entrada.itens),
                    },
                    motivo="Entrada de mercadoria",
                    correlacao_id=entrada_id,
                )
            )
        return {
            "entrada_id": entrada_id,
            "total_centavos": entrada.valor_total.centavos,
            "itens": [
                {
                    "produto_id": item.produto_id,
                    "quantidade_milesimos": item.quantidade.milesimos,
                    "frete_rateado_centavos": item.frete_rateado.centavos,
                    "custo_unitario_com_frete_centavos": entrada.custo_unitario_com_frete(item).centavos,
                }
                for item in entrada.ratear_frete()
            ],
        }

    # -- ajuste -------------------------------------------------------------
    def ajustar(
        self,
        *,
        operador: Usuario,
        autorizador: Usuario,
        produto_id: str,
        quantidade: str,
        motivo: str,
        tipo: TipoMovimentoEstoque = TipoMovimentoEstoque.AJUSTE,
    ) -> int:
        """Ajuste manual (contagem, perda, correção) sempre auditado e com motivo."""
        operador.exigir(Acao.ESTOQUE_AJUSTAR)
        autorizador.exigir(Acao.ESTOQUE_AJUSTAR)
        if autorizador.id == operador.id:
            raise ErroValidacao("Ajuste exige autorizador diferente do operador.")
        if not motivo.strip():
            raise ErroValidacao("Ajuste de estoque exige motivo.")
        produto = self.ctx.produtos.por_id(produto_id)
        qtd = Quantidade.de_unidades(f"{quantidade}".replace(",", "."), escala=produto.unidade.escala)
        if qtd.milesimos == 0:
            raise ErroValidacao("Ajuste com quantidade zero não é registrado.")

        agora = self.ctx.agora()
        with self.ctx.em_transacao():
            self.ctx.estoque.inserir_movimento(
                produto_id=produto_id,
                tipo=tipo,
                quantidade_milesimos_assinada=qtd.milesimos,
                criado_em=agora,
                origem_tipo="AJUSTE",
                origem_id=autorizador.id,
                motivo=motivo,
            )
            novo_saldo = self.ctx.estoque.saldo_milesimos(produto_id)
            self.ctx.auditoria.registrar(
                EventoAuditoria(
                    acao=AcaoAuditoria.AJUSTE_ESTOQUE,
                    criado_em_utc=agora,
                    data_negocio=self.ctx.relogio.data_negocio(),
                    ator_id=operador.id,
                    entidade="produto",
                    entidade_id=produto_id,
                    depois={
                        "quantidade_milesimos": qtd.milesimos,
                        "saldo_milesimos": novo_saldo,
                        "tipo": tipo.value,
                    },
                    motivo=motivo,
                    autorizador_id=autorizador.id,
                )
            )
        return novo_saldo
