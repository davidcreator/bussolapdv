"""Fila local de vendas quando a rede da loja cai (ADR-036).

O problema que isto resolve: o caixa está no meio de uma venda, o servidor não
responde, e a alternativa seria dizer ao cliente "volte depois". A venda é
guardada **no próprio caixa** e reenviada quando a rede voltar.

O que torna o reenvio seguro é uma coisa que já existia: **chave de
idempotência**. Cada venda carrega uma chave gerada uma vez, na montagem do
pedido, e o servidor devolve a venda original se a chave repetir. Então reenviar
duas vezes não duplica nada — nem quando o servidor já gravou e só a resposta se
perdeu no caminho (o caso mais chato de todos).

Limites declarados, para ninguém se enganar:

* **só venda entra na fila.** Sangria, recebimento de crediário, cancelamento e
  cadastro exigem o servidor na hora: são operações em que o dinheiro ou a
  decisão não podem acontecer "depois", e o programa diz isso ao operador;
* **o estoque é conferido no reenvio**, não no momento da venda. Se o item
  acabou nesse meio-tempo, o servidor recusa, a venda fica na fila como
  **pendência com motivo** e alguém decide o que fazer (registrar a venda com
  autorização, ou descartar). Inventar saldo seria pior;
* **a venda pendente é do operador que a fez.** O reenvio exige que ele esteja
  logado no caixa: o servidor recusa identidade emprestada, e a fila não é
  porta para isso;
* **o cupom não sai na hora**. O comprovante é emitido quando a venda é aceita
  (e o operador pode reimprimir depois pelo número).
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..dominio.erros import ErroBussola
from ..infra.api.contrato import codificar, decodificar

NOME_DO_ARQUIVO = "vendas-pendentes.db"

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS vendas_pendentes (
    chave TEXT PRIMARY KEY,
    criada_em TEXT NOT NULL,
    operador_id TEXT NOT NULL,
    operador_login TEXT NOT NULL,
    terminal TEXT NOT NULL,
    carga TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDENTE',
    motivo TEXT NOT NULL DEFAULT '',
    tentativas INTEGER NOT NULL DEFAULT 0,
    ultima_tentativa TEXT NOT NULL DEFAULT ''
);
"""


@dataclass(frozen=True, slots=True)
class VendaPendente:
    chave: str
    criada_em: str
    operador_id: str
    operador_login: str
    terminal: str
    carga: dict
    status: str
    motivo: str
    tentativas: int
    ultima_tentativa: str

    @property
    def precisa_de_atencao(self) -> bool:
        return self.status == "RECUSADA"


class FilaDeVendas:
    """Depósito local (SQLite no caixa) das vendas que o servidor não recebeu."""

    def __init__(self, caminho: str | Path) -> None:
        self.caminho = Path(caminho)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.conexao = sqlite3.connect(str(self.caminho), isolation_level=None)
        self.conexao.row_factory = sqlite3.Row
        self.conexao.execute("PRAGMA journal_mode = WAL")
        self.conexao.executescript(_ESQUEMA)

    # -- ciclo de vida ------------------------------------------------------
    def fechar(self) -> None:
        self.conexao.close()

    def __enter__(self) -> FilaDeVendas:
        return self

    def __exit__(self, *_: object) -> None:
        self.fechar()

    # -- escrita ------------------------------------------------------------
    def enfileirar(
        self,
        *,
        solicitacao: Any,
        operador_id: str,
        operador_login: str,
        terminal: str,
        agora: datetime | None = None,
    ) -> VendaPendente:
        agora = agora or datetime.now(UTC)
        chave = str(getattr(solicitacao, "chave_idempotencia", "") or uuid.uuid4())
        carga = codificar(solicitacao)
        self.conexao.execute(
            """INSERT OR IGNORE INTO vendas_pendentes
               (chave, criada_em, operador_id, operador_login, terminal, carga)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                chave,
                agora.isoformat(timespec="seconds"),
                operador_id,
                operador_login,
                terminal,
                json.dumps(carga, ensure_ascii=False),
            ),
        )
        return self.obter(chave)

    def marcar_enviada(self, chave: str) -> None:
        self.conexao.execute("DELETE FROM vendas_pendentes WHERE chave = ?", (chave,))

    def marcar_recusada(self, chave: str, motivo: str, *, agora: datetime | None = None) -> None:
        agora = agora or datetime.now(UTC)
        self.conexao.execute(
            """UPDATE vendas_pendentes
                  SET status = 'RECUSADA', motivo = ?, tentativas = tentativas + 1,
                      ultima_tentativa = ?
                WHERE chave = ?""",
            (motivo[:500], agora.isoformat(timespec="seconds"), chave),
        )

    def registrar_tentativa(self, chave: str, *, agora: datetime | None = None) -> None:
        agora = agora or datetime.now(UTC)
        self.conexao.execute(
            """UPDATE vendas_pendentes
                  SET tentativas = tentativas + 1, ultima_tentativa = ?
                WHERE chave = ?""",
            (agora.isoformat(timespec="seconds"), chave),
        )

    def descartar(self, chave: str) -> bool:
        cursor = self.conexao.execute("DELETE FROM vendas_pendentes WHERE chave = ?", (chave,))
        return cursor.rowcount > 0

    # -- leitura ------------------------------------------------------------
    def _linha(self, linha: sqlite3.Row) -> VendaPendente:
        return VendaPendente(
            chave=linha["chave"],
            criada_em=linha["criada_em"],
            operador_id=linha["operador_id"],
            operador_login=linha["operador_login"],
            terminal=linha["terminal"],
            carga=json.loads(linha["carga"]),
            status=linha["status"],
            motivo=linha["motivo"],
            tentativas=int(linha["tentativas"]),
            ultima_tentativa=linha["ultima_tentativa"],
        )

    def obter(self, chave: str) -> VendaPendente:
        linha = self.conexao.execute(
            "SELECT * FROM vendas_pendentes WHERE chave = ?", (chave,)
        ).fetchone()
        if linha is None:
            raise ErroBussola(f"Venda pendente não encontrada: {chave}.")
        return self._linha(linha)

    def pendentes(self, *, incluir_recusadas: bool = True) -> list[VendaPendente]:
        sql = "SELECT * FROM vendas_pendentes"
        if not incluir_recusadas:
            sql += " WHERE status = 'PENDENTE'"
        sql += " ORDER BY criada_em"
        return [self._linha(linha) for linha in self.conexao.execute(sql)]

    def quantidade(self) -> int:
        linha = self.conexao.execute("SELECT COUNT(*) AS total FROM vendas_pendentes").fetchone()
        return int(linha["total"])


# -- reenvio ----------------------------------------------------------------


@dataclass
class ResultadoDoReenvio:
    enviadas: int = 0
    recusadas: int = 0
    continuam_pendentes: int = 0
    mensagens: tuple[str, ...] = ()

    @property
    def total(self) -> int:
        return self.enviadas + self.recusadas + self.continuam_pendentes


def reenviar(
    fila: FilaDeVendas,
    cliente: Any,
    *,
    solicitacao_tipo: Any,
    operador_id: str,
) -> ResultadoDoReenvio:
    """Tenta entregar as vendas guardadas, na ordem em que aconteceram.

    Não força nada: se o servidor recusar por regra (estoque, limite do cliente),
    a venda vira **pendência com motivo** e continua na fila. Quem decide o que
    fazer é a loja — reenviar em laço contra uma recusa de negócio só produziria
    log.
    """
    from ..dominio.erros import CredenciaisInvalidas
    from ..infra.api.cliente import ErroDeComunicacao

    enviadas = recusadas = pendentes = 0
    mensagens: list[str] = []
    for registro in fila.pendentes(incluir_recusadas=False):
        if registro.operador_id != operador_id:
            pendentes += 1
            mensagens.append(
                f"{registro.chave[:8]}: venda de {registro.operador_login}; "
                "só quem fez a venda pode reenviar."
            )
            continue
        try:
            solicitacao = decodificar(registro.carga, solicitacao_tipo)
            cliente.executar("pdv", "finalizar_venda", {"solicitacao": solicitacao})
        except CredenciaisInvalidas as exc:
            # Servidor reiniciado derruba as sessões (é o comportamento previsto).
            # Isto **não** é recusa da venda: o operador precisa entrar de novo.
            pendentes += 1
            mensagens.append(
                f"{registro.chave[:8]}: a sessão deste caixa venceu ({exc}). "
                "Entre de novo e reenvie."
            )
            break
        except ErroDeComunicacao as exc:
            pendentes += 1
            fila.registrar_tentativa(registro.chave)
            mensagens.append(f"{registro.chave[:8]}: servidor fora do ar de novo ({exc.mensagem}).")
            break  # rede caiu: não adianta insistir nas próximas agora
        except ErroBussola as exc:
            recusadas += 1
            fila.marcar_recusada(registro.chave, str(exc))
            mensagens.append(f"{registro.chave[:8]}: recusada — {exc}")
            continue
        else:
            fila.marcar_enviada(registro.chave)
            enviadas += 1
    return ResultadoDoReenvio(
        enviadas=enviadas,
        recusadas=recusadas,
        continuam_pendentes=pendentes,
        mensagens=tuple(mensagens),
    )


__all__ = [
    "NOME_DO_ARQUIVO",
    "FilaDeVendas",
    "ResultadoDoReenvio",
    "VendaPendente",
    "reenviar",
]
