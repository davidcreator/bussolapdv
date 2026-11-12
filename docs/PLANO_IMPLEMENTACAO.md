# Plano de implementação e estado real

Correspondência entre a sequência de 10 etapas do `PROMPT_MESTRE_PYTHON.md` e o que existe neste
repositório. **Nada é marcado como pronto sem teste executado.**

| Etapa do prompt mestre | Estado | Evidência |
|---|---|---|
| 1. Esqueleto, CI e banco com migrações | **Implementado e testado** | `pyproject.toml`, `.github/workflows/ci.yml`, `infra/sqlite/migracoes/`, `tests/test_persistencia_seguranca.py` |
| 2. Autenticação, permissões, parâmetros, produtos e clientes | **Implementado e testado** | `dominio/seguranca.py`, `dominio/usuario.py` (5 perfis), `aplicacao/autenticacao.py`, `aplicacao/permissoes.py`, telas administrativas de usuários/permissões/parâmetros, cadastros de produto/cliente + telas de produtos |
| 3. Estoque e entradas de fornecedor | **Parcial** | movimentos assinados, saldo, rateio de frete, entrada transacional e testes; **sem tela de entradas** e sem importação de XML de NF-e |
| 4. Caixa por turno e frente PDV | **Implementado e testado** | `aplicacao/caixa.py`, `aplicacao/pdv.py`, telas de caixa e PDV, testes de atomicidade e idempotência |
| 5. Pagamentos divididos, cartão/PIX e recebíveis | **Parcial** | split de 3 formas, troco, status pendente/confirmado e relatório de pendências; **sem integração TEF/adquirente** e sem recebíveis detalhados |
| 6. Crediário, parcelas, pagamentos parciais, limites | **Implementado e testado** | `dominio/crediario.py`, `aplicacao/crediario.py`, aging, limite e atraso; **sem tela própria** (aparece em fechamento) |
| 7. Cancelamentos, devoluções e auditoria append-only | **Parcial** | cancelamento com estorno e trilha com hash; **devolução parcial de itens não implementada** |
| 8. Fechamento, dashboard e PDF | **Parcial** | fechamento do dia com snapshot versionado + dashboard em texto/dados; **sem PDF e sem gráficos** |
| 9. Backup/restore, migração de dados e empacotamento | **Parcial** | backup consistente com verificação, restauração testada e expostos na tela de manutenção; **sem empacotamento** e sem importação de planilha |
| 10. QA, revisão de segurança/licenças/fiscal e homologação | **Não iniciado** | depende das decisões pendentes (`docs/DECISOES.md`) |

## Módulos da especificação

| Módulo | Estado |
|---|---|
| PDV | Funcional (carrinho, código/EAN, desconto, split, troco, autorização, atalhos) |
| Caixa | Funcional (abrir, sangria, suprimento, contagem, fechar) |
| Produtos | Consulta e indicadores funcionais; cadastro pela API (tela de cadastro pendente) |
| Vendas | Histórico e cancelamento funcional |
| Fechamento | Funcional em tela e snapshot; PDF pendente |
| Auditoria | Consulta e verificação de cadeia funcionais |
| Clientes | CRUD na API; tela pendente |
| Crediário | Recebimento na API e consulta; tela pendente |
| Estoque | API e consulta de saldos; tela de movimentos pendente |
| Entradas | API funcional; tela pendente |
| Parâmetros | Tela administrativa com faixa por parâmetro (admin) |
| Administração | Funcional: diagnóstico, marca/tema, usuários, matriz de permissões, manutenção |
| Instruções / Dashboard gráfico | Pendentes (a casca e os indicadores por tela já existem) |

## Evidências da entrega administrativa

- `tests/test_hierarquia_permissoes.py` (41 testes): níveis, `pode_gerenciar`, `pode_receber_perfil`,
  concessão/revogação auditada, master único, autoelevação recusada, DELETE bloqueado por trigger.
- `tests/test_marca_tema.py` (31): paletas, contraste WCAG AA, presets, validação de CNPJ/logo,
  ida-e-volta por parâmetros, auditoria de marca e de tema, folha de estilo gerada.
- `tests/test_administracao.py` (23): diagnóstico real, integridade, cópia verificada, cópia corrompida
  recusada, restauração exclusiva do master e cópia do estado anterior.
- `tests/test_migracao_hierarquia.py` (7): migração `0003` com venda/turno apontando para usuário,
  `foreign_key_check` limpo, triggers e índice recriados, CHECK novo aceitando só os cinco perfis.
- `tests/test_ui_admin.py` (29): seções por perfil, matriz intocável na coluna do master, criação de
  usuário pela tela, edição de parâmetro, tema aplicado na janela principal e perda de acesso na sessão.

## Evidências da entrega de interface

- `tests/test_ui_adminlte.py` (27): ícones (cor, tamanho, cache, nome inválido), `Cartao`,
  `CaixaInfo`, `Selo`, `BarraLateral` (recolher, sinais, identidade), `BarraSuperior`,
  `PilhaDePaginas` (altura por página), folha de estilo (cartões, paleta, contraste) e casca da janela.
- `docs/INTERFACE.md`: tokens de cor, componentes, ícones, regras e capturas.
- 15 capturas em `docs/capturas/`, geradas offscreen por `make capturas`.

## Evidências da entrega de exportação (v0.5.0)

- `tests/test_exportacao.py` (41): modelo (`Relatorio`/`Tabela`/`Coluna`, validações, nome de arquivo,
  slug, tipos), formatação pt-BR (moeda, centavos→reais sem resíduo, data ISO→BR), escritor `.xlsx`
  (partes do pacote, **leitura por openpyxl** conferindo moeda como número, data como data, texto
  escapado, aba saneada/única, filtro automático, painel congelado, larguras, planilha vazia),
  escritor `.pdf` (**leitura por pypdf**: `%PDF`, `%%EOF`, título, rodapé `página X de Y`, 400 linhas
  em várias páginas, escape de HTML), serviço (valores iguais aos da tela, permissão negada para
  atendente, contabilidade exporta, evento `DADOS_EXPORTADOS`, cadeia de hashes íntegra, loja/CNPJ no
  cabeçalho, aviso fiscal em todos os relatórios) e CLI (sucesso em PDF, nome sugerido em pasta,
  senha errada, perfil sem permissão, falta de `--data`, banco inexistente).
- `tests/test_ui_exportacao.py` (13): menu com os dois formatos, botão oculto para atendente,
  exportação gravando arquivo e emitindo sinal, extensão corrigida, cancelamento sem arquivo, as
  quatro telas com o botão, fechamento exportando o dia escolhido e catálogo respeitando a busca.
- `docs/EXPORTACAO.md` + exemplos versionados (`docs/exemplos/fechamento-exemplo.pdf` e `.xlsx`,
  gerados por `ferramentas/gerar_exemplos.py` a partir de `bussola demo`).

## Evidências da entrega de instalação Windows (v0.4.0)

- `tests/test_primeiro_uso.py` (10): detecção de base ausente/vazia/pronta/arquivo corrompido;
  diálogo cria Admin Master, `Caixa 1` e nome da loja pelos casos de uso do `init`; senhas divergentes,
  campos vazios e senha curta recusados sem deixar base criada.
- `tests/test_empacotamento.py` (21): versão de `versao_info.txt`, `pyproject.toml` e `instalador.iss`
  sincronizadas com `__version__`; `.ico` com 7 resoluções e PNGs válidos; spec aponta para arquivos
  existentes; `.iss` só referencia arquivos reais e não apaga dados na desinstalação; workflow publica
  `.zip` e `setup.exe`; diretório de dados por sistema (`LOCALAPPDATA`, `XDG_DATA_HOME`, `BUSSOLA_DADOS`);
  `bussola-pdv` com argumento devolve o controle ao CLI.
- **Build de fumaça real** (Linux, mesma receita do spec): `python -m PyInstaller empacotamento/bussola.spec`
  produziu um binário congelado que executou `demo` (base criada), `info` (esquema v3, integridade OK,
  cadeia de auditoria íntegra em 42 eventos) e `--version`. O teste pegou um defeito real: as migrações
  `.sql` não estavam no bundle e o executável falhava com `no such table: usuarios` — corrigido em
  `datas` do spec, com teste de regressão.
- `docs/INSTALACAO_WINDOWS.md`: três caminhos (instalador, código, build), pacotes pip por extra,
  pasta de dados, backup/restauração, SmartScreen, desinstalação, problemas comuns e checklist.
- **Não verificado**: binário Windows (`.exe`), instalador `.iss` compilado e instalação em Windows real
  — exigem runner `windows-latest` (workflow `windows.yml`) ou máquina Windows.

## Próximos incrementos sugeridos (ordem)

1. Telas de clientes, crediário e estoque (a API já existe; o crediário já exporta pela API/CLI).
2. Devolução parcial de venda com recomposição de pagamento.
3. Geração de PDF do fechamento (Qt PrintSupport).
4. Importação validada da planilha protótipo (pré-visualização + relatório de erros).
5. Assinatura digital dos binários Windows e hashes publicados na Release.
6. Revisão de segurança/LGPD e homologação com operador real.
