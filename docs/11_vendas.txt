# 04_VENDAS — histórico de teste e consulta

Arquivo `PDV_Empresa_vendas_v1.xlsx`. A aba está visível para consulta, mantém a identidade visual das demais e usa a tabela `tblVendas` em B7:N507. Esta versão é um protótipo, não deve ser utilizada em produção. Não apague nem digite sobre o histórico; a proteção de planilha ainda não está ativa.

## Leia a tabela
B ID da venda; C data; D hora; E operador; F cliente; G subtotal; H total; I status; J troco. Essas posições preservam o contrato do módulo VBA. K quantidade total de itens; L pagamentos aplicados; M diferença entre pagamentos aplicados e total; N conferência. As colunas K:N são fórmulas. A macro simplificada grava em G o total após desconto, portanto G **não representa subtotal bruto**; não use para apuração de descontos.

Sinalização: CONFERIDO em verde apenas quando venda concluída e diferença arredondada é zero; DIVERGÊNCIA em vermelho; REVISAR STATUS em amarelo quando o status não é Concluída. Isso não comprova o recebimento de PIX nem verifica que todos os itens estejam corretos. Código de venda duplicado é realçado em vermelho. Não existe rotina de cancelamento ou estorno neste protótipo.

## Consultar e filtrar
1. Use as setas na linha 7 para aplicar filtros nativos em data, operador, cliente, status e conferência. Pode combinar filtros em mais de uma coluna e ordenar. Para recuperar os dados, limpe os filtros nas mesmas setas.
2. À direita da tabela, na área P:V, o painel de consulta tem campos em S9:S13: data inicial, data final, parte do nome do operador, parte do nome do cliente e status. Deixe data e textos em branco para não restringir. As datas inicial e final são inclusivas. O padrão do status é Concluída; escolha Todos para incluir os demais.
3. A contagem e o total do painel reagem a esses critérios, mas **não filtram nem escondem as linhas da tabela**; os filtros do cabeçalho, por sua vez, não afetam o resumo lateral. O total em Todos inclui valores de canceladas/devolvidas, se existirem, sem estorno. Digitar uma data inicial posterior à final exibirá DATAS INVÁLIDAS.
4. Para investigar divergência, reexiba `05_ITENS_VENDA` e `07_PAGAMENTOS` com botão direito sobre uma guia > Reexibir; busque o mesmo ID. `Valor Aplicado` é líquido do troco, distinto de `Valor Entregue`.

## Fórmulas — linha 8
- K8: `=SE(B8="";"";SOMASE('05_ITENS_VENDA'!$B$8:$B$10000;B8;'05_ITENS_VENDA'!$G$8:$G$10000))`.
- L8: `=SE(B8="";"";SOMASE('07_PAGAMENTOS'!$B$8:$B$10000;B8;'07_PAGAMENTOS'!$E$8:$E$10000))`.
- M8: `=SE(B8="";"";ARRED(L8-H8;2))`.
- N8: `=SE(B8="";"";SE(I8<>"Concluída";"REVISAR STATUS";SE(ABS(M8)<0,005;"CONFERIDO";"DIVERGÊNCIA")))`.

## Módulo VBA atualizado — obrigatório para este arquivo
Importe `ModuloPDV_vendas.bas` no Excel desktop após salvar cópia `.xlsm`. Se já importou o módulo antigo, no editor Alt+F11 remova o módulo `ModuloPDV` anterior antes de importar o novo, para evitar nomes duplicados. O novo módulo procura a primeira linha de ID vazia na tabela e bloqueia novas vendas quando as 500 linhas estão ocupadas. O arquivo `.xlsx` não contém macros. O VBA não foi executado ou homologado neste ambiente.

## Limites técnicos
Fórmulas e resumo usam somente vendas nas linhas 8–507 e detalhes até a linha 10000 das respectivas abas. As 500 linhas do histórico são pré-alocadas e os filtros de tabela incluem as linhas vazias. A consulta lateral precisa de rolagem horizontal em telas menores. A área de impressão B1:N40 é apenas uma amostra, não o histórico completo; ajuste-a antes de imprimir. Filtros nativos não substituem auditoria, proteção ou controle de concorrência.

## Testes pendentes no Excel, em cópia fictícia
1. Com o módulo atualizado instalado, faça duas vendas fictícias e verifique que aparecem em B8 e B9, sem lacuna de 500 linhas.
2. Na primeira venda, P001 × 1 e P002 × 2 pagos com R$ 30 em dinheiro: H8 = R$ 27, J8 = R$ 3, K8 = 3, L8 = R$ 27, M8 = 0, N8 = CONFERIDO.
3. Filtre por operador na seta da tabela e confira as linhas; remova o filtro. Informe operador no painel lateral e confirme contagem e total. Confirme que os dois mecanismos são independentes.
4. Apenas em uma cópia, altere o valor aplicado de um pagamento e recalcule: a venda relacionada deve indicar DIVERGÊNCIA. Descarte a cópia; nunca altere histórico de operação real.
5. Teste datas invertidas, duplicidade e impressão. Não foi executado recálculo, impressão ou VBA no Excel durante a geração.
