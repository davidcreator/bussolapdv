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
| Instruções / Dashboard gráfico | Pendentes |

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

## Próximos incrementos sugeridos (ordem)

1. Telas de clientes, crediário e estoque (a API já existe).
2. Devolução parcial de venda com recomposição de pagamento.
3. Geração de PDF do fechamento (Qt PrintSupport).
4. Importação validada da planilha protótipo (pré-visualização + relatório de erros).
5. Empacotamento Windows com versões fixadas e hashes.
6. Revisão de segurança/LGPD e homologação com operador real.
