"""Cadastro de clientes: criar e alterar, com autorização e auditoria.

O repositório já sabia gravar (`clientes.criar` / `clientes.atualizar`); faltava o
caso de uso — é ele que exige a permissão `CADASTRO_CLIENTE`, recusa documento
repetido com mensagem de gente e registra **quem** mexeu no limite de crédito.
Limite é dinheiro que a loja aceita esperar: mudança silenciosa nele é o tipo de
coisa que só aparece na cobrança.
"""

from __future__ import annotations

from ..dominio.auditoria import AcaoAuditoria, EventoAuditoria
from ..dominio.cliente import Cliente
from ..dominio.erros import ErroConflito, ErroNaoEncontrado, ErroValidacao
from ..dominio.usuario import Acao, Usuario
from .contexto import Contexto


class ServicoClientes:
    def __init__(self, contexto: Contexto) -> None:
        self.ctx = contexto

    # -- criar --------------------------------------------------------------
    def criar_cliente(
        self,
        *,
        operador: Usuario,
        nome: str,
        documento: str | None = None,
        limite_credito: int = 0,
        observacoes: str = "",
    ) -> Cliente:
        operador.exigir(Acao.CADASTRO_CLIENTE)
        cliente = Cliente(
            nome=nome,
            documento=(documento or "").strip() or None,
            limite_credito=limite_credito,
            observacoes=observacoes,
        )
        self._recusar_documento_repetido(cliente)
        agora = self.ctx.agora()
        try:
            with self.ctx.em_transacao():
                criado = self.ctx.clientes.criar(cliente, criado_em=agora.isoformat())
                self._auditar(operador, criado, motivo="Cadastro de cliente", antes=None)
        except ErroConflito as exc:
            raise ErroValidacao(str(exc)) from exc
        return criado

    # -- alterar ------------------------------------------------------------
    def alterar_cliente(
        self,
        *,
        operador: Usuario,
        cliente_id: str,
        nome: str | None = None,
        documento: str | None = None,
        limite_credito: int | None = None,
        ativo: bool | None = None,
        observacoes: str | None = None,
    ) -> Cliente:
        operador.exigir(Acao.CADASTRO_CLIENTE)
        atual = self.ctx.clientes.por_id(cliente_id)
        novo = Cliente(
            id=atual.id,
            nome=atual.nome if nome is None else nome,
            documento=(
                atual.documento if documento is None else ((documento or "").strip() or None)
            ),
            limite_credito=atual.limite_credito if limite_credito is None else limite_credito,
            ativo=atual.ativo if ativo is None else ativo,
            observacoes=atual.observacoes if observacoes is None else observacoes,
        )
        if novo.documento != atual.documento:
            self._recusar_documento_repetido(novo)
        if novo == atual:
            return atual
        try:
            with self.ctx.em_transacao():
                salvo = self.ctx.clientes.atualizar(novo)
                self._auditar(operador, salvo, motivo="Alteração de cliente", antes=atual)
        except ErroConflito as exc:
            raise ErroValidacao(str(exc)) from exc
        return salvo

    # -- interno ------------------------------------------------------------
    def _recusar_documento_repetido(self, cliente: Cliente) -> None:
        if not cliente.documento:
            return
        try:
            existente = self.ctx.clientes.por_documento(cliente.documento)
        except ErroNaoEncontrado:
            return
        if existente.id != cliente.id:
            raise ErroValidacao(
                f"Já existe cliente com o documento {cliente.documento_mascarado()} "
                f"({existente.nome})."
            )

    def _auditar(
        self,
        operador: Usuario,
        cliente: Cliente,
        *,
        motivo: str,
        antes: Cliente | None,
    ) -> None:
        self.ctx.auditoria.registrar(
            EventoAuditoria(
                acao=AcaoAuditoria.CLIENTE_ALTERADO,
                criado_em_utc=self.ctx.agora(),
                data_negocio=self.ctx.relogio.data_negocio(),
                ator_id=operador.id,
                entidade="cliente",
                entidade_id=cliente.id,
                antes=(
                    None
                    if antes is None
                    else {
                        "nome": antes.nome,
                        "documento": antes.documento,
                        "limite_centavos": antes.limite_credito,
                        "ativo": antes.ativo,
                    }
                ),
                depois={
                    "nome": cliente.nome,
                    "documento": cliente.documento,
                    "limite_centavos": cliente.limite_credito,
                    "ativo": cliente.ativo,
                },
                motivo=motivo,
            )
        )


__all__ = ["ServicoClientes"]
