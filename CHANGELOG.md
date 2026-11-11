# Changelog

Formato inspirado em Keep a Changelog; versionamento semântico a partir de releases executáveis.

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
