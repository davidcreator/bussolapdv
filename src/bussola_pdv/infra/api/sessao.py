"""Sessões do terminal (modo remoto, ADR-036).

Por que sessão e não senha a cada chamada: o terminal é um computador da loja
com o operador logado; mandar login e senha em cada venda multiplicaria o
segredo na rede e no log. O terminal autentica **uma vez** (`POST /v1/sessao`),
recebe um token opaco de sessão, e cada chamada leva só esse token.

O que a sessão **não** é: um cookie de navegador. Ela vive na memória do
servidor, expira (12 h por padrão), e o servidor recusa token vencido ou
desconhecido. Reiniciar o servidor derruba todas — e o terminal refaz o login,
que é o comportamento previsível numa loja.

Autorizador não é sessão. Quem autoriza uma exceção (desconto, sangria,
cancelamento) digita a própria senha no terminal e o servidor **verifica** essa
credencial na hora do pedido; nada de o terminal afirmar "o gerente autorizou".
"""

from __future__ import annotations

import secrets
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

#: Validade de uma sessão de terminal. Um turno de loja cabe com folga.
VALIDADE_PADRAO = timedelta(hours=12)


@dataclass(frozen=True, slots=True)
class Sessao:
    token: str
    usuario_id: str
    terminal: str
    criada_em: datetime
    expira_em: datetime

    def vencida(self, agora: datetime) -> bool:
        return agora >= self.expira_em


@dataclass
class ArmazemDeSessoes:
    """Sessões em memória, com validade e remoção na leitura.

    Fica fora do banco de propósito: sessão de terminal não é dado da loja, e
    guardá-la em disco criaria um segredo a mais para fazer backup e proteger.
    """

    validade: timedelta = VALIDADE_PADRAO
    agora: Callable[[], datetime] = lambda: datetime.now(UTC)
    _sessoes: dict[str, Sessao] = field(default_factory=dict, init=False, repr=False)
    _trava: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def criar(self, usuario_id: str, terminal: str) -> Sessao:
        agora = self.agora()
        sessao = Sessao(
            token=secrets.token_urlsafe(32),
            usuario_id=usuario_id,
            terminal=terminal,
            criada_em=agora,
            expira_em=agora + self.validade,
        )
        with self._trava:
            self._varrer(agora)
            self._sessoes[sessao.token] = sessao
        return sessao

    def obter(self, token: str) -> Sessao | None:
        if not token:
            return None
        agora = self.agora()
        with self._trava:
            sessao = self._sessoes.get(token)
            if sessao is None:
                return None
            if sessao.vencida(agora):
                self._sessoes.pop(token, None)
                return None
            return sessao

    def encerrar(self, token: str) -> bool:
        with self._trava:
            return self._sessoes.pop(token, None) is not None

    def encerrar_do_usuario(self, usuario_id: str) -> int:
        """Derruba as sessões de um usuário (usado ao desativar/redefinir senha)."""
        with self._trava:
            alvos = [t for t, s in self._sessoes.items() if s.usuario_id == usuario_id]
            for token in alvos:
                self._sessoes.pop(token, None)
        return len(alvos)

    def quantidade(self) -> int:
        agora = self.agora()
        with self._trava:
            self._varrer(agora)
            return len(self._sessoes)

    def _varrer(self, agora: datetime) -> None:
        for token in [t for t, s in self._sessoes.items() if s.vencida(agora)]:
            self._sessoes.pop(token, None)


__all__ = ["VALIDADE_PADRAO", "ArmazemDeSessoes", "Sessao"]
