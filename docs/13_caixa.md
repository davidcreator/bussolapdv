# 06_CAIXA — controle manual de turnos para teste

Arquivo: `PDV_Empresa_caixa_v1.xlsx`. A aba é uma bancada para testes fictícios; não está pronta para produção. A rotina de PDV NÃO registra automaticamente movimentos de caixa, e os campos são manuais. Faça cópia de segurança antes de cada teste.

## Mapa e orientação visual
- B:V, linhas 7–57: `tblCaixa` — até 50 turnos.
- X:AH, linhas 7–307: `tblMovCaixa` — até 300 movimentos de caixa.
- AJ:AN, linhas 7–257: `tblContagemCaixa` — até 250 registros de denominação.

Use a barra de rolagem horizontal para acessar os três blocos. Cabeçalhos têm filtros nativos; para consultar um turno, filtre ID_Turno nos três blocos. Em branco/amarelo-claro com borda âmbar: digitação; cinza: cálculo. A aba não está protegida. Não sobrescreva fórmulas, não apague histórico. As áreas de dados são largas para manter as três tabelas separadas e auditáveis; a área de impressão inicial B1:V25 cobre apenas parte dos turnos, não os movimentos ou contagens.

## 1. Abrir turno em B:V
Na primeira linha vazia, informe ID_Turno único em B (por exemplo T001), data C, identificador do caixa D, turno E, operador F, hora de abertura G, fundo inicial H e status Aberto em Q. Os campos I:P, T e U são calculados. Há aviso se dois turnos com mesmo caixa estiverem marcados como abertos, mas NÃO há bloqueio efetivo; não inicie outro turno para o mesmo caixa antes de fechar o anterior.

## 2. Movimentações X:AH
Em cada linha informe ID_Mov único em X, o mesmo ID_Turno em Y, data Z, hora AA, tipo AB, forma AC, valor positivo AD, operador AE, documento AF e observações AG. AH informa problemas de vínculo, identificação ou preenchimento. Escolha:
- Venda: valor efetivamente aplicado por forma, sem troco; divida pagamentos em linhas por forma.
- Recebimento: recebimento de título anterior; não conta como nova venda.
- Suprimento: dinheiro adicionado à gaveta.
- Sangria: dinheiro retirado da gaveta.
- Estorno: devolução de dinheiro ou reversão por outra forma, registrada com valor positivo na forma original. Este registro é apenas para teste; não estorna a venda, estoque ou crediário.

Suprimento e sangria exigem forma Dinheiro na conferência. Não duplique uma transação. Não há importação nem conciliação automática com 04_VENDAS e 07_PAGAMENTOS; um lançamento manual errado produz resultado errado. Registre apenas movimentações do turno correto, verifique data, operador e documento. A fórmula não valida automaticamente se a data/hora do movimento coincide com o turno, se ele está aberto ou se já foi lançado no PDV.

## 3. Contagem de dinheiro AJ:AN
Informe ID_Turno em AJ, denominação em AK e quantidade inteira de cédulas/moedas em AL. AM calcula o total e AN sinaliza dados incompletos, turno inexistente ou denominação repetida para o mesmo turno. Use uma linha por denominação, inclusive moedas. Para registrar contagem de zero, informe uma denominação e quantidade zero. A contagem por denominação soma ao dinheiro contado do turno; não digite total manualmente.

## 4. Fechamento
Após revisar todos os movimentos e contagem, preencha hora de fechamento R e conferente S no turno; altere Q para Fechado. Verifique U e diferença P. Verde: conferido sem diferença ou turno aberto; amarelo: diferença não zero até R$ 5,00; vermelho: diferença acima de R$ 5,00 ou outros alertas. Uma diferença de R$ 10 aparece em vermelho. Alertas não impedem fechar ou editar: não são controle de segurança. Guarde comprovação externa e backup; a conferência não encerra, congela nem assina o turno automaticamente.

## Fórmulas e conceitos
Para a linha 8:
- `N8 = H8+I8-J8+K8+L8-M8`: fundo + suprimentos − sangrias + vendas em dinheiro + recebimentos em dinheiro − estornos em dinheiro; a fórmula real retorna vazio se não houver ID.
- `O8 = SOMASE($AJ$8:$AJ$257;B8;$AM$8:$AM$257)`, quando há linhas de contagem; senão permanece vazio.
- `P8 = ARRED(O8-N8;2)`, somente quando há contagem.
- `T8` soma vendas em todas as formas e subtrai estornos; não soma fundo, suprimentos, sangrias ou recebimentos de título. Não equivale a dinheiro em gaveta.
- `SOMASES` apura movimentos filtrando ID de turno, tipo e forma. Cada faixa é fixa; ultrapassar os limites citados não é seguro.

## Teste manual em cópia
1. Cadastre T001, caixa C01, data e horas fictícias, operador, fundo de R$ 100 e status Aberto.
2. Lance venda em dinheiro R$ 50, suprimento R$ 20 e sangria R$ 10 com IDs diferentes e mesmo turno. Esperado: R$ 160. Lance também venda PIX R$ 30; o esperado em gaveta continua R$ 160 e vendas de todas as formas são R$ 80.
3. Contagem: 1 cédula de R$ 100, 1 de R$ 50 e 1 de R$ 10. Contado R$ 160; diferença R$ 0. Preencha fechamento e conferente; status Fechado deve indicar CONFERIDO.
4. Em outra cópia, conte R$ 150: diferença −R$ 10 e aviso vermelho. Teste R$ 157 para diferença −R$ 3 e aviso amarelo.
5. Adicione dois turnos Abertos com caixa C02; confira aviso de duplicidade de caixa. Remova filtros para consultar tudo.

## Limitações críticas
Não integra PDV, formas reais, recebimento de crediário, comprovantes ou fechamento diário. Não existe PIN seguro, validação forte de turno, trava contra edição após fechamento, trilha de auditoria, proteção contra duplicação por colagem, autenticação, segurança, sincronização entre caixas nem atualização automática de data/hora. Datas e horas são digitadas como valores estáticos. Cada lançamento deve ser verificado manualmente; os avisos não impedem gravação. O arquivo foi verificado estruturalmente, mas fórmulas, listas, cores e cenários ainda precisam ser testados no Excel Windows. Não usar em produção.
