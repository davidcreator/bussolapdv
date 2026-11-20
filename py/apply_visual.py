from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
w=load_workbook('PDV_Empresa_instrucoes_v1.xlsx')
nav=[('PDV','03_PDV'),('Produtos','02_PRODUTOS'),('Caixa','06_CAIXA'),('Crediário','09_CREDIARIO'),('Fechamento','08_FECHAMENTO'),('Dashboard','13_DASHBOARD')]
for s in w:
 if s.title=='00_INSTRUCOES':continue
 for m in list(s.merged_cells.ranges):
  if m.min_row<=2:s.unmerge_cells(str(m))
 for row in (1,2):
  for col in range(2,33):
   c=s.cell(row,col);c.value=None;c.hyperlink=None;c.fill=PatternFill('solid',fgColor='383838' if row==1 else '68C2C7');c.border=Border()
 s.merge_cells('B1:F1');s['B1']='PDV  |  SUA MARCA';s['B1'].font=Font(name='Segoe UI',size=14,bold=True,color='FFFFFF');s['B1'].alignment=Alignment(vertical='center',indent=1)
 s.merge_cells('G1:I1');s['G1']='SISTEMA PDV';s['G1'].font=Font(name='Segoe UI',size=10,bold=True,color='FFFFFF');s['G1'].alignment=Alignment(horizontal='right',vertical='center')
 for i,(label,target) in enumerate(nav):
  a=10+3*i;s.merge_cells(start_row=1,start_column=a,end_row=1,end_column=a+2);c=s.cell(1,a,label);c.hyperlink=f"#'{target}'!B4";c.font=Font(name='Segoe UI',size=10,bold=True,color='FFFFFF');c.alignment=Alignment(horizontal='center',vertical='center')
 s.merge_cells('AB1:AF1');s['AB1']='PROTÓTIPO  •  v1.0';s['AB1'].font=Font(name='Segoe UI',size=9,bold=True,color='FFFFFF');s['AB1'].alignment=Alignment(horizontal='right',vertical='center')
 s.merge_cells('B2:I2');s['B2']='NAVEGAÇÃO  /  '+s.title[3:].replace('_',' ');s['B2'].font=Font(name='Segoe UI',size=9,bold=True,color='173A3B');s['B2'].alignment=Alignment(indent=1,vertical='center')
 for col in range(2,33): s.cell(3,col).border=Border(bottom=Side(style='thin',color='D9D9D9'))
 s.row_dimensions[1].height=32;s.row_dimensions[2].height=20;s.row_dimensions[3].height=8;s.row_dimensions[4].height=30;s.row_dimensions[5].height=20;s.row_dimensions[6].height=8
 s.column_dimensions['A'].width=3
 s['B4'].font=Font(name='Segoe UI',size=19,bold=True,color='171717');s['B4'].alignment=Alignment(vertical='center',indent=1)
 s['B5'].font=Font(name='Segoe UI',size=10,italic=True,color='8C2525');s['B5'].alignment=Alignment(vertical='center',indent=1)
# PDV section labels in reference's turquoise + gray
s=w['03_PDV']
for address in ['B7','B10']:
 c=s[address];c.fill=PatternFill('solid',fgColor='68C2C7');c.font=Font(name='Segoe UI',size=10,bold=True,color='173A3B');c.alignment=Alignment(vertical='center',indent=1)
for r in [11,30]:
 for col in range(2,10):
  c=s.cell(r,col);c.fill=PatternFill('solid',fgColor='EFEFEF');c.font=Font(name='Segoe UI',size=10,bold=True,color='262626');c.alignment=Alignment(vertical='center',wrap_text=True)
 s.row_dimensions[r].height=27
w.save('PDV_Empresa_visual_padronizado.xlsx')
