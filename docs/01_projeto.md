# Projeto PDV — documentação e estado

Versão: 1.0 — fase 1. Atualizado em 10/11/2026.

## Objetivo
Construir progressivamente um PDV para comércio varejista, com vendas, pagamentos, estoque, caixa, crediário, fechamento e indicadores. Plataforma principal: Excel 365 para Windows, com atenção à compatibilidade com Excel 2021. Os recursos sujeitos a disponibilidade devem ser testados nas versões usadas pela equipe.

## Situação atual
Apenas a estrutura visual foi criada no arquivo `PDV_Empresa_v1.0_fase1.xlsx`. Não há vendas operacionais, fórmulas de negócio, cadastros, validações, proteção, histórico automático ou massa de teste. Nenhum dos 12 testes funcionais finais foi executado. O arquivo não deve ser usado em produção.

A fase 1 foi entregue para aprovação; a fase 2 depende do aval do responsável. O nome Empresa é provisório.

## Arquitetura
| Aba | Finalidade planejada | Estado na fase 1 |
|---|---|---|
| 00_INSTRUCOES | Manual, checklist e massa de teste | Visível; apenas casca |
| 01_PARAMETROS | Empresa, regras, formas, operadores e turnos | Visível; apenas casca |
| 02_PRODUTOS | Cadastro e indicadores de estoque | Visível; apenas casca |
| 03_PDV | Frente de caixa | Visível; apenas casca |
| 04_VENDAS | Cabeçalhos de vendas | Oculta; apenas casca |
| 05_ITENS_VENDA | Itens das vendas | Oculta; apenas casca |
| 06_CAIXA | Turnos e conferência | Visível; apenas casca |
| 07_PAGAMENTOS | Pagamentos por venda | Oculta; apenas casca |
| 08_FECHAMENTO | Relatório diário | Visível; apenas casca |
| 09_CREDIARIO | Contas a receber | Visível; apenas casca |
| 10_CLIENTES | Cadastro e crédito | Visível; apenas casca |
| 11_ESTOQUE_MOV | Movimentações de estoque | Oculta; apenas casca |
| 12_ENTRADAS | Compras e entradas | Visível; apenas casca |
| 13_DASHBOARD | Indicadores e gráficos | Visível; apenas casca |
| 14_AUDITORIA | Ocorrências | Oculta; apenas casca |
| 15_LISTAS | Domínios de validação | Muito oculta; apenas casca |

## Relações planejadas
- Produtos: código único; itens e movimentações referenciam o código.
- Vendas: ID_Venda único; itens e pagamentos referenciam ID_Venda e têm sequência própria.
- Crediário: títulos/parcelas referenciam venda e cliente; o modelo definitivo deverá usar identificador estável do cliente, não apenas o nome.
- Caixa: turnos e seus movimentos devem ter identificadores rastreáveis. Identificação física do caixa e movimentos detalhados ainda precisam ser modelados.
- Cancelamentos devem preservar o histórico e gerar estornos rastreáveis, sem apagar registros.

## Limitações e decisões pendentes
Fórmulas não gravam transações, não limpam carrinhos nem geram logs imutáveis. A equipe deverá escolher entre operação manual controlada e automação VBA antes de implementar finalização, estornos e atalhos. Proteção de planilha e PIN em células não são mecanismos robustos de segurança. Coautoria simultânea offline e controle de concorrência entre 1–3 caixas não estão garantidos por um único arquivo. Tributação e emissão de documento fiscal não estão implementadas; valide requisitos legais com contador e fornecedor fiscal. Desempenho inferior a três segundos depende do volume e ambiente e ainda não foi medido.

## Fases futuras
2. Parâmetros e listas. 3. Produtos e indicadores. 4. Movimentações e entradas. 5. Carrinho. 6. Pagamentos. 7. Gravação e baixa de estoque. 8. Caixa. 9. Crediário e clientes. 10. Fechamento. 11. Dashboard. 12. Manual, auditoria, proteção e testes finais. Aguarde aprovação entre fases.

## Versionamento
- 1.0, fase 1: estrutura, cores, casca, navegação básica e configuração de impressão.
- Documentação adicional: registro do estado, fórmulas de referência e QA; sem alteração funcional da planilha.
