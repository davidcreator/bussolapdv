# Padrão das planilhas e protótipo do PDV

## Status
`PDV_Empresa_prototipo_pdv.xlsx` é uma bancada de testes local, não uma solução pronta nem um PDV fiscal. Há três produtos fictícios. Foram criados apenas os campos necessários a um fluxo demonstrativo de venda, usando Dinheiro e PIX. As demais abas e o modelo de dados completo ainda estão pendentes; não se deve usar em produção.

## Padrão de layout acordado
Coluna A é margem de largura 3 e fica vazia. B:I devem participar do conteúdo das áreas principais; nenhum espaço de separação é criado como coluna vazia entre B e I. Células específicas podem estar vazias quando não houver valor; exigir conteúdo em cada célula inviabilizaria entradas e títulos. A antiga coluna I espaçadora passou a ter largura 12 em todas as abas; na grade do PDV ela contém estoque. Cada nova tela deve planejar seus campos em B:I; áreas adicionais podem estender-se até AF. Na fase atual, as abas sem conteúdo ainda são cascas e NÃO atendem integralmente à ocupação de B:I.

Linhas 1–3 são casca e divisor; título na linha 4, descrição na 5 e linha 6 livre; tabelas genéricas começam na linha 7, dados na 8. Exceção: o PDV tem identificação a partir da linha 7 e cabeçalho de carrinho na linha 11. Congelamento C7 fixa linhas 1 a 6 e colunas A e B. Não há colunas em branco de espaçamento entre B e I, mas I a partir do menu permanece fora da faixa J:Z definida no briefing.

Entradas em branco com borda âmbar; fórmulas em cinza; cor primária #1F3864, texto Segoe UI. Tabelas de dados estruturadas, sem mesclagem interna. Identificadores e códigos devem ser texto, sem remover zeros. Valores históricos são gravados como valores, não como buscas dinâmicas. As cores e a proteção precisam de revisão ao implementar cada aba.

## O que o protótipo faz
C8 recebe operador; G8 cliente. Nas linhas 12–26, informe código em B, quantidade em E e desconto decimal/percentual em G. Descrição, unidade, preço, total e saldo são calculados nas outras colunas. Total em C28. Até três pagamentos em C:H da linha 31, com formas Dinheiro ou PIX. Troco e mensagem são estimados por fórmula; a macro rejeita troco superior ao dinheiro entregue. A macro verifica produto ativo, quantidades acumuladas e estoque, preço, campos e pagamento e grava venda, itens, pagamentos e saída de estoque, em registros simplificados.

## Instalar a macro no Excel Windows
1. Abra `PDV_Empresa_prototipo_pdv.xlsx` no Excel de desktop. Faça uma cópia de segurança.
2. Arquivo > Salvar como > escolha **Pasta de Trabalho Habilitada para Macro do Excel (*.xlsm)**. Este passo não adiciona macros por si só.
3. Pressione Alt+F11; no projeto da cópia salva, Arquivo > Importar arquivo e escolha `ModuloPDV.bas`. Se necessário, habilite a guia Desenvolvedor nas opções do Excel. Salve o .xlsm.
4. Habilite macros somente se confiar no arquivo e na origem do código; siga a política de segurança. Volte à aba 03_PDV.
5. Digite operador, cliente, códigos e quantidades. Exemplo: P001 quantidade 1 e P002 quantidade 2; total esperado R$ 27,00. Escolha Dinheiro e valor R$ 30,00; troco esperado R$ 3,00.
6. Pressione Alt+F8, escolha `FinalizarVenda` e clique Executar. Confira o aviso, salve e verifique as abas históricas reexibindo-as. Estoque de P001 deve cair de 20 para 19 e de P002 de 15 para 13. A soma de Valor Aplicado deve ser R$ 27,00; dinheiro entregue R$ 30,00; troco R$ 3,00. Use apenas uma cópia de teste.

## Limitações críticas
A macro não foi executada nem testada no Excel neste ambiente; requer homologação no Excel Windows. Não há transação atômica: falha durante escrita pode produzir dados parciais. Nessa situação, NÃO repita; feche sem salvar e restaure a cópia anterior. Salve uma cópia antes de cada teste. O arquivo não oferece controle de concorrência, caixa por turno, PIN, aprovação de descontos, cancelamento/estorno, auditoria, crediário, cartão, taxas, recebimentos, fechamento, impressão fiscal, proteções ou tratamento de fraude. O subtotal gravado nesta demonstração corresponde ao total após desconto; não é o subtotal bruto do modelo final. As tabelas reduzidas precisam de migração antes do modelo definitivo. Não use em produção ou com dados reais.

Os nomes das funções Excel apresentados no documento de fórmulas são traduzidos pelo próprio Excel; o arquivo armazena as fórmulas em formato OOXML em inglês. Cálculos são atualizados ao abrir no Excel; outros visualizadores podem não calcular fórmulas.
