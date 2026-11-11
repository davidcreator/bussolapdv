# 09_CREDIARIO — controle manual de parcelas para testes

Arquivo `PDV_Empresa_crediario_v1.xlsx`. NÃO é um módulo de crediário completo ou homologado. É uma bancada de testes com lançamento manual; não use com clientes ou valores reais.

## Organização
- `tblCrediario`, B7:R207: até 200 parcelas, uma linha por título/parcela. Entradas em branco/âmbar; cálculos em cinza.
- `tblRecebimentosCrediario`, X7:AF507: até 500 recebimentos, uma linha por evento. Podem existir vários recebimentos para uma parcela.
- AH:AM: indicadores e faixas de atraso. Role horizontalmente para acessar os blocos. Use os filtros dos cabeçalhos para consultar por cliente, venda, vencimento, status ou ID.

Essas faixas são fixas. Os resumos só consideram títulos cuja verificação seja OK; títulos em revisão ficam fora dos valores do painel. Sempre confira os contadores de revisão: não interprete o painel isoladamente. As faixas de atraso usam dias corridos e saldos válidos; o prazo de 7 dias inclui hoje e o sétimo dia, e o de 30 dias inclui hoje e o trigésimo. O maior atraso é apenas dos títulos válidos e vencidos.

## Cadastro de parcela de teste
1. Na primeira linha disponível de `tblCrediario`, digite em B um ID único do título, C o ID de uma venda concluída já existente, D código fictício do cliente, E nome fictício, F data da venda, G número da parcela, H quantidade de parcelas, I vencimento e J valor principal daquela parcela.
2. K recebe encargos manuais não negativos, se houver; deixe vazio para zero. Os valores de juros e multa de `01_PARAMETROS` **não são aplicados**. L calcula principal + encargos; M soma apenas recebimentos com verificação OK; N calcula saldo; O calcula atraso; P informa status; Q alerta; R recebe observações.
3. Para parcelamento crie uma linha para cada parcela, com IDs distintos, número e vencimento próprios. O arquivo ainda não gera parcelas automaticamente nem verifica a soma delas com o valor financiado.

A validação verifica que o ID de venda existe exatamente uma vez como venda concluída; NÃO verifica que a venda é a prazo nem que a parcela pertence ao cliente da venda. Código e nome do cliente são manuais e não consultam `10_CLIENTES`.

## Registrar recebimento de teste
1. Na primeira linha vazia de X:AF, informe ID_Recebimento único em X, ID_Título em Y, data em Z, forma em AA, valor positivo em AB e operador em AC. Documento/referência e observações em AD:AE são opcionais. AF apresenta a verificação.
2. Recebimentos OK atualizam M e N da parcela. Não lance o mesmo evento duas vezes. Um valor pago superior ao saldo total gera `PAGAMENTO EXCEDENTE` no título, que fica `REVISAR` e sai do painel; o excesso não é estornado automaticamente.
3. Para caixa real seria necessário registrar recebimento no turno e conferir comprovante. Este protótipo **não registra no caixa nem confirma PIX**. Não faça lançamentos reais.

## Sinalização
Pago: saldo zero; Em aberto: saldo positivo com vencimento hoje ou futuro; Vencido: saldo positivo e vencimento anterior a hoje. Dias em atraso = máximo de zero e HOJE menos vencimento para saldos positivos. Se houver erro de vínculo, dados ou recebimento, o status passa a REVISAR. Ao pagar, o indicador de atraso passa a zero: esta versão não preserva o atraso histórico de liquidação.

Entradas inválidas ou duplicadas são sinalizadas, mas a proteção não está ativa e a validação pode ser contornada por colagem. Recebimento sem ID em X, ou parcela sem ID em B, é ignorado pelas fórmulas e pode não aparecer nos alertas; revise campos antes de concluir qualquer teste.

## Fórmulas de referência
Na linha 8:
- L8: `=SE(B8="";"";SE(E(ÉNÚM(J8);OU(ÉNÚM(K8);K8=""));ARRED(J8+K8;2);""))`.
- M8: `=SE(B8="";"";SOMASES($AB$8:$AB$507;$Y$8:$Y$507;B8;$AF$8:$AF$507;"OK"))`.
- N8: `=SE(OU(B8="";L8="");"";ARRED(L8-M8;2))`.
- O8: `=SE(OU(B8="";N8="";NÃO(ÉNÚM(I8)));"";SE(N8>0;MÁXIMO(0;HOJE()-I8);0))`.

P8 depende da verificação Q8; Q8 verifica dados e recebimentos, e AF8 valida cada recebimento. Não há fórmula de juros automáticos: multas, juros, renegociação e baixa como perda dependem de contrato e desenho posterior. Use HOJE somente para indicadores correntes, não para registrar uma data histórica.

## Testes pendentes no Excel em cópia fictícia
1. Após criar uma venda fictícia concluída de R$ 15, use seu ID no título T001, cliente fictício, parcela 1/1, principal R$ 15, data de venda e vencimento futuro. O teste de vínculo é artificial: a macro atual não realiza venda a prazo.
2. Lance R001, título T001, data válida, Dinheiro, R$ 5 e operador fictício. Recalcule: recebido R$ 5, saldo R$ 10, status Em aberto.
3. Lance R002 de R$ 10 e recalcule: saldo zero, status Pago. Em cópia descartável, adicione mais R$ 1; deve aparecer PAGAMENTO EXCEDENTE e status REVISAR.
4. Em uma segunda cópia, escolha vencimento anterior a hoje e posterior ou igual à data de venda; com saldo positivo deve aparecer Vencido, com atraso correspondente. Teste ID duplicado e título de recebimento inexistente.
5. Confira filtros, cores e resumos no Excel. O painel de 7 dias está contido no de 30 dias; não some esses dois indicadores.

## Pendências para funcionamento real
Integração com vendas a prazo e clientes, validação de crédito e bloqueio por atraso, geração de parcelas, regras contratuais de juros e multa, recebimentos no caixa, comprovantes, renegociação, cancelamento/estorno, baixas em perda, auditoria, segurança, proteção, atomicidade, concorrência e testes de recálculo, carga e impressão. A geração apenas verificou a estrutura e o balanceamento de parênteses; fórmulas e validações não foram executadas no Excel. A área de impressão inicial B1:R30 cobre somente parte dos títulos, não os recebimentos.
