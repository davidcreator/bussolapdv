"""Casos de uso da matriz de permissões.

Quem manda aqui é uma regra só: **o Admin Master define o que cada perfil pode
fazer, e nada nessa tabela alcança o próprio Admin Master**. Isso evita dois
acidentes clássicos de sistema de permissão: (a) trancar o dono para fora da
própria instalação; (b) alguém conceder a si mesmo o poder de conceder.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..dominio.auditoria import AcaoAuditoria, EventoAuditoria
from ..dominio.erros import ErroValidacao
from ..dominio.usuario import (
    ACOES_SOMENTE_MASTER,
    PERMISSOES_PADRAO,
    Acao,
    Perfil,
    Usuario,
)
from .contexto import Contexto


@dataclass(frozen=True, slots=True)
class ResultadoPermissao:
    perfil: Perfil
    acao: Acao
    antes: bool
    depois: bool
    alterado: bool


class ServicoPermissoes:
    def __init__(self, contexto: Contexto) -> None:
        self.ctx = contexto

    # -- leitura ------------------------------------------------------------
    def efetivas(self, perfil: Perfil) -> frozenset[Acao]:
        return self.ctx.permissoes.efetivas(perfil)

    def matriz(self) -> dict[Perfil, dict[Acao, bool]]:
        return self.ctx.permissoes.matriz()

    def excecoes(self) -> list[dict[str, object]]:
        return self.ctx.permissoes.excecoes()

    def resumo(self) -> dict[str, dict[str, object]]:
        matriz = self.matriz()
        return {
            perfil.value: {
                "rotulo": perfil.rotulo,
                "nivel": perfil.nivel,
                "concedidas": sum(1 for permitido in matriz[perfil].values() if permitido),
                "total": len(Acao),
                "excecoes": sum(
                    1
                    for acao, permitido in matriz[perfil].items()
                    if permitido != (acao in PERMISSOES_PADRAO[perfil])
                ),
            }
            for perfil in Perfil
        }

    # -- escrita ------------------------------------------------------------
    def definir(
        self, ator: Usuario, perfil: Perfil, acao: Acao, permitido: bool
    ) -> ResultadoPermissao:
        ator.exigir(Acao.PERMISSAO_GERENCIAR)
        if perfil.eh_master:
            raise ErroValidacao(
                "O Admin Master tem acesso integral por definição; a matriz não se aplica a ele."
            )
        if acao in ACOES_SOMENTE_MASTER and permitido:
            raise ErroValidacao(
                f"A ação {acao.rotulo} é exclusiva do Admin Master e não pode ser delegada."
            )
        antes = acao in self.efetivas(perfil)
        if antes == permitido:
            return ResultadoPermissao(perfil, acao, antes, permitido, alterado=False)

        agora = self.ctx.agora()
        with self.ctx.em_transacao():
            self.ctx.permissoes.definir(
                perfil, acao, permitido, ator_id=ator.id, agora_iso=agora.isoformat()
            )
            self.ctx.auditoria.registrar(
                EventoAuditoria(
                    acao=AcaoAuditoria.PERMISSAO_ALTERADA,
                    criado_em_utc=agora,
                    data_negocio=self.ctx.relogio.data_negocio(),
                    ator_id=ator.id,
                    entidade="perfil",
                    entidade_id=perfil.value,
                    antes={"acao": acao.value, "permitido": antes},
                    depois={"acao": acao.value, "permitido": permitido},
                    motivo=f"Matriz de permissões: {perfil.rotulo} × {acao.rotulo}",
                    correlacao_id=f"permissao:{perfil.value}:{acao.value}",
                )
            )
        return ResultadoPermissao(perfil, acao, antes, permitido, alterado=True)

    def aplicar(
        self, ator: Usuario, mudancas: dict[tuple[Perfil, Acao], bool]
    ) -> list[ResultadoPermissao]:
        """Aplica um lote (a tela salva a matriz inteira de uma vez)."""
        ator.exigir(Acao.PERMISSAO_GERENCIAR)
        resultados: list[ResultadoPermissao] = []
        for (perfil, acao), permitido in mudancas.items():
            resultado = self.definir(ator, perfil, acao, permitido)
            if resultado.alterado:
                resultados.append(resultado)
        return resultados

    def restaurar_padrao(self, ator: Usuario) -> int:
        ator.exigir(Acao.PERMISSAO_GERENCIAR)
        agora = self.ctx.agora()
        excecoes = self.ctx.permissoes.excecoes()
        with self.ctx.em_transacao():
            removidas = self.ctx.permissoes.restaurar_padrao()
            self.ctx.auditoria.registrar(
                EventoAuditoria(
                    acao=AcaoAuditoria.PERMISSOES_RESTAURADAS,
                    criado_em_utc=agora,
                    data_negocio=self.ctx.relogio.data_negocio(),
                    ator_id=ator.id,
                    entidade="perfil",
                    antes={"excecoes": excecoes},
                    depois={"excecoes_removidas": removidas},
                    motivo="Restauração da matriz padrão de permissões",
                )
            )
        return removidas
