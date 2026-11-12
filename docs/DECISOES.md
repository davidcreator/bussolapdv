# Decisões de arquitetura (ADRs) e pendências

Formato curto: contexto → decisão → consequência. Toda decisão aqui é reversível com migração e
registro no CHANGELOG; decisões marcadas **PENDENTE** dependem do responsável pelo projeto.

---

## ADR-001 — Dinheiro em inteiro de centavos, percentual em pontos-base

**Contexto.** O protótipo usa `Double` no VBA e valores com ponto flutuante nas células. Erro de
centavo é inaceitável em caixa.
**Decisão.** Todo valor monetário é `int` de centavos (`Dinheiro`); percentual é `int` de pontos-base
(`Percentual`, 1% = 100 bp); quantidade é inteiro escalonado em milésimos (`Quantidade`). `float` é
recusado na API. Arredondamento é explícito, meio-para-cima, em inteiros.
**Consequência.** 100% determinístico e testável; exige conversão na borda (UI, importação).

## ADR-002 — SQLite local com WAL, `foreign_keys` e `synchronous=FULL`

**Contexto.** Queda de energia não pode gravar meia venda; o padrão do SQLite desliga FKs.
**Decisão.** `PRAGMA foreign_keys=ON`, `journal_mode=WAL`, `synchronous=FULL`, `busy_timeout=5000` em
toda conexão, e transações com `BEGIN IMMEDIATE`.
**Consequência.** Durabilidade e serialização de escritores. Custo: escrita um pouco mais lenta.
**Limite declarado:** não é solução multi-caixa em rede; arquivo em compartilhamento não é suportado.

## ADR-003 — Um único turno aberto por caixa, garantido pelo banco

**Decisão.** Índice parcial `UNIQUE (caixa_id) WHERE status='ABERTO'`.
**Consequência.** A corrida "dois caixas abrindo ao mesmo tempo" é resolvida pelo banco, não por
checagem na UI.

## ADR-004 — Idempotência na própria venda

**Decisão.** `vendas.chave_idempotencia UNIQUE`; repetir a mesma solicitação devolve a venda original
com `ja_existia=True`, sem nova gravação e sem nova baixa de estoque.
**Consequência.** Duplo clique e retentativa após falha são seguros. A sequência de cupom pode
"pular" um número em caso de rollback — melhor que número duplicado.

## ADR-005 — Trilha de auditoria append-only com encadeamento de hash

**Contexto.** O prompt mestre exige trilha append-only e reconhece que SQLite não é imutável.
**Decisão.** Tabela `auditoria` protegida por triggers que abortam `UPDATE`/`DELETE`; cada evento
carrega `hash_anterior` e `hash` SHA-256 sobre uma serialização canônica (incluindo o hash anterior).
`AuditoriaRepositorio.verificar()` recalcula a cadeia.
**Consequência.** Alteração local é detectável; **não** impede um administrador de reescrever o
arquivo inteiro. Compensação: backup externo + verificação periódica + revisão.
**Não prometemos:** imutabilidade criptográfica, WORM ou "à prova de fraude".

## ADR-006 — Pagamento eletrônico nasce PENDENTE

**Decisão.** PIX/cartão são gravados como `PENDENTE` até confirmação humana registrada
(`confirmacao_manual=1`). Nenhum campo preenchido confirma recebimento.
**Consequência.** O fechamento lista pendências de forma explícita. Parâmetro
`venda.exigir_confirmacao_eletronica` permite bloquear a finalização enquanto houver pendência.
**PENDENTE:** integração com adquirente/TEF (fora de escopo até haver contrato e homologação).

## ADR-007 — Perfis e autorização autenticada, não "nome do gerente"

**Decisão.** `Perfil` (ATENDENTE 20 / CONTABILIDADE 30 / GERENTE 40 / ADMIN 70 / ADMIN_MASTER 100)
mapeia ações nomeadas (`Acao`). Ação excepcional exige **outro usuário autenticado** com a permissão;
senha via Argon2id; bloqueio por tentativas com parâmetros configuráveis.
**Consequência.** Desconto excepcional, sangria, estoque negativo, cancelamento e ajuste sempre têm
autorizador identificado no evento de auditoria. Bancos antigos (`OPERADOR`, `ADMINISTRADOR`) são
convertidos pela migração `0003`; os nomes antigos continuam como apelidos de leitura no código.

## ADR-008 — Crediário sem encargos inventados

**Decisão.** O sistema calcula principal, parcelas, vencimentos (com trava de fim de mês),
recebimentos parciais e aging. **Não** aplica juros/multa sem política aprovada.
**Consequência.** Nada de cobrança indevida por padrão. `encargos_centavos` existe como campo, mas só
é preenchido quando alguém informar valor explícito.
**PENDENTE:** política de juros, multa, carência e renegociação.

## ADR-009 — IDs UUID; cupom é sequência transacional

**Decisão.** Chaves primárias em UUID4 (texto). Número de cupom vem de `sequencias` com
`UPDATE ... RETURNING` dentro da transação, no formato `serie-número`.
**Consequência.** Integrações futuras não dependem de contador. Correlação por ID é estável.

## ADR-010 — Datas: instante em UTC, data comercial separada

**Decisão.** `criado_em`/`aberto_em` em UTC ISO-8601 com timezone; `data_negocio` em ISO no fuso da
loja (`America/Sao_Paulo` por padrão). Relógio é injetado (`RelogioFixo` em testes).
**Consequência.** Testes determinísticos e relatórios que não mudam com o fuso do computador.

## ADR-011 — Nada de exclusão de histórico

**Decisão.** Vendas canceladas permanecem com status `CANCELADA` + eventos compensatórios; títulos
recebidos com estorno geram evento inverso; itens de venda não podem ser alterados (trigger).
**Consequência.** Relatórios sempre reconciliam por ID e status.

## ADR-012 — UI só apresentação

**Decisão.** Nenhum cálculo financeiro em widget. A tela monta um carrinho de domínio e chama um caso
de uso; erros de domínio viram mensagens com código estável.
**Consequência.** Testes de domínio cobrem as regras; testes de UI só cobrem integração.

## ADR-013 — A matriz de permissões pertence ao Admin Master

**Decisão.** As permissões de cada perfil são **dados** (`permissoes_perfil`), não código. Somente
quem tem `PERMISSAO_GERENCIAR` (exclusivo do `ADMIN_MASTER`) concede ou revoga. A coluna do master é
sempre integral e não editável; a instalação mantém no máximo um master ativo (índice único parcial) e
recusa rotações que a deixem sem master.
**Consequência.** Não existe autoelevação: ninguém altera o próprio perfil, gerencia par ou quem está
acima, e toda mudança é auditada com antes/depois. Perder acesso tem efeito imediato — a sessão
recarrega o usuário ao abrir a área administrativa. Custo aceito: se o master perder a senha, a
recuperação é operacional (procedimento documentado), não uma tela de "esqueci a senha".

## ADR-014 — Marca e tema são parâmetros, não código

**Decisão.** Nome da loja, razão social, CNPJ, endereço, rodapé do comprovante, logo (PNG em data URI)
e a paleta de cores vivem na tabela `parametros` sob o prefixo `marca.` (cores em `marca.tema.*`).
A folha de estilo é gerada a partir da paleta em tempo de execução; se a leitura falhar, cai no tema
padrão embutido.
**Consequência.** Nenhuma recompilação para trocar a identidade visual, e a UI inteira segue a mesma
paleta. Contraste texto/superfície é conferido na tela (WCAG AA) antes de salvar. Marca exige
`MARCA_GERENCIAR`; cores exigem `TEMA_GERENCIAR` — o master decide quem recebe cada uma.

## ADR-015 — Diagnóstico administrativo calculado, nunca digitado

**Decisão.** A tela "Visão geral" executa checagens reais (versão de Python/PySide6/SQLite, presença do
Argon2id, `PRAGMA integrity_check`, `foreign_keys`, `journal_mode`, `synchronous`, versão do esquema ×
migrações disponíveis, espaço livre, tamanho real da base somando o WAL, contagens e existência de
master ativo) e classifica cada linha em OK / Atenção / Erro.
**Consequência.** A tela responde "esta instalação está saudável?" sem terminal e sem texto fixo; um
problema real aparece em vermelho com o motivo. Restauração de cópia é exclusiva do master, verifica a
cópia antes de sobrescrever e guarda uma cópia do estado anterior ao lado do banco.

## ADR-016 — Interface no vocabulário do AdminLTE, com cor vinda do banco

**Decisão.** A casca (sidebar recolhível, topbar, cabeçalho com trilha, cartões, *small-boxes*,
etiquetas) segue a linguagem do AdminLTE (MIT), reconstruída em PySide6: nenhum arquivo do projeto
original é copiado e os 21 ícones são SVGs próprios. A folha de estilo continua derivada da paleta
salva pela loja; a skin padrão passa a ser a do AdminLTE (azul `#0D6EFD`, sidebar `#343A40`, fundo
`#F4F6F9`), com preset novo `OCEANO`.
**Consequência.** Ganho de legibilidade e densidade sem quebrar a personalização por loja: trocar a
paleta repinta sidebar, cartões e indicadores. Custo aceito: a janela tem altura mínima ~760 px por
causa da densidade de informações do PDV; não há versão "mobile". O CSS do AdminLTE não é carregado
em tempo de execução — se um dia for, a licença MIT exige manter o aviso de copyright.

---

## ADR-017 — Distribuição no Windows: onedir + Inno Setup, dados fora da pasta do programa

**Decisão.** O Windows é o alvo de instalação. Três caminhos convivem: (1) rodar do código com
Python 3.12, (2) `.zip` portátil do PyInstaller, (3) instalador do Inno Setup 6. O PyInstaller roda
em modo **onedir**, com `console=False` no executável principal e um segundo binário com console para
diagnóstico; sem UPX e sem assinatura digital. A base e as cópias ficam no diretório de dados do
usuário (`%LOCALAPPDATA%\BussolaPDV`), nunca em `Program Files`; a desinstalação remove o programa e
preserva os dados por padrão. Quando não há base, o próprio programa abre o assistente de primeiro uso
em vez de exigir `bussola init` no terminal.

**Consequência.** Instalar deixa de exigir Python, e atualizar o programa não toca no banco. Custo
aceito: nenhum binário Windows é produzido no ambiente de desenvolvimento (Linux) — os artefatos saem
do runner `windows-latest` ou de uma máquina Windows, então este repositório versiona a **receita**,
não o `.exe`. Sem certificado de assinatura de código, o SmartScreen alerta no primeiro uso; o guia
assume isso e ensina a conferir o hash em vez de pedir que o usuário ignore o aviso. O caminho `.msi`
(WiX) fica documentado como alternativa não automatizada. Distribuir binário assinado é decisão de
quem publica, não do código.

---

## ADR-018 — Exportação como dado: um `Relatorio`, dois escritores, zero dependência nova

**Decisão.** Tela e arquivo descrevem o mesmo objeto `Relatorio` (`dominio/relatorio.py`): blocos
tabulares com colunas tipadas, indicadores, filtros, avisos e escopo. O `.xlsx` é escrito com a
biblioteca padrão (`zipfile` + XML), e o PDF com `QPdfWriter`/`QTextDocument` do PySide6 que já é
dependência de execução. Nenhuma biblioteca nova entra no caminho de execução. Exportar exige a
permissão que já existia (`EXPORTAR_DADOS`) e grava o evento `DADOS_EXPORTADOS` na trilha
append-only; o botão aparece apenas para quem tem a permissão, mas a autorização é reavaliada no
serviço.

**Alternativas descartadas.** `openpyxl`/`pandas` (duas dependências grandes, mais tempo de
instalação no Windows e mais superfície de CVE) e `reportlab`/`weasyprint` (biblioteca nativa extra
para paginação e fontes). As versões descartadas seriam mais rápidas de implementar, mas o formato
necessário aqui é pequeno e estável: tabelas, números e datas. `openpyxl` e `pypdf` **são** usadas
como dependências de teste, justamente para abrir o arquivo gerado com um leitor de verdade.

**Consequência.** O custo é manter os dois escritores (≈400 linhas) e aceitar o que eles não fazem:
sem fórmulas, gráficos, imagens, células mescladas, PDF/A ou assinatura. Em troca, o programa
continua com duas dependências de execução, o build do Windows fica menor e o arquivo não depende de
versão de biblioteca de terceiro para abrir. Datas e moedas são gravadas como tipos nativos (serial
do Excel e número em reais), não como texto — o que era o requisito prático de quem leva o
fechamento para o contador.

---

## ADR-019 — Tela de consulta desenha o relatório (uma consulta, dois destinos)

**Contexto.** As telas de Clientes, Crediário e Estoque estavam marcadas como não implementadas,
embora a API (`ServicoCrediario.listar`, `RepositorioClientes.listar`, `produtos.saldos`) já
existisse. O caminho óbvio era escrever, em cada tela, uma consulta própria e formatar os números
no widget — e repetir a lógica, mais uma vez, nos relatórios de exportação.

**Decisão.** Cada tela nova monta o `Relatorio` no `ServicoExportacao`
(`relatorio_clientes`, `relatorio_crediario`, `relatorio_estoque`) e **desenha a primeira tabela e os
indicadores** desse objeto; o `BotaoExportar` recebe um `lambda` que chama exatamente o mesmo método.
Formatação de célula vem de `infra.exportacao.formato.celula()` nos dois destinos, então moeda, data e
inteiro aparecem iguais no widget e na planilha.

**Consequências.**

- divergência tela × arquivo deixa de ser possível por construção: não há segundo cálculo para
  esquecer de atualizar;
- o custo é a tela depender do serviço de exportação (camada de aplicação) para ler — o que já era
  verdade para Fechamento e Vendas;
- relatórios com várias tabelas ficam limitados, na tela, à primeira (`tabelas[0]`); as demais
  (resumo por situação, contagem por denominação) só saem no arquivo, e isso está dito no cartão;
- um ajuste de cálculo é feito **uma vez** e aparece nos dois lugares — foi assim que o bug do título
  `PARCIAL` (que sumia do saldo em aberto) foi corrigido nos dois destinos de uma vez.

---

## ADR-020 — Pasta de dados escolhível, ponteiro fora dela e falha sempre visível

**Contexto.** Duas queixas de quem instalou o programa: (1) clicar em **Criar instalação** não fazia
nada; (2) não havia como escolher onde os dados ficam. A causa da primeira não era o botão: o diálogo
só tratava `ErroBussola`, e qualquer outra exceção (permissão de pasta, arquivo travado por
antivírus, base corrompida de uma tentativa anterior) escapava do slot do Qt. O PySide6 imprime isso
no `stderr` — e o executável do Windows roda **sem console**. O erro existia; ninguém podia vê-lo.

**Decisão.**

1. **Toda falha de inicialização é visível.** `ui/primeiro_uso._criar` captura `Exception`, mostra tipo
   e mensagem na própria caixa, grava o traceback em `logs/erros.log`; `ui/entrada.main` instala um
   `sys.excepthook` (`diagnostico.instalar_captura_de_erros`) que faz o mesmo para qualquer exceção não
   tratada. "Nada acontece" deixa de ser um estado possível.
2. **A pasta de dados é escolhida na instalação** e pode ser trocada depois (CLI `bussola dados`,
   Administração → Manutenção).
3. **O ponteiro da escolha mora fora da pasta de dados** (`%APPDATA%\BussolaPDV\instalacao.json`;
   `~/.config/bussola-pdv` no Linux). Se estivesse dentro da pasta de dados, mover os dados perderia o
   ponteiro e a instalação voltaria ao padrão em silêncio.
4. **Precedência fixa e explicável**: `BUSSOLA_DADOS` > pasta escolhida > padrão do sistema, com
   `origem_do_diretorio()` para a tela/CLI dizerem qual das três está valendo.
5. **A pasta é testada antes de abrir o banco.** Escolher uma pasta sem escrita falha com mensagem em
   português, não com `unable to open database file`.

**Alternativas descartadas.** *Guardar a escolha em tabela do próprio banco* — impossível: é preciso
saber onde está o banco para lê-la. *Config em arquivo dentro da pasta de dados* — quebra ao mover a
pasta. *Registro do Windows* — mais uma superfície específica de plataforma e sem ganho. *Mover os
arquivos automaticamente ao trocar a pasta* — decide sobre dados do lojista sem confirmação; a escolha
é registrar + avisar, e a cópia fica em `bussola dados --mover`, com verificação de integridade e sem
apagar a origem.

**Consequência.** O programa deixa de ter um diretório único e implícito: quem dá suporte precisa
rodar `bussola dados` para saber onde a base está (e por quê). Em troca, o dado pode morar na unidade
que o lojista quiser, sobrevive à desinstalação do programa e a instalação deixa de poder falhar em
silêncio.

---

## ADR-021 — Responsividade por faixa de largura, não por tamanho fixo

**Contexto.** A interface nasceu para 1280×820 e isso apareceu no balcão: em monitor de 1024×768 a
página de Produtos pedia 949 px de largura mínima e era cortada; em 800×600 os cartões de indicador se
sobrepunham e os grupos do PDV ficavam por baixo uns dos outros; as tabelas espremiam a coluna de
descrição até o cabeçalho virar "›escriçã". Os números estavam espalhados pelo código: `setFixedWidth`
na sidebar, `setMinimumWidth` em diálogos, `QHBoxLayout` com `addWidget(x, 1)` para quatro cartões.

**Decisão.** Uma única camada, `ui/responsivo.py`, com a régua de largura e as peças que reagem a ela:

* **faixas** — `classe_de_largura()` devolve `compacta` (< 900 px), `media` (< 1180 px) ou `ampla`.
  Nenhuma tela compara pixels por conta própria; todas perguntam a faixa;
* **indicadores** — `GradeDeIndicadores` troca `QHBoxLayout` por `QGridLayout` e reflui 4 → 3 → 2 → 1
  cartão por linha; a altura mínima acompanha as linhas (era a causa da sobreposição);
* **casca** — `CascaResponsiva` (herdado por `JanelaPrincipal` e `JanelaAdmin`) recolhe a sidebar na
  faixa compacta, esconde chip do usuário, trilha e lado direito do rodapé, e reduz a margem de 18 para
  10 px. O botão do menu continua mandando: a escolha manual vale até a janela mudar de faixa;
* **cartões** — o cabeçalho é uma grade: quando o cartão tem menos de 640 px, as ferramentas
  ("Exportar", resumo da consulta) descem para a segunda linha em vez de impor largura mínima à página;
* **tabelas** — `ColunasDaTabela` mede o conteúdo: se cabe, estica a coluna elástica; se não cabe,
  mantém a largura de cada coluna (nunca abaixo de `LARGURA_MINIMA_COLUNA = 84`) e liga a rolagem
  horizontal da própria tabela. O ajuste é adiado 150 ms para não travar o arraste da janela;
* **fileiras de botões** — `FluxoDeAcoes` posiciona os botões em linhas sucessivas: sete ações
  ("Aplicar perfil", "Ativar", "Desativar", "Redefinir senha", "Transferir propriedade…") não cabiam
  lado a lado e saíam pela borda. A geometria é calculada à mão porque guardar `QLayoutItem` em Python
  num `QLayout` próprio derrubava o processo com *segmentation fault* na destruição da janela;
* **diálogos** — `ajustar_dialogo()` limita largura e altura à tela disponível.

O conteúdo ganhou rolagem vertical própria (`QScrollArea` em volta da pilha de páginas) porque em
600 px de altura os formulários do PDV não cabem: sem ela, os grupos se sobrepunham em vez de rolar. A
área administrativa passou a usar `PilhaDePaginas` pelo mesmo motivo de fundo: com `QStackedWidget`
puro, a seção mais larga (856 px) impunha largura mínima às outras oito.

**Alternativas descartadas.** *Uma folha de estilo por resolução* — duplica manutenção e não resolve
mínimos de layout, que são cálculo e não pintura. *`QScrollArea` em cada tela* — o mesmo código dez
vezes e rolagem aninhada. *Layout livre com posições absolutas* — nenhum. *Recolher a sidebar só pelo
botão* — o operador de balcão não deveria precisar descobrir que existe um botão para ver a tela
inteira. *Deixar o `Stretch` espremer colunas* — corta cabeçalho, que é informação.

**Consequência.** A interface foi medida, não só olhada: `ferramentas/verificar_responsivo.py` abre as
duas janelas em 800×600, 1024×768, 1280×800, 1366×768 e 1920×1080 e falha (código 1) se uma página
pedir mais largura do que tem, se uma coluna descer do mínimo legível, se a sidebar recolher sem
motivo ou se a faixa da casca não bater com a largura. Em troca de mais código de layout, o número
1280 deixou de ser uma premissa: em 800×600 nada fica cortado e a janela pode ser reduzida até 720×480.

---

## Pendências que exigem decisão do responsável

| # | Assunto | Situação atual no código | Precisa de |
|---|---|---|---|
| P1 | Emissão fiscal | Não implementada; UI diz "não é documento fiscal" | definição de fornecedor fiscal + homologação |
| P2 | Multi-caixa em rede | Fora de escopo; travas de turno único por caixa | decisão de produto e projeto separado |
| P3 | Encargos de crediário | Não aplicados | regra comercial/jurídica |
| P4 | Limites de desconto | 5% operador / 15% gerente (exemplos do protótipo) | confirmação da política da loja |
| P5 | Estoque negativo | Permitido com autorização de gerente | confirmar se a loja aceita |
| P6 | Retenção/LGPD | Dados mínimos; documento mascarado na UI | prazo de guarda e base legal |
| P7 | Licença/titularidade | GPL-2.0-or-later declarada no `pyproject` | confirmar titular e imagens de referência |
| P8 | Distribuição | Não empacotada nesta entrega | escolha PyInstaller/MSI + assinatura |
| P9 | Backup criptografado | Backup com verificação; sem criptografia | decisão de chave e proteção |
| P11 | Recuperação do Admin Master | Sem tela de recuperação; única saída é procedimento no banco | procedimento aceito pela loja (quem guarda a senha mestra) |
| P10 | Importação da planilha | Não implementada | mapeamento e validação aprovados |
