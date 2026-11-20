from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment, Protection
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import CellIsRule
from openpyxl.comments import Comment
from openpyxl.utils import get_column_letter
w=load_workbook('PDV_Empresa_v1.0_fase1.xlsx')
for s in w:
 s.column_dimensions['I'].width=12
 s['B5']='Estrutura em desenvolvimento — não utilizar em produção.'
# helper
blue='1F3864'; amber='FFC000'; grey='F2F2F2'
def head(s,row,items):
 for j,v in enumerate(items,2):
  c=s.cell(row,j,v);c.fill=PatternFill('solid',fgColor=blue);c.font=Font(name='Segoe UI',size=9,bold=True,color='FFFFFF');c.alignment=Alignment(wrap_text=True,vertical='center')
 s.row_dimensions[row].height=30
def table(s,name,endcol,endrow):
 t=Table(displayName=name,ref=f'B7:{get_column_letter(endcol)}{endrow}');t.tableStyleInfo=TableStyleInfo(name='TableStyleMedium2',showRowStripes=True,showColumnStripes=False,showFirstColumn=False,showLastColumn=False);s.add_table(t)
def inputcell(c):
 c.fill=PatternFill('solid',fgColor='FFFFFF');c.border=Border(bottom=Side(style='thin',color=amber));c.font=Font(name='Segoe UI',size=10,color='262626');c.protection=Protection(locked=False)
def calc(c):
 c.fill=PatternFill('solid',fgColor=grey);c.font=Font(name='Segoe UI',size=10,color='262626')
s=w['02_PRODUTOS'];s['B5']='Dados fictícios de demonstração. Estoque considera movimentos registrados.'
h=['Código','Cód. Barras','Descrição','Categoria','Unidade','Custo','Preço Venda','Estoque Inicial','Estoque Mínimo','Ativo','Estoque Atual'];head(s,7,h)
products=[['P001','7890000000011','Café 500 g','Mercearia','UN',10,15,20,5,'S'],['P002','7890000000028','Leite 1 L','Mercearia','UN',4,6,15,4,'S'],['P003','7890000000035','Sabonete','Higiene','UN',2,4,12,3,'S']]
for r,vals in enumerate(products,8):
 for j,v in enumerate(vals,2): s.cell(r,j,v);inputcell(s.cell(r,j))
 s.cell(r,12,f'=I{r}+SUMIF(\'11_ESTOQUE_MOV\'!$F$8:$F$10000,B{r},\'11_ESTOQUE_MOV\'!$G$8:$G$10000)');calc(s.cell(r,12))
 for col in (7,8):s.cell(r,col).number_format='"R$" #,##0.00'
for col,width in {'B':14,'C':19,'D':26,'E':16,'F':12,'G':14,'H':14,'I':16,'J':16,'K':12,'L':16}.items():s.column_dimensions[col].width=width
table(s,'tblProdutos',12,10)
for name,headers,tn in [
 ('04_VENDAS',['ID_Venda','Data','Hora','Operador','Cliente','Subtotal','Total','Status','Troco'],'tblVendas'),
 ('05_ITENS_VENDA',['ID_Venda','Seq','Código Produto','Descrição','Unidade','Qtd','Preço Unitário','Desconto Item %','Total Item','Custo Unitário'],'tblItensVenda'),
 ('07_PAGAMENTOS',['ID_Venda','Seq','Forma Pagamento','Valor Aplicado','Valor Entregue','Troco'],'tblPagamentos'),
 ('11_ESTOQUE_MOV',['ID_Mov','Data','Hora','Tipo','Código Produto','Qtd Assinada','Documento','Operador'],'tblEstoqueMov')]:
 x=w[name];head(x,7,headers);table(x,tn,1+len(headers),8)
 for j in range(2,2+len(headers)):x.column_dimensions[get_column_letter(j)].width=18
s=w['03_PDV'];s['B5']='PROTÓTIPO: apenas demonstração; finalização requer importar o módulo VBA.'
s.merge_cells('B7:I7');s['B7']='IDENTIFICAÇÃO DA VENDA';s['B7'].fill=PatternFill('solid',fgColor=blue);s['B7'].font=Font(name='Segoe UI',bold=True,color='FFFFFF')
s['B8']='Operador';s.merge_cells('C8:E8');s['F8']='Cliente';s.merge_cells('G8:I8');s['G8']='Consumidor Final';inputcell(s['C8']);inputcell(s['G8'])
s.merge_cells('B10:I10');s['B10']='CARRINHO — digite o código do produto e a quantidade';s['B10'].fill=PatternFill('solid',fgColor=blue);s['B10'].font=Font(name='Segoe UI',bold=True,color='FFFFFF')
head(s,11,['Código','Descrição','Un.','Qtd','Preço','Desc. %','Total','Estoque'])
for r in range(12,27):
 for col in (2,5,7): inputcell(s.cell(r,col))
 for col,formula in {3:f'=IF(B{r}="","",IFERROR(INDEX(tblProdutos[Descrição],MATCH(B{r},tblProdutos[Código],0)),"NÃO ENCONTRADO"))',4:f'=IF(B{r}="","",IFERROR(INDEX(tblProdutos[Unidade],MATCH(B{r},tblProdutos[Código],0)),""))',6:f'=IF(B{r}="","",IFERROR(INDEX(tblProdutos[Preço Venda],MATCH(B{r},tblProdutos[Código],0)),0))',8:f'=IF(OR(B{r}="",E{r}=""),0,ROUND(E{r}*F{r}*(1-G{r}),2))',9:f'=IF(B{r}="","",IFERROR(INDEX(tblProdutos[Estoque Atual],MATCH(B{r},tblProdutos[Código],0)),0))'}.items():s.cell(r,col,formula);calc(s.cell(r,col))
 for col in (6,8):s.cell(r,col).number_format='"R$" #,##0.00'
 s.cell(r,7).number_format='0.0%'
s['B28']='TOTAL';s['C28']='=SUM(H12:H26)';s['C28'].number_format='"R$" #,##0.00';s['C28'].font=Font(name='Segoe UI',size=18,bold=True,color='008040')
s['B30']='PAGAMENTO';s['C30']='Forma 1';s['D30']='Valor 1';s['E30']='Forma 2';s['F30']='Valor 2';s['G30']='Forma 3';s['H30']='Valor 3';s['I30']='Troco'
for col in (3,4,5,6,7,8):inputcell(s.cell(31,col))
s['I31']='=MAX(0,SUM(D31,F31,H31)-C28)';s['I31'].number_format='"R$" #,##0.00';calc(s['I31'])
s.merge_cells('B33:I33');s['B33']='=IF(C28<=0,"CARRINHO VAZIO",IF(SUM(D31,F31,H31)<C28,"FALTA R$ "&TEXT(C28-SUM(D31,F31,H31),"#,##0.00"),IF(SUM(D31,F31,H31)>C28,"TROCO R$ "&TEXT(SUM(D31,F31,H31)-C28,"#,##0.00"),"PAGAMENTO OK")))';s['B33'].font=Font(name='Segoe UI',size=12,bold=True,color=blue)
s.merge_cells('B35:I35');s['B35']='FINALIZAR: Alt+F8 → FinalizarVenda (após importar o módulo)';s['B35'].font=Font(name='Segoe UI',size=10,bold=True,color=blue)
s.merge_cells('B37:I37');s['B37']='Teste: somente dinheiro e PIX. Não usa caixa, desconto autorizado ou crediário.'
for col,width in {'B':16,'C':29,'D':12,'E':12,'F':15,'G':16,'H':16,'I':17}.items():s.column_dimensions[col].width=width
v=DataValidation(type='list',formula1='"Dinheiro,PIX"');v.error='Escolha Dinheiro ou PIX.';v.errorTitle='Forma inválida';v.showErrorMessage=True;v.errorStyle='stop';s.add_data_validation(v)
for c in ['C31','E31','G31']:v.add(s[c])
v=DataValidation(type='decimal',operator='greaterThan',formula1='0');v.showErrorMessage=True;v.error='Digite quantidade maior que zero.';s.add_data_validation(v);v.add('E12:E26')
v=DataValidation(type='decimal',operator='between',formula1='0',formula2='1');v.showErrorMessage=True;v.error='Digite percentual de 0% a 100%.';s.add_data_validation(v);v.add('G12:G26')
w.calculation.fullCalcOnLoad=True; w.calculation.forceFullCalc=True;w.calculation.calcMode='auto'
w.save('PDV_Empresa_prototipo_pdv.xlsx')
