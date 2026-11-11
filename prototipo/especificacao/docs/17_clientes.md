# 10_CLIENTES — cadastro e validações de teste

Arquivo `PDV_Empresa_clientes_v1.xlsx`. A tabela `tblClientes` fica em B7:Q207, com 200 linhas. É um protótipo sem proteção efetiva; não use dados pessoais reais.

## Campos
B código (texto); C nome; D CPF/CNPJ numérico, como texto e sem pontuação; E telefone com DDD, como texto e sem símbolos; F e-mail; G endereço; H limite de crédito; M ativo (S/N); Q observações. Esses são campos de entrada, identificados por fundo claro e borda âmbar. E, F e G são opcionais; os campos de entrada não podem sobrescrever fórmulas.

I saldo devedor, J limite disponível, K maior atraso, L classificação, N verificação do cadastro, O nome normalizado e P verificação de documento são calculados. Filtre pelas setas do cabeçalho; painéis congelados em C8. O guia lateral fica em S:Y e pode exigir rolagem horizontal.

## Duplicidade e formato
- Código e documento são comparados como texto e possuem validação para evitar duplicidade no intervalo previsto.
- Nome é normalizado para maiúsculas, sem espaços de borda, espaços repetidos ou espaço não separável; a validação consulta os outros registros normalizados e rejeita duplicidade. A coluna N também sinaliza duplicatas após recálculo. A regra **não** ignora acentos, abreviações, pontuação, erros de digitação ou caracteres Unicode equivalentes.
- Homônimos reais existem: a exigência de nome único pode impedir cadastros legítimos. O correto em um sistema de produção é permitir nomes iguais com ID único e documento verificado, mas esta versão mantém a regra solicitada. A equipe deverá definir procedimento de exceção antes de operar.
- CPF deve ter 11 dígitos e CNPJ numérico 14 dígitos, sem pontuação, em texto; P verifica o formato e os dígitos verificadores e rejeita sequências de um único dígito. A validação de entrada confere comprimento, caracteres e duplicidade; a conferência dos dígitos ocorre por fórmula após a entrada. Ela NÃO consulta Receita Federal nem garante titularidade ou existência. **CNPJ alfanumérico não é suportado**.
- Telefone, se informado, deve ter DDD + 8 ou 9 dígitos (10 ou 11 no total), como texto, sem símbolos. E-mail, se informado, recebe apenas uma verificação simples de estrutura, não confirmação de existência. Código e documento não são validados por autenticação externa.

A verificação de cadastro só considera uma linha iniciada se B, C ou D tiver conteúdo. Uma linha preenchida apenas com telefone, endereço ou observação pode passar despercebida; não deixe registros parciais. Validação de dados do Excel pode ser contornada por colagem, macros ou remoção de células; não garante ausência absoluta de duplicidade ou erro. A planilha não está protegida.

## Consulta de crédito
I soma `09_CREDIARIO` por código de cliente, considerando apenas títulos cuja verificação Q esteja OK. J = limite − saldo; K = maior atraso de títulos válidos. L sinaliza revisão do cadastro, títulos em revisão, inativo, vencido, limite esgotado ou disponível. Valores são apenas indicativos: o PDV não consulta essa classificação nem bloqueia venda a prazo. A aba de crediário não verifica titularidade do código, e títulos com código incorreto ou ausente podem escapar à consulta. Não conceda crédito com base neste protótipo.

## Fórmulas de consulta
O8: `=SE(C8="";"";MAIÚSCULA(ARRUMAR(SUBSTITUIR(C8;CARACT(160);" "))))`.
I8: `=SE(B8="";"";SOMASES('09_CREDIARIO'!$N$8:$N$207;'09_CREDIARIO'!$D$8:$D$207;B8;'09_CREDIARIO'!$Q$8:$Q$207;"OK"))`.
J8: `=SE(B8="";"";SE(ÉNÚM(H8);H8-I8;""))`.
P8 verifica CPF/CNPJ pelo cálculo dos dígitos, usando SOMARPRODUTO, EXT.TEXTO, LIN e MOD; N8 consolida alertas e L8 combina cadastro e crediário. Consulte as fórmulas completas nas células; elas são mantidas em formato interno de função em inglês e o Excel traduz sua exibição.

## Testes manuais pendentes
1. Em cópia, insira dois nomes fictícios diferentes e depois tente inserir o primeiro nome com diferença apenas de maiúsculas ou espaços: a validação deve rejeitar. Teste também colagem e confira a sinalização após recálculo.
2. Tente duplicar código e documento, telefone com letras, e-mail sem @ e limite negativo. Confira mensagens de validação e indicadores. CPF/CNPJ plausível com dígitos errados deve resultar em `INVÁLIDO`.
3. Em dados inteiramente fictícios, vincule um título de teste com verificação OK ao mesmo código; confira soma do saldo e limite disponível. Gere título em revisão e verifique `REVISAR CRÉDITO`.
4. Confira no Excel os filtros, a legibilidade, o recálculo e a impressão. B1:Q30 imprime apenas o início do cadastro, não todas as linhas. Os testes não foram executados no Excel nesta geração.

## Pendências para produção
Integração com PDV e validação autoritativa de cliente, suporte ao CNPJ alfanumérico, política de homônimos, confirmação externa de documento, controles LGPD e acesso, trilha de auditoria, proteção contra alteração, backup seguro, regras de aprovação e bloqueio de crédito, expansão dinâmica de faixas e homologação. Nome e CPF/CNPJ são dados pessoais: mantenha este arquivo apenas com dados fictícios.
