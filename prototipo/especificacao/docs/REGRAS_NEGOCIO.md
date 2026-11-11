# Regras de negócio e contratos de cálculo

> **Projeto:** Bússola Sistema PDV Open Source

**Estado: proposta; parametrização e cenários precisam de aprovação.**

## Dinheiro e pagamento
- Valores não negativos em centavos. Para cada venda: `total = subtotal − descontos + acréscimos`, segundo política de arredondamento; `soma(aplicado) = total`. Para dinheiro, `troco = entregue − aplicado`, entre zero e o dinheiro entregue. Para métodos sem troco, entregue e aplicado devem seguir política de confirmação, sem criar crédito indevido.
- Separar registro e confirmação de PIX/cartão. Captura de uma referência não comprova pagamento. Taxas, prazos e status da adquirente devem ser explícitos e independentes da dívida do cliente.
- Até três formas por venda; pagamentos de títulos antigos são recebimentos, não faturamento da venda do dia.

## Caixa
`esperado = fundo + vendas_dinheiro_aplicado + recebimentos_de_titulos_em_dinheiro + suprimentos − sangrias − estornos_em_dinheiro`. Contagem por denominação; diferença = contado − esperado. Fechamento por caixa/turno, com identidade, justificativa, snapshot e correções rastreáveis.

## Estoque
Saldo inicial + soma de movimentos assinados. Entradas, devoluções positivas; vendas, perdas negativas; ajuste/transferência conforme sentido. Venda e saída devem ser atômicas, evitando dupla baixa. Definir a política de produto fracionável, arredondamento de quantidade e preço, e autorização em saldo insuficiente. Ruptura inclui saldo <= 0; baixo é saldo positivo <= mínimo; reposição depende de ponto de pedido configurado. Registrar custo unitário histórico.

## Crédito e aging
Saldo da parcela = principal + encargos devidos − alocações válidas + reversões, observado contrato e política específica. Limite disponível considera todos os saldos exigíveis identificados por cliente, inclusive vencidos, e autorizações existentes. Atraso corrente usa data de referência e parcela ainda não liquidada. Faixas: 1–30, 31–60, 61–90 e acima de 90 dias; a vencer separado. Indicadores devem explicitar data de corte e denominador. O fluxo de renegociação, quitação antecipada, multa, juros e pagamento parcial precisa de aprovação jurídica/comercial antes de uso real.

## Integridade e revisão
Autorização, venda, baixa e emissão de títulos devem ocorrer com rollback integral ou evento inverso auditado. Relatórios cruzam por ID e status; cada forma tem linha própria, sem multiplicar vendas em agregações. Fechamento compara pagamentos aplicados com faturamento, mas nunca confirma transação bancária. Definir tratamento de cartão pendente, cancelamento pós-fechamento e recebimento de título por outro turno.
