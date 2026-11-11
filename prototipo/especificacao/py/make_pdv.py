from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.page import PageMargins
names=['00_INSTRUCOES','01_PARAMETROS','02_PRODUTOS','03_PDV','04_VENDAS','05_ITENS_VENDA','06_CAIXA','07_PAGAMENTOS','08_FECHAMENTO','09_CREDIARIO','10_CLIENTES','11_ESTOQUE_MOV','12_ENTRADAS','13_DASHBOARD','14_AUDITORIA','15_LISTAS']
colors=['808080','404040','4472C4','00B050','006100','006100','FFC000','BF9000','ED7D31','7030A0','B4A7D6','9DC3E6','9DC3E6','843C60','404040','808080']
titles=['INSTRUÇÕES','PARÂMETROS','PRODUTOS E ESTOQUE','FRENTE DE CAIXA','HISTÓRICO DE VENDAS','ITENS DE VENDA','CONTROLE DE CAIXA','PAGAMENTOS','FECHAMENTO DIÁRIO','CREDIÁRIO','CLIENTES','MOVIMENTAÇÕES DE ESTOQUE','ENTRADAS','DASHBOARD','AUDITORIA','LISTAS DE VALIDAÇÃO']
nav=[('PDV','03_PDV'),('Vendas','04_VENDAS'),('Caixa','06_CAIXA'),('Estoque','02_PRODUTOS'),('Crediário','09_CREDIARIO'),('Fechamento','08_FECHAMENTO'),('Dashboard','13_DASHBOARD')]
wb=Workbook(); wb.remove(wb.active)
for n in names: wb.create_sheet(n)
for idx,ws in enumerate(wb.worksheets):
 ws.sheet_properties.tabColor=colors[idx]; ws.sheet_view.showGridLines=False; ws.freeze_panes='C7'
 ws.column_dimensions['A'].width=3
 for c in range(2,33): ws.column_dimensions[get_column_letter(c)].width=12
 ws.column_dimensions['I'].width=3; ws.column_dimensions['AA'].width=3
 for r,h in [(1,32),(2,20),(3,8),(4,20),(5,18),(6,8)]: ws.row_dimensions[r].height=h
 ws.merge_cells('B1:H1'); ws['B1']='SUA MARCA  |  PDV'; ws['B1'].font=Font(name='Segoe UI',size=14,bold=True,color='1F3864'); ws['B1'].alignment=Alignment(vertical='center')
 ws.merge_cells('B2:H2'); ws['B2']='LOGO · área reservada'; ws['B2'].font=Font(name='Segoe UI',size=9,color='595959')
 for i,(label,target) in enumerate(nav):
  a=10+i*2; b=a+1; ws.merge_cells(start_row=1,start_column=a,end_row=1,end_column=b)
  cell=ws.cell(1,a,label); cell.font=Font(name='Segoe UI',size=9,bold=True,color='FFFFFF'); cell.fill=PatternFill('solid',fgColor='1F3864'); cell.alignment=Alignment(horizontal='center',vertical='center'); cell.hyperlink=f"#'{target}'!B4"; cell.comment=None
 ws.merge_cells('X1:Z1'); ws['X1']='MENU'; ws['X1'].font=Font(name='Segoe UI',size=9,bold=True,color='FFFFFF'); ws['X1'].fill=PatternFill('solid',fgColor='1F3864'); ws['X1'].alignment=Alignment(horizontal='center',vertical='center')
 ws.merge_cells('J2:Z2'); ws['J2']='Nova venda  ·  Consultar produto  ·  Cancelar  ·  Finalizar' if idx==3 else 'Navegação pelo menu superior  ·  Módulo em construção'; ws['J2'].fill=PatternFill('solid',fgColor='2F5597'); ws['J2'].font=Font(name='Segoe UI',size=9,color='FFFFFF'); ws['J2'].alignment=Alignment(vertical='center',indent=1)
 ws.merge_cells('AB1:AF1'); ws['AB1']='SUA EMPRESA  |  v1.0'; ws['AB1'].font=Font(name='Segoe UI',size=10,bold=True,color='1F3864'); ws['AB1'].alignment=Alignment(horizontal='right',vertical='center')
 for col in range(2,33): ws.cell(3,col).border=Border(bottom=Side(style='thin',color='D9D9D9'))
 ws['B4']=titles[idx]; ws['B4'].font=Font(name='Segoe UI',size=16,bold=True,color='1F3864'); ws['B4'].alignment=Alignment(vertical='center'); ws.merge_cells('B4:H4')
 ws.merge_cells('B5:H5'); ws['B5']='Fase 1: estrutura e navegação; funcionalidade ainda não implementada.'; ws['B5'].font=Font(name='Segoe UI',size=9,color='595959')
 ws.print_area='B1:AF50'; ws.page_setup.orientation='landscape'; ws.page_setup.paperSize=ws.PAPERSIZE_A4; ws.page_setup.fitToWidth=1; ws.page_setup.fitToHeight=0; ws.sheet_properties.pageSetUpPr.fitToPage=True; ws.page_margins=PageMargins(left=.25,right=.25,top=.35,bottom=.35,header=.15,footer=.15)
 ws.oddFooter.center.text='Página &P de &N  |  &D &T'
for n in ['04_VENDAS','05_ITENS_VENDA','07_PAGAMENTOS','11_ESTOQUE_MOV','14_AUDITORIA']: wb[n].sheet_state='hidden'
wb['15_LISTAS'].sheet_state='veryHidden'
wb.active=0
wb.save('/home/user/PDV_Empresa_v1.0_fase1.xlsx')
