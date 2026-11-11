# 13_DASHBOARD — indicadores e bases para gráficos

Arquivo: `PDV_Empresa_dashboard_v1.xlsx`. Os campos e bases foram preparados; não há gráficos ou segmentações criados. O arquivo continua sendo protótipo para dados fictícios, sem homologação ou conciliação bancária.

## Filtros
- C7: data inicial. F7: data final. Por padrão mostram os últimos sete dias incluindo hoje; substitua as fórmulas por datas fixas para outro período.
- I7: parte do nome do operador; vazio significa todos. A busca é textual e não diferencia maiúsculas/minúsculas. As datas são inclusivas. O painel sinaliza datas inválidas.
- Os filtros afetam apenas vendas, pagamentos e suas bases no período. **Estoque e crediário são saldos atuais e não reagem aos filtros de data ou operador.** Não existem filtros gerais por turno, cliente, categoria, forma ou status; o status de vendas é fixo em Concluída.

## Indicadores
B10:F15: faturamento líquido, vendas, ticket médio, itens por venda, lucro bruto estimado, margem bruta estimada, pagamentos aplicados, diferença de conciliação e contagem de alertas. Lucro é o total do item menos custo unitário registrado vezes quantidade; não considera impostos, taxas ou despesas. O pagamento é valor aplicado, não dinheiro entregue. A diferença é pagamentos aplicados menos faturamento.

B17:F21: produtos ativos, estoque vazio, baixo e produtos com movimentos em revisão; estoque a custo de produtos ativos sem movimentos em revisão; saldo a receber e vencido de títulos com verificação OK; títulos em revisão. Valores excluídos por erros podem tornar totais incompletos. Uma reconciliação igual a zero não garante integridade ou liquidação bancária.

## Bases para gráficos
1. **Mix por forma:** K11:N19; formas em K, transações em L, valores aplicados em M e participação em N. K21/M21 mostra o valor associado a outras formas não listadas. A macro atual aceita apenas Dinheiro e PIX. O campo M23 é uma contagem global de pagamentos sem venda vinculada, não filtrada por data/operador.
2. **Evolução diária:** B28:F59; datas em B, cupons em C, faturamento em D, itens em E e ticket em F. A série mostra no máximo os primeiros 31 dias a partir da data inicial; se o período for maior, o painel avisa. Os indicadores de vendas, em contraste, continuam considerando todo o período.
3. **Produtos:** K28:O128; código, descrição atual, quantidade, valor e lucro estimado por produto. Esta base acompanha os 100 produtos cadastrados e não está ordenada. Para criar Top 10, copie a base e cole como valores em uma área de trabalho fora do painel, depois ordene pela métrica desejada; essa cópia não se atualizará automaticamente. Itens cujo código não esteja na lista atual de produtos não aparecem nessa base.

## Como criar os gráficos no Excel
1. Em uma cópia do arquivo no Excel, selecione B28:B59 e, mantendo Ctrl, D28:D59. Acesse Inserir > Gráfico de Linhas para a evolução diária. Ajuste a seleção às linhas com datas do período e confira os rótulos.
2. Para mix, selecione K11:K19 e M11:M19 com Ctrl e escolha Inserir > Rosca. Confira se `Outras formas` é zero; caso contrário, investigue ou inclua-a manualmente.
3. Para produtos, use a cópia ordenada como valores e selecione as dez primeiras linhas de descrição e valor; escolha Inserir > Barras. Atualize a cópia ao mudar os filtros.
4. Após montar os gráficos, teste com filtros diferentes. O comportamento visual de células com fórmula que retorna vazio varia conforme as opções do gráfico no Excel; configure células vazias conforme necessário. A área de impressão inicial B1:O24 inclui somente os indicadores e mix, não os dados diários/produtos completos.

## Fórmulas e fontes
Faturamento usa `SOMASES` (SUMIFS) em 04_VENDAS por data, operador e status Concluída; cupons usam `CONT.SES` (COUNTIFS); ticket é faturamento dividido por cupons com `SEERRO` (IFERROR). Dados de pagamentos vêm de 07_PAGAMENTOS; quantidade e lucro por produto vêm de 05_ITENS_VENDA; estoques de 02_PRODUTOS; crediário de 09_CREDIARIO. O filtro de operador usa `SUBSTITUIR` para tratar curingas como caracteres literais.

A tabela de vendas cobre linhas 8–507, pagamentos e itens 8–1007, produtos 8–107 e títulos de crediário 8–207. São faixas fixas; registros fora delas não entram no painel. As funções dependem dos cálculos e status das abas de origem; aguarde recálculo completo no Excel.

## Checklist de teste — ainda não executado no Excel
- Crie em cópia fictícia uma venda concluída de R$ 27, com R$ 10 em dinheiro e R$ 17 em PIX. Para o dia e operador correspondentes, confira faturamento R$ 27, uma venda, ticket R$ 27, mix R$ 10/R$ 17 e diferença zero.
- Altere o operador e as datas: os indicadores de vendas e bases devem mudar; estoque e crédito devem permanecer atuais e inalterados pelo filtro.
- Selecione período superior a 31 dias: confira o aviso e a limitação apenas da série diária.
- Gere uma divergência em cópia descartável e confira os alertas. Veja se há produtos ou títulos em revisão antes de interpretar saldos.

## Pendências
Não há gráficos, slicers, linha do tempo, indicadores de desconto, cobertura/giro, taxa de inadimplência, ranking automático, previsões, comparativos ou filtros completos; tampouco integração robusta de caixa, crediário e pagamentos. Não houve recálculo, teste de fórmula, gráficos, impressão ou desempenho no Excel. Não utilize os indicadores para decisões reais antes de integração e homologação.
