"""Linha de comando do Bússola PDV (sem dependência externa).

Uso::

    bussola init --banco dados/pdv.db --admin-login admin   # cria base + admin
    bussola demo --banco dados/demo.db                      # massa fictícia
    bussola info --banco dados/demo.db                      # versão/integridade
    bussola backup --banco dados/demo.db --destino copias/
    bussola fechamento --banco dados/demo.db --data 2026-11-11
    bussola exportar --banco dados/demo.db --tipo fechamento --data 2026-11-11 \
        --formato pdf --login master                        # relatório em arquivo
    bussola ui --banco dados/demo.db                        # interface Qt
    bussola dados                                           # onde a instalação guarda dados
    bussola dados --definir "D:\\PDV" --mover               # muda a pasta dos dados
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
from .aplicacao.exportacao import ServicoExportacao
from .aplicacao.impressao import ServicoImpressao
from .aplicacao.relatorios import ServicoRelatorios
from .caminhos import (
    banco_em,
    definir_diretorio_de_dados,
    diretorio_de_dados,
    diretorio_de_dados_padrao,
    origem_do_diretorio,
    pasta_de_copias,
    pasta_de_logs,
    pasta_de_relatorios,
    voltar_ao_diretorio_padrao,
)
from .dominio.dinheiro import Dinheiro
from .dominio.erros import ErroBussola, ErroValidacao
from .dominio.impressao import PERFIS_PAPEL, Papel
from .dominio.relatorio import Relatorio
from .dominio.relogio import RelogioFixo
from .dominio.usuario import Acao, Perfil
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


def cmd_exportar(args: argparse.Namespace) -> int:
    """Exporta um relatório em Excel ou PDF, autenticando quem pede.

    A autenticação não é burocracia: exportar tira dado da loja, então o CLI
    exige um usuário com `EXPORTAR_DADOS` e registra o evento na auditoria —
    exatamente como a interface. A senha vem de `BUSSOLA_SENHA` (útil em script)
    ou é perguntada no terminal.
    """
    _exigir_banco(args.banco)
    formato = args.formato.lower().lstrip(".")
    if formato not in ("xlsx", "pdf"):
        raise ErroValidacao("Formato inválido: use xlsx ou pdf.")

    ctx = Contexto.abrir(Path(args.banco))
    try:
        senha = os.environ.get("BUSSOLA_SENHA") or getpass.getpass(f"Senha de {args.login}: ")
        usuario = ServicoAutenticacao(ctx).entrar(args.login, senha).usuario
        servico = ServicoExportacao(ctx)
        relatorio = _montar_relatorio(servico, args)
        destino = Path(args.destino) if args.destino else None
        if destino is None:
            from .caminhos import pasta_de_relatorios

            destino = pasta_de_relatorios() / relatorio.nome_de_arquivo(formato)
        elif destino.is_dir():
            destino = destino / relatorio.nome_de_arquivo(formato)
        elif destino.suffix.lower() != f".{formato}":
            destino = destino.with_suffix(f".{formato}")
        caminho = servico.exportar(usuario, relatorio, destino)
    finally:
        ctx.fechar()

    print(f"{__app_name__} {__version__}")
    print(f"Relatório: {relatorio.titulo}")
    print(f"Formato: {formato} · linhas: {relatorio.linhas}")
    print(f"Arquivo: {caminho.resolve()}")
    print("Documento interno de conferência: não é documento fiscal.")
    return 0


def _montar_relatorio(servico: ServicoExportacao, args: argparse.Namespace) -> Relatorio:
    tipo = args.tipo
    if tipo == "fechamento":
        if not args.data:
            raise ErroValidacao("Informe --data AAAA-MM-DD para o fechamento.")
        return servico.relatorio_fechamento(args.data)
    if tipo == "vendas":
        if not (args.de and args.ate):
            raise ErroValidacao("Informe --de e --ate (AAAA-MM-DD) para vendas.")
        return servico.relatorio_vendas(args.de, args.ate)
    if tipo == "catalogo":
        return servico.relatorio_catalogo(args.busca or "")
    if tipo == "auditoria":
        return servico.relatorio_auditoria(args.limite)
    if tipo == "crediario":
        return servico.relatorio_crediario(incluir_pagos=args.incluir_pagos)
    if tipo == "clientes":
        return servico.relatorio_clientes(args.busca or "")
    if tipo == "estoque":
        return servico.relatorio_estoque(args.busca or "")
    if tipo == "turno":
        return servico.relatorio_turno(args.turno or None)
    raise ErroValidacao(f"Tipo de relatório desconhecido: {tipo}.")


def cmd_imprimir(args: argparse.Namespace) -> int:
    """Manda um cupom ou relatório para o papel — ou para um arquivo.

    Serve ao caso real de suporte e de retaguarda: "o cupom 1-000012 saiu errado",
    "imprime a conferência do turno para o contador", "salva o fechamento em PDF
    nesse pendrive". Faz o mesmo que a interface, com a mesma permissão e a mesma
    auditoria — a impressão sempre passa por `ServicoImpressao`.

    Sem `--saida`, imprime na impressora configurada. Com `--saida`, grava PDF ou
    TXT (a extensão decide) e **não** gasta papel.
    """
    _exigir_banco(args.banco)
    ctx = Contexto.abrir(Path(args.banco))
    try:
        senha = os.environ.get("BUSSOLA_SENHA") or getpass.getpass(f"Senha de {args.login}: ")
        usuario = ServicoAutenticacao(ctx).entrar(args.login, senha).usuario
        impressao = ServicoImpressao(ctx)
        papel = Papel(args.papel) if args.papel else None

        if args.tipo == "cupom":
            if not args.venda:
                raise ErroValidacao("Informe --venda (id ou rótulo do cupom, ex.: 1-000012).")
            venda = impressao.venda_por_referencia(args.venda)
            documento = impressao.comprovante_da_venda(venda, papel=papel, copia=True)
        else:
            relatorio = _montar_relatorio(ServicoExportacao(ctx), args)
            documento = impressao.documento_de_relatorio(relatorio, papel=papel, rotulo=args.tipo)

        if args.saida:
            destino = Path(args.saida)
            formato = destino.suffix.lstrip(".").lower() or "pdf"
            if formato not in ("pdf", "txt"):
                raise ErroValidacao("A saída aceita .pdf ou .txt.")
            gravado = impressao.salvar(documento, destino.parent, formato=formato)
            if gravado != destino:
                gravado.replace(destino)
            print(f"{__app_name__} {__version__}")
            print(f"Documento: {documento.titulo}")
            print(f"Papel: {PERFIS_PAPEL[documento.papel].rotulo} · linhas: {len(documento.layout())}")
            print(f"Arquivo: {destino.resolve()} (nada foi impresso)")
        else:
            resultado = impressao.despachar(
                documento, ator=usuario, permissao=Acao.CUPOM_REIMPRIMIR
                if args.tipo == "cupom"
                else Acao.EXPORTAR_DADOS
            )
            print(f"{__app_name__} {__version__}")
            print(f"Documento: {documento.titulo}")
            print(f"Enviado para: {resultado.destino}")
            print(f"Papel: {resultado.papel.value} · linhas: {resultado.linhas}")
        print("Documento interno: não é documento fiscal.")
    finally:
        ctx.fechar()
    return 0


def cmd_dados(args: argparse.Namespace) -> int:
    """Mostra — e opcionalmente muda — a pasta onde a instalação guarda dados.

    Existe porque a escolha feita no primeiro uso é invisível depois: quem liga o
    suporte precisa de um comando que diga **onde** está a base e **por que** está
    ali (ambiente, escolha da instalação ou padrão do sistema).
    """
    if getattr(args, "padrao", False):
        voltar_ao_diretorio_padrao()
        print(f"Pasta de dados voltou ao padrão: {diretorio_de_dados_padrao()}")
    if args.definir:
        pasta = definir_diretorio_de_dados(args.definir)
        print(f"Pasta de dados definida: {pasta}")
        if args.mover:
            _mover_dados(args.origem or None, pasta)

    pasta = diretorio_de_dados()
    print(f"{__app_name__} {__version__}")
    print(f"Pasta de dados: {pasta}")
    print(f"Origem da escolha: {origem_do_diretorio()}")
    print(f"Banco: {banco_em(pasta)}")
    print(f"Cópias: {pasta_de_copias()}")
    print(f"Relatórios: {pasta_de_relatorios()}")
    print(f"Logs: {pasta_de_logs()}")
    return 0


def _mover_dados(origem: str | None, destino: Path) -> None:
    """Copia a base e as subpastas para a pasta nova, conferindo a integridade.

    A base é copiada pela **API de backup do SQLite** (segura com WAL ativo), e não
    com `copy2`: copiar o `.db` com o programa aberto pode deixar de fora o que
    está no `-wal`. Cópias e relatórios vão por `shutil`. Nada é apagado da origem:
    quem chama decide isso depois de conferir.
    """
    import shutil

    from_ = Path(origem).expanduser() if origem else diretorio_de_dados_padrao()
    if not from_.exists():
        raise ErroValidacao(f"Pasta de origem não existe: {from_}")
    if from_.resolve() == destino.resolve():
        raise ErroValidacao("Origem e destino são a mesma pasta.")
    origem_db = banco_em(from_)
    if origem_db.exists():
        conexao = abrir_conexao(origem_db, somente_leitura=True)
        try:
            linha = conexao.execute("PRAGMA integrity_check").fetchone()
            integro = bool(linha) and str(linha[0]).lower() == "ok"
            if not integro:
                raise ErroValidacao(
                    "A base de origem não passou na checagem de integridade: "
                    + (str(linha[0]) if linha else "sem resposta")
                )
            fazer_backup(conexao, banco_em(destino))
        finally:
            conexao.close()
    for item in from_.iterdir():
        if item.name == "logs" or item.name.startswith("pdv.db"):
            continue  # log é da máquina; a base já foi copiada pela API de backup
        alvo = destino / item.name
        if item.is_dir():
            shutil.copytree(item, alvo, dirs_exist_ok=True)
        elif item.is_file():
            shutil.copy2(item, alvo)
    print(f"Dados copiados de {from_} para {destino} (o original não foi apagado).")


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

    p_export = sub.add_parser("exportar", help="exporta relatório em Excel (.xlsx) ou PDF")
    p_export.add_argument("--banco", default="dados/bussola.db")
    p_export.add_argument(
        "--tipo",
        default="fechamento",
        choices=[
            "fechamento",
            "vendas",
            "catalogo",
            "auditoria",
            "crediario",
            "clientes",
            "estoque",
            "turno",
        ],
    )
    p_export.add_argument("--formato", default="xlsx", choices=["xlsx", "pdf"])
    p_export.add_argument("--destino", default=None, help="arquivo ou pasta de saída")
    p_export.add_argument("--data", default=None, help="data de negócio (fechamento)")
    p_export.add_argument("--de", default=None, help="início do período (vendas)")
    p_export.add_argument("--ate", default=None, help="fim do período (vendas)")
    p_export.add_argument(
        "--busca", default="", help="filtro de descrição (catálogo, estoque, clientes)"
    )
    p_export.add_argument(
        "--turno", default=None, help="id do turno (padrão: turnos abertos)"
    )
    p_export.add_argument(
        "--incluir-pagos",
        action="store_true",
        dest="incluir_pagos",
        help="inclui títulos já recebidos no crediário",
    )
    p_export.add_argument("--limite", type=int, default=500, help="eventos (auditoria)")
    p_export.add_argument("--login", required=True, help="usuário que assina a exportação")
    p_export.set_defaults(func=cmd_exportar)

    p_imprimir = sub.add_parser(
        "imprimir", help="imprime cupom ou relatório (bobina 58/80 mm ou folha A4)"
    )
    p_imprimir.add_argument("--banco", default="dados/bussola.db")
    p_imprimir.add_argument(
        "--tipo",
        default="cupom",
        choices=[
            "cupom",
            "fechamento",
            "vendas",
            "catalogo",
            "auditoria",
            "crediario",
            "clientes",
            "estoque",
            "turno",
        ],
    )
    p_imprimir.add_argument("--venda", default=None, help="id ou rótulo do cupom (ex.: 1-000012)")
    p_imprimir.add_argument(
        "--papel", default=None, choices=["BOBINA_58", "BOBINA_80", "A4"],
        help="padrão: o papel configurado nos parâmetros",
    )
    p_imprimir.add_argument(
        "--saida", default=None, help="grava .pdf ou .txt em vez de imprimir"
    )
    p_imprimir.add_argument("--data", default=None, help="data de negócio (fechamento)")
    p_imprimir.add_argument("--de", default=None, help="início do período (vendas)")
    p_imprimir.add_argument("--ate", default=None, help="fim do período (vendas)")
    p_imprimir.add_argument("--busca", default="", help="filtro (catálogo, estoque, clientes)")
    p_imprimir.add_argument("--turno", default=None, help="id do turno (padrão: abertos)")
    p_imprimir.add_argument(
        "--incluir-pagos", action="store_true", dest="incluir_pagos",
        help="inclui títulos já recebidos no crediário",
    )
    p_imprimir.add_argument("--limite", type=int, default=500, help="eventos (auditoria)")
    p_imprimir.add_argument("--login", required=True, help="usuário que assina a impressão")
    p_imprimir.set_defaults(func=cmd_imprimir)

    p_ui = sub.add_parser("ui", help="abre a interface desktop")
    p_ui.add_argument("--banco", default="dados/bussola.db")
    p_ui.set_defaults(func=cmd_ui)

    p_dados = sub.add_parser("dados", help="mostra ou muda a pasta de dados da instalação")
    p_dados.add_argument("--definir", default=None, help="nova pasta de dados (ex.: D:\\PDV)")
    p_dados.add_argument(
        "--mover",
        action="store_true",
        help="copia a base e as subpastas da pasta antiga para a nova (não apaga a antiga)",
    )
    p_dados.add_argument(
        "--origem", default=None, help="pasta antiga a copiar (padrão: pasta padrão do sistema)"
    )
    p_dados.add_argument(
        "--padrao", action="store_true", help="descarta a pasta escolhida e volta ao padrão"
    )
    p_dados.set_defaults(func=cmd_dados)

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
