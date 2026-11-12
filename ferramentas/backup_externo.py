#!/usr/bin/env python3
"""Cópia de segurança do Bússola PDV **sem depender do programa**.

Por que este arquivo existe separado:

* o PDV pode não abrir (base corrompida, atualização pela metade, Python do
  sistema removido). O backup não pode depender do aplicativo que falhou;
* por isso este script usa **só a biblioteca padrão** (Python 3.9+) e não
  importa `bussola_pdv`. Ele também funciona com o Python instalado em qualquer
  lugar, inclusive o que vem no Windows;

Como usar (Windows, no Prompt de Comando ou duplo clique no `.bat` ao lado):

    python backup_externo.py                     -> cria a cópia na pasta copias/
    python backup_externo.py listar
    python backup_externo.py verificar ARQUIVO
    python backup_externo.py restaurar ARQUIVO   (feche o PDV antes!)
    python backup_externo.py recuperar           (base danificada -> base nova)

    --pasta CAMINHO   pasta de dados (padrão: a que o PDV usa nesta máquina)
    --destino PASTA   onde gravar as cópias (padrão: <pasta de dados>/copias)

O que é gravado: o arquivo `.db` + `<nome>.db.manifesto.json` com data, versão
do PDV, versão do esquema, contagem de registros e `sha256` — o manifesto é
texto simples justamente para poder ser lido sem o programa.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

NOME_BANCO = "pdv.db"
NOME_COPIAS = "copias"
NOME_PASTA = "BussolaPDV"
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
TABELAS_CONTADAS = ("produtos", "clientes", "vendas", "itens_venda", "usuarios", "auditoria")


# -- descoberta da pasta de dados ------------------------------------------------
def pasta_de_configuracao() -> Path:
    """Onde o PDV guarda o `instalacao.json` (ponteiro para a pasta de dados)."""
    for variavel in ("BUSSOLA_CONFIG",):
        caminho = os.environ.get(variavel, "").strip()
        if caminho:
            return Path(caminho).expanduser()
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / NOME_PASTA
        return Path.home() / "AppData" / "Roaming" / NOME_PASTA
    base = os.environ.get("XDG_CONFIG_HOME")
    return (Path(base) if base else Path.home() / ".config") / "bussola-pdv"


def pasta_de_dados_padrao() -> Path:
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / NOME_PASTA
        return Path.home() / "AppData" / "Local" / NOME_PASTA
    base = os.environ.get("XDG_DATA_HOME")
    return (Path(base) if base else Path.home() / ".local" / "share") / "bussola-pdv"


def pasta_de_dados(escolhida: str | None = None) -> Path:
    """A pasta escolhida, senão a que o PDV gravou, senão o padrão do sistema."""
    if escolhida:
        return Path(escolhida).expanduser()
    configuracao = pasta_de_configuracao() / "instalacao.json"
    try:
        dados = json.loads(configuracao.read_text(encoding="utf-8"))
        caminho = str(dados.get("dados", "")).strip()
        if caminho:
            return Path(caminho).expanduser()
    except (OSError, ValueError):
        pass
    return pasta_de_dados_padrao()


def banco_de(pasta: Path) -> Path:
    direto = pasta / NOME_BANCO
    if direto.is_file():
        return direto
    # quem apontar para a pasta errada recebe uma dica em vez de erro seco
    candidatos = sorted(pasta.glob("*.db")) if pasta.is_dir() else []
    if len(candidatos) == 1:
        return candidatos[0]
    return direto


# -- núcleo de backup ------------------------------------------------------------
def sha256(arquivo: Path) -> str:
    digest = hashlib.sha256()
    with arquivo.open("rb") as manipulador:
        for bloco in iter(lambda: manipulador.read(1024 * 256), b""):
            digest.update(bloco)
    return digest.hexdigest()


def inspecionar(arquivo: Path) -> dict:
    """Integridade, esquema e contagens de um arquivo `.db` (somente leitura)."""
    info: dict = {
        "arquivo": str(arquivo),
        "bytes": arquivo.stat().st_size,
        "integro": False,
        "versao_esquema": 0,
        "contagens": {},
        "detalhe": "",
    }
    try:
        conexao = sqlite3.connect(f"file:{arquivo}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        info["detalhe"] = f"não foi possível abrir: {exc}"
        return info
    try:
        try:
            resultado = conexao.execute("PRAGMA integrity_check").fetchone()
        except sqlite3.DatabaseError as exc:
            info["detalhe"] = f"não é um banco SQLite válido: {exc}"
            return info
        ok = bool(resultado) and str(resultado[0]).lower() == "ok"
        tabelas = {
            linha[0] for linha in conexao.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        faltando = [tabela for tabela in TABELAS_OBRIGATORIAS if tabela not in tabelas]
        if "esquema_versao" in tabelas:
            info["versao_esquema"] = int(
                conexao.execute("SELECT COALESCE(MAX(versao), 0) FROM esquema_versao").fetchone()[0]
            )
        for tabela in TABELAS_CONTADAS:
            if tabela in tabelas:
                # nome de tabela vem da constante TABELAS_CONTADAS, não do usuário
                consulta = f"SELECT COUNT(*) FROM {tabela}"  # noqa: S608
                info["contagens"][tabela] = int(conexao.execute(consulta).fetchone()[0])
        info["integro"] = ok and not faltando
        info["detalhe"] = (
            "íntegro e compatível"
            if info["integro"]
            else ("faltam tabelas: " + ", ".join(faltando) if faltando else "falha de integridade")
        )
        return info
    finally:
        conexao.close()


def criar_copia(banco: Path, destino: Path, rotulo: str = "manual") -> Path:
    destino.mkdir(parents=True, exist_ok=True)
    carimbo = datetime.now().strftime("%Y%m%d-%H%M%S")
    alvo = destino / f"pdv-{carimbo}.db"
    contador = 1
    while alvo.exists():
        alvo = destino / f"pdv-{carimbo}-{contador}.db"
        contador += 1
    # API de backup do SQLite: seguro mesmo com o WAL ativo e com o programa aberto
    origem = sqlite3.connect(f"file:{banco}?mode=ro", uri=True)
    try:
        copia = sqlite3.connect(str(alvo))
        try:
            origem.backup(copia)
        finally:
            copia.close()
    except sqlite3.Error as exc:
        alvo.unlink(missing_ok=True)
        raise SystemExit(
            f"Não foi possível copiar a base ({exc}).\n"
            "Se o arquivo estiver em uso, feche o PDV e tente de novo."
        ) from exc
    finally:
        origem.close()
    info = inspecionar(alvo)
    if not info["integro"]:
        alvo.unlink(missing_ok=True)
        raise SystemExit(f"A cópia não passou na verificação: {info['detalhe']}")
    manifesto = {
        "arquivo": alvo.name,
        "rotulo": rotulo,
        "criado_em_utc": datetime.now(UTC).isoformat(),
        "bytes": info["bytes"],
        "sha256": sha256(alvo),
        "versao_esquema": info["versao_esquema"],
        "contagens": info["contagens"],
        "integro": True,
        "origem": str(banco),
        "gerado_por": "ferramentas/backup_externo.py",
        "como_restaurar": (
            f"Feche o Bússola PDV, guarde o {banco.name} atual e copie este arquivo "
            f"para {banco}"
        ),
    }
    alvo.with_name(f"{alvo.name}.manifesto.json").write_text(
        json.dumps(manifesto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return alvo


def listar(pasta: Path) -> list[dict]:
    itens = []
    for arquivo in sorted(pasta.glob("*.db")):
        info = inspecionar(arquivo)
        manifesto = arquivo.with_name(f"{arquivo.name}.manifesto.json")
        if manifesto.is_file():
            try:
                dados = json.loads(manifesto.read_text(encoding="utf-8"))
                info["rotulo"] = dados.get("rotulo", "manual")
                info["criado_em_utc"] = dados.get("criado_em_utc", "")
            except (OSError, ValueError):
                pass
        info.setdefault("criado_em_utc", "")
        info["nome"] = arquivo.name
        itens.append(info)
    itens.sort(key=lambda item: (item.get("criado_em_utc", ""), item["nome"]), reverse=True)
    return itens


def recuperar(origem: Path, destino: Path) -> Path:
    """Salva o que der de uma base danificada, usando `iterdump`."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists():
        raise SystemExit(f"O destino já existe: {destino}")
    try:
        origem_conexao = sqlite3.connect(f"file:{origem}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise SystemExit(f"Não foi possível abrir a base: {exc}") from exc
    try:
        nova = sqlite3.connect(str(destino))
        try:
            for instrucao in origem_conexao.iterdump():
                nova.execute(instrucao)
            nova.commit()
        finally:
            nova.close()
    except sqlite3.DatabaseError as exc:
        destino.unlink(missing_ok=True)
        raise SystemExit(
            f"A base não pôde ser lida nem parcialmente: {exc}.\n"
            "Tente uma cópia de segurança anterior."
        ) from exc
    finally:
        origem_conexao.close()
    info = inspecionar(destino)
    if not info["integro"]:
        raise SystemExit(f"A recuperação resultou em base inutilizável: {info['detalhe']}")
    return destino


def restaurar(banco: Path, copia: Path) -> Path:
    """Devolve a cópia para o lugar da base, guardando a base atual."""
    info = inspecionar(copia)
    if not info["integro"]:
        raise SystemExit(f"Cópia inválida: {info['detalhe']}")
    if banco.is_file():
        seguranca = banco.with_name(
            f"{banco.name}.antes-de-restaurar-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        )
        banco.replace(seguranca)
    else:
        seguranca = banco
    for sufixo in ("-wal", "-shm"):
        ao_lado = banco.with_name(banco.name + sufixo)
        if ao_lado.exists():
            ao_lado.unlink()
    copia.replace(banco)
    return seguranca


# -- linha de comando ------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Cópia de segurança do Bússola PDV sem depender do programa.",
    )
    parser.add_argument(
        "acao",
        nargs="?",
        default="criar",
        choices=["criar", "listar", "verificar", "restaurar", "recuperar"],
        help="o que fazer (padrão: criar)",
    )
    parser.add_argument("arquivo", nargs="?", help="arquivo .db da ação verificar/restaurar/recuperar")
    parser.add_argument("--pasta", help="pasta de dados do PDV (padrão: a instalada)")
    parser.add_argument("--destino", help="pasta das cópias (padrão: <dados>/copias)")
    parser.add_argument(
        "--manter",
        type=int,
        default=0,
        help="depois de criar, apagar as cópias mais antigas mantendo só N",
    )
    args = parser.parse_args(argv)

    pasta = pasta_de_dados(args.pasta)
    banco = banco_de(pasta)
    destino = Path(args.destino).expanduser() if args.destino else pasta / NOME_COPIAS

    if args.acao == "criar":
        if not banco.is_file():
            raise SystemExit(
                f"Base não encontrada em {pasta}.\n"
                "Use --pasta para apontar a pasta de dados (a que tem o pdv.db)."
            )
        alvo = criar_copia(banco, destino)
        info = inspecionar(alvo)
        print(f"Cópia criada: {alvo}")
        print(f"  {info['bytes'] / 1024:.0f} KB · esquema v{info['versao_esquema']} · {info['detalhe']}")
        print(f"  registros: {info['contagens']}")
        print(f"  manifesto: {alvo.name}.manifesto.json")
        if args.manter > 0:
            copias = listar(destino)
            for antiga in copias[args.manter :]:
                arquivo = destino / antiga["nome"]
                arquivo.unlink(missing_ok=True)
                arquivo.with_name(f"{arquivo.name}.manifesto.json").unlink(missing_ok=True)
                print(f"  removida (rotação): {arquivo.name}")
        return 0

    if args.acao == "listar":
        copias = listar(destino)
        if not copias:
            print(f"Nenhuma cópia em {destino}")
            return 0
        print(f"Cópias em {destino}:")
        for item in copias:
            estado = "íntegra" if item["integro"] else "COM PROBLEMAS"
            print(
                f"  {item['nome']}  {item['bytes'] / 1024:>7.0f} KB  "
                f"esquema v{item['versao_esquema']}  {estado}"
            )
            print(f"    {item.get('criado_em_utc', '')} · {item.get('rotulo', 'manual')}")
        return 0

    if args.acao in {"verificar", "recuperar", "restaurar"} and not args.arquivo:
        raise SystemExit(f"A ação '{args.acao}' precisa do caminho do arquivo .db")

    assert args.arquivo is not None
    alvo = Path(args.arquivo).expanduser()

    if args.acao == "verificar":
        info = inspecionar(alvo)
        print(f"Arquivo: {alvo}")
        print(f"Integridade: {'OK' if info['integro'] else 'FALHA'} ({info['detalhe']})")
        print(f"Esquema: v{info['versao_esquema']} · {info['bytes'] / 1024:.0f} KB")
        print(f"Registros: {info['contagens']}")
        return 0 if info["integro"] else 2

    if args.acao == "recuperar":
        saida = alvo.with_name(f"{alvo.stem}-recuperado.db")
        print(f"Recuperando {alvo} → {saida}")
        recuperar(alvo, saida)
        print("Pronto. Confira antes de usar: python backup_externo.py verificar", saida)
        return 0

    print(f"Restaurando {alvo} sobre {banco}")
    seguranca = restaurar(banco, alvo)
    print(f"Base anterior guardada como: {seguranca}")
    print("Abra o PDV e confira o fechamento do dia antes de voltar a vender.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
