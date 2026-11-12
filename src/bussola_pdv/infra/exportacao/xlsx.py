"""Escritor de `.xlsx` com a biblioteca padrão — sem `openpyxl`, sem `pandas`.

Um `.xlsx` é um ZIP de XMLs. Gerar o mínimo necessário é menos código do que
parece e tira do projeto duas dependências grandes que só serviriam para isso.
O que este módulo entrega:

* aba **Resumo** (loja, filtros, indicadores, avisos, escopo);
* **uma aba por tabela**, com cabeçalho em negrito, filtro automático, painel
  congelado, larguras por coluna, moeda em reais (centavos ÷ 100) e datas como
  data de verdade do Excel (número serial + formato `dd/mm/aaaa`);
* metadados (título, autor, empresa) em `docProps`.

O que ele **não** faz, de propósito: fórmulas, gráficos, imagens, células
mescladas, tema/estilo condicional. Nada disso é necessário para conferir um
fechamento, e cada item ampliaria muito a superfície de erro.
"""

from __future__ import annotations

import zipfile
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

from ...dominio.relatorio import Relatorio, Tabela, TipoColuna
from .formato import numero, reais, texto

# Índices de estilo em `xl/styles.xml` (a ordem tem de casar com o arquivo).
ESTILO_PADRAO = 0
ESTILO_TITULO = 1  # negrito, 14 pt
ESTILO_ROTULO = 2  # negrito
ESTILO_CABECALHO = 3  # negrito sobre fundo claro, com borda
ESTILO_MOEDA = 4
ESTILO_INTEIRO = 5
ESTILO_DATA = 6
ESTILO_TEXTO_QUEBRA = 7

_CABECALHO = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
_NS = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
_NS_REL = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
_LIMITE_ABA = 31
_RESERVADOS_ABA = set('[]:*?/\\')


# -- conversões para o formato do Excel -----------------------------------------
def _serial_de_data(valor: object) -> float | None:
    """Data ISO → número serial do Excel (base 1899-12-30)."""
    if isinstance(valor, date):
        dias = valor.toordinal()
    elif isinstance(valor, str) and valor.strip():
        try:
            dias = date.fromisoformat(valor.strip()[:10]).toordinal()
        except ValueError:
            return None
    else:
        return None
    return float(dias - 693594)  # 1899-12-30 é o "dia zero" do Excel


# -- peças do pacote -------------------------------------------------------------
def _nome_de_aba(bruto: str, usados: set[str]) -> str:
    limpo = "".join("-" if caractere in _RESERVADOS_ABA else caractere for caractere in bruto)
    limpo = " ".join(limpo.split()).strip("'")[:_LIMITE_ABA] or "Planilha"
    candidato, sufixo = limpo, 2
    while candidato.lower() in usados:
        marca = f" ({sufixo})"
        candidato = limpo[: _LIMITE_ABA - len(marca)] + marca
        sufixo += 1
    usados.add(candidato.lower())
    return candidato


def _coluna_excel(indice: int) -> str:
    letras = ""
    indice += 1
    while indice:
        indice, resto = divmod(indice - 1, 26)
        letras = chr(65 + resto) + letras
    return letras


def _celula(linha: int, coluna: int, valor: object, tipo: TipoColuna) -> str:
    referencia = f"{_coluna_excel(coluna)}{linha}"
    if tipo is TipoColuna.MOEDA:
        return f'<c r="{referencia}" s="{ESTILO_MOEDA}"><v>{reais(valor):.2f}</v></c>'
    if tipo is TipoColuna.INTEIRO:
        return f'<c r="{referencia}" s="{ESTILO_INTEIRO}"><v>{numero(valor):.0f}</v></c>'
    if tipo is TipoColuna.DATA:
        serial = _serial_de_data(valor)
        if serial is not None:
            return f'<c r="{referencia}" s="{ESTILO_DATA}"><v>{serial:.0f}</v></c>'
    conteudo = escape(texto(valor))
    return (
        f'<c r="{referencia}" s="{ESTILO_PADRAO}" t="inlineStr">'
        f'<is><t xml:space="preserve">{conteudo}</t></is></c>'
    )


def _linha_simples(linha: int, rotulo: str, valor: object, tipo: TipoColuna) -> str:
    esquerda = (
        f'<c r="A{linha}" s="{ESTILO_ROTULO}" t="inlineStr">'
        f"<is><t>{escape(rotulo)}</t></is></c>"
    )
    return f'<row r="{linha}">{esquerda}{_celula(linha, 1, valor, tipo)}</row>'


def _aba_resumo(relatorio: Relatorio) -> str:
    linhas: list[str] = []
    numero = 1

    def adicionar(conteudo: str) -> None:
        nonlocal numero
        linhas.append(conteudo)
        numero += 1

    adicionar(
        f'<row r="{numero}"><c r="A{numero}" s="{ESTILO_TITULO}" t="inlineStr">'
        f"<is><t>{escape(relatorio.titulo)}</t></is></c></row>"
    )
    if relatorio.subtitulo:
        adicionar(
            f'<row r="{numero}"><c r="A{numero}" s="{ESTILO_PADRAO}" t="inlineStr">'
            f"<is><t>{escape(relatorio.subtitulo)}</t></is></c></row>"
        )
    adicionar("")
    for rotulo, valor in relatorio.identificacao:
        adicionar(_linha_simples(numero, rotulo, valor, TipoColuna.TEXTO))
    for rotulo, valor in relatorio.filtros:
        adicionar(_linha_simples(numero, rotulo, valor, TipoColuna.TEXTO))
    adicionar(
        _linha_simples(
            numero,
            "Gerado em",
            relatorio.gerado_em.strftime("%d/%m/%Y %H:%M"),
            TipoColuna.TEXTO,
        )
    )
    if relatorio.indicadores:
        adicionar("")
        for rotulo, valor in relatorio.indicadores:
            adicionar(_linha_simples(numero, rotulo, valor, TipoColuna.TEXTO))
    for tabela in relatorio.tabelas:
        adicionar("")
        adicionar(
            f'<row r="{numero}"><c r="A{numero}" s="{ESTILO_ROTULO}" t="inlineStr">'
            f"<is><t>{escape(tabela.titulo)}</t></is></c></row>"
        )
        adicionar(
            f'<row r="{numero}"><c r="A{numero}" s="{ESTILO_PADRAO}" t="inlineStr">'
            f"<is><t>{len(tabela.linhas)} linha(s) na aba \"{escape(tabela.titulo[:31])}\"</t>"
            f"</is></c></row>"
        )
    for aviso in relatorio.avisos:
        adicionar("")
        adicionar(
            f'<row r="{numero}"><c r="A{numero}" s="{ESTILO_TEXTO_QUEBRA}" t="inlineStr">'
            f"<is><t>! {escape(aviso)}</t></is></c></row>"
        )
    if relatorio.escopo:
        adicionar("")
        adicionar(
            f'<row r="{numero}"><c r="A{numero}" s="{ESTILO_TEXTO_QUEBRA}" t="inlineStr">'
            f"<is><t>{escape(relatorio.escopo)}</t></is></c></row>"
        )
    adicionar(
        f'<row r="{numero}"><c r="A{numero}" s="{ESTILO_PADRAO}" t="inlineStr">'
        f"<is><t>{escape(relatorio.documento)}</t></is></c></row>"
    )
    corpo = "".join(linha for linha in linhas if linha)
    return (
        f"{_CABECALHO}<worksheet {_NS} {_NS_REL}>"
        '<sheetViews><sheetView workbookViewId="0"/></sheetViews>'
        '<cols><col min="1" max="1" width="34" customWidth="1"/>'
        '<col min="2" max="2" width="46" customWidth="1"/></cols>'
        f'<sheetData>{corpo}</sheetData></worksheet>'
    )


def _aba_tabela(titulo: str, tabela: Tabela) -> str:
    larguras = "".join(
        f'<col min="{indice + 1}" max="{indice + 1}" width="{coluna.largura}" customWidth="1"/>'
        for indice, coluna in enumerate(tabela.colunas)
    )
    ultima_coluna = _coluna_excel(len(tabela.colunas) - 1)
    ultima_linha = len(tabela.linhas) + 2  # linha 1 = título, linha 2 = cabeçalho
    cabecalho = "".join(
        f'<c r="{_coluna_excel(indice)}2" s="{ESTILO_CABECALHO}" t="inlineStr">'
        f"<is><t>{escape(coluna.titulo)}</t></is></c>"
        for indice, coluna in enumerate(tabela.colunas)
    )
    linhas = [
        f'<row r="1"><c r="A1" s="{ESTILO_TITULO}" t="inlineStr">'
        f"<is><t>{escape(titulo)}</t></is></c></row>"
    ]
    linhas.append(f'<row r="2">{cabecalho}</row>')
    for indice_linha, valores in enumerate(tabela.linhas, start=3):
        celulas = "".join(
            _celula(indice_linha, indice_coluna, valor, coluna.tipo)
            for indice_coluna, (valor, coluna) in enumerate(zip(valores, tabela.colunas, strict=True))
        )
        linhas.append(f'<row r="{indice_linha}">{celulas}</row>')
    if tabela.nota:
        linhas.append(
            f'<row r="{ultima_linha + 2}"><c r="A{ultima_linha + 2}" s="{ESTILO_TEXTO_QUEBRA}" '
            f't="inlineStr"><is><t>{escape(tabela.nota)}</t></is></c></row>'
        )
    filtro = (
        f'<autoFilter ref="A2:{ultima_coluna}{max(ultima_linha, 2)}"/>' if tabela.linhas else ""
    )
    return (
        f"{_CABECALHO}<worksheet {_NS} {_NS_REL}>"
        '<sheetViews><sheetView workbookViewId="0">'
        '<pane ySplit="2" topLeftCell="A3" activePane="bottomLeft" state="frozen"/>'
        "</sheetView></sheetViews>"
        f"<cols>{larguras}</cols>"
        f"<sheetData>{''.join(linhas)}</sheetData>{filtro}"
        f'<pageMargins left="0.5" right="0.5" top="0.6" bottom="0.6" header="0.3" footer="0.3"/>'
        '<pageSetup paperSize="9" orientation="landscape"/>'
        "</worksheet>"
    )


def _estilos() -> str:
    return (
        f"{_CABECALHO}<styleSheet {_NS}>"
        '<numFmts count="2">'
        '<numFmt numFmtId="164" formatCode="&quot;R$&quot;\\ #,##0.00"/>'
        '<numFmt numFmtId="165" formatCode="dd/mm/yyyy"/>'
        "</numFmts>"
        '<fonts count="3">'
        '<font><sz val="11"/><name val="Calibri"/></font>'
        '<font><b/><sz val="14"/><name val="Calibri"/></font>'
        '<font><b/><sz val="11"/><name val="Calibri"/></font>'
        "</fonts>"
        '<fills count="3">'
        '<fill><patternFill patternType="none"/></fill>'
        '<fill><patternFill patternType="gray125"/></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FFD3E9F0"/><bgColor indexed="64"/>'
        "</patternFill></fill>"
        "</fills>"
        '<borders count="2"><border/>'
        '<border><left style="thin"><color rgb="FFDEE2E6"/></left>'
        '<right style="thin"><color rgb="FFDEE2E6"/></right>'
        '<top style="thin"><color rgb="FFDEE2E6"/></top>'
        '<bottom style="thin"><color rgb="FFDEE2E6"/></bottom></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="8">'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
        '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>'
        '<xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1"/>'
        '<xf numFmtId="0" fontId="2" fillId="2" borderId="1" xfId="0" '
        'applyFont="1" applyFill="1" applyBorder="1"/>'
        '<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
        '<xf numFmtId="165" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1">'
        '<alignment wrapText="1" vertical="top"/></xf>'
        "</cellXfs>"
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        "</styleSheet>"
    )


def _pacote(relatorio: Relatorio) -> list[tuple[str, str]]:
    usados = {"resumo"}
    abas = [("Resumo", _aba_resumo(relatorio))]
    for tabela in relatorio.tabelas:
        abas.append((_nome_de_aba(tabela.titulo, usados), _aba_tabela(tabela.titulo, tabela)))

    planilhas = "".join(
        f'<sheet name="{escape(nome)}" sheetId="{indice + 1}" r:id="rId{indice + 1}"/>'
        for indice, (nome, _xml) in enumerate(abas)
    )
    workbook = (
        f"{_CABECALHO}<workbook {_NS} {_NS_REL}>"
        f"<sheets>{planilhas}</sheets></workbook>"
    )
    rels_planilhas = "".join(
        f'<Relationship Id="rId{indice + 1}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        f'Target="worksheets/sheet{indice + 1}.xml"/>'
        for indice in range(len(abas))
    )
    total = len(abas) + 1
    rels_workbook = (
        f"{_CABECALHO}<Relationships "
        'xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f"{rels_planilhas}"
        f'<Relationship Id="rId{total}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
        'Target="styles.xml"/></Relationships>'
    )
    tipos = (
        f"{_CABECALHO}<Types "
        'xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        + "".join(
            f'<Override PartName="/xl/worksheets/sheet{indice + 1}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            for indice in range(len(abas))
        )
        + '<Override PartName="/xl/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        '<Override PartName="/docProps/core.xml" '
        'ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        '<Override PartName="/docProps/app.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
        "</Types>"
    )
    rels_raiz = (
        f"{_CABECALHO}<Relationships "
        'xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        '<Relationship Id="rId2" '
        'Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" '
        'Target="docProps/core.xml"/>'
        '<Relationship Id="rId3" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" '
        'Target="docProps/app.xml"/></Relationships>'
    )
    criado = relatorio.gerado_em.strftime("%Y-%m-%dT%H:%M:%SZ")
    core = (
        f"{_CABECALHO}<cp:coreProperties "
        'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        f"<dc:title>{escape(relatorio.titulo)}</dc:title>"
        f"<dc:subject>{escape(relatorio.subtitulo)}</dc:subject>"
        f"<dc:creator>{escape(relatorio.loja or 'Bússola Sistema PDV')}</dc:creator>"
        "<cp:lastModifiedBy>Bússola Sistema PDV</cp:lastModifiedBy>"
        f'<dcterms:created xsi:type="dcterms:W3CDTF">{criado}</dcterms:created>'
        f'<dcterms:modified xsi:type="dcterms:W3CDTF">{criado}</dcterms:modified>'
        "</cp:coreProperties>"
    )
    app = (
        f"{_CABECALHO}<Properties "
        'xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
        'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        "<Application>Bússola Sistema PDV Open Source</Application>"
        f"<Company>{escape(relatorio.loja or 'Bússola Sistema PDV')}</Company>"
        f"<TitlesOfParts><vt:vector size=\"{len(abas)}\" baseType=\"lpstr\">"
        + "".join(f"<vt:lpstr>{escape(nome)}</vt:lpstr>" for nome, _xml in abas)
        + "</vt:vector></TitlesOfParts></Properties>"
    )

    partes = [
        ("[Content_Types].xml", tipos),
        ("_rels/.rels", rels_raiz),
        ("docProps/core.xml", core),
        ("docProps/app.xml", app),
        ("xl/workbook.xml", workbook),
        ("xl/_rels/workbook.xml.rels", rels_workbook),
        ("xl/styles.xml", _estilos()),
    ]
    for indice, (_nome, xml) in enumerate(abas, start=1):
        partes.append((f"xl/worksheets/sheet{indice}.xml", xml))
    return partes


def escrever(relatorio: Relatorio, destino: Path) -> Path:
    """Grava o `.xlsx` em `destino` (criando a pasta) e devolve o caminho."""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_name(destino.name + ".tmp")
    with zipfile.ZipFile(temporario, "w", compression=zipfile.ZIP_DEFLATED) as pacote:
        for nome, conteudo in _pacote(relatorio):
            pacote.writestr(nome, conteudo.encode("utf-8"))
    temporario.replace(destino)
    return destino
