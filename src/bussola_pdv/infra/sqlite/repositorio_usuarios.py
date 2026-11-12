"""Repositório de usuários, tentativas de login e parâmetros do sistema."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import ClassVar

from ...dominio.erros import ErroConflito, ErroNaoEncontrado
from ...dominio.seguranca import PoliticaBloqueio
from ...dominio.usuario import Perfil, Usuario
from .base import RepositorioBase
from .repositorio_permissoes import PermissaoRepositorio

COLUNAS = (
    "id, login, nome, perfil, senha_hash, ativo, tentativas_falhas, bloqueado_ate, criado_por"
)


class UsuarioRepositorio(RepositorioBase):
    def criar(
        self, usuario: Usuario, *, criado_em: str, criado_por: str | None = None
    ) -> Usuario:
        try:
            self.conexao.execute(
                """INSERT INTO usuarios (id, login, nome, perfil, senha_hash, ativo,
                                         tentativas_falhas, bloqueado_ate, criado_em, criado_por)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    usuario.id,
                    usuario.login,
                    usuario.nome,
                    usuario.perfil.value,
                    usuario.senha_hash,
                    int(usuario.ativo),
                    usuario.tentativas_falhas,
                    self.iso(usuario.bloqueado_ate) if usuario.bloqueado_ate else None,
                    criado_em,
                    criado_por,
                ),
            )
        except Exception as exc:
            if "UNIQUE" in str(exc).upper():
                raise ErroConflito(f"Login {usuario.login!r} já existe.") from exc
            raise
        return usuario

    def _para_usuario(self, linha: sqlite3.Row) -> Usuario:
        perfil = Perfil(linha["perfil"])
        return Usuario(
            id=linha["id"],
            login=linha["login"],
            nome=linha["nome"],
            perfil=perfil,
            senha_hash=linha["senha_hash"],
            ativo=bool(linha["ativo"]),
            tentativas_falhas=int(linha["tentativas_falhas"]),
            bloqueado_ate=self.instante(linha["bloqueado_ate"]),
            # Permissões resolvidas no carregamento: quem usa o usuário não
            # precisa consultar a matriz em cada `exigir()`.
            permissoes_concedidas=PermissaoRepositorio(self.conexao).efetivas(perfil),
        )

    def por_login(self, login: str) -> Usuario:
        linha = self.conexao.execute(
            f"SELECT {COLUNAS} FROM usuarios WHERE login = ? COLLATE NOCASE", (login,)
        ).fetchone()
        if linha is None:
            raise ErroNaoEncontrado("Usuário não encontrado.")
        return self._para_usuario(linha)

    def por_id(self, usuario_id: str) -> Usuario:
        linha = self.conexao.execute(
            f"SELECT {COLUNAS} FROM usuarios WHERE id = ?", (usuario_id,)
        ).fetchone()
        if linha is None:
            raise ErroNaoEncontrado("Usuário não encontrado.")
        return self._para_usuario(linha)

    def listar(self) -> list[Usuario]:
        return [
            self._para_usuario(linha)
            for linha in self.conexao.execute(f"SELECT {COLUNAS} FROM usuarios ORDER BY nome")
        ]

    def registrar_falha(
        self, usuario_id: str, *, agora: datetime, politica: PoliticaBloqueio
    ) -> int:
        """Incrementa tentativas e aplica bloqueio temporário quando atinge o limite."""
        linha = self.conexao.execute(
            "SELECT tentativas_falhas FROM usuarios WHERE id = ?", (usuario_id,)
        ).fetchone()
        if linha is None:
            raise ErroNaoEncontrado("Usuário não encontrado.")
        tentativas = int(linha[0]) + 1
        bloqueado = politica.bloqueado_ate(agora, tentativas)
        self.conexao.execute(
            "UPDATE usuarios SET tentativas_falhas = ?, bloqueado_ate = ? WHERE id = ?",
            (tentativas, self.iso(bloqueado) if bloqueado else None, usuario_id),
        )
        return tentativas

    def limpar_falhas(self, usuario_id: str) -> None:
        self.conexao.execute(
            "UPDATE usuarios SET tentativas_falhas = 0, bloqueado_ate = NULL WHERE id = ?",
            (usuario_id,),
        )

    def atualizar_hash(self, usuario_id: str, senha_hash: str) -> None:
        self.conexao.execute(
            "UPDATE usuarios SET senha_hash = ?, tentativas_falhas = 0, bloqueado_ate = NULL WHERE id = ?",
            (senha_hash, usuario_id),
        )

    def definir_ativo(self, usuario_id: str, ativo: bool) -> None:
        self.conexao.execute("UPDATE usuarios SET ativo = ? WHERE id = ?", (int(ativo), usuario_id))

    def atualizar_perfil(self, usuario_id: str, perfil: Perfil) -> None:
        self.conexao.execute(
            "UPDATE usuarios SET perfil = ? WHERE id = ?", (perfil.value, usuario_id)
        )

    def atualizar_nome(self, usuario_id: str, nome: str) -> None:
        if not nome.strip():
            raise ErroConflito("Nome do usuário é obrigatório.")
        self.conexao.execute("UPDATE usuarios SET nome = ? WHERE id = ?", (nome.strip(), usuario_id))

    def masters_ativos(self) -> list[Usuario]:
        return [
            self._para_usuario(linha)
            for linha in self.conexao.execute(
                f"SELECT {COLUNAS} FROM usuarios WHERE perfil = 'ADMIN_MASTER' AND ativo = 1"
            )
        ]

    def contar_por_perfil(self) -> dict[str, int]:
        return {
            linha["perfil"]: int(linha["total"])
            for linha in self.conexao.execute(
                "SELECT perfil, COUNT(*) AS total FROM usuarios GROUP BY perfil"
            )
        }


class ParametroRepositorio(RepositorioBase):
    """Parâmetros de negócio persistidos como texto, com conversão tipada."""

    PADROES: ClassVar[dict[str, str]] = {
        "empresa.nome": "Loja de Demonstração",
        "empresa.cnpj": "",
        "empresa.regime_tributario": "SIMPLES",
        "operacao.modo": "TESTE",
        "operacao.fuso": "America/Sao_Paulo",
        "desconto.limite_operador_bp": "500",
        "desconto.limite_gerente_bp": "1500",
        "desconto.limite_maximo_bp": "10000",
        "venda.exigir_confirmacao_eletronica": "0",
        "crediario.dias_bloqueio_atraso": "30",
        "crediario.maximo_parcelas": "12",
        "caixa.limite_diferenca_centavos": "500",
        "seguranca.maximo_tentativas": "5",
        "seguranca.bloqueio_minutos": "5",
        # Impressão (v0.8.0): bobina de 80 mm é o que a maioria das lojas usa.
        "impressao.motor": "SISTEMA",
        "impressao.impressora": "",
        "impressao.papel": "BOBINA_80",
        "impressao.copias": "1",
        "impressao.cortar_papel": "1",
        "impressao.abrir_gaveta": "0",
        "impressao.codigo_de_barras": "1",
        "impressao.imprimir_automatico": "0",
        # Ajuda (v0.10.0): preferência de interface, não regra de negócio.
        # `guiado` liga a faixa do mentor; `versao` guarda qual versão do guia o
        # operador já viu, para o tour não reaparecer toda vez que o PDV abre.
        "ajuda.guiado": "1",
        "ajuda.versao": "0",
    }

    def obter(self, chave: str) -> str:
        linha = self.conexao.execute("SELECT valor FROM parametros WHERE chave = ?", (chave,)).fetchone()
        if linha is not None:
            return str(linha[0])
        if chave in self.PADROES:
            return self.PADROES[chave]
        raise ErroNaoEncontrado(f"Parâmetro desconhecido: {chave}")

    def obter_int(self, chave: str) -> int:
        return int(self.obter(chave))

    def obter_bool(self, chave: str) -> bool:
        return self.obter(chave).strip() in {"1", "true", "True", "S", "SIM"}

    def definir(self, chave: str, valor: str, *, agora_iso: str) -> None:
        self.conexao.execute(
            """INSERT INTO parametros (chave, valor, atualizado_em) VALUES (?, ?, ?)
               ON CONFLICT (chave) DO UPDATE SET valor = excluded.valor,
                                                 atualizado_em = excluded.atualizado_em""",
            (chave, str(valor), agora_iso),
        )

    def por_prefixo(self, prefixo: str) -> dict[str, str]:
        valores = {chave: valor for chave, valor in self.PADROES.items() if chave.startswith(prefixo)}
        for linha in self.conexao.execute(
            "SELECT chave, valor FROM parametros WHERE chave LIKE ?", (f"{prefixo}%",)
        ):
            valores[linha["chave"]] = linha["valor"]
        return valores

    def definir_varios(self, valores: dict[str, str], *, agora_iso: str) -> None:
        for chave, valor in valores.items():
            self.definir(chave, valor, agora_iso=agora_iso)

    def remover(self, chaves: list[str]) -> int:
        total = 0
        for chave in chaves:
            cursor = self.conexao.execute("DELETE FROM parametros WHERE chave = ?", (chave,))
            total += int(cursor.rowcount or 0)
        return total

    def todos(self) -> dict[str, str]:
        valores = dict(self.PADROES)
        for linha in self.conexao.execute("SELECT chave, valor FROM parametros"):
            valores[linha["chave"]] = linha["valor"]
        return valores
