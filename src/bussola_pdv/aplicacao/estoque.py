"""Cadastro de produtos, entradas de fornecedor e ajustes de estoque."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from ..dominio.auditoria import AcaoAuditoria, EventoAuditoria
from ..dominio.dinheiro import Quantidade
from ..dominio.erros import ErroValidacao
from ..dominio.estoque import EntradaMercadoria, TipoMovimentoEstoque
from ..dominio.produto import Produto, Unidade
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
        garantia_dias: int = 0,
    ) -> Produto:
        operador.exigir(Acao.CADASTRO_PRODUTO)
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
            garantia_dias=garantia_dias,
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

    def alterar_produto(
        self,
        *,
        operador: Usuario,
        produto_id: str,
        **campos: object,
    ) -> Produto:
        """Altera preço, custo, descrição, mínimo e o resto do cadastro do produto.

        A alteração é auditada com o **antes e o depois**: mudar preço de gôndola
        sem rastro é o tipo de coisa que a trilha existe para pegar.
        """
        operador.exigir(Acao.CADASTRO_PRODUTO)
        atual = self.ctx.produtos.por_id(produto_id)
        permitidos = {
            "codigo",
            "descricao",
            "preco",
            "custo",
            "categoria",
            "unidade",
            "codigo_barras",
            "estoque_minimo_milesimos",
            "ponto_pedido_milesimos",
            "fornecedor",
            "ncm",
            "ativo",
            "garantia_dias",
        }
        invalidos = sorted(set(campos) - permitidos)
        if invalidos:
            raise ErroValidacao(f"Campo de produto não alterável: {', '.join(invalidos)}")
        if "unidade" in campos and not isinstance(campos["unidade"], Unidade):
            raise ErroValidacao("Unidade inválida para o produto.")
        alteracoes: dict[str, Any] = {
            chave: valor for chave, valor in campos.items() if valor is not None
        }
        if not alteracoes:
            return atual
        novo = replace(atual, **alteracoes)
        if novo == atual:
            return atual
        agora = self.ctx.agora()
        with self.ctx.em_transacao():
            salvo = self.ctx.produtos.atualizar(novo, atualizado_em=agora.isoformat())
            self.ctx.auditoria.registrar(
                EventoAuditoria(
                    acao=AcaoAuditoria.PRODUTO_ALTERADO,
                    criado_em_utc=agora,
                    data_negocio=self.ctx.relogio.data_negocio(),
                    ator_id=operador.id,
                    entidade="produto",
                    entidade_id=salvo.id,
                    antes={
                        "codigo": atual.codigo,
                        "descricao": atual.descricao,
                        "preco_centavos": atual.preco,
                        "custo_centavos": atual.custo,
                        "minimo_milesimos": atual.estoque_minimo_milesimos,
                        "ponto_pedido_milesimos": atual.ponto_pedido_milesimos,
                        "ativo": atual.ativo,
                    },
                    depois={
                        "codigo": salvo.codigo,
                        "descricao": salvo.descricao,
                        "preco_centavos": salvo.preco,
                        "custo_centavos": salvo.custo,
                        "minimo_milesimos": salvo.estoque_minimo_milesimos,
                        "ponto_pedido_milesimos": salvo.ponto_pedido_milesimos,
                        "ativo": salvo.ativo,
                    },
                    motivo="Alteração de cadastro de produto",
                )
            )
        return salvo

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
        # `Quantidade.de_unidades` recusa negativo — e é bom que recuse. O sinal do
        # ajuste é do movimento, não da grandeza: "-2" é baixa de duas unidades, e
        # sem isso a contagem que encontrou falta não tinha como ser registrada.
        texto = f"{quantidade}".replace(",", ".").strip()
        negativo = texto.startswith("-")
        qtd = Quantidade.de_unidades(
            texto.lstrip("+-") or "0", escala=produto.unidade.escala
        )
        if qtd.milesimos == 0:
            raise ErroValidacao("Ajuste com quantidade zero não é registrado.")
        assinada = -qtd.milesimos if negativo else qtd.milesimos

        agora = self.ctx.agora()
        with self.ctx.em_transacao():
            self.ctx.estoque.inserir_movimento(
                produto_id=produto_id,
                tipo=tipo,
                quantidade_milesimos_assinada=assinada,
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
                        "quantidade_milesimos": assinada,
                        "saldo_milesimos": novo_saldo,
                        "tipo": tipo.value,
                    },
                    motivo=motivo,
                    autorizador_id=autorizador.id,
                )
            )
        return novo_saldo
