# Fórmulas e funções — consulta e aprendizagem

## Estado atual e convenções
A planilha da fase 1 **não contém fórmulas de negócio**. As fórmulas abaixo são exemplos didáticos planejados, não funcionalidades já implementadas. Antes de usá-las, crie as tabelas, colunas e nomes indicados, confirme as regras de negócio e teste no Excel. Os exemplos usam português do Brasil e separador `;`. Em Excel em inglês, use os nomes equivalentes e o separador da instalação. Valores históricos de preço, custo, data e hora precisam ser registrados como valores no momento do evento; buscas em cadastro atual não preservam histórico.

## Funções principais
| Português | Inglês | Uso |
|---|---|---|
| SE | IF | Escolhe resultado conforme condição |
| SEERRO | IFERROR | Trata erro de cálculo; não substitui validação |
| SOMA | SUM | Soma valores |
| SOMASES | SUMIFS | Soma atendendo vários critérios |
| CONT.SES | COUNTIFS | Conta registros com vários critérios |
| ÍNDICE | INDEX | Retorna item de intervalo por posição |
| CORRESP | MATCH | Encontra posição de valor; 0 exige igualdade exata |
| PROCV | VLOOKUP | Busca na primeira coluna de um intervalo |
| SOMARPRODUTO | SUMPRODUCT | Soma produtos de matrizes |
| MÁXIMO | MAX | Retorna maior valor |
| HOJE | TODAY | Data atual, muda com o tempo |
| TEXTO | TEXT | Formata número como texto |
| FILTRAR | FILTER | Retorna linhas por condição |
| ÚNICO | UNIQUE | Lista valores distintos |
| ORDENAR | SORT | Ordena uma matriz |
| FIMMÊS | EOMONTH | Último dia de mês deslocado |

## Busca por código ou código de barras
Com `C15` como entrada e `tblProdutos` contendo as colunas indicadas, descrição:

```excel
=SEERRO(ÍNDICE(tblProdutos[Descrição];CORRESP($C$15;tblProdutos[Código];0));SEERRO(ÍNDICE(tblProdutos[Descrição];CORRESP($C$15;tblProdutos[Cód. Barras];0));"Não encontrado"))
```

Preço:

```excel
=SEERRO(ÍNDICE(tblProdutos[Preço Venda];CORRESP($C$15;tblProdutos[Código];0));SEERRO(ÍNDICE(tblProdutos[Preço Venda];CORRESP($C$15;tblProdutos[Cód. Barras];0));""))
```

A busca prioriza código, depois código de barras. Armazene códigos e EAN como texto, preservando zeros à esquerda; valide duplicidades e conflitos entre os dois domínios. A fórmula PROCV de exemplo no briefing usa índice 4 no intervalo de Código a Preço Venda: pela ordem especificada isso retorna Categoria, não Descrição.

## Item e pagamentos
Se C17 for preço numérico, C18 quantidade e C19 desconto percentual:

```excel
=SE(OU(C18="";C17="");0;C18*C17*(1-C19))
```

Exemplo: preço 10, quantidade 2, desconto 10% → 18. Controle arredondamento monetário explicitamente na implementação. Para três valores pagos em N25:N27 e total em N20:

```excel
=SE(SOMA(N25:N27)<N20;"FALTA R$ "&TEXTO(N20-SOMA(N25:N27);"#.##0,00");SE(SOMA(N25:N27)>N20;"TROCO R$ "&TEXTO(SOMA(N25:N27)-N20;"#.##0,00");"PAGAMENTO OK"))
```

O exemplo é apenas aritmético: na regra real, troco deve ser limitado ao dinheiro recebido; excesso em pagamentos eletrônicos deve ser bloqueado ou tratado. Parcelas e taxas dependem do contrato e da política de repasse.

## Estoque e margem
Margem sobre preço de venda, em uma linha de `tblProdutos`:

```excel
=SEERRO(([@[Preço Venda]]-[@Custo])/[@[Preço Venda]];0)
```

Saldo com movimentos assinados: supondo `tblEstoqueMov` com coluna `Qtd Assinada`, positiva para entradas e estornos e negativa para saídas e perdas:

```excel
=[@[Estoque Inicial]]+SOMASES(tblEstoqueMov[Qtd Assinada];tblEstoqueMov[Código Produto];[@Código])
```

O esquema original não tem `Qtd Assinada`: é uma coluna adicional proposta, ainda não criada. Evite contabilizar duas vezes entradas e estoque inicial. Os lançamentos de entrada precisam ser registrados uma única vez no histórico.

Status, tratando estoque negativo como ruptura:

```excel
=SE([@[Estoque Atual]]<=0;"Ruptura";SE([@[Estoque Atual]]<=[@[Estoque Mínimo]];"Crítico";SE([@[Estoque Atual]]<=[@[Ponto de Pedido]];"Repor";"OK")))
```

Venda média diária de 30 dias = quantidade líquida vendida no período / 30; cobertura = estoque atual / média diária, se positiva. Giro exige definir estoque médio e período. ABC exige ordenar pela receita do período e calcular percentual acumulado; itens cancelados e devoluções devem seguir política explícita.

## Crediário
Atraso de uma parcela, com saldo e datas válidos, usando HOJE apenas como indicador dinâmico:

```excel
=SE([@[Saldo Devedor]]<=0;0;MÁXIMO(0;HOJE()-[@Vencimento]))
```

Uma parcela parcialmente paga continua em atraso sobre o saldo. Uma data de pagamento isolada não representa corretamente múltiplos recebimentos: para auditoria é necessário um histórico de recebimentos. Saldo disponível deve considerar todos os saldos ainda exigíveis, inclusive vencidos, vinculados ao identificador único do cliente, respeitando a política de renegociação/perda.

## Fechamento e filtros
Ticket médio, com `DataFiltro` nomeado e datas sem hora em `tblVendas[Data]`:

```excel
=SEERRO(SOMASES(tblVendas[Total];tblVendas[Status];"Concluída";tblVendas[Data];DataFiltro)/CONT.SES(tblVendas[Status];"Concluída";tblVendas[Data];DataFiltro);0)
```

Pagamentos do esquema proposto não incluem data/status da venda. Antes de somar por data ou operador, acrescente campos de vínculo apropriados ou relacione ao cabeçalho via modelo de dados. Somar pagamentos sem excluir cancelamentos não fecha o faturamento. Para split com troco, defina valor líquido efetivamente aplicado à venda, separado do dinheiro entregue e do troco. Recebimentos de crediário não devem ser contados novamente como venda do dia.

Exemplo de lista dinâmica, depois de criada a tabela e o status textual correspondente:

```excel
=FILTRAR(tblProdutos[[Código]:[Descrição]];tblProdutos[Status Estoque]="Ruptura";"Nenhum item em ruptura")
```

Fórmulas de matriz dinâmica precisam de espaço para se expandir; nem todas podem ser inseridas dentro de uma Tabela do Excel. Evite mascarar falhas relevantes com SEERRO: registre divergências e verifique a origem.

## Revisão e uso seguro
1. Digite a fórmula em uma cópia de teste, não sobre células de entrada ou histórico.
2. Compare com cálculo manual simples, incluindo zero, dados ausentes, cancelamento e valores negativos.
3. Use fórmulas estruturadas e colunas estáveis; valide formatos de texto, data, percentual e moeda.
4. Confirme se referências, nomes e política de arredondamento existem na versão implementada.
5. HOJE é apropriado para indicadores correntes, mas não para registrar a data histórica da operação.
