# Changelog

Formato inspirado em Keep a Changelog; versionamento semântico a partir de releases executáveis.

## [0.15.1] — 2026-11-11 — CI verde: o que o ambiente do CI mostrou e a máquina de quem escreve escondia

O CI ficou vermelho depois da v0.15.0 e a investigação achou **três defeitos reais** — nenhum deles
"coisa de CI". Todos apareciam só num ambiente diferente do de quem desenvolve (Python 3.12, sem
Pillow, suíte inteira num processo só), que é justamente o ambiente que o CI reproduz de propósito.

### Corrigido — servidor deixava threads vivas e derrubava o processo

- **`ServidorAPI.parar()` agora fecha as conexões abertas.** Um cliente que conecta e não manda
  pedido — exatamente o que o botão **Verificar servidor** faz, para ler o certificado — deixava a
  thread do manipulador presa no `recv`, sobrevivendo ao desligamento. No fim do interpretador, a
  thread daemon tentava escrever um traceback de `BrokenPipeError` e o processo abortava com
  `_enter_buffered_busy`. O sintoma no CI era um *segmentation fault* no meio de um teste de layout
  que não tinha relação nenhuma com a rede.
- **Timeout de leitura no manipulador (30 s)**: conexão ociosa não fica mais pendurada para sempre.
- **Cliente que desiste não vira traceback**: `handle_error` silencia `ConnectionError`,
  `TimeoutError`, `ssl.SSLError` e `OSError` — rotina numa API, não defeito do servidor.
- **`inspecionar_certificado` fecha um descritor só para cada conexão**: antes o socket cru e o
  embrulhado em TLS eram fechados os dois (o mesmo descritor duas vezes).
- Testes novos em `tests/test_api.py` (`TestDesligamento`) provam que **nenhuma thread sobrevive ao
  `parar()`** e que cliente que desiste **não imprime nada** no stderr.

### Corrigido — manual sem Pillow saía sem medida de imagem

- O gerador embutia as capturas com `width`/`height` **somente quando o Pillow estava instalado**.
  Sem ele — o caso do CI, que instala só as dependências declaradas — as figuras saíam sem medida e
  o navegador não reservava o espaço. **As medidas agora saem do próprio cabeçalho PNG** (`struct`,
  biblioteca padrão), com ou sem Pillow; o Pillow continua sendo só o que encolhe o arquivo.
- Pillow virou extra opcional declarado (`.[documentacao]`), em vez de dependência invisível.
- Testes novos (`TestSemPillow`) cobrem o caminho do CI, inclusive gerando o manual inteiro sem
  Pillow e conferindo que **toda** captura tem medida.

### Corrigido — instabilidade de Qt na suíte

- **Uma `QApplication` por sessão de testes**: cada arquivo criava a sua e a aplicação era destruída
  ao fim do arquivo (no PySide6 o objeto Qt morre junto com a última referência Python). Criar e
  destruir `QApplication` no mesmo processo é caminho conhecido de crash.
- **Timer do mentor virou filho do painel**: o `QTimer.singleShot` estático deixava um disparo na
  fila com referência ao método de um widget que podia ser destruído antes — callback em objeto
  liberado é segfault, não exceção. O timer com pai morre junto com o painel.

### Verificação

- CI reproduzido localmente passo a passo: Python **3.12** num ambiente limpo, `pip install -e
  ".[dev]"`, `ruff check src tests`, `mypy`, `pytest --cov --junitxml` e a verificação de migrações
  (`demo`/`info`/`backup`) — tudo verde.
- Suíte: **1061 testes** (as 1055 da v0.15.0 + 6 novos). Também verde em Python 3.13.

## [0.15.0] — 2026-11-11 — pré-alfa: o caixa inteiro funcionando pela rede

A v0.14.0 entregou o servidor e deixou uma frase explícita: *a tela do balcão ainda abre a base
direto*. Esta rodada fecha essa frase — e fecha a janela inteira, não uma tela enxuta de PDV. O
caixa agora é **cliente**: vende, recebe, crediário, devolução, estoque, relatórios, cadastros e
administração rodam no servidor, com a mesma janela e as mesmas telas. A decisão está no
**ADR-036**.

### Adicionado — a janela completa em modo cliente (ADR-036)

- **Um executor, não sessenta endpoints**: `POST /v1/executar {servico, metodo, argumentos}` chama
  o **mesmo serviço de aplicação** do servidor. A lista de serviços é fechada e só expõe métodos
  públicos — não é SQL por HTTP.
- **A assinatura do método é o contrato**: o proxy do terminal lê a assinatura e as anotações de
  tipo da classe de serviço, liga argumentos posicionais a nomes e recebe o resultado já
  convertido (`Dinheiro.centavos`, `Quantidade.milesimos`, `Percentual.bp` como inteiros na
  fronteira; `Enum` pelo nome). Sem dois vocabulários para manter em sincronia.
- **Identidade é do servidor**: argumentos de ator enviados pelo terminal são descartados e
  substituídos pelo usuário da sessão; vender em nome de outro é recusado. Autorização de exceção
  exige a senha do gerente **conferida no servidor** e vira credencial de 5 minutos.
- **Leituras de tela** ganharam serviço próprio e fechado (`Consultas`): caixas, turno, movimentos,
  parâmetros, produtos, saldos, clientes, vendas, entradas, auditoria e usuários.
- **`ContextoRemoto`**: as telas continuam escritas como antes (`ctx.parametros.obter_int(...)`) e
  recebem `servicos_de(contexto)` — local ou proxy, a tela não sabe a diferença.
- **27 arquivos de `ui/` migrados** para a fábrica de serviços, sem quebra de comportamento no modo
  local (a suíte inteira continua verde).

### Adicionado — configuração no primeiro uso, com a digital fixada

- **Tela "Este caixa usa um servidor…"** na tela de login (só aparece em máquina ainda local): pede
  endereço, token e nome do caixa, mostra a **impressão digital SHA-256** do certificado do
  servidor e exige confirmação.
- **Fixing por TOFU**: ao confiar, o certificado vai para `servidor-do-caixa.crt` na pasta de dados
  e passa a ser a **única raiz aceita**; servidor com digital diferente é recusado — inclusive por
  quem apagar o `.crt` para "resolver o problema" (ADR-036, item 5).
- **A abertura decide pelo computador**: existe `terminal.json` na pasta de dados? A máquina é
  terminal e abre sem base local, sem backup local e com login por sessão. Sem o arquivo, tudo
  funciona como sempre.
- **`bussola terminal`** (novo comando): `status`, `configurar`, `testar`, `local` e
  `pendencias` — para instalar cinco caixas iguais e para o suporte conferir, da estação, a que
  servidor ela está ligada.
- **`bussola ui --local`**: ignora a configuração de rede e abre a base local (útil para quem
  precisa olhar a base antiga da máquina).

### Adicionado — a rede caiu no meio da venda: fila offline

- **A venda não se perde**: `ServicoPDVRemoto.finalizar_venda` guarda a solicitação em
  `vendas-pendentes.db` (SQLite na pasta do caixa) e devolve `VENDA_NA_FILA`.
- **A tela limpa o carrinho** ao guardar — sem isso o operador tentaria de novo e venderia duas
  vezes — e avisa onde a venda está; a janela ganha a entrada **Vendas pendentes**.
- **Tela de pendências**: lista o que espera envio, o que foi recusado e por quê; reenviar exige
  que seja **o operador que fez a venda**; descartar pede confirmação e nunca acontece sozinho.
- **Reenvio idempotente**: usa a mesma `chave_idempotencia`, então reenviar duas vezes não duplica
  a venda (`ResultadoVenda.ja_existia`).
- **Recusa de negócio não apaga a venda**: estoque, limite ou turno fechado viram pendência com o
  motivo na tela, para a loja decidir.
- **Sessão vencida não é recusa**: servidor reiniciado derruba tokens; a venda continua pendente
  até alguém logar e reenviar, em vez de ser marcada como recusada por um detalhe técnico.

### Corrigido

- **`DELETE /v1/sessao` respondia 501**: `BaseHTTPRequestHandler` devolve "não implementado" para
  método sem `do_*`; agora existe `do_DELETE` e o terminal consegue encerrar a sessão.
- **Terminal mandava `self` ao servidor** (422 `precisa de: self.`): `inspect.signature` de método
  de classe inclui `self`; contrato ganhou `assinatura_remota`, usada pelo executor e pelo proxy.
- **Data de negócio e esquema** agora vêm do servidor na sessão — o relógio do balcão não decide a
  data comercial de um evento gravado no servidor.
- **Auditoria remota chegava como `dict`** e a tela quebrava ao ler `evento.sequencia`: as
  consultas passaram a declarar o tipo de retorno real.
- **`ErroDeComunicacao` é `ErroBussola`**: rede caída aparece na tela como mensagem, não como
  traceback.

### Testes

- **`tests/test_modo_remoto.py` (30)** — venda pelo terminal, identidade, erro de negócio
  atravessando a rede, sessão, certificado de outro servidor recusado.
- **`tests/test_fila_offline.py` (5)** — enfileirar, reenviar, recusa de negócio e descarte.
- **`tests/test_ui_modo_terminal.py` (10)** — primeiro uso fixando a digital, janela remota com
  todos os módulos, tela de pendências reenviando de verdade e login que só oferece rede quando é
  local.
- Suíte: **1053 testes verdes** (baseline anterior: 1010), `ruff` e `mypy` limpos em 119 arquivos.

## [0.14.0] — 2026-11-11 — pré-alfa: encargos cobrados, nuvem de verdade e servidor multi-caixa

A v0.13.0 deixou três frentes "documentadas e preparadas". Esta rodada fecha as três — em código,
com teste — menos a parte que o responsável mandou deixar para depois (a tela do caixa remoto) e a
que está fora de escopo (emissão fiscal). As decisões estão nos **ADR-033**, **ADR-034** e
**ADR-035**.

### Adicionado — encargo de crediário cobrado como receita separada (ADR-033)

- **Calculadora vira cobrança**: `ServicoCrediario.receber(..., cobrar_encargos=True)` calcula multa,
  juros e dias de atraso e grava em `recebimentos`; o **título continua com o valor original**.
- **Receita identificada**: o dinheiro do encargo entra no caixa como movimento próprio
  `RECEBIMENTO_ENCARGOS`, e o resumo do turno passa a separar `recebimentos` de `encargos_centavos`.
- **Nasce desligado**: `encargos.cobrar = 0` de fábrica; ligar é decisão da loja (Parâmetros →
  Encargos), com auditoria da mudança.
- **Perdoar exige autorizador e motivo**: permissão nova `TITULO_ENCARGO_DISPENSAR` (gerente ou
  admin), `motivo_dispensa` obrigatório, valor perdoado na auditoria.
- **Migração 0005** (tabela `recebimentos` com multa, juros, dias, dispensados + novo tipo de
  movimento de caixa via rebuild, porque o `CHECK` de `movimentos_caixa.tipo` é fechado).
- **Tela**: caixa de recebimento mostra multa, juros, dias e total; o botão de dispensar só aparece
  para quem tem a permissão.
- **Parâmetros**: `encargos.cobrar`, `encargos.multa_bp`, `encargos.juros_mes_bp`,
  `encargos.carencia_dias`.

### Adicionado — nuvem AWS S3 e Azure Blob em biblioteca padrão (ADR-034)

- **`infra/nuvem/assinatura.py`**: AWS Signature V4 e Azure Shared Key escritas à mão
  (`hmac` + `hashlib`), conferidas byte a byte contra os exemplos oficiais publicados.
- **`ArmazenamentoS3`** e **`ArmazenamentoAzureBlob`** com `enviar`, `baixar`, `listar`, `remover`
  (e `existe` no S3); `criar_armazenamento(config)` escolhe o provedor.
- **`bussola backup --nuvem aws|azure`**: faz a cópia local, **verifica o `sha256`** e só então envia;
  falha de nuvem devolve **código 2** com a variável que falta, sem invalidar a cópia local.
- **Credencial só em ambiente**: `BUSSOLA_AWS_*` e `BUSSOLA_AZURE_*`; sem elas o cliente não nasce e
  a mensagem diz qual falta. Nenhum SDK, nenhuma dependência nova.
- **Teste sem conta de nuvem**: servidor HTTP local que exige assinatura e devolve os bytes enviados,
  provando o caminho inteiro (ida e volta, listagem, remoção, erro de chave).

### Adicionado — servidor de rede utilizável (ADR-035)

- **Rotas de escrita**: `POST /v1/vendas`, `POST /v1/turnos`, `POST /v1/turnos/{id}/fechar`,
  `POST /v1/crediario/{id}/receber` (com encargo), `POST /v1/entradas`, `POST /v1/devolucoes`,
  `POST /v1/vendas/{id}/cancelar`, mais `GET /v1/turnos` — todas chamando os mesmos serviços da tela.
- **TLS obrigatório fora do loopback**: `bussola api --host 0.0.0.0` sem `--tls` **falha na subida**;
  com `--tls` o servidor sobe em HTTPS.
- **Certificado gerado pelo programa** (`infra/rede/certificado.py`): RSA 2048 + X.509 v3 com SAN,
  em Python puro — sem `openssl` e sem `cryptography`. Gerado uma vez em `<dados>/tls` (chave 0600) e
  reaproveitado; a impressão digital SHA-256 aparece na subida.
- **Identidade de terminal**: cabeçalho `X-Bussola-Terminal` (padrão `--terminal CAIXA-01`) gravado
  em `vendas.terminal_id` e `turnos.terminal_id` (migração 0006).
- **Log de acesso JSONL** (`logs/api-AAAA-MM-DD.jsonl`): quando, terminal, IP, método, rota, status e
  latência — é o que permite reconstruir disputa entre caixas.
- **Concorrência testada**: dois terminais vendendo o último item ao mesmo tempo — uma venda passa, a
  outra é recusada, estoque termina em zero.

### Documentação

- `docs/DECISOES.md`: **ADR-033** (encargo como receita separada), **ADR-034** (nuvem em stdlib),
  **ADR-035** (TLS gerado + terminal identificado); pendências P2, P3 e P14 atualizadas e P16 criada
  (instalar o `.crt` nas máquinas).
- `docs/ENCARGOS.md`, `docs/NUVEM.md`, `docs/REDE.md`, `docs/API.md` reescritos para o estado real.
- Manual do usuário: capítulo Crediário ganhou **Juros e multa de atraso** (ligar, cobrar, perdoar,
  limite legal), Backup ganhou **Guardar a cópia fora da loja (nuvem)**, Problemas ganhou servidor de
  rede e nuvem, e a lista "em construção" passou a dizer o que já **funciona** e o que ainda não tem
  tela.

### Continua fora ou pendente

- **Emissão fiscal**: fora de escopo (ADR-029); roteiro em `docs/FISCAL.md`.
- **Tela do caixa remoto**: próxima fase, por decisão do responsável — o servidor está pronto e o
  programa continua abrindo a base direto.
- Sem multipart upload, sem retry automático na nuvem e sem paginação na listagem (limites em
  `docs/NUVEM.md`).

## [0.13.0] — 2026-11-11 — pré-alfa: devolução tipada, API local e os caminhos de fiscal, rede e nuvem

A v0.12.0 fechou as lacunas de cadastro. Esta rodada atende a um pedido de fôlego maior:
**cancelar, estornar e devolver com tipo e prazo** (prioridade), e, em volta disso, deixar
**documentado e preparado** o que ainda não vai ser construído — homologação fiscal, vários caixas
em rede, calculadora de encargos, nuvem AWS/Azure e uma API para serviços web. Isso reabre parte do
escopo do ADR-029; a separação entre "funciona" e "está preparado" está no **ADR-032**.

### Adicionado — devolução e estorno com tipo, prazo e destino (ADR-031)

- **Tela Vendas → Devolver / estornar itens**: devolve item a item, com a coluna "a devolver" editável
  e as colunas "vendido" e "já devolvido" ao lado; mostra o prazo do tipo escolhido em texto.
- **Quatro tipos de devolução**: arrependimento (7 dias, CDC art. 49), defeito (90 dias, CDC art. 26),
  garantia (prazo do produto, que **só aumenta** o legal) e erro de operação (sem prazo).
- **Fora do prazo continua possível, mas exige segundo usuário** com `VENDA_DEVOLVER`; fica
  registrado `fora_do_prazo` na devolução e na auditoria.
- **Três destinos do valor**: dinheiro (caixa aberto **e** autorizador — o dinheiro sai da gaveta),
  crédito que abate as parcelas em aberto do cliente como recebimento na forma `VALE`, e troca (sem
  movimento financeiro).
- **Documento próprio** (`devolucoes` + `devolucao_itens`) com triggers que recusam `UPDATE`/`DELETE`:
  a venda original continua `CONCLUIDA` com o que foi cobrado.
- **Estoque** volta por movimento `ESTORNO`, com o valor unitário **com desconto do item** (não o preço
  atual da tabela).
- **Garantia por produto**: nova coluna `produtos.garantia_dias` (0–3650), no cadastro pela tela.
- **`ServicoDevolucao`**: `registrar`, `itens_devolviveis`, `avaliar`, `listar`; auditoria
  `DEVOLUCAO_REGISTRADA`.
- **Parâmetros novos**: `devolucao.prazo_arrependimento_dias`, `devolucao.prazo_defeito_dias`,
  `devolucao.estoque_automatico`.

### Adicionado — API HTTP local (docs/API.md)

- `bussola api --banco … --token … [--host 127.0.0.1] [--porta 8765]`, usando **só a biblioteca
  padrão** (`http.server`): nenhuma dependência nova na instalação do Windows.
- Rotas de leitura: `/v1/saude`, `/v1/produtos`, `/v1/estoque`, `/v1/vendas`, `/v1/vendas/{id}`,
  `/v1/crediario`, `/v1/devolucoes`, `/v1/devolucoes/{id}`,
  `/v1/relatorios/{estoque,clientes,crediario,entradas,auditoria}`.
- Rotas de escrita: `POST /v1/devolucoes` e `POST /v1/vendas/{id}/cancelar`.
- **Duas camadas de autenticação**: token do aplicativo em toda rota + `login`/`senha` (e
  `autorizador` quando a regra pede) em toda escrita; nunca sai stack trace na resposta.
- **Contexto por thread**: conexão SQLite não atravessa thread — cada requisição atendida abre a sua.

### Adicionado — estruturas preparadas, com recusa explícita (ADR-032)

- **Fiscal** (`aplicacao/fiscal.py` + `docs/FISCAL.md`): contrato `EmissorFiscal` (`emitir`,
  `cancelar`, `consultar`), `DocumentoFiscal`, `SituacaoFiscal`, configuração lida de parâmetros e
  `EmissorFiscalDesativado`, que **recusa com a lista de pendências**. Roteiro de homologação com 9
  etapas, requisitos (A1, CSC, IE, autorizador, XML por 5 anos) e ordem de grandeza de 4–8 semanas.
- **Rede multi-caixa** (`docs/REDE.md`): arquitetura **servidor central + terminais** (por que
  "SQLite em pasta de rede" corrompe), o que já existe (API), o que falta em ordem (modo servidor com
  TLS, rotas de escrita restantes, `terminal_id`, cliente remoto, teste de concorrência) e a
  alternativa de réplica descartada por ora.
- **Nuvem** (`infra/nuvem/` + `docs/NUVEM.md`): contrato `ArmazenamentoNuvem`
  (`enviar/baixar/listar/remover`), `ConfiguracaoNuvem`, esqueletos `ArmazenamentoS3` e
  `ArmazenamentoAzureBlob` que falham com mensagem, dublê em memória usado nos testes, requisitos,
  política IAM mínima e passos de AWS e Azure.
- **Encargos** (`dominio/encargos.py` + `docs/ENCARGOS.md`): calculadora pura de multa (2%) e juros de
  mora (1% a.m. proporcionais aos dias), com carência e memória de cálculo; **não é aplicada em título
  nenhum** — falta a decisão comercial (P3).

### Corrigido

- Juros por dia calculados com divisão antecipada perdiam centavos (1% ao mês em 30 dias dava R$ 0,90
  em R$ 100,00); agora a divisão é feita uma vez, no fim.

### Mudado

- **Manual**: nova seção *Devolver e estornar* (diferença para cancelamento, passo a passo, prazos e o
  que fica registrado); capítulo 1 ganhou **"Em construção (documentado, ainda sem tela)"** e a seção
  *o que já tem botão e o que ainda não tem* passou a citar encargos e fiscal entre as pendências.
- **README**: devolução, API local e a lista de **pontos de construção** (fiscal, rede, nuvem,
  encargos) com ponteiro para cada documento.
- **DECISOES**: ADR-031 (devolução é documento próprio) e ADR-032 (o que entra agora e o que fica como
  ponto de construção); pendências P2, P3 e P10 atualizadas e P13/P14/P15 abertas.
- **PLANO_IMPLEMENTACAO**: devolução marcada como feita; API entra como próximo incremento.

### Verificação

- `tests/test_devolucao.py` (novo, 20 testes): domínio (total com fração, prazos, garantia que
  aumenta, erro sem prazo), serviço (estoque, dinheiro com autorizador, crédito que abate parcela,
  quantidade acima do vendido, venda cancelada, venda intacta, imutabilidade no banco) e tela
  (devolução pelo diálogo, prazo na tela, erro sem item, botão só para quem tem permissão).
- `tests/test_api.py` (novo, 14 testes): servidor real em porta efêmera, token, credenciais,
  devolução pela API, tipo inválido com lista de aceitos, cancelamento sem autorizador.
- `tests/test_encargos.py` (novo, 9 testes) e `tests/test_nuvem_fiscal.py` (novo, 12 testes).
- Suíte **938 testes / 0 falhas**; ruff e mypy limpos; manual regerado (22 capítulos, 55 seções).

## [0.12.0] — 2026-11-11 — pré-alfa: cadastro, entrada de mercadoria, ajuste e baixa de parcela pela tela

A v0.11.0 fechou o manual apontando quatro buracos: criar produto, criar cliente, lançar estoque
inicial/entrada/ajuste e dar baixa em parcela do crediário “dependiam do serviço técnico”. Esta versão
fecha os quatro. O bazar passa a colocar o catálogo, o cliente e o estoque dentro do programa sem
chamar ninguém — que é o que o escopo do ADR-029 exige.

### Adicionado — escrita pela tela (ADR-030)

- **Novo/alterar produto** (Produtos): código, código de barras, descrição, categoria, unidade, custo,
  preço, estoque mínimo, ponto de pedido, fornecedor e ativo/inativo. Alteração grava
  `PRODUTO_ALTERADO` com antes e depois (preço, custo, mínimo, ponto de pedido, ativo).
- **Novo/alterar cliente** (Clientes): nome, documento, limite de crediário, observações e ativo.
  Documento com dígito conferido e recusa de documento já usado por outro cliente; alteração grava
  `CLIENTE_ALTERADO`.
- **Entrada de mercadoria** (Entradas e Estoque): itens em tabela, custo unitário, frete **rateado**
  por valor ou quantidade, atualização de custo e saldo na mesma transação. A chave
  fornecedor + documento não se repete.
- **Ajuste de saldo** (Estoque): quantidade positiva (acrescenta) ou **negativa** (baixa), motivo
  obrigatório e senha de um **segundo** usuário com permissão de ajuste. É o caminho do estoque
  inicial e da correção de contagem.
- **Receber parcela** (Crediário): total ou parcial, com forma de pagamento e referência; exige turno
  de caixa aberto (o dinheiro entra no turno) e recusa “a prazo” como forma de recebimento.
- **Página Entradas** deixou de ser placeholder: histórico de notas (data, fornecedor, documento,
  itens, quantidade, frete), três indicadores, botão **Nova entrada** e exportação em **Excel/PDF** mais
  impressão. Novo relatório `relatorio_entradas` na camada de exportação.
- **Serviços novos**: `ServicoClientes` (`criar_cliente`, `alterar_cliente`) e
  `ServicoEstoque.alterar_produto`.

### Corrigido

- **Ajuste de estoque não aceitava quantidade negativa**: `Quantidade.de_unidades` recusa negativo, e
  a validação acontecia antes de o sinal ser tratado — dar baixa por contagem era impossível. O sinal
  agora é lido do texto (`-2`, `+2`) antes da conversão, e o movimento guarda a quantidade assinada.
- **Fixture de teste inconsistente**: o produto de exemplo passava `estoque_minimo=2` (milésimos) onde
  se queria “2 unidades”; com o cadastro pela tela isso aparecia como `0,002` e impedia salvar o
  produto. Virou `2000`.
- **Módulo Entradas**: estava listado no menu sem página; agora tem página na posição certa da pilha.

### Mudado

- **Manual do usuário**: a seção *o que já tem botão e o que ainda não tem* passou a ter dois lados —
  sete operações “pela tela” (com passo a passo de cadastro, ajuste, entrada e recebimento) e cinco que
  continuam sem botão (cancelar entrada lançada, importar planilha, juros de atraso, multi-caixa, nota
  fiscal). O capítulo *Da caderneta para o sistema* agora ensina a lançar o **estoque inicial** pela
  tela em vez de mandar chamar o serviço técnico. Captura nova da página Entradas (26 imagens).
- **README**: telas de operação incluem Entradas; a lista de limites troca “telas são de consulta” pelo
  que de fato continua sem botão.
- **DECISOES**: ADR-030 (a tela não duplica regra; permissão por ação; segundo usuário no ajuste;
  antes/depois na auditoria).
- **PLANO_IMPLEMENTACAO**: item “operação nas telas novas” marcado como feito.

### Verificação

- `tests/test_cadastros_ui.py` (novo, 23 testes): serviço de clientes (permissão, documento repetido,
  auditoria do limite), `alterar_produto` (preço, campo inválido), entrada (saldo sobe, documento
  repetido recusado), ajuste negativo, ajuste sem motivo e sem segundo autorizador; e, pela tela,
  cadastro de produto, erro que não fecha o diálogo, alteração de preço, cadastro de cliente, documento
  inválido, entrada com item, entrada sem item, ajuste com e sem senha correta, recebimento com turno
  aberto e recusa sem turno, botões que existem só com permissão, e a tela Entradas com histórico.
- Testes de placeholder ajustados: `Entradas` saiu da lista; quem continua marcado é **Parâmetros**
  (`test_ui_smoke`, `test_ui_adminlte`, `test_ui_telas_modulos`).
- `tests/test_manual.py`: o teste da seção passou a exigir os dois lados (as quatro operações “pela
  tela”, as cinco pendências reais) e falha se o manual voltar a dizer que o módulo Entradas não existe.
- Suíte **883 testes / 0 falhas / 0 skipped**; ruff e mypy limpos (98 arquivos); `make responsivo`
  verde; capturas e manual regerados.

## [Não lançado]

### Mudado — manual do usuário conta a história do bazar e o que a tela ainda não faz

O manual foi escrito antes de o escopo ficar claro. Agora ele começa pela origem real do programa e
diz, sem rodeio, o que já tem botão e o que ainda não tem — as duas coisas que um voluntário precisa
saber antes do primeiro dia.

- **Nova seção "O que já tem botão e o que ainda não tem"** (capítulo 1), montada a partir do próprio
  código desta versão: vender/caixa/cancelar e consultar/exportar/imprimir **pela tela**; criar produto,
  criar cliente, lançar estoque inicial/entrada/ajuste e dar baixa em parcela do crediário **ainda não**
  — dependem do serviço técnico. Com o aviso de que operar o dia está pronto, mas colocar o catálogo
  dentro do programa precisa ser combinado antes.
- **Nova seção "Da caderneta para o sistema"**: tabela antes/depois (somar o dia à mão, caderno do
  crediário, contagem de prateleira, papel solto da sangria, "quem deu esse desconto?") e um roteiro de
  virada em quatro passos, incluindo rodar os dois em paralelo por alguns dias.
- **Aviso honesto sobre as dívidas antigas**: o programa cria título a partir de venda a prazo e não
  importa a caderneta; trazer os saldos em aberto é decisão de vocês, com o critério anotado.
- **Capítulo 1 reancorado no bazar da ONG** ("Ele nasceu para o bazar de uma ONG...") e glossário com
  *bazar*, *caderneta*, *coordenação* e *prestação de contas*.
- **Correções de texto onde o manual prometia tela que não existe**: a seção *Entrada de fornecedor*
  agora diz que o módulo Entradas está no menu mas a página não foi implementada; Produtos, Clientes,
  Crediário e Estoque recebem a marca de "consulta/exporta/imprime"; o item "Cadastra produtos e
  clientes" da lista de capacidades virou "guarda o catálogo... e o cadastro ainda não tem botão".
- **README**: o limite correspondente agora inclui criar produto e cita o módulo *Entradas* sem página.

### Verificação — manual e escopo

- `tests/test_manual.py` ganhou o teste `test_manual_diz_o_que_a_tela_ainda_nao_faz`, que falha se a
  seção `nao-da-pela-tela` desaparecer, se as quatro telas deixarem de apontar para ela ou se o texto
  voltar a prometer cadastro pela tela.
- Suíte **860 testes / 0 falhas / 0 skipped**; ruff e mypy limpos; manual regerado e conferido no
  navegador (1440 px: tabela, avisos e links internos; nenhum erro de console).

### Mudado — escopo fechado: bazar de ONG, controle interno, sem emissão fiscal (ADR-029)

O responsável delimitou o uso: a fase de operação é o **bazar de uma ONG**, onde nota fiscal não é
necessária — o objetivo é **controle interno**, sair das anotações em caderneta. Com isso, a emissão
fiscal deixa de ser "pendência que um dia será feita" e passa a ser **fora de escopo**; o que o bazar
precisa (venda, caixa, estoque, crediário, fechamento, relatórios em Excel/PDF, comprovante interno,
auditoria e backup) já está no escopo.

- **`docs/DECISOES.md`**: **ADR-029** com contexto, decisão e consequências; a linha **P1** da tabela
  de pendências fica riscada e explica o motivo. Multi-caixa em rede (P2), encargos de crediário (P3),
  importação da planilha (P10) e as demais pendências continuam como estão — nenhuma delas é
  pré-requisito para o bazar operar.
- **`README.md`**: o bloco de estado passa a dizer **onde** o programa é usado (bazar da ONG, controle
  no lugar da caderneta) e que a ausência de nota fiscal é decisão de escopo, não pendência.
- **Manual (`ferramentas/manual_conteudo.py`)**: capítulo 1 reescrito — "Ele nasceu para o bazar de
  uma ONG...", e o quadro "Antes de tudo, a parte honesta" agora diz que não emitir documento fiscal é
  **decisão de escopo** e avisa, na mesma frase, que quem precisa de nota precisa de outro sistema. A
  lista "Não faz (ainda)" virou **"Não faz, por decisão de escopo"**.
- **`CONTRIBUINDO.md`**: quem procura suporte contratual e emissão fiscal é avisado de que não é
  questão de tempo — é escopo fechado.
- O aviso de que o cupom e os relatórios **não são documento fiscal** continua no rodapé do
  comprovante, no cabeçalho das exportações e no manual: a decisão é sobre escopo, não sobre verdade.

### Verificação — escopo

- `tests/test_manual.py` ganhou dois testes: o manual gerado contém "decisão de escopo", continua
  contendo "não emite documento fiscal" e **não** voltou a tratar a P1 como pendência (a checagem
  ignora "P11", que é outro assunto, — encontrado pelo próprio teste antes de fechar); e README,
  CONTRIBUINDO e DECISOES apontam para a ADR-029.
- Suíte **859 testes / 0 falhas / 0 skipped**; ruff e mypy limpos; manual regerado.

### Adicionado — manual do usuário em HTML, CSS e JS (`manual/index.html`)

O guia dentro do programa (F1) responde à dúvida do momento; faltava o documento inteiro para quem
está aprendendo do zero. Agora existe, e é gerado **do próprio programa**, não escrito à parte.

- **22 capítulos, 52 seções**: o que é o programa (e o que ele não é), instalação no Windows/Linux/
  macOS, primeiro uso, login e os cinco perfis, anatomia da tela, o dia de trabalho, a venda no PDV,
  caixa, produtos, clientes, crediário, estoque, vendas e relatórios, fechamento, auditoria, backup,
  área administrativa, ajuda, problemas comuns, atalhos e o capítulo técnico.
- **Duas trilhas no mesmo texto**: o corpo é escrito para quem nunca operou um PDV; o que é técnico
  (linha de comando, arquivos, variáveis de ambiente, arquitetura do código) vai em bloco recolhido
  "Para usuário avançado" — 6 deles — ou no capítulo técnico do fim do manual.
- **Conteúdo amarrado ao código**: o passo a passo, os campos e os atalhos de cada tela são lidos do
  guia de `aplicacao/ajuda.py` (14 temas); a matriz de permissões e os números citados vêm de
  `dominio/usuario.py` (32 ações; 8/24/5/30/32 permissões por perfil) e dos parâmetros de fábrica.
- **25 capturas embutidas** em `data:` URI (WebP, Pillow), com largura e altura declaradas — sem
  arquivo vizinho e sem `loading="lazy"`, que faria o salto de capítulo cair no lugar errado.
- **Cinco demonstrações que respondem**: calculadora de troco com até três formas de pagamento
  (formato brasileiro, avisa quando falta dinheiro), o caminho de uma venda em cinco passos, a matriz
  real de permissões com filtro por perfil e por ação, e a tabela de atalhos com busca.
- **Leitura**: sumário lateral com o capítulo atual marcado, busca no texto inteiro (sem acento, com
  destaque e sumário acompanhando o filtro), tema claro/escuro, imagem ampliada, barra de progresso,
  layout de 390 px a 2560 px e folha de estilo de impressão (imprimir/PDF pelo navegador).
- **`ferramentas/gerar_manual.py`** + **`ferramentas/manual_conteudo.py`** e `make manual`. O gerador
  recusa terminar se houver âncora sem destino, `id` repetido, recurso externo, captura ausente ou
  simulador citado e não implementado.
- O arquivo gerado é **versionado** (`manual/index.html`, 1,45 MB): abre por duplo clique, sem
  internet e sem o programa instalado.

### Verificação — manual

- `tests/test_manual.py` (20 testes): capítulos e seções não vazios, ids únicos, toda chave `guia`
  existente no programa e com conteúdo, toda captura citada presente em `docs/capturas/`, todo
  simulador implementado, HTML com as tags fechadas (parser), todo `href="#…"` com destino, nenhum
  recurso externo (`src` http, `<link>`, `@import`), capturas embutidas e com medida, `{VERSAO}`
  substituído, toda classe usada definida no CSS, e o arquivo versionado contendo os capítulos de
  hoje (pega "esqueci de rodar `make manual`").
- Página conferida em navegador de verdade (Chromium headless): 1440×900 e 390×844, tema claro e
  escuro, busca por "sangria" (8 seções, com destaque), salto de capítulo pelo sumário, calculadora
  de troco (R$ 37,40 com R$ 50,00 → R$ 12,60), imagem ampliada e fechamento com `Esc` — nenhum erro
  de console.

### Adicionado — pacotes de instalação para Windows, Linux e macOS

Até aqui só existia a receita do Windows (`build_windows.ps1` + Inno Setup). Agora há **um comando
só** para o sistema em que se está, e o mesmo pacote simples nos três: extrair (ou duplo clique),
abrir, usar.

- **`empacotamento/gerar_pacote.py`**: roda a suíte, chama o PyInstaller com a receita única e monta
  o pacote da plataforma — `.zip` portátil e `setup.exe` no Windows (quando há Inno Setup),
  `.tar.gz` com `Instalar.sh`/`Iniciar.sh`/atalho de menu no Linux, `.zip` com `BussolaPDV.app` e
  `.dmg` no macOS. `--sem-pyinstaller` reaproveita `dist/`, `--lista` só mostra o plano.
- **`empacotamento/pacotes/`**: os modelos que vão dentro do pacote — `Instalar.sh` (instala por
  usuário, sem sudo, com `--remover` que não toca na base), `Iniciar.sh`, `BussolaPDV.desktop`,
  `Iniciar.command` e o `LEIA-ME.txt` escrito para cada sistema.
- **`empacotamento/gerar_icone.py`**: passou a gerar também o **`.icns`** do macOS (contêiner da
  Apple com PNGs, escrito com `struct` — sem `iconutil`, que só existe no macOS) e o PNG 256 usado
  no menu do Linux.
- **`empacotamento/bussola.spec`**: no macOS cria o bundle `.app` (`BUNDLE`) com `Info.plist`,
  identificador, versão e ícone; no Windows e no Linux o bloco não existe.
- **`.github/workflows/pacotes.yml`**: matriz Linux + macOS que compila o pacote e sobe como
  artefato — é o caminho para gerar os pacotes dos outros sistemas sem ter as máquinas. Traz teste
  de fumaça (`--version` no binário empacotado) e não publica release sozinho.
- **`docs/PACOTES.md`**: o caminho simples, o **passo a passo manual** de cada sistema (comandos de
  PyInstaller, Inno Setup, `tar.gz`, `ditto`/`hdiutil`, AppImage opcional), a regra da compilação
  cruzada e a separação entre o que foi verificado e o que não foi.
- **`make pacote`** e `docs/INSTALACAO_WINDOWS.md` apontando para o documento novo.

### Verificação

- `tests/test_pacotes.py` (29 testes): três deles exercitam o empacotamento de verdade com um
  `dist/` falso — o zip do Windows abre com `LEIA-ME` sem marcador, o `.tar.gz` do Linux traz os
  scripts com bit de execução, e o macOS empacota o `.app`. O `.icns` é lido bloco a bloco (cabeçalho, tamanho declarado
  igual ao real, PNGs em 128/256/512), o `.desktop` é relido como INI, os três scripts passam em
  `sh -n` e estão com bit de execução, o `Instalar.sh` não usa sudo nem menciona a base, o `LEIA-ME`
  só usa marcadores que o gerador substitui, o `spec` cria o `.app` só no macOS e o workflow não
  publica release.
- Rodado nesta máquina (Linux x86_64): `python empacotamento/gerar_pacote.py` completo em **~58 s**;
  binário empacotado respondeu `--version`; `.tar.gz` de **100,3 MB** com migrações, `tzdata` e os
  dois logos dentro; `Instalar.sh` num `HOME` vazio criou programa, ícone e atalho, o instalado
  respondeu `--version`, e `--remover` apagou programa + atalho.
- **Não** gerados nem executados aqui: `.exe`, `setup.exe`, `.app` e `.dmg` — dependem de Windows e
  macOS.

## [0.11.0] — 2026-11-11 — Identidade visual: os dois logos oficiais

### Adicionado — identidade visual: os dois logos oficiais (ADR-028)

- **`src/bussola_pdv/recursos/`**: os dois arquivos enviados pelo responsável passam a ser versionados
  dentro do pacote — `logo_mini.png` (símbolo quadrado, 450×450) e `logo_comercial.png` (assinatura
  horizontal, 296×132). Nenhuma cor, traço ou texto foi redesenhado.
- **`src/bussola_pdv/ui/identidade.py`**: carrega, escala e tinge os logos; resolve o caminho em
  `sys._MEIPASS` (executável) antes do código-fonte; `RotuloLogo` (widget que se redesenha quando a
  densidade de tela muda, para não borrar em monitor a 150%).
- **Menu lateral**: o quadrado branco deixou de mostrar a **inicial da loja** e passou a mostrar o
  **símbolo oficial**, tingido com a cor primária da paleta. `tinta_do_simbolo` escurece o mínimo
  necessário quando a primária é clara demais para aparecer no branco (3:1).
- **Login, primeiro uso e diálogos**: faixa do cartão com o logo comercial. Quando há título de ação,
  o logo fica a 34 px ao lado dele; no login, o logo fica sozinho e maior (48 px), porque a assinatura
  já diz o nome e repetir o título seria redundante.
- **Área administrativa**: nunca troca de logo — o topo da coluna mostra a assinatura oficial e o
  `logo_data_uri` da loja é ignorado ali (inclusive ao salvar em *Marca e tema*).
- **Logo da loja**: quando o Admin Master envia um PNG, ele substitui o oficial **em tudo** no programa
  do usuário (login, primeiro uso, telas e menu) e não é tingido.
- **Ícone do programa**: `ui/app.py` aplica `logo_mini.png` como ícone de janela; o `.exe` continua
  usando o `.ico` embutido no recurso do Windows.
- **Instalador**: `empacotamento/gerar_icone.py` foi reescrito — em vez de desenhar uma bússola
  genérica, **deriva** tudo do `logo_mini.png`: `.ico` com 7 tamanhos (16 a 256), `bussola.png` 256² e
  os dois BMP do assistente (`WizardImageFile` e `WizardSmallImageFile`).
- **`empacotamento/bussola.spec`**: os PNG entram no bundle (`datas`). Sem isso o executável abriria
  sem logo nenhum.

### Verificação

- `tests/test_ui_identidade.py` (novo, 21 testes): caminho normal e em `sys._MEIPASS`, queda para o
  código-fonte quando o *data* falta, tinta do símbolo igual à primária (e escurecida quando a primária
  não aparece no branco), símbolo quadrado e em HiDPI, logo da loja vencendo o oficial, **admin
  ignorando o logo da loja**, data URI inválido recusado sem exceção, `RotuloLogo` com altura fixa.
- `tests/test_empacotamento.py`: o `spec` precisa listar os logos, o `.iss` precisa usar os dois BMP e o
  `.ico` precisa ter 16/32/48/256.
- `make responsivo` passa a medir também o `DialogoLogin` (o cartão com logo não pode passar de 640 px).
- Corrigidos dois testes que verificavam a implementação antiga (`monograma.text() == "M"` e a tinta da
  faixa do login, que agora é a do título).
- Suíte: **805 testes**, 0 falhas, 2 pulados; `ruff` e `mypy` (95 arquivos) limpos; `make responsivo` OK
  em 640×440 até 2560×1440.

### Adicionado — documento de contribuição e doação

- **`CONTRIBUINDO.md`**: como contribuir (relato de defeito, código, as regras que o projeto não abre
  mão, áreas onde ajuda é bem-vinda) e como apoiar financeiramente — **PIX**, **transferência bancária**
  e **PayPal**. Todos os campos de recebimento ficam como `«PREENCHER»`, com aviso explícito de que,
  enquanto houver marcador, **nenhuma doação deve ser enviada** e nenhum dado bancário deve ser
  inventado. Também diz o que a doação **não** compra (funcionalidade sob medida, prioridade, suporte
  com prazo) e o que o projeto nunca pede (senha, token, acesso remoto à base).
- **`ferramentas/gerar_qr_pix.py`**: gera o **BR Code** do PIX (padrão EMV do Banco Central) a partir da
  chave real — TLV, CRC16-CCITT e o texto do "copia e cola" — e desenha o QR em SVG (ou PNG, com
  Pillow). Sem serviço de terceiros no meio: a chave não sai da máquina. Uso:
  `python ferramentas/gerar_qr_pix.py --chave "..." --nome "..." --cidade "..."`.
- **`docs/doacoes/qr-pix.svg`**: espaço reservado que **diz na própria imagem** que não é QR válido —
  melhor do que um QR de exemplo que alguém escaneia e recebe erro do banco.
- **`.github/FUNDING.yml`**: liga o botão *Sponsor* do GitHub ao documento, com o modelo comentado para
  PayPal/Buy Me a Coffee/Liberapay quando as contas existirem.
- **README**: seção "Contribuir e apoiar" apontando para o documento.

### Verificação

- `tests/test_doacoes.py` (44 testes): CRC conferido contra o valor de referência do CCITT-FALSE
  (`"123456789"` → `29B1`) e não contra o próprio código; estrutura do payload relida campo por campo;
  chaves aceitas e recusadas; e — o ponto principal — o documento **falha no teste se alguém apagar os
  marcadores `«PREENCHER»`** ou deixar um campo de recebimento em branco.
- Suíte: **773 testes** passando; `ruff` e `mypy` (93 arquivos) limpos.

## [0.10.1] — 2026-11-11 — CI do Windows: testes de plataforma e falha que se explica

O GitHub mostrava **CI vermelho** no repositório. O workflow `CI` (Linux, 3.12 e 3.13) estava verde
desde o primeiro run; o `Windows` falhava sempre no mesmo passo — *Testes (Qt offscreen)* — e a única
mensagem na aba Actions era `Process completed with exit code 1`, sem dizer qual teste quebrou.

### Corrigido — teste preso à plataforma de quem roda a suíte

- **`TestEnvioCru` (envio ESC/POS cru).** O teste injetava `executores={"posix": ...}`, mas
  `enviar_bytes()` escolhe a chave pela plataforma: no Windows procura `"win32"`, não encontrava nada e
  levantava `ImpressoraIndisponivel`. Passava no Linux, falhava no Windows **por causa de uma chave de
  dicionário**, não do comportamento. Agora o mapa leva as duas chaves; o que o teste prova continua
  sendo o repasse dos bytes ao executor escolhido.
- **`TestFerramentaExterna` (backup sem o app).** O subprocesso recebia um `env` montado à mão com
  `PATH=/usr/bin:/bin:/usr/local/bin`. No Windows faltavam `SYSTEMROOT`/`COMSPEC` e o processo nem
  iniciava. O ambiente passou a ser herdado (`dict(os.environ)`), mantendo o que o teste quer de fato:
  `PYTHONPATH` vazio e `PYTHONIOENCODING=utf-8`.
- **Isolamento da pasta de dados nos testes de `caminhos`.** O fixture isolava só `XDG_DATA_HOME`; no
  Windows a pasta padrão vem de `%LOCALAPPDATA%`/`%APPDATA%`, então a suíte escrevia no perfil real do
  usuário. Agora as quatro variáveis (`XDG_*`, `LOCALAPPDATA`, `APPDATA`, `HOME`/`USERPROFILE`) apontam
  para o `tmp_path`.

### Adicionado — o CI aprende a dizer o que quebrou

- **`ferramentas/anotar_falhas.py`**: lê o JUnit XML do pytest e emite anotações no formato do GitHub
  Actions (`::error file=...,title=<teste>::<mensagem>`), mais um resumo em texto. Só biblioteca padrão,
  porque precisa rodar mesmo quando o projeto está quebrado.
- **Os dois workflows** (`ci.yml` e `windows.yml`) agora rodam o pytest com
  `--junitxml=relatorio-testes.xml`, chamam o anotador `if: failure()` e sobem o XML como artefato com
  `if: always()`. O próximo vermelho aparece com nome de teste, arquivo e mensagem — não com "exit code 1".

### Verificação

- Suíte local: **729 testes, 0 falhas** (`pytest -q --junitxml`), `ruff` e `mypy` limpos.
- `tests/test_anotar_falhas.py` (9 testes): o anotador extrai nome/arquivo/mensagem, não derruba o passo
  quando o relatório está ausente ou corrompido, e — o que mais importa — **falha se alguém tirar o
  `--junitxml` ou a chamada do anotador de qualquer um dos dois workflows**.
- O que **não** foi verificado: a execução real no Windows. O diagnóstico dos dois defeitos acima saiu da
  leitura do código (`sys.platform`, ambiente do subprocesso, variáveis de pasta); a confirmação vem do
  próximo run, agora com anotações.

## [0.10.0] — 2026-11-11 — mentor que explica a tela, e o guia completo na Ajuda

Pedido: *"gerar um mentor que irá explicar como as telas e os campos dentro do PDV funcionam e deixar
no menu a opção ajuda onde tenha o guia completo de uso do PDV e também se deseja ativar novamente o
uso orientado ou guiado"*.

### Adicionado — mentor (uso orientado)

- **Faixa de condução no rodapé do conteúdo.** Ao abrir uma tela com o uso orientado ligado, o mentor
  apresenta os passos daquele módulo — *Identifique a venda*, *Lance o produto*, *Pagamento*,
  *Finalize* — com o **campo do passo destacado** (borda na cor de destaque) e a tela rolando até ele.
- **Nada cobre a tela.** A faixa fica entre o conteúdo e o rodapé, não é máscara escura: o operador
  continua vendo e usando o que o mentor está explicando.
- **Anterior / Próximo / Concluir / Parar** e o atalho para o guia completo. Concluir o tour ou clicar
  em Parar gravam a escolha; o tour não volta a importunar. A fileira de botões quebra em linhas em
  janela estreita (`FluxoDeAcoes`) em vez de sair pela borda.
- Mentor por módulo: PDV, Caixa, Produtos, Vendas, Fechamento, Auditoria, Clientes, Crediário,
  Estoque e Administração. Entradas e Parâmetros não têm o que explicar — ali ele não aparece.

### Adicionado — Ajuda no menu

- **Item "Ajuda" com `F1`** (atalho de aplicação inteira). Não é página: abre a janela do guia e devolve
  o menu à página que estava aberta.
- **14 temas com busca**: começando o dia, PDV, caixa, produtos, vendas, fechamento, auditoria,
  clientes, crediário, estoque, administração, backup/reinstalação, mensagens de erro e atalhos. A busca
  ignora acento e caixa e varre título, resumo, passos, campos, atalhos e cuidados.
- **Campos explicados um a um** — o que é, o que aceita, o que acontece se errar — com os nomes que
  estão na tela.
- **Reativar o uso orientado**: botão no rodapé da Ajuda, além de "Começar do primeiro passo". A
  preferência mora em `ajuda.guiado` e sobrevive ao fechamento do programa.
- **Salvar o guia (.md)**: o guia inteiro em Markdown, para imprimir ou compartilhar.

### Verificação

- Suíte: **712 passando, 8 pulados**; `ruff` e `mypy` (93 arquivos) limpos; `make responsivo` OK em
  640×440 … 2560×1440 — agora medindo **com o mentor ligado**, que é como o programa abre no primeiro
  uso.
- `tests/test_ajuda.py` (34 testes) amarra guia e telas: todo `Passo.alvo` tem que existir como widget
  na tela real do módulo, todo tema com módulo tem que ter passo, todo ícone citado tem que existir em
  `icones.DESENHOS`, o parâmetro de preferência tem que estar em `ParametroRepositorio.PADROES`, e
  ligar/desligar/reativar tem que persistir.
- Capturas novas em `docs/capturas/`: `30_mentor_pdv.png`, `31_mentor_caixa.png`,
  `32_ajuda_guia.png`, `33_ajuda_busca.png`.

## [0.9.2] — 2026-11-11 — textos e campos que voltaram a aparecer

Dois relatos com print do Windows: *"na janela de login o botão de login não aparece texto"* e
*"na conferência e fechamento de turno a quantidade de notas fica difícil de entender e os campos não
aumentam"*.

### Corrigido — login com fundo apagado

- **Faixa do título e botão "Entrar" brancos sobre branco.** A causa não era a paleta: era a folha de
  estilo local que a v0.9.1 pôs no `QScrollArea` do cartão (`background: transparent`). No Qt, folha
  definida num widget **vale também para os filhos** — ela apagava o fundo da faixa do título e dos
  botões do diálogo, deixando texto branco sobre o branco do cartão. A folha local saiu; o fundo do
  diálogo passou a ser regra global por `objectName` (`QScrollArea#rolagemDialogo`).
- **Tinta da faixa por contraste**: `#loginMarca` usava `color: #FFFFFF` fixo. Com marca de primária
  clara (rosa, areia, cinza) o título sumia. Agora sai de `tinta_sobre()` — a mesma régua WCAG do resto.
- **Ícone do botão principal** deixou de ser branco fixo: `tinta_do_botao()` escolhe a cor pela paleta
  em vigor (login e primeiro uso).
- **Prévia de *Marca e tema*** usa tinta calculada nos três retângulos de exemplo; antes o texto de
  exemplo podia ficar invisível justo na tela em que a cor é escolhida.

### Corrigido — conferência de gaveta

- **Campo de quantidade cortado.** A coluna "Quantidade" era dimensionada pelo cabeçalho (~70 px) e o
  `QSpinBox` não cabia: o dígito ficava debaixo das setas e a seta direita caía fora da célula. Agora
  a coluna tem largura fixa de 132 px, o campo tem mínimo de 96×30, alinhamento à direita e
  `padding-right` de 16 px para as setas não cobrirem o número.
- **As 13 denominações aparecem de uma vez**: a tabela abre com a altura das 13 linhas (antes abria com
  5 e o conferente precisava rolar para terminar de contar a gaveta). Em tela baixa o teto de
  `ajustar_dialogo()` manda e a rolagem volta, como deve ser.

### Verificação

- 678 testes passando, 8 pulados; `ruff` e `mypy` limpos; `make responsivo` OK.
- Testes novos: o diálogo de login não pode ter folha local (é o defeito que apagava os fundos), a faixa
  do login tem de usar tinta com ≥ 4,5:1 em qualquer paleta, o ícone do botão acompanha a paleta, e os
  campos/tabela da conferência têm de caber sem corte e sem rolagem.
- Capturas `07_login`, `20_primeiro_uso`, `14_tema_personalizado`, `24_impressao_previa` e demais
  regeradas com o tema da loja aplicado.

## [0.9.1] — 2026-11-11 — a janela se ajusta à tela do Windows

O relato: *"a janela não está tendo todas as alterações de tamanhos e ajustes responsivos do Windows"*.
A interface já reagia à largura (v0.8.0), mas reagia a uma largura que o programa inventava: tamanho
inicial de 1280×820 e minimums de 720×480 / 700×460 escritos no código, medidos numa tela grande.

### Corrigido — a janela cabe na tela

- **Tamanho inicial derivado do monitor.** `abrir_no_tamanho_da_tela()` usa
  `primaryScreen().availableGeometry()`: até 92% da área útil, centralizado. Em 1366×768 com escala de
  150% o Windows oferece 911×512 de espaço lógico, e a janela nascia **maior do que a tela** — o rodapé
  e os botões da direita ficavam fora. O pedido agora é teto, nunca promessa.
- **Piso real de 946 px virou 640×440.** Medindo, o layout cobrava 737 px da janela de operação e
  **946 px** da administração, por causa de textos longos, não de conteúdo: rodapé (585 px), cabeçalho
  de cartão com título + ferramentas (614 px na Auditoria), status do turno do caixa (600 px) e a
  fileira "04 · Finalizar" do PDV (731 px).
- **`RotuloElastico`** para rodapé, barra superior, nome da loja e nome do operador: cortam com "…" e
  mostram o texto inteiro no `toolTip`; `.text()` continua devolvendo o texto completo.
- **`Cartao.minimumSizeHint()`**: o cabeçalho sempre cabe empilhado, então o mínimo é o maior dos dois
  (título **ou** ferramentas), não a soma.
- **Status do turno do caixa** com quebra de linha; **"04 · Finalizar"** virou `FluxoDeAcoes` (total e
  botões descem de linha em vez de passar da página).

### Corrigido — campos e conteúdo proporcionais

- **Bloco de pagamento do PDV com teto de 620 px**: combo de forma até 300, valor até 420. Em 1920 os
  dois recebiam **760 px cada** — caixa larguíssima com o texto perdido no meio e o valor longe do
  rótulo.
- **Quantidade** saiu da largura fixa de 80 px para a faixa 56–88.
- **`CaixaInfo`** com 74 px de altura mínima: o valor em corpo grande vem do QSS e o `sizeHint` do
  `QLabel` é medido antes de a folha ser aplicada; com 56 px o número aparecia cortado embaixo quando a
  grade refluía para duas colunas.
- **Diálogos altos rolam** (`RolagemDeCartao`): em 512 px lógicos o formulário de primeiro uso era
  cortado em cima e embaixo, sem barra para chegar ao resto. `ajustar_dialogo()` também não fixa mais
  altura mínima que estoure em tela baixa.

### Verificação

- `make responsivo` mede agora **640×440, 800×600, 911×512 (1366×768 a 150%), 1024×768, 1280×800,
  1366×768, 1920×1080 e 2560×1440** e falha se a janela abrir maior do que a área útil, menor do que o
  próprio mínimo, se algum campo de pagamento passar do teto ou se uma página pedir mais largura do que
  tem. Resultado: **OK nas oito resoluções**.
- Novas capturas `28_pdv_911x512.png` e `29_vendas_911x512.png`.
- 673 testes passando, 8 pulados; `ruff` e `mypy` limpos.

### Nota

A medição é offscreen, onde a tela do Qt tem 800×800. Falta o teste no Windows real com escala de 125%
e 150% — é o próximo passo do responsivo, e está registrado como pendência.

## [0.9.0] — 2026-11-11 — contraste legível e backup que sobrevive à reinstalação

Dois relatos de campo nesta rodada: "as cores de algumas áreas do PDV estão
gerando problemas de leitura" e "gere um recurso de backup caso seja preciso
reinstalar, mesmo que o programa não esteja funcionando".

### Corrigido — leitura

- **Fundo preto atrás do conteúdo no Windows em modo escuro.** O Qt 6.5+ segue o
  tema do sistema: com o Windows escuro, a paleta padrão vinha escura e o
  `QScrollArea` (deixado transparente na v0.8.0) mostrava o preto atrás dos
  cartões — descrição de seção, rodapé e faixas ficavam ilegíveis. Agora
  `criar_aplicacao()` fixa estilo `Fusion` + `QPalette` clara derivada da marca
  (`paleta_do_tema`), e a folha pinta `QScrollArea`, o viewport e `#pagina`.
- **Texto branco sobre amarelo/verde-água nas amostras de cor.** A tinta do
  rótulo vinha de luminosidade média (`lightnessF() > 0.6`), que erra no amarelo:
  `#FFC107` com branco dá **1,63:1**. Agora a escolha é por **razão de contraste
  WCAG** (`tinta_sobre`), a mesma regra usada nos botões.
- **Cinza do texto secundário abaixo de AA**: `#6C757D` sobre `#F4F6F9` dava
  **4,33:1**. O padrão passou a `#5F686F` (5,25:1) e a folha **corrige qualquer
  paleta** nessa situação (`garantir_contraste`), aproximando a tinta do preto só
  o necessário.
- A prévia de acessibilidade em *Marca e tema* mostra as três medidas
  (texto/superfície, branco/primária, secundário/fundo) e explica quando corrige.

### Adicionado — backup

- **`aplicacao/backup.py`: cópia com manifesto.** `ServicoBackup` cria a cópia
  pela API do SQLite, verifica `integrity_check` + tabelas obrigatórias e grava
  `*.manifesto.json` com data, versão do app, versão do esquema, contagem de
  registros e `sha256`. O manifesto é legível sem o programa — de propósito.
- **Cópia automática diária** ao abrir o programa (uma por 24 h, mantendo as 14
  últimas; manual nunca é podada). Falha de backup não impede a loja de abrir:
  vira aviso em `logs/erros.log`.
- **`ferramentas/backup_externo.py` + `backup_externo.bat`**: backup que **não
  depende do aplicativo** — só biblioteca padrão. Verbos `criar`, `listar`,
  `verificar`, `restaurar` e `recuperar` (base danificada via `iterdump`).
  Shipado nas pastas `Backup\` do executável e do instalador.
- **CLI**: `bussola backup --listar | --verificar ARQ | --restaurar ARQ |
  --recuperar ARQ | --automatico | --manter N`.
- **Manutenção (interface)**: grupo "Cópias automáticas" com a última cópia, botão
  para forçar a do dia e o caminho do backup externo. A pasta sugerida deixou de
  ser `copias` relativa (que não aceita escrita em `Program Files`) e passou a ser
  `<pasta de dados>\copias`.
- **`docs/BACKUP.md`**: onde ficam os dados, os três tipos de cópia, recuperação
  de base danificada e o **checklist de reinstalação** sem perder nada.

### Verificado

- 664 testes (28 novos), `ruff`, `mypy` (90 arquivos) e `make responsivo` verdes.
- O tema foi conferido com a **paleta escura do sistema forçada** e as telas
  capturadas (PDV, Caixa e Administração › Marca e tema) saem claras e legíveis.
- A ferramenta externa roda em **processo separado com `PYTHONPATH` vazio**:
  criar, listar, verificar (inclusive arquivo inválido → código 2), restaurar e
  recuperar foram exercitados contra uma base de demonstração.
- **Limite declarado**: nada disto rodou em Windows real; o `.bat` não tem teste
  automatizado (o conteúdo é verificado só por leitura).

## [0.8.2] — 2026-11-11 — primeiro uso no Windows: fuso horário e base preservada

Correção do erro relatado em campo: `PermissionError: [WinError 32] O arquivo já
está sendo usado por outro processo: 'D:\pdv\pdv.db' -> 'D:\pdv\pdv.db.antigo-…'`
na tela de instalação. Havia **dois** problemas, e o segundo escondia o primeiro.

### Corrigido

- **`ZoneInfoNotFoundError: America/Sao_Paulo` no Windows.** O Windows não traz
  base IANA de fusos: `ZoneInfo` depende do pacote PyPI `tzdata`. Ele passou a ser
  dependência de execução (`pyproject.toml`) e é copiado para dentro do
  executável (`collect_data_files("tzdata")` no `.spec`).
- **Fuso com reserva**: sem a base IANA, `resolver_fuso` usa deslocamento fixo
  (São Paulo = `UTC-03:00`), registra o aviso em `logs/erros.log` e a loja abre
  normalmente. Nome de fuso desconhecido continua sendo erro, com a mensagem
  que aponta o `tzdata`.
- **A base não é mais movida por erro que não é dela.** `_abrir_ou_recomecar`
  tratava **qualquer** exceção como "banco corrompido": arrastava um `pdv.db` bom
  para `pdv.db.antigo-…` e o operador via `WinError 32`. Agora só
  `sqlite3.DatabaseError` e o novo `EsquemaAusente` autorizam o recomeço; o resto
  sobe com o motivo real.
- **`Contexto.abrir` monta o relógio antes de abrir o arquivo** e fecha a conexão
  se a migração falhar: a falha de fuso não deixa mais o `.db` travado.
- **`WinError 32` explicado**: o `rename` da base tenta três vezes (antivírus e
  `-wal`/`-shm` seguram o arquivo por instantes) e, se persistir, a mensagem manda
  fechar as outras janelas do programa em vez de mostrar o código do Windows.
- `bussola relogio` (sem `--banco`) virou diagnóstico de fuso: mostra o fuso em
  uso, a data de negócio e se a base IANA está OK; com `--banco` continua
  mostrando a data de negócio da instalação.

### Verificado

- 636 testes (13 novos), `ruff`, `mypy` (89 arquivos) e `make responsivo` verdes.
- Novos testes reproduzem o relato: falha de fuso **não** move a base, base presa
  por outro processo explica o que fazer, conexão é fechada quando a migração
  falha, `Contexto.abrir` não toca no arquivo se o fuso falhar, e o `.spec`/o
  `pyproject.toml` carregam o `tzdata`.
- Executado no sandbox **sem** `tzdata` (mesma condição do Windows sem o pacote):
  `bussola relogio` avisa e `bussola info`/primeiro uso seguem funcionando.
- **Limite declarado mantido**: nada disto foi rodado em Windows real nem no
  `.exe` compilado — o que está verificado é a suíte automatizada.

## [0.8.1] — 2026-11-11 — imprimir relatório, reimprimir por cupom e imprimir pela CLI

Complemento da v0.8.0: a impressão deixa de ser só do cupom do PDV e do turno do Caixa.

### Adicionado

- **"Imprimir" em todas as telas de relatório** — Fechamento, Vendas, Produtos (catálogo),
  Auditoria, Clientes, Crediário e Estoque ganharam o botão ao lado do "Exportar", alimentado pela
  **mesma função** que monta o relatório exportado (`botao_para_relatorio`). O relatório é montado no
  clique, então o papel sai com o filtro que está na tela.
- **Reimpressão pela tela de Vendas**: selecionar a venda e clicar em "Reimprimir cupom" imprime a 2ª
  via daquela venda — fecha a lacuna do F8, que só alcançava a última venda da estação.
- **`bussola imprimir` na linha de comando**: cupom (`--venda 1-000012`) ou qualquer relatório
  (`--tipo turno|fechamento|vendas|…`) para a impressora configurada ou para `.pdf`/`.txt`
  (`--saida`). Mesma autenticação, mesma permissão e mesma auditoria da interface.
- **`VendaRepositorio.por_rotulo`**: busca pelo número que está impresso no papel (`1-000012`), não
  só pelo UUID — é o que o suporte tem em mãos.
- **`ServicoImpressao.venda_por_referencia`**: aceita id, rótulo, número puro e `cupom:1-000012`.

### Alterado

- **Permissão de impressão passou a depender do documento**: cupom continua exigindo
  `CUPOM_REIMPRIMIR` (atendente tem); **relatório** exige `EXPORTAR_DADOS` (atendente não tem,
  contabilidade tem) — imprimir relatório é tirar dado da loja, igual a exportar. A checagem é no
  serviço (`despachar(..., permissao=...)`), não só no botão.
- **Grade × pares na bobina agora é decidida pela viabilidade, não pela largura do papel**: antes uma
  tabela com 4 colunas em 80 mm saía como `R$ 30,…` — dinheiro truncado é dado errado. Agora a grade
  só é usada quando cabeçalho, dinheiro, quantidade e data cabem inteiros; texto pode ser elidido com
  `…` e, se o resto não couber, a tabela vira pares rótulo/valor.
- **Par na bobina usa a última coluna numérica como valor** (e não a última coluna qualquer): a coluna
  "Autorizador" vazia empurrava o dinheiro para o meio da linha.
- **Rodapé sem aviso fiscal repetido**: os relatórios já trazem "não é documento fiscal"; o aviso
  padrão só entra se nenhum outro falar de documento fiscal (antes saíam três linhas quase iguais).
- `BotaoImprimir` expõe `permitido` e recebe `permissao`; `DialogoPreviaImpressao` idem.
- **Ferramentas de cartão passaram a quebrar de linha**: `Cartao.ferramentas` virou um
  `FluxoDeAcoes`. Com "Exportar" + "Imprimir" + resumo do filtro lado a lado, a tela de Produtos
  pedia 732 px e a de Vendas 823 px num espaço de 731 px — o `make responsivo` reprovava as duas.
  A fileira de filtros da tela de Vendas (datas, Filtrar, Reimprimir cupom, Cancelar venda) também
  virou fluxo. `FluxoDeAcoes.adicionar` deixou de chamar `show()` em widget escondido de propósito:
  reparentar escondia o filho e o `show()` reexibia o botão sem permissão.

### Verificado

- 623 testes (13 novos), `ruff`, `mypy` (89 arquivos) e `make responsivo` verdes
  (`800×600`, `1024×768`, `1280×800`, `1366×768`, `1920×1080`, sem tela cortada).
- CLI exercitada de verdade contra base de demonstração: cupom `1-000012` em PDF de 58 mm, turno em
  TXT de 80 mm, cupom inexistente (`1-999999`) recusado com mensagem, contabilidade barrada no cupom.
- **Limite declarado mantido**: nenhuma impressão em hardware real; segue valendo o roteiro manual de
  `docs/IMPRESSAO.md`.

## [0.8.0] — 2026-11-11 — impressão em impressora comum e em térmica (58/80 mm)

### Adicionado

- **`dominio/impressao.py`: o documento imprimível é dado, não texto de tela.** Blocos
  (`Texto`, `Par`, `Divisor`, `Espaco`, `Item`, `CodigoDeBarras`), perfis de papel com largura em
  colunas (bobina 58 → 32, bobina 80 → 48, A4 → 80) e **uma única** quebra de linha, em
  `DocumentoImpresso.layout()`. Os renderizadores só pintam — o cupom do PDV, a 2ª via e o PDF saem
  do mesmo documento.
- **`infra/impressao/papel.py`: desenho em grade de colunas + driver do sistema.** Cada caractere é
  pintado na coluna que lhe cabe (fonte proporcional não desalinha mais o valor à direita); PDF no
  tamanho exato do papel (bobina = uma página contínua), prévia em imagem e impressão por `QPrinter`
  com detecção de impressora que não aceitou o trabalho.
- **`infra/impressao/escpos.py`: bytes ESC/POS.** `ESC @`, tabela cp1252, alinhamento, negrito,
  duplo, código de barras nativo (`GS k 4`), avanço, corte (`GS V 66 0`) e gaveta (`ESC p`), com
  transliteração do acento (a página de código da térmica varia por fabricante).
- **`infra/impressao/impressoras.py`: descobrir e enviar.** Lista as instaladas pelo sistema, sugere
  quais são térmicas pelo nome (só sugestão, nunca decisão) e envia bytes crus por `winspool.drv`
  (`ctypes`, sem `pywin32`) no Windows ou `lp -o raw` no Linux/macOS.
- **`infra/impressao/texto.py`**: prévia em texto puro, `.txt` e depuração da transliteração.
- **`aplicacao/impressao.py`: `ServicoImpressao`.** Monta o cupom a partir do que está **gravado** no
  banco (`itens()`, `pagamentos()`, `Marca`), converte `Relatorio` em documento impresso (tabela em
  grade no A4, pares rótulo/valor na bobina), despacha pelo motor configurado e grava auditoria.
  Também salva PDF/TXT em qualquer pasta — plano B quando não há impressora.
- **`ui/impressao.py`: prévia antes do papel.** Diálogo com escolha de papel, impressora instalada,
  cópias e prévia desenhada pelo mesmo código que imprime; botões Imprimir / Salvar PDF / Salvar TXT.
  `BotaoImprimir` é o equivalente do `BotaoExportar` para as telas.
- **PDV**: o comprovante da venda virou caixa com **"Imprimir cupom"**, e a última venda da estação
  pode ser reimpressa com **F8**, marcada como 2ª via. Com `impressao.imprimir_automatico` ligado, o
  cupom sai sem clique extra.
- **Caixa**: botão **"Imprimir turno"** ao lado do Exportar e oferta do comprovante de fechamento
  logo depois de fechar o turno (o relatório é montado com o `turno_id`, já fechado).
- **Código de barras CODE 39** com o número do cupom, desenhado módulo a módulo no PDF (razão 3:1,
  teto de 60 mm para não virar um borrão em A4) e impresso nativamente na térmica.
- **Oito parâmetros de impressão** (`impressao.motor`, `.impressora`, `.papel`, `.copias`,
  `.cortar_papel`, `.abrir_gaveta`, `.codigo_de_barras`, `.imprimir_automatico`), com novo tipo
  `OPCAO` (lista fechada) e campo de impressora que lista as instaladas sem impedir nome digitado.
- **Permissão `CUPOM_REIMPRIMIR`** (master, admin, gerente e atendente; contabilidade não) e eventos
  de auditoria **`IMPRESSAO_REALIZADA`** / **`IMPRESSAO_FALHOU`**, com impressora, motor, papel,
  linhas, cópias e motivo da falha.
- **Erros de impressão com saída clara**: `ErroImpressao` e `ImpressoraIndisponivel`, carregando
  impressora, motivo e lista de instaladas.
- **`docs/IMPRESSAO.md`** (configuração, arquitetura, roteiro de teste manual em hardware, problemas
  comuns), **ADR-022**, exemplos em `docs/exemplos/cupom-exemplo-*.pdf|txt` e captura da prévia.

### Alterado

- `TelaCaixa`: a fileira de ações do turno passou de `QHBoxLayout` para `FluxoDeAcoes` — com o botão
  de impressão, seis ações não cabiam lado a lado em 800 px.
- `dominio/erros.py`, `dominio/usuario.py`, `dominio/auditoria.py`, `aplicacao/parametros.py`,
  `ui/admin/parametros.py` e `infra/sqlite/repositorio_usuarios.py` ganharam o que a impressão exige
  (erros, permissão, eventos, tipo de parâmetro e padrões).
- `ferramentas/gerar_exemplos.py` passou a gerar os cupons de exemplo e `ferramentas/captura_telas.py`
  a capturar a prévia de impressão.

### Verificado

- 610 testes passando (47 novos em `tests/test_impressao.py`), incluindo: nenhuma linha do cupom passa
  das colunas do papel nos três papéis; o cupom traz os dados gravados da venda; PDF de bobina com
  57,9 mm de largura em página única; motor `ESCPOS` manda os bytes uma vez por cópia e recusa A4;
  falha de impressão audita e propaga; impressora inexistente falha com mensagem acionável.
- `ruff`, `mypy` (89 arquivos) e `make responsivo` (800×600 → 1920×1080) verdes.
- **Limite declarado**: não houve impressão em hardware real — o ambiente de desenvolvimento não tem
  CUPS nem impressora. O roteiro de conferência manual está em `docs/IMPRESSAO.md`.

## [0.7.0] — 2026-11-11 — responsividade: a interface se organiza pela largura da janela

### Adicionado

- **`ui/responsivo.py`, a camada de responsividade.** Régua única de largura (`compacta` < 900 px,
  `media` < 1180 px, `ampla`) e as peças que reagem a ela. Nenhuma tela compara pixels por conta
  própria — todas perguntam a faixa.
- **`GradeDeIndicadores`**: os cartões de indicador deixaram de ser um `QHBoxLayout` fixo e passaram a
  refluir 4 → 3 → 2 → 1 por linha, com altura mínima acompanhando as linhas.
- **`CascaResponsiva`** (herdado por `JanelaPrincipal` e `JanelaAdmin`): sidebar recolhe sozinha na
  faixa compacta, chip do usuário/trilha/rodapé direito somem e a margem cai de 18 para 10 px. O botão
  do menu continua valendo e a escolha manual do operador dura até a janela mudar de faixa.
- **Cabeçalho de cartão em duas formas**: com o cartão abaixo de 640 px, as ferramentas ("Exportar",
  resumo da consulta) descem para a segunda linha em vez de impor largura mínima à página.
- **`ColunasDaTabela`**: tabela mede o conteúdo e decide entre esticar a coluna elástica (quando cabe)
  e ligar a rolagem horizontal da própria tabela (quando não cabe), com piso de 84 px por coluna.
- **Rolagem vertical da área de conteúdo** (`QScrollArea` em volta da pilha de páginas): em 600 px de
  altura os formulários do PDV rolam em vez de se sobrepor.
- **`ajustar_dialogo()`**: login, autorização, primeiro uso e conferência de gaveta não nascem maiores
  do que a tela disponível.
- **`FluxoDeAcoes`**: fileiras de botões (Usuários, Permissões, Manutenção, Parâmetros, Marca,
  Dependências) quebram em várias linhas em vez de sair pela borda — a fileira de sete botões de
  Usuários ficava cortada em 800 px.
- **`GradeDeCartoes`**: os dois blocos de "Marca e tema" (identidade e prévia) empilham em janela
  estreita; os quinze botões de cor passam de duas colunas para uma.
- **Rolagem vertical também na área administrativa**, que passou a usar `PilhaDePaginas`: antes a
  seção mais larga (856 px) impunha largura mínima a todas e "Marca e tema" era cortada em 800×600.
- **`ferramentas/verificar_responsivo.py`** (`make responsivo`): mede as duas janelas em 800×600,
  1024×768, 1280×800, 1366×768 e 1920×1080 e falha se algo estourar.
- **Capturas novas** em 800×600 (`docs/capturas/21_pdv_800x600.png`, `22_produtos_800x600.png`) ao lado
  das capturas em 1280×820.
- **25 testes** em `tests/test_ui_responsivo.py`; suíte em **563**.

### Corrigido

- **Página de Produtos exigia 949 px de largura mínima** (título + subtítulo + "Exportar" lado a lado) e
  era cortada em 1024×768.
- **Cartões de indicador se sobrepunham em 800×600**: a grade refluía para duas linhas sem crescer a
  altura mínima, e o segundo cartão era desenhado sobre o primeiro.
- **Grupos do PDV ficavam por baixo uns dos outros** em janela baixa, sem rolagem.
- **Coluna elástica colapsava**: em janela estreita o cabeçalho "Descrição" aparecia como "›escriçã" e
  "Saldo" saía da área visível, sem rolagem.
- **Janela não podia ser reduzida**: mínimo declarado agora é 720×480 (operação) e 700×460 (administração).

## [0.6.1] — 2026-11-11 — correção: botão "Criar instalação" mudo e pasta de dados escolhível

### Corrigido

- **"Criar instalação" não fazia nada em caso de erro.** O diálogo de primeiro uso só tratava
  `ErroBussola`: qualquer outra exceção (`sqlite3.OperationalError` de pasta sem permissão ou arquivo
  travado, `DatabaseError` de base corrompida, erro de esquema ausente em instalação incompleta)
  escapava do slot do Qt e ia para o `stderr` — que **o executável do Windows não tem**. Para o
  operador, o botão estava morto. Agora: erro aparece na tela com tipo e mensagem, vai para
  `logs/erros.log` e o botão volta a funcionar.
- **Nenhuma exceção não tratada some.** `diagnostico.instalar_captura_de_erros()` troca o
  `sys.excepthook` na entrada do app empacotado: exceção fora de `try` vira caixa de diálogo com
  resumo e caminho do log (idempotente, sem empilhar hooks).
- **Base inutilizável não prende a instalação.** Se já existe um `pdv.db` vazio ou corrompido (tentativa
  anterior interrompida), o arquivo é guardado como `pdv.db.antigo-AAAAMMDD-HHMMSS` e a instalação
  recomeça; nada é apagado.
- **`entrada.main` recalculava o banco antes do diálogo**: a pasta escolhida na primeira tela era
  ignorada e o programa abria a base antiga.
- **Pasta sem escrita falhava com "unable to open database file"**: agora é testada antes de abrir o
  banco, com mensagem que diz o que fazer.

### Adicionado

- **Pasta dos dados escolhível no primeiro uso** (`ui/primeiro_uso.py`): campo com *Procurar…*,
  prévia do caminho do banco e validação de escrita. A escolha é gravada em
  `%APPDATA%\BussolaPDV\instalacao.json` (Linux: `~/.config/bussola-pdv`) — **fora** da pasta de
  dados, senão mudar de pasta perderia o ponteiro.
- **`caminhos.py` com precedência explícita**: `BUSSOLA_DADOS` > pasta escolhida > padrão do sistema;
  `origem_do_diretorio()` diz de onde veio a escolha.
- **CLI `bussola dados`**: mostra pasta de dados, origem, banco, cópias, relatórios e logs;
  `--definir PASTA [--mover]` copia a base com verificação de integridade (sem apagar a antiga) e
  `--padrao` descarta a escolha.
- **Administração → Manutenção → "Pasta de dados da instalação"**: mostra a pasta em uso e a origem;
  o Admin Master troca dali, com a mudança registrada na trilha (`PARAMETRO_ALTERADO`,
  entidade `pasta_de_dados`).
- **Instalador permite escolher a pasta do programa**: `DisableDirPage=no` explícito no `.iss`.
- `tests/test_caminhos_instalacao.py` (23) e mais 8 testes em `tests/test_primeiro_uso.py` (20 no total);
  captura `20_primeiro_uso.png`.
- `docs/DECISOES.md` ADR-020 (ponteiro de configuração fora dos dados e falha sempre visível).

### Alterado

- `docs/INSTALACAO_WINDOWS.md` separa **pasta do programa** × **pasta dos dados**, com o passo a passo
  para escolher, mover e voltar ao padrão.

### Limites conhecidos

- Mudar a pasta de dados **não move os arquivos sozinho** pela interface: a tela grava a escolha e
  avisa; a cópia é feita por `bussola dados --mover` (ou manualmente) com o programa fechado.
- Em Linux/macOS o log e o ponteiro seguem os diretórios XDG/Application Support; só o caminho do
  instalador é específico do Windows.

## [0.6.0] — 2026-11-11 — pré-alfa: clientes, crediário e estoque fora do placeholder

### Adicionado

- **Tela de Clientes** (`ui/telas_clientes.py`): carteira com limite, saldo em aberto, disponível e
  vencido por cliente, busca por nome/documento mascarado, quatro indicadores no topo e
  `BotaoExportar` (Excel/PDF).
- **Tela de Crediário** (`ui/telas_crediario.py`): títulos com vencimento, principal, recebido, saldo,
  atraso em dias e status; linhas em atraso destacadas em vermelho; caixa "incluir títulos já
  recebidos"; indicadores de títulos em aberto, saldo, atraso e saldo vencido.
- **Tela de Estoque** (`ui/telas_estoque.py`): saldo, mínimo, ponto de pedido, situação
  (`RUPTURA`/`BAIXO`/`REPOSICAO`/`OK`) e valor a custo por produto, busca por código/descrição e
  indicadores de ruptura e abaixo do mínimo.
- **Exportar do turno** (`ui/tela_caixa.py`): botão no cartão *Turno* que grava a conferência do turno
  aberto em Excel **ou** PDF (dinheiro esperado, movimentos e contagem por denominação). Fica
  desabilitado quando não há turno aberto e não aparece para quem não tem `EXPORTAR_DADOS`.
- **Novos relatórios** em `ServicoExportacao`: `relatorio_clientes(busca)`, `relatorio_estoque(busca)`,
  `relatorio_turno(turno_id=None)` e `relatorio_crediario(incluir_pagos=…)`, com as respectivas
  funções `exportar_clientes`, `exportar_estoque`, `exportar_turno` e `exportar_crediario`.
- **CLI**: `--tipo clientes|estoque|turno`, `--turno <id>` e `--incluir-pagos` no `bussola exportar`.
- `ajustar_colunas()` (`ui/widgets.py`): coluna esticada + demais pelo conteúdo, para cabeçalho como
  "Ponto de pedido" não ser cortado.
- Testes: `tests/test_exportacao_modulos.py` (27) e `tests/test_ui_telas_modulos.py` (12).
- Capturas `16_clientes`, `17_crediario`, `18_estoque` e `19_caixa_exportar`; exemplos
  `docs/exemplos/turno-exemplo.{pdf,xlsx}` e `estoque-exemplo.{pdf,xlsx}`.

### Corrigido

- **Saldo do crediário subestimado**: os relatórios contavam só `status == "ABERTO"` e ignoravam
  título `PARCIAL`, que ainda tem saldo. Agora "em aberto" é todo título com `saldo_centavos > 0`.
- **Placeholder de módulo era inalcançável**: `_selecionar()` criava a página vazia sob demanda e
  chamava `setCurrentIndex(10)` num `QStackedWidget` com 9 páginas; o índice era ignorado e a tela
  anterior continuava visível. As páginas de módulo não implementado agora existem desde o início,
  no índice certo — clicar em "Entradas" ou "Parâmetros" mostra o aviso de fato.

### Alterado

- Módulos **Clientes, Crediário e Estoque** deixaram de ser placeholder; restam **Entradas** e
  **Parâmetros** marcados como não implementados.
- `ServicoCrediario.listar(incluir_pagos=…)` passou a ser usado também pela exportação, para que a
  tela e o arquivo mostrem exatamente o mesmo conjunto de títulos.

### Limites conhecidos

- As telas de Clientes, Crediário e Estoque são **de consulta e exportação**: cadastrar cliente,
  receber título e dar entrada em estoque continuam só na API/serviço (com testes), sem botão.
- **Entradas** de estoque e **Parâmetros** de tela continuam não implementados e aparecem marcados.
- Documento de cliente sai **mascarado** no arquivo (LGPD): não há opção de exportar CPF/CNPJ inteiro.

## [0.5.0] — 2026-11-11 — pré-alfa: exportação em Excel e PDF

### Adicionado

- **`BotaoExportar`** (`ui/exportacao.py`) no cabeçalho do cartão de **Fechamento, Vendas, Produtos e
  Auditoria**: menu com *Excel (.xlsx)* e *PDF*, nome de arquivo sugerido
  (`fechamento-do-caixa-2026-11-11.xlsx`), pasta de relatórios do usuário, botão "Abrir pasta" na
  confirmação e correção da extensão quando o usuário não digita. O botão **não aparece** para quem
  não tem `EXPORTAR_DADOS`.
- **Relatório como dado** (`dominio/relatorio.py`): `Relatorio`, `Tabela`, `Coluna` e `TipoColuna`
  (texto, inteiro, moeda, data). Tela e arquivo partem da mesma estrutura e dos mesmos centavos
  inteiros; a formatação é do exportador, não de quem monta.
- **Escritor `.xlsx` sem dependência** (`infra/exportacao/xlsx.py`): aba `Resumo` + uma aba por
  tabela, filtro automático, painel congelado, larguras, moeda como número com formato `R$`, data
  como data do Excel (serial + `dd/mm/aaaa`), metadados, nome de aba saneado (31 caracteres, sem
  `[]:*?/\`, único) e gravação atômica.
- **Escritor `.pdf` com Qt** (`infra/exportacao/pdf.py`): A4, identificação da loja, indicadores,
  tabelas zebradas, avisos, paginação própria e rodapé `página X de Y` em todas as páginas.
- **`ServicoExportacao`** (`aplicacao/exportacao.py`): monta os relatórios de **fechamento, vendas,
  catálogo/estoque, auditoria e crediário**, exige `EXPORTAR_DADOS` e grava o evento
  `DADOS_EXPORTADOS` (autor, formato, linhas, filtros, arquivo) na trilha append-only.
- **CLI `bussola exportar`**: `--tipo fechamento|vendas|catalogo|auditoria|crediario`, `--formato
  xlsx|pdf`, `--destino` (arquivo ou pasta), `--data`, `--de/--ate`, `--busca`, `--limite`,
  `--login`; autentica de verdade (senha via `BUSSOLA_SENHA` ou prompt) e sai com código 2 quando
  falta permissão, senha está errada ou o banco não existe.
- `caminhos.pasta_de_relatorios()` (`%LOCALAPPDATA%\BussolaPDV\relatorios`, sobreponível por
  `BUSSOLA_DADOS`), ícones `planilha` e `documento` (23 → 25 SVGs).
- `docs/EXPORTACAO.md` (o que exporta, formatos, permissão, auditoria, limites, checklist),
  exemplos versionados em `docs/exemplos/` e `ferramentas/gerar_exemplos.py`.
- Testes: `tests/test_exportacao.py` (41) e `tests/test_ui_exportacao.py` (13).

### Alterado

- `Acao.EXPORTAR_DADOS` passou a se chamar "Exportar relatórios (Excel e PDF)" na tela de permissões
  (o rótulo antigo dizia CSV, formato que o programa nunca gerou).
- `openpyxl` e `pypdf` entraram no extra `dev` **só para teste**: são usados para abrir o arquivo
  gerado com uma biblioteca de verdade. Execução continua com duas dependências.
- Captura `05_fechamento.png` regerada com sessão de gerente e dia com movimento, para mostrar o
  botão *Exportar*.

### Corrigido

- PDF exportado pelo terminal criava um `QGuiApplication` temporário que era coletado; a janela Qt
  seguinte abortava o processo (`QWidget: Must construct a QApplication`). Agora a aplicação criada
  é `QApplication`, fica referenciada no módulo e é reaproveitada.
- `Marca` ausente na base recém-criada não impede mais exportar (cai no nome padrão).

### Limites desta versão

- Sem agendamento de exportação, sem gráficos/fórmulas na planilha, sem assinatura digital no PDF e
  sem homologação de impressora térmica.
- O PDF não é PDF/A e a planilha não tem macro: são documentos de conferência, não fiscais.

## [0.4.0] — 2026-11-11 — pré-alfa: instalação no Windows e empacotamento

### Adicionado

- **`docs/INSTALACAO_WINDOWS.md`**: guia passo a passo (Python 3.12 x64, PowerShell/CMD, venv,
  `pip install -e .`, primeiro `init`, abrir o programa, backup, atalho, atualização, desinstalação),
  com tabela de pacotes pip (execução, `dev`, `empacotamento`), dependências de sistema, pasta de
  dados, SmartScreen/antivírus, solução de problemas e checklist de validação.
- **Primeiro uso sem terminal** (`ui/primeiro_uso.py`): quando a base não existe (ou existe sem
  usuário), o programa abre um diálogo que cria o Admin Master, o caixa `Caixa 1` e grava o nome da
  loja — pelos mesmos casos de uso do `bussola init`, sem caminho paralelo de escrita.
- **`ui/entrada.py`** (`bussola-pdv`) agora abre a instalação instalada de verdade: base em
  `%LOCALAPPDATA%\BussolaPDV`, primeiro uso quando necessário, e qualquer argumento devolve o
  controle ao CLI (`backup`, `info`, `demo`…).
- **`caminhos.py`**: diretório de dados por sistema operacional
  (`%LOCALAPPDATA%\BussolaPDV`, `XDG_DATA_HOME/bussola-pdv`, `~/Library/Application Support`),
  sobreponível por `BUSSOLA_DADOS`; dados deixam de morar na pasta do programa.
- **`empacotamento/`**: `bussola.spec` (PyInstaller **onedir**, `console=False` no executável
  principal, `upx=False`, exclusões de módulos Qt não usados, `hiddenimports` do argon2),
  `versao_info.txt` (metadados do `.exe`), `entrada.py` (ponto de entrada congelado com
  `freeze_support` e AppUserModelID), `gerar_icone.py` + `bussola.ico` (ícone 16→256 px desenhado
  com QPainter, sem dependência externa), `instalador.iss` (Inno Setup 6, instalação por usuário,
  não apaga a base ao desinstalar), `AVISO.txt`, `LEIA-ME.txt` e `build_windows.ps1` (build completo
  em um comando).
- **`BussolaPDV-console.exe`**: segundo executável, com console, para diagnosticar quando a versão
  sem janela falha em silêncio.
- **Workflow `.github/workflows/windows.yml`** (`windows-latest`): testes, lint, ícone, PyInstaller,
  teste de fumaça do executável, Inno Setup e publicação do `.zip` portátil e do `setup.exe` como
  artefato.
- **`python -m bussola_pdv`** como alternativa ao script instalado.
- Testes novos: primeiro uso (criação, validações, senha curta, base corrompida) e empacotamento
  (versões sincronizadas, `.ico` válido, arquivos referenciados, caminhos por sistema, workflow).

### Alterado

- `pyproject.toml`: extra `empacotamento` (`pyinstaller`), versão 0.4.0 e `bussola-pdv` apontando
  para `ui.entrada:main`.
- `README.md`: seção **Instalação** reescrita para Windows (instalador pronto, rodar do código,
  compilar) com tabela de pacotes e link para o guia completo.

### Verificado

- Build de fumaça da receita PyInstaller em Linux: binário congelado rodou `demo`, `info` e
  `--version` com a base íntegra. O teste revelou que as migrações `.sql` não entravam no bundle
  (`no such table: usuarios`); as `datas` do spec foram corrigidas e ganharam teste de regressão.

### Limites desta versão

- `BussolaPDV.exe`, o instalador e o `.zip` **não** foram gerados no ambiente de desenvolvimento
  (Linux, sem Windows/Wine). Saem do workflow `windows.yml` ou de uma máquina Windows via
  `empacotamento/build_windows.ps1`. O caminho `.msi` (WiX) está descrito, mas não automatizado.
- Sem assinatura digital: SmartScreen avisa na primeira execução (documentado).

## [0.3.0] — 2026-11-11 — pré-alfa: interface no padrão AdminLTE

### Adicionado

- **Casca nova** (`ui/widgets.py`) com a linguagem visual do AdminLTE: `BarraLateral` (marca, painel
  do usuário, navegação com ícones, recolher para 62 px), `BarraSuperior` (botão de recolher, título,
  chip do usuário), `CabecalhoConteudo` (título + trilha), `Cartao`, `CaixaInfo` (*small-box*),
  `Selo` (*badge*), `Rodape` e `PilhaDePaginas`.
- **21 ícones SVG próprios** (`ui/icones.py`), coloridos em tempo de execução e cacheados; nenhum
  arquivo de terceiros, nenhuma dependência de rede.
- **Indicadores por tela**: PDV (itens, desconto, situação do pagamento), Caixa (fundo, esperado,
  movimentos), Produtos (ativos, sem estoque, abaixo do mínimo), Vendas (cupons, faturamento, ticket).
- **Cartões** em Produtos, Vendas, Auditoria e Fechamento, com ferramentas no cabeçalho.
- **Skin padrão do AdminLTE** (azul `#0D6EFD`, sidebar `#343A40`, fundo `#F4F6F9`), presets
  GRAFITE/ESMERALDA/NOTURNO recalibrados e preset novo **OCEANO**; tela de tema com nomes de papel
  atualizados.
- **Login em cartão** (`login-box`), com faixa da marca, rodapé e versão real.
- `docs/INTERFACE.md`: tokens, componentes, ícones, regras e capturas; ADR-016 com a decisão e o
  enquadramento de licença.

### Alterado

- `ui/janela.py` e `ui/admin/janela.py` reconstruídos sobre a casca; a área administrativa usa a mesma
  sidebar, ganhou trilha de navegação e o botão "Voltar ao PDV".
- Títulos internos duplicados das seções administrativas foram removidos — o cabeçalho de conteúdo é
  a única fonte do título.
- Tabelas não inflam mais o layout (`AdjustIgnored`), então a tela não passa a rolar ao receber linhas;
  a área de conteúdo deixou de usar `QScrollArea` (cada tela rola o que precisa).
- Cores de status em tabelas vêm da paleta (`sucesso`/`alerta`/`erro`), não de constantes do Qt.

### Corrigido

- Retorno de módulo alto (ex.: Auditoria) não deixava mais a barra de rolagem presa nas outras telas.
- Colunas apertadas em Caixa e Auditoria (tipo, data e ação truncados).
- Ícone sem cor herdava cinza sobre fundo escuro e desaparecia na sidebar.

### Testes

- `tests/test_ui_adminlte.py` (27 testes): ícones (cor, tamanho, cache, nome inválido), widgets,
  recolher da sidebar, trilha, pilha por página, folha de estilo e casca da janela.
- Total: **381 testes**, 80% de cobertura; 15 capturas em `docs/capturas/`.

## [0.2.0] — 2026-11-11 — pré-alfa: administração, marca e hierarquia

### Adicionado

- **Hierarquia de cinco perfis**: `ATENDENTE` (20) < `CONTABILIDADE` (30) < `GERENTE` (40) <
  `ADMIN` (70) < `ADMIN_MASTER` (100). Cada perfil tem nível numérico; quem está acima gerencia quem
  está abaixo, ninguém gerencia par ou superior e ninguém altera o próprio acesso.
- **Matriz de permissões editável** (`permissoes_perfil`): ~30 ações por perfil, exclusiva do Admin
  Master (`PERMISSAO_GERENCIAR`), com efeito imediato, auditoria antes/depois e botão de restaurar o
  padrão. A coluna do master é integral e intocável.
- **Master único**: índice parcial garante no máximo um `ADMIN_MASTER` ativo; criar outro é recusado e
  a troca exige *transferência de propriedade* (auditada).
- **Área administrativa** (`ui/admin/`, menu Administração, `bussola ui --admin`): seis seções —
  Visão geral, Marca e tema, Usuários, Perfis e permissões, Parâmetros, Manutenção — filtradas pelo
  que o perfil pode acessar. Contabilidade e Atendente recebem autorização negada.
- **Marca da loja personalizável**: nome fantasia, razão social, CNPJ (validação numérica e
  alfanumérica), telefone, endereço, rodapé do comprovante e logo PNG, persistidos em `parametros`
  sob `marca.` e aplicados na janela, no título e no cupom interno.
- **Tema personalizável**: paleta de 13 cores + fonte, presets BÚSSOLA/GRAFITE/ESMERALDA/NOTURNO,
  edição cor a cor (tema personalizado), prévia com contraste WCAG AA calculado e folha de estilo
  gerada em tempo de execução — vale para PDV, caixa, consultas e área administrativa.
- **Diagnóstico de dependências real**: Python, PySide6/Qt, Argon2id, SQLite, versão do esquema vs.
  migrações disponíveis, `integrity_check`, `foreign_keys`, WAL, `synchronous`, espaço livre, tamanho
  real da base (páginas + WAL) e contagens; cada linha classificada em OK/Atenção/Erro.
- **Manutenção**: cópia de segurança pela API do SQLite com verificação imediata do arquivo,
  listagem das cópias, verificação de integridade e da cadeia de auditoria, otimização (`VACUUM`) e
  **restauração exclusiva do master**, que valida a cópia, recusa esquema mais novo e guarda ao lado
  uma cópia do estado anterior.
- **Perfil Contabilidade**: leitura de relatórios, fechamentos, títulos e auditoria; sem vender,
  cancelar, sangrar ou alterar cadastros.
- **Migração `0003_hierarquia_e_permissoes.sql`**: recria `usuarios` (CHECK novo) convertendo
  `OPERADOR → ATENDENTE` e `ADMINISTRADOR → ADMIN`, preservando ids, hashes e datas, com
  `foreign_key_check` e reativação das FKs; cria `permissoes_perfil`, índice do master e trigger que
  bloqueia `DELETE` de usuário.
- **CLI**: `init` cria o Admin Master (senha com política de 8+ caracteres); `demo` cria os cinco
  perfis; `ui --admin` abre direto a área administrativa.
- **Testes**: 354 (antes 223), 79% de cobertura total. Novos: hierarquia/permissões (41),
  marca/tema (31), administração/manutenção/backup (23), migração da hierarquia (7) e UI
  administrativa offscreen (29).

### Alterado

- `Perfil.OPERADOR` e `Perfil.ADMINISTRADOR` viram apelidos de classe de `ATENDENTE` e `ADMIN`
  (não são valores válidos ao construir o enum; bancos antigos passam pela migração).
- A criação de usuário passou a exigir nível superior ao do novo usuário e recusa criar master.
- Massa de demonstração com cinco logins (`master`, `admin`, `gerente`, `contabilidade`,
  `operador`), todos recarregados com as permissões efetivas.
- Documentação: README com hierarquia, área administrativa e capturas novas; ADR-013 (matriz do
  master), ADR-014 (marca/tema como parâmetros), ADR-015 (diagnóstico calculado); 14 capturas.

### Segurança

- Nenhuma rota de autoelevação: trocar o próprio perfil, redefinir a própria senha por atalho
  administrativo ou desativar a si mesmo é recusado.
- Revogação de permissão vale na próxima abertura da área administrativa (o usuário da sessão é
  recarregado antes de construir a janela).
- A restauração de cópia é a única operação que sobrescreve o banco: exige master, valida a cópia e
  registra o evento com o caminho do estado anterior.

## [0.1.0] — 2026-11-11 — pré-alfa

Primeira entrega executável derivada da especificação `davidcreator/bussolapdv`.

### Adicionado

- **Núcleo de domínio**: dinheiro em centavos inteiros, percentual em pontos-base, quantidade
  escalonada, arredondamento único meio-para-cima (`dominio/dinheiro.py`).
- **Venda**: carrinho com consolidação por produto, descontos por item/cupom, política de desconto
  por perfil, verificação de estoque (`dominio/venda.py`).
- **Pagamentos**: até três formas, troco restrito a dinheiro, PIX/cartão como `PENDENTE`,
  configuração de taxa e prazo (`dominio/pagamentos.py`).
- **Caixa**: turno, movimentos de gaveta, esperado, contagem por denominação, classificação de
  diferença (`dominio/caixa.py`).
- **Crediário**: parcelas com trava de fim de mês, resíduo na primeira parcela, saldo, aging
  (`dominio/crediario.py`).
- **Estoque**: movimentos assinados, saldo, status, rateio de frete com soma exata
  (`dominio/estoque.py`).
- **Auditoria** append-only com encadeamento SHA-256 (`dominio/auditoria.py`).
- **Segurança**: Argon2id, política de senha/PIN, bloqueio por tentativas
  (`dominio/seguranca.py`), perfis e permissões por ação (`dominio/usuario.py`).
- **Validação de documentos**: CPF, CNPJ numérico e alfanumérico (IN RFB 2.229/2024), EAN-8/13/14.
- **Persistência**: SQLite com WAL, `foreign_keys`, `synchronous=FULL`, migrações versionadas
  (v1 e v2), triggers de imutabilidade, índices de relatório.
- **Casos de uso**: finalizar venda (atômica + idempotente), cancelar venda com estorno, abrir/fechar
  turno, sangria/suprimento, receber título, registrar entrada de fornecedor, ajustar estoque,
  fechamento com snapshot, dashboard.
- **Backup** consistente pela API do SQLite com verificação de integridade.
- **Interface PySide6**: tema grafite/turquesa/âmbar, login, PDV com atalhos, caixa, produtos,
  vendas com cancelamento, fechamento e auditoria; módulos não prontos são identificados.
- **CLI** com `init`, `demo`, `info`, `backup`, `fechamento`, `ui`, `relogio`.
- **Massa de demonstração fictícia**: 16 produtos, 5 clientes, entrada de fornecedor, 16 vendas em
  3 dias, venda cancelada, crediário em 3 parcelas e turno aberto.
- **Testes**: 223 testes (unidade, integração com SQLite real, falha injetada, idempotência,
  concorrência de turno, auditoria, backup/restore, massa de demonstração e UI offscreen) — 77% de
  cobertura total, 88–100% nos módulos de domínio. `ruff` e `mypy --strict` sem apontamentos.
- **CI** (GitHub Actions) com `ruff`, `mypy` e `pytest` em Python 3.12/3.13 com Qt offscreen.
- **Documentação**: análise do repositório de origem, ADRs, plano de implementação e capturas de tela.

### Organização

- Repositório **único** (`bussolapdv`): código em `src/`, testes em `tests/`, documentação vigente em
  `docs/` e material histórico em `prototipo/especificacao/` (especificação, planilhas, VBA e scripts
  de build), com `prototipo/README.md` explicando o que é e o que não é fonte de verdade.
- `.gitignore` ignora planilhas e bases em geral, com exceção explícita para o protótipo preservado.

### Decisões registradas

- ADR-001 a ADR-012 em `docs/DECISOES.md` (dinheiro inteiro, WAL, turno único por caixa,
  idempotência, auditoria com hash, pagamento pendente, autorização autenticada, crediário sem
  encargos, UUID + cupom transacional, UTC + data comercial, imutabilidade, UI sem regra).

### Pendente (não incluído)

- Emissão fiscal, integração TEF/adquirente, multi-caixa em rede.
- Telas de clientes, crediário, estoque, entradas e parâmetros.
- Devolução parcial, PDF do fechamento, importação da planilha protótipo, empacotamento Windows.
- Política de encargos, revisão LGPD, homologação com operador real.
