"""Documento imprimível: a mesma estrutura para bobina térmica, folha A4 e PDF.

Por que existe uma camada aqui em vez de "cada tela monta seu texto": um cupom
impresso em três lugares diferentes (impressora térmica pelo driver, térmica em
ESC/POS direto, PDF para e-mail) divergiria na primeira manutenção. Então o
documento é **dado**, no mesmo espírito de `dominio/relatorio.py`:

* quem monta o comprovante (camada de aplicação) descreve **blocos**: texto, par
  rótulo/valor, divisor, item de venda, código de barras;
* `layout()` transforma blocos em **linhas de largura fixa**, quebrando o que não
  cabe nas colunas do papel — a quebra acontece uma vez, não em cada renderizador;
* os renderizadores (`infra/impressao/`) só pintam: texto puro, bytes ESC/POS ou
  páginas Qt.

Assim o cupom de 58 mm, o de 80 mm e o PDF saem idênticos no conteúdo, e o teste
compara os três.

Código de barras: **CODE 39**, escolhido porque é o único simbólico que qualquer
impressora térmica compatível com ESC/POS sabe imprimir sozinha (`GS k 4`) e que
dá para desenhar à mão no PDF (barras de 1 e 3 módulos). Não há leitura de código
de barras nesta entrega — só impressão.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from enum import StrEnum

from .dinheiro import Dinheiro, Quantidade
from .erros import ErroValidacao


class Papel(StrEnum):
    """Suportes que a loja realmente usa."""

    BOBINA_58 = "BOBINA_58"  # térmica pequena: 32 colunas
    BOBINA_80 = "BOBINA_80"  # térmica de balcão: 48 colunas
    A4 = "A4"  # impressora comum, quando a térmica está fora


@dataclass(frozen=True, slots=True)
class PerfilPapel:
    """Medidas do suporte. Letras maiúsculas porque são constantes de operação."""

    papel: Papel
    rotulo: str
    largura_mm: float
    altura_mm: float | None  # None = bobina contínua (altura vem do conteúdo)
    colunas: int
    margem_mm: float
    altura_linha_mm: float

    @property
    def contínuo(self) -> bool:
        return self.altura_mm is None

    @property
    def largura_util_mm(self) -> float:
        return self.largura_mm - 2 * self.margem_mm


PERFIS_PAPEL: dict[Papel, PerfilPapel] = {
    Papel.BOBINA_58: PerfilPapel(Papel.BOBINA_58, "Bobina 58 mm", 58.0, None, 32, 3.0, 4.2),
    Papel.BOBINA_80: PerfilPapel(Papel.BOBINA_80, "Bobina 80 mm", 80.0, None, 48, 4.0, 4.6),
    # 80 colunas: o mesmo cupom cabe em folha comum sem parecer relatório.
    Papel.A4: PerfilPapel(Papel.A4, "Folha A4", 210.0, 297.0, 80, 12.0, 4.6),
}


class Alinhamento(StrEnum):
    ESQUERDA = "ESQUERDA"
    CENTRO = "CENTRO"
    DIREITA = "DIREITA"


class Enfase(StrEnum):
    """O que a térmica sabe fazer: normal, negrito e título (duplo)."""

    NORMAL = "NORMAL"
    FORTE = "FORTE"
    TITULO = "TITULO"


# -- blocos do documento --------------------------------------------------
@dataclass(frozen=True, slots=True)
class Texto:
    texto: str
    alinhamento: Alinhamento = Alinhamento.ESQUERDA
    enfase: Enfase = Enfase.NORMAL


@dataclass(frozen=True, slots=True)
class Par:
    """Rótulo à esquerda e valor à direita, na mesma linha do cupom."""

    rotulo: str
    valor: str
    enfase: Enfase = Enfase.NORMAL


@dataclass(frozen=True, slots=True)
class Divisor:
    caractere: str = "-"

    def __post_init__(self) -> None:
        if len(self.caractere) != 1:
            raise ErroValidacao("Divisor usa um único caractere.")


@dataclass(frozen=True, slots=True)
class Espaco:
    linhas: int = 1

    def __post_init__(self) -> None:
        if self.linhas < 1:
            raise ErroValidacao("Espaço precisa de ao menos uma linha.")


@dataclass(frozen=True, slots=True)
class Item:
    """Linha de mercadoria: descrição, quantidade, unitário e total."""

    descricao: str
    quantidade: Quantidade
    unidade: str
    unitario: Dinheiro
    total: Dinheiro
    desconto: Dinheiro = field(default_factory=lambda: Dinheiro(0))
    codigo: str = ""


@dataclass(frozen=True, slots=True)
class CodigoDeBarras:
    """CODE 39 do identificador do documento (série-número do cupom)."""

    dado: str
    altura_mm: float = 12.0
    mostrar_texto: bool = True


Bloco = Texto | Par | Divisor | Espaco | Item | CodigoDeBarras


# -- linhas prontas -------------------------------------------------------
@dataclass(frozen=True, slots=True)
class LinhaPronta:
    """Uma linha física do papel, já dentro da largura do suporte."""

    texto: str = ""
    alinhamento: Alinhamento = Alinhamento.ESQUERDA
    enfase: Enfase = Enfase.NORMAL
    barras: str = ""  # preenchido quando a linha é um código de barras
    altura_barras_mm: float = 0.0

    @property
    def eh_codigo_de_barras(self) -> bool:
        return bool(self.barras)


@dataclass(frozen=True, slots=True)
class DocumentoImpresso:
    """O que vai para o papel: título, suporte, blocos e aviso final."""

    titulo: str
    papel: Papel
    blocos: tuple[Bloco, ...]
    rotulo: str = "documento"  # base do nome de arquivo, sem extensão
    avisos: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.blocos:
            raise ErroValidacao("Documento de impressão sem conteúdo.")
        if not self.titulo.strip():
            raise ErroValidacao("Documento de impressão precisa de título.")
        if not _NOME_ARQUIVO.match(self.rotulo):
            raise ErroValidacao("Rótulo do arquivo aceita letras, números e hífen.")

    @property
    def perfil(self) -> PerfilPapel:
        return PERFIS_PAPEL[self.papel]

    @property
    def colunas(self) -> int:
        return self.perfil.colunas

    def com_papel(self, papel: Papel) -> DocumentoImpresso:
        """Mesmo conteúdo em outro suporte (a prévia troca 58 ↔ 80 ↔ A4)."""
        return DocumentoImpresso(self.titulo, papel, self.blocos, self.rotulo, self.avisos)

    def layout(self) -> tuple[LinhaPronta, ...]:
        """Blocos → linhas de largura fixa. Único lugar que sabe quebrar texto."""
        colunas = self.colunas
        linhas: list[LinhaPronta] = []
        for bloco in self.blocos:
            if isinstance(bloco, Texto):
                for pedaco in _quebrar(bloco.texto, colunas):
                    linhas.append(
                        LinhaPronta(
                            _alinhar(pedaco, colunas, bloco.alinhamento),
                            bloco.alinhamento,
                            bloco.enfase,
                        )
                    )
            elif isinstance(bloco, Par):
                linhas.extend(_par(bloco, colunas))
            elif isinstance(bloco, Divisor):
                linhas.append(LinhaPronta(bloco.caractere * colunas))
            elif isinstance(bloco, Espaco):
                linhas.extend(LinhaPronta() for _ in range(bloco.linhas))
            elif isinstance(bloco, Item):
                linhas.extend(_item(bloco, colunas))
            elif isinstance(bloco, CodigoDeBarras):
                linhas.append(
                    LinhaPronta(barras=bloco.dado, altura_barras_mm=bloco.altura_mm)
                )
                if bloco.mostrar_texto:
                    linhas.append(
                        LinhaPronta(_alinhar(bloco.dado, colunas, Alinhamento.CENTRO), Alinhamento.CENTRO)
                    )
        for aviso in self.avisos:
            for pedaco in _quebrar(aviso, colunas):
                linhas.append(LinhaPronta(_alinhar(pedaco, colunas, Alinhamento.CENTRO), Alinhamento.CENTRO))
        return tuple(linhas)

    def texto(self) -> str:
        """Renderização em texto puro (prévia, `.txt` e base do `.bin`)."""
        return "\n".join(
            linha.barras if linha.eh_codigo_de_barras else linha.texto for linha in self.layout()
        )

    def altura_mm(self) -> float:
        """Altura total do conteúdo — vira a altura da página no PDF da bobina."""
        perfil = self.perfil
        total = 2 * perfil.margem_mm
        for linha in self.layout():
            total += linha.altura_barras_mm if linha.eh_codigo_de_barras else perfil.altura_linha_mm
        return total


# -- texto de largura fixa ------------------------------------------------
def largura_de(texto: str) -> int:
    """Largura em colunas de impressão (acento não ocupa coluna extra)."""
    sem_acento = unicodedata.normalize("NFKD", texto)
    return len("".join(c for c in sem_acento if not unicodedata.combining(c)))


def _alinhar(texto: str, colunas: int, alinhamento: Alinhamento) -> str:
    if alinhamento is Alinhamento.CENTRO:
        return centrar(texto, colunas)
    if alinhamento is Alinhamento.DIREITA:
        return a_direita(texto, colunas)
    return texto


def centrar(texto: str, colunas: int) -> str:
    """Centraliza considerando a largura real (acentos não contam como coluna)."""
    excesso = max(0, colunas - largura_de(texto))
    return " " * (excesso // 2) + texto


def a_direita(texto: str, colunas: int) -> str:
    return " " * max(0, colunas - largura_de(texto)) + texto


def _quebrar(texto: str, colunas: int) -> list[str]:
    """Quebra por palavra; palavra maior que a linha é cortada em pedaços."""
    partes: list[str] = []
    for paragrafo in str(texto).splitlines() or [""]:
        palavras = paragrafo.split()
        if not palavras:
            partes.append("")
            continue
        linha = ""
        for palavra in palavras:
            while largura_de(palavra) > colunas:  # palavra sozinha não cabe
                if linha:
                    partes.append(linha)
                    linha = ""
                corte = _corte_que_cabe(palavra, colunas)
                partes.append(palavra[:corte])
                palavra = palavra[corte:]
            candidata = f"{linha} {palavra}".strip()
            if largura_de(candidata) <= colunas:
                linha = candidata
            else:
                partes.append(linha)
                linha = palavra
        if linha:
            partes.append(linha)
    return partes or [""]


def _corte_que_cabe(palavra: str, colunas: int) -> int:
    """Maior prefixo que cabe em `colunas` (sem cortar acento no meio)."""
    corte = 0
    while corte < len(palavra) and largura_de(palavra[: corte + 1]) <= colunas:
        corte += 1
    return max(corte, 1)


def _par(bloco: Par, colunas: int) -> list[LinhaPronta]:
    """Rótulo e valor na mesma linha; valor longo desce alinhado à direita."""
    valor = bloco.valor
    espaco = colunas - largura_de(bloco.rotulo) - largura_de(valor)
    if espaco >= 1:
        linha = bloco.rotulo + " " * espaco + valor
        return [LinhaPronta(linha, Alinhamento.ESQUERDA, bloco.enfase)]
    linhas = [LinhaPronta(bloco.rotulo, Alinhamento.ESQUERDA, bloco.enfase)]
    for pedaco in _quebrar(valor, colunas):
        linhas.append(LinhaPronta(a_direita(pedaco, colunas), Alinhamento.DIREITA, bloco.enfase))
    return linhas


def _item(bloco: Item, colunas: int) -> list[LinhaPronta]:
    """Descrição em cima, `qtd un × unitário` e total embaixo — cabe em 32 colunas."""
    linhas = [LinhaPronta(pedaco) for pedaco in _quebrar(bloco.descricao, colunas)]
    quantidade = bloco.quantidade.formatada()
    esquerda = f"{quantidade} {bloco.unidade} x {bloco.unitario.formatado()}"
    total = bloco.total.formatado()
    if largura_de(esquerda) + 1 + largura_de(total) <= colunas:
        preenchimento = " " * (colunas - largura_de(esquerda) - largura_de(total))
        linhas.append(LinhaPronta(esquerda + preenchimento + total))
    else:
        linhas.append(LinhaPronta(esquerda))
        linhas.append(LinhaPronta(a_direita(total, colunas), Alinhamento.DIREITA))
    if bloco.desconto.centavos:
        rotulo = "  desconto"
        valor = f"-{bloco.desconto.formatado()}"
        preenchimento = " " * max(1, colunas - largura_de(rotulo) - largura_de(valor))
        linhas.append(LinhaPronta(rotulo + preenchimento + valor))
    if bloco.codigo:
        linhas.append(LinhaPronta(f"  cod. {bloco.codigo}"))
    return linhas


# -- CODE 39 --------------------------------------------------------------
#: Máscara de 9 elementos por caractere (1 = elemento largo). Barras nas posições
#: pares, espaços nas ímpares; três largos por caractere, como manda o CODE 39.
_TABELA_C39: dict[str, int] = {
    "0": 0x034, "1": 0x121, "2": 0x061, "3": 0x160, "4": 0x031,
    "5": 0x130, "6": 0x070, "7": 0x025, "8": 0x124, "9": 0x064,
    "A": 0x109, "B": 0x049, "C": 0x148, "D": 0x019, "E": 0x118,
    "F": 0x058, "G": 0x00D, "H": 0x10C, "I": 0x04C, "J": 0x01C,
    "K": 0x103, "L": 0x043, "M": 0x142, "N": 0x013, "O": 0x112,
    "P": 0x052, "Q": 0x007, "R": 0x106, "S": 0x046, "T": 0x016,
    "U": 0x181, "V": 0x0C1, "W": 0x1C0, "X": 0x091, "Y": 0x190,
    "Z": 0x0D0, "-": 0x085, ".": 0x184, " ": 0x0C4, "$": 0x0A8,
    "/": 0x0A2, "+": 0x08A, "%": 0x02A, "*": 0x094,
}
LARGURA_LARGO = 3  # módulos por elemento largo (razão 3:1, a mínima do CODE 39)
CARACTERE_INICIAL = "*"


def padrao_code39(dado: str) -> str:
    """Sequência de módulos (``1`` = barra preta, ``0`` = espaço) do CODE 39.

    O resultado já inclui os caracteres de início e fim (`*`). É o que os
    renderizadores desenham: no PDF, um retângulo por `1`; na térmica em ESC/POS,
    o comando nativo `GS k 4` recebe o dado.
    """
    texto = str(dado).strip().upper()
    if not texto:
        raise ErroValidacao("Código de barras sem dado.")
    invalidos = [c for c in texto if c not in _TABELA_C39 or c == CARACTERE_INICIAL]
    if invalidos:
        permitidos = "".join(sorted(c for c in _TABELA_C39 if c != CARACTERE_INICIAL))
        raise ErroValidacao(
            f"CODE 39 não representa {''.join(invalidos)!r}. Use apenas: {permitidos}."
        )
    modulos: list[str] = []
    for indice, caractere in enumerate(f"{CARACTERE_INICIAL}{texto}{CARACTERE_INICIAL}"):
        if indice:  # espaço estreito entre caracteres
            modulos.append("0")
        mascara = _TABELA_C39[caractere]
        for elemento in range(9):
            largo = bool(mascara & (0x100 >> elemento))
            if elemento % 2 == 0:  # barra
                modulos.append("1" * (LARGURA_LARGO if largo else 1))
            else:  # espaço
                modulos.append("0" * (LARGURA_LARGO if largo else 1))
    return "".join(modulos)


def barras_do_codigo(dado: str) -> list[tuple[int, int]]:
    """Lista de `(início, largura)` em módulos das barras pretas — para desenhar."""
    padrao = padrao_code39(dado)
    barras: list[tuple[int, int]] = []
    inicio = -1
    for posicao, modulo in enumerate(padrao):
        if modulo == "1":
            if inicio < 0:
                inicio = posicao
        elif inicio >= 0:
            barras.append((inicio, posicao - inicio))
            inicio = -1
    if inicio >= 0:
        barras.append((inicio, len(padrao) - inicio))
    return barras


_NOME_ARQUIVO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-_.]*$")


__all__ = [
    "CARACTERE_INICIAL",
    "LARGURA_LARGO",
    "PERFIS_PAPEL",
    "Alinhamento",
    "Bloco",
    "CodigoDeBarras",
    "Divisor",
    "DocumentoImpresso",
    "Enfase",
    "Espaco",
    "Item",
    "LinhaPronta",
    "Papel",
    "Par",
    "PerfilPapel",
    "Texto",
    "a_direita",
    "barras_do_codigo",
    "centrar",
    "largura_de",
    "padrao_code39",
]
