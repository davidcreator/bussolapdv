# 07_PAGAMENTOS — verificação e conciliação de teste

Arquivo `PDV_Empresa_pagamentos_v1.xlsx`; aba visível. É um protótipo e não substitui conciliação financeira ou confirmação bancária. Não usar em produção nem inserir dados reais.

## Estrutura
`tblPagamentos` em B7:Q1007, com 1.000 linhas pré-alocadas. A macro preenche B:G: ID da venda, sequência, forma, valor aplicado, valor entregue e troco. H:M são fórmulas de data, operador, status e total da venda, soma aplicada e diferença por venda; N verifica a linha; O confere a soma com o total; P:Q são reservados, ainda sem captura de NSU e observações pela macro. Os dados históricos B:G não devem ser editados; não há proteção ativa. Cabeçalho fixado e filtros nativos. O guia lateral S:Y pode exigir rolagem horizontal.

## Conferência
- N: OK em verde significa somente verificações básicas da linha; em vermelho, venda não encontrada, sequência inválida/duplicada, forma não suportada, valor inválido, troco fora do dinheiro ou valor inconsistente.
- O: VALORES CONFEREM em verde significa que a soma aplicada por venda corresponde ao total; DIVERGÊNCIA ou SEM VENDA em vermelho; REVISAR STATUS em amarelo. Esses indicadores NÃO comprovam pagamento ou liquidação de PIX.
- Cada venda com split tem mais de uma linha. A coluna L repete o total aplicado em cada uma delas: não some L para obter faturamento. Use E para valores por pagamento e exclua vendas canceladas conforme a política futura.

Para investigar, use os filtros da linha 7 pelo ID da venda; confira as linhas e compare com 04_VENDAS. Em caso de inconsistência, preserve uma cópia e investigue. Não edite registros de operação real.

## Fórmulas de referência
Linha 8, em português do Excel:
- `H8 = SE(B8="";"";SEERRO(ÍNDICE('04_VENDAS'!$C$8:$C$507;CORRESP(B8;'04_VENDAS'!$B$8:$B$507;0));""))`.
- `L8 = SE(B8="";"";SOMASE($B$8:$B$1007;B8;$E$8:$E$1007))`.
- `M8 = SE(B8="";"";ARRED(L8-K8;2))`.
- `O8 = SE(B8="";"";SE(J8="SEM VENDA";"SEM VENDA";SE(J8<>"Concluída";"REVISAR STATUS";SE(ABS(M8)<0,005;"VALORES CONFEREM";"DIVERGÊNCIA"))))`.
- N8 contém verificações de sequência, forma e valores; consulte a fórmula na célula. As buscas de cabeçalhos são limitadas às linhas 8–507 em 04_VENDAS.

## Módulo atualizado
Para registrar novas vendas nesta versão, salve uma cópia `.xlsm`, abra o editor VBA com Alt+F11, remova o módulo `ModuloPDV` antigo e importe `ModuloPDV_pagamentos.bas`. Ele verifica a capacidade de linhas de vendas, itens e pagamentos antes de gravar. Não é uma transação atômica, não verifica a capacidade do histórico de estoque e não foi executado neste ambiente. Faça backup antes de cada teste.

## Testes a executar no Excel, em cópia fictícia
1. Venda R$ 27: dinheiro entregue R$ 30. A linha deve mostrar aplicado R$ 27, troco R$ 3, verificação OK e VALORES CONFEREM.
2. Outra venda R$ 27: R$ 10 em dinheiro e R$ 17 em PIX. Devem existir duas linhas de mesmo ID, com sequências distintas; a soma aplicada é R$ 27 e O mostra VALORES CONFEREM em ambas.
3. Apenas em cópia descartável, duplique a sequência ou altere o valor aplicado; recalcule e confira o alerta correspondente. Descarte a cópia, sem alterar histórico real.
4. Filtre por ID, forma e conferência; confira que limpar o filtro restaura as linhas. Teste também ausência de venda vinculada.

## Pendências
Não há cartão, parcelamento, taxas de adquirente, bandeira, NSU integrado, datas de liquidação, PIX confirmado, crediário, estornos, cancelamentos ou conciliação bancária. Os cálculos usam faixas fixas, apenas 500 vendas e 1.000 pagamentos; exige redesenho e homologação antes de ampliar. Avisos não impedem edição ou lançamento inválido por colagem, e os dados não são invioláveis. Não há teste real de fórmulas, execução de macro, performance ou renderização no Excel.
