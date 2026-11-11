# 12_ENTRADAS — compras e entrada de mercadorias para teste

Arquivo `PDV_Empresa_entradas_v1.xlsx`; a tabela `tblEntradas` ocupa B7:U207, com 200 linhas de itens. É uma bancada de testes; não foi homologada e não deve ser usada em produção. O histórico pode ser editado ou excluído porque ainda não há proteção ou auditoria efetiva.

## Campos e orientação
Entradas com borda âmbar: B ID_Entrada único por linha/item; C data; D fornecedor; E CNPJ numérico opcional em texto, sem pontuação; F número da nota como texto; G código do produto; H quantidade; I custo unitário; K frete alocado à linha; M markup; O atualiza estoque? S/N; P operador; T observações. Preço, quantidade, frete e markup são valores numéricos.

Calculados em cinza: J total dos produtos; L custo final unitário; N preço sugerido; Q quantidade de movimentos válidos; R diferença de quantidade; S verificação; U descrição atual do produto. A descrição é dinâmica, não histórica. A linha 7 tem filtros; o congelamento C8 mantém o cabeçalho visível. O guia lateral fica em W:AC, acessível com rolagem horizontal.

O CNPJ recebe verificação de formato numérico, não valida dígitos, existência ou titularidade. CNPJ alfanumérico não é suportado. Para informações de fornecedores reais ou dados pessoais é preciso completar requisitos de segurança e homologação.

## Processo de teste
1. Cadastre o produto em `02_PRODUTOS`. Em `12_ENTRADAS`, use uma linha vazia e informe um ID_Entrada único para cada item, data, fornecedor, NF, código, quantidade positiva, custo unitário não negativo, operador e S ou N em O. CNPJ é opcional. O mesmo número de nota pode aparecer em várias linhas; não reutilize ID_Entrada.
2. Informe em K apenas o frete atribuído àquela linha, após rateio externo, e em M o markup sobre o custo. Exemplo: 25% significa multiplicador 1,25. A planilha não rateia automaticamente o frete total da nota nem confirma que a soma dos fretes alocados corresponde ao total da nota.
3. Se O = S, abra `11_ESTOQUE_MOV` e registre manualmente um movimento válido de tipo `Entrada`, quantidade positiva, mesmo código de produto e Documento = ID_Entrada. Informe ID_Mov, data, hora e operador. Uma entrada com S não cria movimento automaticamente. Se O = N, não registre movimento de entrada associado a esse ID.
4. Volte a `12_ENTRADAS`; verifique Q, R e S. `MOVIMENTO PENDENTE` indica ausência da entrada esperada; `MOVIMENTO INVÁLIDO`, `PRODUTO DIVERGENTE` e `DIVERGÊNCIA DE QTD` indicam necessidade de investigação. OK verifica apenas as regras implementadas; não prova autenticidade da nota ou aprova a compra.
5. A integração é feita pelo texto do documento na movimentação, não por vínculo seguro. Evite IDs repetidos ou usados para outros documentos. O saldo em `02_PRODUTOS` considera movimentos OK, independentemente de a entrada ter sido preenchida ou aprovada.

## Fórmulas
- J8: `=SE(B8="";"";SEERRO(ARRED(H8*I8;2);""))`.
- L8: `=SE(B8="";"";SEERRO((J8+K8)/H8;""))`. O custo unitário final conserva precisão; o formato mostra duas casas.
- N8: `=SE(B8="";"";SEERRO(ARRED(L8*(1+M8);2);""))`. É sugestão de markup sobre custo, não margem sobre preço, e não atualiza `02_PRODUTOS`.
- Q8 usa SOMASES para somar apenas movimentos `Entrada` com mesmo ID de documento, código de produto e verificação OK.
- R8 compara Q8 com a quantidade H8 para O = S; para O = N, indica qualquer movimento vinculado indevido.
- S8 verifica dados básicos, ID duplicado, produto, movimento inválido, código divergente e diferença. As fórmulas usam linhas fixas 8–2007 em `11_ESTOQUE_MOV` e 8–207 nesta aba.

## Cenário de teste em cópia
1. P001 inicia com 20 unidades na base fictícia original. Crie entrada E001 de 10 unidades de P001, custo unitário R$ 10, frete alocado R$ 10, markup 25%, O = S. Resultado esperado: total produtos R$ 100, custo final R$ 11 por unidade e preço sugerido R$ 13,75. Antes do movimento, estado MOVIMENTO PENDENTE.
2. Crie em `11_ESTOQUE_MOV` movimento `Entrada` de +10 P001, Documento E001 e demais campos obrigatórios. Após recálculo: Q = 10, R = 0, S = OK e saldo P001 = 30, desde que não haja outros movimentos válidos.
3. Em cópia descartável, teste documento com produto diferente, quantidade diferente, ID repetido e movimento com sinal inválido. Confira os alertas. O saldo do produto pode refletir movimentos válidos mesmo se a entrada estiver em revisão; não interprete saldo como aprovação da compra.
4. Teste O = N sem movimento e depois com movimento vinculado; no segundo caso deve haver divergência. Teste os filtros e impressão.

## Limites e pendências
Sem integração automática entre nota e movimento, importação XML, validação fiscal, custo médio, atualização de preço, rateio por nota, contas a pagar, workflow de aprovação, controle de estoque negativo, estornos rastreáveis, bloqueio de edição, acesso seguro e concorrência. As regras não verificam duplicidade de NF por fornecedor, consistência de data entre nota e movimento ou movimentos com outro tipo que usem o mesmo documento. Filtros e validações não substituem controles no lançamento; colagem pode contorná-los. A área de impressão B1:U30 cobre apenas uma amostra. Fórmulas, interface e cenários não foram executados no Excel nesta geração.
