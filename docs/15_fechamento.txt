# 08_FECHAMENTO — prévia de vendas e pagamentos

Arquivo: `PDV_Empresa_fechamento_v1.xlsx`. Esta aba é uma prévia aritmética para dados fictícios. Não substitui fechamento de caixa, conciliação bancária ou emissão fiscal e não deve ser usada em produção.

## Filtros e escopo
C7: data inicial; F7: data final; I7: parte do nome do operador. As datas são inclusivas e iniciam com `=HOJE()`; podem ser substituídas por datas fixas. I7 vazio inclui todos os operadores. A fórmula trata caracteres `*`, `?` e `~` no nome como texto literal. Somente vendas com status `Concluída` entram nas métricas do período. Turno, caixa, cliente, categoria e forma não são filtros gerais deste relatório. Pagamentos usam data e operador derivados da venda vinculada em 07_PAGAMENTOS.

## Blocos
- Linhas 10–13: quantidade de cupons, itens, faturamento líquido, ticket médio, pagamentos aplicados e diferença entre pagamentos aplicados e faturamento.
- Linhas 16–27: número de linhas de transação, valor aplicado, valor entregue, troco, percentual e verificação aritmética por forma. O protótipo registra Dinheiro e PIX; as outras linhas são reservadas, não indicam que cartões ou crediário estejam operacionais. `Formas não listadas` calcula a diferença entre o total aplicado e as formas apresentadas.
- Linha 28: alerta consolidado. Se não houver divergência detectada, o texto não é prova de liquidação, integridade dos dados ou fechamento final.
- Linhas 30–32: pagamentos com erro de linha, vendas com diferença, vendas sem itens e pagamentos órfãos. A última contagem é global, não filtrada por período/operador, porque não existe venda da qual obter data e operador.

Valor aplicado é valor entregue menos troco; por isso o troco não deve ser somado ao faturamento. Transações são linhas de pagamento, não quantidade de cupons. O total de pagamentos não é o dinheiro na gaveta, e uma soma equilibrada não prova que o pagamento foi recebido. A conferência por forma verifica apenas entregue − troco = aplicado agregados: erros de linhas podem se compensar, por isso confira também os alertas individuais.

## Passo a passo
1. Abra uma cópia no Excel, com cálculo automático ativo. Em C7 e F7, digite o período de teste. Deixe I7 vazio ou digite parte do operador fictício.
2. Revise os totais da seção 01, a distribuição de formas na seção 02 e cada alerta da seção 03. Diferença em F13 deve ser zero para valores conciliados. Abra 04_VENDAS e 07_PAGAMENTOS e filtre pelo ID de venda para investigar divergências.
3. Compare externamente PIX e demais recebimentos, e confira gaveta na aba 06_CAIXA. Não existe vínculo automático entre movimentos manuais do caixa e pagamentos do PDV.
4. Arquivo > Imprimir: área B1:I42, A4 paisagem, uma página de largura. O relatório é dinâmico: não fica congelado ao imprimir ou salvar. Faça uma cópia/PDF com procedimento aprovado, mas saiba que a geração automática e a trava não estão implementadas.

## Fórmulas e funções
Nomes internos das funções são em inglês, mas no Excel PT-BR são traduzidos:
- `SOMASES` (SUMIFS) soma os valores por status, período e operador.
- `CONT.SES` (COUNTIFS) conta cupons ou linhas de pagamento com os mesmos critérios.
- `SE` (IF), `SEERRO` (IFERROR) e `ÉNÚM` (ISNUMBER) validam o período e evitam divisão por zero no ticket médio.
- `SUBSTITUIR` (SUBSTITUTE) escapa caracteres curinga no operador.
- `ARRED` (ROUND) calcula a diferença em centavos; `HOJE` (TODAY) fornece a data corrente, não um fechamento histórico.
- F13: `=SE(E(ÉNÚM($C$7);ÉNÚM($F$7);$C$7<=$F$7);ARRED(C13-C12;2);"")`.

As fórmulas completas estão nas respectivas células. Elas usam 04_VENDAS linhas 8–507 e 07_PAGAMENTOS linhas 8–1007, limites fixos do protótipo. O resultado depende das fórmulas intermediárias das abas de origem e do recálculo completo do Excel.

## Testes manuais pendentes — cópia fictícia
1. Registre uma venda de R$ 27 com dinheiro entregue R$ 30. Para o mesmo dia e operador, confira 1 cupom, faturamento R$ 27, aplicado R$ 27, entregue R$ 30, troco R$ 3 e diferença zero.
2. Em outra venda de R$ 27, divida R$ 10 em dinheiro e R$ 17 em PIX. As formas devem somar R$ 27 e a diferença permanecer zero. Confirme a contagem de duas transações para essa venda.
3. Filtre outro operador e teste data inicial posterior à final: deve surgir alerta de datas inválidas e as métricas devem ficar vazias.
4. Em cópia descartável, altere um valor aplicado; recalcule e verifique diferença e alerta. Teste também pagamento sem ID de venda válido. Nunca edite histórico real.

## Pendências
Não há fechamento por turno, assinaturas, apuração de taxas ou recebíveis, cartão parcelado, crediário, devoluções, cancelamento, custo/lucro, top produtos, auditoria, integração com caixa, congelamento do relatório ou PDF automático. A aba não bloqueia alterações retroativas. Não houve teste interativo, recálculo ou impressão no Excel, nem homologação da macro; o desempenho de fórmulas repetidas também não foi medido.
