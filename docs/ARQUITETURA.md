# Arquitetura proposta

> **Projeto:** Bússola Sistema PDV Open Source

**Estado: especificação; não implementada.**

## Contexto e limites
Uma aplicação desktop opera offline em um único computador. SQLite local é o registro autoritativo, com integridade referencial ativada em todas as conexões e transações explícitas. Não suportar simultaneidade entre computadores via arquivo compartilhado. Multiestação requer serviço central, protocolo, banco e plano de falhas próprios; não faz parte da primeira versão.

## Camadas
- Interface Qt: formulários, filtros, acessibilidade, visualização e notificações; sem regras financeiras em widgets.
- Aplicação: casos de uso, autorização, coordenação de transação, idempotência e respostas de erro.
- Domínio: regras de venda, valores, estoque, caixa, crediário, política de arredondamento e eventos.
- Infraestrutura: repositórios SQL, migrações, relógio, IDs, criptografia de backup, exportação e leitura de planilha.
- Testes: domínio isolado; integração com SQLite temporário; testes UI e falhas.

## Esboço de entidades e relacionamentos
| Entidade | Identificador / vínculo | Observações |
|---|---|---|
| Usuario, Perfil, Permissao | usuario_id, perfil_id | credenciais com hash robusto; autorização por ação |
| Cliente | cliente_id | documento validado quando fornecido; nome não é chave |
| Produto | produto_id, SKU, EAN | unicidade definida por domínio; custo/preço atual não substituem histórico |
| Caixa, Turno | caixa_id, turno_id | uma sessão aberta por caixa, restrição transacional |
| Venda, ItemVenda | venda_id, item_id | valores históricos; cada item vinculado à venda |
| Pagamento | pagamento_id, venda_id | forma, entregue, aplicado, troco, estado, referências externas |
| MovimentoCaixa | movimento_caixa_id, turno_id | venda/recebimento e suprimento/sangria ligados por IDs |
| MovimentoEstoque | movimento_estoque_id, produto_id | quantidade assinada, origem, evento de correlação |
| Entrada, EntradaItem | entrada_id, item_id | fornecedor, documento, frete rateado por item |
| Titulo, Parcela | titulo_id, parcela_id, cliente_id, venda_id | vencimento, principal, encargos conforme política |
| Recebimento, Alocacao | recebimento_id, parcela_id | parcial, estorno, data, forma e caixa/turno |
| AuditoriaEvento | evento_id, correlacao_id | append-only na aplicação; antes/depois e autorização |
| FechamentoSnapshot | fechamento_id, versão | período, filtros, valores, reabertura auditada |
| Migracao | versão | aplicação ordenada e reversibilidade planejada |

O esquema definitivo deve definir tipos, `NOT NULL`, `CHECK`, chaves únicas, exclusões proibidas, índices por data/status/cliente, integridade monetária e migrations testadas. UUID ou IDs de outra estratégia devem ser escolhidos e documentados; números de cupom sequenciais precisam de geração transacional.

## Transações e recuperação
Na finalização, validar novamente sessão, estoque, crédito, soma de pagamentos e permissões dentro da transação. Criar venda, itens, saídas, pagamentos, parcelas e auditoria conjuntamente. Se qualquer gravação falhar, rollback de todas. Uma chave de idempotência deve evitar repetição em tentativas após falha ou duplo clique. Cancelamento/devolução usa eventos compensatórios, não exclusão. Testar falhas em cada etapa e retomada após encerramento abrupto.

## Precisão e tempo
Centavos inteiros para dinheiro, escala inteira documentada por produto para quantidade. Política de arredondamento por item/total, rateio residual e impostos deve ser configurada e testada. Instantes em UTC; datas comerciais e fuso da loja explícitos; horário local pode variar por regras históricas. Não substituir horários históricos por `now()` em consultas.

## Risco e decisões pendentes
Autenticação offline e segurança física, limitação de tentativas, criptografia de backup/segredos, política de estoque negativo, juros e multa, cartão e conciliação, emissor fiscal, política de retenção e controle de privacidade dependem de decisões do responsável e revisão especializada. Apenas SQLite local não impede adulteração por administrador do computador.
