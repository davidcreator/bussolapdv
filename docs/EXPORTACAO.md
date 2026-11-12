# Exportação de relatórios (Excel e PDF)

O PDV mostra números na tela; este documento trata do que sai da tela. **Todo
relatório do sistema pode ser exportado em `.xlsx` (Excel) e em `.pdf`**, com o
mesmo dado que a tela mostra — porque a tela e o arquivo leem a mesma consulta.

> Os arquivos exportados são **documento interno de conferência**. Não são nota
> fiscal, não substituem relatório contábil assinado e não confirmam liquidação
> de PIX ou cartão.

## Onde está o botão

No **cabeçalho do cartão** de cada tela de consulta há o botão **Exportar**, com
um menu de dois itens:

| Tela | Relatório exportado | Abas do Excel | Filtro que a tela aplica |
| --- | --- | --- | --- |
| Fechamento | Fechamento do caixa | Resumo do dia, Por forma de pagamento, Por operador, Conciliação, Turnos de caixa, Pagamentos pendentes, Estoque por situação, Crediário | data de negócio escolhida |
| Vendas | Vendas do período | Cupons | período (De/Até) da tela |
| Produtos | Catálogo e estoque | Produtos | busca digitada |
| Auditoria | Trilha de auditoria | Eventos | últimos 500 eventos |
| Caixa | Fechamento do turno | Caixa e dinheiro, Movimentos do turno, Contagem por denominação | turno aberto (ou `--turno <id>`) |
| Clientes | Clientes | Clientes | busca digitada |
| Crediário | Crediário | Títulos | caixa "incluir títulos já recebidos" |
| Estoque | Estoque | Produtos, Resumo por situação | busca digitada |

O botão **só aparece para quem tem a permissão `EXPORTAR_DADOS`**. Na matriz
padrão: Admin Master, Admin, Gerente e Contabilidade têm; Atendente não tem. A
permissão é conferida de novo no serviço, no momento de gravar — esconder o
botão é conforto visual, não segurança.

Depois de salvar, o programa oferece **abrir a pasta** do arquivo. Por padrão o
nome sugerido aponta para:

| Sistema | Pasta |
| --- | --- |
| Windows | `%LOCALAPPDATA%\BussolaPDV\relatorios\` |
| Linux | `~/.local/share/bussola-pdv/relatorios/` |
| Qualquer | `$BUSSOLA_DADOS/relatorios/` |

## Linha de comando

Útil para fechar o dia em lote, agendar em `.bat`/cron ou gerar o arquivo em um
servidor sem tela:

```bash
# fechamento do dia em PDF (senha via variável de ambiente)
export BUSSOLA_SENHA='sua-senha'
bussola exportar --banco dados/pdv.db --tipo fechamento --data 2026-11-11 \
    --formato pdf --login master

# período de vendas em Excel, direto na pasta de relatórios
bussola exportar --banco dados/pdv.db --tipo vendas --de 2026-11-01 --ate 2026-11-11 \
    --formato xlsx --login gerente

# conferência do turno aberto (o mesmo relatório do botão Exportar do Caixa)
bussola exportar --banco dados/pdv.db --tipo turno --formato xlsx --login master

# carteira de clientes e posição de estoque
bussola exportar --banco dados/pdv.db --tipo clientes --formato pdf --login gerente
bussola exportar --banco dados/pdv.db --tipo estoque --formato xlsx --login gerente

# crediário incluindo títulos já recebidos
bussola exportar --banco dados/pdv.db --tipo crediario --incluir-pagos --login contador

# outras opções: --destino arquivo-ou-pasta, --busca TEXTO (catálogo, clientes,
# estoque), --limite N (auditoria), --turno ID (turno específico, inclusive fechado)
```

No Windows (executável empacotado), o mesmo comando sai como
`BussolaPDV-console.exe exportar ...`. Sem `--destino`, o arquivo vai para a
pasta de relatórios do usuário. A senha também pode ser digitada no terminal, se
`BUSSOLA_SENHA` não estiver definida.

## O que vai no Excel

Um `.xlsx` comum, gerado sem `openpyxl`/`pandas` (o formato é um ZIP de XMLs):

- **aba `Resumo`**: título, loja/CNPJ/endereço, filtros usados, data/hora de
  geração, indicadores, avisos e o escopo do relatório ("posição corrente; não
  reage a filtro de data", por exemplo);
- **uma aba por tabela**, com cabeçalho em negrito, **filtro automático**,
  **painel congelado** (cabeçalho sempre visível), larguras por coluna e nota de
  rodapé;
- **moeda é número, não texto**: `R$ 164,49` está gravado como `164,49` com
  formato de moeda — dá para somar, ordenar e montar tabela dinâmica;
- **data é data**: gravada como data do Excel (formato `dd/mm/aaaa`), não como
  texto;
- metadados do arquivo (título, empresa) preenchidos.

O que ele **não** tem, de propósito: fórmulas, gráficos, imagens, células
mescladas e formatação condicional. Nada disso é necessário para conferir um
fechamento e cada item aumentaria bastante a chance de gerar arquivo inválido.

## O que vai no PDF

A4, margens de 14 mm, gerado pelo Qt que já vem com o programa:

- cabeçalho com a loja, o título do relatório e o subtítulo;
- identificação (CNPJ, telefone, endereço) e filtros, em tabela;
- indicadores em faixa destacada (cupons, faturamento, ticket, conciliação);
- uma seção numerada por tabela, com cabeçalho azul, linhas zebradas e valores
  monetários alinhados à direita;
- avisos em vermelho, escopo em cinza e a frase "Documento interno — não fiscal";
- **rodapé em todas as páginas** com loja, data/hora de geração e `página X de Y`.

Sem assinatura digital, sem PDF/A e sem marca d'água: é comprovante de
conferência, não documento fiscal.

## Permissão, auditoria e privacidade

Exportar é **tirar dado da loja**. Por isso:

1. exige a permissão `EXPORTAR_DADOS` (mesma matriz da área administrativa);
2. grava um evento `DADOS_EXPORTADOS` na trilha append-only com **quem**, **quando**,
   **título do relatório**, **formato**, **quantidade de linhas**, **filtros** e
   **nome do arquivo**. É assim que se responde "quem levou o fechamento do dia 12?";
3. não envia nada pela rede: o arquivo é gravado onde você mandar.

Quem não tem a permissão recebe `AutorizacaoNegada` (`O perfil Atendente não tem
permissão para EXPORTAR_DADOS.`) e o arquivo não é criado.

## Conferindo o que foi gerado

Checklist rápido para o arquivo que vai para o contador:

- [ ] O total do PDF é **igual** ao total da tela de fechamento e ao do cupom
      somado no dia? (Se divergir, não é arredondamento: é bug — abra uma issue.)
- [ ] No Excel, a coluna de valores soma o mesmo que o total? (Se a célula estiver
      como texto, o formato não foi respeitado.)
- [ ] A data do relatório é a **data comercial** do dia escolhido, não a data em
      que você clicou em exportar.
- [ ] "Pagamentos pendentes" está vazio ou foi conferido? PIX/cartão nascidos
      `PENDENTE` não compõem faturamento conciliado.
- [ ] O rodapé diz "Documento interno — não fiscal"? Ele não deve ser arquivado
      como documento fiscal.

Arquivos de exemplo, gerados a partir da base fictícia de demonstração, ficam em
[`docs/exemplos/`](exemplos/): `fechamento-exemplo`, `turno-exemplo` e `estoque-exemplo`, cada um em
`.pdf` e `.xlsx`.
Para regerá-los:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src python3 ferramentas/gerar_exemplos.py
```

## Limites conhecidos

- **Cliente sai com documento mascarado** (`*******4725`), como na tela: não há
  opção de exportar CPF/CNPJ completo — decisão de privacidade (LGPD), não falta
  de recurso.
- **As telas de Clientes, Crediário e Estoque só consultam e exportam.** Cadastrar
  cliente, receber título e lançar entrada continuam na API/serviço.
- **Não há agendamento.** Para fechar todo dia automaticamente, chame o CLI no
  Agendador de Tarefas do Windows apontando para `BussolaPDV-console.exe`.
- **A planilha não tem gráficos nem fórmulas.** Quem quiser tendência monta a
  tabela dinâmica em cima dos dados.
- **O PDF não é editável nem assinado.** Para assinar, use o certificado da loja
  por fora (o projeto não tem certificado de assinatura).
- **Impressão em térmica** não foi homologada; o PDF foi pensado para A4 e para
  leitura em tela.
- **Catálogo grande** gera planilha grande: o Excel aguenta, mas acima de ~50 mil
  linhas vale filtrar por busca antes de exportar.

## Como isso é testado

`tests/test_exportacao.py` (41 testes), `tests/test_ui_exportacao.py` (13),
`tests/test_exportacao_modulos.py` (27) e `tests/test_ui_telas_modulos.py` (12):

- o `.xlsx` é **aberto por `openpyxl`** e conferido célula a célula (moeda como
  número, data como data, texto com `&`/`<` intacto, aba única e saneada,
  cabeçalho congelado, filtro automático, planilha sem linhas);
- o `.pdf` é **lido por `pypdf`**: cabeçalho `%PDF`, `%%EOF`, título presente,
  rodapé com "página X de Y" e paginação em relatório de 400 linhas;
- o relatório de fechamento exportado tem os **mesmos valores** do relatório que a
  tela mostra;
- exportação exige permissão, grava o evento e **mantém a cadeia de hashes íntegra**;
- o CLI falha com código 2 em senha errada, perfil sem permissão, banco
  inexistente e falta de `--data`, sem criar arquivo;
- o botão aparece só para quem pode, oferece os dois formatos e corrige a
  extensão quando o usuário não digita;
- **clientes, crediário, estoque e turno** também são abertos por `openpyxl`/`pypdf`, e a tela
  compara célula a célula com o relatório (mesma consulta, mesmo número);
- o saldo do crediário conta título **PARCIAL** (regressão: a primeira versão só somava `ABERTO`);
- `--tipo turno` sem turno aberto sai com código 2 e mensagem clara, sem criar arquivo.

`openpyxl` e `pypdf` são dependências **de teste** (extra `dev`), não de execução:
o programa não precisa delas para gerar os arquivos.
