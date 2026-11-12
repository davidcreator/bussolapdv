# 03_PDV — frente de caixa de teste

Arquivo: `PDV_Empresa_frente_caixa_v1.xlsx`. Esta revisão organiza a operação em quatro etapas, preservando as posições das células usadas pelo módulo VBA existente. Visual inspirado nas referências: grafite, turquesa, cinza para cálculos e âmbar para entradas. Zoom inicial 80%; ajuste em Exibir > Zoom conforme sua tela.

## Orientação visual
- B7:I8 — 01 Identifique a venda: operador em C8 e cliente em G8. Ambos são texto livre; não há autenticação ou vínculo aos cadastros.
- B10:I26 — 02 Lance produtos: linhas 12–26, código em B, quantidade em E e desconto percentual opcional em G. C, D, F, H e I são cálculos. Digite código do produto; busca por código de barras ainda não foi implementada.
- B28:C28 — total calculado, soma dos totais dos itens arredondados.
- B30:I33 — 03 Pagamento: C/D, E/F e G/H são três pares de forma e valor. I31 mostra o excesso aritmético e B33 informa falta, troco ou alerta.
- B35:I35 — 04 Finalizar: orientação para executar a macro, não é botão clicável. K:Q — guia de preenchimento, conferência e alertas.

Células com entrada têm fundo amarelo-claro e borda âmbar; campos calculados são cinza. Descrição não encontrada, quantidade ausente/inválida e saldo insuficiente para o total do mesmo código no carrinho recebem alerta vermelho. As cores são auxiliares: faça também a leitura das mensagens. Não há proteção de planilha aplicada; evite sobrescrever fórmulas.

## Venda fictícia
1. Trabalhe em cópia da planilha. Para usar a macro, abra no Excel Windows, salve como `.xlsm`, pressione Alt+F11 e importe `ModuloPDV.bas`; salve novamente. Habilite macros somente se confiar no código. O arquivo `.xlsx` entregue NÃO inclui macro incorporada.
2. Em `03_PDV`, preencha C8 com operador fictício e G8 com cliente fictício.
3. Em B12 informe P001 e em E12, 1. Em B13 informe P002 e em E13, 2. Deixe desconto em branco. Confira total R$ 27,00.
4. Em C31 selecione Dinheiro; em D31 digite 30. Confira troco R$ 3,00. Alternativamente, para pagamento dividido, informe Dinheiro R$ 10,00 e PIX R$ 17,00: o resultado deve ser PAGAMENTO OK. O PIX é apenas registro e deve ser confirmado fora do protótipo.
5. Pressione Alt+F8 > `FinalizarVenda` > Executar. O carrinho e pagamentos serão limpos após o sucesso. Confira venda, itens, pagamentos e movimentos nas abas ocultas, e salve a cópia. A macro não foi executada nem homologada neste ambiente.
6. Se ocorrer erro após início da gravação, NÃO execute novamente: feche sem salvar e restaure a cópia de segurança, pois pode haver gravação parcial.

## Fórmulas e comportamento
C28: `=SOMA(H12:H26)`. H12: `=SE(OU(B12="";E12="");0;ARRED(E12*F12*(1-G12);2))`; I31: `=MÁXIMO(0;SOMA(D31;F31;H31)-C28)`. A mensagem B33 também compara o excesso com o dinheiro entregue, evitando apresentar como troco válido um excedente superior ao dinheiro. Ela não verifica todos os campos de pagamento; a macro executa validações adicionais ao finalizar.

## Limitações críticas
O sistema não oferece caixa aberto por operador, desconto máximo ou autorização de gerente, PIN, acesso por perfil, recebimento comprovado de PIX, cartão, venda a prazo, cancelamento, estorno, auditoria, emissão fiscal ou concorrência segura. A macro não lê os parâmetros cadastrados. O desconto de teste admite até 100%; o total da venda deve ser positivo. Não usar para operações reais ou dados pessoais. O desenho foi verificado estruturalmente; a aparência, recálculo, impressão e execução da macro precisam ser testados no Excel.
