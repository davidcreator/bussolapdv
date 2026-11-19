"""Testes do manual web (`manual/index.html`).

O manual é gerado a partir de três fontes que podem sair de sincronia sem ninguém
notar: o texto em `ferramentas/manual_conteudo.py`, o guia que vive dentro do
programa (`bussola_pdv.aplicacao.ajuda`) e as capturas em `docs/capturas/`. Estes
testes cobrem justamente o que quebra em silêncio: seção apontando para um tema
que não existe, imagem que foi regerada com outro nome, simulador citado e não
implementado, link interno sem destino e recurso externo (o manual precisa abrir
sem internet).
"""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import ClassVar

import pytest

RAIZ = Path(__file__).resolve().parent.parent
FERRAMENTAS = RAIZ / "ferramentas"

if str(FERRAMENTAS) not in sys.path:
    sys.path.insert(0, str(FERRAMENTAS))

import gerar_manual  # noqa: E402  (depende do sys.path acima)
import manual_conteudo  # noqa: E402

#: Classes que só o JavaScript aplica em tempo de execução: não existem no HTML
#: gerado, então o teste não tem como vê-las no CSS.
CLASSES_DO_SCRIPT = {"destaque", "aberto", "ativo", "escondido", "oculto", "aberta", "feito", "atual"}


class _Balanceador(HTMLParser):
    """Só serve para achar tag que abre e não fecha."""

    VAZIAS: ClassVar[frozenset[str]] = frozenset({
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    })

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.pilha: list[str] = []
        self.erros: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in self.VAZIAS:
            self.pilha.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in self.VAZIAS:
            return
        if not self.pilha:
            self.erros.append(f"</{tag}> sem abertura")
            return
        if self.pilha[-1] != tag:
            self.erros.append(f"</{tag}> fecha no lugar de </{self.pilha[-1]}>")
            while self.pilha and self.pilha[-1] != tag:
                self.pilha.pop()
            if self.pilha:
                self.pilha.pop()
            return
        self.pilha.pop()


@pytest.fixture(scope="module")
def dados() -> dict:
    return gerar_manual._dados()


@pytest.fixture(scope="module")
def pagina(tmp_path_factory) -> str:
    """Manual completo (com imagens), gerado uma vez para todos os testes."""
    destino = tmp_path_factory.mktemp("manual") / "index.html"
    codigo = gerar_manual.main(["--saida", str(destino)])
    assert codigo == 0
    return destino.read_text(encoding="utf-8")


def _ids(html: str) -> list[str]:
    return re.findall(r'\sid="([^"]+)"', html)


# -- conteúdo ------------------------------------------------------------------
def test_ha_capitulos_e_secoes() -> None:
    assert len(manual_conteudo.CAPITULOS) >= 20
    for capitulo in manual_conteudo.CAPITULOS:
        assert capitulo["secoes"], capitulo["id"]
        assert capitulo["titulo"].strip()
        assert capitulo["resumo"].strip()


def test_identificadores_sao_unicos() -> None:
    capitulos = [c["id"] for c in manual_conteudo.CAPITULOS]
    secoes = [s["id"] for c in manual_conteudo.CAPITULOS for s in c["secoes"]]
    assert len(set(capitulos)) == len(capitulos)
    assert len(set(secoes)) == len(secoes)
    # capítulo e seção não podem usar o mesmo id: a âncora ficaria ambígua
    assert not set(capitulos) & set(secoes)


def test_toda_secao_tem_algum_conteudo() -> None:
    for capitulo in manual_conteudo.CAPITULOS:
        for secao in capitulo["secoes"]:
            tem = any(
                secao.get(chave)
                for chave in ("corpo", "guia", "imagem", "demo", "avancado")
            )
            assert tem, f"{capitulo['id']}/{secao['id']} está vazia"


def test_toda_chave_de_guia_existe_no_programa(dados: dict) -> None:
    """Seção que aponta para um tema inexistente geraria página sem o passo a passo."""
    for capitulo in manual_conteudo.CAPITULOS:
        for secao in capitulo["secoes"]:
            chave = secao.get("guia")
            if chave:
                assert chave in dados["guia"], f"{secao['id']}: tema {chave!r} não existe"
                tema = dados["guia"][chave]
                assert tema.passos or tema.campos or tema.cuidados, (
                    f"{secao['id']}: tema {chave!r} está sem conteúdo no programa"
                )


def test_toda_imagem_citada_esta_em_docs_capturas() -> None:
    for capitulo in manual_conteudo.CAPITULOS:
        for secao in capitulo["secoes"]:
            imagem = secao.get("imagem")
            if imagem:
                nome = imagem[0]
                assert (RAIZ / "docs" / "capturas" / nome).is_file(), (
                    f"{secao['id']}: falta docs/capturas/{nome} — rode `make capturas`"
                )


def test_todo_simulador_citado_esta_implementado() -> None:
    for capitulo in manual_conteudo.CAPITULOS:
        for secao in capitulo["secoes"]:
            demo = secao.get("demo")
            if demo:
                assert demo in gerar_manual.DEMOS, f"{secao['id']}: simulador {demo!r} não existe"


def test_manual_serve_a_leigo_e_a_avancado() -> None:
    """A tarefa pede as duas trilhas: texto de entrada e bloco técnico."""
    capitulos = {c["id"] for c in manual_conteudo.CAPITULOS}
    assert "comecar" in capitulos
    assert "avancado" in capitulos
    avancados = [
        secao
        for capitulo in manual_conteudo.CAPITULOS
        for secao in capitulo["secoes"]
        if secao.get("avancado")
    ]
    assert len(avancados) >= 5


# -- página gerada -------------------------------------------------------------
def test_pagina_tem_o_comeco_e_o_fim(pagina: str) -> None:
    assert pagina.startswith("<!DOCTYPE html>")
    assert pagina.rstrip().endswith("</html>")
    assert '<html lang="pt-BR">' in pagina
    assert 'charset="utf-8"' in pagina


def test_paginas_nao_ficam_sem_fechar_tag(pagina: str) -> None:
    balanceador = _Balanceador()
    balanceador.feed(pagina)
    assert not balanceador.erros, balanceador.erros[:5]


def test_todo_link_interno_tem_destino(pagina: str) -> None:
    identidades = set(_ids(pagina))
    destinos = set(re.findall(r'href="#([^"]+)"', pagina))
    assert destinos, "o manual precisa de sumário navegável"
    assert not destinos - identidades, sorted(destinos - identidades)


def test_ids_repetidos_nao_existem(pagina: str) -> None:
    identidades = _ids(pagina)
    repetidos = {i for i in identidades if identidades.count(i) > 1}
    assert not repetidos, sorted(repetidos)


def test_manual_abre_sem_internet(pagina: str) -> None:
    assert not re.search(r'(?:src|srcset)="https?://', pagina)
    assert "<link " not in pagina
    assert "@import" not in pagina
    assert "fonts.googleapis" not in pagina
    # as capturas entram embutidas, não por caminho relativo
    assert pagina.count("data:image/") >= 10
    assert 'src="docs/' not in pagina


def test_todas_as_capturas_entram_embutidas(pagina: str) -> None:
    pedidas = {
        secao["imagem"][0]
        for capitulo in manual_conteudo.CAPITULOS
        for secao in capitulo["secoes"]
        if secao.get("imagem")
    }
    assert len(pedidas) >= 20
    assert pagina.count("data:image/") >= len(pedidas)


def test_imagem_tem_medida_para_nao_deslocar_a_pagina(pagina: str) -> None:
    """Sem width/height, clicar num capítulo cai no lugar errado enquanto pinta."""
    imagens = re.findall(r"<img [^>]*>", pagina)
    com_medida = [i for i in imagens if 'width="' in i and 'height="' in i]
    assert len(com_medida) >= 20
    assert 'loading="lazy"' not in pagina


def test_versao_aparece_e_o_marcador_sumiu(pagina: str, dados: dict) -> None:
    assert dados["versao"] in pagina
    assert "{VERSAO}" not in pagina
    assert re.search(r"\{[A-Z_]+\}", pagina) is None


def test_cada_capitulo_esta_na_pagina_e_no_sumario(pagina: str) -> None:
    for capitulo in manual_conteudo.CAPITULOS:
        assert f'id="{capitulo["id"]}"' in pagina
        assert f'href="#{capitulo["id"]}"' in pagina
        for secao in capitulo["secoes"]:
            assert f'href="#{secao["id"]}"' in pagina


def test_toda_classe_usada_existe_no_css(pagina: str) -> None:
    """Classe digitada errada no texto não quebra nada: só não estiliza."""
    css = gerar_manual.CSS
    usadas: set[str] = set()
    for atributo in re.findall(r'class="([^"]+)"', pagina):
        usadas.update(atributo.split())
    faltando = {c for c in usadas if f".{c}" not in css and c not in CLASSES_DO_SCRIPT}
    assert not faltando, sorted(faltando)


def test_numeracao_dos_passos_nao_duplica() -> None:
    """O guia do programa já numera alguns títulos; a bolinha do CSS numera de novo."""
    tema = gerar_manual._dados()["guia"]["pdv"]
    assert any(p.titulo[:2] == "1." for p in tema.passos), "o caso real deixou de existir"
    html = gerar_manual.passos_do_guia(tema)
    assert "<strong>1. " not in html
    assert re.search(r"<strong>\d+[.)]\s", html) is None
    assert html.count("<li>") == len(tema.passos)


def test_arquivo_do_repositorio_esta_atualizado(pagina: str) -> None:
    """`manual/index.html` é versionado: precisa ter os capítulos de hoje."""
    publicado = RAIZ / "manual" / "index.html"
    assert publicado.is_file(), "rode `make manual` e versione o arquivo"
    html = publicado.read_text(encoding="utf-8")
    for capitulo in manual_conteudo.CAPITULOS:
        assert f'id="{capitulo["id"]}"' in html, (
            f"o manual versionado não tem o capítulo {capitulo['id']} — rode `make manual`"
        )


def test_modo_sem_imagens_gera_arquivo_menor(tmp_path) -> None:
    destino = tmp_path / "leve.html"
    assert gerar_manual.main(["--saida", str(destino), "--sem-imagens"]) == 0
    texto = destino.read_text(encoding="utf-8")
    assert "data:image/" not in texto
    assert len(texto) > 40_000  # o texto todo continua lá
