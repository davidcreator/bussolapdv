from openpyxl import load_workbook
from openpyxl.styles import Font,PatternFill,Border,Side,Alignment
from openpyxl.formatting.rule import FormulaRule
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.comments import Comment
from openpyxl.utils import get_column_letter
w=load_workbook('PDV_Empresa_produtos_v1.xlsx');s=w['03_PDV']
s.sheet_view.showGridLines=False;s.sheet_view.zoomScale=80
for c,width in {'B':18,'C':30,'D':13,'E':14,'F':17,'G':17,'H':18,'I':18,'J':3,'K':18,'L':16,'M':16,'N':16,'O':16,'P':16,'Q':16}.items():s.column_dimensions[c].width=width
s['B4']='FRENTE DE CAIXA';s['B5']='AMBIENTE DE TESTE  •  Vendas fictícias  •  Não utilizar em produção'
s['B4'].font=Font(name='Segoe UI',size=19,bold=True,color='171717');s['B5'].font=Font(name='Segoe UI',size=10,italic=True,color='9C2525')
for r in [7,10]:s.row_dimensions[r].height=25
s['B7']='01  IDENTIFIQUE A VENDA';s['B10']='02  LANCE OS PRODUTOS  •  código e quantidade obrigatórios'
for r in [7,10]:
 c=s[f'B{r}'];c.fill=PatternFill('solid',fgColor='68C2C7');c.font=Font(name='Segoe UI',size=10,bold=True,color='173A3B');c.alignment=Alignment(vertical='center',indent=1)
s.row_dimensions[8].height=28
for c in ['B8','F8']:
 x=s[c];x.fill=PatternFill('solid',fgColor='EFEFEF');x.font=Font(name='Segoe UI',size=10,bold=True,color='262626');x.alignment=Alignment(vertical='center',indent=1)
for c in ['C8','G8']:
 x=s[c];x.fill=PatternFill('solid',fgColor='FFF9E6');x.border=Border(bottom=Side(style='medium',color='D39700'));x.font=Font(name='Segoe UI',size=11,color='262626');x.alignment=Alignment(vertical='center',indent=1)
for i,title in enumerate(['CÓDIGO','DESCRIÇÃO','UN.','QTD.','PREÇO UNIT.','DESC. %','TOTAL ITEM','SALDO'],2):
 c=s.cell(11,i);c.value=title;c.fill=PatternFill('solid',fgColor='383838');c.font=Font(name='Segoe UI',size=9,bold=True,color='FFFFFF');c.alignment=Alignment(horizontal='center',vertical='center',wrap_text=True)
s.row_dimensions[11].height=28
for r in range(12,27):
 s.row_dimensions[r].height=25
 for col in range(2,10):
  c=s.cell(r,col);c.alignment=Alignment(vertical='center',horizontal='left' if col in (2,3,4) else 'right',indent=1)
  if col in (2,5,7):c.fill=PatternFill('solid',fgColor='FFF9E6');c.border=Border(bottom=Side(style='thin',color='D39700'));c.font=Font(name='Segoe UI',size=10,color='262626')
  else:c.fill=PatternFill('solid',fgColor='F2F3F4' if r%2==0 else 'F8F9FA');c.font=Font(name='Segoe UI',size=10,color='262626')
 s.cell(r,2).number_format='@';s.cell(r,5).number_format='#,##0.000';s.cell(r,9).number_format='#,##0.000'
for range_,f,bg,fg in [('C12:C26','AND($B12<>"",$C12="NÃO ENCONTRADO")','FCE8E6','9C0006'),('E12:E26','AND($B12<>"",OR(NOT(ISNUMBER($E12)),$E12<=0))','FCE8E6','9C0006'),('I12:I26','AND($B12<>"",ISNUMBER($E12),SUMIF($B$12:$B$26,$B12,$E$12:$E$26)>$I12)','FCE8E6','9C0006')]:s.conditional_formatting.add(range_,FormulaRule(formula=[f],fill=PatternFill('solid',fgColor=bg),font=Font(color=fg,bold=True)))
s['B28']='TOTAL DA VENDA';s['B28'].fill=PatternFill('solid',fgColor='68C2C7');s['B28'].font=Font(name='Segoe UI',size=10,bold=True,color='173A3B');s['B28'].alignment=Alignment(vertical='center',indent=1);s['C28'].fill=PatternFill('solid',fgColor='E5F3E8');s['C28'].font=Font(name='Segoe UI',size=19,bold=True,color='17662B');s['C28'].alignment=Alignment(vertical='center',horizontal='right');s.row_dimensions[28].height=34
s['B30']='03  PAGAMENTO'
for c in range(2,10):
 x=s.cell(30,c);x.fill=PatternFill('solid',fgColor='383838');x.font=Font(name='Segoe UI',size=9,bold=True,color='FFFFFF');x.alignment=Alignment(vertical='center',horizontal='center',wrap_text=True)
s.row_dimensions[30].height=28;s.row_dimensions[31].height=30
for col in range(3,9):
 c=s.cell(31,col);c.fill=PatternFill('solid',fgColor='FFF9E6');c.border=Border(bottom=Side(style='medium',color='D39700'));c.font=Font(name='Segoe UI',size=10,color='262626');c.alignment=Alignment(vertical='center',horizontal='center')
for c in ['D31','F31','H31','I31']:s[c].number_format='"R$" #,##0.00'
s['I31'].fill=PatternFill('solid',fgColor='E7F0F8');s['I31'].font=Font(name='Segoe UI',size=12,bold=True,color='1F4E79');s['I31'].alignment=Alignment(horizontal='right',vertical='center')
s['B33']='=IF(C28<=0,"CARRINHO VAZIO",IF(SUM(D31,F31,H31)<C28,"FALTA R$ "&TEXT(C28-SUM(D31,F31,H31),"#,##0.00"),IF(SUM(D31,F31,H31)-C28>SUMIF(C31,"Dinheiro",D31)+SUMIF(E31,"Dinheiro",F31)+SUMIF(G31,"Dinheiro",H31),"ATENÇÃO: TROCO MAIOR QUE DINHEIRO",IF(SUM(D31,F31,H31)>C28,"TROCO R$ "&TEXT(SUM(D31,F31,H31)-C28,"#,##0.00"),"PAGAMENTO OK"))))'
s.row_dimensions[33].height=26;s['B33'].fill=PatternFill('solid',fgColor='E7F0F8');s['B33'].font=Font(name='Segoe UI',size=11,bold=True,color='1F3864');s['B33'].alignment=Alignment(indent=1,vertical='center')
s['B35']='04  FINALIZAR TESTE  →  Alt+F8  →  FinalizarVenda';s.row_dimensions[35].height=28;s['B35'].fill=PatternFill('solid',fgColor='68C2C7');s['B35'].font=Font(name='Segoe UI',size=11,bold=True,color='173A3B');s['B35'].alignment=Alignment(indent=1,vertical='center')
s['B37']='A macro precisa ser importada na cópia .xlsm. Cartão, crediário e caixa ainda não funcionam.';s['B37'].font=Font(name='Segoe UI',size=10,bold=True,color='9C2525');s['B37'].alignment=Alignment(wrap_text=True,vertical='center');s.row_dimensions[37].height=30
# side panel: intentionally not blocking main inputs
for r in [7,12,18,24,30]:s.merge_cells(start_row=r,start_column=11,end_row=r,end_column=17)
for start,end in [(8,10),(13,16),(19,22),(25,28),(31,34)]:s.merge_cells(start_row=start,start_column=11,end_row=end,end_column=17)
def panel(row,title,text,bg='EFEFEF'):
 h=s.cell(row,11);h.value=title;h.fill=PatternFill('solid',fgColor='68C2C7');h.font=Font(name='Segoe UI',size=10,bold=True,color='173A3B');h.alignment=Alignment(indent=1,vertical='center');s.row_dimensions[row].height=max(s.row_dimensions[row].height or 20,23)
 c=s.cell(row+1,11);c.value=text;c.fill=PatternFill('solid',fgColor=bg);c.font=Font(name='Segoe UI',size=10,color='262626');c.alignment=Alignment(wrap_text=True,vertical='center',indent=1)
panel(7,'GUIA RÁPIDO','1  Informe operador e cliente.\n2  Digite código, quantidade e desconto.\n3  Confira saldo e total.\n4  Preencha pagamentos e execute a macro.')
panel(12,'CAMPOS DA GRADE','Âmbar: preencha código, quantidade e, se houver, desconto.\nCinza: descrição, unidade, preço, total e saldo são calculados.\nCadastre produtos em 02_PRODUTOS antes da venda.')
panel(18,'ANTES DE FINALIZAR','Código não encontrado e quantidade inválida aparecem em vermelho. Saldo vermelho indica quantidade acumulada superior ao estoque. A macro também verifica produto ativo e pagamento.')
panel(24,'PAGAMENTO','Somente Dinheiro e PIX neste teste. Preencha forma e valor juntos; use até três pares. O troco não pode superar o dinheiro entregue. PIX aqui é apenas registro: não confirma recebimento.')
panel(30,'SEGURANÇA E LIMITES','Faça backup antes de cada teste. Em erro após início da gravação, feche sem salvar e restaure a cópia. Não há caixa, permissão por operador, limite de desconto, estorno, crediário ou emissão fiscal.',bg='FFF2CC')
# improve input validation for payments
v=DataValidation(type='decimal',operator='greaterThanOrEqual',formula1='0',allow_blank=True);v.showErrorMessage=True;v.errorTitle='Valor inválido';v.error='Informe um pagamento numérico maior ou igual a zero.';v.errorStyle='stop';s.add_data_validation(v)
for cell in ['D31','F31','H31']:v.add(cell)
s['C8'].comment=Comment('Operador é texto livre; não há autenticação ou vínculo com tblOperadores nesta versão.','Equipe PDV');s['G12'].comment=Comment('Desconto aceita 0% a 100%; limites de aprovação ainda não são aplicados.','Equipe PDV');s['I31'].comment=Comment('Valor aritmético; não confirma que o excesso foi recebido em dinheiro. Consulte a mensagem e a validação da macro.','Equipe PDV')
s.freeze_panes='C7';s.print_area='B1:Q37';s.page_setup.orientation='landscape';s.page_setup.fitToWidth=1;s.page_setup.fitToHeight=0
w.calculation.fullCalcOnLoad=True;w.calculation.forceFullCalc=True
w.save('PDV_Empresa_frente_caixa_v1.xlsx')
