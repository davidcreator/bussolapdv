"""Gestão de usuários respeitando a hierarquia.

Três travas que a interface não pode contornar porque vivem no serviço (e são
testadas): ninguém gerencia a si mesmo, ninguém cria ou promove alguém ao próprio
nível, e o último Admin Master ativo não pode ser desativado — a instalação
sempre tem um proprietário identificável.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..dominio.auditoria import AcaoAuditoria, EventoAuditoria
from ..dominio.erros import ErroConflito, ErroValidacao
from ..dominio.seguranca import gerar_hash, validar_senha, verificar_senha
from ..dominio.usuario import Acao, Perfil, Usuario
from .contexto import Contexto


@dataclass(frozen=True, slots=True)
class UsuarioResumo:
    id: str
    login: str
    nome: str
    perfil: Perfil
    ativo: bool
    criado_em: str
    permissoes: int
    bloqueado: bool

    @property
    def perfil_rotulo(self) -> str:
        return self.perfil.rotulo


class ServicoUsuarios:
    def __init__(self, contexto: Contexto) -> None:
        self.ctx = contexto

    # -- leitura ------------------------------------------------------------
    def listar(self, ator: Usuario) -> list[UsuarioResumo]:
        ator.exigir(Acao.USUARIO_GERENCIAR)
        linhas = self.ctx.conexao.execute(
            """SELECT id, login, nome, perfil, ativo, criado_em, bloqueado_ate
                 FROM usuarios ORDER BY
                 CASE perfil
                     WHEN 'ADMIN_MASTER' THEN 0
                     WHEN 'ADMIN' THEN 1
                     WHEN 'GERENTE' THEN 2
                     WHEN 'CONTABILIDADE' THEN 3
                     ELSE 4
                 END, nome"""
        ).fetchall()
        resumos: list[UsuarioResumo] = []
        for linha in linhas:
            perfil = Perfil(linha["perfil"])
            resumos.append(
                UsuarioResumo(
                    id=linha["id"],
                    login=linha["login"],
                    nome=linha["nome"],
                    perfil=perfil,
                    ativo=bool(linha["ativo"]),
                    criado_em=linha["criado_em"],
                    permissoes=len(self.ctx.permissoes.efetivas(perfil)),
                    bloqueado=linha["bloqueado_ate"] is not None,
                )
            )
        return resumos

    def perfis_disponiveis(self, ator: Usuario) -> list[Perfil]:
        """Somente perfis que o ator pode atribuir — a UI usa esta lista."""
        if not ator.pode(Acao.USUARIO_GERENCIAR):
            return []
        return [perfil for perfil in Perfil if ator.pode_receber_perfil(perfil)]

    def obter(self, usuario_id: str) -> Usuario:
        return self.ctx.usuarios.por_id(usuario_id)

    # -- escrita ------------------------------------------------------------
    def criar(
        self,
        ator: Usuario,
        *,
        login: str,
        nome: str,
        perfil: Perfil,
        senha: str,
    ) -> Usuario:
        ator.exigir(Acao.USUARIO_GERENCIAR)
        if perfil.eh_master:
            # A instalação tem um proprietário por vez: criar um segundo master
            # seria um caminho silencioso de escalada. Troca-se por transferência.
            raise ErroConflito(
                "A instalação tem um único Admin Master; use a transferência de propriedade."
            )
        if not ator.pode_receber_perfil(perfil):
            raise ErroValidacao(
                f"Você não pode criar um usuário de nível igual ou superior ao seu "
                f"({perfil.rotulo})."
            )
        validar_senha(senha)
        usuario = Usuario(
            login=login.strip(),
            nome=nome.strip(),
            perfil=perfil,
            senha_hash=gerar_hash(senha),
        )
        agora = self.ctx.agora()
        with self.ctx.em_transacao():
            self.ctx.usuarios.criar(usuario, criado_em=agora.isoformat(), criado_por=ator.id)
            self._auditar(
                AcaoAuditoria.USUARIO_CRIADO,
                ator,
                usuario,
                depois={"login": usuario.login, "perfil": perfil.value, "nome": usuario.nome},
                motivo=f"Criação de usuário {perfil.rotulo}",
            )
        return self.ctx.usuarios.por_id(usuario.id)

    def alterar_perfil(self, ator: Usuario, usuario_id: str, novo_perfil: Perfil) -> Usuario:
        alvo = self._alvo_gerenciavel(ator, usuario_id)
        if not ator.pode_receber_perfil(novo_perfil):
            raise ErroValidacao(
                f"Você não pode atribuir o perfil {novo_perfil.rotulo}: é igual ou superior ao seu."
            )
        if novo_perfil.eh_master:
            raise ErroValidacao("Para promover alguém a Admin Master use a transferência.")
        if alvo.perfil == novo_perfil:
            return alvo
        if alvo.eh_master:
            raise ErroValidacao("O perfil do Admin Master só muda por transferência de propriedade.")
        with self.ctx.em_transacao():
            self.ctx.usuarios.atualizar_perfil(usuario_id, novo_perfil)
            self._auditar(
                AcaoAuditoria.USUARIO_ALTERADO,
                ator,
                alvo,
                antes={"perfil": alvo.perfil.value},
                depois={"perfil": novo_perfil.value},
                motivo="Alteração de perfil",
            )
        return self.ctx.usuarios.por_id(usuario_id)

    def renomear(self, ator: Usuario, usuario_id: str, nome: str) -> Usuario:
        alvo = self._alvo_gerenciavel(ator, usuario_id)
        if not nome.strip():
            raise ErroValidacao("Nome é obrigatório.")
        with self.ctx.em_transacao():
            self.ctx.usuarios.atualizar_nome(usuario_id, nome)
            self._auditar(
                AcaoAuditoria.USUARIO_ALTERADO,
                ator,
                alvo,
                antes={"nome": alvo.nome},
                depois={"nome": nome.strip()},
                motivo="Alteração de nome",
            )
        return self.ctx.usuarios.por_id(usuario_id)

    def definir_ativo(self, ator: Usuario, usuario_id: str, ativo: bool) -> Usuario:
        alvo = self._alvo_gerenciavel(ator, usuario_id)
        if alvo.id == ator.id:
            raise ErroValidacao("Você não pode desativar o próprio acesso.")
        if not ativo and alvo.eh_master:
            raise ErroValidacao(
                "O Admin Master não pode ser desativado; transfira a propriedade primeiro."
            )
        if alvo.ativo == ativo:
            return alvo
        with self.ctx.em_transacao():
            self.ctx.usuarios.definir_ativo(usuario_id, ativo)
            self._auditar(
                AcaoAuditoria.USUARIO_REATIVADO if ativo else AcaoAuditoria.USUARIO_DESATIVADO,
                ator,
                alvo,
                antes={"ativo": alvo.ativo},
                depois={"ativo": ativo},
                motivo="Reativação de acesso" if ativo else "Desativação de acesso",
            )
        return self.ctx.usuarios.por_id(usuario_id)

    def redefinir_senha(self, ator: Usuario, usuario_id: str, nova_senha: str) -> None:
        alvo = self._alvo_gerenciavel(ator, usuario_id)
        validar_senha(nova_senha)
        with self.ctx.em_transacao():
            self.ctx.usuarios.atualizar_hash(usuario_id, gerar_hash(nova_senha))
            self._auditar(
                AcaoAuditoria.SENHA_REDEFINIDA,
                ator,
                alvo,
                motivo="Redefinição de senha por administrador",
            )

    def trocar_propria_senha(self, usuario: Usuario, senha_atual: str, nova_senha: str) -> None:
        """Autoatendimento: exige a senha atual, nunca só a sessão aberta."""
        if not verificar_senha(senha_atual, usuario.senha_hash):
            raise ErroValidacao("Senha atual incorreta.")
        validar_senha(nova_senha)
        if senha_atual == nova_senha:
            raise ErroValidacao("A nova senha deve ser diferente da atual.")
        with self.ctx.em_transacao():
            self.ctx.usuarios.atualizar_hash(usuario.id, gerar_hash(nova_senha))
            self._auditar(
                AcaoAuditoria.SENHA_REDEFINIDA,
                usuario,
                usuario,
                motivo="Troca da própria senha",
            )

    def transferir_propriedade(
        self, ator: Usuario, *, usuario_id: str, senha_do_ator: str
    ) -> tuple[Usuario, Usuario]:
        """Passa o bastão do Admin Master, com senha do atual e registro na trilha.

        O master atual é rebaixado a Admin (não é excluído: o histórico de vendas
        e autorizações continua apontando para ele) e o novo assume o nível 100.
        """
        if not ator.eh_master:
            raise ErroValidacao("Somente o Admin Master transfere a propriedade.")
        if not verificar_senha(senha_do_ator, ator.senha_hash):
            raise ErroValidacao("Senha do Admin Master incorreta.")
        if usuario_id == ator.id:
            raise ErroValidacao("Escolha outro usuário para receber a propriedade.")
        novo = self.ctx.usuarios.por_id(usuario_id)
        if not novo.ativo:
            raise ErroValidacao("O novo Admin Master precisa estar ativo.")
        if novo.perfil.eh_master:
            return ator, novo
        agora = self.ctx.agora()
        with self.ctx.em_transacao():
            self.ctx.usuarios.atualizar_perfil(ator.id, Perfil.ADMIN)
            self.ctx.usuarios.atualizar_perfil(novo.id, Perfil.ADMIN_MASTER)
            self.ctx.auditoria.registrar(
                EventoAuditoria(
                    acao=AcaoAuditoria.MASTER_TRANSFERIDO,
                    criado_em_utc=agora,
                    data_negocio=self.ctx.relogio.data_negocio(),
                    ator_id=ator.id,
                    entidade="usuario",
                    entidade_id=novo.id,
                    antes={"master_anterior": ator.login, "perfil_anterior": novo.perfil.value},
                    depois={"master_atual": novo.login, "perfil_anterior_dono": "ADMIN"},
                    motivo="Transferência de propriedade da instalação",
                )
            )
        return self.ctx.usuarios.por_id(ator.id), self.ctx.usuarios.por_id(novo.id)

    # -- apoio --------------------------------------------------------------
    def _alvo_gerenciavel(self, ator: Usuario, usuario_id: str) -> Usuario:
        ator.exigir(Acao.USUARIO_GERENCIAR)
        alvo = self.ctx.usuarios.por_id(usuario_id)
        if ator.id == alvo.id:
            raise ErroValidacao("Use os dados da própria conta para alterar a si mesmo.")
        if not ator.pode_gerenciar(alvo):
            raise ErroValidacao(
                f"O perfil {alvo.perfil.rotulo} não está sob sua hierarquia."
            )
        return alvo

    def _auditar(
        self,
        acao: AcaoAuditoria,
        ator: Usuario,
        alvo: Usuario,
        *,
        antes: dict[str, object] | None = None,
        depois: dict[str, object] | None = None,
        motivo: str = "",
    ) -> None:
        self.ctx.auditoria.registrar(
            EventoAuditoria(
                acao=acao,
                criado_em_utc=self.ctx.agora(),
                data_negocio=self.ctx.relogio.data_negocio(),
                ator_id=ator.id,
                entidade="usuario",
                entidade_id=alvo.id,
                antes=antes,
                depois=depois,
                motivo=motivo,
            )
        )
