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
| `BotaoImprimir` | `card-tools` | abre a prévia de impressão do documento que a tela montar; só aparece com `CUPOM_REIMPRIMIR` |
| `DialogoPreviaImpressao` | `modal` | papel (58/80/A4), impressora instalada, cópias, prévia desenhada e ações Imprimir / Salvar PDF / Salvar TXT |
| `ajustar_colunas` | `table-responsive` | coluna esticada + demais pelo conteúdo, para não cortar "Ponto de pedido" |

## Ícones (`ui/icones.py`)

25 desenhos SVG de 24×24 escritos neste repositório, com traço de 1,8 e pontas arredondadas,
coloridos em tempo de execução (cache por nome/cor/tamanho). Não há dependência de rede nem de
pacote de ícones; nome inexistente devolve ícone vazio em vez de quebrar a tela.

## Responsividade (ADR-021)

A interface não tem um tamanho de projeto: ela pergunta a largura e se reorganiza. Tudo o que decide
isso mora em `ui/responsivo.py` — nenhuma tela compara pixels por conta própria.

| Faixa | Largura | O que muda |
|---|---|---|
| **compacta** | < 900 px | sidebar recolhida (só ícones, com dica de tela), chip do usuário, trilha e lado direito do rodapé escondidos, margem de 18 → 10 px |
| **média** | 900–1179 px | sidebar aberta, chip visível, indicadores até 3 por linha |
| **ampla** | ≥ 1180 px | layout completo, até 4 indicadores por linha |

Peças que reagem à largura:

- **`GradeDeIndicadores`** — cartões de indicador em `QGridLayout`: 4 → 3 → 2 → 1 por linha, e a altura
  mínima cresce com o número de linhas (sem isso o segundo cartão era desenhado sobre o primeiro).
- **`CascaResponsiva`** — herdado por `JanelaPrincipal` e `JanelaAdmin`: recolhe a sidebar na faixa
  compacta, esconde os complementos e ajusta margens. O botão do menu continua valendo: a escolha
  manual do operador dura até a janela mudar de faixa.
- **`Cartao`** — cabeçalho em grade: abaixo de 640 px de cartão, as ferramentas ("Exportar", resumo da
  consulta) descem para a segunda linha em vez de alargar a página.
- **`ColunasDaTabela`** — mede o conteúdo (adiado 150 ms): se cabe, estica a coluna elástica; se não
  cabe, mantém cada coluna legível (piso de 84 px) e liga a rolagem horizontal da própria tabela.
- **`QScrollArea`** em volta da pilha de páginas, nas duas janelas — em 600 px de altura o PDV rola em
  vez de sobrepor os grupos, e a área administrativa usa `PilhaDePaginas` para não herdar a largura
  mínima da seção mais larga.
- **`FluxoDeAcoes`** — fileiras de botões quebram em várias linhas; `QHBoxLayout` não quebra e a
  fileira de ações de Usuários saía pela borda em 800 px.
- **`GradeDeCartoes`** — dois blocos de conteúdo lado a lado (identidade/prévia da marca) empilham
  quando não cabem.
- **`ajustar_dialogo()`** — login, autorização, primeiro uso e conferência de gaveta nunca nascem
  maiores do que a tela.

A janela recusa ficar menor que 720×480 (operação) e 700×460 (administração): abaixo disso a operação
deixa de ser segura, e é melhor um limite honesto do que um layout quebrado.

Medido, não só olhado: `make responsivo` (`ferramentas/verificar_responsivo.py`) abre as duas janelas em
800×600, 1024×768, 1280×800, 1366×768 e 1920×1080 e falha se alguma página pedir mais largura do que
tem, se uma coluna descer do mínimo legível, se a sidebar recolher sem motivo ou se a faixa não bater
com a largura. Hoje: **OK nas cinco resoluções**.

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
pasta dos dados). As capturas `21`, `22` e `23` são o mesmo PDV, Produtos e Caixa em **800×600**: ficam
ao lado das de 1280×820 para mostrar a interface se reorganizando (sidebar só de ícones, indicadores 2
por linha, ferramentas do cartão na segunda linha, tabela rolando na horizontal).

As capturas de fechamento, clientes, crediário, estoque e do caixa com exportação usam a sessão de
gerente de propósito: o perfil Atendente não tem `EXPORTAR_DADOS` e, para ele, o botão não existe —
o que é o comportamento correto.


## Impressão (`ui/impressao.py`)

A prévia é o único lugar da interface que conhece `QPrinter`: as telas chamam `BotaoImprimir` com uma
função que devolve o `DocumentoImpresso` **no clique**, e o diálogo cuida do resto. Ver
[IMPRESSAO.md](IMPRESSAO.md) para configuração e para o que foi (e não foi) testado.

- **Prévia no tamanho real do papel** — o cupom é desenhado em grade de colunas por
  `infra/impressao/papel.py`; a tela mostra a imagem gerada pelo mesmo código que imprime, então
  prévia e papel não divergem;
- **Papel trocável na hora** (58 ↔ 80 ↔ A4) com as medidas à vista: colunas, linhas e altura estimada;
- **Aviso quando o motor não serve**: `ESCPOS` + A4 mostra "o motor ESC/POS imprime bobina" em vez de
  falhar só no envio;
- **Falha com saída**: erro de impressora aparece no diálogo, com o motivo, e a venda continua
  registrada — o operador pode salvar PDF, tentar de novo (F8) ou seguir o expediente.

![Prévia de impressão](capturas/24_impressao_previa.png)
