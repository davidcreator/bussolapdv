# Plano de testes e critérios de aceite

> **Projeto:** Bússola Sistema PDV Open Source

Estado: planejamento; nenhum teste da aplicação desktop foi executado.

## Massa fictícia
Pelo menos 15 produtos de quatro categorias, com estoque normal, baixo e zero; cinco clientes incluindo um com limite esgotado e um com parcela vencida; 20 vendas em três dias, três formas de pagamento, uma cancelada e uma a prazo de três parcelas. Use geradores e identificadores fictícios, sem dados reais.

## Aceite funcional
- [ ] Venda de três itens em dinheiro com troco para R$ 100; valores em centavos conferem.
- [ ] Split dinheiro + PIX fecha sem excedente não monetário; PIX pendente não é confundido com comprovado.
- [ ] Estoque insuficiente bloqueado ou excepcionalmente autorizado com evidência.
- [ ] Desconto além do limite requer autenticação de gerente e evento de auditoria.
- [ ] Venda a prazo acima do limite e com atraso proibido é bloqueada.
- [ ] Cancelamento/devolução preserva venda, reverte estoque e dívida e trata pagamentos existentes sem duplicidade.
- [ ] Fechamento por forma, operador e turno concilia com faturamento líquido; recebimento de dívida antiga não é nova venda.
- [ ] Caixa com R$ 10 faltando apresenta diferença −R$ 10 e histórico de conferência.
- [ ] Filtros de relatório isolam operador, datas e status de forma consistente.
- [ ] Parcela vencida, pagamento parcial, quitação, aging e encargos seguem regra aprovada.
- [ ] Autorização, acesso por perfil e tentativas indevidas são testados; segredos não aparecem em logs.
- [ ] Aplicação funciona offline, com foco por teclado, texto legível e apresentação consistente em DPI distintos.

## Integridade e falhas
- [ ] Duplo clique e repetição com mesma chave de idempotência não criam duas vendas.
- [ ] Injete falha após cada etapa de gravação: venda, itens, pagamentos, movimentos, parcelas e auditoria devem sofrer rollback conjunto.
- [ ] Teste falha na inicialização, disco cheio, interrupção e reinício; banco íntegro e mensagem apropriada.
- [ ] Tente abrir dois turnos para o mesmo caixa e concorrer por último item; regra transacional é preservada.
- [ ] Não trate arquivo SQLite em compartilhamento de rede como solução multiestação.
- [ ] Faça backup com banco em uso, restaure em diretório isolado, execute verificação de integridade e compare registros críticos.
- [ ] Exercite migrações a partir de cada versão suportada, cópia de segurança e recuperação de falha.

## Limites, fiscal e release
- [ ] Cálculos de centavos, rateio com resíduos, quantidades fracionárias e datas de fim de mês têm casos parametrizados.
- [ ] CPF/CNPJ numérico e alfanumérico são testados de acordo com documentação oficial vigente; dados não são confundidos com titularidade validada.
- [ ] Release inclui licenças e notices de dependências, instruções, hashes, notas de atualização e suporte a rollback.
- [ ] Exista revisão de segurança, privacidade/LGPD e fiscal; nenhum recurso fiscal alegado sem homologação.
- [ ] Equipe operacional homologa em máquina representativa offline. Registre versão, data, responsável e evidências.
