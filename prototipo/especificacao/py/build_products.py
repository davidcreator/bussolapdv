from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment, Protection
from openpyxl.worksheet.table import Table,TableStyleInfo
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import FormulaRule
from openpyxl.comments import Comment
from openpyxl.utils import get_column_letter
w=load_workbook('PDV_Empresa_parametros_v1.xlsx');s=w['02_PRODUTOS']
s['B5']='Cadastre produtos em branco; filtre o cabeçalho para localizar ou revisar o estoque.'
if 'tblProdutos' in s.tables:del s.tables['tblProdutos']
headers=['Código','Cód. Barras','Descrição','Categoria','Unidade','Custo','Preço Venda','Estoque Inicial','Estoque Mínimo','Ativo','Estoque Atual','Status Estoque','Margem %','Valor Estoque Custo','Valor Estoque Venda','Vendas 30d']
widths=[16,20,30,18,13,16,16,17,18,12,17,19,15,21,21,17]
for i,(h,width) in enumerate(zip(headers,widths),2):
 c=s.cell(7,i,h);c.fill=PatternFill('solid',fgColor='383838');c.font=Font(name='Segoe UI',size=10,bold=True,color='FFFFFF');c.alignment=Alignment(wrap_text=True,vertical='center');s.column_dimensions[get_column_letter(i)].width=width
s.row_dimensions[7].height=32
for row,data in [(11,['P004','7890000000042','Arroz 1 kg','Mercearia','UN',6,9,2,4,'S']),(12,['P005','7890000000059','Papel toalha','Limpeza','UN',3,6,0,3,'S'])]:
 for col,val in enumerate(data,2):s.cell(row,col,val)
for r in range(8,108):
 for c in range(2,12):
  x=s.cell(r,c);x.fill=PatternFill('solid',fgColor='FFFFFF');x.border=Border(bottom=Side(style='thin',color='D39700'));x.font=Font(name='Segoe UI',size=10,color='262626');x.protection=Protection(locked=False)
 for c in (2,3):s.cell(r,c).number_format='@'
 for c in (7,8):s.cell(r,c).number_format='"R$" #,##0.00'
 for c in (9,10):s.cell(r,c).number_format='#,##0.000'
 formulas={12:f'=IF(B{r}="","",I{r}+SUMIF(\'11_ESTOQUE_MOV\'!$F$8:$F$10000,B{r},\'11_ESTOQUE_MOV\'!$G$8:$G$10000))',13:f'=IF(B{r}="","",IF(L{r}<=0,"ESTOQUE VAZIO",IF(L{r}<=J{r},"ESTOQUE BAIXO","ESTOQUE BOM")))',14:f'=IF(OR(B{r}="",H{r}<=0),"",IFERROR((H{r}-G{r})/H{r},0))',15:f'=IF(B{r}="","",L{r}*G{r})',16:f'=IF(B{r}="","",L{r}*H{r})',17:f'=IF(B{r}="","",-SUMIFS(\'11_ESTOQUE_MOV\'!$G$8:$G$10000,\'11_ESTOQUE_MOV\'!$F$8:$F$10000,B{r},\'11_ESTOQUE_MOV\'!$E$8:$E$10000,"Saída Venda",\'11_ESTOQUE_MOV\'!$C$8:$C$10000,">="&TODAY()-29,\'11_ESTOQUE_MOV\'!$C$8:$C$10000,"<"&TODAY()+1))'}
 for c,f in formulas.items():
  x=s.cell(r,c,f);x.fill=PatternFill('solid',fgColor='F2F2F2');x.font=Font(name='Segoe UI',size=10,color='262626');x.protection=Protection(locked=True)
 s.cell(r,12).number_format='#,##0.000';s.cell(r,14).number_format='0.0%'
 for c in (15,16):s.cell(r,c).number_format='"R$" #,##0.00'
 s.cell(r,17).number_format='#,##0.000'
 s.row_dimensions[r].height=20
t=Table(displayName='tblProdutos',ref='B7:Q107');t.tableStyleInfo=TableStyleInfo(name='TableStyleMedium2',showRowStripes=True,showColumnStripes=False,showFirstColumn=False,showLastColumn=False);s.add_table(t)
def validation(typ,formula1,rg,formula2=None,operator=None,msg='Selecione um valor válido.',allow=True):
 d=DataValidation(type=typ,formula1=formula1,formula2=formula2,operator=operator,allow_blank=allow);d.showErrorMessage=True;d.errorStyle='stop';d.errorTitle='Entrada inválida';d.error=msg;s.add_data_validation(d);d.add(rg)
validation('custom','=AND(B8<>"",COUNTIF($B$8:$B$107,B8)=1)','B8:B107',msg='Informe um código único.')
validation('custom','=OR(C8="",COUNTIF($C$8:$C$107,C8)=1)','C8:C107',msg='Código de barras duplicado.')
validation('list','"UN,KG,LT,CX"','F8:F107',msg='Selecione UN, KG, LT ou CX.')
validation('list','=listaSimNao','K8:K107',msg='Selecione S ou N.')
for col,op,val in [('G','greaterThanOrEqual','0'),('H','greaterThan','0'),('I','greaterThanOrEqual','0'),('J','greaterThanOrEqual','0')]:validation('decimal',val,f'{col}8:{col}107',operator=op,msg='Informe um valor numérico válido e não negativo; preço deve ser maior que zero.')
for condition,bg,fg in [('$M8="ESTOQUE VAZIO"','FCE8E6','9C0006'),('$M8="ESTOQUE BAIXO"','FFF2CC','805900'),('$M8="ESTOQUE BOM"','E2F0D9','225C21')]:
 s.conditional_formatting.add('M8:M107',FormulaRule(formula=[condition],fill=PatternFill('solid',fgColor=bg),font=Font(name='Segoe UI',bold=True,color=fg)))
s.conditional_formatting.add('B8:B107',FormulaRule(formula=['AND(B8<>"",COUNTIF($B$8:$B$107,B8)>1)'],fill=PatternFill('solid',fgColor='FFC7CE'),font=Font(color='9C0006',bold=True)))
s.conditional_formatting.add('C8:C107',FormulaRule(formula=['AND(C8<>"",COUNTIF($C$8:$C$107,C8)>1)'],fill=PatternFill('solid',fgColor='FFC7CE'),font=Font(color='9C0006',bold=True)))
s['L7'].comment=Comment('Estoque inicial mais quantidades assinadas em movimentos. Limite atual de leitura: linhas 8 a 10000 da aba de movimentos.','Equipe PDV')
s['Q7'].comment=Comment('Soma saídas de venda registradas hoje e nos 29 dias anteriores. Ainda não desconta cancelamentos/devoluções; não existe fluxo de estorno no protótipo.','Equipe PDV')
for c in range(20,28):s.column_dimensions[get_column_letter(c)].width=15
cards=[('T','U','SKUs ATIVOS','=COUNTIFS(B8:B107,"<>\u0022,K8:K107,"S")'),('V','W','ESTOQUE VAZIO','=COUNTIFS(B8:B107,"<>\u0022,K8:K107,"S",M8:M107,"ESTOQUE VAZIO")'),('X','Y','ESTOQUE BAIXO','=COUNTIFS(B8:B107,"<>\u0022,K8:K107,"S",M8:M107,"ESTOQUE BAIXO")'),('Z','AA','ESTOQUE A CUSTO','=SUM(O8:O107)')]
for a,b,title,f in cards:
 s.merge_cells(f'{a}4:{b}4');s.merge_cells(f'{a}5:{b}5');h=s[f'{a}4'];h.value=title;h.fill=PatternFill('solid',fgColor='68C2C7');h.font=Font(name='Segoe UI',size=9,bold=True,color='173A3B');h.alignment=Alignment(horizontal='center',vertical='center');v=s[f'{a}5'];v.value=f;v.fill=PatternFill('solid',fgColor='EFEFEF');v.font=Font(name='Segoe UI',size=12,bold=True,color='262626');v.alignment=Alignment(horizontal='center',vertical='center')
s['Z5'].number_format='"R$" #,##0.00'
s.freeze_panes='C8' # mantém cabeçalho visível
s.auto_filter.ref=None;s.print_area='B1:Q22';s.page_setup.fitToWidth=1;s.page_setup.fitToHeight=0
w.calculation.fullCalcOnLoad=True;w.calculation.forceFullCalc=True
w.save('PDV_Empresa_produtos_v1.xlsx')
