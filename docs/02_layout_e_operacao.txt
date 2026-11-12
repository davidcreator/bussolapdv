# Layout e operação — fase 1

## Medidas atuais
Todas as 16 abas: coluna A = 3, vazia; B:H, J:Z e AB:AF = 12; I e AA = 3. Alturas em pontos: linha 1 = 32, 2 = 20, 3 = 8, 4 = 20, 5 = 18, 6 = 8. Congelamento em C7 fixa linhas 1–6 e colunas A–B, não a linha 7. Área de impressão B1:AF50, A4 paisagem, uma página de largura, altura livre.

## Áreas
B1:H1: marca provisória. B2:H2: área reservada ao logo. J1:Z1: menu; J2:Z2: submenu informativo. AB1:AF1: empresa e versão provisórias. B3:AF3: vazias com borda inferior cinza. B4:H4: título; B5:H5: descrição provisória; linha 6 vazia. Tabelas e dados serão criados nas fases seguintes.

Menu: J1:K1 PDV; L1:M1 Vendas; N1:O1 Caixa; P1:Q1 Estoque; R1:S1 Crediário; T1:U1 Fechamento; V1:W1 Dashboard; X1:Z1 MENU. As entradas são hiperlinks, não ações de venda. Para acessar Vendas, reexiba primeiro a aba oculta. O submenu não executa ações.

## Conferir no Excel
1. Abra `PDV_Empresa_v1.0_fase1.xlsx`. Nas guias visíveis, selecione o número de uma linha e acesse Página Inicial > Formatar > Altura da Linha para conferir os valores. Use Largura da Coluna para conferir A e as demais.
2. Em Exibir > Congelar Painéis, verifique o congelamento ao rolar. A célula C7 define a posição.
3. Em Arquivo > Imprimir, confira A4, orientação paisagem e uma página de largura.
4. Para reexibir uma aba comum, clique com o botão direito numa guia > Reexibir. A aba 15_LISTAS é muito oculta e não aparece nesse diálogo; sua alteração exige editor VBA ou ferramenta compatível. Evite modificá-la sem autorização.
5. Para colocar o logo posteriormente, use Inserir > Imagens; posicione próximo de B1 e ajuste aproximadamente para 150 × 40 pixels mantendo a proporção. Pontos de altura da linha não equivalem diretamente a pixels em todas as telas.

## Cores previstas
Primária #1F3864; secundária #2F5597; destaque #FFC000; sucesso #00B050; erro #C00000; fundo de área #F2F2F2; bordas #D9D9D9; texto #262626. Os estilos de tabelas, entradas e alertas serão implementados nas respectivas fases.

## Backup
Antes de alterar, salve uma cópia pelo Excel em Arquivo > Salvar como, por exemplo `PDV_20261110.xlsx`, substituindo a data pela do backup. Guarde-a em local separado e restrito. Proteja dados pessoais conforme a política da empresa.
