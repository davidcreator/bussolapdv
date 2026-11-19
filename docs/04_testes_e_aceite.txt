# Testes e aceite

## Fase 1 — verificar no Excel
- [ ] Alturas 32/20/8/20/18/8 nas linhas 1–6 e coluna A = 3, vazia, em todas as abas.
- [ ] Linha 3 sem conteúdo, borda inferior B3:AF3; primeiro conteúdo da página em B4; linha 6 vazia.
- [ ] C7 congela linhas 1–6 e colunas A–B; links das abas visíveis funcionam.
- [ ] Impressão A4, paisagem, uma página de largura; 16 abas e estados de visibilidade corretos.

Verificação automatizada de estrutura: 16 abas, altura da linha 1, largura da coluna A, congelamento e estados de visibilidade conferidos na geração. A conferência visual e de impressão no Excel pelo usuário permanece pendente.

## Aceite funcional final — não executado
- [ ] Venda de três itens em dinheiro e troco correto.
- [ ] Pagamento dividido dinheiro + PIX fecha.
- [ ] Estoque insuficiente bloqueado ou autorizado conforme política auditável.
- [ ] Desconto acima do limite exige autorização e gera registro.
- [ ] Crediário acima do limite bloqueado.
- [ ] Cancelamento preserva histórico e estorna estoque e crediário.
- [ ] Fechamento concilia pagamentos e faturamento líquido.
- [ ] Falta de R$ 10 no caixa aparece como divergência vermelha e registrada.
- [ ] Filtro por operador retorna somente suas vendas.
- [ ] Parcela vencida apresenta atraso e encargos corretos.
- [ ] Nenhum erro de fórmula ou valor cortado nos cenários testados.
- [ ] Layout obrigatório conferido em todas as abas.

Massa de teste prevista para bloco em 00_INSTRUCOES, ainda não criada: 15 produtos em quatro categorias, cinco clientes, 20 vendas em três dias, três formas, uma venda cancelada e uma venda a prazo em três parcelas. Testes devem usar dados fictícios, sem dados pessoais reais.
