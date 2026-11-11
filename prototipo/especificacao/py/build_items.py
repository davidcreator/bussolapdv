from openpyxl import load_workbook
from openpyxl.styles import Font,PatternFill,Alignment,Protection
from openpyxl.worksheet.table import Table,TableStyleInfo
from openpyxl.formatting.rule import FormulaRule
from openpyxl.utils import get_column_letter
from openpyxl.comments import Comment
w=load_workbook('PDV_Empresa_vendas_v1.xlsx');s=w['05_ITENS_VENDA'];s.sheet_state='visible';s['B4']='ITENS DE VENDA';s['B5']='CONSULTA DE TESTE  •  Detalhamento por cupom  •  Não altere o histórico manualmente.'
if 'tblItensVenda' in s.tables:del s.tables['tblItensVenda']
headers=['ID_Venda','Seq','Código Produto','Descrição','Unidade','Qtd','Preço Unitário','Desconto Item %','Total Item','Custo Unitário','Subtotal Bruto','Lucro Item','Data Venda','Operador Venda','Status Venda','Conferência']
widths=[16,10,19,30,12,15,17,18,17,17,19,17,16,21,18,24]
for col,(title,width) in enumerate(zip(headers,widths),2):
 c=s.cell(7,col,title);c.fill=PatternFill('solid',fgColor='383838');c.font=Font(name='Segoe UI',size=10,bold=True,color='FFFFFF');c.alignment=Alignment(vertical='center',wrap_text=True);s.column_dimensions[get_column_letter(col)].width=width
s.row_dimensions[7].height=32
for r in range(8,1008):
 for col in range(2,18):
  c=s.cell(r,col);c.font=Font(name='Segoe UI',size=10,color='262626');c.fill=PatternFill('solid',fgColor='F5F6F7' if col<12 else 'EEF2F3');c.alignment=Alignment(vertical='center');c.protection=Protection(locked=True)
 for col in (8,10,11,12,13):s.cell(r,col).number_format='"R$" #,##0.00;[Red]-"R$" #,##0.00'
 s.cell(r,7).number_format='#,##0.000';s.cell(r,9).number_format='0.0%';s.cell(r,14).number_format='dd/mm/yyyy'
 fs={12:f'=IF(B{r}="","",ROUND(G{r}*H{r},2))',13:f'=IF(B{r}="","",ROUND(J{r}-G{r}*K{r},2))',14:f'=IF(B{r}="","",IFERROR(INDEX(\'04_VENDAS\'!$C$8:$C$507,MATCH(B{r},\'04_VENDAS\'!$B$8:$B$507,0)),""))',15:f'=IF(B{r}="","",IFERROR(INDEX(\'04_VENDAS\'!$E$8:$E$507,MATCH(B{r},\'04_VENDAS\'!$B$8:$B$507,0)),""))',16:f'=IF(B{r}="","",IFERROR(INDEX(\'04_VENDAS\'!$I$8:$I$507,MATCH(B{r},\'04_VENDAS\'!$B$8:$B$507,0)),"SEM VENDA"))',17:f'=IF(B{r}="","",IF(P{r}="SEM VENDA","SEM VENDA",IF(COUNTIFS($B$8:$B$1007,B{r},$C$8:$C$1007,C{r})>1,"ID/SEQ DUPLICADO",IF(OR(NOT(ISNUMBER(G{r})),G{r}<=0,NOT(ISNUMBER(H{r})),H{r}<=0,NOT(ISNUMBER(J{r})),NOT(ISNUMBER(K{r})),K{r}<0,I{r}<0,I{r}>1),"DADOS INVÁLIDOS",IF(ABS(J{r}-ROUND(G{r}*H{r}*(1-I{r}),2))>0.005,"TOTAL DIVERGENTE",IF(P{r}<>"Concluída","REVISAR STATUS","CONFERIDO"))))))'}
 for col,formula in fs.items():s.cell(r,col,formula)
t=Table(displayName='tblItensVenda',ref='B7:Q1007');t.tableStyleInfo=TableStyleInfo(name='TableStyleMedium2',showRowStripes=True,showColumnStripes=False,showFirstColumn=False,showLastColumn=False);s.add_table(t)
for form,bg,fg in [('$Q8="CONFERIDO"','E2F0D9','225C21'),('OR($Q8="SEM VENDA",$Q8="ID/SEQ DUPLICADO",$Q8="DADOS INVÁLIDOS",$Q8="TOTAL DIVERGENTE")','FCE8E6','9C0006'),('$Q8="REVISAR STATUS"','FFF2CC','805900')]:s.conditional_formatting.add('Q8:Q1007',FormulaRule(formula=[form],fill=PatternFill('solid',fgColor=bg),font=Font(color=fg,bold=True)))
s['M7'].comment=Comment('Lucro aproximado do item = total líquido do item − quantidade × custo unitário registrado. Não inclui despesas, impostos ou rateios.','Equipe PDV')
s['Q7'].comment=Comment('A conferência é apenas aritmética e de vínculo. Não comprova pagamento, estoque, legalidade ou integridade dos dados; descontos gerais ainda não existem.','Equipe PDV')
s.freeze_panes='C8';s.sheet_view.zoomScale=80
for col in range(19,26):s.column_dimensions[get_column_letter(col)].width=17
for row,title,content in [(7,'COMO CONSULTAR','Use as setas na linha 7 para filtrar por ID, produto, data, operador, status da venda ou conferência. Combine os filtros e limpe-os para mostrar todos os registros.'),(13,'ENTENDA OS VALORES','Subtotal bruto = quantidade × preço. Total item inclui desconto do item. Lucro estimado = total item − quantidade × custo registrado; não é lucro líquido.'),(19,'ATENÇÃO','A aba é histórico de teste: não edite nem apague dados. Sinalização verde não confirma pagamento. Em caso de divergência, investigue o cupom e os detalhes.'),(25,'LIMITAÇÕES','Sem cancelamento, estorno, auditoria, proteção efetiva, gravação atômica ou concorrência segura. Uso exclusivo em cópia com dados fictícios.')]:
 s.merge_cells(start_row=row,start_column=19,end_row=row,end_column=25);c=s.cell(row,19,title);c.fill=PatternFill('solid',fgColor='68C2C7');c.font=Font(name='Segoe UI',size=10,bold=True,color='173A3B');c.alignment=Alignment(indent=1,vertical='center')
 s.merge_cells(start_row=row+1,start_column=19,end_row=row+4,end_column=25);c=s.cell(row+1,19,content);c.fill=PatternFill('solid',fgColor='EFEFEF');c.font=Font(name='Segoe UI',size=10,color='262626');c.alignment=Alignment(indent=1,vertical='center',wrap_text=True)
s.print_area='B1:Q40';s.page_setup.orientation='landscape';s.page_setup.fitToWidth=1;s.page_setup.fitToHeight=0
w.calculation.fullCalcOnLoad=True;w.calculation.forceFullCalc=True
w.save('PDV_Empresa_itens_v1.xlsx')
