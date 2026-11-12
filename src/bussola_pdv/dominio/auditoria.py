"""Trilha de auditoria append-only com encadeamento de hash.

O modelo da aplicação proíbe alteração e exclusão (garantido também por triggers
no SQLite). O encadeamento SHA-256 permite detectar edição posterior feita por
quem tem acesso ao arquivo — mas **não** torna o arquivo imutável: um
administrador do sistema pode reescrever a base inteira. Essa limitação está
documentada em docs/DECISOES.md e deve ser compensada com backup externo.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class AcaoAuditoria(StrEnum):
    SESSAO_INICIADA = "SESSAO_INICIADA"
    SESSAO_ENCERRADA = "SESSAO_ENCERRADA"
    TURNO_ABERTO = "TURNO_ABERTO"
    TURNO_FECHADO = "TURNO_FECHADO"
    SANGRIA = "SANGRIA"
    SUPRIMENTO = "SUPRIMENTO"
    VENDA_FINALIZADA = "VENDA_FINALIZADA"
    VENDA_CANCELADA = "VENDA_CANCELADA"
    PAGAMENTO_CONFIRMADO = "PAGAMENTO_CONFIRMADO"
    DESCONTO_AUTORIZADO = "DESCONTO_AUTORIZADO"
    ESTOQUE_NEGATIVO_AUTORIZADO = "ESTOQUE_NEGATIVO_AUTORIZADO"
    AJUSTE_ESTOQUE = "AJUSTE_ESTOQUE"
    ENTRADA_REGISTRADA = "ENTRADA_REGISTRADA"
    TITULO_RECEBIDO = "TITULO_RECEBIDO"
    PRODUTO_ALTERADO = "PRODUTO_ALTERADO"
    CLIENTE_ALTERADO = "CLIENTE_ALTERADO"
    PARAMETRO_ALTERADO = "PARAMETRO_ALTERADO"
    FECHAMENTO_GERADO = "FECHAMENTO_GERADO"
    BACKUP_EXECUTADO = "BACKUP_EXECUTADO"
    BACKUP_RESTAURADO = "BACKUP_RESTAURADO"
    USUARIO_CRIADO = "USUARIO_CRIADO"
    USUARIO_ALTERADO = "USUARIO_ALTERADO"
    USUARIO_DESATIVADO = "USUARIO_DESATIVADO"
    USUARIO_REATIVADO = "USUARIO_REATIVADO"
    SENHA_REDEFINIDA = "SENHA_REDEFINIDA"
    MASTER_TRANSFERIDO = "MASTER_TRANSFERIDO"
    PERMISSAO_ALTERADA = "PERMISSAO_ALTERADA"
    PERMISSOES_RESTAURADAS = "PERMISSOES_RESTAURADAS"
    MARCA_ALTERADA = "MARCA_ALTERADA"
    TEMA_ALTERADO = "TEMA_ALTERADO"
    MANUTENCAO_EXECUTADA = "MANUTENCAO_EXECUTADA"
    DADOS_EXPORTADOS = "DADOS_EXPORTADOS"


@dataclass(frozen=True, slots=True)
class EventoAuditoria:
    acao: AcaoAuditoria
    criado_em_utc: datetime
    data_negocio: str
    ator_id: str | None = None
    entidade: str = ""
    entidade_id: str = ""
    antes: dict | None = None
    depois: dict | None = None
    motivo: str = ""
    autorizador_id: str | None = None
    origem: str = "DESKTOP"
    correlacao_id: str = ""
    sequencia: int = 0
    hash_anterior: str = ""
    hash: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        if self.criado_em_utc.tzinfo is None:
            raise ValueError("Evento de auditoria exige instante UTC timezone-aware.")

    def carga_canonica(self) -> str:
        """Serialização estável usada no hash (ordem fixa, UTF-8, sem espaços extras)."""
        corpo = {
            "sequencia": self.sequencia,
            "acao": self.acao.value,
            "criado_em_utc": self.criado_em_utc.isoformat(),
            "data_negocio": self.data_negocio,
            "ator_id": self.ator_id,
            "entidade": self.entidade,
            "entidade_id": self.entidade_id,
            "antes": self.antes,
            "depois": self.depois,
            "motivo": self.motivo,
            "autorizador_id": self.autorizador_id,
            "origem": self.origem,
            "correlacao_id": self.correlacao_id,
            "hash_anterior": self.hash_anterior,
        }
        return json.dumps(corpo, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def calcular_hash(self) -> str:
        return hashlib.sha256(self.carga_canonica().encode("utf-8")).hexdigest()

    def com_hash(self) -> EventoAuditoria:
        return EventoAuditoria(
            acao=self.acao,
            criado_em_utc=self.criado_em_utc,
            data_negocio=self.data_negocio,
            ator_id=self.ator_id,
            entidade=self.entidade,
            entidade_id=self.entidade_id,
            antes=self.antes,
            depois=self.depois,
            motivo=self.motivo,
            autorizador_id=self.autorizador_id,
            origem=self.origem,
            correlacao_id=self.correlacao_id,
            sequencia=self.sequencia,
            hash_anterior=self.hash_anterior,
            hash=self.calcular_hash(),
        )


@dataclass(frozen=True, slots=True)
class ResultadoVerificacao:
    eventos: int
    integro: bool
    primeira_divergencia: int | None = None

    @property
    def mensagem(self) -> str:
        if self.integro:
            return f"Cadeia íntegra em {self.eventos} eventos."
        return (
            f"Cadeia rompida no evento de sequência {self.primeira_divergencia}. "
            "Preserve uma cópia e investigue antes de continuar operando."
        )


def verificar_cadeia(eventos: list[EventoAuditoria]) -> ResultadoVerificacao:
    """Recalcula os hashes em ordem e aponta a primeira divergência."""
    esperado_anterior = ""
    for evento in eventos:
        if evento.hash_anterior != esperado_anterior:
            return ResultadoVerificacao(len(eventos), False, evento.sequencia)
        if evento.calcular_hash() != evento.hash:
            return ResultadoVerificacao(len(eventos), False, evento.sequencia)
        esperado_anterior = evento.hash
    return ResultadoVerificacao(len(eventos), True, None)


def encadear(eventos: list[EventoAuditoria], novo: EventoAuditoria) -> EventoAuditoria:
    """Preenche sequência e hash anterior do próximo evento da trilha."""
    sequencia = (eventos[-1].sequencia + 1) if eventos else 1
    anterior = eventos[-1].hash if eventos else ""
    base = EventoAuditoria(
        acao=novo.acao,
        criado_em_utc=novo.criado_em_utc,
        data_negocio=novo.data_negocio,
        ator_id=novo.ator_id,
        entidade=novo.entidade,
        entidade_id=novo.entidade_id,
        antes=novo.antes,
        depois=novo.depois,
        motivo=novo.motivo,
        autorizador_id=novo.autorizador_id,
        origem=novo.origem,
        correlacao_id=novo.correlacao_id,
        sequencia=sequencia,
        hash_anterior=anterior,
    )
    return base.com_hash()
