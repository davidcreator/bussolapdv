"""Login, bloqueio por tentativas e criação do administrador inicial."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from ..dominio.auditoria import AcaoAuditoria, EventoAuditoria
from ..dominio.erros import CredenciaisInvalidas, ErroValidacao
from ..dominio.seguranca import (
    PoliticaBloqueio,
    autenticar,
    gerar_hash,
    precisa_rehash,
    validar_pin,
    validar_senha,
    verificar_senha,
)
from ..dominio.usuario import Acao, Perfil, Usuario
from .contexto import Contexto


@dataclass(frozen=True, slots=True)
class ResultadoLogin:
    usuario: Usuario
    rehash_aplicado: bool = False


class ServicoAutenticacao:
    def __init__(self, contexto: Contexto) -> None:
        self.ctx = contexto

    def _politica(self) -> PoliticaBloqueio:
        return PoliticaBloqueio(
            maximo_tentativas=self.ctx.parametros.obter_int("seguranca.maximo_tentativas"),
            duracao_bloqueio=timedelta(
                minutes=self.ctx.parametros.obter_int("seguranca.bloqueio_minutos")
            ),
        )

    def criar_usuario(
        self,
        *,
        login: str,
        nome: str,
        senha: str,
        perfil: Perfil,
        autor: Usuario | None = None,
        criar_admin_inicial: bool = False,
    ) -> Usuario:
        """Cria usuário com hash Argon2id. Não existe caminho para senha em texto.

        Fora do bootstrap (`criar_admin_inicial`), exige autor com permissão de
        gerenciar usuários.
        """
        if autor is not None:
            autor.exigir(Acao.USUARIO_GERENCIAR)
        elif not criar_admin_inicial:
            raise CredenciaisInvalidas("Criação de usuário exige administrador autenticado.")
        if criar_admin_inicial and not perfil.eh_master:
            raise ErroValidacao(
                "O usuário inicial deve ser o Admin Master (proprietário da instalação)."
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
            criado = self.ctx.usuarios.criar(usuario, criado_em=agora.isoformat())
            if autor is not None:
                self.ctx.auditoria.registrar(
                    EventoAuditoria(
                        acao=AcaoAuditoria.PARAMETRO_ALTERADO,
                        criado_em_utc=agora,
                        data_negocio=self.ctx.relogio.data_negocio(),
                        ator_id=autor.id,
                        entidade="usuario",
                        entidade_id=criado.id,
                        depois={"login": criado.login, "perfil": criado.perfil.value},
                        motivo="Criação de usuário",
                    )
                )
        return criado

    def criar_pin_usuario(self, *, usuario_id: str, pin: str, autor: Usuario) -> None:
        """PIN usa a mesma derivação Argon2id da senha (nunca texto simples)."""
        autor.exigir(Acao.USUARIO_GERENCIAR)
        validar_pin(pin)
        with self.ctx.em_transacao():
            self.ctx.usuarios.atualizar_hash(usuario_id, gerar_hash(pin))

    def entrar(self, login: str, senha: str) -> ResultadoLogin:
        agora = self.ctx.agora()
        politica = self._politica()
        try:
            usuario = self.ctx.usuarios.por_login(login)
        except Exception as exc:
            # Mesma mensagem de senha errada: não revela se o login existe.
            raise CredenciaisInvalidas("Login ou senha inválidos.") from exc

        try:
            autenticar(
                senha=senha,
                hash_armazenado=usuario.senha_hash,
                ativo=usuario.ativo,
                tentativas_falhas=usuario.tentativas_falhas,
                bloqueado_ate=usuario.bloqueado_ate,
                agora=agora,
                politica=politica,
            )
        except CredenciaisInvalidas:
            with self.ctx.em_transacao():
                self.ctx.usuarios.registrar_falha(usuario.id, agora=agora, politica=politica)
            raise
        except Exception:
            raise

        rehash = precisa_rehash(usuario.senha_hash)
        with self.ctx.em_transacao():
            self.ctx.usuarios.limpar_falhas(usuario.id)
            if rehash:
                self.ctx.usuarios.atualizar_hash(usuario.id, gerar_hash(senha))
            self.ctx.auditoria.registrar(
                EventoAuditoria(
                    acao=AcaoAuditoria.SESSAO_INICIADA,
                    criado_em_utc=agora,
                    data_negocio=self.ctx.relogio.data_negocio(),
                    ator_id=usuario.id,
                    entidade="usuario",
                    entidade_id=usuario.id,
                )
            )
        return ResultadoLogin(usuario=usuario, rehash_aplicado=rehash)

    def autorizar(self, login: str, senha: str, acao: Acao) -> Usuario:
        """Autentica um autorizador e confirma que ele pode executar a ação.

        É esta função que substitui o "digite o nome do gerente" do protótipo.
        """
        autorizador = self.entrar(login, senha).usuario
        autorizador.exigir(acao)
        return autorizador

    def verificar_senha_usuario(self, usuario: Usuario, senha: str) -> bool:
        return verificar_senha(senha, usuario.senha_hash)
