# PROMPT MESTRE — Bússola Sistema PDV Open Source

**Nome oficial do projeto:** Bússola Sistema PDV Open Source.

## Papel e missão
Atue como equipe sênior de arquitetura, desenvolvimento Python desktop, engenharia de dados, segurança, UX e QA. Implemente o **Bússola Sistema PDV Open Source**, um PDV varejista desktop offline, em português do Brasil, a partir desta especificação e dos documentos do repositório. Entregue código executável, testes e documentação — não somente protótipos. Não apresente nada como pronto para produção antes de cumprir os critérios de liberação. Não finja executar testes, auditorias ou integrações.

## Modo de trabalho
1. Inspecione o repositório, confirme o ambiente e mantenha uma lista de decisões e riscos. Antes de decisões comerciais, legais ou de segurança não especificadas, pergunte ao responsável; quando for possível, aplique a opção conservadora e documente-a.
2. Trabalhe em incrementos verificáveis com testes e migrações. Registre mudanças em CHANGELOG.md. Não apague dados históricos e não quebre retrocompatibilidade sem migração e documentação.
3. Em cada entrega, informe alterações, arquivos, comandos efetivamente executados, resultados, limitações e próximos passos. Diferencie implementado, testado, pendente e não aplicável.
4. Se houver conflito entre a planilha protótipo e estas regras, priorize integridade, rastreabilidade e segurança; documente o conflito. Não reproduza limitações de intervalos fixos, lançamentos manuais duplicados ou fórmulas que tratem cálculos como confirmação de pagamento.

## Escopo técnico e implantação
- Python 3.12 ou superior; PySide6/Qt Widgets para Windows desktop, UI em pt-BR. A aplicação deve iniciar sem acesso à internet e guardar dados localmente. Linux/macOS são opcionais e somente declarados suportados após CI e testes reais.
- SQLite em arquivo local por instalação, com chaves estrangeiras ligadas, migrações versionadas, WAL quando apropriado e transações explícitas. Um único computador pode ter vários operadores e caixas configurados, mas não prometa vendas simultâneas em vários computadores via compartilhamento de arquivo. Uma versão futura multiestação pode usar serviço local e banco servidor, com protocolo e testes próprios.
- Separar interface, aplicação/casos de uso, domínio, persistência e relatórios. Lógica de negócio não pode ficar em handlers de interface. Injetar relógio e dependências para testes.
- Dinheiro em centavos inteiros; quantidade em unidades inteiras escalonadas conforme precisão do produto, e taxas representadas de forma exata. Use Decimal apenas com conversões e arredondamentos explícitos; nunca `float` para valores financeiros. Datas de negócio sem hora separadas de instantes em UTC; apresentar horário de America/Sao_Paulo conforme configuração. Registro histórico não muda com recálculo.
- PySide6, SQLite, empacotamento e todas as bibliotecas precisam ter licenças, notices e obrigações de redistribuição revisadas. Projeto GPL-2.0-or-later; não inclua ativos com direitos desconhecidos.

## Interface e acessibilidade
Identifique a aplicação pelo nome oficial **Bússola Sistema PDV Open Source**; use uma marca provisória tipográfica até que o responsável forneça ou aprove um logotipo. Use como referência visual os protótipos: faixa superior grafite, faixa secundária turquesa, rótulos claros, áreas de entrada em amarelo suave com borda de destaque, células calculadas em cinza e mensagens explícitas. Não copie logotipos de terceiros; forneça espaço para marca do usuário. Aplique tipografia legível, contraste adequado, foco visível, ordenação por teclado, navegação Tab/Enter e suporte a leitores de tela quando viável. Não dependa apenas de cor. Componentes responsivos ao redimensionamento e DPI alto.

Módulos de navegação: Instruções, Parâmetros, Produtos, PDV, Vendas, Itens, Caixa, Pagamentos, Fechamento, Crediário, Clientes, Movimentos de estoque, Entradas, Dashboard e Auditoria. Listas configuráveis ficam em administração, não devem ser editáveis sem autorização. Exiba diferenças e erros com mensagens que orientem correção. Os atalhos F2/F4/F5/F6/F7/F8 só devem ser documentados após implementação e testes; confirme conflitos do sistema.

## Usuários, permissões e segurança
- Perfis operador, gerente e administrador, com permissões explícitas por ação. Abrir/fechar caixa, suprimento, sangria, desconto excepcional, venda com estoque insuficiente, cancelamento e ajuste exigem políticas configuráveis e autorização rastreável.
- Senhas/PINs nunca em texto simples; use derivação de senha moderna e adequada, como Argon2id, com salt aleatório, parâmetros documentados e limitação de tentativas apropriada. A aprovação exige autenticação do aprovador; não basta digitar seu nome. Não armazene credenciais em logs.
- Crie trilha de auditoria append-only no modelo da aplicação, com ID, UTC e horário local, ator autenticado, ação, entidade, antes/depois quando pertinente, motivo, autorizador, origem e correlação da operação. Cancelar ou corrigir gera novo evento. SQLite local não é imutável contra administrador do sistema: documente limitação e considere verificação de integridade, cópias externas e auditoria externa.
- Minimize dados pessoais; acesso por perfil, mascaramento, retenção, backup seguro e documentação LGPD. Criptografia de backups e proteção de chaves devem ser definidas e testadas; não prometa criptografia em repouso do banco SQLite padrão.

## Modelo de dados mínimo
Projetar esquema relacional com IDs imutáveis, restrições, índices, valores históricos e migrações; detalhar em `docs/ARQUITETURA.md`:
1. empresa/configurações, usuários, perfis, permissões e autorização;
2. clientes com identificador estável e documento opcional validado; permitir homônimos, sem deduplicar por nome; suportar CPF e CNPJ numérico e alfanumérico conforme especificação vigente, sem alegar verificação oficial de titularidade;
3. produtos com SKU e código de barras únicos por domínio, nome, categoria, unidade, custo, preço, mínimo, ponto de pedido, ativo, fornecedor e identificador fiscal opcional;
4. caixas físicos, turnos, movimentações de gaveta, contagem por denominação e conferência;
5. venda/cupom, itens com preço, custo e desconto congelados, pagamentos com valores entregues, aplicados, troco, taxas e estado;
6. movimentações de estoque com sinal, motivo, origem, documento e ID de correlação; compras com nota e itens, rateio de frete e custo histórico;
7. títulos e parcelas de crediário, recebimentos parciais e reversões, regras de juros/multa e histórico de renegociação;
8. eventos de auditoria, versões do esquema, fechamento diário com snapshot e backups.

Não armazenar CVV, dados sensíveis completos de cartão, credenciais bancárias ou comprovantes sem necessidade e política expressa. IDs externos PIX/NSU são referências, não prova de recebimento.

## Regras funcionais obrigatórias
### Produtos e estoque
Cadastros com validação, códigos em texto e unidades; saldo = saldo inicial + movimentos assinados válidos, sem duplicar entradas. Sem venda que exceda estoque salvo autorização gerencial explícita e auditada. Calcule ruptura (saldo <= 0), baixo (saldo positivo <= mínimo), reposição e OK, respeitando configuração. Permita ajustes, perdas, devoluções e transferências com rastreabilidade. Calcule custo em estoque, giro, cobertura e curva ABC documentando período, estoque médio, empates, itens sem vendas e devoluções. Não use valores atuais para reconstruir custos históricos.

### PDV
Operador autenticado, caixa/turno aberto e carrinho não vazio. Busca por SKU ou leitor EAN; tratamento explícito de colisões e código inexistente. Múltiplos itens, quantidades fracionadas conforme unidade, desconto por item e no cupom, limite de desconto e autorização. Total calculado por política única de arredondamento. Apresente estoque, subtotal, descontos, acréscimos, total, pagamentos e troco. Venda não finaliza sem cobertura completa, permissões, estoque e crédito verificados no momento da transação. Finalização grava venda, itens, pagamentos, saídas, títulos e evento de auditoria em uma transação atômica; erro deixa tudo inalterado. Prevenir duplo clique e repetição por chave de idempotência.

### Pagamentos
Até três formas por venda: dinheiro, débito, crédito à vista/parcelado, PIX, transferência, vale, cheque e a prazo quando implementados. Registrar valor entregue, aplicado e troco separadamente. Troco não pode exceder dinheiro recebido; soma dos valores aplicados deve ser igual ao total, em centavos. Registrar NSU/bandeira e referência de forma minimizada; não classificar pagamento como confirmado apenas por preenchimento de campos. Definir status, taxas contratuais, D+ de recebimento e repasse de taxa antes da implementação; distinguir parcelas de cartão, recebível da adquirente e dívida de cliente. Sem integrações externas, comprovação é manual e deve ser explicitamente marcada como tal.

### Caixa
Um turno aberto por caixa físico, garantido no banco de dados e em transação. Abertura com fundo; movimentações individuais de sangria/suprimento e recebimentos de títulos; exigência de motivo e autorização conforme política. Esperado da gaveta = fundo + vendas em dinheiro aplicadas + recebimentos de títulos em dinheiro + suprimentos − sangrias − estornos em dinheiro. Contagem por denominação; diferença = contado − esperado. Sinalize zero, até R$ 5 e acima de R$ 5 como política configurável. Cartões, PIX e crédito não são dinheiro físico. Ao fechar, registrar conferente, horário, motivo de diferença e snapshot; bloquear edições retroativas via fluxo de correção auditado.

### Crediário
Um título por parcela, cliente por ID e vencimento explícito; parcelas geradas em periodicidade configurável com datas válidas para fim de mês. Recebimentos parciais geram eventos por data e forma; saldo e recebimentos de caixa são atualizados atomicamente, sem contar novamente como venda. Bloquear crédito se limite disponível insuficiente ou atraso exceder política, salvo autorização apenas se a empresa permitir. Juros, multa, arredondamento, pagamentos parciais e renegociação requerem política parametrizada explícita, exemplos e testes; não inventar encargos. Aging e inadimplência devem ter denominador e data de referência documentados.

### Cancelamento e devolução
Não apagar cupons nem sobrescrever valores: registrar status e eventos inversos, com motivo e autorizador. Estornar estoque, títulos, pagamentos e caixa de modo consistente, incluindo valores já recebidos e situações que exigem reembolso manual. Bloquear ou tratar cada caso com segurança quando não for possível reverter automaticamente.

### Entradas de fornecedor
Cada item tem quantidade, custo, documento e fornecedor. Ratear frete por critério escolhido (por valor, quantidade ou manual) e garantir que a soma alocada em centavos corresponda ao frete total, com regra de distribuição de centavos. Gerar movimento de estoque uma única vez e custo histórico por transação. Evitar notas e documentos duplicados conforme chave comercial validada; permitir exceção auditada. Preço sugerido deve declarar se é markup sobre custo ou margem sobre venda; nunca alterar preço automaticamente sem autorização.

### Fechamento e dashboard
Relatórios por período, operador, turno, status e forma sem duplicar vendas com split. Soma de pagamentos aplicados de vendas concluídas deve conciliar com totais das vendas, ressalvados estados pendentes explicitamente mostrados. Destacar órfãos, diferenças, duplicidades, falhas de fonte e filtros divergentes; não classificar igualdade aritmética como confirmação bancária. Fechamento diário: resumo, formas, operadores/turnos, dinheiro esperado/contado, prazo, produtos, categorias, estoque, ocorrências e assinaturas. Criar snapshot/versionamento com controle de reabertura, PDF local e auditoria. Dashboard com filtros e indicadores, gráficos gerados localmente, origens/intervalos claros e comparações definidas. Indicadores de estoque e crediário correntes devem deixar explícito se ignoram filtros.

## Importação opcional do Excel protótipo
Permita somente importação explícita de `.xlsx`, sem executar VBA e sem confiar em valores calculados sem recálculo. Pré-visualizar, mapear campos e versões, validar cabeçalhos, códigos, datas, totais, sinais, duplicidades e documentos; identificar registros de teste. Oferecer execução simulada e relatório de erros. Efetivar transacionalmente após confirmação, com backup anterior e arquivo de relatório. Nunca sobrescrever base de produção silenciosamente. Não interpretar dados mascarados, planilhas ocultas ou células de fórmula como fonte confiável sem validação.

## Operação e distribuição
- Backup consistente usando API apropriada do SQLite, incluindo transações, teste de integridade e restauração efetiva em diretório isolado. Rotação, recuperação de falhas, proteção de segredos e plano de retenção documentados. Desligamento e queda de energia não podem produzir venda parcialmente registrada.
- Instalação e empacotamento para Windows com versões fixadas, build reproduzível tanto quanto viável, avisos de licenças, hash, changelog e instrução de atualização/rollback. Não exigir rede no uso normal. Evitar atualizador online obrigatório.
- Observabilidade local sem dados sensíveis; mensagens de falha orientadas ao operador e detalhes técnicos restritos ao administrador. Logs operacionais não substituem trilha de auditoria.

## Qualidade, testes e entregáveis
Implemente testes unitários, integração com SQLite real em diretórios temporários, testes de UI essenciais e fluxos de falha/concorrência, com dataset fictício. Consulte `docs/PLANO_TESTES.md`. Inclua lint, tipagem, testes e CI nas plataformas implementadas, com comandos reais e versões fixadas. Documente instalação, migrações, backup/restore, operação diária, segurança, limitações, modelos de dados, licenças e suporte. Publique código sem dados reais e sem arquivos de segredo; configure issue templates, revisão e política de segurança.

Não diga que o projeto é fiscalmente compatível, que o backup foi restaurado, que é seguro contra adulteração, que suporta múltiplas estações ou que está pronto para produção sem comprovação. Registre evidências de testes, revisão legal/fiscal e homologação por usuários.

## Sequência de implementação
1. Confirmar regras de operação, fiscal, perfis e política de risco. Criar esqueleto, CI e banco com migrações.
2. Autenticação, permissões, parâmetros e cadastros de produtos/clientes.
3. Estoque e entradas de fornecedor; testes de sinal, rateio e reversão.
4. Caixa por turno e frente PDV; gravação atômica e idempotência.
5. Pagamentos divididos, cartão, PIX e recebíveis conforme integrações aprovadas.
6. Crediário, parcelas, pagamentos parciais, limites e atrasos.
7. Cancelamentos, devoluções, estornos e auditoria append-only.
8. Fechamento, dashboard e PDF; dados e filtros reconciliados.
9. Backup/restore, migração de dados e empacotamento.
10. QA, revisão de segurança/licenças/fiscal, documentação e homologação antes de release.

Comece apresentando decisões pendentes e um plano de implementação verificável. Em seguida implemente a primeira etapa aprovada, sem afirmar que etapas futuras estão prontas.
