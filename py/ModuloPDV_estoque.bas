Attribute VB_Name = "ModuloPDV"
Option Explicit

' PROTÓTIPO PARA TESTES LOCAIS. Não utilizar para vendas reais.
Private Function ProximaLinha(ByVal tabela As ListObject) As Range
    Dim linha As ListRow
    For Each linha In tabela.ListRows
        If Len(Trim$(CStr(linha.Range.Cells(1, 1).Value))) = 0 Then
            Set ProximaLinha = linha.Range
            Exit Function
        End If
    Next linha
    Set linha = tabela.ListRows.Add
    Set ProximaLinha = linha.Range
End Function

Public Sub FinalizarVenda()
    Dim p As Worksheet, produtos As Worksheet, v As Worksheet, it As Worksheet, pg As Worksheet, mov As Worksheet
    Dim linha As Long, j As Long, qtd As Double, total As Double, pago As Double, dinheiro As Double, troco As Double
    Dim valor As Double, aplicado As Double, abater As Double, desconto As Double, preco As Double
    Dim codigo As String, forma As String, operador As String, cliente As String, id As String
    Dim achou As Variant, estoque As Double, acumulado As Double, k As Long, n As Long, seq As Long, nPag As Long
    Dim destino As Range, dataHora As Date, maior As Long, atual As String, houveGravacao As Boolean
    On Error GoTo Falha
    Set p = ThisWorkbook.Worksheets("03_PDV")
    Set produtos = ThisWorkbook.Worksheets("02_PRODUTOS")
    Set v = ThisWorkbook.Worksheets("04_VENDAS")
    Set it = ThisWorkbook.Worksheets("05_ITENS_VENDA")
    Set pg = ThisWorkbook.Worksheets("07_PAGAMENTOS")
    Set mov = ThisWorkbook.Worksheets("11_ESTOQUE_MOV")
    Application.CalculateFull
    operador = Trim$(CStr(p.Range("C8").Value))
    cliente = Trim$(CStr(p.Range("G8").Value))
    If operador = "" Then Err.Raise vbObjectError + 1, , "Informe o operador."
    If cliente = "" Then Err.Raise vbObjectError + 2, , "Informe o cliente."
    For linha = 12 To 26
        codigo = Trim$(CStr(p.Cells(linha, 2).Value))
        If codigo <> "" Then
            achou = Application.Match(codigo, produtos.ListObjects("tblProdutos").ListColumns("Código").DataBodyRange, 0)
            If IsError(achou) Then Err.Raise vbObjectError + 3, , "Produto não encontrado: " & codigo
            If UCase$(Trim$(CStr(produtos.ListObjects("tblProdutos").DataBodyRange.Cells(CLng(achou), 10).Value))) <> "S" Then Err.Raise vbObjectError + 4, , "Produto inativo: " & codigo
            If CStr(produtos.ListObjects("tblProdutos").DataBodyRange.Cells(CLng(achou), 17).Value) <> "OK" Then Err.Raise vbObjectError + 23, , "Revise movimentos inválidos do produto: " & codigo
            If Not IsNumeric(p.Cells(linha, 5).Value) Then Err.Raise vbObjectError + 5, , "Quantidade inválida na linha " & linha
            qtd = CDbl(p.Cells(linha, 5).Value)
            If qtd <= 0 Then Err.Raise vbObjectError + 6, , "Quantidade deve ser positiva na linha " & linha
            If Not IsNumeric(p.Cells(linha, 7).Value) And p.Cells(linha, 7).Value <> "" Then Err.Raise vbObjectError + 7, , "Desconto inválido."
            desconto = 0
            If IsNumeric(p.Cells(linha, 7).Value) Then desconto = CDbl(p.Cells(linha, 7).Value)
            If desconto < 0 Or desconto > 1 Then Err.Raise vbObjectError + 8, , "Desconto fora do intervalo de 0% a 100%."
            If Not IsNumeric(p.Cells(linha, 6).Value) Or p.Cells(linha, 6).Value <= 0 Then Err.Raise vbObjectError + 9, , "Preço inválido: " & codigo
            estoque = CDbl(produtos.ListObjects("tblProdutos").DataBodyRange.Cells(CLng(achou), 11).Value)
            acumulado = 0
            For k = 12 To 26
                If Trim$(CStr(p.Cells(k, 2).Value)) = codigo And IsNumeric(p.Cells(k, 5).Value) Then acumulado = acumulado + CDbl(p.Cells(k, 5).Value)
            Next k
            If acumulado > estoque Then Err.Raise vbObjectError + 10, , "Estoque insuficiente para " & codigo & ": restam " & estoque
            n = n + 1
        ElseIf p.Cells(linha, 5).Value <> "" Or p.Cells(linha, 7).Value <> "" Then
            Err.Raise vbObjectError + 11, , "Há quantidade ou desconto sem código na linha " & linha
        End If
    Next linha
    If n = 0 Then Err.Raise vbObjectError + 12, , "Carrinho vazio."
    total = Round(CDbl(p.Range("C28").Value), 2)
    If total <= 0 Then Err.Raise vbObjectError + 13, , "Total deve ser positivo."
    For j = 3 To 7 Step 2
        forma = Trim$(CStr(p.Cells(31, j).Value))
        If Not IsNumeric(p.Cells(31, j + 1).Value) And p.Cells(31, j + 1).Value <> "" Then Err.Raise vbObjectError + 14, , "Pagamento inválido."
        valor = 0
        If IsNumeric(p.Cells(31, j + 1).Value) Then valor = CDbl(p.Cells(31, j + 1).Value)
        If valor < 0 Then Err.Raise vbObjectError + 15, , "Pagamento negativo."
        If (forma = "" And valor <> 0) Or (forma <> "" And valor <= 0) Then Err.Raise vbObjectError + 16, , "Informe forma e valor positivo juntos."
        If forma <> "" And forma <> "Dinheiro" And forma <> "PIX" Then Err.Raise vbObjectError + 17, , "Somente Dinheiro e PIX estão disponíveis no protótipo."
        If forma <> "" Then nPag = nPag + 1
        pago = pago + valor
        If forma = "Dinheiro" Then dinheiro = dinheiro + valor
    Next j
    pago = Round(pago, 2): troco = Round(pago - total, 2)
    If troco < 0 Then Err.Raise vbObjectError + 18, , "Pagamento insuficiente."
    If troco > dinheiro Then Err.Raise vbObjectError + 19, , "O troco não pode superar o valor em dinheiro."
    For Each destino In v.ListObjects("tblVendas").ListColumns(1).DataBodyRange
        atual = CStr(destino.Value)
        If Left$(atual, 1) = "V" And IsNumeric(Mid$(atual, 2)) Then
            If CLng(Mid$(atual, 2)) > maior Then maior = CLng(Mid$(atual, 2))
        End If
    Next destino
    If Application.WorksheetFunction.CountBlank(v.ListObjects("tblVendas").ListColumns(1).DataBodyRange) = 0 Then Err.Raise vbObjectError + 20, , "Limite de 500 vendas do protótipo atingido. Não registre novas vendas antes de atualizar o modelo."
    If Application.WorksheetFunction.CountBlank(it.ListObjects("tblItensVenda").ListColumns(1).DataBodyRange) < n Then Err.Raise vbObjectError + 21, , "Capacidade de itens insuficiente: limite do protótipo é 1.000 linhas."
    If Application.WorksheetFunction.CountBlank(pg.ListObjects("tblPagamentos").ListColumns(1).DataBodyRange) < nPag Then Err.Raise vbObjectError + 22, , "Capacidade de pagamentos insuficiente: limite do protótipo é 1.000 linhas."
    For k = 8 To 2007
        If Len(Trim$(CStr(mov.Cells(k, 2).Value))) = 0 Then
            If Application.WorksheetFunction.CountA(mov.Range(mov.Cells(k, 3), mov.Cells(k, 9))) + Application.WorksheetFunction.CountA(mov.Cells(k, 12)) > 0 Then Err.Raise vbObjectError + 24, , "Há movimento incompleto sem ID na linha " & k & ". Corrija antes de vender."
        End If
    Next k
    If Application.WorksheetFunction.CountBlank(mov.ListObjects("tblEstoqueMov").ListColumns(1).DataBodyRange) < n Then Err.Raise vbObjectError + 25, , "Capacidade insuficiente no histórico de estoque (2.000 linhas)."
    id = "V" & Format$(maior + 1, "000000")
    dataHora = Now
    houveGravacao = True
    Set destino = ProximaLinha(v.ListObjects("tblVendas"))
    destino.Cells(1, 1).Value = id: destino.Cells(1, 2).Value = DateValue(dataHora): destino.Cells(1, 2).NumberFormat = "dd/mm/yyyy"
    destino.Cells(1, 3).Value = TimeValue(dataHora): destino.Cells(1, 3).NumberFormat = "hh:mm:ss"
    destino.Cells(1, 4).Value = operador: destino.Cells(1, 5).Value = cliente
    destino.Cells(1, 6).Value = total: destino.Cells(1, 7).Value = total: destino.Cells(1, 8).Value = "Concluída": destino.Cells(1, 9).Value = troco
    For linha = 12 To 26
        codigo = Trim$(CStr(p.Cells(linha, 2).Value))
        If codigo <> "" Then
            seq = seq + 1: achou = Application.Match(codigo, produtos.ListObjects("tblProdutos").ListColumns("Código").DataBodyRange, 0)
            Set destino = ProximaLinha(it.ListObjects("tblItensVenda"))
            destino.Cells(1, 1).Value = id: destino.Cells(1, 2).Value = seq: destino.Cells(1, 3).Value = codigo
            destino.Cells(1, 4).Value = p.Cells(linha, 3).Value: destino.Cells(1, 5).Value = p.Cells(linha, 4).Value
            destino.Cells(1, 6).Value = p.Cells(linha, 5).Value: destino.Cells(1, 7).Value = p.Cells(linha, 6).Value
            destino.Cells(1, 8).Value = p.Cells(linha, 7).Value: destino.Cells(1, 9).Value = p.Cells(linha, 8).Value
            destino.Cells(1, 10).Value = produtos.ListObjects("tblProdutos").DataBodyRange.Cells(CLng(achou), 6).Value
            Set destino = ProximaLinha(mov.ListObjects("tblEstoqueMov"))
            destino.Cells(1, 1).Value = id & "-" & Format$(seq, "000"): destino.Cells(1, 2).Value = DateValue(dataHora): destino.Cells(1, 2).NumberFormat = "dd/mm/yyyy"
            destino.Cells(1, 3).Value = TimeValue(dataHora): destino.Cells(1, 3).NumberFormat = "hh:mm:ss"
            destino.Cells(1, 4).Value = "Saída Venda": destino.Cells(1, 5).Value = codigo: destino.Cells(1, 6).Value = -CDbl(p.Cells(linha, 5).Value)
            destino.Cells(1, 7).Value = id: destino.Cells(1, 8).Value = operador
        End If
    Next linha
    seq = 0: abater = troco
    For j = 3 To 7 Step 2
        forma = Trim$(CStr(p.Cells(31, j).Value))
        If forma <> "" Then
            seq = seq + 1: valor = CDbl(p.Cells(31, j + 1).Value): aplicado = valor
            If forma = "Dinheiro" And abater > 0 Then
                If abater >= valor Then aplicado = 0: abater = abater - valor Else aplicado = valor - abater: abater = 0
            End If
            Set destino = ProximaLinha(pg.ListObjects("tblPagamentos"))
            destino.Cells(1, 1).Value = id: destino.Cells(1, 2).Value = seq: destino.Cells(1, 3).Value = forma
            destino.Cells(1, 4).Value = aplicado: destino.Cells(1, 5).Value = valor: destino.Cells(1, 6).Value = valor - aplicado
        End If
    Next j
    For linha = 12 To 26
        p.Cells(linha, 2).ClearContents: p.Cells(linha, 5).ClearContents: p.Cells(linha, 7).ClearContents
    Next linha
    p.Range("C31:H31").ClearContents
    Application.CalculateFull
    MsgBox "Venda " & id & " registrada. Troco: R$ " & Format$(troco, "0.00") & ". Salve o arquivo.", vbInformation
    Exit Sub
Falha:
    If houveGravacao Then
        MsgBox "ERRO APÓS INÍCIO DA GRAVAÇÃO: " & Err.Description & vbCrLf & "Pode haver registros parciais. Não repita a venda; feche sem salvar e restaure a cópia anterior.", vbCritical
    Else
        MsgBox "Venda não registrada: " & Err.Description, vbExclamation
    End If
End Sub
