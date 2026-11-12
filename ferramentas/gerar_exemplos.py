"""Gera os relatórios de exemplo versionados em `docs/exemplos/`.

Usa a massa **fictícia** de demonstração — nenhum dado de loja real. Serve para
que quem avalia o projeto veja o formato do PDF e da planilha sem instalar nada.

Uso:

    QT_QPA_PLATFORM=offscreen PYTHONPATH=src python3 ferramentas/gerar_exemplos.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from bussola_pdv.aplicacao.contexto import Contexto
from bussola_pdv.aplicacao.exportacao import ServicoExportacao
from bussola_pdv.aplicacao.marca import ServicoMarca
from bussola_pdv.dominio.marca import Marca
from bussola_pdv.infra.massa_demo import popular, relogio_demo

DESTINO = RAIZ / "docs" / "exemplos"


def main() -> int:
    DESTINO.mkdir(parents=True, exist_ok=True)
    banco = Path("/tmp/bussola_demo_exemplos.db")
    if banco.exists():
        banco.unlink()
    contexto = Contexto.abrir(banco, relogio=relogio_demo())
    popular(contexto)
    master = contexto.usuarios.por_login("master")
    ServicoMarca(contexto).salvar(
        master,
        Marca(
            nome_fantasia="Loja de Demonstração",
            razao_social="Loja de Demonstração Ltda.",
            cnpj="12.345.678/0001-90",
            telefone="(11) 5555-0100",
            endereco="Rua das Bússolas, 100 — Jandira/SP",
            rodape_comprovante="Dados fictícios de demonstração.",
        ),
    )
    servico = ServicoExportacao(contexto)
    relatorio = servico.relatorio_fechamento("2026-11-11")
    for extensao in ("pdf", "xlsx"):
        caminho = DESTINO / f"fechamento-exemplo.{extensao}"
        servico.exportar(master, relatorio, caminho)
        print(f"gerado: {caminho.relative_to(RAIZ)} ({caminho.stat().st_size / 1024:.1f} kB)")
    contexto.fechar()
    print("Atenção: conteúdo fictício, gerado de `bussola demo`. Não é dado de loja real.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
