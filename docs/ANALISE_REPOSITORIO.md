# Análise técnica do repositório `davidcreator/bussolapdv`

**Data da análise:** 11/11/2026
**Commit analisado:** `fd4e1e4` — "inicio de projeto" (único commit, branch `main`)
**Método:** clone integral, leitura de toda a documentação, inspeção programática das 20 pastas de
trabalho `.xlsx` (openpyxl 3.1.5), leitura dos 5 módulos VBA e dos 20 scripts Python, verificação de
estrutura do Git (configuração, arquivos rastreáveis, governança).

> **Onde está esse material hoje.** Tudo o que este documento analisa foi preservado em
> `prototipo/especificacao/` neste mesmo repositório (`docs/` → `prototipo/especificacao/docs/`,
> `excel/` → `.../excel/`, `py/` → `.../py/`, `uploads/` → `.../uploads/`; os documentos de raiz
> ganharam o sufixo `_ORIGINAL`). Os caminhos citados ao longo do texto são os do repositório de
> origem, antes da consolidação. Ver `prototipo/README.md`.

> Este documento é diagnóstico, não parecer jurídico, fiscal ou contábil. Nenhuma afirmação aqui
> transforma o protótipo em produto homologado.

---

## 1. Resumo executivo

O repositório é uma **especificação forte com implementação protótipo em planilha**. A documentação é
madura, honesta e cobre o domínio melhor do que a média de projetos de PDV open source: define
regras de caixa, crediário, arredondamento, auditoria e limites explícitos (multi-caixa, fiscal,
LGPD). Esse é o maior ativo do projeto e foi integralmente aproveitado na implementação Python.

Do lado do código, o que existe é:

* **20 pastas de trabalho `.xlsx`** (8,4 MB), cada uma com as mesmas 16 abas, geradas em cadeia por
  scripts de uso único — são **artefatos de build versionados**, não uma aplicação;
* **5 módulos VBA** (694 linhas) que gravam vendas sem transação atômica;
* **20 scripts Python** de construção de planilha, sem `requirements.txt`, sem testes e sem
  reprodutibilidade (um deles grava em caminho absoluto `/home/user/...`);
* **zero** teste automatizado, **zero** CI, **zero** `.gitignore`, **zero** empacotamento.

Conclusão: o projeto precisa de uma implementação real. A especificação permite começar pelo domínio
sem adivinhação — e foi o que esta entrega fez.

---

## 2. Inventário medido

| Item | Medida |
|---|---|
| Commits / branches / tags | 1 / 1 / 0 |
| Pastas de trabalho `.xlsx` | 20 (8,4 MB) |
| Abas por pasta de trabalho | 16 (320 abas no total) |
| Fórmulas na maior pasta (`listas_v1`, `auditoria_avancada_v1`) | 27.712 e 28.070 |
| Tabelas estruturadas (`ListObject`) por arquivo | 5 a 15 |
| Módulos VBA | 5 arquivos, 694 linhas, 10 procedimentos |
| Scripts Python (build) | 20 arquivos, 7,6 mil linhas somadas |
| Documentos em `docs/` | 23 `.md` + 23 `.txt` **idênticos** (188 KB + 152 KB) |
| Documentos de governança | README, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, NOTICE, CHANGELOG, LICENSE, PROMPT_MESTRE |
| Imagens de referência em `uploads/` | 3 PNG de ~1900 × 770 px (referências visuais de terceiros) |
| Testes automatizados | **0** |
| Pipeline CI/CD | **0** |
| `requirements.txt` / `pyproject.toml` | **ausentes** |
| `.gitignore` | **ausente** |
| Templates de issue/PR (`.github/`) | **ausentes** (o CHANGELOG afirma que existem) |

---

## 3. O que está bom e deve ser preservado

1. **Regras de negócio explícitas e numericamente definidas.** `docs/REGRAS_NEGOCIO.md` define a
   identidade do caixa (`esperado = fundo + vendas em dinheiro + recebimentos + suprimentos − sangrias
   − estornos`), a proibição de tratar PIX como confirmado e a separação entre valor entregue, aplicado
   e troco. Isso virou código quase literal em `dominio/caixa.py` e `dominio/pagamentos.py`.
2. **Honestidade sobre o estado.** README, CHANGELOG e cada `docs/NN_*.md` dizem o que **não**
   funciona. O projeto não finge ter homologação fiscal, multi-caixa ou segurança.
3. **Critérios de aceite já escritos** (`docs/PLANO_TESTES.md`) — incluindo casos difíceis: troco para
   R$ 100, split dinheiro+PIX, duplo clique/idempotência, falha injetada em cada etapa, aging.
4. **Anti-metas corretas.** "Não usar intervalo fixo", "não tratar igualdade aritmética como
   confirmação bancária", "não apagar histórico", "não aceitar float para dinheiro".
5. **Governança iniciada** (licença proposta GPL-2.0-or-later, SECURITY, CODE_OF_CONDUCT, NOTICE com
   pendências jurídicas declaradas).

---

## 4. Achados técnicos

### 4.1 Documentação

| Achado | Evidência | Consequência |
|---|---|---|
| 23 documentos duplicados em `.md` e `.txt` com conteúdo **byte a byte idêntico** | `cmp` em todos os 23 pares: `IGUAL` | 46 arquivos onde 23 bastariam; risco de editar a cópia errada e divergir a "verdade" |
| `GITHUB_PUBLICACAO.md` afirma "o repositório ainda não foi criado" | repositório público existe e está ativo | checklist desatualizado induz a erro |
| `CHANGELOG.md` declara "Modelos iniciais de issues e pull requests" | não existe `.github/` | histórico de mudanças impreciso |
| Duas famílias de documentação convivem | `docs/ARQUITETURA.md` (visão alvo) × `docs/01..23_*.md` (protótipo Excel) | leitura exige saber qual é a fonte vigente |
| Normas de layout em pontos de célula (larguras 3/12, alturas 32/20/8, congelar em `C7`) | `02_layout_e_operacao.md` | não transponível para Qt; vira "contrato" inútil na aplicação |

**Recomendação:** manter um único `.md` por assunto, marcar o que é "alvo" e o que é "protótipo
histórico", e corrigir o checklist de publicação.

### 4.2 Pastas de trabalho `.xlsx` (protótipo)

* **20 arquivos são 20 estados intermediários do mesmo modelo.** Cada script `build_*.py` carrega um
  snapshot anterior e salva um novo arquivo (`build_audit.py` abre `PDV_Empresa_auditoria_v1.xlsx`,
  `build_lists.py` abre `PDV_Empresa_listas_v1.xlsx`, etc.). Não há um arquivo canônico, nem *make*
  reprodutível, nem indicação de qual é o "atual". Um leitor novo não sabe qual abrir.
* **Volume de fórmulas por pré-alocação de linhas.** `07_PAGAMENTOS` tem 1.000 linhas pré-alocadas;
  `04_VENDAS` 500; `05_ITENS_VENDA` 10.000; `11_ESTOQUE_MOV` 10.000. Isso produz ~28 mil células de
  fórmula por arquivo, todas recalculadas a cada abertura — o oposto de um banco de dados.
* **Fórmulas replicam a regra de negócio em texto.** Cada planilha reimplementa arredondamento,
  saldo e conferência com `SOMASE`/`ÍNDICE`/`CORRESP`, inclusive dentro de faixas fixas
  (`$B$8:$B$507`, `$F$8:$F$10000`). Qualquer mudança de regra exige editar 20 arquivos.
* **Integridade depende de validação de célula.** IDs (`P001`, `T001`) são texto livre, sem chave
  estrangeira; a própria documentação reconhece que a validação "pode ser contornada por colagem".
* **Estoque inicial e movimentos convivem** — a documentação avisa do risco de dupla contagem e
  propõe uma coluna "Qtd Assinada" que **não existe** no arquivo.
* **Gráficos do dashboard não existem**, apesar do nome do módulo: há bases preparadas, sem gráfico.

**Consequência:** a planilha serve como **especificação executável de protótipo**, não como base de
migração. Ela não deve ser importada para uma base de produção sem mapeamento e validação (o prompt
mestre já exige isso).

### 4.3 VBA

* 5 módulos quase idênticos (`ModuloPDV`, `..._vendas`, `..._itens`, `..._pagamentos`, `..._estoque`),
  cada um com 2 procedimentos — são versões concorrentes do mesmo fluxo, não módulos distintos.
* **Não há transação.** A gravação escreve venda → itens → pagamentos → movimentos em sequência;
  falha no meio deixa dados parciais. A documentação instrui o usuário a **não repetir** e restaurar
  backup — ou seja, o próprio protótipo transfere a integridade ao operador.
* `Application.Match` com `On Error GoTo` central; ausência de checagem de linha livre em todos os
  históricos (só `ModuloPDV_pagamentos.bas` verifica capacidade).
* Nenhum módulo foi executado/homologado — declarado explicitamente.

### 4.4 Scripts Python de construção

* 20 scripts, sem funções reutilizáveis (código em nível de módulo, uma linha por célula em vários
  casos), sem `if __name__ == "__main__"`, sem testes.
* `make_pdv.py` salva em `/home/user/PDV_Empresa_v1.0_fase1.xlsx` — caminho absoluto de máquina
  pessoal: **não reproduzível**.
* Não há `requirements.txt` nem versão fixada de openpyxl.
* Nenhum dos scripts valida o resultado (não há asserções); erros silenciosos são possíveis.

### 4.5 Processo, licenciamento e segurança

| Achado | Risco |
|---|---|
| Sem `.gitignore` | bases SQLite, backups, planilhas de operação e segredos entram no Git por acidente |
| Sem CI | nenhuma barreira impede commit quebrado |
| Sem testes | toda regressão é descoberta em produção |
| `uploads/*.png` são capturas de outra aplicação | risco de licença/autoral ao redistribuir (o NOTICE já alerta) |
| Nenhum cabeçalho SPDX nos arquivos | GPL-2.0-or-later declarada no README/LICENSE, mas não nos fontes |
| Senha/PIN em planilha | `01_PARAMETROS` reserva coluna PIN; a documentação proíbe digitar senhas reais — correto, mas não há mecanismo |

---

## 5. Contradições entre documentação e repositório

1. README afirma "não contém ainda uma aplicação de PDV executável" — **verdadeiro**; mas 20 `.xlsx`
   com 28 mil fórmulas dão a impressão contrária a quem abre a pasta `excel/`.
2. `docs/INDICE_MODULOS.md` descreve 16 módulos como plano; `docs/07_padronizacao_visual.md` descreve
   padronização "nas 16 abas", o que pode ser lido como módulos prontos.
3. `docs/GITHUB_PUBLICACAO.md` desatualizado (item 4.1).
4. `docs/03_formulas_e_funcoes.md` aponta um erro do briefing (PROCV com índice 4 devolveria
   Categoria, não Descrição) — a documentação corrige o próprio briefing; bom, mas mostra que as
   fórmulas de referência nunca foram executadas.
5. CHANGELOG x ausência de `.github/` (item 4.1).

---

## 6. Riscos priorizados

| # | Risco | Impacto | Probabilidade | Mitigação nesta entrega |
|---|---|---|---|---|
| R1 | Gravação parcial de venda (sem transação) | Alto (dinheiro e estoque divergentes) | Certa no protótipo | Transação única com `BEGIN IMMEDIATE` + teste de falha injetada |
| R2 | Dupla baixa de estoque por item repetido | Alto | Alta | Carrinho consolida por produto; movimento único por venda |
| R3 | PIX/cartão tratado como recebido | Alto (caixa fictício) | Alta | `PENDENTE` por padrão, confirmação manual registrada, relatório de pendências |
| R4 | Desconto sem autorização real | Médio/Alto | Alta | Perfis + autorização autenticada (Argon2id) e evento de auditoria |
| R5 | Perda de histórico por edição/exclusão | Alto | Média | Trilha append-only com triggers `RAISE(ABORT)` + cadeia SHA-256 |
| R6 | Erro de centavo por arredondamento | Médio | Média | Dinheiro inteiro em centavos, política única, testes parametrizados |
| R7 | Base corrompida/backup inválido | Alto | Média | Backup pela API do SQLite + verificação + restauração testada |
| R8 | Multi-caixa prometido sem base | Alto (expectativa) | Média | Documentado como fora de escopo; travas de turno único por caixa no banco |
| R9 | Fiscal tratado como resolvido | Alto (legal) | Baixa | Nenhuma emissão fiscal; rótulo "não é documento fiscal" na UI |
| R10 | Licença de ativos de terceiros | Médio (jurídico) | Média | Imagens não incorporadas ao código; pendência registrada |

---

## 7. Rastreabilidade: da especificação ao código Python

| Fonte no repositório | O que foi implementado | Onde |
|---|---|---|
| `REGRAS_NEGOCIO.md` — dinheiro/pagamento | Centavos inteiros, split ≤ 3 formas, troco só em dinheiro, `soma(aplicado)=total` | `dominio/dinheiro.py`, `dominio/pagamentos.py` |
| `ARQUITETURA.md` — camadas e transações | Domain / application / infra / UI separados; validação refeita dentro da transação | `dominio/`, `aplicacao/pdv.py` |
| `REGRAS_NEGOCIO.md` — caixa | Fórmula do esperado, contagem por denominação, classificação de diferença | `dominio/caixa.py` |
| `16_crediario.md` | Um título por parcela, recebimentos parciais, aging 1–30/31–60/61–90/>90 | `dominio/crediario.py` |
| `18_movimentos_estoque.md` / `19_entradas.md` | Saldo por movimentos assinados, rateio de frete com soma exata | `dominio/estoque.py` |
| `23_auditoria_avancada.md` | Eventos com ator, autorizador, motivo, antes/depois, correlação | `dominio/auditoria.py` |
| `PLANO_TESTES.md` | Casos de aceite convertidos em testes automatizados | `tests/` |
| `06/07_*visual*.md` | Grafite + turquesa, entradas âmbar, calculadas cinza | `ui/tema.py` |
| `PROMPT_MESTRE` — sequência | Etapas 1–4 iniciadas (esqueleto, migrações, auth, cadastros, estoque, PDV) | ver `docs/PLANO_IMPLEMENTACAO.md` |

---

## 8. Decisões que dependem do responsável (não decididas por mim)

1. **Fiscal:** emitir ou não documento fiscal; qual integração e quando.
2. **Multicaixa:** permanece 1 estação? Se houver 2+ estações, é preciso serviço local + banco
   servidor (projeto separado, com testes de concorrência).
3. **Política de encargos do crediário:** juros, multa, carência, renegociação — sem aprovação, o
   sistema **não** aplica encargo algum.
4. **Desconto:** limites por perfil (hoje 5% operador / 15% gerente, espelhando `01_PARAMETROS`,
   que são exemplos).
5. **Estoque negativo:** permitido com autorização por padrão; confirmar se a loja aceita.
6. **Retenção/privacidade:** prazo de guarda de dados pessoais e de auditoria (LGPD).
7. **Licença e titularidade:** confirmar GPL-2.0-or-later e autoria das imagens de referência.
8. **Empacotamento:** PyInstaller ou instalador MSI; assinatura de código.

---

## 9. Recomendações (ordem de execução)

1. ~~**Aposentar os 20 `.xlsx` do controle de versão** e mover para `prototipo/` com um README dizendo
   qual é o último e que não são fonte de verdade.~~ **Feito:** `prototipo/especificacao/` +
   `prototipo/README.md`, com `.gitignore` abrindo exceção só para eles.
2. ~~**Remover os 23 `.txt` duplicados** de `docs/`.~~ **Feito na prática:** a documentação vigente é
   `docs/` (só `.md`); as cópias `.txt` ficaram congeladas dentro de `prototipo/especificacao/docs/`
   como histórico, sem papel de verdade.
3. **Manter um único `docs/`** com: visão, regras, arquitetura, operação, testes, decisões (ADRs).
4. **CI obrigatório** (`ruff`, `mypy`, `pytest`) — criado nesta entrega.
5. **Transformar cada item do `PLANO_TESTES.md` em teste automatizado** — feito para os itens
   funcionais; itens de UI/DPI ainda exigem estação real.
6. **Definir as 8 decisões pendentes** antes de qualquer uso com dados reais.
7. **Homologação em máquina representativa offline** com operador real, antes de release.

---

## 10. Veredito

| Dimensão | Nota | Comentário |
|---|---|---|
| Clareza de requisitos | Forte | documentação acima da média |
| Arquitetura de software | Inexistente no código | planilha + VBA não escalam |
| Integridade de dados | Fraca no protótipo | sem transação, sem FK, sem imutabilidade |
| Testes | Inexistente | plano escrito, nada executado |
| Segurança | Inexistente no protótipo | PIN em planilha, sem autorização real |
| Potencial | Alto | o domínio está descrito o suficiente para implementar |

O repositório é um **excelente briefing** e um **protótipo frágil**. A implementação Python desta
entrega converte o briefing em software executável, com testes que comprovam o que funciona e
documentação que diz o que falta — sem alegar homologação.
