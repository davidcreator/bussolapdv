"""Linha de comando do Bússola PDV (sem dependência externa).

Uso::

    bussola init --banco dados/pdv.db --admin-login admin   # cria base + admin
    bussola demo --banco dados/demo.db                      # massa fictícia
    bussola info --banco dados/demo.db                      # versão/integridade
    bussola backup --banco dados/demo.db --destino copias/
    bussola fechamento --banco dados/demo.db --data 2026-11-11
    bussola ui --banco dados/demo.db                        # interface Qt
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

from . import __app_name__, __version__
from .aplicacao.autenticacao import ServicoAutenticacao
from .aplicacao.contexto import Contexto
from .aplicacao.relatorios import ServicoRelatorios
from .dominio.dinheiro import Dinheiro
from .dominio.erros import ErroBussola, ErroValidacao
from .dominio.relogio import RelogioFixo
from .dominio.usuario import Perfil
from .infra.massa_demo import popular, relogio_demo
from .infra.sqlite.conexao import abrir_conexao, fazer_backup, verificar_integridade


def _contexto(args: argparse.Namespace) -> Contexto:
    caminho = Path(args.banco)
    return Contexto.abrir(caminho)


def _exigir_banco(caminho: str) -> None:
    if not Path(caminho).exists():
        raise ErroValidacao(f"Banco não encontrado: {caminho}. Rode `bussola init` ou `bussola demo`.")


# -- comandos -------------------------------------------------------------------
def cmd_init(args: argparse.Namespace) -> int:
    destino = Path(args.banco)
    if destino.exists() and not args.forcar:
        raise ErroBussola(f"Já existe banco em {destino}. Use --forcar para recriar (perde dados).")
    if destino.exists() and args.forcar:
        destino.unlink()
    ctx = Contexto.abrir(destino)
    servico = ServicoAutenticacao(ctx)
    senha = args.senha or os.environ.get("BUSSOLA_SENHA_ADMIN") or getpass.getpass(
        "Senha do Admin Master (mín. 8 caracteres, com variedade): "
    )
    admin = servico.criar_usuario(
        login=args.admin_login,
        nome=args.admin_nome,
        senha=senha,
        perfil=Perfil.ADMIN_MASTER,
        criar_admin_inicial=True,
    )
    caixa_id = ctx.caixas.garantir_caixa(args.caixa, criado_em=ctx.agora().isoformat())
    print(f"{__app_name__} {__version__}")
    print(f"Banco criado: {destino.resolve()}")
    print(f"Esquema na versão: {ctx.versao_esquema()}")
    print(f"Admin Master: {admin.login} ({admin.perfil.rotulo}) — proprietário da instalação")
    print(f"Caixa cadastrado: {args.caixa} ({caixa_id})")
    ctx.fechar()
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    destino = Path(args.banco)
    if destino.exists() and not args.forcar:
        raise ErroBussola(f"Já existe banco em {destino}. Use --forcar para recriar.")
    if destino.exists():
        destino.unlink()
    ctx = Contexto.abrir(destino, relogio=relogio_demo())
    resumo = popular(ctx)
    print(f"{__app_name__} {__version__} — base de demonstração")
    print(f"Banco: {destino.resolve()}")
    print(json.dumps(resumo, ensure_ascii=False, indent=2, default=str))
    print("\nAtenção: dados fictícios. Não use para operação real.")
    ctx.fechar()
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    _exigir_banco(args.banco)
    ctx = Contexto.abrir(Path(args.banco))
    integro, problemas = ctx.conferir_integridade()
    verificacao = ctx.auditoria.verificar()
    print(f"{__app_name__} {__version__}")
    print(f"Banco: {Path(args.banco).resolve()}")
    print(f"Esquema: v{ctx.versao_esquema()}")
    print(f"Integridade SQLite: {'OK' if integro else 'FALHA'}")
    for problema in problemas:
        print(f"  - {problema}")
    print(f"Trilha de auditoria: {verificacao.mensagem}")
    print(f"Produtos: {len(ctx.produtos.listar(apenas_ativos=False, limite=10000))}")
    print(f"Clientes: {len(ctx.clientes.listar(limite=10000))}")
    turnos = ctx.caixas.turnos_abertos()
    print(f"Turnos abertos: {len(turnos)}")
    for turno in turnos:
        print(f"  - caixa {turno.caixa_id} desde {turno.aberto_em.isoformat()}")
    ctx.fechar()
    return 0


def cmd_backup(args: argparse.Namespace) -> int:
    _exigir_banco(args.banco)
    origem = abrir_conexao(args.banco, somente_leitura=True)
    destino = Path(args.destino)
    if destino.is_dir() or not destino.suffix:
        carimbo = ctx_stamp()
        destino = destino / f"bussola-{carimbo}.db"
    caminho = fazer_backup(origem, destino)
    origem.close()
    # Confere a cópia abrindo o arquivo gerado em modo somente leitura.
    copia = abrir_conexao(caminho, somente_leitura=True)
    integro, problemas = verificar_integridade(copia)
    copia.close()
    print(f"Backup gravado: {caminho.resolve()}")
    print(f"Verificação da cópia: {'OK' if integro else 'FALHA'}")
    for problema in problemas:
        print(f"  - {problema}")
    return 0 if integro else 1


def cmd_fechamento(args: argparse.Namespace) -> int:
    _exigir_banco(args.banco)
    ctx = Contexto.abrir(Path(args.banco))
    relatorio = ServicoRelatorios(ctx).fechamento_dia(args.data)
    resumo = relatorio["resumo"]
    print(f"Fechamento {args.data}")
    print(f"Cupons: {resumo['cupons']}  Faturamento: {Dinheiro(resumo['faturamento_centavos']).formatado()}")
    print(f"Ticket médio: {Dinheiro(resumo['ticket_medio_centavos']).formatado()}")
    for forma in relatorio["por_forma"]:
        print(
            f"  {forma['rotulo']:<22} aplicado {Dinheiro(forma['aplicado_centavos']).formatado():>12}"
            f"  pendente {Dinheiro(forma['pendente_centavos']).formatado():>12}"
        )
    conciliacao = relatorio["conciliacao"]
    print(f"Conciliação: {'OK' if conciliacao['conciliado'] else 'DIVERGENTE'} "
          f"(diferença {Dinheiro(conciliacao['diferenca_centavos']).formatado()})")
    print(f"Aviso: {conciliacao['aviso']}")
    ctx.fechar()
    return 0


def cmd_ui(args: argparse.Namespace) -> int:
    _exigir_banco(args.banco)
    from .ui.app import executar

    return executar(Path(args.banco))


def cmd_simular_dia(args: argparse.Namespace) -> int:
    """Mostra a data de negócio (fuso da loja) usada nas transações."""
    _exigir_banco(args.banco)
    ctx = Contexto.abrir(Path(args.banco), relogio=RelogioFixo(datetime.now(tz=UTC)))
    print(f"Data de negócio atual: {ctx.relogio.data_negocio()}")
    print(f"Fuso: {ctx.relogio.fuso()}")
    ctx.fechar()
    return 0


def ctx_stamp() -> str:
    return datetime.now(tz=UTC).astimezone().strftime("%Y%m%d-%H%M%S")


# -- parser ---------------------------------------------------------------------
def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bussola",
        description=f"{__app_name__} — PDV desktop offline (pré-alfa, não homologado).",
    )
    parser.add_argument("--version", action="version", version=f"{__app_name__} {__version__}")
    sub = parser.add_subparsers(dest="comando", required=True)

    p_init = sub.add_parser("init", help="cria a base e o administrador inicial")
    p_init.add_argument("--banco", default="dados/bussola.db")
    p_init.add_argument("--admin-login", default="admin")
    p_init.add_argument("--admin-nome", default="Administrador")
    p_init.add_argument("--senha", default=None, help="prefira a variável BUSSOLA_SENHA_ADMIN")
    p_init.add_argument("--caixa", default="Caixa 1")
    p_init.add_argument("--forcar", action="store_true")
    p_init.set_defaults(func=cmd_init)

    p_demo = sub.add_parser("demo", help="cria base com massa fictícia de demonstração")
    p_demo.add_argument("--banco", default="dados/demo.db")
    p_demo.add_argument("--forcar", action="store_true")
    p_demo.set_defaults(func=cmd_demo)

    p_info = sub.add_parser("info", help="mostra versão, integridade e auditoria")
    p_info.add_argument("--banco", default="dados/bussola.db")
    p_info.set_defaults(func=cmd_info)

    p_backup = sub.add_parser("backup", help="backup consistente com verificação")
    p_backup.add_argument("--banco", default="dados/bussola.db")
    p_backup.add_argument("--destino", default="copias/")
    p_backup.set_defaults(func=cmd_backup)

    p_fech = sub.add_parser("fechamento", help="relatório de fechamento do dia")
    p_fech.add_argument("--banco", default="dados/bussola.db")
    p_fech.add_argument("--data", required=True)
    p_fech.set_defaults(func=cmd_fechamento)

    p_ui = sub.add_parser("ui", help="abre a interface desktop")
    p_ui.add_argument("--banco", default="dados/bussola.db")
    p_ui.set_defaults(func=cmd_ui)

    p_sim = sub.add_parser("relogio", help="mostra a data de negócio do relógio")
    p_sim.add_argument("--banco", default="dados/bussola.db")
    p_sim.set_defaults(func=cmd_simular_dia)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = construir_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except ErroBussola as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        if getattr(exc, "detalhe", None):
            print(f"Detalhe: {exc.detalhe}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nInterrompido.", file=sys.stderr)
        return 130
    except sqlite3.Error as exc:
        print(f"Erro de banco de dados: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
