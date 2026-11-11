# 02_PRODUTOS — cadastro, filtros e sinalizações

Arquivo: `PDV_Empresa_produtos_v1.xlsx`. Módulo de teste; o projeto ainda não está homologado para produção.

## Estrutura
Tabela `tblProdutos`, B7:Q107, com filtros automáticos no cabeçalho e 100 linhas de cadastro (8 a 107). As dez primeiras colunas mantêm a ordem usada pela macro do protótipo: código, código de barras, descrição, categoria, unidade, custo, preço, estoque inicial, mínimo e ativo. Em L:Q estão estoque atual, status, margem, valor a custo, valor a preço de venda e saídas de venda dos últimos 30 dias. Coluna A permanece vazia. O painel é congelado em C8, mantendo visível a linha 7, diferente do padrão C7 das outras abas.

Os cartões T4:AA5 mostram número de SKUs ativos, ativos com estoque vazio, ativos com estoque baixo e valor de estoque a custo. O valor a custo inclui produtos ativos e inativos; quantidade negativa diminui esse valor. Esses cartões resumem todos os registros e não mudam ao aplicar filtros de tabela.

## Cadastro
1. Abra `02_PRODUTOS`. Use uma linha vazia de 8 a 107 e informe em B um código único como texto, em C o código de barras como texto, em D descrição e em E categoria.
2. Em F selecione UN, KG, LT ou CX. Em G digite custo não negativo; em H digite preço de venda maior que zero. Em I informe estoque inicial não negativo e em J estoque mínimo não negativo. Em K selecione S ou N.
3. L:Q são calculadas; não digite sobre as fórmulas. As células de entrada têm borda âmbar; as calculadas têm fundo cinza. Não há proteção ativa, portanto a equipe pode sobrescrever fórmulas acidentalmente.
4. Os cadastros P001 a P005 são fictícios. P004 começa com saldo 2 e mínimo 4; P005 começa com saldo zero. As fórmulas serão atualizadas quando o Excel recalcular o arquivo.

## Sinalização
- **ESTOQUE VAZIO**, vermelho: saldo menor ou igual a zero; valores negativos também são sinalizados como vazios.
- **ESTOQUE BAIXO**, amarelo: saldo positivo e menor ou igual ao mínimo.
- **ESTOQUE BOM**, verde: saldo superior ao mínimo.

Os rótulos continuam visíveis mesmo sem distinguir as cores. Produto inativo ainda recebe status na linha; os cartões de quantidade consideram apenas ativos. Código ou EAN duplicado é destacado em vermelho. As validações são auxiliares e podem ser contornadas por colagem; revise duplicidades antes de vender. O sistema não verifica colisões entre código e EAN nem dígito verificador do EAN.

## Filtros
Clique na seta do cabeçalho da tabela. Em `Status Estoque`, desmarque os demais valores e selecione `ESTOQUE BAIXO` ou `ESTOQUE VAZIO`. Use também os filtros de categoria, unidade e ativo, e ordenação crescente do estoque. Para remover um filtro, abra a seta da coluna e escolha Limpar filtro. Estes são filtros nativos de Tabela do Excel; não são segmentações nem filtros dinâmicos de dashboard.

## Fórmulas de referência — Excel PT-BR
Na linha 8, copiadas até a 107 (o arquivo interno armazena nomes em inglês):

**L8, estoque atual:**
`=SE(B8="";"";I8+SOMASE('11_ESTOQUE_MOV'!$F$8:$F$10000;B8;'11_ESTOQUE_MOV'!$G$8:$G$10000))`

**M8, situação:**
`=SE(B8="";"";SE(L8<=0;"ESTOQUE VAZIO";SE(L8<=J8;"ESTOQUE BAIXO";"ESTOQUE BOM")))`

**N8, margem:**
`=SE(OU(B8="";H8<=0);"";SEERRO((H8-G8)/H8;0))`

**O8, valor de estoque a custo:** `=SE(B8="";"";L8*G8)`

**P8, valor de estoque a preço:** `=SE(B8="";"";L8*H8)`

**Q8, saídas dos últimos 30 dias incluindo hoje:**
`=SE(B8="";"";-SOMASES('11_ESTOQUE_MOV'!$G$8:$G$10000;'11_ESTOQUE_MOV'!$F$8:$F$10000;B8;'11_ESTOQUE_MOV'!$E$8:$E$10000;"Saída Venda";'11_ESTOQUE_MOV'!$C$8:$C$10000;">="&HOJE()-29;'11_ESTOQUE_MOV'!$C$8:$C$10000;"<"&HOJE()+1))`

`SOMASE` (SUMIF) soma quantidades assinadas dos movimentos do produto; `SOMASES` (SUMIFS) acrescenta critérios de tipo e data; `SE` (IF) escolhe o status; `SEERRO` (IFERROR) trata erro da margem; `HOJE` (TODAY) é dinâmico e não grava data histórica.

## Limitações relevantes
- As fórmulas de movimento leem apenas as linhas 8 a 10000 de `11_ESTOQUE_MOV`. Os cartões e validações cobrem apenas as 100 linhas previstas. Expandir a tabela não expande automaticamente esses intervalos: a migração para referências estruturadas e sua homologação são necessárias antes de ultrapassar esses limites.
- A venda 30d é saída bruta de movimentos do tipo `Saída Venda`, não líquida de estornos e devoluções. Não há cancelamento integrado no protótipo.
- A aba `12_ENTRADAS` ainda não está integrada. Alterar saldo inicial ou custos após início da operação pode distorcer o histórico. Não há histórico confiável de custo, curva ABC, ponto de pedido, cobertura ou giro nesta versão.
- Recalcule no Excel. O visualizador pode não mostrar resultados calculados; a verificação aqui foi estrutural, não houve execução no Excel nem teste da macro.

## Checklist em cópia de teste
1. Abra no Excel, habilite cálculo automático e confira P001 bom, P004 baixo e P005 vazio; cartões devem indicar 5 ativos, 1 vazio, 1 baixo e R$ 296,00 de estoque a custo.
2. Filtre `Status Estoque` por `ESTOQUE BAIXO`: P004 deve aparecer. Limpe o filtro e selecione `ESTOQUE VAZIO`: P005 deve aparecer.
3. Tente inserir um código duplicado e um preço negativo; confira a mensagem de validação. Copiar e colar pode contorná-la; teste também a cor de duplicidade.
4. Para baixa por venda, instale a macro conforme `05_padrao_e_prototipo`; faça venda fictícia e confira a movimentação. Isso requer teste manual no Excel e uma cópia de backup.
