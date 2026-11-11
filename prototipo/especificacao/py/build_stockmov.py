from openpyxl import load_workbook
from openpyxl.styles import Font,PatternFill,Border,Side,Alignment,Protection
from openpyxl.worksheet.table import Table,TableStyleInfo
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import FormulaRule
from openpyxl.comments import Comment
from openpyxl.utils import get_column_letter
w=load_workbook('PDV_Empresa_clientes_v1.xlsx');s=w['11_ESTOQUE_MOV'];s.sheet_state='visible';s['B4']='MOVIMENTAÇÃO DE ESTOQUE';s['B5']='TESTE • quantidades assinadas • somente movimentos OK compõem o saldo de produtos.';s.freeze_panes='C8';s.sheet_view.zoomScale=80
if 'tblEstoqueMov' in s.tables:del s.tables['tblEstoqueMov']
headers=['ID_Mov','Data','Hora','Tipo','Código Produto','Qtd Assinada','Documento','Operador','Descrição Atual','Verificação','Observações'];widths=[21,15,13,22,20,19,20,21,30,27,29]
for col,(h,wd) in enumerate(zip(headers,widths),2):
 c=s.cell(7,col,h);c.fill=PatternFill('solid',fgColor='383838');c.font=Font(name='Segoe UI',size=10,bold=True,color='FFFFFF');c.alignment=Alignment(vertical='center',wrap_text=True);s.column_dimensions[get_column_letter(col)].width=wd
s.row_dimensions[7].height=32
for r in range(8,2008):
 for col in range(2,13):
  c=s.cell(r,col);inp=col not in (10,11);c.fill=PatternFill('solid',fgColor='FFF9E6' if inp else 'EEF2F3');c.font=Font(name='Segoe UI',size=10,color='262626');c.alignment=Alignment(vertical='center');c.protection=Protection(locked=not inp)
  if inp:c.border=Border(bottom=Side(style='thin',color='D39700'))
 s.cell(r,2).number_format='@';s.cell(r,6).number_format='@';s.cell(r,3).number_format='dd/mm/yyyy';s.cell(r,4).number_format='hh:mm:ss';s.cell(r,7).number_format='#,##0.000;[Red]-#,##0.000'
 s.cell(r,10,f'=IF(F{r}="","",IFERROR(INDEX(tblProdutos[Descrição],MATCH(F{r},tblProdutos[Código],0)),"PRODUTO NÃO ENCONTRADO"))')
 s.cell(r,11,f'=IF(COUNTA(B{r}:I{r},L{r})=0,"",IF(OR(B{r}="",NOT(ISNUMBER(C{r})),NOT(ISNUMBER(D{r})),E{r}="",F{r}="",NOT(ISNUMBER(G{r})),I{r}=""),"DADOS INCOMPLETOS",IF(SUMPRODUCT(--($B$8:$B$2007=B{r}))>1,"ID DUPLICADO",IF(COUNTIF(tblProdutos[Código],F{r})<>1,"PRODUTO INVÁLIDO",IF(AND(E{r}<>"Entrada",E{r}<>"Saída Venda",E{r}<>"Ajuste",E{r}<>"Perda",E{r}<>"Devolução",E{r}<>"Transferência"),"TIPO INVÁLIDO",IF(OR(G{r}=0,AND(OR(E{r}="Entrada",E{r}="Devolução"),G{r}<0),AND(OR(E{r}="Saída Venda",E{r}="Perda"),G{r}>0)),"SINAL INVÁLIDO","OK"))))))')
t=Table(displayName='tblEstoqueMov',ref='B7:L2007');t.tableStyleInfo=TableStyleInfo(name='TableStyleMedium2',showRowStripes=True,showColumnStripes=False,showFirstColumn=False,showLastColumn=False);s.add_table(t)
def dv(t,rg,f1,op=None,f2=None,msg='Informe um valor válido.'):
 d=DataValidation(type=t,formula1=f1,formula2=f2,operator=op,allow_blank=True);d.showErrorMessage=True;d.errorStyle='stop';d.errorTitle='Valor inválido';d.error=msg;s.add_data_validation(d);d.add(rg)
dv('custom','B8:B2007','=AND(ISTEXT(B8),LEN(TRIM(B8))>0,SUMPRODUCT(--($B$8:$B$2007=B8),--(ROW($B$8:$B$2007)<>ROW(B8)))=0)',msg='Informe um ID único como texto.')
dv('list','E8:E2007','"Entrada,Saída Venda,Ajuste,Perda,Devolução,Transferência"',msg='Selecione um tipo da lista.')
dv('date','C8:C2007','DATE(2000,1,1)','between','DATE(2100,12,31)',msg='Digite uma data válida.')
dv('time','D8:D2007','0','between','0.99999999',msg='Digite uma hora válida.')
dv('decimal','G8:G2007','-1000000000','between','1000000000',msg='Digite quantidade numérica e observe o sinal correto.')
for rg,form,bg,fg in [('K8:K2007','$K8="OK"','E2F0D9','225C21'),('K8:K2007','AND($K8<>"",$K8<>"OK")','FCE8E6','9C0006'),('G8:G2007','AND(ISNUMBER($G8),$G8<0)','FCE8E6','9C0006'),('G8:G2007','AND(ISNUMBER($G8),$G8>0)','E2F0D9','225C21')]:s.conditional_formatting.add(rg,FormulaRule(formula=[form],fill=PatternFill('solid',fgColor=bg),font=Font(color=fg,bold=True)))
s['J7'].comment=Comment('Descrição atual do cadastro; não é fotografia histórica. O código do produto permanece no lançamento.','Equipe PDV');s['K7'].comment=Comment('Movimentos com verificação diferente de OK não compõem saldo ou vendas 30 dias em 02_PRODUTOS nesta versão.','Equipe PDV')
# Product stock uses approved-looking formula status; no approval workflow exists
p=w['02_PRODUTOS'];tb=p.tables['tblProdutos'];tb.ref='B7:R107';p['R7']='Revisar Movimentos';p['R7'].font=Font(name='Segoe UI',size=10,bold=True,color='FFFFFF');p['R7'].fill=PatternFill('solid',fgColor='383838');p['R7'].alignment=Alignment(wrap_text=True,vertical='center');p.column_dimensions['R'].width=24
# openpyxl table tableColumns explicitly update on save
from openpyxl.worksheet.table import TableColumn
if tb.tableColumns:
 tb.tableColumns.append(TableColumn(id=17,name='Revisar Movimentos'))
if tb.autoFilter:tb.autoFilter.ref='B7:R107'
for r in range(8,108):
 p[f'L{r}']=f'=IF(B{r}="","",I{r}+SUMIFS(\'11_ESTOQUE_MOV\'!$G$8:$G$2007,\'11_ESTOQUE_MOV\'!$F$8:$F$2007,B{r},\'11_ESTOQUE_MOV\'!$K$8:$K$2007,"OK"))'
 p[f'Q{r}']=f'=IF(B{r}="","",-SUMIFS(\'11_ESTOQUE_MOV\'!$G$8:$G$2007,\'11_ESTOQUE_MOV\'!$F$8:$F$2007,B{r},\'11_ESTOQUE_MOV\'!$E$8:$E$2007,"Saída Venda",\'11_ESTOQUE_MOV\'!$K$8:$K$2007,"OK",\'11_ESTOQUE_MOV\'!$C$8:$C$2007,">="&TODAY()-29,\'11_ESTOQUE_MOV\'!$C$8:$C$2007,"<"&TODAY()+1))'
 p[f'R{r}']=f'=IF(B{r}="","",IF(COUNTIFS(\'11_ESTOQUE_MOV\'!$F$8:$F$2007,B{r},\'11_ESTOQUE_MOV\'!$K$8:$K$2007,"<>OK")>0,"REVISAR","OK"))'
 p[f'R{r}'].fill=PatternFill('solid',fgColor='EEF2F3');p[f'R{r}'].font=Font(name='Segoe UI',size=10,color='262626')
p.conditional_formatting.add('R8:R107',FormulaRule(formula=['$R8="REVISAR"'],fill=PatternFill('solid',fgColor='FCE8E6'),font=Font(bold=True,color='9C0006')))
p['L7'].comment=Comment('Saldo = inicial + movimentos com verificação OK dentro das linhas 8 a 2007. Verifique também a coluna Revisar Movimentos e erros globais.','Equipe PDV')
for col in range(14,21):s.column_dimensions[get_column_letter(col)].width=17
for row,title,text in [(7,'CONVENÇÃO DOS SINAIS','Entrada e devolução: quantidade positiva. Saída de venda e perda: negativa. Ajuste e transferência podem ter ambos os sinais, conforme a origem e o destino.'),(13,'ORIENTAÇÃO','Movimentos de venda são gerados pela macro. Entradas, ajustes e perdas são manuais neste teste. Informe ID único, data e hora estáticas, tipo, código, quantidade e operador.'),(19,'VALIDAÇÃO','Apenas linhas com OK atualizam o saldo dos produtos. Corrija linhas em vermelho antes de analisar o estoque. Um lançamento inválido pode deixar o saldo incompleto.'),(25,'CUIDADOS','Não há aprovação, estorno auditável, bloqueio de edição, integração com compras ou rastreabilidade imutável. Não lance dados ou operações reais.')]:
 s.merge_cells(start_row=row,start_column=14,end_row=row,end_column=20);c=s.cell(row,14,title);c.fill=PatternFill('solid',fgColor='68C2C7');c.font=Font(name='Segoe UI',size=10,bold=True,color='173A3B');c.alignment=Alignment(indent=1,vertical='center')
 s.merge_cells(start_row=row+1,start_column=14,end_row=row+4,end_column=20);c=s.cell(row+1,14,text);c.fill=PatternFill('solid',fgColor='FFF2CC' if row>=19 else 'EFEFEF');c.font=Font(name='Segoe UI',size=10,color='262626');c.alignment=Alignment(wrap_text=True,vertical='center',indent=1)
s.print_area='B1:L40';s.page_setup.orientation='landscape';s.page_setup.fitToWidth=1;s.page_setup.fitToHeight=0
w.calculation.fullCalcOnLoad=True;w.calculation.forceFullCalc=True;w.save('PDV_Empresa_movimentos_v1.xlsx')
