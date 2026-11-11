from openpyxl import load_workbook
from openpyxl.styles import Font,PatternFill,Border,Side,Alignment
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import FormulaRule
from openpyxl.comments import Comment
from openpyxl.utils import get_column_letter
w=load_workbook('PDV_Empresa_entradas_v1.xlsx');s=w['13_DASHBOARD'];s['B4']='DASHBOARD GERENCIAL';s['B5']='TESTE • indicadores e bases para gráficos • sem conexão bancária ou fechamento definitivo.';s.sheet_view.zoomScale=80;s.freeze_panes='C8'
for c in range(2,24):s.column_dimensions[get_column_letter(c)].width=17
s.column_dimensions['B'].width=25;s.column_dimensions['E'].width=25;s.column_dimensions['H'].width=27;s.column_dimensions['K'].width=25;s.column_dimensions['N'].width=24;s.column_dimensions['R'].width=17;s.column_dimensions['S'].width=25;s.column_dimensions['T'].width=20;s.column_dimensions['U'].width=20
navy='383838';turq='68C2C7'
def inp(c):c.fill=PatternFill('solid',fgColor='FFF9E6');c.border=Border(bottom=Side(style='medium',color='D39700'));c.font=Font(name='Segoe UI',size=10,color='262626');c.alignment=Alignment(vertical='center',indent=1)
def label(c):c.fill=PatternFill('solid',fgColor='EFEFEF');c.font=Font(name='Segoe UI',size=10,bold=True,color='262626');c.alignment=Alignment(vertical='center',indent=1,wrap_text=True)
def stat(c,money=False,percent=False):
 c.fill=PatternFill('solid',fgColor='F2F4F5');c.font=Font(name='Segoe UI',size=11,bold=True,color='173A3B');c.alignment=Alignment(vertical='center',horizontal='right')
 if money:c.number_format='"R$" #,##0.00;[Red]-"R$" #,##0.00'
 if percent:c.number_format='0.0%'
def section(row,start,end,text):
 s.merge_cells(start_row=row,start_column=start,end_row=row,end_column=end);c=s.cell(row,start,text);c.fill=PatternFill('solid',fgColor=turq);c.font=Font(name='Segoe UI',size=10,bold=True,color='173A3B');c.alignment=Alignment(vertical='center',indent=1);s.row_dimensions[row].height=24
def header(row,start,values):
 for col,text in enumerate(values,start):c=s.cell(row,col,text);c.fill=PatternFill('solid',fgColor=navy);c.font=Font(name='Segoe UI',size=9,bold=True,color='FFFFFF');c.alignment=Alignment(wrap_text=True,vertical='center')
 s.row_dimensions[row].height=30
for addr,text in [('B7','Data inicial'),('E7','Data final'),('H7','Operador contém')]:s[addr]=text;label(s[addr])
for addr in ['C7','F7','I7']:inp(s[addr])
s['C7']='=TODAY()-6';s['F7']='=TODAY()';s['C7'].number_format='dd/mm/yyyy';s['F7'].number_format='dd/mm/yyyy';s.row_dimensions[7].height=26
v=DataValidation(type='date',operator='between',formula1='DATE(2000,1,1)',formula2='DATE(2100,12,31)',allow_blank=False);v.showErrorMessage=True;v.error='Informe data válida entre 2000 e 2100.';s.add_data_validation(v);v.add('C7');v.add('F7')
s.merge_cells('B8:I8');s['B8']='=IF(OR(NOT(ISNUMBER(C7)),NOT(ISNUMBER(F7))),"INFORME DATAS VÁLIDAS",IF(C7>F7,"DATAS INVÁLIDAS",IF(F7-C7+1>31,"ATENÇÃO: SÉRIE DIÁRIA LIMITADA A 31 DIAS","PERÍODO VÁLIDO • vendas concluídas")))';s['B8'].font=Font(name='Segoe UI',size=10,bold=True,color='173A3B');s['B8'].alignment=Alignment(vertical='center',indent=1)
vc="'04_VENDAS'!$C$8:$C$507";vo="'04_VENDAS'!$E$8:$E$507";vs="'04_VENDAS'!$I$8:$I$507";vi="'04_VENDAS'!$B$8:$B$507";vt="'04_VENDAS'!$H$8:$H$507";vitems="'04_VENDAS'!$K$8:$K$507"
pc="'07_PAGAMENTOS'!$H$8:$H$1007";po="'07_PAGAMENTOS'!$I$8:$I$1007";ps="'07_PAGAMENTOS'!$J$8:$J$1007";pid="'07_PAGAMENTOS'!$B$8:$B$1007";pf="'07_PAGAMENTOS'!$D$8:$D$1007";pa="'07_PAGAMENTOS'!$E$8:$E$1007"
ic="'05_ITENS_VENDA'!$N$8:$N$1007";io="'05_ITENS_VENDA'!$O$8:$O$1007";ist="'05_ITENS_VENDA'!$P$8:$P$1007";iid="'05_ITENS_VENDA'!$B$8:$B$1007";icode="'05_ITENS_VENDA'!$D$8:$D$1007";iq="'05_ITENS_VENDA'!$G$8:$G$1007";iv="'05_ITENS_VENDA'!$J$8:$J$1007";iprofit="'05_ITENS_VENDA'!$M$8:$M$1007"
wild='"*"&SUBSTITUTE(SUBSTITUTE(SUBSTITUTE($I$7,"~","~~"),"*","~*"),"?","~?")&"*"'
def cr(d,o,st,id,first='$C$7',last='$F$7'):return f'{id},"<>",{d},">="&{first},{d},"<"&({last}+1),{o},{wild},{st},"Concluída"'
cv=cr(vc,vo,vs,vi);cp=cr(pc,po,ps,pid);ci=cr(ic,io,ist,iid)
valid='AND(ISNUMBER($C$7),ISNUMBER($F$7),$C$7<=$F$7)'
def safe(f):return f'=IF({valid},{f},"")'
section(10,2,9,'01  INDICADORES DE VENDAS • PERÍODO E OPERADOR')
# fixed fields pairs
rows=[(11,'Faturamento líquido',f'SUMIFS({vt},{cv})','Nº de vendas',f'COUNTIFS({cv})'),(12,'Ticket médio','IFERROR(C11/F11,0)','Itens por venda',f'IFERROR(SUMIFS({vitems},{cv})/F11,0)'),(13,'Lucro bruto estimado',f'SUMIFS({iprofit},{ci})','Margem bruta estimada','IFERROR(C13/C11,0)'),(14,'Pagamentos aplicados',f'SUMIFS({pa},{cp})','Diferença de conciliação','ROUND(C14-C11,2)'),(15,'Pagamentos com erro',f'COUNTIFS({cp},\'07_PAGAMENTOS\'!$N$8:$N$1007,"<>OK")','Vendas com divergência',f'COUNTIFS({cv},\'04_VENDAS\'!$N$8:$N$507,"DIVERGÊNCIA")')]
for r,l,f,l2,f2 in rows:
 s.cell(r,2,l);label(s.cell(r,2));s.cell(r,3,safe(f));stat(s.cell(r,3),money=r in (11,13,14));s.cell(r,5,l2);label(s.cell(r,5));s.cell(r,6,safe(f2));stat(s.cell(r,6),money=r in (12,14),percent=r==13);s.row_dimensions[r].height=25
# fix items per sale as noncurrency
s['F12'].number_format='0.00'
section(17,2,9,'02  ESTOQUE E CREDIÁRIO • SALDOS ATUAIS, SEM FILTRO DE DATA OU OPERADOR')
# only product marked active and R ok, credits Q ok
stock="'02_PRODUTOS'!";credit="'09_CREDIARIO'!"
ind=[(18,'Produtos ativos',f'COUNTIFS({stock}$B$8:$B$107,"<>",{stock}$K$8:$K$107,"S")','Produtos sem estoque',f'COUNTIFS({stock}$K$8:$K$107,"S",{stock}$M$8:$M$107,"ESTOQUE VAZIO")'),(19,'Produtos estoque baixo',f'COUNTIFS({stock}$K$8:$K$107,"S",{stock}$M$8:$M$107,"ESTOQUE BAIXO")','Produtos com movimentos em revisão',f'COUNTIFS({stock}$B$8:$B$107,"<>",{stock}$R$8:$R$107,"REVISAR")'),(20,'Estoque a custo*',f'SUMIFS({stock}$O$8:$O$107,{stock}$K$8:$K$107,"S",{stock}$R$8:$R$107,"OK")','Saldo a receber*',f'SUMIFS({credit}$N$8:$N$207,{credit}$Q$8:$Q$207,"OK",{credit}$N$8:$N$207,">0")'),(21,'Saldo vencido*',f'SUMIFS({credit}$N$8:$N$207,{credit}$Q$8:$Q$207,"OK",{credit}$P$8:$P$207,"Vencido")','Títulos em revisão',f'COUNTIFS({credit}$B$8:$B$207,"<>",{credit}$Q$8:$Q$207,"<>OK")')]
for r,l,f,l2,f2 in ind:
 s.cell(r,2,l);label(s.cell(r,2));s.cell(r,3,'='+f);stat(s.cell(r,3),money=r in (20,21));s.cell(r,5,l2);label(s.cell(r,5));s.cell(r,6,'='+f2);stat(s.cell(r,6),money=r==20);s.row_dimensions[r].height=27
s.merge_cells('B23:I24');s['B23']='* Estoque a custo exclui produtos com movimentos em revisão; saldos de crediário excluem títulos em revisão. Indicadores de estoque e crédito não obedecem aos filtros acima. Acesse as abas de origem para investigar.';s['B23'].fill=PatternFill('solid',fgColor='FFF2CC');s['B23'].font=Font(name='Segoe UI',size=10,color='262626');s['B23'].alignment=Alignment(wrap_text=True,vertical='center',indent=1)
# payment chart data
section(10,11,15,'03  BASE • MIX DE PAGAMENTO')
header(11,11,['Forma','Transações','Aplicado','% do total','Observação'])
forms=['Dinheiro','PIX','Cartão Débito','Cartão Crédito','Transferência','Vale','Cheque','A Prazo']
for r,form in enumerate(forms,12):
 s.cell(r,11,form);s.cell(r,12,safe(f'COUNTIFS({cp},{pf},K{r})'));s.cell(r,13,safe(f'SUMIFS({pa},{cp},{pf},K{r})'));s.cell(r,14,safe(f'IFERROR(M{r}/$C$14,0)'));s.cell(r,15,'Só Dinheiro/PIX no protótipo' if r==12 else '');s.cell(r,13).number_format='"R$" #,##0.00';s.cell(r,14).number_format='0.0%'
s['K21']='Outras formas';s['M21']=safe('ROUND(C14-SUM(M12:M19),2)');s['M21'].number_format='"R$" #,##0.00';s['K23']='Pagamentos sem venda (global)';s['M23']='=COUNTIF(\'07_PAGAMENTOS\'!$N$8:$N$1007,"VENDA NÃO ENCONTRADA")';s['K23'].alignment=Alignment(wrap_text=True)
# daily base 31 days
section(27,2,6,'04  BASE • FATURAMENTO DIÁRIO (ATÉ 31 DIAS)')
header(28,2,['Data','Vendas','Faturamento','Itens','Ticket médio'])
for r in range(29,60):
 s.cell(r,2,f'=IF({valid},IF($C$7+ROW()-29<=$F$7,$C$7+ROW()-29,""),"")');s.cell(r,2).number_format='dd/mm/yyyy'
 daily=cr(vc,vo,vs,vi,first=f'$B{r}',last=f'$B{r}')
 for col,expr in [(3,f'COUNTIFS({daily})'),(4,f'SUMIFS({vt},{daily})'),(5,f'SUMIFS({vitems},{daily})'),(6,f'IFERROR(D{r}/C{r},0)')]:s.cell(r,col,f'=IF($B{r}="","",{expr})')
 for col in (4,6):s.cell(r,col).number_format='"R$" #,##0.00'
# product chart source, by underlying customer products entries
section(27,11,15,'05  BASE • VENDAS POR PRODUTO (NÃO ORDENADA)')
header(28,11,['Código','Produto','Quantidade','Valor vendido','Lucro estimado'])
for r in range(29,129):
 pr=r-21 # 29 -> product 8
 s.cell(r,11,f'=IF(\'02_PRODUTOS\'!B{pr}="","",\'02_PRODUTOS\'!B{pr})')
 s.cell(r,12,f'=IF(K{r}="","",\'02_PRODUTOS\'!D{pr})')
 for col,source in [(13,iq),(14,iv),(15,iprofit)]:s.cell(r,col,f'=IF(OR(K{r}="",NOT({valid})),"",SUMIFS({source},{ci},{icode},K{r}))')
 for col in (14,15):s.cell(r,col).number_format='"R$" #,##0.00'
for c in ['B11','B13','B20','E20']:s[c].comment=Comment('Consulte docs/20_dashboard para escopo, limitações e orientações de conferência.','Equipe PDV')
s['B13'].comment=Comment('Lucro estimado dos itens = total de item menos custo registrado. Não inclui taxas, impostos e despesas.','Equipe PDV')
s.conditional_formatting.add('F14',FormulaRule(formula=['AND(ISNUMBER(F14),ABS(F14)>0.005)'],fill=PatternFill('solid',fgColor='FCE8E6'),font=Font(color='9C0006',bold=True)))
s.print_area='B1:O24';s.page_setup.orientation='landscape';s.page_setup.fitToWidth=1;s.page_setup.fitToHeight=0;w.calculation.fullCalcOnLoad=True;w.calculation.forceFullCalc=True;w.save('PDV_Empresa_dashboard_v1.xlsx')
