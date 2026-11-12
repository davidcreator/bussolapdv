from openpyxl import load_workbook
from openpyxl.styles import Font,PatternFill,Border,Side,Alignment,Protection
from openpyxl.worksheet.table import Table,TableStyleInfo
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import FormulaRule
from openpyxl.comments import Comment
from openpyxl.utils import get_column_letter
w=load_workbook('PDV_Empresa_movimentos_v1.xlsx');s=w['12_ENTRADAS'];s['B4']='ENTRADAS DE MERCADORIAS';s['B5']='TESTE MANUAL • uma linha por item • estoque é atualizado somente por movimento válido.';s.freeze_panes='C8';s.sheet_view.zoomScale=80
headers=['ID_Entrada','Data','Fornecedor','CNPJ Fornecedor','Nº NF','Código Produto','Quantidade','Custo Unitário','Total Produtos','Frete Alocado','Custo Final Unitário','Markup %','Preço Sugerido','Atualiza Estoque?','Operador','Qtd Movimento OK','Diferença Qtd','Verificação','Observações','Descrição Atual']
widths=[18,15,25,21,17,19,16,18,19,18,22,15,19,20,21,20,19,28,30,30]
for col,(h,wd) in enumerate(zip(headers,widths),2):
 c=s.cell(7,col,h);c.fill=PatternFill('solid',fgColor='383838');c.font=Font(name='Segoe UI',size=10,bold=True,color='FFFFFF');c.alignment=Alignment(wrap_text=True,vertical='center');s.column_dimensions[get_column_letter(col)].width=wd
s.row_dimensions[7].height=32
inputs=(2,3,4,5,6,7,8,9,11,13,15,16,20)
for r in range(8,208):
 for col in range(2,22):
  c=s.cell(r,col);inp=col in inputs;c.fill=PatternFill('solid',fgColor='FFF9E6' if inp else 'EEF2F3');c.font=Font(name='Segoe UI',size=10,color='262626');c.alignment=Alignment(vertical='center');c.protection=Protection(locked=not inp)
  if inp:c.border=Border(bottom=Side(style='thin',color='D39700'))
 for col in (2,5,6,7):s.cell(r,col).number_format='@'
 s.cell(r,3).number_format='dd/mm/yyyy'
 for col in (9,10,11,12,14):s.cell(r,col).number_format='"R$" #,##0.00'
 for col in (8,17,18):s.cell(r,col).number_format='#,##0.000;[Red]-#,##0.000'
 s.cell(r,13).number_format='0.0%'
 # Mov table H doc, F product, E type, G qty, K status
 fs={10:f'=IF(B{r}="","",IFERROR(ROUND(H{r}*I{r},2),""))',12:f'=IF(B{r}="","",IFERROR((J{r}+K{r})/H{r},""))',14:f'=IF(B{r}="","",IFERROR(ROUND(L{r}*(1+M{r}),2),""))',17:f'=IF(B{r}="","",SUMIFS(\'11_ESTOQUE_MOV\'!$G$8:$G$2007,\'11_ESTOQUE_MOV\'!$H$8:$H$2007,B{r},\'11_ESTOQUE_MOV\'!$F$8:$F$2007,G{r},\'11_ESTOQUE_MOV\'!$E$8:$E$2007,"Entrada",\'11_ESTOQUE_MOV\'!$K$8:$K$2007,"OK"))',18:f'=IF(B{r}="","",IF(O{r}="S",ROUND(Q{r}-H{r},3),Q{r}))',19:f'=IF(COUNTA(B{r}:I{r},K{r},M{r},O{r}:P{r},T{r})=0,"",IF(OR(B{r}="",NOT(ISNUMBER(C{r})),D{r}="",F{r}="",G{r}="",NOT(ISNUMBER(H{r})),NOT(ISNUMBER(I{r})),O{r}="",P{r}=""),"DADOS INCOMPLETOS",IF(SUMPRODUCT(--($B$8:$B$207=B{r}))>1,"ID DUPLICADO",IF(COUNTIF(tblProdutos[Código],G{r})<>1,"PRODUTO INVÁLIDO",IFERROR(IF(OR(H{r}<=0,I{r}<0,NOT(OR(ISNUMBER(K{r}),K{r}="")),NOT(OR(ISNUMBER(M{r}),M{r}="")),K{r}<0,M{r}<0,AND(O{r}<>"S",O{r}<>"N"),AND(E{r}<>"",NOT(AND(ISTEXT(E{r}),LEN(E{r})=14,ISNUMBER(--E{r})))) ),"DADOS INVÁLIDOS",IF(COUNTIFS(\'11_ESTOQUE_MOV\'!$H$8:$H$2007,B{r},\'11_ESTOQUE_MOV\'!$E$8:$E$2007,"Entrada",\'11_ESTOQUE_MOV\'!$K$8:$K$2007,"<>OK")>0,"MOVIMENTO INVÁLIDO",IF(COUNTIFS(\'11_ESTOQUE_MOV\'!$H$8:$H$2007,B{r},\'11_ESTOQUE_MOV\'!$E$8:$E$2007,"Entrada",\'11_ESTOQUE_MOV\'!$F$8:$F$2007,"<>"&G{r})>0,"PRODUTO DIVERGENTE",IF(ABS(R{r})>0.0005,IF(AND(O{r}="S",Q{r}=0),"MOVIMENTO PENDENTE","DIVERGÊNCIA DE QTD"),"OK")))),"DADOS INVÁLIDOS")))))',21:f'=IF(G{r}="","",IFERROR(INDEX(tblProdutos[Descrição],MATCH(G{r},tblProdutos[Código],0)),"PRODUTO NÃO ENCONTRADO"))'}
 for col,f in fs.items():s.cell(r,col,f)
t=Table(displayName='tblEntradas',ref='B7:U207');t.tableStyleInfo=TableStyleInfo(name='TableStyleMedium2',showRowStripes=True,showColumnStripes=False,showFirstColumn=False,showLastColumn=False);s.add_table(t)
def dv(t,rg,f1,op=None,f2=None,msg='Informe um valor válido.'):
 d=DataValidation(type=t,formula1=f1,formula2=f2,operator=op,allow_blank=True);d.showErrorMessage=True;d.errorTitle='Valor inválido';d.error=msg;d.errorStyle='stop';s.add_data_validation(d);d.add(rg)
dv('custom','B8:B207','=AND(ISTEXT(B8),LEN(TRIM(B8))>0,SUMPRODUCT(--($B$8:$B$207=B8),--(ROW($B$8:$B$207)<>ROW(B8)))=0)',msg='Informe ID único como texto.')
dv('date','C8:C207','DATE(2000,1,1)','between','DATE(2100,12,31)',msg='Informe uma data válida.')
dv('custom','E8:E207','=IFERROR(AND(ISTEXT(E8),LEN(E8)=14,ISNUMBER(--E8)),FALSE)',msg='CNPJ numérico: 14 dígitos, em texto e sem pontuação.')
dv('decimal','H8:H207','0','greaterThan',msg='A quantidade deve ser positiva.')
for rg in ['I8:I207','K8:K207','M8:M207']:dv('decimal',rg,'0','greaterThanOrEqual',msg='Informe valor numérico não negativo.')
dv('list','O8:O207','=listaSimNao',msg='Escolha S ou N.')
for f,bg,fg in [('$S8="OK"','E2F0D9','225C21'),('$S8="MOVIMENTO PENDENTE"','FFF2CC','805900'),('AND($S8<>"",$S8<>"OK",$S8<>"MOVIMENTO PENDENTE")','FCE8E6','9C0006')]:s.conditional_formatting.add('S8:S207',FormulaRule(formula=[f],fill=PatternFill('solid',fgColor=bg),font=Font(bold=True,color=fg)))
s['K7'].comment=Comment('Frete já alocado manualmente a esta linha. Não se soma automaticamente por nota.','Equipe PDV');s['O7'].comment=Comment('S exige um movimento de Entrada válido, com documento igual ao ID_Entrada. Não cria o movimento automaticamente.','Equipe PDV');s['N7'].comment=Comment('Preço sugerido = custo final unitário × (1 + markup). Não altera preço do produto.','Equipe PDV')
for col in range(23,30):s.column_dimensions[get_column_letter(col)].width=17
for row,title,text in [(7,'01 • CADASTRE O ITEM','Uma linha por item. Preencha ID único, data, fornecedor, NF, produto, quantidade e custo. Selecione S para solicitar controle de estoque; N para não movimentar.'),(13,'02 • CUSTO E FRETE','Lance em Frete Alocado apenas a parcela correspondente a este item. Custo final inclui esse valor; preço sugerido usa markup e não altera o cadastro de produto.'),(19,'03 • REGISTRE A ENTRADA','Se selecionou S, registre manualmente em 11_ESTOQUE_MOV um movimento Entrada, positivo, com Documento igual ao ID_Entrada e mesmo código de produto. Não lance duas vezes.'),(25,'04 • CONFIRA','MOVIMENTO PENDENTE, MOVIMENTO INVÁLIDO ou DIVERGÊNCIA DE QTD exigem revisão. Verde significa conferência básica; não garante autenticidade da NF nem proteção do histórico.'),(31,'ATENÇÃO','Não há importação de nota fiscal, aprovação, rateio automático entre itens, custo médio, integração automática ou estorno. Use apenas dados fictícios.')]:
 s.merge_cells(start_row=row,start_column=23,end_row=row,end_column=29);c=s.cell(row,23,title);c.fill=PatternFill('solid',fgColor='68C2C7');c.font=Font(name='Segoe UI',size=10,bold=True,color='173A3B');c.alignment=Alignment(indent=1,vertical='center')
 s.merge_cells(start_row=row+1,start_column=23,end_row=row+4,end_column=29);c=s.cell(row+1,23,text);c.fill=PatternFill('solid',fgColor='FFF2CC' if row>=25 else 'EFEFEF');c.font=Font(name='Segoe UI',size=10,color='262626');c.alignment=Alignment(wrap_text=True,vertical='center',indent=1)
s.print_area='B1:U30';s.page_setup.orientation='landscape';s.page_setup.fitToWidth=1;s.page_setup.fitToHeight=0;w.calculation.fullCalcOnLoad=True;w.calculation.forceFullCalc=True;w.save('PDV_Empresa_entradas_v1.xlsx')
