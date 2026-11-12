# 05_ITENS_VENDA — detalhamento e conferência de teste

Arquivo: `PDV_Empresa_itens_v1.xlsx`; aba visível. **Não está pronta para produção**: a planilha e a macro não foram homologadas, não há segurança efetiva nem transações atômicas.

## Organização
A tabela `tblItensVenda` ocupa B7:Q1007, com 1.000 linhas pré-alocadas. B:K preserva a posição usada pela macro: ID de venda, sequência, código, descrição, unidade, quantidade, preço, desconto, total e custo unitário. L:Q contém subtotal bruto, lucro estimado, data, operador, status da venda e conferência. O congelamento C8 mantém o cabeçalho fixo. O painel S:Y orienta a consulta; pode exigir rolagem horizontal.

Dados B:K são históricos gravados pela macro; L:Q são fórmulas. Não altere ou exclua registros; a planilha não está protegida. As datas, operador e status são obtidos do histórico de vendas e podem mudar se o cabeçalho for editado. A chave lógica é ID + sequência.

## Filtrar e entender
Clique na seta de cada cabeçalho para filtrar por ID, código, data, operador, status ou conferência; combine filtros e remova-os pelo mesmo menu. Linhas vazias fazem parte da tabela prealocada.

CONFERIDO em verde indica apenas que há vínculo com venda, ID/sequência não duplicados e cálculos básicos consistentes. SEM VENDA, ID/SEQ DUPLICADO, DADOS INVÁLIDOS e TOTAL DIVERGENTE aparecem em vermelho. REVISAR STATUS aparece em amarelo quando a venda vinculada não está concluída. Esses alertas não comprovam pagamento, estoque ou integridade geral.

Subtotal bruto = quantidade × preço; lucro estimado = total líquido do item − quantidade × custo unitário histórico. Não inclui impostos, taxas ou despesas; não é lucro líquido. O protótipo não tem desconto geral ou alocação proporcional desse desconto.

## Fórmulas de referência
L8: `=SE(B8="";"";ARRED(G8*H8;2))`
M8: `=SE(B8="";"";ARRED(J8-G8*K8;2))`
N8: `=SE(B8="";"";SEERRO(ÍNDICE('04_VENDAS'!$C$8:$C$507;CORRESP(B8;'04_VENDAS'!$B$8:$B$507;0));""))`
O8 e P8 buscam operador e status nas colunas E e I de 04_VENDAS. Q8 valida vínculo, duplicidade, dados numéricos básicos e cálculo de total; a fórmula completa está na própria célula. As consultas estão limitadas aos cabeçalhos de vendas das linhas 8–507. Fórmulas não estabelecem integridade referencial nem substituem auditoria.

## Módulo atualizado
Para esta versão use `ModuloPDV_itens.bas`, em uma cópia salva como `.xlsm`. No Excel Windows pressione Alt+F11, remova o módulo anterior `ModuloPDV` e importe o novo. Ele procura linhas vazias e impede uma venda quando não há capacidade suficiente nas 1.000 linhas pré-alocadas. O `.xlsx` entregue não inclui macro. A macro não foi executada neste ambiente.

## Testes pendentes em cópia
1. Com o módulo atualizado importado, registre P001 × 1 e P002 × 2, sem desconto; confira duas linhas com o mesmo ID e sequências 1 e 2, total de R$ 27,00 e status CONFERIDO após recálculo.
2. Filtre pelo ID da venda e depois pelo produto. Confira que as linhas exibidas correspondem ao filtro.
3. Em cópia descartável, duplique ID e sequência e recalcule; espere ID/SEQ DUPLICADO. Altere o total de item e espere TOTAL DIVERGENTE. Não modifique registros reais.
4. Confira datas, operadores, cores e impressão no Excel. A impressão B1:Q40 cobre apenas parte inicial da tabela; ajuste conforme necessidade.

## Pendências para produção
Proteção e autenticação adequadas; gravação transacional com recuperação; concorrência entre caixas; cancelamento e estornos auditáveis; registro imutável e backups verificados; limites expansíveis sem fórmulas de intervalo fixo; integração fiscal; testes de arredondamento, carga, falhas e segurança; homologação no Excel. Enquanto esses itens não estiverem concluídos, não usar em produção.
