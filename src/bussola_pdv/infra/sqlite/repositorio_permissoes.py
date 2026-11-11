"""Persistência da matriz de permissões por perfil.

Regra de leitura: **ausência de linha = padrão do código**. Só o que o Admin
Master mudou fica gravado, o que torna a auditoria da matriz curta e legível
(dá para listar exatamente as exceções aprovadas).
"""

from __future__ import annotations

import sqlite3

from ...dominio.usuario import PERMISSOES_PADRAO, Acao, Perfil
from .base import RepositorioBase


class PermissaoRepositorio(RepositorioBase):
    def _concessoes(self) -> dict[Perfil, dict[Acao, bool]]:
        resultado: dict[Perfil, dict[Acao, bool]] = {}
        for linha in self.conexao.execute(
            "SELECT perfil, acao, permitido FROM permissoes_perfil"
        ):
            try:
                perfil = Perfil(linha["perfil"])
                acao = Acao(linha["acao"])
            except ValueError:  # perfil/ação desconhecida de versão futura: ignora
                continue
            resultado.setdefault(perfil, {})[acao] = bool(linha["permitido"])
        return resultado

    def efetivas(self, perfil: Perfil) -> frozenset[Acao]:
        """Permissões válidas hoje: padrão do código, sobreposto pelo banco."""
        if perfil.eh_master:  # master nunca depende de tabela
            return frozenset(Acao)
        efetivas = set(PERMISSOES_PADRAO[perfil])
        for acao, permitido in self._concessoes().get(perfil, {}).items():
            if permitido:
                efetivas.add(acao)
            else:
                efetivas.discard(acao)
        return frozenset(efetivas)

    def matriz(self) -> dict[Perfil, dict[Acao, bool]]:
        """Matriz completa perfil × ação, já resolvida (padrão + exceções)."""
        return {perfil: {acao: acao in self.efetivas(perfil) for acao in Acao} for perfil in Perfil}

    def excecoes(self) -> list[dict[str, object]]:
        """Somente as linhas que divergem do padrão — usado na tela e na auditoria."""
        linhas: list[dict[str, object]] = []
        for perfil, concessoes in self._concessoes().items():
            for acao, permitido in concessoes.items():
                padrao = acao in PERMISSOES_PADRAO.get(perfil, frozenset())
                if permitido != padrao:
                    linhas.append(
                        {
                            "perfil": perfil.value,
                            "perfil_rotulo": perfil.rotulo,
                            "acao": acao.value,
                            "acao_rotulo": acao.rotulo,
                            "permitido": permitido,
                            "padrao": padrao,
                        }
                    )
        return sorted(linhas, key=lambda item: (str(item["perfil"]), str(item["acao"])))

    def definir(
        self,
        perfil: Perfil,
        acao: Acao,
        permitido: bool,
        *,
        ator_id: str,
        agora_iso: str,
    ) -> None:
        self.conexao.execute(
            """INSERT INTO permissoes_perfil (perfil, acao, permitido, atualizado_em, atualizado_por)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT (perfil, acao) DO UPDATE SET
                   permitido = excluded.permitido,
                   atualizado_em = excluded.atualizado_em,
                   atualizado_por = excluded.atualizado_por""",
            (perfil.value, acao.value, int(permitido), agora_iso, ator_id),
        )

    def restaurar_padrao(self) -> int:
        cursor = self.conexao.execute("DELETE FROM permissoes_perfil")
        return int(cursor.rowcount or 0)

    def contar(self) -> int:
        linha = self.conexao.execute("SELECT COUNT(*) FROM permissoes_perfil").fetchone()
        return int(linha[0])


def permissoes_do_usuario(
    conexao: sqlite3.Connection, perfil: Perfil
) -> frozenset[Acao]:
    """Atalho usado pelo repositório de usuários ao materializar um ``Usuario``."""
    return PermissaoRepositorio(conexao).efetivas(perfil)
