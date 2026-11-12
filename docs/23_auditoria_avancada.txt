# 14_AUDITORIA — painel integrado de verificação

Arquivo: `PDV_Empresa_auditoria_avancada_v1.xlsx`. Esta revisão preserva `tblAuditoria` em B7:R307 e substitui o antigo painel lateral por indicadores, comparação de relatórios e amostras de alertas. O painel é atualizado por fórmulas e mostra o estado atual das fontes; ele não cria um histórico automático nem autentica eventos. O protótipo não deve ser usado em produção.

## Como navegar
1. A aba `14_AUDITORIA` está visível. B:R continua sendo o registro manual de ocorrências, com filtros e validações descritos em `21_auditoria`.
2. Role horizontalmente até T:AA. Em T7:AA22 veja as contagens globais; T27:AA34 contém a comparação de relatórios; a partir da linha 37 fica a amostra das ocorrências atuais.
3. Os indicadores contam **linhas com estado diferente do estado aceito**, não pessoas, transações únicas ou perdas financeiras. A mesma situação pode ser contada em mais de uma categoria. Estado vazio é ignorado; erro de fórmula na célula de estado é contado como alerta e exibido como `ERRO NA FONTE` na amostra, quando identificável.
4. As amostras mostram até as primeiras cinco linhas de cada categoria na ordem física da fonte; não são as mais recentes nem a lista completa. Compare com a contagem. Para investigar todas, abra a respectiva aba e filtre pela coluna de verificação. A coluna `Linha na fonte` ajuda a localizar a célula; a linha pode mudar se a origem for ordenada.

## Origens e critérios de alerta
| Categoria | Origem | Coluna e estado aceito |
|---|---|---|
| Auditoria manual | 14_AUDITORIA | P = OK |
| Vendas | 04_VENDAS | N = CONFERIDO |
| Itens | 05_ITENS_VENDA | Q = CONFERIDO |
| Pagamentos — linha | 07_PAGAMENTOS | N = OK |
| Pagamentos — venda | 07_PAGAMENTOS | O = VALORES CONFEREM; uma venda dividida pode aparecer mais de uma vez |
| Caixa — turno | 06_CAIXA | U = CONFERIDO ou TURNO ABERTO |
| Caixa — movimento | 06_CAIXA | AH = OK |
| Caixa — contagem | 06_CAIXA | AN = OK |
| Crediário — título | 09_CREDIARIO | Q = OK |
| Crediário — recebimento | 09_CREDIARIO | AF = OK |
| Clientes | 10_CLIENTES | N = OK |
| Estoque — movimento | 11_ESTOQUE_MOV | K = OK |
| Entradas | 12_ENTRADAS | S = OK |
| Listas | 15_LISTAS | Q = PADRÃO ORIGINAL |

A inclusão de `TURNO ABERTO` como estado aceito não garante que o turno esteja operacional ou conciliado. Títulos vencidos, por si só, não são erros quando sua verificação é OK. O painel de listas detecta apenas o estado do catálogo preparado na versão anterior. Uma alteração legítima continua aparecendo como alerta até que o padrão seja revisado.

As contagens usam as faixas fixas já previstas nas abas. Registros fora desses limites, linhas sem estado, erros não cobertos pelas regras originais e operações que não geram registros automaticamente não são detectados. A amostra de contagem do caixa e de clientes não tem data de evento; a categoria de listas usa o nome da lista como referência.

## Comparação dos relatórios
- `Y28` mostra a diferença pagamentos − faturamento do filtro atual de `08_FECHAMENTO`; `Y29` mostra a mesma métrica do filtro atual de `13_DASHBOARD`.
- `T31` compara as duas datas e o texto do operador; `Y30` calcula a diferença entre as diferenças somente quando os filtros estão alinhados e ambos os resultados são numéricos. Se os filtros forem distintos ou inválidos, Y30 fica vazia.
- Mesmo com filtros alinhados e Y30 = 0, os relatórios podem compartilhar a mesma fonte incorreta; isso não prova que os pagamentos foram recebidos, que todas as vendas existem ou que o caixa está fechado. Confira também os alertas e evidências externas.

## Fórmulas
As contagens usam `SOMARPRODUTO` (SUMPRODUCT), `SEERRO` (IFERROR) e comparação dos estados das faixas de origem. As amostras usam `AGREGAR` (AGGREGATE) para encontrar posições das linhas que atendem ao critério e `ÍNDICE` (INDEX) para mostrar ID, data e estado. AC39:AC108 contém posições auxiliares ocultas; não edite essa coluna. Os números de linha exibidos são localizadores, não identificadores permanentes.

Essas fórmulas repetem consultas sobre intervalos extensos; desempenho depende da versão do Excel, volume e equipamento e não foi medido. O arquivo foi gerado para Excel 365/2021, mas recálculo, compatibilidade de fórmulas, ordenação e impressão ainda precisam ser validados no Excel.

## Roteiro de teste — cópia fictícia
1. No registro manual, informe uma ocorrência incompleta. Recalcule; a contagem `Auditoria manual` deve crescer e uma amostra deve indicar a linha e o estado. Complete-a e confirme que o alerta desaparece; o registro manual deve permanecer.
2. Gere em cópia uma divergência de pagamento e confira as categorias correspondentes. Um único cupom pode gerar alertas na linha e na venda; não some as categorias como se fossem eventos independentes.
3. Gere mais de cinco ocorrências de uma mesma categoria: a contagem deve mostrar todas dentro da faixa e a amostra apenas as primeiras cinco. Investigue as demais na aba de origem.
4. Em 08_FECHAMENTO e 13_DASHBOARD, alinhe as datas e o operador; confira `FILTROS ALINHADOS` e Y30. Altere um dos filtros e confirme `FILTROS DIFERENTES` e Y30 vazia.
5. Confira que os dados em B:R não foram apagados e teste filtros e impressão. A área de impressão inicial T7:AA34 cobre o resumo lateral, não o registro completo ou as amostras. Ajuste antes de exportar.

## Controles que continuam pendentes
O módulo VBA não grava eventos de auditoria. Não há evento imutável, autenticação, horários confiáveis, rastreio de antes/depois automático, aprovação, proteção de dados, assinatura, prevenção de exclusão, armazenamento seguro, concorrência, reconciliação bancária, teste de recuperação ou homologação. O painel integra **sinais existentes**, não implementa todas as verificações de negócio. Use somente dados fictícios.
