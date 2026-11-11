from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.page import PageMargins
w=load_workbook('PDV_Empresa_prototipo_pdv.xlsx');s=w['00_INSTRUCOES']
for m in list(s.merged_cells.ranges):s.unmerge_cells(str(m))
for row in s:
 for c in row:
  c.value=None;c.hyperlink=None;c.border=Border();c.fill=PatternFill(fill_type=None)
s.sheet_view.showGridLines=False;s.freeze_panes='C7';s.column_dimensions['A'].width=3
s.column_dimensions['B'].width=17
for c in 'CDEFGHI':s.column_dimensions[c].width=12
for c in range(10,33):s.column_dimensions[get_column_letter(c)].width=12
for col in range(2,33):
 s.cell(1,col).fill=PatternFill('solid',fgColor='383838');s.cell(2,col).fill=PatternFill('solid',fgColor='68C2C7');s.cell(3,col).border=Border(bottom=Side(style='thin',color='D9D9D9'))
s.row_dimensions[1].height=32;s.row_dimensions[2].height=20;s.row_dimensions[3].height=8;s.row_dimensions[4].height=30;s.row_dimensions[5].height=20;s.row_dimensions[6].height=8
s.merge_cells('B1:F1');s['B1']='PDV  |  SUA MARCA';s['B1'].font=Font(name='Segoe UI',size=14,bold=True,color='FFFFFF');s['B1'].alignment=Alignment(vertical='center',indent=1)
s.merge_cells('G1:I1');s['G1']='GUIA DE USO';s['G1'].font=Font(name='Segoe UI',size=10,color='FFFFFF',bold=True);s['G1'].alignment=Alignment(vertical='center',horizontal='right')
nav=[('PDV','03_PDV'),('Produtos','02_PRODUTOS'),('Caixa','06_CAIXA'),('Crediário','09_CREDIARIO'),('Fechamento','08_FECHAMENTO'),('Dashboard','13_DASHBOARD')]
for i,(label,target) in enumerate(nav):
 a=10+3*i;s.merge_cells(start_row=1,start_column=a,end_row=1,end_column=a+2);c=s.cell(1,a,label);c.hyperlink=f"#'{target}'!B4";c.font=Font(name='Segoe UI',size=10,color='FFFFFF',bold=True);c.alignment=Alignment(horizontal='center',vertical='center')
s.merge_cells('AB1:AF1');s['AB1']='PROTÓTIPO  •  v1.0';s['AB1'].font=Font(name='Segoe UI',size=9,bold=True,color='FFFFFF');s['AB1'].alignment=Alignment(horizontal='right',vertical='center')
s.merge_cells('B2:I2');s['B2']='MANUAL  /  PRIMEIROS PASSOS  /  SUPORTE';s['B2'].font=Font(name='Segoe UI',size=9,bold=True,color='173A3B');s['B2'].alignment=Alignment(indent=1,vertical='center')
s['B4']='Planilha:';s['B4'].fill=PatternFill('solid',fgColor='68C2C7');s['B4'].font=Font(name='Segoe UI',size=10,bold=True,color='173A3B');s['B4'].alignment=Alignment(horizontal='right',vertical='center')
s.merge_cells('C4:I4');s['C4']='Instruções de uso do PDV';s['C4'].font=Font(name='Segoe UI',size=19,bold=True,color='171717');s['C4'].alignment=Alignment(vertical='center',indent=1)
s['B5']='Importante:';s['B5'].fill=PatternFill('solid',fgColor='68C2C7');s['B5'].font=Font(name='Segoe UI',size=10,bold=True,color='173A3B');s['B5'].alignment=Alignment(horizontal='right',vertical='center')
s.merge_cells('C5:I5');s['C5']='Protótipo para testes fictícios. Não utilizar em vendas reais.';s['C5'].font=Font(name='Segoe UI',size=10,italic=True,color='8C2525');s['C5'].alignment=Alignment(vertical='center',indent=1)
sections=[
('Passo 1','Conheça o estado do projeto','Esta pasta é um protótipo. Estão disponíveis o carrinho, três produtos fictícios e um módulo VBA separado para testar o registro de vendas. Caixa, crediário, cartão, cancelamento, auditoria e fechamento ainda não estão operacionais.',48),
('Passo 2','Prepare uma cópia de teste','Abra o arquivo no Excel para Windows e salve uma cópia em uma pasta segura. Não use dados pessoais ou financeiros reais. Ative edição e macros apenas se confiar na origem e nas políticas de segurança da empresa.',42),
('Passo 3','Instale a macro na cópia','No Excel, acesse Arquivo → Salvar como e escolha Pasta de Trabalho Habilitada para Macro (*.xlsm). Pressione Alt+F11; no projeto da cópia, escolha Arquivo → Importar arquivo e selecione ModuloPDV.bas. Salve novamente.',48),
('Passo 4','Confira os produtos de demonstração','Abra 02_PRODUTOS. Os códigos P001, P002 e P003 são fictícios. Código, descrição, unidade, custo, preço, saldo inicial e ativo alimentam o teste do PDV. O estoque atual considera movimentos gravados.',42),
('Passo 5','Preencha uma venda','Em 03_PDV, digite o operador em C8 e o cliente em G8. Nas linhas 12 a 26, informe o código na coluna B e a quantidade na E; informe desconto em G, se necessário. Confira descrição, preço, total e estoque calculados.',48),
('Passo 6','Escolha o pagamento e finalize','Na linha 31, selecione até três formas entre Dinheiro e PIX e digite os respectivos valores. O protótipo valida o valor pago e limita o troco ao dinheiro entregue. Pressione Alt+F8, selecione FinalizarVenda e clique em Executar.',48),
('Passo 7','Confira, salve e faça backup','Após o aviso de venda registrada, salve a cópia. Para conferir os registros, clique com o botão direito em uma guia → Reexibir e abra as abas de vendas, itens, pagamentos e movimentos. Salve uma cópia diária separada.',48),
('Teste','Exemplo de venda e conferência','Em uma cópia nova: P001 × 1 e P002 × 2, sem desconto. Total esperado: R$ 27,00. Pagamento em dinheiro: R$ 30,00; troco: R$ 3,00. Após executar a macro, estoques esperados: P001 = 19 e P002 = 13.',48),
('Atenção','Se houver erro durante a gravação','A macro ainda não tem gravação atômica. Se informar erro após o início da gravação, não repita a venda: feche a cópia sem salvar e restaure o backup anterior. A macro não foi homologada neste ambiente.',42),
('Limites','O que ainda não funciona','Não há abertura de caixa, autorização de desconto, venda a prazo, cartão, cancelamento ou estorno, registro de auditoria, emissão fiscal, operação simultânea segura nem fechamento diário funcional. Não use em produção.',48),
('Navegação','Atalhos disponíveis','Alt+F8: escolher e executar macro. Alt+F11: editor VBA. Ctrl+S: salvar. Tab e Enter: navegação padrão do Excel. F2, F4, F5, F6, F7 e F8 não foram configurados como ações do PDV.',42),
('Cores','Como interpretar os campos','Branco com borda âmbar: campo de entrada no protótipo. Cinza: célula calculada. Azul-marinho: títulos e comandos. Verde: destaque de total. Consulte sempre o rótulo; cor isolada não confirma validação.',42),
('Suporte','Perguntas frequentes','Não encontrou a macro? Confirme se importou ModuloPDV.bas na cópia .xlsm e se macros estão habilitadas. Fórmulas não calcularam? Abra no Excel e confirme o cálculo automático. A planilha ainda não tem canal de suporte configurado.',48),
('Logo','Como substituir a marca','Selecione Inserir → Imagens, escolha sua marca e posicione-a na faixa superior, preservando a proporção. Antes de inserir, apague o texto provisório em B1. Ajuste a imagem sem encobrir o menu.',42),
('Versão','Registro de alterações','v1.0 — protótipo de PDV e documentação. Revisão visual: aba de instruções refeita com faixa grafite, faixa turquesa e blocos de orientação. Os demais módulos mantêm o estado anterior.',42)]
r=7
for label,title,text,h in sections:
 s.cell(r,2,label);s.cell(r,2).fill=PatternFill('solid',fgColor='68C2C7');s.cell(r,2).font=Font(name='Segoe UI',size=10,bold=True,color='173A3B');s.cell(r,2).alignment=Alignment(horizontal='right',vertical='center',indent=1)
 s.merge_cells(start_row=r,start_column=3,end_row=r,end_column=9);c=s.cell(r,3,title);c.fill=PatternFill('solid',fgColor='EFEFEF');c.font=Font(name='Segoe UI',size=11,bold=True,color='222222');c.alignment=Alignment(vertical='center',indent=1);s.row_dimensions[r].height=23
 s.merge_cells(start_row=r+1,start_column=3,end_row=r+1,end_column=9);c=s.cell(r+1,3,text);c.font=Font(name='Segoe UI',size=10,color='262626');c.alignment=Alignment(wrap_text=True,vertical='center',indent=1);s.row_dimensions[r+1].height=h
 s.row_dimensions[r+2].height=6;r+=3
s.print_area=f'B1:I{r-2}';s.page_setup.orientation='portrait';s.page_setup.paperSize=s.PAPERSIZE_A4;s.page_setup.fitToWidth=1;s.page_setup.fitToHeight=0;s.sheet_properties.pageSetUpPr.fitToPage=True;s.page_margins=PageMargins(left=.3,right=.3,top=.4,bottom=.4,header=.15,footer=.15)
w.active=0;w.save('PDV_Empresa_instrucoes_v1.xlsx')
