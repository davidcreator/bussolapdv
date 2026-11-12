from openpyxl import load_workbook
from openpyxl.styles import Font,PatternFill,Border,Side,Alignment,Protection
from openpyxl.worksheet.table import Table,TableStyleInfo
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import FormulaRule
from openpyxl.comments import Comment
from openpyxl.utils import get_column_letter
w=load_workbook('PDV_Empresa_fechamento_v1.xlsx');s=w['09_CREDIARIO'];s['B4']='CREDIÁRIO  •  CONTAS A RECEBER';s['B5']='TESTE MANUAL  •  uma linha por parcela; recebimentos ficam na tabela à direita.';s.sheet_view.zoomScale=80;s.freeze_panes='C8'
titles=['ID_Título','ID_Venda','Código Cliente','Cliente','Data Venda','Parcela','Nº Parcelas','Vencimento','Principal','Encargos Lançados','Total Devido','Valor Pago Válido','Saldo Devedor','Dias Atraso','Status','Verificação','Observações']
receipts=['ID_Recebimento','ID_Título','Data Recebimento','Forma Pagamento','Valor','Operador','Documento / Referência','Observações','Verificação']
def section(start,headers,rows,name):
 for col,h in enumerate(headers,start):
  c=s.cell(7,col,h);c.fill=PatternFill('solid',fgColor='383838');c.font=Font(name='Segoe UI',size=10,bold=True,color='FFFFFF');c.alignment=Alignment(wrap_text=True,vertical='center');s.column_dimensions[get_column_letter(col)].width=max(16,min(len(h)+3,24))
 for row in range(8,8+rows):
  for col in range(start,start+len(headers)):
   c=s.cell(row,col);c.fill=PatternFill('solid',fgColor='FFF9E6');c.border=Border(bottom=Side(style='thin',color='D39700'));c.font=Font(name='Segoe UI',size=10,color='262626');c.alignment=Alignment(vertical='center');c.protection=Protection(locked=False)
 t=Table(displayName=name,ref=f'{get_column_letter(start)}7:{get_column_letter(start+len(headers)-1)}{7+rows}');t.tableStyleInfo=TableStyleInfo(name='TableStyleMedium2',showRowStripes=True,showColumnStripes=False,showFirstColumn=False,showLastColumn=False);s.add_table(t)
section(2,titles,200,'tblCrediario');section(24,receipts,500,'tblRecebimentosCrediario');s.row_dimensions[7].height=32
s.column_dimensions['S'].width=3;s.column_dimensions['W'].width=3
# B id C venda D code E name F data G numero H max I due J principal K manual charges L total M paid N balance O days P status Q check R notes
for r in range(8,208):
 fs={12:f'=IF(B{r}="","",IF(AND(ISNUMBER(J{r}),OR(ISNUMBER(K{r}),K{r}="")),ROUND(J{r}+K{r},2),""))',13:f'=IF(B{r}="","",SUMIFS($AB$8:$AB$507,$Y$8:$Y$507,B{r},$AF$8:$AF$507,"OK"))',14:f'=IF(OR(B{r}="",L{r}=""),"",ROUND(L{r}-M{r},2))',15:f'=IF(OR(B{r}="",N{r}="",NOT(ISNUMBER(I{r}))),"",IF(N{r}>0,MAX(0,TODAY()-I{r}),0))',16:f'=IF(B{r}="","",IF(Q{r}<>"OK","REVISAR",IF(N{r}<=0,"Pago",IF(I{r}<TODAY(),"Vencido","Em aberto"))))',17:f'=IF(B{r}="","",IF(COUNTIF($B$8:$B$207,B{r})<>1,"ID DUPLICADO",IF(OR(C{r}="",COUNTIFS(\'04_VENDAS\'!$B$8:$B$507,C{r},\'04_VENDAS\'!$I$8:$I$507,"Concluída")<>1),"REVISAR VENDA",IF(OR(D{r}="",E{r}="",NOT(ISNUMBER(F{r})),NOT(ISNUMBER(I{r})),NOT(ISNUMBER(G{r})),NOT(ISNUMBER(H{r})),NOT(ISNUMBER(J{r}))),"DADOS INCOMPLETOS",IFERROR(IF(OR(G{r}<1,H{r}<1,G{r}>H{r},G{r}<>INT(G{r}),H{r}<>INT(H{r}),J{r}<=0,K{r}<0,I{r}<F{r}),"DADOS INVÁLIDOS",IF(COUNTIFS($Y$8:$Y$507,B{r},$AF$8:$AF$507,"<>OK")>0,"REVISAR RECEBIMENTOS",IF(N{r}<-0.005,"PAGAMENTO EXCEDENTE","OK"))),"DADOS INVÁLIDOS")))))'}
 for col,f in fs.items():c=s.cell(r,col,f);c.fill=PatternFill('solid',fgColor='EEF2F3');c.font=Font(name='Segoe UI',size=10,color='262626');c.protection=Protection(locked=True)
 for col in (6,9):s.cell(r,col).number_format='dd/mm/yyyy'
 for col in (10,11,12,13,14):s.cell(r,col).number_format='"R$" #,##0.00;[Red]-"R$" #,##0.00'
 for col in (2,3,4):s.cell(r,col).number_format='@'
# X receipt ID Y title Z date AA payment AB value AC operator AD doc AE notes AF check
for r in range(8,508):
 f=f'=IF(X{r}="","",IF(COUNTIF($X$8:$X$507,X{r})<>1,"ID DUPLICADO",IF(OR(Y{r}="",COUNTIF($B$8:$B$207,Y{r})<>1),"TÍTULO INVÁLIDO",IF(OR(NOT(ISNUMBER(Z{r})),AA{r}="",NOT(ISNUMBER(AB{r})),AC{r}=""),"DADOS INCOMPLETOS",IFERROR(IF(OR(AB{r}<=0,AND(AA{r}<>"Dinheiro",AA{r}<>"PIX",AA{r}<>"Transferência",AA{r}<>"Cartão Débito")),"DADOS INVÁLIDOS",IF(Z{r}<INDEX($F$8:$F$207,MATCH(Y{r},$B$8:$B$207,0)),"DATA ANTERIOR À VENDA","OK")),"DADOS INVÁLIDOS")))))'
 c=s.cell(r,32,f);c.fill=PatternFill('solid',fgColor='EEF2F3');c.font=Font(name='Segoe UI',size=10,color='262626');c.protection=Protection(locked=True);s.cell(r,26).number_format='dd/mm/yyyy';s.cell(r,28).number_format='"R$" #,##0.00';s.cell(r,24).number_format='@';s.cell(r,25).number_format='@'
def dv(t,rg,f1,op=None,f2=None,msg='Informe um valor válido.'):
 d=DataValidation(type=t,formula1=f1,formula2=f2,operator=op,allow_blank=True);d.showErrorMessage=True;d.errorStyle='stop';d.error=msg;s.add_data_validation(d);d.add(rg)
for rg in ['F8:F207','I8:I207','Z8:Z507']:dv('date',rg,'DATE(2000,1,1)','between','DATE(2100,12,31)','Informe uma data válida.')
for rg in ['G8:G207','H8:H207']:dv('whole',rg,'1','between','360','Use um número inteiro entre 1 e 360.')
for rg in ['J8:J207','AB8:AB507']:dv('decimal',rg,'0','greaterThan',msg='Digite valor positivo.')
dv('decimal','K8:K207','0','greaterThanOrEqual',msg='Encargos devem ser não negativos.')
dv('list','AA8:AA507','"Dinheiro,PIX,Transferência,Cartão Débito"',msg='Escolha uma forma da lista.')
for rg,form,bg,fg in [('P8:P207','$P8="Pago"','E2F0D9','225C21'),('P8:P207','$P8="Em aberto"','E7F0F8','1F4E79'),('P8:P207','$P8="Vencido"','FCE8E6','9C0006'),('P8:P207','$P8="REVISAR"','FFF2CC','805900'),('Q8:Q207','AND($B8<>"",$Q8<>"OK")','FCE8E6','9C0006'),('AF8:AF507','AND($X8<>"",$AF8<>"OK")','FCE8E6','9C0006'),('AF8:AF507','$AF8="OK"','E2F0D9','225C21')]:s.conditional_formatting.add(rg,FormulaRule(formula=[form],fill=PatternFill('solid',fgColor=bg),font=Font(bold=True,color=fg)))
s['K7'].comment=Comment('Encargos manuais ainda não são calculados por contrato; não usar dados reais. Pagamentos anteriores não atualizam encargos automaticamente.','Equipe PDV')
s['M7'].comment=Comment('Soma apenas recebimentos marcados OK; pagamento excedente é sinalizado no título e exige revisão.','Equipe PDV')
# summary on right AH:AM
for col in range(34,40):s.column_dimensions[get_column_letter(col)].width=18
s.merge_cells('AH7:AM7');s['AH7']='PAINEL DE CONTAS A RECEBER  •  TESTE';s['AH7'].fill=PatternFill('solid',fgColor='68C2C7');s['AH7'].font=Font(name='Segoe UI',size=10,bold=True,color='173A3B');s['AH7'].alignment=Alignment(vertical='center',indent=1)
rows=[(9,'Saldo em aberto', '=SUMIFS($N$8:$N$207,$Q$8:$Q$207,"OK",$P$8:$P$207,"Em aberto")'),(10,'Saldo vencido','=SUMIFS($N$8:$N$207,$Q$8:$Q$207,"OK",$P$8:$P$207,"Vencido")'),(11,'A vencer em 7 dias','=SUMIFS($N$8:$N$207,$Q$8:$Q$207,"OK",$P$8:$P$207,"Em aberto",$I$8:$I$207,">="&TODAY(),$I$8:$I$207,"<="&TODAY()+7)'),(12,'A vencer em 30 dias','=SUMIFS($N$8:$N$207,$Q$8:$Q$207,"OK",$P$8:$P$207,"Em aberto",$I$8:$I$207,">="&TODAY(),$I$8:$I$207,"<="&TODAY()+30)'),(13,'Títulos para revisão','=COUNTIFS($B$8:$B$207,"<>",$Q$8:$Q$207,"<>OK")'),(14,'Recebimentos para revisão','=COUNTIFS($X$8:$X$507,"<>",$AF$8:$AF$507,"<>OK")'),(15,'Maior atraso (dias)','=IFERROR(MAXIFS($O$8:$O$207,$Q$8:$Q$207,"OK",$P$8:$P$207,"Vencido"),0)'),(17,'Atraso 1–30 dias','=SUMIFS($N$8:$N$207,$Q$8:$Q$207,"OK",$O$8:$O$207,">=1",$O$8:$O$207,"<=30")'),(18,'Atraso 31–60 dias','=SUMIFS($N$8:$N$207,$Q$8:$Q$207,"OK",$O$8:$O$207,">=31",$O$8:$O$207,"<=60")'),(19,'Atraso 61–90 dias','=SUMIFS($N$8:$N$207,$Q$8:$Q$207,"OK",$O$8:$O$207,">=61",$O$8:$O$207,"<=90")'),(20,'Atraso acima de 90 dias','=SUMIFS($N$8:$N$207,$Q$8:$Q$207,"OK",$O$8:$O$207,">90")')]
for row,label,f in rows:
 s.merge_cells(start_row=row,start_column=34,end_row=row,end_column=37);c=s.cell(row,34,label);c.fill=PatternFill('solid',fgColor='EFEFEF');c.font=Font(name='Segoe UI',size=10,bold=True,color='262626');c.alignment=Alignment(vertical='center',indent=1)
 s.merge_cells(start_row=row,start_column=38,end_row=row,end_column=39);c=s.cell(row,38,f);c.fill=PatternFill('solid',fgColor='E2F0D9');c.font=Font(name='Segoe UI',size=10,bold=True,color='225C21');c.alignment=Alignment(vertical='center',horizontal='right');
 if row not in (13,14,15):c.number_format='"R$" #,##0.00'
 s.row_dimensions[row].height=24
for start,end,title,text in [(23,26,'REGRA DE USO','Lance uma linha por parcela em B:R e um ID único por recebimento em X:AF. Consulte os alertas antes de interpretar os saldos. O painel exclui títulos com erro.'),(28,32,'ATENÇÃO','Não há integração com PDV, limite de crédito, caixa ou comprovantes. PIX é apenas registro. Encargos não são calculados automaticamente; nenhum fechamento automático é feito.')]:
 s.merge_cells(start_row=start,start_column=34,end_row=start,end_column=39);c=s.cell(start,34,title);c.fill=PatternFill('solid',fgColor='68C2C7');c.font=Font(name='Segoe UI',size=10,bold=True,color='173A3B');c.alignment=Alignment(indent=1,vertical='center')
 s.merge_cells(start_row=start+1,start_column=34,end_row=end,end_column=39);c=s.cell(start+1,34,text);c.fill=PatternFill('solid',fgColor='FFF2CC');c.font=Font(name='Segoe UI',size=10,color='262626');c.alignment=Alignment(wrap_text=True,indent=1,vertical='center')
s.print_area='B1:R30';s.page_setup.orientation='landscape';s.page_setup.fitToWidth=1;s.page_setup.fitToHeight=0
w.calculation.fullCalcOnLoad=True;w.calculation.forceFullCalc=True;w.save('PDV_Empresa_crediario_v1.xlsx')
