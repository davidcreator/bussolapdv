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
