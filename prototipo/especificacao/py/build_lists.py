from openpyxl import load_workbook
from openpyxl.styles import Font,PatternFill,Border,Side,Alignment,Protection
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import FormulaRule
from openpyxl.worksheet.table import Table,TableStyleInfo
from openpyxl.utils import get_column_letter
from openpyxl.comments import Comment
w=load_workbook('PDV_Empresa_auditoria_v1.xlsx');s=w['15_LISTAS'];s.sheet_state='veryHidden';s['B4']='LISTAS DE VALIDAÇÃO';s['B5']='MANUTENÇÃO CONTROLADA • valores exatos usados pelo protótipo • veja o catálogo à direita.';s.freeze_panes='C8';s.sheet_view.zoomScale=80
spec=[('B','listaSimNao','S/N','Indicador usado em parâmetros, produtos e clientes; fórmulas esperam S e N.'),('C','listaPerfis','Perfis','Cadastro de operadores; não autentica nem concede permissões.'),('D','listaTiposPagamento','Tipo pagamento','Domínio dos parâmetros; não habilita novos meios no PDV.'),('E','listaRegimes','Regime','Lista cadastral da empresa, sem cálculo fiscal.'),('F','listaModo','Modo','Texto informativo; não muda controles do aplicativo.'),('G','listaMoedas','Moeda','Código cadastral; o protótipo está formatado em BRL.'),('H','listaDenominacoes','Cédulas / moedas','Valores numéricos usados na contagem do caixa.'),('I','listaTiposAuditoria','Tipo auditoria','Alguns textos acionam exigência de autorizador.'),('J','listaOrigensAuditoria','Origem auditoria','Aba informada no registro manual; não valida o vínculo.'),('K','listaSeveridadeAuditoria','Severidade','Lista de risco escolhida manualmente.'),('L','listaStatusAuditoria','Status auditoria','Lista de acompanhamento; não bloqueia edição.')]
s.row_dimensions[7].height=34
for col,name,short,usage in spec:
 dim=w.defined_names[name].attr_text.split('!')[1];first=int(dim.split('$')[2].split(':')[0]);last=int(dim.split('$')[-1]);s.column_dimensions[col].width=25 if col not in ['I','J'] else 29
 c=s[f'{col}7'];c.value=name;c.fill=PatternFill('solid',fgColor='383838');c.font=Font(name='Segoe UI',size=9,bold=True,color='FFFFFF');c.alignment=Alignment(wrap_text=True,vertical='center',indent=1);c.comment=Comment(f'{short} — {usage}\nIntervalo ativo: {col}{first}:{col}{last}.','Equipe PDV')
 for r in range(8,21):
  c=s[f'{col}{r}'];active=r<=last;c.fill=PatternFill('solid',fgColor='FFF9E6' if active else 'F2F2F2');c.font=Font(name='Segoe UI',size=10,color='262626' if active else '808080');c.alignment=Alignment(vertical='center',indent=1);c.protection=Protection(locked=not active)
  if active:c.border=Border(bottom=Side(style='thin',color='D39700'))
  if col=='H' and active:c.number_format='"R$" #,##0.00'
 # uniqueness and type; validations on live cells only, not expansion slots
 target=f'{col}{first}:{col}{last}';cell=f'{col}{first}';ranges=f'${col}${first}:${col}${last}'
 typecheck=f'AND(ISNUMBER({cell}),{cell}>0)' if col=='H' else f'AND(ISTEXT({cell}),LEN(TRIM({cell}))>0)'
 formula=f'=AND({typecheck},SUMPRODUCT(--({ranges}={cell}),--(ROW({ranges})<>ROW({cell})))=0)'
 d=DataValidation(type='custom',formula1=formula,allow_blank=False);d.showErrorMessage=True;d.errorStyle='stop';d.errorTitle='Valor inválido ou duplicado';d.error='Use valor único e não vazio, de tipo apropriado. Alterações exigem revisão das fórmulas.';s.add_data_validation(d);d.add(target)
 s.conditional_formatting.add(target,FormulaRule(formula=[f'AND({cell}<>"",COUNTIF({ranges},{cell})>1)'],fill=PatternFill('solid',fgColor='FFC7CE'),font=Font(color='9C0006',bold=True)))
# metadata outside the validated range; no columns added to original lists
for col,wd in {'N':27,'O':20,'P':13,'Q':24,'R':52}.items():s.column_dimensions[col].width=wd
meta=['Nome definido','Intervalo ativo','Qtde atual','Verificação','Uso e cuidado']
for j,h in enumerate(meta,14):
 c=s.cell(7,j,h);c.fill=PatternFill('solid',fgColor='383838');c.font=Font(name='Segoe UI',size=10,bold=True,color='FFFFFF');c.alignment=Alignment(vertical='center',wrap_text=True)
for idx,(col,name,short,usage) in enumerate(spec,8):
 ref=w.defined_names[name].attr_text.split('!')[1];last=int(ref.split('$')[-1]);active=f'{col}8:{col}{last}';vals=[s[f'{col}{j}'].value for j in range(8,last+1)]
 s.cell(idx,14,name);s.cell(idx,15,f'{col}8:{col}{last}');s.cell(idx,16,f'=COUNTA({active})')
 conditions=[]
 for r,v in enumerate(vals,8):
  v=str(v).replace('"','""') if isinstance(v,str) else v
  literal=f'"{v}"' if isinstance(v,str) else str(v)
  conditions.append(f'{col}{r}={literal}')
 # exact typed values check; checks ranges captured at generation, not content outside the active range
 f=f'=IF(COUNTBLANK({active})>0,"CÉLULA VAZIA",IF(SUMPRODUCT(--(COUNTIF({active},{active})>1))>0,"DUPLICADA",IF(AND({",".join(conditions)}),"PADRÃO ORIGINAL","ALTERADA • REVISAR")))'
 s.cell(idx,17,f);s.cell(idx,18,usage)
 for j in range(14,19):
  c=s.cell(idx,j);c.font=Font(name='Segoe UI',size=10,color='262626');c.fill=PatternFill('solid',fgColor='F2F4F5' if idx%2==0 else 'FFFFFF');c.alignment=Alignment(wrap_text=True,vertical='center',indent=1)
 s.row_dimensions[idx].height=30
s.conditional_formatting.add('Q8:Q18',FormulaRule(formula=['$Q8="PADRÃO ORIGINAL"'],fill=PatternFill('solid',fgColor='E2F0D9'),font=Font(color='225C21',bold=True)))
s.conditional_formatting.add('Q8:Q18',FormulaRule(formula=['AND($Q8<>"",$Q8<>"PADRÃO ORIGINAL")'],fill=PatternFill('solid',fgColor='FCE8E6'),font=Font(color='9C0006',bold=True)))
for r,title,text in [(23,'ORIENTAÇÃO','As células amarelas compõem listas já vinculadas às validações; cinza está fora dos intervalos nomeados. Não altere rótulos usados em fórmulas ou macros sem revisar todo o projeto.'),(27,'ATUALIZAÇÃO','Para acrescentar itens é necessário ampliar o nome definido no Gerenciador de Nomes e atualizar as validações da própria aba; células adicionais não entram na lista automaticamente.'),(31,'SEGURANÇA','A aba é muito oculta, mas isso não é proteção. Copie o arquivo antes da manutenção. A planilha não impede exclusão, colagem nem mudanças feitas por VBA.')]:
 s.merge_cells(start_row=r,start_column=2,end_row=r,end_column=12);c=s.cell(r,2,title);c.fill=PatternFill('solid',fgColor='68C2C7');c.font=Font(name='Segoe UI',size=10,bold=True,color='173A3B');c.alignment=Alignment(indent=1,vertical='center')
 s.merge_cells(start_row=r+1,start_column=2,end_row=r+2,end_column=12);c=s.cell(r+1,2,text);c.fill=PatternFill('solid',fgColor='FFF2CC');c.font=Font(name='Segoe UI',size=10,color='262626');c.alignment=Alignment(wrap_text=True,vertical='center',indent=1)
s.print_area='B1:R18';s.page_setup.orientation='landscape';s.page_setup.fitToWidth=1;s.page_setup.fitToHeight=0;w.calculation.fullCalcOnLoad=True;w.calculation.forceFullCalc=True;w.save('PDV_Empresa_listas_v1.xlsx')
