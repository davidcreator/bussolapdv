"""Persistência SQLite da aplicação."""

from .conexao import abrir_conexao, fazer_backup, transacao, verificar_integridade
from .migrador import migrar, versao_atual

__all__ = [
    "abrir_conexao",
    "fazer_backup",
    "migrar",
    "transacao",
    "verificar_integridade",
    "versao_atual",
]
