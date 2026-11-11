from openpyxl import load_workbook
from openpyxl.styles import Font,PatternFill,Alignment,Border,Side
from openpyxl.formatting.rule import FormulaRule
from openpyxl.comments import Comment
from openpyxl.utils import get_column_letter
w=load_workbook('PDV_Empresa_listas_v1.xlsx');s=w['14_AUDITORIA'];s['B5']='Registro manual em B:R • verificações automáticas e amostras a partir da coluna T.'
# somente substituir painel lateral, preservando integralmente a tabela manual e dados existentes
for m in list(s.merged_cells.ranges):
 if m.min_row>=7 and m.min_col>=20:s.unmerge_cells(str(m))
for row in s.iter_rows(min_row=7,max_row=160,min_col=20,max_col=34):
 for c in row:c.value=None;c.fill=PatternFill(fill_type=None);c.border=Border();c.comment=None
for col,wd in {'T':32,'U':25,'V':18,'W':27,'X':32,'Y':22,'Z':21,'AA':21,'AB':3,'AC':15}.items():s.column_dimensions[col].width=wd
s.column_dimensions['AC'].hidden=True
s.merge_cells('T7:AA7');s['T7']='PAINEL DE AUDITORIA • ESTADO ATUAL DAS FONTES';s['T7'].fill=PatternFill('solid',fgColor='383838');s['T7'].font=Font(name='Segoe UI',size=11,bold=True,color='FFFFFF');s['T7'].alignment=Alignment(vertical='center',indent=1)
# status arrays and exclusions: only nonempty status values that differ from the stated accepted values
sources=[
 ('Auditoria manual','14_AUDITORIA','P','B','C',8,307,['OK']),
 ('Vendas','04_VENDAS','N','B','C',8,507,['CONFERIDO']),
 ('Itens de venda','05_ITENS_VENDA','Q','B','N',8,1007,['CONFERIDO']),
 ('Pagamentos • linha','07_PAGAMENTOS','N','B','H',8,1007,['OK']),
 ('Pagamentos • venda','07_PAGAMENTOS','O','B','H',8,1007,['VALORES CONFEREM']),
 ('Caixa • turno','06_CAIXA','U','B','C',8,57,['CONFERIDO','TURNO ABERTO']),
 ('Caixa • movimento','06_CAIXA','AH','X','Z',8,307,['OK']),
 ('Caixa • contagem','06_CAIXA','AN','AJ',None,8,257,['OK']),
 ('Crediário • título','09_CREDIARIO','Q','B','F',8,207,['OK']),
 ('Crediário • recebimento','09_CREDIARIO','AF','X','Z',8,507,['OK']),
 ('Clientes','10_CLIENTES','N','B',None,8,207,['OK']),
 ('Estoque • movimento','11_ESTOQUE_MOV','K','B','C',8,2007,['OK']),
 ('Entradas','12_ENTRADAS','S','B','C',8,207,['OK']),
 ('Listas • padrão','15_LISTAS','Q','N',None,8,18,['PADRÃO ORIGINAL'])]
def fmt_range(sheet,col,first,last):return f"'{sheet}'!${col}${first}:${col}${last}"
def cond(status,accepted):
 st=f'IFERROR({status},"#ERRO NA FONTE")'
 return [f'--({st}<>"")']+[f'--({st}<>"{v}")' for v in accepted]
for idx,(label,sh,status,idcol,datecol,first,last,accepted) in enumerate(sources,9):
 sr=fmt_range(sh,status,first,last);f='=SUMPRODUCT('+','.join(cond(sr,accepted))+')'
 s.merge_cells(start_row=idx,start_column=20,end_row=idx,end_column=24);c=s.cell(idx,20,label);c.fill=PatternFill('solid',fgColor='EFEFEF');c.font=Font(name='Segoe UI',size=10,bold=True,color='262626');c.alignment=Alignment(indent=1,vertical='center')
 s.merge_cells(start_row=idx,start_column=25,end_row=idx,end_column=27);c=s.cell(idx,25,f);c.fill=PatternFill('solid',fgColor='F2F4F5');c.font=Font(name='Segoe UI',size=11,bold=True,color='173A3B');c.alignment=Alignment(horizontal='right',vertical='center');s.row_dimensions[idx].height=22
s.merge_cells('T24:AA25');s['T24']='Contagens globais por linha de fonte, não por evento único. Um mesmo problema pode aparecer em mais de uma categoria. A amostra abaixo mostra até cinco linhas por categoria; filtre a aba de origem para ver todas.';s['T24'].fill=PatternFill('solid',fgColor='FFF2CC');s['T24'].font=Font(name='Segoe UI',size=10,color='262626');s['T24'].alignment=Alignment(wrap_text=True,vertical='center',indent=1)
s.merge_cells('T27:AA27');s['T27']='CONFERÊNCIA DOS RELATÓRIOS • CONTEXTOS INDEPENDENTES';s['T27'].fill=PatternFill('solid',fgColor='68C2C7');s['T27'].font=Font(name='Segoe UI',size=10,bold=True,color='173A3B');s['T27'].alignment=Alignment(indent=1,vertical='center')
for row,label,formula in [(28,'Fechamento • diferença','=IF(ISNUMBER(\'08_FECHAMENTO\'!F13),\'08_FECHAMENTO\'!F13,"")'),(29,'Dashboard • diferença','=IF(ISNUMBER(\'13_DASHBOARD\'!F14),\'13_DASHBOARD\'!F14,"")'),(30,'Diferença entre relatórios*','=IF(AND(ISNUMBER(Y28),ISNUMBER(Y29),T31="FILTROS ALINHADOS"),ROUND(Y28-Y29,2),"")')]:
 s.merge_cells(start_row=row,start_column=20,end_row=row,end_column=24);s.cell(row,20,label);s.cell(row,20).fill=PatternFill('solid',fgColor='EFEFEF');s.cell(row,20).font=Font(name='Segoe UI',size=10,bold=True,color='262626');s.cell(row,20).alignment=Alignment(indent=1,vertical='center');s.merge_cells(start_row=row,start_column=25,end_row=row,end_column=27);s.cell(row,25,formula);s.cell(row,25).number_format='"R$" #,##0.00;[Red]-"R$" #,##0.00';s.cell(row,25).fill=PatternFill('solid',fgColor='F2F4F5');s.cell(row,25).font=Font(name='Segoe UI',size=10,bold=True,color='262626');s.cell(row,25).alignment=Alignment(horizontal='right',vertical='center')
s.merge_cells('T31:AA31');s['T31']='=IF(OR(NOT(ISNUMBER(\'08_FECHAMENTO\'!C7)),NOT(ISNUMBER(\'08_FECHAMENTO\'!F7)),NOT(ISNUMBER(\'13_DASHBOARD\'!C7)),NOT(ISNUMBER(\'13_DASHBOARD\'!F7))),"FILTROS INVÁLIDOS",IF(AND(\'08_FECHAMENTO\'!C7=\'13_DASHBOARD\'!C7,\'08_FECHAMENTO\'!F7=\'13_DASHBOARD\'!F7,\'08_FECHAMENTO\'!C7<=\'08_FECHAMENTO\'!F7,\'08_FECHAMENTO\'!I7=\'13_DASHBOARD\'!I7),"FILTROS ALINHADOS","FILTROS DIFERENTES"))';s['T31'].font=Font(name='Segoe UI',size=10,bold=True,color='173A3B');s['T31'].alignment=Alignment(indent=1,vertical='center')
s.merge_cells('T32:AA34');s['T32']='* Compare relatórios apenas após alinhar datas e operador em 08_FECHAMENTO e 13_DASHBOARD. Se os filtros forem diferentes, a diferença não é erro comprovado. Zero não comprova recebimento externo ou fechamento correto.';s['T32'].fill=PatternFill('solid',fgColor='FFF2CC');s['T32'].font=Font(name='Segoe UI',size=10,color='262626');s['T32'].alignment=Alignment(wrap_text=True,vertical='center',indent=1)
s.merge_cells('T37:AA37');s['T37']='AMOSTRA DE OCORRÊNCIAS ATUAIS • ATÉ 5 POR CATEGORIA';s['T37'].fill=PatternFill('solid',fgColor='383838');s['T37'].font=Font(name='Segoe UI',size=10,bold=True,color='FFFFFF');s['T37'].alignment=Alignment(indent=1,vertical='center')
for col,name in [(20,'Fonte / categoria'),(21,'Referência / ID'),(22,'Data'),(23,'Estado da fonte'),(24,'Linha na fonte')]:
 c=s.cell(38,col,name);c.fill=PatternFill('solid',fgColor='383838');c.font=Font(name='Segoe UI',size=9,bold=True,color='FFFFFF');c.alignment=Alignment(vertical='center',wrap_text=True)
s.row_dimensions[38].height=30
for idx,(label,sh,status,idcol,datecol,first,last,accepted) in enumerate(sources):
 start=39+5*idx;end=start+4;sr=fmt_range(sh,status,first,last);ir=fmt_range(sh,idcol,first,last);firstcell=f"'{sh}'!${status}${first}";dr=fmt_range(sh,datecol,first,last) if datecol else None
 condition='*'.join(cond(sr,accepted));den=f'({condition})'
 for row in range(start,end+1):
  s.cell(row,20,label);s.cell(row,20).font=Font(name='Segoe UI',size=9,color='262626');
  s.cell(row,29,f'=IFERROR(AGGREGATE(15,6,(ROW({sr})-ROW({firstcell})+1)/{den},ROWS($AC${start}:AC{row})),"")')
  s.cell(row,21,f'=IF(AC{row}="","",IF(INDEX({ir},AC{row})="","[SEM ID]",INDEX({ir},AC{row})))')
  s.cell(row,22,f'=IF(AC{row}="","",IFERROR(IF(INDEX({dr},AC{row})="","",INDEX({dr},AC{row})),"[ERRO]"))' if dr else '=""');s.cell(row,22).number_format='dd/mm/yyyy'
  s.cell(row,23,f'=IF(AC{row}="","",IFERROR(INDEX({sr},AC{row}),"ERRO NA FONTE"))')
  s.cell(row,24,f'=IF(AC{row}="","",AC{row}+{first-1})')
  for col in range(20,25):
   c=s.cell(row,col);c.fill=PatternFill('solid',fgColor='F2F4F5' if idx%2==0 else 'FFFFFF');c.font=Font(name='Segoe UI',size=9,color='262626');c.alignment=Alignment(vertical='center',wrap_text=True)
  s.row_dimensions[row].height=22
# status condition highlighting
s.conditional_formatting.add('Y9:Y22',FormulaRule(formula=['AND(ISNUMBER(Y9),Y9>0)'],fill=PatternFill('solid',fgColor='FCE8E6'),font=Font(color='9C0006',bold=True)))
s.conditional_formatting.add('Y28:Y30',FormulaRule(formula=['AND(ISNUMBER(Y28),ABS(Y28)>0.005)'],fill=PatternFill('solid',fgColor='FCE8E6'),font=Font(color='9C0006',bold=True)))
s['T7'].comment=Comment('Painel formulaico, sem criação automática de logs ou comprovação externa. Não substitui investigação e trilha imutável.','Equipe PDV')
s.sheet_view.zoomScale=75;s.print_area='T7:AA34';s.page_setup.orientation='landscape';s.page_setup.fitToWidth=1;s.page_setup.fitToHeight=0;w.calculation.fullCalcOnLoad=True;w.calculation.forceFullCalc=True;w.save('PDV_Empresa_auditoria_avancada_v1.xlsx')
