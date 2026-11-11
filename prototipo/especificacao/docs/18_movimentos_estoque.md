# 11_ESTOQUE_MOV — controle de movimentações para testes

Arquivo `PDV_Empresa_movimentos_v1.xlsx`; aba visível. `tblEstoqueMov` ocupa B7:L2007, com 2.000 linhas pré-alocadas, filtros no cabeçalho e congelamento em C8. A planilha é protótipo e NÃO deve ser usada em produção. O arquivo não protege o histórico contra edição, exclusão ou colagem.

## Campos
B ID_Mov (texto, único); C data; D hora; E tipo; F código do produto; G quantidade assinada; H documento; I operador; J descrição atual buscada no cadastro; K verificação; L observações. B:I mantêm a posição esperada pela macro; J:L foram acrescentadas. A descrição é atual, não fotografia histórica. Entradas são amarelo-claro; cálculos cinza. Os filtros de linha 7 permitem consultar por tipo, produto, data, operador e verificação. O guia lateral está em N:T.

## Regra de sinais
- Entrada e Devolução: positivas.
- Saída Venda e Perda: negativas.
- Ajuste e Transferência: positivas ou negativas, conforme sentido. Não há vínculo entre as duas pontas de uma transferência e não existe controle de depósitos.
- Zero não é válido. Data, hora, operador, tipo, produto e ID são obrigatórios para ter verificação OK. Data/hora são valores estáticos, não `HOJE()`/`AGORA()` para eventos históricos.

## Saldo e verificações
A aba `02_PRODUTOS` foi alterada: **somente movimentos com K = OK** compõem o estoque atual e as saídas de venda dos últimos 30 dias. A coluna R `Revisar Movimentos` mostra REVISAR quando um movimento identificado pelo código daquele produto não está OK. Um saldo pode parecer disponível apesar de haver movimentos rejeitados: não o use até solucionar os alertas. Registros sem código não são atribuídos a um produto, mas aparecem como erro na tabela de movimentos.

K sinaliza dados incompletos, ID duplicado, produto ausente ou duplicado no cadastro, tipo inválido ou sinal inadequado; verde indica apenas verificações básicas, não aprovação ou autorização. O cálculo não comprova que a saída representa uma venda legítima, nem que houve conferência física, nem impede estoque negativo. Verifique também linhas com dados soltos e sem ID; elas são sinalizadas como incompletas.

L8 de `02_PRODUTOS`, para referência:
`=SE(B8="";"";I8+SOMASES('11_ESTOQUE_MOV'!$G$8:$G$2007;'11_ESTOQUE_MOV'!$F$8:$F$2007;B8;'11_ESTOQUE_MOV'!$K$8:$K$2007;"OK"))`.
R8 conta, para o código do produto, movimentos com verificação diferente de OK. As fórmulas só cobrem linhas 8–2007. Esta regra substitui a fórmula de estoque descrita na documentação anterior `09_produtos`.

## Uso de teste
1. Em cópia fictícia, abra `11_ESTOQUE_MOV` e procure uma linha sem dados. Para uma entrada manual, informe ID único, data, hora, `Entrada`, código existente como P001, quantidade positiva, documento e operador fictício.
2. Confira K = OK e o saldo do produto em `02_PRODUTOS`. Para registrar perda, use quantidade negativa e um ID diferente. Não altere o saldo inicial para refletir o mesmo movimento, evitando duplicidade.
3. A macro cria saídas de venda; `12_ENTRADAS` ainda não está integrada. Devoluções e estornos digitados manualmente NÃO cancelam vendas nem crediário.
4. Para testar a macro nesta versão, salve cópia `.xlsm`, remova o módulo `ModuloPDV` anterior em Alt+F11 e importe `ModuloPDV_estoque.bas`. A versão verifica capacidade das tabelas e impede venda quando o produto possui movimentos sinalizados ou há linha de estoque preenchida sem ID. O código não foi executado no Excel neste ambiente.

## Testes manuais pendentes
1. P001 inicia com 20 unidades. Faça entrada fictícia de +10 com dados completos: deve resultar 30 e OK após recálculo.
2. Em nova linha, registre perda −2: deve resultar 28. Registre uma saída de venda fictícia −1: deve resultar 27.
3. Lance entrada com quantidade −3: deve aparecer SINAL INVÁLIDO; o saldo deve permanecer 27 e a coluna R do produto deve indicar REVISAR. Corrija ou descarte a cópia de teste; não apague histórico real.
4. Teste ID duplicado, código inexistente, campo obrigatório vazio, filtros e impressão. Confira que o novo módulo impede nova venda com movimento inválido associado ao produto.

## Limitações críticas
Não há gravação atômica, aprovação de gerente, auditoria imutável, integração com entradas de fornecedor, custo histórico, múltiplos depósitos, controle de concorrência ou cancelamento automático. Ao editar registros antigos, o saldo muda. Movimentos após linha 2007 ficam fora dos cálculos; ampliar tabelas e fórmulas exige revisão técnica. A impressão inicial B1:L40 cobre somente uma amostra. Não houve teste de fórmulas, macro, performance ou apresentação no Excel; o pré-preenchimento de fórmulas pode afetar desempenho.
