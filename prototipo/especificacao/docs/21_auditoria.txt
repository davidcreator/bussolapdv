# 14_AUDITORIA — ocorrências e alertas de teste

Arquivo `PDV_Empresa_auditoria_v1.xlsx`. A aba está visível para consulta, com `tblAuditoria` em B7:R307 e 300 linhas pré-alocadas. Esta é uma área de registro MANUAL; não há trilha automática, imutável, autenticada ou apropriada para produção.

## Registro manual
1. Em uma cópia fictícia, informe ID único em B, data e hora estáticas em C:D, tipo em E, aba de origem em F, referência ou documento em G, operador em H, motivo em J, severidade em N, status em O e data do registro em Q. Os demais campos são opcionais, exceto o autorizador I para cancelamento, desconto acima do limite e ajuste de estoque.
2. `Valor Anterior`, `Valor Novo` e `Impacto R$` são informações manuais: o impacto não é calculado nem afeta financeiro ou estoque. Não escreva dados pessoais ou financeiros reais.
3. P é calculada e mostra OK ou o primeiro problema: dados incompletos, ID duplicado, domínio inválido, autorizador ausente ou dados inválidos. O nome do autorizador é texto livre e não comprova identidade ou aprovação; referência não é verificada automaticamente contra a aba de origem.
4. Use os filtros da linha 7 por tipo, referência, operador, status, severidade ou verificação. O guia e o painel lateral estão em T:AA e podem exigir rolagem horizontal.

As listas ficam na aba muito oculta `15_LISTAS` e usam os nomes `listaTiposAuditoria`, `listaOrigensAuditoria`, `listaSeveridadeAuditoria` e `listaStatusAuditoria`. As validações não são uma barreira de segurança e podem ser contornadas por colagem. A verificação P confere também os valores de domínio após a entrada.

## Alertas atuais
O painel T:AA conta ocorrências abertas/em análise e registros manuais com problemas, além de alguns alertas existentes em itens, vendas, pagamentos, estoque, entradas, crediário, clientes e diferenças de caixa. Ele mostra o estado atual das células de origem, sem filtro por período. As contagens são listas explícitas de status implementados; novos tipos de alerta exigem revisão das fórmulas. Caixa contempla apenas os dois textos de diferença, não todos os problemas de turno. Valores zero não comprovam ausência de fraude ou inconsistência.

**Alertas não criam linhas de auditoria automaticamente.** Registre e investigue manualmente em uma cópia de teste; guarde evidências de acordo com a política da empresa quando existir uma solução segura. A atualização do indicador pode remover uma contagem anterior, e ela não constitui histórico.

## Regras de cálculo
P8 usa `SE` (IF), `CONTAR.VAZIO` ou `CONT.SE`/`SOMARPRODUTO` conforme a verificação, e compara campos, listas e datas. Consulte a fórmula completa na célula. Exemplos de indicadores: vendas com divergência = `CONT.SE('04_VENDAS'!$N$8:$N$507;"DIVERGÊNCIA")`; títulos em revisão = `CONT.SE('09_CREDIARIO'!$P$8:$P$207;"REVISAR")`. As faixas são fixas às capacidades de cada protótipo; dados fora delas não entram nas contagens.

## Testes manuais pendentes no Excel
1. Em cópia fictícia, registre ocorrência de ajuste de estoque com campos obrigatórios, mas sem autorizador: P deve informar AUTORIZADOR AUSENTE. Preencha um nome fictício e recalcule: deve indicar OK se os demais campos forem válidos.
2. Tente um ID duplicado; teste também colagem de ID duplicado e confira o alerta. Insira data de registro anterior à ocorrência e confira DADOS INVÁLIDOS.
3. Em cópia descartável, gere uma divergência aritmética em pagamento ou venda na aba de origem e confira o contador lateral. Corrigir a origem deve alterar o contador, mas não gerar ou apagar uma linha de auditoria.
4. Confira filtros, cores e impressão. A área de impressão B1:R30 inclui apenas parte dos registros e não inclui o painel lateral. Nenhum desses testes foi executado no Excel nesta geração.

## Pendências antes de produção
Registro automático no ato da operação, eventos completos de antes/depois, identificação autenticada, permissões reais, data/hora confiável e imutável, proteção contra exclusão/alteração, armazenamento e retenção seguros, evidências, privacidade/LGPD, concorrência, recuperação, testes e homologação. O módulo VBA atual não grava nesta aba. Até que esses controles existam, a planilha não é uma auditoria confiável.
