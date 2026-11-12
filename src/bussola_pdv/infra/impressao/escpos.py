"""Renderização ESC/POS: os bytes que a impressora térmica entende.

Duas formas de usar a térmica existem no mercado e o projeto suporta as duas:

* **driver do fabricante** (o normal): a impressora aparece como qualquer outra no
  Windows/Linux e o sistema pinta o cupom como página — é o caminho padrão, feito
  por `infra/impressao/papel.py`;
* **ESC/POS direto** (este módulo): os bytes de comando vão crus para a porta da
  impressora. Vantagens: velocidade, corte de papel automático, gaveta e código de
  barras nativo (sem virar imagem). Custo: depende do modelo aceitar o conjunto de
  comandos e da tabela de caracteres configurada.

O conjunto usado aqui é o mínimo comum das térmicas de 58 e 80 mm (Epson TM-T20,
Elgin i9, Bematech MP-4200, Knup, etc.): `ESC @` (inicializa), `ESC t` (tabela de
caracteres), `ESC a` (alinhamento), `ESC E` (negrito), `GS !` (duplo), `GS h`/`GS w`
/`GS k 4` (CODE 39), `ESC d` (avança), `GS V` (corta) e `ESC p` (pulso da gaveta).

**Limite honesto:** este código foi escrito a partir da especificação ESC/POS e
testado byte a byte aqui; a impressão em hardware real não foi verificada nesta
entrega. Modelos que trocam a tabela de caracteres podem imprimir acento errado —
por isso o texto é transliterado para o que a tabela suporta, e a configuração
`impressao.motor` permite voltar ao driver do sistema a qualquer momento.
"""

from __future__ import annotations

import unicodedata

from ...dominio.impressao import Alinhamento, DocumentoImpresso, Enfase

# -- comandos -------------------------------------------------------------
ESC = b"\x1b"
GS = b"\x1d"
INICIALIZAR = ESC + b"@"  # ESC @
TABELA_1252 = ESC + b"t" + bytes([16])  # ESC t 16 = WPC1252
NEGRITO_ON = ESC + b"E" + bytes([1])
NEGRITO_OFF = ESC + b"E" + bytes([0])
DUPLO_ON = GS + b"!" + bytes([0x11])  # largura e altura dobradas
DUPLO_OFF = GS + b"!" + bytes([0x00])
CORTAR = GS + b"V" + bytes([66, 0])  # GS V 66 0 — corte parcial com avanço
GAVETA = ESC + b"p" + bytes([0, 25, 250])  # ESC p 0 25 250 — pulso de 50/500 ms

ALINHAMENTO_ESCPOS = {
    Alinhamento.ESQUERDA: 0,
    Alinhamento.CENTRO: 1,
    Alinhamento.DIREITA: 2,
}

#: Trocas para o que a tabela de caracteres da térmica costuma ter.
_SUBSTITUICOES = {
    "×": "x",
    "·": "|",
    "—": "-",
    "–": "-",
    "“": '"',
    "”": '"',
    "‘": "'",
    "’": "'",
    "→": "->",
    "≥": ">=",
    "≤": "<=",
    "R$": "R$",
}

#: Altura e largura do código de barras nativo (`GS h` e `GS w`).
ALTURA_BARRAS_PONTOS = 96
LARGURA_BARRAS = 3  # 3 dots por módulo: legível em 203 dpi sem estourar a bobina


def transliterar(texto: str) -> str:
    """Deixa o texto dentro do que a tabela de caracteres da térmica representa.

    Acentos não existem em todas as tabelas e um acento mal codificado imprime
    lixo no meio do cupom. Aqui o texto perde o acento (mantendo a letra) e os
    símbolos tipográficos viram equivalentes simples.
    """
    for simbolo, troca in _SUBSTITUICOES.items():
        texto = texto.replace(simbolo, troca)
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def _codificar(texto: str) -> bytes:
    """Texto → bytes na tabela da impressora, com rede de segurança."""
    limpo = "".join(c for c in str(texto) if c >= " " or c == "\t")
    try:
        return transliterar(limpo).encode("cp1252", errors="strict")
    except UnicodeEncodeError:
        return transliterar(limpo).encode("cp1252", errors="replace")


def _alinhamento(n: int) -> bytes:
    return ESC + b"a" + bytes([n])


def _avancar(linhas: int) -> bytes:
    return ESC + b"d" + bytes([max(0, min(255, linhas))])


def _barras(dado: str) -> bytes:
    """CODE 39 nativo: `GS h`, `GS w` e `GS k 4 <dado> NUL`."""
    return (
        GS
        + b"h"
        + bytes([ALTURA_BARRAS_PONTOS])
        + GS
        + b"w"
        + bytes([LARGURA_BARRAS])
        + GS
        + b"k"
        + bytes([4])
        + _codificar(dado)
        + b"\x00"
    )


def renderizar(
    documento: DocumentoImpresso,
    *,
    abrir_gaveta: bool = False,
    cortar: bool = True,
    avancar_linhas: int = 4,
) -> bytes:
    """Documento → bytes prontos para enviar crus à impressora."""
    partes: list[bytes] = [INICIALIZAR, TABELA_1252]
    alinhamento_atual: int | None = None
    negrito = False
    duplo = False

    for linha in documento.layout():
        if linha.eh_codigo_de_barras:
            if negrito:
                partes.append(NEGRITO_OFF)
                negrito = False
            if duplo:
                partes.append(DUPLO_OFF)
                duplo = False
            partes.append(_alinhamento(ALINHAMENTO_ESCPOS[Alinhamento.CENTRO]))
            alinhamento_atual = ALINHAMENTO_ESCPOS[Alinhamento.CENTRO]
            partes.append(_barras(linha.barras))
            partes.append(b"\n")
            continue

        alvo = ALINHAMENTO_ESCPOS[linha.alinhamento]
        if alvo != alinhamento_atual:
            partes.append(_alinhamento(alvo))
            alinhamento_atual = alvo
        quer_negrito = linha.enfase in (Enfase.FORTE, Enfase.TITULO)
        if quer_negrito != negrito:
            partes.append(NEGRITO_ON if quer_negrito else NEGRITO_OFF)
            negrito = quer_negrito
        quer_duplo = linha.enfase is Enfase.TITULO
        if quer_duplo != duplo:
            partes.append(DUPLO_ON if quer_duplo else DUPLO_OFF)
            duplo = quer_duplo
        partes.append(_codificar(linha.texto.rstrip()) + b"\n")

    if negrito:
        partes.append(NEGRITO_OFF)
    if duplo:
        partes.append(DUPLO_OFF)
    partes.append(_alinhamento(ALINHAMENTO_ESCPOS[Alinhamento.ESQUERDA]))
    partes.append(_avancar(avancar_linhas))
    if abrir_gaveta:
        partes.append(GAVETA)
    if cortar and documento.papel.value.startswith("BOBINA"):
        partes.append(CORTAR)
    return b"".join(partes)


__all__ = [
    "CORTAR",
    "GAVETA",
    "INICIALIZAR",
    "TABELA_1252",
    "renderizar",
    "transliterar",
]
