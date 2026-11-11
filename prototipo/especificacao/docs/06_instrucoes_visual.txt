# Aba de instruções — revisão visual

Arquivo: `PDV_Empresa_instrucoes_v1.xlsx`. A aba `00_INSTRUCOES` foi redesenhada a partir das referências visuais fornecidas: faixa grafite superior, faixa turquesa, rótulos turquesa à esquerda e títulos de seção em cinza-claro, com orientações logo abaixo. A marca é um texto provisório, não uma cópia do logotipo da referência.

## Padrão aplicado
Coluna A vazia, largura 3. Na aba de instruções, B tem largura 17 e C:I têm largura 12. Linha 1 = 32 pontos; linha 2 = 20; linha 3 = 8 e vazia; linha 4 = 30 para acomodar título; linha 5 = 20; linha 6 = 8. Congelamento em C7. A área de conteúdo inicia em B4; os blocos começam em B7, com texto em C:I. Os blocos utilizam células mescladas para títulos e parágrafos, não para tabelas de dados. Impressão de B1:I50, A4 retrato, uma página de largura e altura livre.

Esta revisão visual aplica-se somente a 00_INSTRUCOES. As outras abas não foram redesenhadas e seus módulos ainda estão incompletos. Se houver conflito com o antigo padrão de alturas e orientação, esta revisão adota as medidas descritas acima somente nesta aba.

## Conteúdo
O manual cobre estado do protótipo, preparação de cópia, importação do módulo VBA, produtos fictícios, venda, pagamento, registro, exemplo numérico, backup, falhas, limites, atalhos, cores, suporte, marca e versão. Não se trata do manual de um sistema completo: os módulos futuros precisam ser documentados quando implementados e homologados.

## Instalação da macro
O arquivo entregue continua `.xlsx` sem macro incorporada. Importar `ModuloPDV.bas` no Excel desktop e salvar uma cópia `.xlsm`, conforme a seção Passo 3. A macro não foi executada neste ambiente; utilize apenas dados fictícios. Consulte `05_padrao_e_prototipo` para os detalhes e limitações.

## Verificação
A estrutura foi inspecionada via biblioteca de arquivos Excel; não houve teste de renderização, impressão ou execução de VBA no Excel. Faça uma conferência visual em sua versão do Excel e ajuste quebras/alturas se necessário.
