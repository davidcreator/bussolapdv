# Changelog

Formato inspirado em Keep a Changelog; versionamento semântico a partir de releases executáveis.

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
