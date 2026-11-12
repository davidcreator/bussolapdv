# Changelog

Formato inspirado em Keep a Changelog; versionamento semântico a partir de releases executáveis.

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
