from openpyxl import load_workbook
from openpyxl.styles import Font,PatternFill,Border,Side,Alignment,Protection
from openpyxl.worksheet.table import Table,TableStyleInfo
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import FormulaRule
from openpyxl.comments import Comment
from openpyxl.utils import get_column_letter
from openpyxl.workbook.defined_name import DefinedName
w=load_workbook('PDV_Empresa_itens_v1.xlsx');s=w['06_CAIXA'];s['B4']='CONTROLE DE CAIXA POR TURNO';s['B5']='TESTE MANUAL • lance cada movimento uma única vez; o PDV ainda não integra o caixa.';s.freeze_panes='C8';s.sheet_view.zoomScale=80
# three tables horizontally; reserved empty separator columns W, AJ
turn=['ID_Turno','Data','Caixa','Turno','Operador','Hora Abertura','Fundo Inicial','Suprimentos','Sangrias','Vendas Dinheiro','Recebimentos Dinheiro','Estornos Dinheiro','Esperado Gaveta','Dinheiro Contado','Diferença','Status','Hora Fechamento','Conferido por','Vendas Todas Formas','Conferência','Observações']
mov=['ID_Mov','ID_Turno','Data','Hora','Tipo','Forma','Valor','Operador','Documento','Observações','Conferência']
count=['ID_Turno','Denominação','Quantidade','Total','Conferência']
def section(start,headers,rows,name):
 for j,h in enumerate(headers,start):
  c=s.cell(7,j,h);c.fill=PatternFill('solid',fgColor='383838');c.font=Font(name='Segoe UI',size=9,bold=True,color='FFFFFF');c.alignment=Alignment(wrap_text=True,vertical='center');s.column_dimensions[get_column_letter(j)].width=max(15,min(22,len(h)+4))
 for r in range(8,8+rows):
  for j in range(start,start+len(headers)):
   c=s.cell(r,j);c.fill=PatternFill('solid',fgColor='FFF9E6');c.border=Border(bottom=Side(style='thin',color='D39700'));c.font=Font(name='Segoe UI',size=10,color='262626');c.protection=Protection(locked=False);c.alignment=Alignment(vertical='center')
 t=Table(displayName=name,ref=f'{get_column_letter(start)}7:{get_column_letter(start+len(headers)-1)}{7+rows}');t.tableStyleInfo=TableStyleInfo(name='TableStyleMedium2',showRowStripes=True,showColumnStripes=False,showFirstColumn=False,showLastColumn=False);s.add_table(t)
section(2,turn,50,'tblCaixa');section(24,mov,300,'tblMovCaixa');section(36,count,250,'tblContagemCaixa')
s.row_dimensions[7].height=34;s.column_dimensions['W'].width=3;s.column_dimensions['AI'].width=3
# cells B:V by enumeration
def calc(r,col,f):
 c=s.cell(r,col,f);c.fill=PatternFill('solid',fgColor='EEF2F3');c.font=Font(name='Segoe UI',size=10,color='262626');c.protection=Protection(locked=True)
for r in range(8,58):
 # Y = ID turno, AB = tipo, AC forma, AD valor
 crit=f"$Y$8:$Y$307,B{r}"
 fs={9:f'=IF(B{r}="","",SUMIFS($AD$8:$AD$307,{crit},$AB$8:$AB$307,"Suprimento",$AC$8:$AC$307,"Dinheiro"))',10:f'=IF(B{r}="","",SUMIFS($AD$8:$AD$307,{crit},$AB$8:$AB$307,"Sangria",$AC$8:$AC$307,"Dinheiro"))',11:f'=IF(B{r}="","",SUMIFS($AD$8:$AD$307,{crit},$AB$8:$AB$307,"Venda",$AC$8:$AC$307,"Dinheiro"))',12:f'=IF(B{r}="","",SUMIFS($AD$8:$AD$307,{crit},$AB$8:$AB$307,"Recebimento",$AC$8:$AC$307,"Dinheiro"))',13:f'=IF(B{r}="","",SUMIFS($AD$8:$AD$307,{crit},$AB$8:$AB$307,"Estorno",$AC$8:$AC$307,"Dinheiro"))',14:f'=IF(B{r}="","",H{r}+I{r}-J{r}+K{r}+L{r}-M{r})',15:f'=IF(B{r}="","",IF(COUNTIF($AJ$8:$AJ$257,B{r})=0,"",SUMIF($AJ$8:$AJ$257,B{r},$AM$8:$AM$257)))',16:f'=IF(OR(B{r}="",O{r}=""),"",ROUND(O{r}-N{r},2))',20:f'=IF(B{r}="","",SUMIFS($AD$8:$AD$307,{crit},$AB$8:$AB$307,"Venda")-SUMIFS($AD$8:$AD$307,{crit},$AB$8:$AB$307,"Estorno"))',21:f'=IF(B{r}="","",IF(COUNTIF($B$8:$B$57,B{r})>1,"ID DUPLICADO",IF(OR(C{r}="",D{r}="",E{r}="",F{r}="",G{r}="",NOT(ISNUMBER(H{r})),H{r}<0,Q{r}=""),"DADOS INCOMPLETOS",IF(AND(Q{r}="Aberto",COUNTIFS($D$8:$D$57,D{r},$Q$8:$Q$57,"Aberto")>1),"CAIXA JÁ ABERTO",IF(COUNTIFS($Y$8:$Y$307,B{r},$AH$8:$AH$307,"<>OK")+COUNTIFS($AJ$8:$AJ$257,B{r},$AN$8:$AN$257,"<>OK")>0,"REVISAR LANÇAMENTOS",IF(Q{r}="Fechado",IF(OR(O{r}="",R{r}="",S{r}=""),"FECHAMENTO INCOMPLETO",IF(ABS(P{r})<0.005,"CONFERIDO",IF(ABS(P{r})<=5,"DIFERENÇA ATÉ R$ 5","DIFERENÇA ACIMA R$ 5"))),"TURNO ABERTO"))))))'}
 for col,f in fs.items():calc(r,col,f)
 for col in range(8,17):s.cell(r,col).number_format='"R$" #,##0.00;[Red]-"R$" #,##0.00'
 s.cell(r,20).number_format='"R$" #,##0.00';s.cell(r,3).number_format='dd/mm/yyyy';s.cell(r,7).number_format='hh:mm';s.cell(r,18).number_format='hh:mm';s.cell(r,2).number_format='@';s.cell(r,4).number_format='@'
for r in range(8,308):
 # AH flag
 f=f'=IF(X{r}="","",IF(COUNTIF($X$8:$X$307,X{r})>1,"ID DUPLICADO",IF(OR(Y{r}="",COUNTIF($B$8:$B$57,Y{r})<>1),"TURNO INVÁLIDO",IF(OR(Z{r}="",AA{r}="",AB{r}="",AC{r}="",NOT(ISNUMBER(AD{r})),AD{r}<=0,AE{r}=""),"DADOS INCOMPLETOS",IF(AND(OR(AB{r}="Suprimento",AB{r}="Sangria"),AC{r}<>"Dinheiro"),"FORMA INVÁLIDA","OK")))))'
 calc(r,34,f);s.cell(r,26).number_format='dd/mm/yyyy';s.cell(r,27).number_format='hh:mm';s.cell(r,30).number_format='"R$" #,##0.00';s.cell(r,24).number_format='@';s.cell(r,25).number_format='@'
for r in range(8,258):
 calc(r,39,f'=IF(AJ{r}="","",IF(OR(NOT(ISNUMBER(AK{r})),NOT(ISNUMBER(AL{r}))),"",ROUND(AK{r}*AL{r},2)))')
 calc(r,40,f'=IF(AJ{r}="","",IF(COUNTIF($B$8:$B$57,AJ{r})<>1,"TURNO INVÁLIDO",IF(OR(NOT(ISNUMBER(AK{r})),NOT(ISNUMBER(AL{r})),AL{r}<0,AL{r}<>INT(AL{r})),"DADOS INCOMPLETOS",IF(COUNTIFS($AJ$8:$AJ$257,AJ{r},$AK$8:$AK$257,AK{r})>1,"DENOMINAÇÃO DUPLICADA","OK"))))')
 s.cell(r,37).number_format='"R$" #,##0.00';s.cell(r,39).number_format='"R$" #,##0.00';s.cell(r,36).number_format='@'
def val(t,rg,f1,op=None,f2=None,error='Informe valor válido.',allow=True):
 d=DataValidation(type=t,formula1=f1,formula2=f2,operator=op,allow_blank=allow);d.showErrorMessage=True;d.errorTitle='Valor inválido';d.error=error;d.errorStyle='stop';s.add_data_validation(d);d.add(rg)
val('list','Q8:Q57','"Aberto,Fechado"',error='Selecione Aberto ou Fechado.')
val('list','E8:E57','"Manhã,Tarde,Noite"',error='Selecione o turno.')
val('list','AB8:AB307','"Venda,Recebimento,Suprimento,Sangria,Estorno"',error='Selecione o tipo.')
val('list','AC8:AC307','"Dinheiro,PIX,Cartão Débito,Cartão Crédito,Transferência,Vale,Cheque,A Prazo"',error='Selecione a forma.')
for rg in ['H8:H57','AD8:AD307']:val('decimal',rg,'0','greaterThanOrEqual',error='Valor deve ser não negativo; movimento exige valor positivo.')
val('whole','AL8:AL257','0','greaterThanOrEqual',error='Quantidade deve ser inteira e não negativa.')
lists=w['15_LISTAS'];lists['H7']='listaDenominacoes'
for row,amount in enumerate([200,100,50,20,10,5,2,1,.50,.25,.10,.05,.01],8):
 lists.cell(row,8,amount).number_format='0.00'
w.defined_names.add(DefinedName('listaDenominacoes',attr_text="'15_LISTAS'!$H$8:$H$20"))
val('list','AK8:AK257','=listaDenominacoes',error='Selecione uma denominação válida.')
for rg in ['C8:C57','Z8:Z307']:val('date',rg,'DATE(2000,1,1)','between','DATE(2100,12,31)',error='Informe uma data válida.')
for rg in ['G8:G57','R8:R57','AA8:AA307']:val('time',rg,'0','between','0.999999',error='Informe uma hora válida.')
# status highlights for every block
for rg,form in [('U8:U57','AND($B8<>"",OR($U8="CONFERIDO",$U8="TURNO ABERTO"))'),('AH8:AH307','AND($X8<>"",$AH8="OK")'),('AN8:AN257','AND($AJ8<>"",$AN8="OK")')]:s.conditional_formatting.add(rg,FormulaRule(formula=[form],fill=PatternFill('solid',fgColor='E2F0D9'),font=Font(bold=True,color='225C21')))
for rg,form in [('U8:U57','AND($B8<>"",$U8<>"CONFERIDO",$U8<>"TURNO ABERTO",$U8<>"DIFERENÇA ATÉ R$ 5")'),('AH8:AH307','AND($X8<>"",$AH8<>"OK")'),('AN8:AN257','AND($AJ8<>"",$AN8<>"OK")')]:s.conditional_formatting.add(rg,FormulaRule(formula=[form],fill=PatternFill('solid',fgColor='FCE8E6'),font=Font(bold=True,color='9C0006')))
s.conditional_formatting.add('U8:U57',FormulaRule(formula=['$U8="DIFERENÇA ATÉ R$ 5"'],fill=PatternFill('solid',fgColor='FFF2CC'),font=Font(bold=True,color='805900')))
# separate distinct yellow warning 5
s['N7'].comment=Comment('Fundo + suprimentos − sangrias + vendas em dinheiro + recebimentos em dinheiro − estornos em dinheiro.','Equipe PDV')
s['T7'].comment=Comment('Venda menos estorno em todas as formas; movimentos são lançados manualmente e não estão vinculados automaticamente ao PDV.','Equipe PDV')
s.print_area='B1:V25';s.page_setup.orientation='landscape';s.page_setup.fitToWidth=1;s.page_setup.fitToHeight=0
w.calculation.fullCalcOnLoad=True;w.calculation.forceFullCalc=True
w.save('PDV_Empresa_caixa_v1.xlsx')
