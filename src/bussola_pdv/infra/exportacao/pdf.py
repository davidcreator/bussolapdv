"""Escritor de PDF usando o Qt que já está no projeto.

Por que Qt e não `reportlab`/`weasyprint`: o PySide6 já é dependência de execução
do PDV, compila no Windows sem biblioteca de sistema extra e resolve paginação,
quebra de linha, acentuação e fontes. Uma dependência a menos para quem instala.

Como o desenho é feito:

* o conteúdo vira HTML de rico texto (`QTextDocument`), com tabelas de verdade;
* o documento é **paginado à mão** (`drawContents` por página), para caber
  cabeçalho e rodapé com numeração — o `print_()` do Qt não permite isso;
* cada página recebe o nome da loja, a data de geração e "página X de Y" no
  rodapé, além do aviso de que é documento interno.

Fora do escopo, de propósito: assinatura digital, PDF/A, marca d'água e logos
grandes. O PDF aqui é comprovante de conferência, não documento fiscal.
"""

from __future__ import annotations

import html
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from ...dominio.relatorio import Relatorio, Tabela, TipoColuna, carimbo_do_dia
from .formato import celula

if TYPE_CHECKING:  # pragma: no cover - só para o verificador de tipos
    from PySide6.QtGui import QPainter, QPdfWriter

A4_LARGURA_MM = 210
A4_ALTURA_MM = 297
MARGEM_MM = 14
RESOLUCAO = 300
ALTURA_RODAPE = 34  # pixels de dispositivo reservados ao rodapé
COR_DESTAQUE = "#0D6EFD"
COR_TEXTO = "#212529"
COR_SUAVE = "#5F686F"  # mesmo cinza legível da interface (WCAG AA)
COR_BORDA = "#DEE2E6"
COR_ZEBRA = "#F4F6F9"


#: Referência viva ao QGuiApplication criado aqui. Sem isso o objeto é coletado
#: ao fim da exportação e a próxima janela Qt do processo aborta com
#: "QWidget: Must construct a QApplication before a QWidget" — crash que só
#: aparece quando PDF e interface convivem no mesmo processo (CLI e testes).
_APLICACAO = None


def _garantir_aplicacao() -> object:
    """QTextDocument precisa de uma aplicação Qt viva.

    Cria-se `QApplication` (e não `QGuiApplication`) de propósito: um processo
    que exporta PDF pelo terminal e depois abre janela — caso dos testes e do
    `bussola ui` na mesma sessão — precisa de uma instância que também sirva
    para widgets. Criar a versão "só GUI" aqui faz a janela seguinte abortar.
    """
    global _APLICACAO
    from PySide6.QtWidgets import QApplication

    existente = QApplication.instance()
    if existente is not None:
        return existente
    if not os.environ.get("DISPLAY") and sys.platform not in ("win32", "darwin"):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _APLICACAO = QApplication([sys.argv[0] if sys.argv else "bussola-pdf"])
    return _APLICACAO


def _escrever(valor: object) -> str:
    """Escapa para HTML preservando quebras de linha do texto."""
    return html.escape(str(valor), quote=False).replace("\n", "<br>")


def _tabela_de_pares(pares: tuple[tuple[str, str], ...]) -> str:
    if not pares:
        return ""
    linhas = "".join(
        f'<tr><td width="34%" bgcolor="{COR_ZEBRA}"><b>{_escrever(rotulo)}</b></td>'
        f'<td bgcolor="#FFFFFF">{_escrever(valor)}</td></tr>'
        for rotulo, valor in pares
    )
    return (
        f'<table width="100%" cellspacing="0" cellpadding="4" border="0" '
        f'style="border: 1px solid {COR_BORDA};">{linhas}</table>'
    )


def _tabela_de_indicadores(pares: tuple[tuple[str, str], ...]) -> str:
    if not pares:
        return ""
    celulas = "".join(
        f'<td width="{100 // max(len(pares), 1)}%" bgcolor="{COR_ZEBRA}" align="center">'
        f'<font size="2" color="{COR_SUAVE}">{_escrever(rotulo)}</font><br>'
        f'<b><font size="4">{_escrever(valor)}</font></b></td>'
        for rotulo, valor in pares
    )
    return (
        f'<table width="100%" cellspacing="0" cellpadding="6" border="0"><tr>{celulas}</tr></table>'
    )


def _tabela_dados(tabela: Tabela, indice: int) -> str:
    total = sum(coluna.largura for coluna in tabela.colunas)
    larguras = [max(6, round(100 * coluna.largura / total)) for coluna in tabela.colunas]
    cabecalho = "".join(
        f'<th width="{largura}%" bgcolor="{COR_DESTAQUE}" align="'
        f'{"right" if coluna.numerica else "left"}">'
        f'<font color="#FFFFFF">{_escrever(coluna.titulo)}</font></th>'
        for coluna, largura in zip(tabela.colunas, larguras, strict=True)
    )
    corpo = []
    for posicao, valores in enumerate(tabela.linhas):
        fundo = "#FFFFFF" if posicao % 2 == 0 else COR_ZEBRA
        celulas = "".join(
            f'<td bgcolor="{fundo}" align="{"right" if coluna.numerica else "left"}">'
            f"{_escrever(celula(valor, coluna.tipo))}</td>"
            for valor, coluna in zip(valores, tabela.colunas, strict=True)
        )
        corpo.append(f"<tr>{celulas}</tr>")
    if not corpo:
        corpo.append(
            f'<tr><td colspan="{len(tabela.colunas)}" bgcolor="#FFFFFF" align="center">'
            f"<font color=\"{COR_SUAVE}\">Sem registros.</font></td></tr>"
        )
    nota = (
        f'<p><font size="2" color="{COR_SUAVE}">{_escrever(tabela.nota)}</font></p>'
        if tabela.nota
        else ""
    )
    return (
        f'<h3 style="margin-bottom: 2px;"><font color="{COR_TEXTO}">'
        f"{_escrever(str(indice))}. {_escrever(tabela.titulo)}</font></h3>"
        f'<table width="100%" cellspacing="0" cellpadding="4" border="1" '
        f'style="border-collapse: collapse; border: 1px solid {COR_BORDA};">'
        f"<tr>{cabecalho}</tr>{''.join(corpo)}</table>{nota}"
    )


def montar_html(relatorio: Relatorio) -> str:
    partes = [
        f'<p style="margin: 0;"><font size="2" color="{COR_SUAVE}">'
        f"{_escrever(relatorio.loja or 'Bússola Sistema PDV')}</font></p>",
        f'<h1 style="margin: 0;"><font color="{COR_TEXTO}">{_escrever(relatorio.titulo)}</font></h1>',
    ]
    if relatorio.subtitulo:
        partes.append(
            f'<p style="margin-top: 0;"><font color="{COR_SUAVE}">'
            f"{_escrever(relatorio.subtitulo)}</font></p>"
        )
    partes.append(f'<hr style="border: 1px solid {COR_DESTAQUE};">')
    if relatorio.identificacao:
        partes.append(_tabela_de_pares(relatorio.identificacao) + "<br>")
    filtros = (*relatorio.filtros, ("Gerado em", carimbo_do_dia(relatorio.gerado_em)))
    partes.append(_tabela_de_pares(filtros) + "<br>")
    if relatorio.indicadores:
        partes.append(_tabela_de_indicadores(relatorio.indicadores) + "<br>")
    for indice, tabela in enumerate(relatorio.tabelas, start=1):
        partes.append(_tabela_dados(tabela, indice))
    for aviso in relatorio.avisos:
        partes.append(
            f'<p style="margin: 2px 0;"><font color="#B02A37">! {_escrever(aviso)}</font></p>'
        )
    if relatorio.escopo:
        partes.append(f'<p><font size="2" color="{COR_SUAVE}">{_escrever(relatorio.escopo)}</font></p>')
    partes.append(f'<p><font size="2">{_escrever(relatorio.documento)}</font></p>')
    return "".join(partes)


def escrever(relatorio: Relatorio, destino: Path) -> Path:
    """Grava o PDF em `destino` e devolve o caminho."""
    from PySide6.QtCore import QMarginsF, QRectF, QSizeF
    from PySide6.QtGui import QFont, QPageLayout, QPageSize, QPainter, QPdfWriter, QTextDocument

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    _garantir_aplicacao()

    escritor = QPdfWriter(str(destino))
    escritor.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    escritor.setPageMargins(
        QMarginsF(MARGEM_MM, MARGEM_MM, MARGEM_MM, MARGEM_MM + 4),
        QPageLayout.Unit.Millimeter,
    )
    escritor.setResolution(RESOLUCAO)
    escritor.setTitle(relatorio.titulo)
    escritor.setCreator("Bússola Sistema PDV Open Source")
    escritor.setAuthor(relatorio.loja or "Bússola Sistema PDV")

    documento = QTextDocument()
    documento.setDefaultFont(QFont("Segoe UI", 9))
    documento.setHtml(montar_html(relatorio))
    altura_pagina = escritor.height() - ALTURA_RODAPE
    documento.setPageSize(QSizeF(escritor.width(), altura_pagina))

    pintor = QPainter(escritor)
    try:
        total = max(documento.pageCount(), 1)
        for pagina in range(total):
            if pagina:
                escritor.newPage()
            pintor.save()
            pintor.translate(0, -pagina * altura_pagina)
            documento.drawContents(
                pintor, QRectF(0, pagina * altura_pagina, escritor.width(), altura_pagina)
            )
            pintor.restore()
            _rodape(pintor, escritor, relatorio, pagina + 1, total, altura_pagina)
    finally:
        pintor.end()
    return destino


def _rodape(
    pintor: QPainter,
    escritor: QPdfWriter,
    relatorio: Relatorio,
    pagina: int,
    total: int,
    topo: float,
) -> None:
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QPen

    fonte = QFont("Segoe UI", 7)
    pintor.setFont(fonte)
    pintor.setPen(QPen(QColor(COR_BORDA), 1))
    pintor.drawLine(0, int(topo) + 6, escritor.width(), int(topo) + 6)
    pintor.setPen(QPen(QColor(COR_SUAVE)))
    esquerda = QRectF(0, topo + 10, escritor.width() * 0.74, ALTURA_RODAPE - 10)
    direita = QRectF(escritor.width() * 0.74, topo + 10, escritor.width() * 0.26, ALTURA_RODAPE - 10)
    agora = datetime.now(tz=UTC)
    pintor.drawText(
        esquerda,
        int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
        f"{relatorio.loja or 'Bússola Sistema PDV'} · gerado em {carimbo_do_dia(agora)}",
    )
    pintor.drawText(
        direita,
        int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
        f"página {pagina} de {total}",
    )


__all__ = ["TipoColuna", "escrever", "montar_html"]
