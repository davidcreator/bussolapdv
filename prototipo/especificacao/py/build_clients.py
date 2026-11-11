from openpyxl import load_workbook
from openpyxl.styles import Font,PatternFill,Border,Side,Alignment,Protection
from openpyxl.worksheet.table import Table,TableStyleInfo
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import FormulaRule
from openpyxl.utils import get_column_letter
from openpyxl.comments import Comment
w=load_workbook('PDV_Empresa_crediario_v1.xlsx');s=w['10_CLIENTES'];s['B4']='CADASTRO DE CLIENTES';s['B5']='TESTE • use dados fictícios; revise alertas antes de consultar o crédito.';s.freeze_panes='C8';s.sheet_view.zoomScale=80
headers=['Código','Nome','CPF/CNPJ','Telefone com DDD','E-mail','Endereço','Limite de Crédito','Saldo Devedor','Limite Disponível','Maior Atraso (dias)','Classificação','Ativo','Verificação Cadastro','Nome Normalizado','Verificação Documento','Observações']
widths=[16,30,20,22,30,30,20,19,21,21,23,12,26,30,24,28]
for col,(h,wd) in enumerate(zip(headers,widths),2):
 c=s.cell(7,col,h);c.fill=PatternFill('solid',fgColor='383838');c.font=Font(name='Segoe UI',size=10,bold=True,color='FFFFFF');c.alignment=Alignment(wrap_text=True,vertical='center');s.column_dimensions[get_column_letter(col)].width=wd
s.row_dimensions[7].height=32
for r in range(8,208):
 for col in range(2,18):
  c=s.cell(r,col);c.fill=PatternFill('solid',fgColor='FFF9E6' if col in (2,3,4,5,6,7,8,13,17) else 'EEF2F3');c.font=Font(name='Segoe UI',size=10,color='262626');c.alignment=Alignment(vertical='center');c.protection=Protection(locked=col not in (2,3,4,5,6,7,8,13,17))
  if col in (2,3,4,5,6,7,8,13,17):c.border=Border(bottom=Side(style='thin',color='D39700'))
 for col in (2,4,5):s.cell(r,col).number_format='@'
 for col in (8,9,10):s.cell(r,col).number_format='"R$" #,##0.00;[Red]-"R$" #,##0.00'
 # Document checksum uses numeric strings; I/O value 'VÁLIDO' / 'INVÁLIDO' / 'NÃO INFORMADO'.
 d=f'D{r}';s1=f'MOD(SUMPRODUCT(--MID({d},ROW($1:$9),1),11-ROW($1:$9)),11)';s2=f'MOD(SUMPRODUCT(--MID({d},ROW($1:$10),1),12-ROW($1:$10)),11)';c1=f'MOD(SUMPRODUCT(--MID({d},ROW($1:$12),1),MOD(12-ROW($1:$12),8)+2),11)';c2=f'MOD(SUMPRODUCT(--MID({d},ROW($1:$13),1),MOD(13-ROW($1:$13),8)+2),11)'
 cpf=f'AND(--MID({d},10,1)=IF({s1}<2,0,11-{s1}),--MID({d},11,1)=IF({s2}<2,0,11-{s2}))'
 cnpj=f'AND(--MID({d},13,1)=IF({c1}<2,0,11-{c1}),--MID({d},14,1)=IF({c2}<2,0,11-{c2}))'
 doc=f'=IF({d}="","NÃO INFORMADO",IFERROR(IF(AND(ISTEXT({d}),OR(LEN({d})=11,LEN({d})=14),ISNUMBER(--{d}),{d}<>REPT(LEFT({d},1),LEN({d}))),IF(IF(LEN({d})=11,{cpf},{cnpj}),"VÁLIDO","INVÁLIDO"),"INVÁLIDO"),"INVÁLIDO"))'
 fs={9:f'=IF(B{r}="","",SUMIFS(\'09_CREDIARIO\'!$N$8:$N$207,\'09_CREDIARIO\'!$D$8:$D$207,B{r},\'09_CREDIARIO\'!$Q$8:$Q$207,"OK"))',10:f'=IF(B{r}="","",IF(ISNUMBER(H{r}),H{r}-I{r},""))',11:f'=IF(B{r}="","",IFERROR(MAXIFS(\'09_CREDIARIO\'!$O$8:$O$207,\'09_CREDIARIO\'!$D$8:$D$207,B{r},\'09_CREDIARIO\'!$Q$8:$Q$207,"OK"),0))',12:f'=IF(B{r}="","",IF(N{r}<>"OK","REVISAR CADASTRO",IF(COUNTIFS(\'09_CREDIARIO\'!$D$8:$D$207,B{r},\'09_CREDIARIO\'!$B$8:$B$207,"<>\",\'09_CREDIARIO\'!$Q$8:$Q$207,"<>OK")>0,"REVISAR CRÉDITO",IF(M{r}="N","INATIVO",IF(K{r}>0,"VENCIDO",IF(J{r}<=0,"LIMITE ESGOTADO","DISPONÍVEL"))))))',14:f'=IF(AND(B{r}="",C{r}="",D{r}=""),"",IF(OR(B{r}="",C{r}="",M{r}="",NOT(ISNUMBER(H{r}))),"DADOS INCOMPLETOS",IF(SUMPRODUCT(--($B$8:$B$207=B{r}))>1,"CÓDIGO DUPLICADO",IF(OR(O{r}="",SUMPRODUCT(--($O$8:$O$207=O{r}))>1),"NOME DUPLICADO",IF(P{r}<>"VÁLIDO","REVISAR DOCUMENTO",IF(SUMPRODUCT(--($D$8:$D$207=D{r}))>1,"DOCUMENTO DUPLICADO",IF(OR(H{r}<0,AND(M{r}<>"S",M{r}<>"N"),LEN(O{r})<3,AND(E{r}<>"",IFERROR(NOT(AND(ISTEXT(E{r}),OR(LEN(E{r})=10,LEN(E{r})=11),ISNUMBER(--E{r}))),TRUE)),AND(F{r}<>"",IFERROR(NOT(AND(ISTEXT(F{r}),LEN(F{r})-LEN(SUBSTITUTE(F{r},"@",""))=1,FIND("@",F{r})>1,FIND(".",F{r},FIND("@",F{r})+2)<LEN(F{r}),ISERROR(FIND(" ",F{r})))),TRUE))),"DADOS INVÁLIDOS","OK")))))))',15:f'=IF(C{r}="","",UPPER(TRIM(SUBSTITUTE(C{r},CHAR(160)," "))))',16:doc}
 for col,f in fs.items():s.cell(r,col,f)
t=Table(displayName='tblClientes',ref='B7:Q207');t.tableStyleInfo=TableStyleInfo(name='TableStyleMedium2',showRowStripes=True,showColumnStripes=False,showFirstColumn=False,showLastColumn=False);s.add_table(t)
def dv(t,rg,f1,op=None,f2=None,msg='Informe um valor válido.',blank=True):
 d=DataValidation(type=t,formula1=f1,formula2=f2,operator=op,allow_blank=blank);d.showErrorMessage=True;d.errorStyle='stop';d.errorTitle='Valor inválido';d.error=msg;s.add_data_validation(d);d.add(rg)
dv('custom','B8:B207','=AND(ISTEXT(B8),LEN(TRIM(B8))>0,SUMPRODUCT(--($B$8:$B$207=B8),--(ROW($B$8:$B$207)<>ROW(B8)))=0)',msg='Informe um código de texto único.')
dv('custom','C8:C207','=AND(ISTEXT(C8),LEN(TRIM(C8))>=3,SUMPRODUCT(--($O$8:$O$207=UPPER(TRIM(SUBSTITUTE(C8,CHAR(160)," ")))),--(ROW($O$8:$O$207)<>ROW(C8)))=0)',msg='Nome deve ter ao menos 3 caracteres e não pode duplicar outro nome.')
dv('custom','D8:D207','=IFERROR(AND(ISTEXT(D8),OR(LEN(D8)=11,LEN(D8)=14),ISNUMBER(--D8),SUMPRODUCT(--($D$8:$D$207=D8),--(ROW($D$8:$D$207)<>ROW(D8)))=0),FALSE)',msg='Digite 11 ou 14 dígitos, como texto e sem pontuação; não pode duplicar.')
dv('custom','E8:E207','=IFERROR(AND(ISTEXT(E8),OR(LEN(E8)=10,LEN(E8)=11),ISNUMBER(--E8)),FALSE)',msg='Telefone: DDD + 8 ou 9 dígitos, sem símbolos; use texto.')
dv('custom','F8:F207','=IFERROR(AND(ISTEXT(F8),LEN(F8)-LEN(SUBSTITUTE(F8,"@",""))=1,FIND("@",F8)>1,FIND(".",F8,FIND("@",F8)+2)<LEN(F8),ISERROR(FIND(" ",F8))),FALSE)',msg='Informe e-mail com @ e domínio; sem espaços.')
dv('decimal','H8:H207','0','greaterThanOrEqual',msg='Informe limite igual ou maior que zero.')
dv('list','M8:M207','=listaSimNao',msg='Selecione S ou N.')
for rg,form,bg,fg in [('N8:N207','AND($N8<>"",$N8<>"OK")','FCE8E6','9C0006'),('P8:P207','$P8="INVÁLIDO"','FCE8E6','9C0006'),('L8:L207','OR($L8="REVISAR CRÉDITO",$L8="REVISAR CADASTRO",$L8="VENCIDO",$L8="LIMITE ESGOTADO")','FFF2CC','805900'),('L8:L207','$L8="DISPONÍVEL"','E2F0D9','225C21')]:s.conditional_formatting.add(rg,FormulaRule(formula=[form],fill=PatternFill('solid',fgColor=bg),font=Font(color=fg,bold=True)))
s['I7'].comment=Comment('Soma apenas títulos de crediário com verificação OK; títulos em revisão são excluídos. Não autoriza crédito automaticamente.','Equipe PDV');s['P7'].comment=Comment('Valida CPF/CNPJ numéricos atuais pelos dígitos verificadores, não verifica existência, titularidade ou situação cadastral.','Equipe PDV')
for col in range(19,26):s.column_dimensions[get_column_letter(col)].width=17
for row,title,text in [(7,'COMO CADASTRAR','Preencha código único, nome, CPF/CNPJ, limite e ativo. Documento e telefone devem ser texto, apenas dígitos. E-mail e endereço são opcionais; confira os avisos antes de usar.'),(13,'NOMES DUPLICADOS','A comparação ignora maiúsculas/minúsculas e espaços extras. Pessoas diferentes podem ter nomes iguais: esta regra bloqueará homônimos e requer decisão de gestão.'),(19,'CRÉDITO','Saldo soma somente títulos verificados. Títulos em revisão geram alerta específico e devem ser investigados. Esta tela não bloqueia vendas nem concede crédito automaticamente.'),(25,'PRIVACIDADE','Use apenas dados fictícios. Ainda não há proteção efetiva, autenticação, trilha de auditoria, retenção ou controle de acesso adequado para dados pessoais.')]:
 s.merge_cells(start_row=row,start_column=19,end_row=row,end_column=25);c=s.cell(row,19,title);c.fill=PatternFill('solid',fgColor='68C2C7');c.font=Font(name='Segoe UI',size=10,bold=True,color='173A3B');c.alignment=Alignment(indent=1,vertical='center')
 s.merge_cells(start_row=row+1,start_column=19,end_row=row+4,end_column=25);c=s.cell(row+1,19,text);c.fill=PatternFill('solid',fgColor='FFF2CC' if row>=19 else 'EFEFEF');c.font=Font(name='Segoe UI',size=10,color='262626');c.alignment=Alignment(wrap_text=True,vertical='center',indent=1)
s.print_area='B1:Q30';s.page_setup.orientation='landscape';s.page_setup.fitToWidth=1;s.page_setup.fitToHeight=0;w.calculation.fullCalcOnLoad=True;w.calculation.forceFullCalc=True;w.save('PDV_Empresa_clientes_v1.xlsx')
