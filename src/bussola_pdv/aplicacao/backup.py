"""Cópias de segurança da base: criar, listar, verificar, podar e recuperar.

Por que um serviço só para isto, se `ServicoManutencao` já gerava uma cópia?

Porque "backup" tem três promessas que a cópia manual não cumpria:

1. **sobreviver à reinstalação** — a cópia tem de ser identificável depois:
   quando foi feita, de que versão, de que esquema, quantos registros, e um
   `sha256` que prova que o arquivo é o mesmo. Isso vai num manifesto ao lado
   do `.db`, em texto que se lê sem o programa;
2. **acontecer sem ninguém lembrar** — `automatico()` cria a cópia do dia e
   mantém as últimas N, sem o operador precisar abrir a tela;
3. **funcionar quando o programa não funciona** — por isso o formato é o mais
   burro possível (arquivo SQLite + JSON) e existe `ferramentas/backup_externo.py`,
   que não importa este pacote. Se o aplicativo não abre, a cópia continua
   possível.

A cópia é feita pela **API de backup do SQLite** (`Connection.backup`), nunca por
cópia de arquivo: com WAL ativo, copiar o `.db` pode produzir um arquivo sem as
últimas transações.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from .. import __version__
from ..caminhos import NOME_BANCO, pasta_de_copias
from ..dominio.erros import ErroNaoEncontrado, ErroValidacao

if TYPE_CHECKING:
    from .contexto import Contexto

#: Tabelas que precisam existir para a cópia servir para restaurar.
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

#: Tabelas contadas no manifesto (o que o dono da loja quer ver).
TABELAS_CONTADAS = ("produtos", "clientes", "vendas", "itens_venda", "usuarios", "auditoria")

SUFIXO_MANIFESTO = ".manifesto.json"
PADRAO_NOME = "pdv"


@dataclass(frozen=True, slots=True)
class Copia:
    """Uma cópia de segurança, com o que é preciso para confiar nela."""

    arquivo: Path
    rotulo: str = "manual"
    criado_em: datetime | None = None
    bytes: int = 0
    integro: bool = False
    versao_esquema: int = 0
    automatico: bool = False
    contagens: dict[str, int] = field(default_factory=dict)
    sha256: str = ""
    detalhe: str = ""

    @property
    def nome(self) -> str:
        return self.arquivo.name

    @property
    def manifesto(self) -> Path:
        return self.arquivo.with_name(f"{self.arquivo.name}{SUFIXO_MANIFESTO}")

    def resumo(self) -> str:
        """Linha de lista: data, rótulo, tamanho e integridade, sem jargão."""
        quando = (
            self.criado_em.strftime("%d/%m/%Y %H:%M") if self.criado_em else "data desconhecida"
        )
        tamanho = _tamanho_legivel(self.bytes)
        estado = "íntegra" if self.integro else "COM PROBLEMAS"
        origem = "automática" if self.automatico else self.rotulo
        return f"{quando} · {origem} · {tamanho} · esquema v{self.versao_esquema} · {estado}"


def _tamanho_legivel(bytes_: int) -> str:
    if bytes_ >= 1024 * 1024:
        return f"{bytes_ / (1024 * 1024):.1f} MB"
    if bytes_ >= 1024:
        return f"{bytes_ / 1024:.0f} KB"
    return f"{bytes_} B"


def _sha256(arquivo: Path) -> str:
    digest = hashlib.sha256()
    with arquivo.open("rb") as manipulador:
        for bloco in iter(lambda: manipulador.read(1024 * 256), b""):
            digest.update(bloco)
    return digest.hexdigest()


def inspecionar(arquivo: str | Path) -> Copia:
    """Abre a cópia em modo somente leitura e diz se ela serve para restaurar.

    Não confia no manifesto: o arquivo pode ter sido truncado por uma cópia
    interrompida. `sqlite3` em `mode=ro` + `PRAGMA integrity_check` respondem.
    """
    caminho = Path(arquivo)
    if not caminho.is_file():
        raise ErroNaoEncontrado(f"Cópia não encontrada: {caminho}")
    bytes_ = caminho.stat().st_size
    try:
        conexao = sqlite3.connect(f"file:{caminho}?mode=ro", uri=True)
    except sqlite3.Error as exc:  # pragma: no cover - caminho ilegível
        raise ErroValidacao(f"Não foi possível abrir a cópia: {exc}") from exc
    try:
        try:
            resultado = conexao.execute("PRAGMA integrity_check").fetchone()
        except sqlite3.DatabaseError as exc:
            return Copia(
                arquivo=caminho,
                bytes=bytes_,
                integro=False,
                detalhe=f"O arquivo não é um banco SQLite válido: {exc}",
            )
        integro = bool(resultado) and str(resultado[0]).lower() == "ok"
        tabelas = {
            linha[0] for linha in conexao.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        faltando = [tabela for tabela in TABELAS_OBRIGATORIAS if tabela not in tabelas]
        versao = 0
        if "esquema_versao" in tabelas:
            versao = int(
                conexao.execute("SELECT COALESCE(MAX(versao), 0) FROM esquema_versao").fetchone()[0]
            )
        contagens: dict[str, int] = {}
        for tabela in TABELAS_CONTADAS:
            if tabela in tabelas:
                # nome de tabela vem da constante TABELAS_CONTADAS, não do usuário
                consulta = f"SELECT COUNT(*) FROM {tabela}"  # noqa: S608
                contagens[tabela] = int(conexao.execute(consulta).fetchone()[0])
    finally:
        conexao.close()

    servem = integro and not faltando
    if servem:
        detalhe = "Cópia íntegra e compatível."
    elif faltando:
        detalhe = "Faltam tabelas do PDV: " + ", ".join(faltando)
    else:
        detalhe = "O SQLite reportou problemas de integridade."
    manifesto = _ler_manifesto(caminho)
    return Copia(
        arquivo=caminho,
        rotulo=str(manifesto.get("rotulo", "manual")),
        criado_em=_data_do_manifesto(manifesto) or _data_do_arquivo(caminho),
        bytes=bytes_,
        integro=servem,
        versao_esquema=versao,
        automatico=bool(manifesto.get("automatico", False)),
        contagens=contagens,
        sha256=str(manifesto.get("sha256", "")),
        detalhe=detalhe,
    )


def _data_do_arquivo(arquivo: Path) -> datetime | None:
    try:
        # sempre *aware*: comparar data ingênua com `ctx.agora()` explodia com
        # "can't compare offset-naive and offset-aware datetimes"
        return datetime.fromtimestamp(arquivo.stat().st_mtime).astimezone()
    except OSError:  # pragma: no cover - sistema de arquivos exótico
        return None


def _data_do_manifesto(manifesto: dict) -> datetime | None:
    texto = str(manifesto.get("criado_em_utc", "")).strip()
    if not texto:
        return None
    try:
        data = datetime.fromisoformat(texto)
    except ValueError:
        return None
    if data.tzinfo is None:  # manifesto escrito por versão antiga/robô
        data = data.replace(tzinfo=UTC)
    return data.astimezone()


def _ler_manifesto(arquivo: Path) -> dict:
    caminho = arquivo.with_name(f"{arquivo.name}{SUFIXO_MANIFESTO}")
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return dados if isinstance(dados, dict) else {}


def _gravar_manifesto(copia: Copia, extra: dict | None = None) -> Path:
    dados = {
        "arquivo": copia.arquivo.name,
        "rotulo": copia.rotulo,
        "automatico": copia.automatico,
        "criado_em_utc": (copia.criado_em or datetime.now().astimezone()).astimezone().isoformat(),
        "versao_aplicativo": __version__,
        "versao_esquema": copia.versao_esquema,
        "bytes": copia.bytes,
        "sha256": copia.sha256,
        "contagens": copia.contagens,
        "integro": copia.integro,
        "formato": 1,
        "como_restaurar": (
            "Feche o Bússola PDV, guarde o pdv.db atual e copie este arquivo para "
            "pdv.db na pasta de dados. Ou, com o programa aberto: Administração › "
            "Manutenção › Restaurar selecionada."
        ),
    }
    if extra:
        dados.update(extra)
    caminho = copia.manifesto
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return caminho


class ServicoBackup:
    """Cópias de segurança da instalação, com manifesto e rotação."""

    def __init__(self, contexto: Contexto) -> None:
        self.ctx = contexto

    # -- pasta ---------------------------------------------------------------
    def pasta(self, destino: str | Path | None = None) -> Path:
        if destino is not None:
            pasta = Path(destino).expanduser()
            pasta.mkdir(parents=True, exist_ok=True)
            return pasta
        try:
            return pasta_de_copias()
        except OSError:  # pragma: no cover - pasta de dados somente leitura
            ao_lado = (self.ctx.caminho or Path.cwd()).parent / "copias"
            ao_lado.mkdir(parents=True, exist_ok=True)
            return ao_lado

    # -- criar ---------------------------------------------------------------
    def criar(
        self,
        *,
        rotulo: str = "manual",
        destino: str | Path | None = None,
        automatico: bool = False,
    ) -> Copia:
        """Cópia consistente + manifesto verificado."""
        if self.ctx.caminho is None:
            raise ErroValidacao("Banco em memória não pode ser copiado para disco.")
        pasta = self.pasta(destino)
        # `criado_em` é sempre o relógio da aplicação (UTC), nunca o do sistema de
        # arquivos: é o que entra na auditoria e no manifesto.
        agora = self.ctx.agora()
        carimbo = agora.strftime("%Y%m%d-%H%M%S")
        alvo = pasta / f"{PADRAO_NOME}-{carimbo}.db"
        contador = 1
        while alvo.exists():  # duas cópias no mesmo segundo
            alvo = pasta / f"{PADRAO_NOME}-{carimbo}-{contador}.db"
            contador += 1
        copia_conexao = sqlite3.connect(str(alvo))
        try:
            self.ctx.conexao.backup(copia_conexao)
        finally:
            copia_conexao.close()
        inspecionada = inspecionar(alvo)
        if not inspecionada.integro:
            alvo.unlink(missing_ok=True)
            raise ErroValidacao(f"A cópia não passou na verificação: {inspecionada.detalhe}")
        copia = Copia(
            arquivo=alvo,
            rotulo=rotulo,
            criado_em=agora,
            bytes=inspecionada.bytes,
            integro=True,
            versao_esquema=inspecionada.versao_esquema,
            automatico=automatico,
            contagens=inspecionada.contagens,
            sha256=_sha256(alvo),
        )
        _gravar_manifesto(
            copia,
            {"banco_origem": str(self.ctx.caminho), "automatico": automatico},
        )
        return copia

    # -- listar / verificar --------------------------------------------------
    def listar(self, destino: str | Path | None = None) -> list[Copia]:
        """Cópias da pasta, da mais nova para a mais antiga (só `.db`)."""
        pasta = self.pasta(destino)
        copias: list[Copia] = []
        for arquivo in sorted(pasta.glob("*.db")):
            if arquivo.name.endswith(("-wal", "-shm")):
                continue
            try:
                copias.append(inspecionar(arquivo))
            except ErroNaoEncontrado:  # pragma: no cover - corrida com remoção
                continue
        copias.sort(key=lambda c: (c.criado_em or datetime.min, c.nome), reverse=True)
        return copias

    def verificar(self, arquivo: str | Path) -> Copia:
        return inspecionar(arquivo)

    # -- rotação -------------------------------------------------------------
    def podar(self, *, manter: int = 14, destino: str | Path | None = None) -> list[Path]:
        """Apaga as cópias **automáticas** mais antigas, mantendo as `manter`.

        Cópia manual nunca é apagada pelo programa: é o operador quem decidiu
        guardá-la (talvez antes de uma restauração).
        """
        if manter < 1:
            raise ErroValidacao("É preciso manter ao menos uma cópia.")
        automaticas = [c for c in self.listar(destino) if c.automatico]
        removidas: list[Path] = []
        for copia in automaticas[manter:]:
            copia.manifesto.unlink(missing_ok=True)
            copia.arquivo.unlink(missing_ok=True)
            removidas.append(copia.arquivo)
        return removidas

    # -- automático ----------------------------------------------------------
    def ultima_automatica(self, destino: str | Path | None = None) -> Copia | None:
        for copia in self.listar(destino):
            if copia.automatico:
                return copia
        return None

    def automatico(
        self,
        *,
        intervalo_horas: int = 24,
        manter: int = 14,
        destino: str | Path | None = None,
    ) -> Copia | None:
        """Cópia do dia, uma por intervalo; devolve `None` quando ainda não é hora.

        Chamado ao abrir o programa: quem usa o PDV todo dia passa a ter sempre
        uma cópia de menos de 24 h sem clicar em nada.
        """
        ultima = self.ultima_automatica(destino)
        if ultima is not None and ultima.criado_em is not None:
            limite = self.ctx.agora() - timedelta(hours=intervalo_horas)
            criada = ultima.criado_em
            if criada.tzinfo is None:  # defensivo: manifesto sem fuso
                criada = criada.replace(tzinfo=UTC)
            if criada >= limite:
                return None
        copia = self.criar(rotulo="automática", destino=destino, automatico=True)
        self.podar(manter=manter, destino=destino)
        return copia

    # -- recuperação de base corrompida --------------------------------------
    def recuperar(self, origem: str | Path, destino: str | Path) -> Copia:
        """Salva o que der de uma base danificada, num arquivo novo.

        Usa `iterdump()`, que lê o arquivo página a página: quando o cabeçalho
        está bom mas há páginas corrompidas, ele ainda devolve a maior parte dos
        dados. O que não puder ser lido fica de fora — e é dito assim, sem
        prometer recuperação total.
        """
        entrada = Path(origem)
        if not entrada.is_file():
            raise ErroNaoEncontrado(f"Base não encontrada: {entrada}")
        saida = Path(destino)
        if saida.exists():
            raise ErroValidacao(f"O destino já existe: {saida}")
        saida.parent.mkdir(parents=True, exist_ok=True)
        try:
            origem_conexao = sqlite3.connect(f"file:{entrada}?mode=ro", uri=True)
        except sqlite3.Error as exc:
            raise ErroValidacao(f"Não foi possível abrir a base: {exc}") from exc
        recuperados = 0
        try:
            nova = sqlite3.connect(str(saida))
            try:
                for instrucao in origem_conexao.iterdump():
                    nova.execute(instrucao)
                    recuperados += 1
                nova.commit()
            finally:
                nova.close()
        except sqlite3.DatabaseError as exc:
            saida.unlink(missing_ok=True)  # não deixar meia-base para trás
            raise ErroValidacao(
                f"A base não pôde ser lida nem parcialmente: {exc}. "
                "Tente uma cópia de segurança anterior."
            ) from exc
        finally:
            origem_conexao.close()
        copia = inspecionar(saida)
        if not copia.integro:
            raise ErroValidacao(f"A recuperação resultou em base inutilizável: {copia.detalhe}")
        return Copia(
            arquivo=saida,
            rotulo="recuperada",
            criado_em=self.ctx.agora(),
            bytes=copia.bytes,
            integro=copia.integro,
            versao_esquema=copia.versao_esquema,
            contagens=copia.contagens,
            sha256=_sha256(saida),
            detalhe=f"{recuperados} instruções recuperadas de {entrada.name}.",
        )

    # -- restauração fora da interface ---------------------------------------
    def restaurar_arquivo(self, origem: str | Path) -> Path:
        """Restaura a cópia sobre o arquivo da base — **com o programa fechado**.

        A restauração com o programa aberto é feita pela interface
        (`ServicoManutencao.restaurar`), que usa a API do SQLite e audita. Esta
        via existe para o caso de o aplicativo não abrir.
        """
        if self.ctx.caminho is None:
            raise ErroValidacao("Não há arquivo de base para restaurar (banco em memória).")
        copia = inspecionar(origem)
        if not copia.integro:
            raise ErroValidacao(f"Cópia inválida: {copia.detalhe}")
        carimbo = self.ctx.agora().strftime("%Y%m%d-%H%M%S")
        seguranca = self.ctx.caminho.with_name(f"{self.ctx.caminho.name}.antes-de-restaurar-{carimbo}")
        self.ctx.fechar()
        self.ctx.caminho.replace(seguranca)
        Path(origem).replace(self.ctx.caminho)
        return seguranca


def banco_em_pasta(pasta: str | Path) -> Path:
    """Caminho do `pdv.db` dentro de uma pasta de dados."""
    return Path(pasta).expanduser() / NOME_BANCO


__all__ = [
    "TABELAS_CONTADAS",
    "TABELAS_OBRIGATORIAS",
    "Copia",
    "ServicoBackup",
    "banco_em_pasta",
    "inspecionar",
]
