# Aba 01_PARAMETROS — cadastro inicial

Arquivo: `PDV_Empresa_parametros_v1.xlsx`. Versão de trabalho para testes. A aba usa a identidade grafite/turquesa; branco com borda âmbar indica campo de entrada. Não há proteção aplicada nesta versão.

## 1. Empresa — B7:H8
1. Em B8, substitua `SUA EMPRESA` pelo nome fantasia. O nome aparece por fórmula em AB1 das abas.
2. Informe CNPJ em C8, endereço em D8, telefone em E8, nome/caminho do arquivo de logo em F8 e regime tributário em G8; observações em H8. CNPJ e telefone são texto, preservando zeros.
3. O caminho em F8 é informativo: não insere imagem automaticamente. Insira a imagem manualmente no Excel. CNPJ não tem validação de dígitos verificadores.

## 2. Operação — B12:E18
As células C e E contêm os valores associados aos rótulos imediatamente à esquerda. A data C12 é um exemplo fixo, 10/11/2026; substitua pela data correta de início. Moeda BRL; casas decimais 2; desconto operador 5%, gerente 15%; taxa de débito 2%, crédito 3,5%; prazo de crediário 30 dias; bloqueio por atraso 30 dias; juros de 1% ao mês e multa de 2%; taxa repassada N; chave PIX vazia; modo Teste. **São exemplos, não recomendações ou taxas reais.** Insira valores conforme contrato e política da empresa.

Percentuais recebem valores entre 0% e 100%. Casas decimais aceitam 0 a 4; prazos e dias aceitam 0 a 3650. Chave PIX é apenas cadastro: não cria cobrança nem confirma pagamento. O modo é informativo e não ativa controles de produção.

Nomes definidos: `nomeEmpresa`, `cnpjEmpresa`, `enderecoEmpresa`, `telefoneEmpresa`, `logoArquivo`, `regimeTributario`, `dataAberturaSistema`, `moedaSistema`, `casasDecimais`, `descontoOperador`, `descontoGerente`, `taxaDebito`, `taxaCredito`, `prazoCrediario`, `diasBloqueioAtraso`, `jurosMensal`, `multaAtraso`, `taxaRepassada`, `chavePix` e `modoOperacao`.

## 3. Formas de pagamento — B20:H31
`tblFormasPagamento`: código, descrição, tipo, taxa, prazo, indicador de geração de contas a receber e ativo. Foram cadastradas as 11 formas previstas, com valores exemplificativos. Débito e crédito têm prazo e taxa ilustrativos. O indicador de contas a receber refere-se ao crediário do cliente; recebíveis de adquirente devem ser tratados separadamente no modelo futuro. Tipos e S/N têm listas de validação. Alterar esses dados não altera automaticamente as formas aceitas pelo protótipo, que continua aceitando apenas Dinheiro e PIX.

## 4. Operadores e turnos
`tblOperadores` fica em B32:H38, com seis linhas inicialmente vazias. Informe matrícula, nome, perfil, ativo e observações. A coluna PIN está reservada, mas **não digite senhas reais**: não existe autenticação segura nem armazenamento protegido. O campo de perfil é apenas cadastro e não concede permissões.

Em B40:H43, ajuste Manhã, Tarde e Noite, horários, tolerância em minutos e ativo. Os horários são ilustrativos e não validam sobreposição, turnos que cruzam a meia-noite ou abertura de caixa. O PDV não utiliza essas configurações ainda.

## 5. Listas e validações
`15_LISTAS` permanece muito oculta e contém as listas nomeadas `listaSimNao`, `listaPerfis`, `listaTiposPagamento`, `listaRegimes`, `listaModo` e `listaMoedas`. Estão ligadas às validações configuradas nesta aba; listas não foram conectadas ao restante do arquivo. A validação de dados ajuda na digitação, mas pode ser contornada por colagem e não substitui controles na macro. Para expandir as listas, ajuste também os intervalos nomeados no Gerenciador de Nomes.

## 6. Teste de aceite em uma cópia
1. No Excel para Windows, altere B8 para `Loja Teste`; confira se AB1 das abas mostra esse nome. Restaure antes de usar outra base.
2. Em E13, digite `5%`; em uma cópia, tente `110%` e confira se a validação rejeita. Confira também S/N em H21 e perfil em D33.
3. Em B33:D33, cadastre matrícula e nome fictícios e escolha Operador; em F33 selecione S. Não preencha PIN.
4. Confira as 11 formas em B21:H31 e os três turnos em B41:H43. Modifique somente dados de teste.
5. Abra Arquivo > Imprimir e confira a área B1:I46 em A4 paisagem. Confira visualmente textos e larguras na versão instalada do Excel.

## Limitações e verificação
A geração verificou nomes definidos, tabelas, fórmulas de identidade e contagem de linhas de forma estrutural. Não houve execução, recálculo, impressão nem teste interativo de validações no Excel. A macro de venda não lê limites, taxas, parâmetros de operador/turno ou clientes desta aba. Nenhum campo cadastrado aqui garante o bloqueio descrito no projeto final. As próximas fases precisam integrar, validar e testar os parâmetros.
