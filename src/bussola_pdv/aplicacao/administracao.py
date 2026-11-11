"""Área administrativa: diagnóstico das dependências, cópias e manutenção.

O objetivo é responder, dentro do próprio sistema, às perguntas que hoje só se
respondem com terminal: *"esta instalação está íntegra? a versão do banco está
atualizada? o Argon2 está disponível? existe cópia recente? qual o tamanho da
base?"*. Nada aqui é estimativa: cada linha vem de uma checagem real e o status
é calculado, não digitado.
"""

from __future__ import annotations

import platform
import shutil
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from .. import __version__
from ..dominio.auditoria import AcaoAuditoria, EventoAuditoria
from ..dominio.erros import ErroNaoEncontrado, ErroValidacao
from ..dominio.usuario import Acao, Usuario
from ..infra.sqlite.conexao import verificar_integridade
from ..infra.sqlite.migrador import migracoes_disponiveis, versao_atual
from .contexto import Contexto

VERSAO_MINIMA_PYTHON = (3, 12)
TAMANHO_MINIMO_LIVRE_MB = 100
TABELAS_OBRIGATORIAS = (
    "usuarios",
    "permissoes_perfil",
    "parametros",
    "produtos",
    "vendas",
    "itens_venda",
    "pagamentos",
    "auditoria",
    "esquema_versao",
)


class StatusDiagnostico(StrEnum):
    OK = "OK"
    ATENCAO = "ATENCAO"
    ERRO = "ERRO"
    INFO = "INFO"

    @property
    def rotulo(self) -> str:
        return {
            StatusDiagnostico.OK: "OK",
            StatusDiagnostico.ATENCAO: "Atenção",
            StatusDiagnostico.ERRO: "Erro",
            StatusDiagnostico.INFO: "Informativo",
        }[self]


@dataclass(frozen=True, slots=True)
class ItemDiagnostico:
    grupo: str
    nome: str
    valor: str
    status: StatusDiagnostico
    detalhe: str = ""

    @property
    def critico(self) -> bool:
        return self.status is StatusDiagnostico.ERRO


def formatar_bytes(total: int) -> str:
    """Bytes em B/KB/MB/GB — evita mostrar "0,0 MB" para uma base recém-criada."""
    valor = float(total)
    for unidade in ("B", "KB", "MB"):
        if valor < 1024:
            return f"{valor:.0f} {unidade}" if unidade != "MB" else f"{valor:.1f} MB"
        valor /= 1024
    return f"{valor:.1f} GB"


class ServicoAdministracao:
    def __init__(self, contexto: Contexto) -> None:
        self.ctx = contexto

    # -- diagnóstico --------------------------------------------------------
    def diagnostico(self) -> list[ItemDiagnostico]:
        itens: list[ItemDiagnostico] = []
        itens.extend(self._ambiente())
        itens.extend(self._banco())
        itens.extend(self._conteudo())
        return itens

    def problemas(self) -> list[ItemDiagnostico]:
        return [item for item in self.diagnostico() if item.status is StatusDiagnostico.ERRO]

    def _ambiente(self) -> list[ItemDiagnostico]:
        itens = [
            ItemDiagnostico(
                grupo="Aplicação",
                nome="Versão do Bússola",
                valor=__version__,
                status=StatusDiagnostico.INFO,
                detalhe="Pré-alfa: não homologado para operação real.",
            )
        ]
        versao = sys.version_info
        atual = (versao.major, versao.minor)
        itens.append(
            ItemDiagnostico(
                grupo="Aplicação",
                nome="Python",
                valor=f"{versao.major}.{versao.minor}.{versao.micro}",
                status=(
                    StatusDiagnostico.OK
                    if atual >= VERSAO_MINIMA_PYTHON
                    else StatusDiagnostico.ERRO
                ),
                detalhe=(
                    f"Requer {VERSAO_MINIMA_PYTHON[0]}.{VERSAO_MINIMA_PYTHON[1]} ou superior."
                ),
            )
        )
        itens.append(
            ItemDiagnostico(
                grupo="Aplicação",
                nome="Sistema operacional",
                valor=f"{platform.system()} {platform.release()} ({platform.machine()})",
                status=StatusDiagnostico.INFO,
            )
        )
        itens.append(self._item_pyside())
        itens.append(self._item_argon2())
        return itens

    @staticmethod
    def _item_pyside() -> ItemDiagnostico:
        try:
            from PySide6 import __version__ as versao_qt

            return ItemDiagnostico(
                grupo="Aplicação",
                nome="PySide6 / Qt",
                valor=str(versao_qt),
                status=StatusDiagnostico.OK,
                detalhe="Licença LGPLv3/GPL — ver NOTICE.md.",
            )
        except Exception as exc:  # pragma: no cover - depende do ambiente
            return ItemDiagnostico(
                grupo="Aplicação",
                nome="PySide6 / Qt",
                valor="indisponível",
                status=StatusDiagnostico.ERRO,
                detalhe=f"Interface gráfica não abrirá: {exc}",
            )

    @staticmethod
    def _item_argon2() -> ItemDiagnostico:
        from ..dominio import seguranca

        if getattr(seguranca, "_ARGON2_DISPONIVEL", False):
            return ItemDiagnostico(
                grupo="Segurança",
                nome="Argon2id",
                valor="disponível",
                status=StatusDiagnostico.OK,
                detalhe="Derivação de senha ativa (64 MiB, 3 iterações, paralelismo 4).",
            )
        return ItemDiagnostico(
            grupo="Segurança",
            nome="Argon2id",
            valor="indisponível",
            status=StatusDiagnostico.ERRO,
            detalhe="Instale argon2-cffi. O sistema não aceita hash simples como substituto.",
        )

    def _tamanho_da_base(self, caminho: Path) -> int:
        """Tamanho real: páginas do SQLite mais o diário WAL (no WAL o .db fica pequeno)."""
        try:
            paginas = int(self.ctx.conexao.execute("PRAGMA page_count").fetchone()[0])
            tamanho_pagina = int(self.ctx.conexao.execute("PRAGMA page_size").fetchone()[0])
            total = paginas * tamanho_pagina
        except (sqlite3.Error, TypeError, ValueError):  # pragma: no cover - banco estranho
            return caminho.stat().st_size
        diario = Path(f"{caminho}-wal")
        if diario.exists():
            total += diario.stat().st_size
        return max(total, caminho.stat().st_size)

    def _banco(self) -> list[ItemDiagnostico]:
        conexao = self.ctx.conexao
        versao_sqlite = sqlite3.sqlite_version
        atual = versao_atual(conexao)
        ultima = max((v for v, _, _ in migracoes_disponiveis()), default=0)
        integro, problemas = verificar_integridade(conexao)
        caminho = self.ctx.caminho
        pragmas = {
            "journal_mode": conexao.execute("PRAGMA journal_mode").fetchone()[0],
            "foreign_keys": conexao.execute("PRAGMA foreign_keys").fetchone()[0],
            "synchronous": conexao.execute("PRAGMA synchronous").fetchone()[0],
        }
        itens = [
            ItemDiagnostico(
                grupo="Banco",
                nome="SQLite",
                valor=versao_sqlite,
                status=StatusDiagnostico.OK,
                detalhe="Biblioteca embutida no Python — sem servidor, sem rede.",
            ),
            ItemDiagnostico(
                grupo="Banco",
                nome="Esquema",
                valor=f"v{atual} de v{ultima}",
                status=(
                    StatusDiagnostico.OK if atual >= ultima else StatusDiagnostico.ATENCAO
                ),
                detalhe=(
                    "Migrações em dia."
                    if atual >= ultima
                    else f"{ultima - atual} migração(ões) pendente(s) para esta versão do app."
                ),
            ),
            ItemDiagnostico(
                grupo="Banco",
                nome="Integridade",
                valor="íntegro" if integro else "com problemas",
                status=StatusDiagnostico.OK if integro else StatusDiagnostico.ERRO,
                detalhe="; ".join(problemas) if problemas else "PRAGMA quick_check sem apontamentos.",
            ),
            ItemDiagnostico(
                grupo="Banco",
                nome="Modo de diário",
                valor=str(pragmas["journal_mode"]),
                status=(
                    StatusDiagnostico.OK
                    if str(pragmas["journal_mode"]).lower() == "wal"
                    else StatusDiagnostico.ATENCAO
                ),
                detalhe="WAL permite leitura durante a escrita e reduz risco de corrupção.",
            ),
            ItemDiagnostico(
                grupo="Banco",
                nome="Chaves estrangeiras",
                valor="ativas" if pragmas["foreign_keys"] else "desligadas",
                status=(
                    StatusDiagnostico.OK
                    if pragmas["foreign_keys"]
                    else StatusDiagnostico.ERRO
                ),
                detalhe="Sem FK ativa, referência órfã passa despercebida.",
            ),
            ItemDiagnostico(
                grupo="Banco",
                nome="Sincronização",
                valor={0: "OFF", 1: "NORMAL", 2: "FULL"}.get(
                    int(pragmas["synchronous"]), str(pragmas["synchronous"])
                ),
                status=(
                    StatusDiagnostico.OK
                    if int(pragmas["synchronous"]) == 2
                    else StatusDiagnostico.ATENCAO
                ),
                detalhe="FULL é exigido para não perder venda em queda de energia.",
            ),
            ItemDiagnostico(
                grupo="Banco",
                nome="Caminho",
                valor=str(caminho) if caminho else "em memória",
                status=StatusDiagnostico.INFO,
            ),
        ]
        if caminho is not None and caminho.exists():
            itens.append(
                ItemDiagnostico(
                    grupo="Banco",
                    nome="Tamanho da base",
                    valor=formatar_bytes(self._tamanho_da_base(caminho)),
                    status=StatusDiagnostico.INFO,
                    detalhe=(
                        "Páginas do SQLite somadas ao diário WAL: no modo WAL o arquivo .db "
                        "parece pequeno mesmo com dados gravados."
                    ),
                )
            )
            try:
                livre = shutil.disk_usage(caminho.parent).free / (1024 * 1024)
                itens.append(
                    ItemDiagnostico(
                        grupo="Banco",
                        nome="Espaço livre",
                        valor=f"{livre:.0f} MB",
                        status=(
                            StatusDiagnostico.OK
                            if livre >= TAMANHO_MINIMO_LIVRE_MB
                            else StatusDiagnostico.ATENCAO
                        ),
                        detalhe="Cópias de segurança precisam de espaço no mesmo disco.",
                    )
                )
            except OSError:  # pragma: no cover - ambiente sem statvfs
                pass
        return itens

    def _conteudo(self) -> list[ItemDiagnostico]:
        consultas = {
            "Usuários ativos": "SELECT COUNT(*) FROM usuarios WHERE ativo = 1",
            "Produtos": "SELECT COUNT(*) FROM produtos",
            "Vendas": "SELECT COUNT(*) FROM vendas",
            "Eventos de auditoria": "SELECT COUNT(*) FROM auditoria",
            "Exceções de permissão": "SELECT COUNT(*) FROM permissoes_perfil",
        }
        itens = [
            ItemDiagnostico(
                grupo="Conteúdo",
                nome=nome,
                valor=str(self.ctx.conexao.execute(sql).fetchone()[0]),
                status=StatusDiagnostico.INFO,
            )
            for nome, sql in consultas.items()
        ]
        masters = self.ctx.usuarios.masters_ativos()
        itens.append(
            ItemDiagnostico(
                grupo="Conteúdo",
                nome="Admin Master ativo",
                valor=masters[0].login if masters else "nenhum",
                status=StatusDiagnostico.OK if masters else StatusDiagnostico.ERRO,
                detalhe=(
                    "Proprietário identificado."
                    if masters
                    else "Sem Admin Master, ninguém pode ajustar permissões ou restaurar cópias."
                ),
            )
        )
        cadeia = self.ctx.auditoria.verificar()
        itens.append(
            ItemDiagnostico(
                grupo="Conteúdo",
                nome="Cadeia de auditoria",
                valor="íntegra" if cadeia.integro else "violada",
                status=StatusDiagnostico.OK if cadeia.integro else StatusDiagnostico.ERRO,
                detalhe=(
                    f"{cadeia.eventos} eventos verificados."
                    if cadeia.integro
                    else f"Divergência a partir do evento {cadeia.primeira_divergencia}."
                ),
            )
        )
        return itens

    # -- manutenção ---------------------------------------------------------
    def verificar_integridade(self, ator: Usuario) -> dict[str, object]:
        ator.exigir(Acao.MANUTENCAO_EXECUTAR)
        integro, problemas = verificar_integridade(self.ctx.conexao)
        cadeia = self.ctx.auditoria.verificar()
        return {
            "integro": integro,
            "problemas": problemas,
            "auditoria_integra": cadeia.integro,
            "eventos_auditoria": cadeia.eventos,
        }

    def otimizar(self, ator: Usuario) -> dict[str, object]:
        ator.exigir(Acao.MANUTENCAO_EXECUTAR)
        antes = self._tamanho()
        self.ctx.conexao.execute("ANALYZE")
        self.ctx.conexao.execute("VACUUM")
        depois = self._tamanho()
        agora = self.ctx.agora()
        with self.ctx.em_transacao():
            self.ctx.auditoria.registrar(
                EventoAuditoria(
                    acao=AcaoAuditoria.MANUTENCAO_EXECUTADA,
                    criado_em_utc=agora,
                    data_negocio=self.ctx.relogio.data_negocio(),
                    ator_id=ator.id,
                    entidade="banco",
                    depois={"antes_bytes": antes, "depois_bytes": depois},
                    motivo="ANALYZE + VACUUM",
                )
            )
        return {"antes_bytes": antes, "depois_bytes": depois, "liberado_bytes": max(0, antes - depois)}

    def backup(self, ator: Usuario, destino: str | Path) -> dict[str, object]:
        """Cópia consistente pela API do SQLite (não é cópia de arquivo aberto)."""
        ator.exigir(Acao.BACKUP_EXECUTAR)
        if self.ctx.caminho is None:
            raise ErroValidacao("Banco em memória não pode ser copiado para disco.")
        pasta = Path(destino)
        pasta.mkdir(parents=True, exist_ok=True)
        nome = f"{self.ctx.caminho.stem}-{self.ctx.agora().strftime('%Y%m%d-%H%M%S')}.db"
        alvo = pasta / nome
        copia = sqlite3.connect(alvo)
        try:
            self.ctx.conexao.backup(copia)
        finally:
            copia.close()
        verificacao = self.verificar_arquivo(alvo)
        agora = self.ctx.agora()
        with self.ctx.em_transacao():
            self.ctx.auditoria.registrar(
                EventoAuditoria(
                    acao=AcaoAuditoria.BACKUP_EXECUTADO,
                    criado_em_utc=agora,
                    data_negocio=self.ctx.relogio.data_negocio(),
                    ator_id=ator.id,
                    entidade="banco",
                    entidade_id=str(alvo),
                    depois={
                        "arquivo": str(alvo),
                        "bytes": alvo.stat().st_size,
                        "verificado": verificacao["integro"],
                    },
                    motivo="Cópia de segurança manual",
                )
            )
        return {
            "arquivo": str(alvo),
            "bytes": alvo.stat().st_size,
            "verificado": verificacao["integro"],
            "detalhe": verificacao["detalhe"],
        }

    def verificar_arquivo(self, caminho: str | Path) -> dict[str, object]:
        """Abre a cópia em modo somente leitura e confere estrutura e integridade."""
        arquivo = Path(caminho)
        if not arquivo.is_file():
            raise ErroNaoEncontrado(f"Arquivo não encontrado: {arquivo}")
        try:
            conexao = sqlite3.connect(f"file:{arquivo}?mode=ro", uri=True)
        except sqlite3.Error as exc:
            raise ErroValidacao(f"Não foi possível abrir a cópia: {exc}") from exc
        try:
            resultado = conexao.execute("PRAGMA integrity_check").fetchone()
        except sqlite3.DatabaseError as exc:
            conexao.close()
            raise ErroValidacao(f"O arquivo não é um banco SQLite válido: {exc}") from exc
        try:
            integro = bool(resultado) and str(resultado[0]).lower() == "ok"
            tabelas = {
                linha[0]
                for linha in conexao.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            faltando = [tabela for tabela in TABELAS_OBRIGATORIAS if tabela not in tabelas]
            versao = 0
            if "esquema_versao" in tabelas:
                versao = int(
                    conexao.execute("SELECT COALESCE(MAX(versao), 0) FROM esquema_versao").fetchone()[0]
                )
            return {
                "integro": integro and not faltando,
                "sqlite_ok": integro,
                "faltando": faltando,
                "versao_esquema": versao,
                "detalhe": (
                    "Cópia íntegra e compatível."
                    if integro and not faltando
                    else f"Problemas: faltando {faltando or 'nada'}"
                ),
            }
        finally:
            conexao.close()

    def restaurar(self, ator: Usuario, origem: str | Path) -> dict[str, object]:
        """Restaura uma cópia sobre a base atual, guardando a base anterior.

        A restauração usa a API de backup do SQLite (origem → conexão viva), o que
        substitui o conteúdo sem derrubar a aplicação. O arquivo atual é copiado
        antes para `<banco>.antes-de-restaurar-<timestamp>`; se algo der errado,
        esse arquivo é o caminho de volta.
        """
        ator.exigir(Acao.BACKUP_RESTAURAR)
        if not ator.eh_master:
            raise ErroValidacao("Somente o Admin Master restaura cópias de segurança.")
        if self.ctx.caminho is None:
            raise ErroValidacao("Não é possível restaurar sobre um banco em memória.")
        verificacao = self.verificar_arquivo(origem)
        if not verificacao["integro"]:
            raise ErroValidacao(f"Cópia inválida: {verificacao['detalhe']}")
        if int(str(verificacao["versao_esquema"])) > versao_atual(self.ctx.conexao):
            raise ErroValidacao(
                "A cópia é de uma versão mais nova do sistema. Atualize o aplicativo antes de restaurar."
            )

        carimbo = self.ctx.agora().strftime("%Y%m%d-%H%M%S")
        seguranca = self.ctx.caminho.with_name(
            f"{self.ctx.caminho.name}.antes-de-restaurar-{carimbo}"
        )
        anterior = sqlite3.connect(seguranca)
        try:
            self.ctx.conexao.backup(anterior)
        finally:
            anterior.close()

        origem_conexao = sqlite3.connect(f"file:{Path(origem)}?mode=ro", uri=True)
        try:
            origem_conexao.backup(self.ctx.conexao)
        finally:
            origem_conexao.close()

        integro, problemas = verificar_integridade(self.ctx.conexao)
        if not integro:  # pragma: no cover - só em cenário de desastre
            raise ErroValidacao(
                "Restauração resultou em base inconsistente: " + "; ".join(problemas)
            )
        agora = self.ctx.agora()
        with self.ctx.em_transacao():
            self.ctx.auditoria.registrar(
                EventoAuditoria(
                    acao=AcaoAuditoria.BACKUP_RESTAURADO,
                    criado_em_utc=agora,
                    data_negocio=self.ctx.relogio.data_negocio(),
                    ator_id=ator.id,
                    entidade="banco",
                    entidade_id=str(origem),
                    depois={
                        "origem": str(origem),
                        "copia_de_seguranca": str(seguranca),
                        "versao_esquema": int(str(verificacao["versao_esquema"])),
                    },
                    motivo="Restauração de cópia de segurança",
                )
            )
        return {
            "origem": str(origem),
            "copia_de_seguranca": str(seguranca),
            "versao_esquema": int(str(verificacao["versao_esquema"])),
            "integro": integro,
        }

    def listar_copias(self, pasta: str | Path) -> list[dict[str, object]]:
        diretorio = Path(pasta)
        if not diretorio.is_dir():
            return []
        copias = []
        for arquivo in sorted(diretorio.glob("*.db"), key=lambda a: a.stat().st_mtime, reverse=True):
            modificado = datetime.fromtimestamp(arquivo.stat().st_mtime)
            copias.append(
                {
                    "arquivo": arquivo.name,
                    "caminho": str(arquivo),
                    "bytes": arquivo.stat().st_size,
                    "modificado": modificado.strftime("%d/%m/%Y %H:%M"),
                }
            )
        return copias

    def _tamanho(self) -> int:
        if self.ctx.caminho is None or not self.ctx.caminho.exists():
            return 0
        return self.ctx.caminho.stat().st_size
