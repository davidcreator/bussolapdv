from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment, Protection
from openpyxl.worksheet.table import Table,TableStyleInfo
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.comments import Comment
from datetime import date,time
from openpyxl.utils import get_column_letter
w=load_workbook('PDV_Empresa_visual_padronizado.xlsx');s=w['01_PARAMETROS'];lists=w['15_LISTAS']
s['B5']='Preencha os campos em branco; os valores iniciais são exemplos e não alteram o PDV automaticamente.'
for c in range(2,10):s.column_dimensions[get_column_letter(c)].width=[24,24,22,23,20,22,19,18][c-2]
def header(row,values):
 s.row_dimensions[row].height=27
 for col,value in enumerate(values,2):
  c=s.cell(row,col,value);c.fill=PatternFill('solid',fgColor='383838');c.font=Font(name='Segoe UI',size=10,bold=True,color='FFFFFF');c.alignment=Alignment(vertical='center',wrap_text=True)
def inp(c):
 c.fill=PatternFill('solid',fgColor='FFFFFF');c.font=Font(name='Segoe UI',size=10,color='262626');c.border=Border(bottom=Side(style='thin',color='D39700'));c.protection=Protection(locked=False);c.alignment=Alignment(vertical='center')
def label(c):
 c.fill=PatternFill('solid',fgColor='68C2C7');c.font=Font(name='Segoe UI',size=10,bold=True,color='173A3B');c.alignment=Alignment(vertical='center',wrap_text=True)
def name(n,ref):w.defined_names.add(DefinedName(n,attr_text=ref))
def table(name_,start,end):
 t=Table(displayName=name_,ref=f'B{start}:H{end}');t.tableStyleInfo=TableStyleInfo(name='TableStyleMedium2',showRowStripes=True,showColumnStripes=False,showFirstColumn=False,showLastColumn=False);s.add_table(t)
def dvlist(rng,formula,msg):
 d=DataValidation(type='list',formula1=formula,allow_blank=False);d.showErrorMessage=True;d.errorTitle='Valor inválido';d.error=msg;d.errorStyle='stop';s.add_data_validation(d);d.add(rng)
def numeric(rng,kind,op,a,b=None):
 d=DataValidation(type=kind,operator=op,formula1=str(a),formula2=str(b) if b is not None else None,allow_blank=False);d.showErrorMessage=True;d.errorTitle='Valor inválido';d.error='Informe um valor dentro do intervalo permitido.';d.errorStyle='stop';s.add_data_validation(d);d.add(rng)
header(7,['Nome fantasia','CNPJ','Endereço','Telefone','Logo (arquivo)','Regime tributário','Observações'])
for col in range(2,9):inp(s.cell(8,col));s.cell(8,col).number_format='@'
s['B8']='SUA EMPRESA';s['G8']='A definir';s['C8'].comment=Comment('Armazene como texto. A validação de dígitos verificadores do CNPJ não está implementada.','Equipe PDV')
for nm,cell in [('nomeEmpresa','B8'),('cnpjEmpresa','C8'),('enderecoEmpresa','D8'),('telefoneEmpresa','E8'),('logoArquivo','F8'),('regimeTributario','G8')]:name(nm,f"'01_PARAMETROS'!${cell[0]}${cell[1:]}")
# identity
for sh in w:
 sh['AB1']='=IF(nomeEmpresa="","SUA EMPRESA",nomeEmpresa)&"  |  PROTÓTIPO v1.0"'
sh=w['00_INSTRUCOES'];sh['AB1']='=IF(nomeEmpresa="","SUA EMPRESA",nomeEmpresa)&"  |  PROTÓTIPO v1.0"'
ops=[(12,'Data de início',date(2026,11,10),'Moeda','BRL'),(13,'Casas decimais',2,'Desc. operador',0.05),(14,'Desc. gerente',0.15,'Taxa débito',0.02),(15,'Taxa crédito',0.035,'Prazo crediário (dias)',30),(16,'Bloqueio por atraso (dias)',30,'Juros ao mês',0.01),(17,'Multa por atraso',0.02,'Taxa repassada?','N'),(18,'Chave PIX','','Modo de operação','Teste')]
for row,l,v,l2,v2 in ops:
 s.row_dimensions[row].height=24;s.cell(row,2,l);label(s.cell(row,2));s.cell(row,3,v);inp(s.cell(row,3));s.cell(row,4,l2);label(s.cell(row,4));s.cell(row,5,v2);inp(s.cell(row,5))
for c in ['E13','C14','E14','C15','E16','C17']:s[c].number_format='0.0%'
s['C12'].number_format='dd/mm/yyyy';s['C18'].comment=Comment('A chave é apenas cadastral. Este protótipo não gera cobrança PIX nem verifica recebimento.','Equipe PDV')
for nm,ref in [('dataAberturaSistema','C12'),('moedaSistema','E12'),('casasDecimais','C13'),('descontoOperador','E13'),('descontoGerente','C14'),('taxaDebito','E14'),('taxaCredito','C15'),('prazoCrediario','E15'),('diasBloqueioAtraso','C16'),('jurosMensal','E16'),('multaAtraso','C17'),('taxaRepassada','E17'),('chavePix','C18'),('modoOperacao','E18')]:name(nm,f"'01_PARAMETROS'!${ref[0]}${ref[1:]}")
header(20,['Código','Descrição','Tipo','Taxa %','Prazo (dias)','Gera contas a receber?','Ativo'])
forms=[('01','Dinheiro','Dinheiro',0,0,'N','S'),('02','Cartão Débito','Débito',0.02,1,'N','S'),('03','Cartão Crédito à vista','Crédito',0.035,30,'N','S'),('04','Cartão Crédito Parcelado','Crédito',0.035,30,'N','S'),('05','PIX','PIX',0,0,'N','S'),('06','Transferência/TED','Transferência',0,0,'N','S'),('07','Vale Alimentação/Refeição','Vale',0,0,'N','S'),('08','Cheque','Cheque',0,0,'N','S'),('09','Crediário (pagar depois)','A Prazo',0,30,'S','S'),('10','Convênio/Faturado','A Prazo',0,30,'S','S'),('11','Boleto futuro','A Prazo',0,30,'S','S')]
for r,values in enumerate(forms,21):
 s.row_dimensions[r].height=22
 for col,v in enumerate(values,2):s.cell(r,col,v);inp(s.cell(r,col))
 s.cell(r,2).number_format='@';s.cell(r,5).number_format='0.0%'
table('tblFormasPagamento',20,31)
header(32,['Matrícula','Nome','Perfil','PIN (não usar)','Ativo','Observações','Reserva'])
for r in range(33,39):
 for col in range(2,9):inp(s.cell(r,col))
 s.row_dimensions[r].height=21
s['E32'].comment=Comment('Não insira PIN real. Esta planilha não possui autenticação segura; proteção de célula não protege segredos.','Equipe PDV')
table('tblOperadores',32,38)
header(40,['Turno','Início','Fim','Tolerância (min)','Ativo','Observações','Reserva'])
for r,(turno,start,end) in enumerate([('Manhã',time(6),time(12)),('Tarde',time(12),time(18)),('Noite',time(18),time(23,59))],41):
 for col,val in enumerate([turno,start,end,0,'S','',''],2):s.cell(r,col,val);inp(s.cell(r,col))
 s.cell(r,3).number_format='hh:mm';s.cell(r,4).number_format='hh:mm'
s['B45']='ATENÇÃO';label(s['B45']);s.merge_cells('C45:I46');s['C45']='Taxas, limites, operadores e turnos são parâmetros cadastrados; a macro do protótipo ainda não os consulta nem impõe bloqueios.';s['C45'].font=Font(name='Segoe UI',size=10,bold=True,color='9C2525');s['C45'].alignment=Alignment(wrap_text=True,vertical='center');s.row_dimensions[45].height=28;s.row_dimensions[46].height=20
# lists with names
for col,(nm,vals) in enumerate([('listaSimNao',['S','N']),('listaPerfis',['Operador','Gerente']),('listaTiposPagamento',['Dinheiro','Débito','Crédito','PIX','Transferência','Vale','Cheque','A Prazo']),('listaRegimes',['A definir','Simples Nacional','Lucro Presumido','Lucro Real','MEI']),('listaModo',['Teste','Produção']),('listaMoedas',['BRL'])],2):
 lists.cell(7,col,nm)
 for row,val in enumerate(vals,8):lists.cell(row,col,val)
 letter=get_column_letter(col);name(nm,f"'15_LISTAS'!${letter}$8:${letter}${7+len(vals)}")
dvlist('G8','=listaRegimes','Selecione um regime tributário da lista.')
dvlist('E12','=listaMoedas','Selecione a moeda disponível.')
dvlist('E17','=listaSimNao','Selecione S ou N.')
dvlist('E18','=listaModo','Selecione Teste ou Produção. O modo é apenas informativo.')
dvlist('D21:D31','=listaTiposPagamento','Selecione um tipo de pagamento.')
dvlist('G21:H31','=listaSimNao','Selecione S ou N.')
dvlist('D33:D38','=listaPerfis','Selecione Operador ou Gerente.')
dvlist('F33:F38','=listaSimNao','Selecione S ou N.')
dvlist('F41:F43','=listaSimNao','Selecione S ou N.')
numeric('C13','whole','between',0,4);numeric('E15','whole','between',0,3650);numeric('C16','whole','between',0,3650);numeric('F21:F31','whole','between',0,3650);numeric('E41:E43','whole','between',0,1440)
for rng in ['E13','C14','E14','C15','E16','C17','E21:E31']:numeric(rng,'decimal','between',0,1)
s.print_area='B1:I46';s.page_setup.orientation='landscape';s.page_setup.fitToWidth=1;s.page_setup.fitToHeight=0
w.calculation.fullCalcOnLoad=True;w.calculation.forceFullCalc=True
w.save('PDV_Empresa_parametros_v1.xlsx')
