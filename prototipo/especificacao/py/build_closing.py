from openpyxl import load_workbook
from openpyxl.styles import Font,PatternFill,Border,Side,Alignment
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import FormulaRule
from openpyxl.comments import Comment
from openpyxl.utils import get_column_letter
w=load_workbook('PDV_Empresa_pagamentos_v1.xlsx');s=w['08_FECHAMENTO'];s['B4']='FECHAMENTO DE VENDAS E PAGAMENTOS';s['B5']='PRÉVIA DE TESTE  •  Filtros por data e operador  •  Não substitui conferência bancária.'
s.sheet_view.zoomScale=85;s.freeze_panes='C7'
for i,wd in enumerate([25,18,20,19,19,19,20,20,22,19,20,20,20,20,20],2):s.column_dimensions[get_column_letter(i)].width=wd
DARK='383838';TURQ='68C2C7';INPUT='FFF9E6';WARN='FFF2CC'
def label(c):c.fill=PatternFill('solid',fgColor='EFEFEF');c.font=Font(name='Segoe UI',bold=True,size=10,color='262626');c.alignment=Alignment(vertical='center',wrap_text=True,indent=1)
def input_(c):c.fill=PatternFill('solid',fgColor=INPUT);c.border=Border(bottom=Side(style='medium',color='D39700'));c.font=Font(name='Segoe UI',size=10,color='262626');c.alignment=Alignment(vertical='center',indent=1)
def section(row,title):
 s.merge_cells(start_row=row,start_column=2,end_row=row,end_column=9);c=s.cell(row,2,title);c.fill=PatternFill('solid',fgColor=TURQ);c.font=Font(name='Segoe UI',size=10,bold=True,color='173A3B');c.alignment=Alignment(vertical='center',indent=1);s.row_dimensions[row].height=25
def valcell(c,money=False):
 c.fill=PatternFill('solid',fgColor='F1F3F4');c.font=Font(name='Segoe UI',size=11,bold=True,color='262626');c.alignment=Alignment(vertical='center',horizontal='right');
 if money:c.number_format='"R$" #,##0.00;[Red]-"R$" #,##0.00'
for c,text in [('B7','Data inicial'),('E7','Data final'),('H7','Operador contém')]:s[c]=text;label(s[c])
for c in ['C7','F7','I7']:input_(s[c])
s['C7']='=TODAY()';s['F7']='=TODAY()';s['C7'].number_format='dd/mm/yyyy';s['F7'].number_format='dd/mm/yyyy';s.row_dimensions[7].height=26
s.merge_cells('B8:I8');s['B8']='=IF(OR(NOT(ISNUMBER(C7)),NOT(ISNUMBER(F7))),"INFORME DATAS VÁLIDAS",IF(C7>F7,"DATAS INVÁLIDAS: INÍCIO POSTERIOR AO FIM","FILTRO ATIVO • status: Concluída • operador vazio = todos"))';s['B8'].font=Font(name='Segoe UI',size=10,bold=True,color='173A3B');s['B8'].alignment=Alignment(vertical='center',indent=1);s.row_dimensions[8].height=23
v=DataValidation(type='date',operator='between',formula1='DATE(2000,1,1)',formula2='DATE(2100,12,31)',allow_blank=False);v.showErrorMessage=True;v.error='Informe uma data válida entre 2000 e 2100.';v.errorStyle='stop';s.add_data_validation(v);v.add('C7');v.add('F7')
# user text must not act as wildcard
wild='"*"&SUBSTITUTE(SUBSTITUTE(SUBSTITUTE($I$7,"~","~~"),"*","~*"),"?","~?")&"*"'
vc="'04_VENDAS'!$C$8:$C$507";vo="'04_VENDAS'!$E$8:$E$507";vs="'04_VENDAS'!$I$8:$I$507";vi="'04_VENDAS'!$B$8:$B$507";vt="'04_VENDAS'!$H$8:$H$507"
pc="'07_PAGAMENTOS'!$H$8:$H$1007";po="'07_PAGAMENTOS'!$I$8:$I$1007";ps="'07_PAGAMENTOS'!$J$8:$J$1007";pid="'07_PAGAMENTOS'!$B$8:$B$1007";pf="'07_PAGAMENTOS'!$D$8:$D$1007";pa="'07_PAGAMENTOS'!$E$8:$E$1007";pr="'07_PAGAMENTOS'!$F$8:$F$1007";pt="'07_PAGAMENTOS'!$G$8:$G$1007"
def crit(date,op,status,id):return f'{id},"<>",{date},">="&$C$7,{date},"<"&($F$7+1),{op},{wild},{status},"Concluída"'
cv=crit(vc,vo,vs,vi);cp=crit(pc,po,ps,pid)
valid='AND(ISNUMBER($C$7),ISNUMBER($F$7),$C$7<=$F$7)'
def safe(expr):return f'=IF({valid},{expr},"")'
section(10,'01  RESUMO DE VENDAS CONCLUÍDAS')
for r,l1,f1,l2,f2 in [(11,'Cupons',f'COUNTIFS({cv})','Itens vendidos',f'SUMIFS(\'04_VENDAS\'!$K$8:$K$507,{cv})'),(12,'Faturamento líquido',f'SUMIFS({vt},{cv})','Ticket médio','IFERROR(C12/C11,0)'),(13,'Pagamentos aplicados',f'SUMIFS({pa},{cp})','Diferença pagamentos','ROUND(F13-C12,2)')]:
 s.cell(r,2,l1);label(s.cell(r,2));s.cell(r,3,safe(f1));valcell(s.cell(r,3),r in [12,13]);s.cell(r,5,l2);label(s.cell(r,5));s.cell(r,6,safe(f2));valcell(s.cell(r,6),r in [12,13]);s.row_dimensions[r].height=25
# 13 second formula needs F? Pagamentos applied C13, difference F13 = C13-C12
s['F13']=safe('ROUND(C13-C12,2)');valcell(s['F13'],True)
section(16,'02  PAGAMENTOS POR FORMA • VALOR APLICADO, ENTREGUE E TROCO')
heads=['Forma de pagamento','Transações','Valor aplicado','Valor entregue','Troco','% do total','Conferência']
for i,h in enumerate(heads,2):c=s.cell(17,i,h);c.fill=PatternFill('solid',fgColor=DARK);c.font=Font(name='Segoe UI',size=10,bold=True,color='FFFFFF');c.alignment=Alignment(wrap_text=True,vertical='center')
s.row_dimensions[17].height=30
forms=['Dinheiro','PIX','Cartão Débito','Cartão Crédito','Transferência','Vale','Cheque','A Prazo']
for r,form in enumerate(forms,18):
 s.cell(r,2,form);s.cell(r,2).font=Font(name='Segoe UI',size=10,color='262626')
 for col,f in [(3,f'COUNTIFS({cp},{pf},B{r})'),(4,f'SUMIFS({pa},{cp},{pf},B{r})'),(5,f'SUMIFS({pr},{cp},{pf},B{r})'),(6,f'SUMIFS({pt},{cp},{pf},B{r})'),(7,f'IFERROR(D{r}/$C$13,0)'),(8,f'IF(C{r}=0,"—",IF(ABS(E{r}-F{r}-D{r})<0.005,"ARITMÉTICA OK","REVISAR VALORES"))')]:s.cell(r,col,safe(f));valcell(s.cell(r,col),col in (4,5,6))
 s.cell(r,7).number_format='0.0%';s.row_dimensions[r].height=23
s['B26']='TOTAL LISTADO';label(s['B26'])
for col in range(3,7):s.cell(26,col,safe(f'SUM({get_column_letter(col)}18:{get_column_letter(col)}25)'));valcell(s.cell(26,col),col>=4)
s['B27']='Formas não listadas';label(s['B27']);s['D27']=safe('ROUND(C13-D26,2)');valcell(s['D27'],True)
s['B28']='ALERTA GERAL';label(s['B28']);s.merge_cells('C28:I28');s['C28']=safe('IF(OR(ABS(F13)>0.005,ABS(D27)>0.005,C31>0,F31>0,C32>0,F32>0),"ATENÇÃO: REVISAR DIVERGÊNCIAS E ALERTAS","SEM DIVERGÊNCIA ARITMÉTICA DETECTADA")');s['C28'].font=Font(name='Segoe UI',size=10,bold=True,color='173A3B');s['C28'].alignment=Alignment(vertical='center',indent=1);s.row_dimensions[28].height=24
section(30,'03  ALERTAS DO PERÍODO E VÍNCULOS')
for r,l,f,l2,f2 in [(31,'Linhas de pagamento com erro',f'COUNTIFS({cp},\'07_PAGAMENTOS\'!$N$8:$N$1007,"<>OK")','Vendas com diferença',f'COUNTIFS({cv},\'04_VENDAS\'!$N$8:$N$507,"DIVERGÊNCIA")'),(32,'Vendas sem itens',f'COUNTIFS({cv},\'04_VENDAS\'!$K$8:$K$507,"<=0")','Pagamentos sem venda (geral)','COUNTIF(\'07_PAGAMENTOS\'!$N$8:$N$1007,"VENDA NÃO ENCONTRADA")')]:
 s.cell(r,2,l);label(s.cell(r,2));s.cell(r,3,safe(f));valcell(s.cell(r,3));s.cell(r,5,l2);label(s.cell(r,5));s.cell(r,6,safe(f2));valcell(s.cell(r,6));s.row_dimensions[r].height=27
section(35,'04  ORIENTAÇÕES E LIMITAÇÕES')
for a,b,text in [(36,37,'Altere as datas em C7 e F7; deixe I7 vazio para todos os operadores ou digite parte do nome. As datas são inclusivas. Para voltar ao dia atual, digite =HOJE() nas duas datas.'),(38,39,'O relatório considera somente vendas Concluídas. Pagamentos sem venda vinculada aparecem apenas no alerta geral, pois não possuem data/operador confiáveis. A conciliação é aritmética e não comprova PIX ou cartão.'),(40,42,'Aba de teste: não fecha ou congela o dia, não consulta caixa por turno e não trata taxas, liquidações, cancelamentos, devoluções, crediário ou registros fiscais. Confirme os valores no Excel e em fontes externas.')]:
 s.merge_cells(start_row=a,start_column=2,end_row=b,end_column=9);c=s.cell(a,2,text);c.fill=PatternFill('solid',fgColor='EFEFEF' if a!=40 else WARN);c.font=Font(name='Segoe UI',size=10,color='262626');c.alignment=Alignment(wrap_text=True,vertical='center',indent=1);s.row_dimensions[a].height=24;s.row_dimensions[b].height=24
s['C13'].comment=Comment('Valor aplicado líquido de troco, não valor entregue. Depende de dados do histórico de pagamentos.','Equipe PDV')
s['F32'].comment=Comment('Contagem global, sem filtro de data ou operador, pois pagamentos órfãos não têm venda para fornecer esses campos.','Equipe PDV')
s.conditional_formatting.add('F13',FormulaRule(formula=['AND(ISNUMBER(F13),ABS(F13)>0.005)'],fill=PatternFill('solid',fgColor='FCE8E6'),font=Font(color='9C0006',bold=True)))
s.conditional_formatting.add('C28',FormulaRule(formula=['LEFT(C28,7)="ATENÇÃO"'],fill=PatternFill('solid',fgColor='FCE8E6'),font=Font(color='9C0006',bold=True)))
s.print_area='B1:I42';s.page_setup.orientation='landscape';s.page_setup.fitToWidth=1;s.page_setup.fitToHeight=0
w.calculation.fullCalcOnLoad=True;w.calculation.forceFullCalc=True;w.save('PDV_Empresa_fechamento_v1.xlsx')
