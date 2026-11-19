"""Gera o manual web do Bússola PDV: um único HTML, que abre sem internet.

Por que um arquivo só: quem usa PDV abre o manual no mesmo computador da loja, que
pode estar sem rede, e a documentação precisa funcionar com duplo clique. Por isso
CSS, JavaScript e as imagens vão **dentro** do `.html` (imagens em `data:` URI,
reduzidas para não virar um arquivo de 40 MB).

O texto operacional não é reescrito aqui: ele vem do **mesmo guia** que o `F1` do
programa mostra (`bussola_pdv.aplicacao.ajuda.GUIA`). Se o guia mudar, o manual
muda junto — e o teste `tests/test_manual.py` falha se um tema do guia sumir do
manual.

Uso (na raiz do repositório)::

    python ferramentas/gerar_manual.py                 # escreve manual/index.html
    python ferramentas/gerar_manual.py --sem-imagens   # HTML leve, sem capturas
    python ferramentas/gerar_manual.py --saida /tmp/manual.html

As capturas vêm de `docs/capturas/` (geradas por `make capturas`).
"""

from __future__ import annotations

import argparse
import base64
import html
import io
import re
import sys
from pathlib import Path
from typing import NamedTuple

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
CAPTURAS = RAIZ / "docs" / "capturas"
if str(AQUI) not in sys.path:  # o módulo de texto mora ao lado deste script
    sys.path.insert(0, str(AQUI))
from manual_conteudo import CAPITULOS  # noqa: E402  (precisa do sys.path acima)

SAIDA_PADRAO = RAIZ / "manual" / "index.html"

#: Maior largura de imagem embutida (px). Acima disso o arquivo cresce sem ganho
#: de leitura: a captura é de tela de PDV, não de fotografia.
LARGURA_MAXIMA = 1120


#: Ícones da barra do topo em SVG (traço herda a cor do texto). Emoji renderiza como
#: quadradinho em sistema sem fonte de emoji — e a barra é justamente o que a pessoa
#: precisa achar de primeira.
ICONE_MENU = (
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16"/>'
    '</svg>'
)
ICONE_LUA = (
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12.8A8.5 8.5 0 1 1 11.2 3a6.6 6.6 0 0 0 9.8 9.8z"/>'
    '</svg>'
)
ICONE_SOL = (
    '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4.2"/>'
    '<path d="M12 2v2.4M12 19.6V22M2 12h2.4M19.6 12H22M4.9 4.9l1.7 1.7'
    'M17.4 17.4l1.7 1.7M19.1 4.9l-1.7 1.7M6.6 17.4l-1.7 1.7"/></svg>'
)
ICONE_IMPRIMIR = (
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 9V3h10v6"/>'
    '<path d="M7 18H5a2 2 0 0 1-2-2v-4a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-2"/>'
    '<path d="M7 14h10v7H7z"/></svg>'
)
ICONE_BUSSOLA = (
    '<svg viewBox="0 0 24 24" aria-hidden="true">'
    '<circle cx="12" cy="12" r="9.2"/><path d="M15.4 8.6l-2 5.4-5.4 2 2-5.4z"/></svg>'
)

#: Perfis na ordem em que aparecem no manual (do menor para o maior poder).
PERFIS = ("ATENDENTE", "GERENTE", "CONTABILIDADE", "ADMIN", "ADMIN_MASTER")

PERFIS_ROTULO = {
    "ATENDENTE": "Atendente",
    "GERENTE": "Gerente",
    "CONTABILIDADE": "Contabilidade",
    "ADMIN": "Admin",
    "ADMIN_MASTER": "Admin Master",
}


def _dados() -> dict[str, object]:
    """Lê do código o que o manual afirma: versão, perfis, ações, permissões, guia."""
    sys.path.insert(0, str(RAIZ / "src"))
    from bussola_pdv import __version__
    from bussola_pdv.aplicacao.ajuda import GUIA
    from bussola_pdv.dominio.usuario import PERMISSOES_PADRAO, Acao

    return {
        "versao": __version__,
        "guia": {tema.chave: tema for tema in GUIA},
        "acoes": [acao.name for acao in Acao],
        "permissoes": {
            perfil: sorted(acao.name for acao in acoes)
            for perfil, acoes in PERMISSOES_PADRAO.items()
        },
    }


class Imagem(NamedTuple):
    """Captura já embutida, com as medidas originais para reservar o espaço."""

    uri: str
    largura: int
    altura: int


def imagem_embutida(nome: str) -> Imagem:
    """Captura → `data:` URI reduzida (WebP), para o HTML não depender de arquivo."""
    origem = CAPTURAS / nome
    if not origem.is_file():
        raise SystemExit(
            f"Captura ausente: {origem}. Rode `make capturas` antes de gerar o manual."
        )
    try:
        from PIL import Image
    except ImportError:  # pragma: no cover - Pillow é dependência de empacotamento
        dados = origem.read_bytes()
        return Imagem("data:image/png;base64," + base64.b64encode(dados).decode("ascii"), 0, 0)

    with Image.open(origem) as imagem:
        imagem = imagem.convert("RGB")
        if imagem.width > LARGURA_MAXIMA:
            altura = round(imagem.height * LARGURA_MAXIMA / imagem.width)
            imagem = imagem.resize((LARGURA_MAXIMA, altura), Image.LANCZOS)
        largura, altura = imagem.size
        buffer = io.BytesIO()
        imagem.save(buffer, format="WEBP", quality=82, method=6)
    return Imagem(
        "data:image/webp;base64," + base64.b64encode(buffer.getvalue()).decode("ascii"),
        largura,
        altura,
    )


# -- blocos do texto -----------------------------------------------------------
#: Numeração solta no começo do título ("1. ", "2) "): some porque o CSS numera.
NUMERO_NO_TITULO = re.compile(r"^\d+[.)]\s*")


def _sem_numero(titulo: str) -> str:
    return NUMERO_NO_TITULO.sub("", titulo)


def passos_do_guia(tema) -> str:
    if not tema.passos:
        return ""
    # O texto do guia no programa já traz "1. ", "2. " em alguns passos; aqui quem
    # numera é o próprio CSS (bolinha), então o prefixo sairia repetido.
    itens = "".join(
        f"<li><strong>{html.escape(_sem_numero(passo.titulo))}</strong>"
        f" — {html.escape(passo.texto)}</li>"
        for passo in tema.passos
    )
    return f'<ol class="passos">{itens}</ol>'


def campos_do_guia(tema) -> str:
    if not tema.campos:
        return ""
    linhas = "".join(
        f"<tr><th scope=\"row\">{html.escape(campo.rotulo)}</th>"
        f"<td>{html.escape(campo.o_que_e)}</td>"
        f"<td>{html.escape(campo.como_usar)}</td></tr>"
        for campo in tema.campos
    )
    return (
        '<div class="tabela-rolagem"><table class="tabela">'
        "<caption>Campo por campo</caption>"
        "<thead><tr><th>Campo</th><th>O que é</th><th>Como usar</th></tr></thead>"
        f"<tbody>{linhas}</tbody></table></div>"
    )


def atalhos_do_guia(tema) -> str:
    if not tema.atalhos:
        return ""
    linhas = "".join(
        f"<tr><td><kbd>{html.escape(tecla)}</kbd></td><td>{html.escape(descricao)}</td></tr>"
        for tecla, descricao in tema.atalhos
    )
    return (
        '<div class="tabela-rolagem"><table class="tabela">'
        "<caption>Atalhos desta tela</caption>"
        "<thead><tr><th>Tecla</th><th>Faz</th></tr></thead>"
        f"<tbody>{linhas}</tbody></table></div>"
    )


def cuidados_do_guia(tema) -> str:
    if not tema.cuidados:
        return ""
    itens = "".join(f"<li>{html.escape(texto)}</li>" for texto in tema.cuidados)
    return f'<div class="aviso aviso-atencao"><p class="aviso-titulo">Atenção</p><ul>{itens}</ul></div>'


# -- HTML ----------------------------------------------------------------------
CSS = r"""
:root{
  --azul:#0D6EFD; --azul-escuro:#0B5ED7; --grafite:#343A40; --texto:#212529;
  --texto-suave:#5F686F; --fundo:#F4F6F9; --superficie:#FFFFFF; --borda:#DEE2E6;
  --dica:#0F5132; --dica-fundo:#D1E7DD; --atencao:#664D03; --atencao-fundo:#FFF3CD;
  --perigo:#842029; --perigo-fundo:#F8D7DA; --info:#055160; --info-fundo:#CFE2FF;
  --raio:10px; --sombra:0 1px 2px rgba(16,24,40,.06),0 8px 24px rgba(16,24,40,.06);
  --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace;
}
body.escuro{
  --azul:#4C8DFF; --azul-escuro:#3B7BF0; --grafite:#1C2024; --texto:#E9ECEF;
  --texto-suave:#ADB5BD; --fundo:#14171A; --superficie:#1E2328; --borda:#343A40;
  --dica:#A3E4C1; --dica-fundo:#12301F; --atencao:#FFE08A; --atencao-fundo:#3A2E08;
  --perigo:#F5B7BE; --perigo-fundo:#3A1418; --info:#B6D4FF; --info-fundo:#10243A;
  --sombra:0 1px 2px rgba(0,0,0,.4),0 10px 30px rgba(0,0,0,.35);
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto} *{transition:none!important;animation:none!important}}
body{margin:0;background:var(--fundo);color:var(--texto);
  font:16px/1.65 system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif}
a{color:var(--azul);text-decoration:none}
a:hover{text-decoration:underline}
code,kbd,pre{font-family:var(--mono)}
code{background:rgba(13,110,253,.08);padding:.1em .35em;border-radius:5px;font-size:.92em}
body.escuro code{background:rgba(76,141,255,.14)}
kbd{background:var(--superficie);border:1px solid var(--borda);border-bottom-width:2px;
  border-radius:5px;padding:.05em .4em;font-size:.85em;white-space:nowrap}
pre{background:var(--grafite);color:#E9ECEF;padding:14px 16px;border-radius:var(--raio);
  overflow:auto;font-size:.86em;line-height:1.5}
pre code{background:none;padding:0;color:inherit}

/* ---- topo ---- */
#topo{position:sticky;top:0;z-index:40;display:flex;gap:12px;align-items:center;
  padding:10px 16px;background:var(--superficie);border-bottom:1px solid var(--borda);
  box-shadow:0 1px 3px rgba(16,24,40,.06)}
#topo .marca{display:flex;align-items:center;gap:10px;font-weight:700;white-space:nowrap}
#topo .marca span.selo{background:var(--azul);color:#fff;border-radius:6px;padding:2px 8px;
  font-size:12px;font-weight:700;letter-spacing:.02em}
#busca{flex:1;min-width:120px;max-width:520px;padding:9px 12px;border:1px solid var(--borda);
  border-radius:8px;background:var(--fundo);color:var(--texto);font-size:15px}
#busca:focus{outline:2px solid var(--azul);outline-offset:1px}
.botao-icone{background:var(--fundo);border:1px solid var(--borda);color:var(--texto);
  border-radius:8px;padding:8px 10px;cursor:pointer;font-size:15px;line-height:1}
.botao-icone:hover{border-color:var(--azul);color:var(--azul)}
#progresso{position:fixed;top:0;left:0;height:3px;background:var(--azul);width:0;z-index:60}
.botao-icone svg,.marca svg{width:18px;height:18px;display:block;fill:none;
  stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
.marca svg{width:22px;height:22px;stroke:var(--azul);stroke-width:1.6}
.botao-icone{display:grid;place-items:center}

/* ---- casca ---- */
#casca{display:flex;align-items:flex-start;gap:26px;max-width:1500px;margin:0 auto;padding:22px}
#lateral{position:sticky;top:calc(var(--altura-topo, 60px) + 10px);width:300px;flex:0 0 300px;max-height:calc(100vh - 84px);
  overflow:auto;background:var(--superficie);border:1px solid var(--borda);border-radius:var(--raio);
  padding:14px;box-shadow:var(--sombra)}
#lateral h2{font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:var(--texto-suave);
  margin:4px 0 10px}
#sumario{list-style:none;margin:0;padding:0;font-size:14px}
#sumario>li{margin:2px 0}
#sumario a{display:flex;gap:8px;align-items:baseline;padding:7px 8px;border-radius:7px;color:var(--texto)}
#sumario a:hover{background:var(--fundo);text-decoration:none}
#sumario a.ativo{background:rgba(13,110,253,.1);color:var(--azul);font-weight:600}
#sumario .num{color:var(--texto-suave);font-variant-numeric:tabular-nums;font-size:12px;min-width:18px}
#sumario .sub{list-style:none;margin:2px 0 8px 26px;padding:0;font-size:13px}
#sumario .sub a{padding:4px 6px;color:var(--texto-suave)}
#sumario li.oculto{display:none}
main{flex:1;min-width:0}

/* ---- capítulos ---- */
.capitulo{margin-bottom:34px;scroll-margin-top:calc(var(--altura-topo, 60px) + 16px)}
.cabecalho-capitulo{display:flex;gap:14px;align-items:flex-start;margin:0 0 14px}
.cabecalho-capitulo .icone{font-size:30px;line-height:1.1}
.cabecalho-capitulo h2{margin:0;font-size:27px;line-height:1.25}
.cabecalho-capitulo p{margin:4px 0 0;color:var(--texto-suave)}
.secao{background:var(--superficie);border:1px solid var(--borda);border-radius:var(--raio);
  padding:22px 24px;margin:0 0 16px;box-shadow:var(--sombra);
  scroll-margin-top:calc(var(--altura-topo, 60px) + 16px)}
.secao h3{margin:0 0 12px;font-size:20px;line-height:1.3}
.secao h4{margin:18px 0 8px;font-size:16px}
.secao p{margin:.6em 0}
.secao ul,.secao ol{margin:.6em 0;padding-left:1.35em}
.secao li{margin:.28em 0}
.secao.escondido{display:none}
.duas-colunas{display:grid;grid-template-columns:1fr 1fr;gap:18px}
@media (max-width:760px){.duas-colunas{grid-template-columns:1fr}}

/* ---- passos ---- */
ol.passos{counter-reset:passo;list-style:none;padding:0;margin:14px 0}
ol.passos li{position:relative;padding:0 0 12px 42px;margin:0}
ol.passos li::before{counter-increment:passo;content:counter(passo);position:absolute;left:0;top:-2px;
  width:28px;height:28px;border-radius:50%;background:var(--azul);color:#fff;font-weight:700;
  font-size:14px;display:grid;place-items:center}
ol.passos li::after{content:"";position:absolute;left:13px;top:28px;bottom:0;width:2px;
  background:var(--borda)}
ol.passos li:last-child{padding-bottom:0}
ol.passos li:last-child::after{display:none}

/* ---- tabelas ---- */
.tabela-rolagem{overflow-x:auto;margin:14px 0}
.tabela{width:100%;border-collapse:collapse;font-size:14.5px}
.tabela caption{caption-side:top;text-align:left;font-weight:700;font-size:13px;
  color:var(--texto-suave);text-transform:uppercase;letter-spacing:.06em;padding-bottom:6px}
.tabela th,.tabela td{border:1px solid var(--borda);padding:9px 11px;text-align:left;vertical-align:top}
.tabela thead th{background:var(--fundo);font-size:13px;text-transform:uppercase;letter-spacing:.05em}
.tabela tbody th{background:rgba(0,0,0,.02);font-weight:600;white-space:nowrap}
body.escuro .tabela tbody th{background:rgba(255,255,255,.04)}

/* ---- avisos ---- */
.aviso{border-left:4px solid;border-radius:8px;padding:12px 16px;margin:16px 0}
.aviso p{margin:.35em 0}
.aviso ul{margin:.35em 0;padding-left:1.2em}
.aviso-titulo{font-weight:700;margin:0 0 4px!important}
.aviso-dica{background:var(--dica-fundo);border-color:var(--dica);color:var(--dica)}
.aviso-atencao{background:var(--atencao-fundo);border-color:#C99700;color:var(--atencao)}
.aviso-perigo{background:var(--perigo-fundo);border-color:#C82333;color:var(--perigo)}
.aviso-info{background:var(--info-fundo);border-color:#0A58CA;color:var(--info)}
.pilula{display:inline-block;border-radius:999px;padding:1px 9px;font-size:12px;font-weight:700}
.pilula-dica{background:var(--dica-fundo);color:var(--dica)}
.pilula-atencao{background:var(--atencao-fundo);color:var(--atencao)}
.pilula-perigo{background:var(--perigo-fundo);color:var(--perigo)}
.marca-avancado{background:rgba(13,110,253,.12);color:var(--azul);border-radius:5px;
  padding:1px 6px;font-size:12px;font-weight:700;white-space:nowrap}

/* ---- figuras ---- */
figure{margin:16px 0}
figure img{width:100%;height:auto;max-height:min(620px,72vh);object-fit:contain;
  object-position:top left;border:1px solid var(--borda);border-radius:8px;cursor:zoom-in;
  display:block;background:#F8F9FA}
figure img:hover,figure img:focus-visible{border-color:var(--azul);outline:none}
figcaption{font-size:13.5px;color:var(--texto-suave);margin-top:7px}
figcaption .ampliar{float:right;font-size:12.5px;color:var(--azul)}
#luz{position:fixed;inset:0;background:rgba(10,12,16,.9);display:none;place-items:center;
  z-index:80;padding:24px;cursor:zoom-out}
#luz.aberta{display:grid}
#luz img{max-width:100%;max-height:100%;border-radius:8px;box-shadow:0 20px 60px rgba(0,0,0,.5)}
#luz .fechar{position:fixed;top:16px;right:22px;color:#fff;font-size:30px;background:none;
  border:none;cursor:pointer}

/* ---- avançado ---- */
details.avancado{margin:14px 0;border:1px dashed var(--borda);border-radius:8px;padding:10px 14px;
  background:rgba(13,110,253,.03)}
details.avancado summary{cursor:pointer;font-weight:600;color:var(--azul);font-size:14px}
details.avancado[open] summary{margin-bottom:8px}

/* ---- simuladores ---- */
.demo{border:1px solid var(--borda);border-radius:var(--raio);padding:16px;margin:16px 0;
  background:linear-gradient(180deg,rgba(13,110,253,.05),transparent 60%)}
.demo h4{margin:0 0 10px;font-size:15px}
.demo .linha{display:flex;flex-wrap:wrap;gap:10px;align-items:flex-end;margin-bottom:10px}
.demo label{font-size:13px;color:var(--texto-suave);display:block;margin-bottom:3px}
.demo input,.demo select{padding:8px 10px;border:1px solid var(--borda);border-radius:7px;
  background:var(--superficie);color:var(--texto);font-size:15px;width:130px}
.demo [data-papel="filtro"]{width:200px}
.demo button{padding:9px 14px;border-radius:7px;border:1px solid var(--azul);background:var(--azul);
  color:#fff;font-weight:600;cursor:pointer;font-size:14px}
.demo button.secundario{background:transparent;color:var(--azul)}
.demo .resultado{font-size:22px;font-weight:700;margin-top:8px}
.demo .resultado.erro{color:#C82333;font-size:15px;font-weight:600}
.demo .dica{font-size:13px;color:var(--texto-suave)}
.passos-demo{list-style:none;padding:0;margin:0;counter-reset:d}
.passos-demo li{padding:9px 12px;border-radius:8px;margin:4px 0;border:1px solid transparent;
  display:flex;gap:10px;align-items:center;font-size:14.5px}
.passos-demo li .n{width:24px;height:24px;border-radius:50%;background:var(--fundo);
  border:1px solid var(--borda);display:grid;place-items:center;font-size:12px;font-weight:700;flex:0 0 auto}
.passos-demo li.atual{background:rgba(13,110,253,.1);border-color:var(--azul)}
.passos-demo li.feito .n{background:var(--azul);color:#fff;border-color:var(--azul)}
.passos-demo li.atual .n{background:var(--azul);color:#fff;border-color:var(--azul)}
.matriz-perfis{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px}
.matriz-perfis label{display:flex;align-items:center;gap:6px;font-size:13px;background:var(--superficie);
  border:1px solid var(--borda);border-radius:999px;padding:5px 11px;cursor:pointer}
.matriz-perfis input{width:auto;margin:0}

/* ---- busca ---- */
#resultado-busca{font-size:13px;color:var(--texto-suave);margin:0 0 12px;display:none}
#resultado-busca.visivel{display:block}
mark{background:#FFE69C;color:#212529;border-radius:3px;padding:0 2px}
body.escuro mark{background:#8A6D00;color:#FFF}

/* ---- rodapé ---- */
#fim{max-width:1500px;margin:0 auto;padding:0 22px 44px;color:var(--texto-suave);font-size:13.5px}
.assinatura{font-size:13px;color:var(--texto-suave);border-top:1px solid var(--borda);padding-top:12px}

/* ---- tela pequena ---- */
@media (max-width:720px){
  #topo{flex-wrap:wrap;padding:8px 12px;gap:8px}
  #topo .marca{flex:1;font-size:15px}
  #topo .marca .selo{display:none}
  #busca{order:3;flex-basis:100%;max-width:none}
  #lateral{max-height:none}
}
@media (max-width:1080px){
  #casca{padding:14px;gap:0}
  #lateral{position:fixed;z-index:50;left:0;bottom:0;width:300px;max-height:none;
    top:calc(var(--altura-topo, 60px) + 6px);
    border-radius:0 10px 10px 0;transform:translateX(-104%);transition:transform .18s ease}
  #lateral.aberta{transform:none}
  #menu-botao{display:inline-block}
  .cabecalho-capitulo h2{font-size:23px}
  .secao{padding:16px 15px}
}
@media (min-width:1081px){#menu-botao{display:none}}

/* ---- impressão ---- */
@media print{
  #topo,#lateral,#luz,#progresso,#fim .voltar{display:none!important}
  body{background:#fff}
  #casca{display:block;padding:0;max-width:none}
  .secao{box-shadow:none;border:1px solid #ccc;break-inside:avoid-page}
  .capitulo{break-before:page}
  details.avancado{display:block}
  details.avancado>summary{list-style:none}
  a{color:inherit;text-decoration:none}
  figure img{max-height:9cm;object-fit:contain}
}
"""

JS = r"""
(function(){
  "use strict";

  // ---- menu lateral em tela pequena ----
  var lateral = document.getElementById('lateral');
  var botaoMenu = document.getElementById('menu-botao');
  var topo = document.getElementById('topo');
  // O topo cresce quando a busca cai para a segunda linha (celular): o painel e as
  // âncoras usam a altura real, senão o sumário cobre o campo de busca.
  function medirTopo(){
    if (!topo) return;
    document.documentElement.style.setProperty('--altura-topo', topo.offsetHeight + 'px');
  }
  medirTopo();
  window.addEventListener('resize', medirTopo);
  function fecharMenu(){
    lateral.classList.remove('aberta');
    if (botaoMenu) botaoMenu.setAttribute('aria-expanded', 'false');
  }
  if (botaoMenu) {
    botaoMenu.addEventListener('click', function(){
      var aberto = lateral.classList.toggle('aberta');
      botaoMenu.setAttribute('aria-expanded', aberto ? 'true' : 'false');
    });
    // no celular, escolher um capítulo fecha o painel
    lateral.addEventListener('click', function(evento){
      var link = evento.target.closest ? evento.target.closest('a') : null;
      if (link) fecharMenu();
    });
    document.addEventListener('click', function(evento){
      if (window.innerWidth > 1080) return;
      if (lateral.contains(evento.target) || botaoMenu.contains(evento.target)) return;
      lateral.classList.remove('aberta');
      botaoMenu.setAttribute('aria-expanded','false');
    });
  }

  // ---- tema claro/escuro (sem guardar nada: a página funciona em sandbox) ----
  var botaoTema = document.getElementById('tema-botao');
  if (botaoTema) {
    var lua = botaoTema.innerHTML;
    var sol = botaoTema.getAttribute('data-sol') || lua;
    botaoTema.addEventListener('click', function(){
      var escuro = document.body.classList.toggle('escuro');
      botaoTema.innerHTML = escuro ? sol : lua;
      botaoTema.setAttribute('aria-label', escuro ? 'Usar tema claro' : 'Usar tema escuro');
    });
  }

  // ---- barra de progresso da leitura ----
  var barra = document.getElementById('progresso');
  function progresso(){
    var altura = document.documentElement.scrollHeight - window.innerHeight;
    var lido = window.scrollY;
    barra.style.width = (altura > 0 ? (lido / altura) * 100 : 0) + '%';
  }
  window.addEventListener('scroll', progresso, {passive:true});
  progresso();

  // ---- sumário ativo conforme a leitura ----
  // Um ouvinte de rolagem calculado é mais previsível que IntersectionObserver
  // quando a pessoa salta de capítulo pelo sumário (vários alvos cruzam a tela
  // ao mesmo tempo e a "última entrada observada" não é a mais visível).
  var links = Array.prototype.slice.call(document.querySelectorAll('#sumario a'));
  var itensSumario = links.map(function(link){
    return {link: link, alvo: document.querySelector(link.getAttribute('href'))};
  }).filter(function(item){ return item.alvo; });
  var caixaSumario = document.getElementById('lateral');
  var pendente = false;
  function atualizarAtivo(){
    pendente = false;
    if (!itensSumario.length) return;
    var linha = window.scrollY + 130;
    var atual = null;
    itensSumario.forEach(function(item){
      var topo = item.alvo.getBoundingClientRect().top + window.scrollY;
      if (topo <= linha) atual = item;
    });
    if (!atual) atual = itensSumario[0];
    links.forEach(function(link){ link.classList.remove('ativo'); });
    atual.link.classList.add('ativo');
    if (caixaSumario) {
      // mede pela tela, não por offsetTop: o painel é "sticky" e isso muda o pai
      var caixa = caixaSumario.getBoundingClientRect();
      var linhaLink = atual.link.getBoundingClientRect();
      if (linhaLink.top < caixa.top + 8 || linhaLink.bottom > caixa.bottom - 16) {
        caixaSumario.scrollTop += (linhaLink.top - caixa.top) - caixaSumario.clientHeight / 2 + 20;
      }
    }
  }
  function agendarAtivo(){
    if (pendente) return;
    pendente = true;
    window.requestAnimationFrame(atualizarAtivo);
  }
  window.addEventListener('scroll', agendarAtivo, {passive:true});
  window.addEventListener('resize', agendarAtivo);
  window.addEventListener('hashchange', agendarAtivo);
  atualizarAtivo();

  // ---- imagem ampliada ----
  var luz = document.getElementById('luz');
  var luzImg = luz ? luz.querySelector('img') : null;
  document.querySelectorAll('figure img').forEach(function(img){
    img.addEventListener('click', function(){
      luzImg.src = img.src;
      luzImg.alt = img.alt;
      luz.classList.add('aberta');
      luzImg.focus();
    });
  });
  function fecharLuz(){ if (luz) luz.classList.remove('aberta'); }
  if (luz) {
    luz.addEventListener('click', fecharLuz);
    document.addEventListener('keydown', function(e){ if (e.key === 'Escape') fecharLuz(); });
  }

  // ---- busca no manual ----
  var campo = document.getElementById('busca');
  var aviso = document.getElementById('resultado-busca');
  var secoes = Array.prototype.slice.call(document.querySelectorAll('.secao'));
  var capitulos = Array.prototype.slice.call(document.querySelectorAll('.capitulo'));
  function normalizar(texto){
    return (texto || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'');
  }
  function limparMarcas(raiz){
    raiz.querySelectorAll('mark.destaque').forEach(function(marca){
      var pai = marca.parentNode;
      pai.replaceChild(document.createTextNode(marca.textContent), marca);
      pai.normalize();
    });
  }
  function marcar(raiz, termo){
    if (!termo) return;
    var alvo = normalizar(raiz.textContent);
    var posicao = alvo.indexOf(termo);
    if (posicao < 0) return;
    // destaca só a primeira ocorrência de cada seção: o suficiente para localizar
    var andador = document.createTreeWalker(raiz, NodeFilter.SHOW_TEXT, {
      acceptNode: function(no){
        if (!no.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
        if (no.parentNode.nodeName === 'MARK') return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    var no, contador = 0;
    while ((no = andador.nextNode())) {
      var texto = normalizar(no.nodeValue);
      var achou = texto.indexOf(termo);
      if (achou >= 0) {
        var antes = no.nodeValue.slice(0, achou);
        var meio = no.nodeValue.slice(achou, achou + termo.length);
        var depois = no.nodeValue.slice(achou + termo.length);
        var marca = document.createElement('mark');
        marca.className = 'destaque';
        marca.textContent = meio;
        var pai = no.parentNode;
        pai.replaceChild(marca, no);
        if (depois) pai.insertBefore(document.createTextNode(depois), marca.nextSibling);
        if (antes) pai.insertBefore(document.createTextNode(antes), marca);
        contador++;
        if (contador >= 2) return;
      }
    }
  }
  var espera = null;
  if (campo) {
    campo.addEventListener('input', function(){
      clearTimeout(espera);
      espera = setTimeout(function(){
        var termo = normalizar(campo.value.trim());
        limparMarcas(document.body);
        var visiveis = 0;
        secoes.forEach(function(secao){
          var bate = !termo || normalizar(secao.textContent).indexOf(termo) >= 0;
          secao.classList.toggle('escondido', !bate);
          if (bate) { visiveis++; marcar(secao, termo); }
        });
        capitulos.forEach(function(capitulo){
          var algum = capitulo.querySelector('.secao:not(.escondido)');
          capitulo.style.display = algum ? '' : 'none';
        });
        // o sumário acompanha a busca: só fica o caminho que ainda existe na página
        document.querySelectorAll('#sumario a').forEach(function(link){
          var alvo = document.querySelector(link.getAttribute('href'));
          if (!alvo) return;
          var visivel = alvo.classList.contains('secao')
            ? !alvo.classList.contains('escondido')
            : (alvo.querySelector('.secao:not(.escondido)') !== null);
          var item = link.parentNode;
          if (item && item.tagName === 'LI') item.classList.toggle('oculto', !visivel);
        });
        document.querySelectorAll('#sumario ul.sub').forEach(function(lista){
          var algum = lista.querySelector('li:not(.oculto)');
          lista.parentNode.classList.toggle('oculto', !algum);
        });
        if (termo) {
          aviso.textContent = visiveis
            ? visiveis + ' seção(ões) com "' + campo.value.trim() + '"'
            : 'Nada encontrado para "' + campo.value.trim() + '" — tente outra palavra (ex.: troco, sangria, backup).';
          aviso.classList.add('visivel');
        } else {
          aviso.classList.remove('visivel');
        }
      }, 180);
    });
    campo.addEventListener('keydown', function(e){
      if (e.key === 'Escape') { campo.value = ''; campo.dispatchEvent(new Event('input')); }
    });
  }

  // ---- simulador de troco ----
  var troco = document.querySelector('[data-demo="troco"]');
  if (troco) {
    var centavos = function(valor){
      var limpo = String(valor).replace(/[^\d,.-]/g,'').replace(/\./g,'').replace(',', '.');
      var numero = parseFloat(limpo);
      if (isNaN(numero)) return null;
      return Math.round(numero * 100);
    };
    var reais = function(c){ return 'R$ ' + (c/100).toFixed(2).replace('.', ','); };
    var saida = troco.querySelector('[data-papel="saida"]');
    var detalhe = troco.querySelector('[data-papel="detalhe"]');
    var calcular = function(){
      var total = centavos(troco.querySelector('[data-papel="total"]').value);
      var soma = 0;
      troco.querySelectorAll('[data-papel="pago"]').forEach(function(campo){
        soma += centavos(campo.value) || 0;
      });
      if (total === null || total <= 0) {
        saida.className = 'resultado erro';
        saida.textContent = 'Informe o total da venda.';
        detalhe.textContent = '';
        return;
      }
      if (soma <= 0) {
        saida.className = 'resultado erro';
        saida.textContent = 'Informe quanto o cliente entregou.';
        detalhe.textContent = '';
        return;
      }
      if (soma < total) {
        saida.className = 'resultado erro';
        saida.textContent = 'Faltam ' + reais(total - soma) + ' para fechar a venda.';
        detalhe.textContent = 'O programa não deixa finalizar com pagamento incompleto.';
        return;
      }
      var sobra = soma - total;
      saida.className = 'resultado';
      saida.textContent = 'Troco: ' + reais(sobra);
      detalhe.textContent = 'Total ' + reais(total) + ' · recebido ' + reais(soma) +
        (sobra === 0 ? ' · sem troco' : '');
    };
    troco.querySelectorAll('input').forEach(function(campo){
      campo.addEventListener('input', calcular);
    });
    troco.querySelector('[data-papel="calcular"]').addEventListener('click', function(evento){
      evento.preventDefault();
      calcular();
    });
    calcular();
  }

  // ---- simulador do fluxo da venda (pode aparecer mais de uma vez) ----
  document.querySelectorAll('[data-demo="fluxo"]').forEach(function(fluxo){
    var itens = fluxo.querySelectorAll('.passos-demo li');
    var rotulo = fluxo.querySelector('[data-papel="rotulo"]');
    var atual = 0;
    function pintar(){
      itens.forEach(function(item, indice){
        item.classList.toggle('atual', indice === atual);
        item.classList.toggle('feito', indice < atual);
      });
      rotulo.textContent = 'Passo ' + (atual + 1) + ' de ' + itens.length;
    }
    fluxo.querySelector('[data-papel="proximo"]').addEventListener('click', function(){
      atual = (atual + 1) % itens.length; pintar();
    });
    fluxo.querySelector('[data-papel="anterior"]').addEventListener('click', function(){
      atual = (atual - 1 + itens.length) % itens.length; pintar();
    });
    pintar();
  });

  // ---- matriz de permissões ----
  var matriz = document.querySelector('[data-demo="permissoes"]');
  if (matriz) {
    var corpo = matriz.querySelector('tbody');
    var filtro = matriz.querySelector('[data-papel="filtro"]');
    var caixas = Array.prototype.slice.call(matriz.querySelectorAll('.matriz-perfis input'));
    var linhas = Array.prototype.slice.call(corpo.querySelectorAll('tr'));
    var celulas = Array.prototype.slice.call(matriz.querySelectorAll('[data-perfil]'));
    function aplicar(){
      var escolhidos = caixas.filter(function(c){ return c.checked; }).map(function(c){ return c.value; });
      var termo = normalizar(filtro.value.trim());
      linhas.forEach(function(linha){
        var acao = linha.getAttribute('data-acao');
        linha.style.display = (!termo || normalizar(acao).indexOf(termo) >= 0) ? '' : 'none';
      });
      celulas.forEach(function(celula){
        var perfil = celula.getAttribute('data-perfil');
        celula.style.display = (escolhidos.length === 0 || escolhidos.indexOf(perfil) >= 0) ? '' : 'none';
      });
    }
    caixas.forEach(function(c){ c.addEventListener('change', aplicar); });
    filtro.addEventListener('input', aplicar);
    aplicar();
  }

  // ---- filtro da tabela de atalhos ----
  var atalhos = document.querySelector('[data-demo="atalhos"]');
  if (atalhos) {
    var entrada = atalhos.querySelector('[data-papel="filtro"]');
    var lista = Array.prototype.slice.call(atalhos.querySelectorAll('tbody tr'));
    entrada.addEventListener('input', function(){
      var termo = normalizar(entrada.value.trim());
      lista.forEach(function(linha){
        linha.style.display = normalizar(linha.textContent).indexOf(termo) >= 0 ? '' : 'none';
      });
    });
  }
})();
"""


# -- simuladores ---------------------------------------------------------------
def demo_troco() -> str:
    campos = "".join(
        f'<label>Recebido {indice}<input data-papel="pago" inputmode="decimal" '
        f'placeholder="0,00"></label>'
        for indice in (1, 2, 3)
    )
    return f"""
<div class="demo" data-demo="troco">
<h4>Calculadora de troco</h4>
<p class="dica">Digite valores como <code>10</code>, <code>10,50</code> ou <code>R$ 10,50</code>. O
troco é sempre o que passou do total.</p>
<div class="linha">
  <label>Total da venda<input data-papel="total" inputmode="decimal" placeholder="0,00"></label>
  {campos}
  <button type="button" data-papel="calcular">Calcular</button>
</div>
<p class="resultado" data-papel="saida">Informe o total e quanto foi recebido.</p>
<p class="dica" data-papel="detalhe"></p>
</div>
"""


def demo_fluxo() -> str:
    passos = [
        ("Abrir o turno no módulo Caixa", "informe o fundo de troco; sem isso o PDV não finaliza venda"),
        ("Identificar a venda", "cliente é opcional à vista e obrigatório no crediário"),
        ("Lançar os itens", "digite o código e aperte Enter; o leitor faz o mesmo caminho"),
        ("Receber o pagamento", "até três formas; dinheiro calcula o troco na hora"),
        ("Finalizar e imprimir", "F4 finaliza; F8 reimprime a última venda"),
    ]
    itens = "".join(
        f'<li><span class="n">{indice + 1}</span><span><strong>{titulo}</strong> — {texto}</span></li>'
        for indice, (titulo, texto) in enumerate(passos)
    )
    return f"""
<div class="demo" data-demo="fluxo">
<h4>O caminho de uma venda</h4>
<ol class="passos-demo">{itens}</ol>
<div class="linha" style="margin-top:12px">
  <button type="button" class="secundario" data-papel="anterior">← Anterior</button>
  <button type="button" data-papel="proximo">Próximo →</button>
  <span class="dica" data-papel="rotulo"></span>
</div>
</div>
"""


def demo_permissoes(dados: dict) -> str:
    permissoes = dados["permissoes"]
    acoes = dados["acoes"]
    caixas = "".join(
        f'<label><input type="checkbox" value="{perfil}"> {PERFIS_ROTULO.get(perfil, perfil)}</label>'
        for perfil in PERFIS
    )
    cabecalho = "".join(
        f'<th scope="col" data-perfil="{perfil}">{PERFIS_ROTULO.get(perfil, perfil)}</th>'
        for perfil in PERFIS
    )
    linhas = []
    for acao in acoes:
        celulas = "".join(
            f'<td data-perfil="{perfil}">'
            f'{"✓" if acao in permissoes.get(perfil, []) else "·"}</td>'
            for perfil in PERFIS
        )
        linhas.append(
            f'<tr data-acao="{html.escape(acao)}"><th scope="row">{html.escape(acao)}</th>{celulas}</tr>'
        )
    total = "".join(
        f"<li><strong>{PERFIS_ROTULO.get(perfil, perfil)}</strong>: "
        f"{len(permissoes.get(perfil, []))} de {len(acoes)} ações</li>"
        for perfil in PERFIS
    )
    return f"""
<div class="demo" data-demo="permissoes">
<h4>Quem pode o quê (matriz real do programa)</h4>
<p class="dica">Esta tabela é montada a partir das permissões que o programa aplica de verdade.
Marque um perfil para esconder as colunas dos outros, ou digite parte do nome de uma ação.</p>
<div class="matriz-perfis">{caixas}</div>
<div class="linha"><label>Filtrar ação<input data-papel="filtro" placeholder="ex.: DESCONTO"></label></div>
<div class="tabela-rolagem" style="max-height:420px;overflow:auto">
<table class="tabela">
<thead><tr><th scope="col">Ação</th>{cabecalho}</tr></thead>
<tbody>{"".join(linhas)}</tbody>
</table></div>
<ul class="dica">{total}</ul>
</div>
"""


def demo_atalhos(dados: dict) -> str:
    guia = dados["guia"]["atalhos"]
    extras = [("F1", "Abre o guia completo de ajuda, de qualquer tela")]
    vistos: dict[str, str] = {}
    for tecla, descricao in list(guia.atalhos) + extras:
        vistos.setdefault(tecla, descricao)
    linhas = "".join(
        f"<tr><td><kbd>{html.escape(tecla)}</kbd></td><td>{html.escape(descricao)}</td></tr>"
        for tecla, descricao in vistos.items()
    )
    return f"""
<div class="demo" data-demo="atalhos">
<h4>Encontre a tecla</h4>
<p class="dica">Digite o que você quer fazer — "cancelar", "reimprimir", "cliente" — e a tabela
filtra.</p>
<div class="linha"><label>O que você quer fazer
<input data-papel="filtro" style="width:220px" placeholder="ex.: reimprimir"></label></div>
<div class="tabela-rolagem"><table class="tabela">
<thead><tr><th>Tecla</th><th>Faz</th></tr></thead>
<tbody>{linhas}</tbody></table></div>
</div>
"""


DEMOS = {
    "troco": lambda dados: demo_troco(),
    "fluxo": lambda dados: demo_fluxo(),
    "fluxo-venda": lambda dados: demo_fluxo(),
    "permissoes": demo_permissoes,
    "atalhos": demo_atalhos,
}


# -- montagem ------------------------------------------------------------------
def _texto_com_versao(texto: str, dados: dict) -> str:
    return texto.replace("{VERSAO}", str(dados["versao"]))


def render_secao(secao: dict, dados: dict, imagens: dict[str, str]) -> str:
    partes = [f'<section class="secao" id="{secao["id"]}">']
    partes.append(f'<h3>{html.escape(secao["titulo"])}</h3>')
    partes.append(_texto_com_versao(secao.get("corpo", ""), dados))

    chave = secao.get("guia")
    if chave:
        tema = dados["guia"].get(chave)
        if tema is None:
            raise SystemExit(
                f"A seção {secao['id']!r} pede o tema {chave!r}, que não existe no guia do programa."
            )
        partes.append(passos_do_guia(tema))
        partes.append(campos_do_guia(tema))
        partes.append(atalhos_do_guia(tema))
        partes.append(cuidados_do_guia(tema))

    demo = secao.get("demo")
    if demo:
        montar = DEMOS.get(demo)
        if montar is None:
            raise SystemExit(f"Simulador desconhecido: {demo!r} (seção {secao['id']!r})")
        partes.append(montar(dados))

    imagem = secao.get("imagem")
    if imagem:
        nome, legenda = imagem
        fonte = imagens.get(nome)
        if fonte:
            # width/height reservam o espaço antes da imagem pintar: sem isso, clicar
            # num capítulo do sumário cai no lugar errado enquanto as figuras carregam.
            medida = f' width="{fonte.largura}" height="{fonte.altura}"' if fonte.largura else ""
            partes.append(
                f'<figure><img src="{fonte.uri}" alt="{html.escape(legenda)}"{medida} '
                f'tabindex="0"><figcaption>{html.escape(legenda)}'
                f'<span class="ampliar">clique para ampliar</span></figcaption></figure>'
            )

    if secao.get("avancado"):
        partes.append(
            '<details class="avancado"><summary>Para usuário avançado</summary>'
            f'{secao["avancado"]}</details>'
        )
    partes.append("</section>")
    return "\n".join(parte for parte in partes if parte)


def render_capitulo(indice: int, capitulo: dict, dados: dict, imagens: dict[str, str]) -> str:
    corpo = "\n".join(
        render_secao(secao, dados, imagens) for secao in capitulo["secoes"]
    )
    return f"""
<section class="capitulo" id="{capitulo["id"]}" data-capitulo="{capitulo["id"]}">
  <header class="cabecalho-capitulo">
    <span class="icone" aria-hidden="true">{capitulo["icone"]}</span>
    <div>
      <h2>Capítulo {indice} · {html.escape(capitulo["titulo"])}</h2>
      <p>{html.escape(capitulo["resumo"])}</p>
    </div>
  </header>
  {corpo}
</section>
"""


def montar_sumario(capitulos: list[dict]) -> str:
    itens = []
    for indice, capitulo in enumerate(capitulos, start=1):
        subsecoes = "".join(
            f'<li><a href="#{secao["id"]}">{html.escape(secao["titulo"])}</a></li>'
            for secao in capitulo["secoes"]
        )
        itens.append(
            f'<li><a href="#{capitulo["id"]}"><span class="num">{indice}</span>'
            f'<span>{html.escape(capitulo["titulo"])}</span></a></li>'
            f'<li><ul class="sub">{subsecoes}</ul></li>'
        )
    return "\n".join(itens)


def montar_html(dados: dict, imagens: dict[str, str]) -> str:
    capitulos = CAPITULOS
    corpo = "\n".join(
        render_capitulo(indice, capitulo, dados, imagens)
        for indice, capitulo in enumerate(capitulos, start=1)
    )
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Manual do Bússola PDV — {dados["versao"]}</title>
<meta name="description" content="Manual completo do Bússola Sistema PDV Open Source: instalação,
operação do caixa, crediário, estoque, backup, administração e atalhos.">
<style>{CSS}</style>
</head>
<body>
<div id="progresso" aria-hidden="true"></div>

<header id="topo">
  <button class="botao-icone" id="menu-botao" aria-expanded="false" aria-controls="lateral"
          aria-label="Abrir o sumário">{ICONE_MENU}</button>
  <div class="marca">{ICONE_BUSSOLA} Bússola PDV
    <span class="selo">manual {dados["versao"]}</span></div>
  <input id="busca" type="search" placeholder="Buscar no manual (ex.: troco, sangria, backup)"
         aria-label="Buscar no manual">
  <button class="botao-icone" id="tema-botao" aria-label="Usar tema escuro"
          data-sol="{html.escape(ICONE_SOL)}">{ICONE_LUA}</button>
  <button class="botao-icone" onclick="window.print()" aria-label="Imprimir o manual">{ICONE_IMPRIMIR}</button>
</header>

<div id="casca">
  <nav id="lateral" aria-label="Sumário do manual">
    <h2>Sumário</h2>
    <ol id="sumario">{montar_sumario(capitulos)}</ol>
  </nav>

  <main id="conteudo">
    <p id="resultado-busca" role="status" aria-live="polite"></p>
    {corpo}
  </main>
</div>

<footer id="fim">
  <p>Bússola Sistema PDV Open Source · manual gerado do próprio programa ·
  <a href="https://github.com/davidcreator/bussolapdv">código-fonte no GitHub</a> ·
  licença GPL-2.0-or-later</p>
  <p class="voltar"><a href="#topo">Voltar ao topo ↑</a> · versão {dados["versao"]} ·
  este manual abre sem internet</p>
</footer>

<div id="luz" role="dialog" aria-modal="true" aria-label="Imagem ampliada">
  <button class="fechar" aria-label="Fechar">×</button>
  <img alt="">
</div>

<script>{JS}</script>
</body>
</html>
"""


def validar(pagina: str) -> None:
    """Confere o que quebraria o manual em silêncio: âncora órfã e id repetido.

    Um `href="#pdv"` sem destino leva a lugar nenhum quando a pessoa clica; um `id`
    repetido faz o navegador ir sempre para o primeiro. Os dois são invisíveis para
    `ruff`/`mypy` e para quem gerou o arquivo com pressa.
    """
    identidades = re.findall(r'\sid="([^"]+)"', pagina)
    repetidos = {i for i in identidades if identidades.count(i) > 1}
    if repetidos:
        raise SystemExit(f"Id repetido no manual: {sorted(repetidos)}")

    destinos = set(re.findall(r'href="#([^"]+)"', pagina))
    orfas = sorted(destinos - set(identidades))
    if orfas:
        raise SystemExit(f"Âncora sem destino no manual: {orfas}")

    # Nada de recurso externo: o manual precisa abrir sem internet, e a prévia do
    # repositório roda em iframe sem rede.
    externos = re.findall(r'(?:src|srcset)="(https?://[^"]+)"', pagina)
    if externos:
        raise SystemExit(f"Recurso externo no manual (quebraria offline): {externos}")
    if "@import" in pagina or "fonts.googleapis" in pagina:
        raise SystemExit("O manual não pode importar fonte externa: precisa abrir sem rede.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Gera o manual web do Bússola PDV em um único arquivo HTML."
    )
    parser.add_argument("--saida", default=str(SAIDA_PADRAO), help="arquivo de saída")
    parser.add_argument(
        "--sem-imagens", action="store_true", help="gera sem as capturas (HTML leve)"
    )
    argumentos = parser.parse_args(argv)

    dados = _dados()
    pedidas: list[str] = []
    for capitulo in CAPITULOS:
        for secao in capitulo["secoes"]:
            imagem = secao.get("imagem")
            if imagem:
                pedidas.append(imagem[0])

    imagens: dict[str, str] = {}
    if not argumentos.sem_imagens:
        for nome in dict.fromkeys(pedidas):
            imagens[nome] = imagem_embutida(nome)

    destino = Path(argumentos.saida)
    destino.parent.mkdir(parents=True, exist_ok=True)
    pagina = montar_html(dados, imagens)
    validar(pagina)
    destino.write_text(pagina, encoding="utf-8")

    tamanho = destino.stat().st_size / (1024 * 1024)
    print(
        f"Manual gerado: {destino} ({tamanho:.2f} MB, {len(CAPITULOS)} capítulos, "
        f"{sum(len(c['secoes']) for c in CAPITULOS)} seções, {len(imagens)} imagens embutidas)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
