# 15_LISTAS — organização e manutenção

Arquivo: `PDV_Empresa_listas_v1.xlsx`. A aba permanece **muito oculta** para evitar alteração acidental. Não é proteção de segurança; o arquivo continua sendo um protótipo, sem controles robustos de acesso. Não há macros incorporadas ao `.xlsx`.

## Estrutura
As listas existentes permanecem em B:L a partir da linha 8; não foram renomeadas nem tiveram seus valores movidos. Em N:R há um catálogo com nome definido, intervalo ativo, quantidade de células preenchidas, verificação e uso. A faixa amarela indica células que já fazem parte do nome definido; as cinzas estão fora da lista atual. O catálogo é documentação e diagnóstico, não modifica os nomes definidos.

| Coluna | Nome definido | Faixa inicial | Finalidade |
|---|---|---|---|
| B | listaSimNao | B8:B9 | S/N |
| C | listaPerfis | C8:C9 | Perfil cadastral de operador |
| D | listaTiposPagamento | D8:D15 | Tipos de pagamento dos parâmetros |
| E | listaRegimes | E8:E12 | Regimes cadastrais |
| F | listaModo | F8:F9 | Modo informativo |
| G | listaMoedas | G8:G8 | Moeda cadastral |
| H | listaDenominacoes | H8:H20 | Denominações da contagem de caixa, numéricas |
| I | listaTiposAuditoria | I8:I17 | Tipo de ocorrência |
| J | listaOrigensAuditoria | J8:J18 | Origem declarada da ocorrência |
| K | listaSeveridadeAuditoria | K8:K11 | Severidade declarada |
| L | listaStatusAuditoria | L8:L10 | Situação declarada |

Os textos são parte do contrato atual com validações, fórmulas e, em alguns casos, VBA. Por exemplo, `S`, `N`, `Concluída`, `Dinheiro` e outros valores são comparados literalmente em fórmulas. Mudar um texto pode quebrar regras mesmo que a lista aceite a mudança. **Adicionar forma de pagamento à lista não implementa seu processamento.** Alguns domínios de outras abas ainda são listas literais nas próprias validações e não estão centralizados aqui; consulte `01_PARAMETROS`, `03_PDV`, `06_CAIXA`, `09_CREDIARIO` e `11_ESTOQUE_MOV` antes de alterar regras.

## Verificação e limites
Cada célula ativa possui validação para valor único e não vazio; H exige número positivo e as demais exigem texto. Valores duplicados recebem destaque vermelho. O catálogo sinaliza CÉLULA VAZIA, DUPLICADA, PADRÃO ORIGINAL ou ALTERADA • REVISAR, comparando os valores originais desta versão. A comparação textual do Excel não distingue necessariamente maiúsculas/minúsculas. Não analisa células fora das faixas originais nem garante que uma alteração seja compatível com outras abas. A contagem usa CONT.VALORES (COUNTA), e a verificação usa CONTAR.VAZIO (COUNTBLANK), CONT.SE (COUNTIF), SOMARPRODUTO (SUMPRODUCT) e SE (IF).

A validação de dados pode ser contornada por colagem, exclusão ou VBA; não impede mudanças não autorizadas. O painel de integridade não substitui revisão de fórmulas, macros e testes.

## Mostrar e ocultar novamente no Excel Windows
1. Faça uma cópia de segurança do arquivo e abra a cópia no Excel para desktop.
2. Pressione Alt+F11. No Explorador de Projetos, localize o arquivo aberto e a planilha `15_LISTAS`. Se a janela de propriedades estiver oculta, pressione F4.
3. Na propriedade **Visible**, selecione `-1 - xlSheetVisible`. Volte ao Excel para consultar. Este procedimento usa o editor VBA, mas não exige adicionar ou executar uma macro.
4. Após a revisão, volte ao editor, selecione a mesma planilha e defina **Visible = 2 - xlSheetVeryHidden**. Salve. Não altere outras propriedades ou código. Nomes e valores só devem ser modificados por responsável técnico.

## Se for necessário ampliar uma lista
1. Em cópia de desenvolvimento, inventarie as fórmulas, validações e o módulo VBA que usam os valores. Decida como tratar registros históricos existentes; não renomeie opções críticas arbitrariamente.
2. Preencha a próxima célula na coluna, revise tipo e duplicidade e acesse **Fórmulas > Gerenciador de Nomes**. Selecione o nome correto, clique em Editar e amplie `Refere-se a` para a nova última linha. Essa alteração não é automática.
3. Amplie também a faixa de validação e formatação condicional da própria aba usando **Dados > Validação de Dados** e **Página Inicial > Formatação Condicional > Gerenciar Regras**. Atualize manualmente o catálogo N:R, suas fórmulas de integridade e o texto de documentação; eles guardam os limites e valores originais desta versão.
4. Revise cada validação consumidora, fórmulas e VBA. Execute os testes de todas as abas afetadas com dados fictícios. Se o novo valor alterar regras de negócio, implemente a lógica antes de disponibilizá-lo. O número de itens das listas de seleção pode ser limitado pelo contexto do Excel; confirme na instalação usada.

## Checklist de teste pendente no Excel
- [ ] Na cópia, reexibir a aba e conferir as 11 listas e seus nomes no Gerenciador de Nomes; ao fim torná-la muito oculta novamente.
- [ ] Alterar temporariamente um valor para outro já existente: conferir rejeição da validação; testar colagem e verificar a sinalização após recálculo.
- [ ] Limpar uma célula ativa em cópia descartável: verificar `CÉLULA VAZIA`; trocar valor por um texto distinto e verificar `ALTERADA • REVISAR`.
- [ ] Em cópia de desenvolvimento, ampliar uma lista conforme o procedimento e conferir a validação consumidora, catálogo e regras de negócio. Descartar a cópia após o teste.
- [ ] Verificar filtros/listas em parâmetros, caixa e auditoria e confirmar a aparência e impressão no Excel.

A estrutura e os nomes foram conferidos na geração, mas os testes de recálculo, validação interativa, exibição e impressão não foram executados no Excel. A área de impressão B1:R18 é larga e pode ficar pequena em uma página.
