"""Relatório como dado, não como texto na tela.

A tela, o Excel e o PDF mostram a mesma coisa porque todos partem da mesma
estrutura. Isso evita o clássico "o PDF diz R$ 164,49 e a tela diz R$ 164,50":
a formatação é responsabilidade do exportador, o **valor** é sempre o mesmo
inteiro em centavos que veio do domínio.

Regra de tipos: nenhum campo aqui é pré-formatado por quem monta o relatório.
`TipoColuna.MOEDA` guarda centavos, `TipoColuna.INTEIRO` guarda inteiro,
`TipoColuna.DATA` guarda data ISO (``AAAA-MM-DD``) e `TEXTO` guarda texto. Quem
decide separador de milhar, símbolo de moeda e largura é o formato de saída.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from .erros import ErroValidacao

DOCUMENTO_INTERNO = "Documento interno — não fiscal"


class TipoColuna(StrEnum):
    TEXTO = "TEXTO"
    INTEIRO = "INTEIRO"
    MOEDA = "MOEDA"
    DATA = "DATA"


@dataclass(frozen=True, slots=True)
class Coluna:
    titulo: str
    tipo: TipoColuna = TipoColuna.TEXTO
    largura: int = 16  # em caracteres; vira width do Excel e proporção no PDF

    def __post_init__(self) -> None:
        if not self.titulo.strip():
            raise ErroValidacao("Coluna precisa de título.")
        if self.largura < 4:
            raise ErroValidacao("Largura de coluna mínima é 4.")

    @property
    def numerica(self) -> bool:
        return self.tipo in (TipoColuna.INTEIRO, TipoColuna.MOEDA)


@dataclass(frozen=True, slots=True)
class Tabela:
    """Bloco tabular do relatório: cabeçalho, linhas e uma nota de rodapé."""

    titulo: str
    colunas: tuple[Coluna, ...]
    linhas: tuple[tuple[object, ...], ...] = ()
    nota: str = ""

    def __post_init__(self) -> None:
        if not self.colunas:
            raise ErroValidacao(f"Tabela {self.titulo!r} sem colunas.")
        for indice, linha in enumerate(self.linhas):
            if len(linha) != len(self.colunas):
                raise ErroValidacao(
                    f"Tabela {self.titulo!r}: linha {indice + 1} tem {len(linha)} "
                    f"valor(es) para {len(self.colunas)} coluna(s)."
                )

    @property
    def vazia(self) -> bool:
        return not self.linhas


def criar_tabela(
    titulo: str,
    colunas: Sequence[tuple[str, TipoColuna] | tuple[str, TipoColuna, int]],
    linhas: Sequence[Sequence[object]],
    nota: str = "",
) -> Tabela:
    """Atalho legível: `criar_tabela("Por forma", [("Forma", TEXTO)], linhas)`."""
    definidas: list[Coluna] = []
    for item in colunas:
        largura = int(item[2]) if len(item) == 3 else 16
        definidas.append(Coluna(titulo=str(item[0]), tipo=TipoColuna(item[1]), largura=largura))
    return Tabela(
        titulo=titulo,
        colunas=tuple(definidas),
        linhas=tuple(tuple(linha) for linha in linhas),
        nota=nota,
    )


@dataclass(frozen=True, slots=True)
class Relatorio:
    """Documento exportável: identificação, indicadores, tabelas e escopo."""

    titulo: str
    subtitulo: str = ""
    loja: str = ""
    identificacao: tuple[tuple[str, str], ...] = ()  # ex.: ("Loja", "Mercadinho")
    filtros: tuple[tuple[str, str], ...] = ()  # ex.: ("Data de negócio", "2026-11-11")
    indicadores: tuple[tuple[str, str], ...] = ()  # rótulo, valor já legível
    tabelas: tuple[Tabela, ...] = ()
    avisos: tuple[str, ...] = ()
    escopo: str = ""
    documento: str = DOCUMENTO_INTERNO
    gerado_em: datetime = field(default_factory=lambda: datetime.now(tz=UTC))

    def __post_init__(self) -> None:
        if not self.titulo.strip():
            raise ErroValidacao("Relatório precisa de título.")

    @property
    def linhas(self) -> int:
        return sum(len(tabela.linhas) for tabela in self.tabelas)

    def nome_de_arquivo(self, extensao: str) -> str:
        """`fechamento-2026-11-11.xlsx` — estável, sem acento e sem espaços."""
        extensao = extensao if extensao.startswith(".") else f".{extensao}"
        partes = [self.titulo]
        recorte = next(
            (
                valor
                for rotulo, valor in self.filtros
                if rotulo.lower().startswith(("data", "período", "periodo"))
            ),
            "",
        )
        if recorte:
            partes.append(recorte)
        elif self.gerado_em:
            partes.append(self.gerado_em.strftime("%Y%m%d-%H%M"))
        return slug("-".join(partes)) + extensao.lower()


def slug(texto: str) -> str:
    """Minúsculas, sem acento, só `a-z0-9` e hífen — nome de arquivo seguro."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    limpo = re.sub(r"[^a-zA-Z0-9]+", "-", sem_acento).strip("-")
    return (limpo or "relatorio").lower()


def carimbo_do_dia(quando: datetime) -> str:
    """Data legível no fuso local do processo (o do computador da loja)."""
    return quando.astimezone().strftime("%d/%m/%Y %H:%M")
