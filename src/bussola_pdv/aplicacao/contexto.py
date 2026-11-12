"""Composição das dependências: conexão, relógio, repositórios e casos de uso."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from ..dominio.relogio import Relogio, RelogioSistema
from ..infra.sqlite.conexao import abrir_conexao, transacao, verificar_integridade
from ..infra.sqlite.migrador import migrar, versao_atual
from ..infra.sqlite.repositorio_auditoria import AuditoriaRepositorio
from ..infra.sqlite.repositorio_caixa import CaixaRepositorio
from ..infra.sqlite.repositorio_clientes import ClienteRepositorio
from ..infra.sqlite.repositorio_crediario import CrediarioRepositorio
from ..infra.sqlite.repositorio_estoque import EntradaRepositorio, EstoqueRepositorio
from ..infra.sqlite.repositorio_fechamentos import FechamentoRepositorio
from ..infra.sqlite.repositorio_permissoes import PermissaoRepositorio
from ..infra.sqlite.repositorio_produtos import ProdutoRepositorio
from ..infra.sqlite.repositorio_usuarios import ParametroRepositorio, UsuarioRepositorio
from ..infra.sqlite.repositorio_vendas import VendaRepositorio


@dataclass
class Contexto:
    """Raiz de composição. Uma instância por processo/estação."""

    conexao: sqlite3.Connection
    relogio: Relogio
    caminho: Path | None = None

    produtos: ProdutoRepositorio = field(init=False)
    clientes: ClienteRepositorio = field(init=False)
    usuarios: UsuarioRepositorio = field(init=False)
    parametros: ParametroRepositorio = field(init=False)
    permissoes: PermissaoRepositorio = field(init=False)
    caixas: CaixaRepositorio = field(init=False)
    vendas: VendaRepositorio = field(init=False)
    estoque: EstoqueRepositorio = field(init=False)
    entradas: EntradaRepositorio = field(init=False)
    crediario: CrediarioRepositorio = field(init=False)
    auditoria: AuditoriaRepositorio = field(init=False)
    fechamentos: FechamentoRepositorio = field(init=False)

    def __post_init__(self) -> None:
        self.produtos = ProdutoRepositorio(self.conexao)
        self.clientes = ClienteRepositorio(self.conexao)
        self.usuarios = UsuarioRepositorio(self.conexao)
        self.parametros = ParametroRepositorio(self.conexao)
        self.permissoes = PermissaoRepositorio(self.conexao)
        self.caixas = CaixaRepositorio(self.conexao)
        self.vendas = VendaRepositorio(self.conexao)
        self.estoque = EstoqueRepositorio(self.conexao)
        self.entradas = EntradaRepositorio(self.conexao)
        self.crediario = CrediarioRepositorio(self.conexao)
        self.auditoria = AuditoriaRepositorio(self.conexao)
        self.fechamentos = FechamentoRepositorio(self.conexao)

    # -- ciclo de vida ------------------------------------------------------
    @classmethod
    def abrir(
        cls,
        caminho: str | Path,
        *,
        relogio: Relogio | None = None,
        aplicar_migracoes: bool = True,
    ) -> Contexto:
        destino = Path(caminho)
        # O relógio é montado ANTES de abrir o arquivo: um erro de fuso (Windows
        # sem `tzdata`) precisa estourar com a base ainda intocada. Na versão
        # anterior ele nascia depois da conexão, e a base ficava travada com o
        # programa tentando movê-la — o operador via "arquivo em uso" em vez do
        # motivo real.
        relogio = relogio or RelogioSistema()
        conexao = abrir_conexao(destino)
        try:
            if aplicar_migracoes:
                migrar(conexao)
            return cls(conexao=conexao, relogio=relogio, caminho=destino)
        except BaseException:
            conexao.close()  # nunca deixar o arquivo preso por uma falha de abertura
            raise

    @classmethod
    def em_memoria(cls, *, relogio: Relogio | None = None) -> Contexto:
        """Banco efêmero para testes (SQLite não aceita WAL em memória; ver conexao)."""
        conexao = sqlite3.connect(":memory:", isolation_level=None)
        conexao.row_factory = sqlite3.Row
        conexao.execute("PRAGMA foreign_keys = ON")
        migrar(conexao)
        return cls(conexao=conexao, relogio=relogio or RelogioSistema())

    def fechar(self) -> None:
        self.conexao.close()

    def __enter__(self) -> Contexto:
        return self

    def __exit__(self, *_: object) -> None:
        self.fechar()

    # -- transações ---------------------------------------------------------
    @contextmanager
    def em_transacao(self) -> Iterator[sqlite3.Connection]:
        with transacao(self.conexao) as conexao:
            yield conexao

    # -- utilidades ---------------------------------------------------------
    def versao_esquema(self) -> int:
        return versao_atual(self.conexao)

    def conferir_integridade(self) -> tuple[bool, list[str]]:
        return verificar_integridade(self.conexao)

    def agora(self) -> datetime:
        return self.relogio.agora_utc()

    def data_negocio(self) -> str:
        return self.relogio.data_negocio()
