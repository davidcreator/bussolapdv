"""Hash de senha e política de bloqueio por tentativas.

Decisão: Argon2id (``argon2-cffi``) com parâmetros explícitos e salt aleatório
por senha. Nenhum log, mensagem ou evento de auditoria recebe a senha, o PIN ou
o hash. O hash só sai do banco para verificação.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from .erros import CredenciaisInvalidas, ErroValidacao, UsuarioBloqueado

try:  # pragma: no cover - depende do ambiente
    from argon2 import PasswordHasher
    from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

    _ARGON2_DISPONIVEL = True
except ModuleNotFoundError:  # pragma: no cover
    _ARGON2_DISPONIVEL = False
    PasswordHasher = None  # type: ignore[assignment,misc]


MEMORIA_KIB = 64 * 1024  # 64 MiB
ITERACOES = 3
PARALELISMO = 4

_HASHER: PasswordHasher | None

if _ARGON2_DISPONIVEL:  # pragma: no cover - trivial
    _HASHER = PasswordHasher(
        time_cost=ITERACOES,
        memory_cost=MEMORIA_KIB,
        parallelism=PARALELISMO,
        hash_len=32,
        salt_len=16,
    )
else:  # pragma: no cover
    _HASHER = None


class Argon2Indisponivel(RuntimeError):
    """Erro fatal de ambiente: o app não deve rodar sem derivação forte."""


def _hasher() -> PasswordHasher:
    if _HASHER is None:
        raise Argon2Indisponivel(
            "argon2-cffi não está instalado. Instale as dependências do projeto; "
            "não substitua por hash simples."
        )
    return _HASHER


def gerar_hash(senha: str) -> str:
    """Gera hash Argon2id com salt aleatório embutido no formato PHC."""
    validar_senha(senha)
    return _hasher().hash(senha)


def verificar_senha(senha: str, hash_armazenado: str) -> bool:
    """Comparação em tempo constante feita pelo argon2. Não levanta em senha errada."""
    try:
        return bool(_hasher().verify(hash_armazenado, senha))
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def precisa_rehash(hash_armazenado: str) -> bool:
    """Indica hash gerado com parâmetros antigos (deve ser regravado no login)."""
    try:
        return bool(_hasher().check_needs_rehash(hash_armazenado))
    except Exception:  # pragma: no cover - hash corrompido
        return True


def validar_senha(senha: str) -> None:
    """Política mínima: 8 caracteres e não apenas um caractere repetido."""
    if senha is None or len(senha) < 8:
        raise ErroValidacao("Senha deve ter ao menos 8 caracteres.")
    if len(set(senha)) == 1:
        raise ErroValidacao("Senha não pode ser um único caractere repetido.")


def validar_pin(pin: str) -> None:
    """PIN é numérico de 4 a 8 dígitos; nunca é armazenado em texto."""
    if not re.fullmatch(r"\d{4,8}", str(pin or "")):
        raise ErroValidacao("PIN deve ter de 4 a 8 dígitos numéricos.")


@dataclass(frozen=True, slots=True)
class PoliticaBloqueio:
    maximo_tentativas: int = 5
    duracao_bloqueio: timedelta = timedelta(minutes=5)

    def bloqueado_ate(self, agora: datetime, tentativas: int) -> datetime | None:
        if tentativas >= self.maximo_tentativas:
            return agora + self.duracao_bloqueio
        return None

    def conferir(self, agora: datetime, bloqueado_ate: datetime | None) -> None:
        if bloqueado_ate is not None and bloqueado_ate > agora:
            resta = int((bloqueado_ate - agora).total_seconds() // 60) + 1
            raise UsuarioBloqueado(
                f"Usuário bloqueado por tentativas inválidas. Tente novamente em {resta} minuto(s)."
            )


def autenticar(
    *,
    senha: str,
    hash_armazenado: str,
    ativo: bool,
    tentativas_falhas: int,
    bloqueado_ate: datetime | None,
    agora: datetime,
    politica: PoliticaBloqueio = PoliticaBloqueio(),
) -> None:
    """Valida credenciais e devolve erro genérico quando não confere.

    Mensagem genérica evita revelar se o login existe. O bloqueio é conferido
    antes da comparação da senha.
    """
    politica.conferir(agora, bloqueado_ate)
    if not ativo:
        raise CredenciaisInvalidas("Usuário inativo ou credenciais inválidas.")
    if not verificar_senha(senha, hash_armazenado):
        raise CredenciaisInvalidas("Login ou senha inválidos.")
