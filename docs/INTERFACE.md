# Interface: linguagem visual e componentes

A interface segue a **linguagem visual do [AdminLTE](https://github.com/ColorlibHQ/AdminLTE)**
(dashboard administrativo em Bootstrap, MIT): barra lateral escura com a marca no topo, painel do
usuário, menu com ícones, barra superior com botão de recolher, cabeçalho de página com trilha,
cartões brancos sobre fundo cinza-azulado, *small-boxes* coloridas para indicadores, etiquetas de
status e rodapé discreto.

**O que é aproveitado:** hierarquia, densidade, proporções (cantos de 4 px, sombras discretas),
vocabulário de componentes e a ideia de skin. **O que não é aproveitado:** nenhum arquivo do projeto
original — não há CSS, HTML, fonte, imagem ou ícone do AdminLTE neste repositório. Tudo é
reconstruído em PySide6 (QSS + widgets) e pintado com a **paleta da loja**, para que a
personalização de cores do painel administrativo continue valendo.

## Estrutura da casca

```
┌───────────────┬──────────────────────────────────────────────┐
│ marca (faixa) │ ☰  Loja · Módulo                  [usuário]  │  barra superior (52 px)
│ painel usuário├──────────────────────────────────────────────┤
│               │ Módulo                     Início › Módulo   │  cabeçalho de conteúdo
│  navegação    ├──────────────────────────────────────────────┤
│  (ícones)     │  [KPI] [KPI] [KPI]                           │
│               │  cartão / grupo / tabela                     │  conteúdo
│               │                                              │
│ rodapé        ├──────────────────────────────────────────────┤
└───────────────┴──────────────────────────────────────────────┘  rodapé
```

A side bar recolhe para 62 px (só ícones) pelo botão `☰`; os rótulos ficam no *tooltip*.

## Cores (tokens)

Tudo sai de `dominio/marca.Paleta` e vira QSS em `ui/tema.py`. A skin padrão é a do AdminLTE:

| Token | Padrão | Papel |
|---|---|---|
| `primaria` | `#0D6EFD` | botões, faixa da marca, links |
| `primaria_escura` | `#343A40` | barra lateral, item ativo, tooltip |
| `secundaria` | `#17A2B8` | informação, ícone de indicador |
| `secundaria_clara` | `#D3E9F0` | seleção suave |
| `destaque` | `#FFC107` | item ativo da navegação, avisos |
| `fundo` | `#F4F6F9` | fundo do conteúdo |
| `superficie` | `#FFFFFF` | cartões, tabelas, barra superior |
| `texto` / `texto_suave` | `#212529` / `#6C757D` | texto principal / secundário |
| `sucesso` / `alerta` / `erro` | `#198754` / `#856404` / `#B02A37` | estados |
| `borda` | `#DEE2E6` | bordas e divisórias |
| `entrada` | `#FFFFFF` | fundo de campos |

Presets: `BUSSOLA` (padrão), `GRAFITE`, `ESMERALDA`, `NOTURNO`, `OCEANO`, além de
`PERSONALIZADO` quando o lojista troca uma cor. Paletas com contraste abaixo de 4,5:1 recebem aviso
na tela de tema; se o branco sobre a primária não passar, o texto do botão vira escuro.

## Componentes (`ui/widgets.py`)

| Componente | Equivalente no AdminLTE | Uso |
|---|---|---|
| `BarraLateral` | `main-sidebar` | marca, painel do usuário, navegação com ícones, recolher |
| `BarraSuperior` | `main-header` | botão de recolher, título da página, chip do usuário |
| `CabecalhoConteudo` | `content-header` + `breadcrumb` | título e trilha da página |
| `Cartao` | `card` | cabeçalho (título/subtítulo/ferramentas) + corpo |
| `CaixaInfo` | `small-box` | indicador com número grande, rótulo e ícone |
| `Selo` | `badge` | status: ativo, ruptura, cancelado, conciliado |
| `PilhaDePaginas` | — | pilha cuja altura segue a página visível |
| `Rodape` | `main-footer` | nome da loja, aviso de escopo e versão |
| `BotaoExportar` | `card-tools` + `dropdown` | menu Excel/PDF no cabeçalho do cartão; só aparece para quem tem `EXPORTAR_DADOS` |
| `ajustar_colunas` | `table-responsive` | coluna esticada + demais pelo conteúdo, para não cortar "Ponto de pedido" |

## Ícones (`ui/icones.py`)

25 desenhos SVG de 24×24 escritos neste repositório, com traço de 1,8 e pontas arredondadas,
coloridos em tempo de execução (cache por nome/cor/tamanho). Não há dependência de rede nem de
pacote de ícones; nome inexistente devolve ícone vazio em vez de quebrar a tela.

## Regras que a interface respeita

1. **A tela não calcula.** Cálculo é domínio; widget só mostra e emite intenção (ADR-012).
2. **Cor é dado.** A paleta vem do banco via `Marca`; nada de cor fixa em widget.
3. **Estado não é só cor.** Status aparece com texto + etiqueta, nunca apenas com cor.
4. **Nada é simulado.** Módulo inexistente mostra cartão explícito dizendo que não foi implementado
   (hoje: **Entradas** e **Parâmetros**).
5. **Tela de consulta desenha o relatório.** Clientes, Crediário e Estoque montam a tabela a partir do
   mesmo `Relatorio` que o botão Exportar grava (ADR-019): o que está na tela e o que vai para a
   planilha são a mesma consulta, no mesmo instante.
6. **Tudo que altera é auditado** — o rodapé lembra isso em todas as telas.

## Capturas

`docs/capturas/` é gerado por `make capturas` (`ferramentas/captura_telas.py`, Qt offscreen, sem
servidor gráfico): PDV vazio e com itens, caixa (e o caixa com o *Exportar* do turno), produtos,
fechamento, **clientes**, **crediário**, **estoque**, auditoria, login, as seis seções
administrativas, tema personalizado, menu recolhido e **primeiro uso** (tela onde se escolhe a
pasta dos dados).

As capturas de fechamento, clientes, crediário, estoque e do caixa com exportação usam a sessão de
gerente de propósito: o perfil Atendente não tem `EXPORTAR_DADOS` e, para ele, o botão não existe —
o que é o comportamento correto.

