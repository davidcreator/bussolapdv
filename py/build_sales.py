from openpyxl import load_workbook
from openpyxl.styles import Font,PatternFill,Border,Side,Alignment,Protection
from openpyxl.worksheet.table import Table,TableStyleInfo
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import FormulaRule
from openpyxl.comments import Comment
from copy import copy
from openpyxl.utils import get_column_letter
w=load_workbook('PDV_Empresa_frente_caixa_v1.xlsx');s=w['04_VENDAS'];s.sheet_state='visible'
s['B4']='HISTÓRICO DE VENDAS';s['B5']='PROTÓTIPO  •  use os filtros do cabeçalho; não edite nem apague o histórico.'
for m in list(s.merged_cells.ranges):
 if m.min_row>=7:s.unmerge_cells(str(m))
if 'tblVendas' in s.tables:del s.tables['tblVendas']
headers=['ID_Venda','Data','Hora','Operador','Cliente','Subtotal','Total','Status','Troco','Qtd Itens','Pagamentos Aplicados','Diferença','Conferência']
widths=[16,15,13,21,24,17,17,18,16,15,22,17,22]
for col,(h,width) in enumerate(zip(headers,widths),2):
 c=s.cell(7,col,h);c.fill=PatternFill('solid',fgColor='383838');c.font=Font(name='Segoe UI',size=10,bold=True,color='FFFFFF');c.alignment=Alignment(vertical='center',wrap_text=True);s.column_dimensions[get_column_letter(col)].width=width
s.row_dimensions[7].height=32
for r in range(8,508):
 for c in range(2,15):
  x=s.cell(r,c);x.font=Font(name='Segoe UI',size=10,color='262626');x.alignment=Alignment(vertical='center');x.fill=PatternFill('solid',fgColor='F5F6F7' if c<11 else 'EEF2F3');x.protection=Protection(locked=True)
 s.cell(r,3).number_format='dd/mm/yyyy';s.cell(r,4).number_format='hh:mm:ss'
 for c in (7,8,10,12,13):s.cell(r,c).number_format='"R$" #,##0.00;[Red]-"R$" #,##0.00'
 s.cell(r,11).number_format='#,##0.000'
 fs={11:f'=IF(B{r}="","",SUMIF(\'05_ITENS_VENDA\'!$B$8:$B$10000,B{r},\'05_ITENS_VENDA\'!$G$8:$G$10000))',12:f'=IF(B{r}="","",SUMIF(\'07_PAGAMENTOS\'!$B$8:$B$10000,B{r},\'07_PAGAMENTOS\'!$E$8:$E$10000))',13:f'=IF(B{r}="","",ROUND(L{r}-H{r},2))',14:f'=IF(B{r}="","",IF(I{r}<>"Concluída","REVISAR STATUS",IF(ABS(M{r})<0.005,"CONFERIDO","DIVERGÊNCIA")))'}
 for col,form in fs.items():s.cell(r,col,form)
t=Table(displayName='tblVendas',ref='B7:N507');t.tableStyleInfo=TableStyleInfo(name='TableStyleMedium2',showRowStripes=True,showColumnStripes=False,showFirstColumn=False,showLastColumn=False);s.add_table(t)
for f,bg,fg in [('$N8="CONFERIDO"','E2F0D9','225C21'),('$N8="DIVERGÊNCIA"','FCE8E6','9C0006'),('$N8="REVISAR STATUS"','FFF2CC','805900')]:s.conditional_formatting.add('N8:N507',FormulaRule(formula=[f],fill=PatternFill('solid',fgColor=bg),font=Font(color=fg,bold=True)))
s.conditional_formatting.add('B8:B507',FormulaRule(formula=['AND(B8<>"",COUNTIF($B$8:$B$507,B8)>1)'],fill=PatternFill('solid',fgColor='FFC7CE'),font=Font(color='9C0006',bold=True)))
s['G7'].comment=Comment('No protótipo, a macro grava o total após desconto também como subtotal; não representa subtotal bruto.','Equipe PDV')
s['L7'].comment=Comment('Soma Valor Aplicado nos pagamentos da mesma venda, limitado às linhas 8 a 10000 da aba de pagamentos.','Equipe PDV')
s['N7'].comment=Comment('Verifica apenas a diferença entre pagamento aplicado e total de venda concluída. Não valida o recebimento bancário ou a integridade do histórico.','Equipe PDV')
s.freeze_panes='C8'
# lateral, não interfere na tabela nem na faixa superior
for c in range(16,23):s.column_dimensions[get_column_letter(c)].width=15
s.merge_cells('P7:V7');s['P7']='CONSULTA  •  RESUMO POR CRITÉRIOS';s['P7'].fill=PatternFill('solid',fgColor='68C2C7');s['P7'].font=Font(name='Segoe UI',size=10,bold=True,color='173A3B');s['P7'].alignment=Alignment(indent=1,vertical='center')
for r,label in [(9,'Data inicial'),(10,'Data final'),(11,'Operador contém'),(12,'Cliente contém'),(13,'Status')]:
 s.merge_cells(start_row=r,start_column=16,end_row=r,end_column=18);c=s.cell(r,16,label);c.fill=PatternFill('solid',fgColor='EFEFEF');c.font=Font(name='Segoe UI',size=10,bold=True,color='262626');c.alignment=Alignment(vertical='center',indent=1)
 s.merge_cells(start_row=r,start_column=19,end_row=r,end_column=22);c=s.cell(r,19);c.fill=PatternFill('solid',fgColor='FFF9E6');c.border=Border(bottom=Side(style='medium',color='D39700'));c.font=Font(name='Segoe UI',size=10,color='262626');c.protection=Protection(locked=False);c.alignment=Alignment(indent=1,vertical='center');s.row_dimensions[r].height=24
s['S13']='Concluída';s['S9'].number_format='dd/mm/yyyy';s['S10'].number_format='dd/mm/yyyy'
d=DataValidation(type='list',formula1='"Concluída,Cancelada,Devolvida,Todos"',allow_blank=False);d.showErrorMessage=True;d.error='Escolha um status da lista.';d.errorStyle='stop';s.add_data_validation(d);d.add(s['S13'])
d=DataValidation(type='date',operator='between',formula1='DATE(1900,1,1)',formula2='DATE(9999,12,30)',allow_blank=True);d.showErrorMessage=True;d.error='Informe uma data válida.';d.errorStyle='stop';s.add_data_validation(d);d.add('S9:S10')
# Contagens têm critério de id e faixa de datas, os campos texto aceitam busca parcial e status Todos.
criteria='$B$8:$B$507,"<>",$C$8:$C$507,">="&IF($S$9="",0,$S$9),$C$8:$C$507,"<"&IF($S$10="",DATE(9999,12,31),$S$10+1),$E$8:$E$507,"*"&$S$11&"*",$F$8:$F$507,"*"&$S$12&"*",$I$8:$I$507,IF(OR($S$13="Todos",$S$13=""),"*",$S$13)'
for row,label,formula in [(16,'Vendas no resumo',f'=IF(AND(ISNUMBER(S9),ISNUMBER(S10),S9>S10),"DATAS INVÁLIDAS",COUNTIFS({criteria}))'),(17,'Total no resumo',f'=IF(AND(ISNUMBER(S9),ISNUMBER(S10),S9>S10),"DATAS INVÁLIDAS",SUMIFS($H$8:$H$507,{criteria}))')]:
 s.merge_cells(start_row=row,start_column=16,end_row=row,end_column=19);s.cell(row,16,label);s.cell(row,16).font=Font(name='Segoe UI',size=10,bold=True,color='262626');s.merge_cells(start_row=row,start_column=20,end_row=row,end_column=22);s.cell(row,20,formula);s.cell(row,20).fill=PatternFill('solid',fgColor='E2F0D9');s.cell(row,20).font=Font(name='Segoe UI',size=11,bold=True,color='225C21');s.cell(row,20).alignment=Alignment(horizontal='right',vertical='center')
s['T17'].number_format='"R$" #,##0.00'
for a,b,title,text in [(19,22,'COMO CONSULTAR','Use as setas em B7:N7 para filtrar ou ordenar as linhas por data, operador, cliente, status ou conferência. O resumo lateral NÃO filtra a tabela.'),(24,27,'COMO CONFERIR','CONFERIDO compara total e pagamentos aplicados; DIVERGÊNCIA indica diferença; REVISAR STATUS não representa estorno automático. Detalhes estão nas abas ocultas de itens e pagamentos.'),(29,33,'CUIDADOS','Não digite sobre o histórico. A macro é experimental, não implementa cancelamentos e não oferece gravação atômica. Não use em produção. Resumo não desconta valores cancelados ao selecionar Todos.')]:
 s.merge_cells(start_row=a,start_column=16,end_row=a,end_column=22);h=s.cell(a,16,title);h.fill=PatternFill('solid',fgColor='68C2C7');h.font=Font(name='Segoe UI',size=10,bold=True,color='173A3B');h.alignment=Alignment(indent=1,vertical='center')
 s.merge_cells(start_row=a+1,start_column=16,end_row=b,end_column=22);c=s.cell(a+1,16,text);c.fill=PatternFill('solid',fgColor='EFEFEF');c.font=Font(name='Segoe UI',size=10,color='262626');c.alignment=Alignment(wrap_text=True,vertical='center',indent=1)
s.print_area='B1:N40';s.page_setup.orientation='landscape';s.page_setup.fitToWidth=1;s.page_setup.fitToHeight=0
w.calculation.fullCalcOnLoad=True;w.calculation.forceFullCalc=True
w.save('PDV_Empresa_vendas_v1.xlsx')
