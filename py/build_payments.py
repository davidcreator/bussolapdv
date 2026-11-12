from openpyxl import load_workbook
from openpyxl.styles import Font,PatternFill,Alignment,Protection
from openpyxl.worksheet.table import Table,TableStyleInfo
from openpyxl.formatting.rule import FormulaRule
from openpyxl.comments import Comment
from openpyxl.utils import get_column_letter
w=load_workbook('PDV_Empresa_caixa_v1.xlsx');s=w['07_PAGAMENTOS'];s.sheet_state='visible';s['B4']='PAGAMENTOS E CONFERÊNCIA';s['B5']='TESTE  •  verifique vínculos, valores e diferenças; confirmação bancária é externa.'
if 'tblPagamentos' in s.tables:del s.tables['tblPagamentos']
headers=['ID_Venda','Seq','Forma Pagamento','Valor Aplicado','Valor Entregue','Troco','Data Venda','Operador','Status Venda','Total Venda','Total Aplicado Venda','Diferença Venda','Verificação Parcela','Conciliação Venda','Referência / NSU','Observações']
width=[17,10,22,19,19,16,16,21,19,18,23,19,26,24,22,28]
for col,(h,wd) in enumerate(zip(headers,width),2):
 c=s.cell(7,col,h);c.fill=PatternFill('solid',fgColor='383838');c.font=Font(name='Segoe UI',size=10,bold=True,color='FFFFFF');c.alignment=Alignment(vertical='center',wrap_text=True);s.column_dimensions[get_column_letter(col)].width=wd
s.row_dimensions[7].height=32
for r in range(8,1008):
 for col in range(2,18):
  c=s.cell(r,col);c.font=Font(name='Segoe UI',size=10,color='262626');c.fill=PatternFill('solid',fgColor='F2F4F5');c.alignment=Alignment(vertical='center');c.protection=Protection(locked=True)
 for col in (5,6,7,11,12,13):s.cell(r,col).number_format='"R$" #,##0.00;[Red]-"R$" #,##0.00'
 s.cell(r,8).number_format='dd/mm/yyyy'
 fs={8:f'=IF(B{r}="","",IFERROR(INDEX(\'04_VENDAS\'!$C$8:$C$507,MATCH(B{r},\'04_VENDAS\'!$B$8:$B$507,0)),""))',9:f'=IF(B{r}="","",IFERROR(INDEX(\'04_VENDAS\'!$E$8:$E$507,MATCH(B{r},\'04_VENDAS\'!$B$8:$B$507,0)),""))',10:f'=IF(B{r}="","",IFERROR(INDEX(\'04_VENDAS\'!$I$8:$I$507,MATCH(B{r},\'04_VENDAS\'!$B$8:$B$507,0)),"SEM VENDA"))',11:f'=IF(B{r}="","",IFERROR(INDEX(\'04_VENDAS\'!$H$8:$H$507,MATCH(B{r},\'04_VENDAS\'!$B$8:$B$507,0)),0))',12:f'=IF(B{r}="","",SUMIF($B$8:$B$1007,B{r},$E$8:$E$1007))',13:f'=IF(B{r}="","",ROUND(L{r}-K{r},2))',14:f'=IF(B{r}="","",IF(J{r}="SEM VENDA","VENDA NÃO ENCONTRADA",IF(IFERROR(OR(NOT(ISNUMBER(C{r})),C{r}<=0,C{r}<>INT(C{r})),TRUE),"SEQUÊNCIA INVÁLIDA",IF(COUNTIFS($B$8:$B$1007,B{r},$C$8:$C$1007,C{r})>1,"ID/SEQ DUPLICADO",IF(AND(D{r}<>"Dinheiro",D{r}<>"PIX"),"FORMA NÃO SUPORTADA",IF(OR(NOT(ISNUMBER(E{r})),NOT(ISNUMBER(F{r})),NOT(ISNUMBER(G{r}))),"VALOR INVÁLIDO",IF(OR(E{r}<0,F{r}<=0,G{r}<0,G{r}>F{r}),"VALOR INVÁLIDO",IF(AND(D{r}<>"Dinheiro",G{r}<>0),"TROCO NÃO É DINHEIRO",IF(ABS(E{r}-ROUND(F{r}-G{r},2))>0.005,"VALOR INCONSISTENTE","OK")))))))))',15:f'=IF(B{r}="","",IF(J{r}="SEM VENDA","SEM VENDA",IF(J{r}<>"Concluída","REVISAR STATUS",IF(ABS(M{r})<0.005,"VALORES CONFEREM","DIVERGÊNCIA"))))'}
 for col,f in fs.items():s.cell(r,col,f)
t=Table(displayName='tblPagamentos',ref='B7:Q1007');t.tableStyleInfo=TableStyleInfo(name='TableStyleMedium2',showRowStripes=True,showColumnStripes=False,showFirstColumn=False,showLastColumn=False);s.add_table(t)
for rg,f,bg,fg in [('N8:N1007','$N8="OK"','E2F0D9','225C21'),('N8:N1007','AND($B8<>"",$N8<>"OK")','FCE8E6','9C0006'),('O8:O1007','$O8="VALORES CONFEREM"','E2F0D9','225C21'),('O8:O1007','OR($O8="DIVERGÊNCIA",$O8="SEM VENDA")','FCE8E6','9C0006'),('O8:O1007','$O8="REVISAR STATUS"','FFF2CC','805900')]:s.conditional_formatting.add(rg,FormulaRule(formula=[f],fill=PatternFill('solid',fgColor=bg),font=Font(bold=True,color=fg)))
s['E7'].comment=Comment('Valor aplicado à venda, descontado o troco. A conferência compara esse valor ao total do cupom; não verifica recebimento externo.','Equipe PDV')
s['P7'].comment=Comment('Referência reservada; a macro atual não captura NSU nem ID de transação. Não preencha informações financeiras reais no protótipo.','Equipe PDV')
s.freeze_panes='C8';s.sheet_view.zoomScale=80
for col in range(19,26):s.column_dimensions[get_column_letter(col)].width=17
for row,title,text in [(7,'COMO CONSULTAR','Use as setas do cabeçalho para filtrar por venda, forma, data, operador ou alertas. Cada linha representa uma forma de pagamento de um cupom.'),(13,'VERIFICAÇÃO DA LINHA','A coluna N verifica vínculo, sequência duplicada, forma suportada, valores e troco. Apenas Dinheiro e PIX são suportados pela macro atual.'),(19,'CONCILIAÇÃO DO CUPOM','A coluna O compara a soma dos valores aplicados com o total da venda. É repetida em cada linha da venda: não some a coluna L para evitar duplicidade.'),(25,'ATENÇÃO','Valores que conferem não comprovam PIX ou liquidação bancária. Cartões, parcelamento, taxas, contas a receber e estornos ainda não estão implementados.'),(31,'ORIENTAÇÃO DE USO','Não altere o histórico nem insira dados reais. Identifique o cupom e consulte 04_VENDAS antes de investigar. Este arquivo é apenas para testes.')]:
 s.merge_cells(start_row=row,start_column=19,end_row=row,end_column=25);c=s.cell(row,19,title);c.fill=PatternFill('solid',fgColor='68C2C7');c.font=Font(name='Segoe UI',size=10,bold=True,color='173A3B');c.alignment=Alignment(indent=1,vertical='center')
 s.merge_cells(start_row=row+1,start_column=19,end_row=row+4,end_column=25);c=s.cell(row+1,19,text);c.fill=PatternFill('solid',fgColor='FFF2CC' if row==25 else 'EFEFEF');c.font=Font(name='Segoe UI',size=10,color='262626');c.alignment=Alignment(indent=1,vertical='center',wrap_text=True)
s.print_area='B1:Q40';s.page_setup.orientation='landscape';s.page_setup.fitToWidth=1;s.page_setup.fitToHeight=0
w.calculation.fullCalcOnLoad=True;w.calculation.forceFullCalc=True;w.save('PDV_Empresa_pagamentos_v1.xlsx')
