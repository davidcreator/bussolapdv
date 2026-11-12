"""Mede a interface em vários tamanhos de janela e aponta o que estoura.

Por que existe: "responsivo" não é opinião. Este script abre a janela principal e a
área administrativa em resoluções reais de balcão e verifica, uma a uma:

* a janela **consegue** assumir o tamanho pedido (nenhum conteúdo força mais largura);
* nenhuma página da pilha pede mais largura do que a área de conteúdo oferece
  (é isso que "corta" um formulário em tela pequena);
* as tabelas não ficam com rolagem horizontal escondida pelo layout;
* a faixa da casca (compacta/média/ampla) e o número de colunas dos indicadores
  são os esperados.

Uso:
    QT_QPA_PLATFORM=offscreen PYTHONPATH=src python3 ferramentas/verificar_responsivo.py

Sai com código 1 se qualquer verificação falhar — serve para CI.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtWidgets import QApplication, QTableWidget, QWidget

from bussola_pdv.aplicacao.contexto import Contexto
from bussola_pdv.infra.massa_demo import popular, relogio_demo
from bussola_pdv.ui.admin.janela import JanelaAdmin
from bussola_pdv.ui.app import criar_aplicacao
from bussola_pdv.ui.janela import JanelaPrincipal
from bussola_pdv.ui.responsivo import (
    CLASSE_AMPLA,
    CLASSE_COMPACTA,
    CLASSE_MEDIA,
    MARGEM_COMPACTA,
    MARGEM_NORMAL,
    PONTO_COMPACTO,
    PONTO_MEDIO,
    colunas_para,
)

#: Resoluções que a loja realmente usa: monitor de balcão antigo até 4K.
TAMANHOS = ((800, 600), (1024, 768), (1280, 800), (1366, 768), (1920, 1080))


def _classe_esperada(largura: int) -> str:
    if largura < PONTO_COMPACTO:
        return CLASSE_COMPACTA
    if largura < PONTO_MEDIO:
        return CLASSE_MEDIA
    return CLASSE_AMPLA


def _maior_minimo(widget: QWidget) -> tuple[str, int]:
    """Pior (nome, largura mínima) entre a tela e todas as páginas da pilha."""
    pior = (widget.__class__.__name__, widget.minimumSizeHint().width())
    for filho in widget.findChildren(QWidget):
        if not filho.isVisibleTo(widget):
            continue
        if filho.objectName() == "barraLateral":
            continue  # a sidebar tem largura própria e já é contabilizada
        largura = filho.minimumSizeHint().width()
        if largura > pior[1]:
            pior = (f"{filho.__class__.__name__}[{filho.objectName() or '—'}]", largura)
    return pior


def _esperar(app: QApplication, segundos: float = 0.35) -> None:
    """Deixa o ajuste das colunas (com espera de 150 ms) acontecer de verdade."""
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        app.processEvents()


def verificar(janela: QWidget, rotulo: str, app: QApplication) -> list[str]:
    problemas: list[str] = []
    for largura, altura in TAMANHOS:
        janela.resize(largura, altura)
        app.processEvents()
        _esperar(app)
        real = janela.size()
        esperada = _classe_esperada(real.width())
        classe = janela.classe_da_casca
        if classe != esperada:
            problemas.append(
                f"{rotulo} {largura}×{altura}: faixa {classe!r}, esperada {esperada!r}"
            )
        if real.width() > largura or real.height() > altura:
            nome, minimo = _maior_minimo(janela)
            problemas.append(
                f"{rotulo} {largura}×{altura}: janela não encolheu até o pedido "
                f"(ficou {real.width()}×{real.height()}); maior mínimo: {nome} pede {minimo} px"
            )

        pilha = getattr(janela, "pilha", None)
        if pilha is not None:
            conteudo_largura = pilha.width()
            for indice in range(pilha.count()):
                pagina = pilha.widget(indice)
                if pagina is None:
                    continue
                pede = pagina.minimumSizeHint().width()
                if pede > conteudo_largura:
                    problemas.append(
                        f"{rotulo} {largura}×{altura}: página {indice} "
                        f"({pagina.__class__.__name__}) pede {pede} px de "
                        f"{conteudo_largura} px disponíveis"
                    )
                for tabela in pagina.findChildren(QTableWidget):
                    if not tabela.isVisibleTo(pagina):
                        continue
                    if tabela.width() > tabela.parentWidget().width():
                        problemas.append(
                            f"{rotulo} {largura}×{altura}: tabela {tabela.objectName() or '—'} "
                            f"mais larga que o pai"
                        )
                    for coluna in range(tabela.columnCount()):
                        if tabela.columnWidth(coluna) < tabela.horizontalHeader().minimumSectionSize():
                            problemas.append(
                                f"{rotulo} {largura}×{altura}: coluna {coluna} de "
                                f"{tabela.objectName() or 'tabela'} abaixo do mínimo legível"
                            )
                    transborda = (
                        tabela.horizontalHeader().length() > tabela.viewport().width()
                    )
                    if transborda and tabela.horizontalScrollBar().maximum() == 0:
                        problemas.append(
                            f"{rotulo} {largura}×{altura}: colunas passam da área visível "
                            "sem rolagem horizontal"
                        )
        margem_esperada = MARGEM_COMPACTA if esperada == CLASSE_COMPACTA else MARGEM_NORMAL
        moldura = getattr(janela, "moldura", None)
        if moldura is not None and moldura.layout() is not None:
            margem = moldura.layout().contentsMargins().left()
            if margem != margem_esperada:
                problemas.append(
                    f"{rotulo} {largura}×{altura}: margem {margem} px, esperada {margem_esperada} px"
                )
        if getattr(janela, "barra_lateral", None) is not None:
            recolhida = janela.barra_lateral.recolhida
            if esperada == CLASSE_COMPACTA and not recolhida:
                problemas.append(f"{rotulo} {largura}×{altura}: sidebar deveria estar recolhida")
            if esperada != CLASSE_COMPACTA and recolhida:
                problemas.append(f"{rotulo} {largura}×{altura}: sidebar recolhida sem motivo")
        print(
            f"  {largura}×{altura}: ficou {real.width()}×{real.height()} · faixa {classe} · "
            f"sidebar {'recolhida' if janela.barra_lateral.recolhida else 'aberta'} · "
            f"indicadores {colunas_para(real.width(), 4)} por linha"
        )
    return problemas


def main() -> int:
    banco = Path("/tmp/bussola_demo_responsivo.db")
    if banco.exists():
        banco.unlink()
    ctx = Contexto.abrir(banco, relogio=relogio_demo())
    popular(ctx)
    app = criar_aplicacao(["responsivo"])
    problemas: list[str] = []

    gerente = ctx.usuarios.por_login("gerente")
    janela = JanelaPrincipal(ctx, gerente)
    janela.show()
    print(f"JanelaPrincipal — mínimo declarado {janela.minimumWidth()}×{janela.minimumHeight()}")
    problemas += verificar(janela, "JanelaPrincipal", app)

    admin = JanelaAdmin(ctx, ctx.usuarios.por_login("admin"))
    admin.show()
    print(f"JanelaAdmin — mínimo declarado {admin.minimumWidth()}×{admin.minimumHeight()}")
    problemas += verificar(admin, "JanelaAdmin", app)

    janela.close()
    admin.close()
    ctx.fechar()

    if problemas:
        print("\nPROBLEMAS:")
        for problema in problemas:
            print(" -", problema)
        return 1
    print("\nOK: nenhuma tela cortada nas resoluções testadas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
