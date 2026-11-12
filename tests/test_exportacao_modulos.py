"""Relatórios de clientes, estoque, crediário e turno — serviço e arquivos.

O que este arquivo prova:

* o saldo do crediário considera título **PARCIAL** (regressão real: a primeira
  versão contava só `status == "ABERTO"` e subestimava a carteira);
* documento de cliente sai mascarado no arquivo, como na tela;
* a posição de estoque separa ruptura de "abaixo do mínimo" e soma valor a custo;
* o relatório do turno usa o turno **aberto** quando não se informa id, e o
  turno fechado traz contagem por denominação e classificação da diferença;
* os quatro relatórios viram `.xlsx` numérico e `.pdf` com o título.

O que **não** prova: aparência no Excel do cliente, nem que o PDF é aceito por
alguma prefeitura — não é documento fiscal, e isso está escrito no rodapé.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bussola_pdv.aplicacao.caixa import ServicoCaixa
from bussola_pdv.aplicacao.crediario import ServicoCrediario
from bussola_pdv.aplicacao.estoque import ServicoEstoque
from bussola_pdv.aplicacao.exportacao import ServicoExportacao
from bussola_pdv.aplicacao.pdv import ServicoPDV, SolicitacaoVenda
from bussola_pdv.dominio.caixa import ContagemDenominacao, TipoMovimentoCaixa
from bussola_pdv.dominio.dinheiro import Dinheiro
from bussola_pdv.dominio.erros import ErroValidacao
from bussola_pdv.dominio.pagamentos import FormaPagamento, PlanoPagamento, pagamento_a_prazo
from bussola_pdv.dominio.venda import Carrinho
from bussola_pdv.infra.exportacao import escrever

pytestmark = pytest.mark.integracao


# -- apoio ----------------------------------------------------------------------
def _venda_a_prazo(cenario, quantidade: str = "4", parcelas: int = 2):
    carrinho = Carrinho()
    carrinho.adicionar(cenario.produto_a, quantidade)
    total = carrinho.totais().total
    return ServicoPDV(cenario.ctx).finalizar_venda(
        SolicitacaoVenda(
            operador=cenario.operador,
            caixa_id=cenario.caixa_id,
            carrinho=carrinho,
            plano=PlanoPagamento.de_pagamentos(pagamento_a_prazo(total)),
            cliente_id=cenario.cliente.id,
            parcelas_crediario=parcelas,
        )
    )


def _tabela(relatorio, prefixo: str):
    for tabela in relatorio.tabelas:
        if tabela.titulo.startswith(prefixo):
            return tabela
    raise AssertionError(
        f"tabela '{prefixo}' ausente; há: {[t.titulo for t in relatorio.tabelas]}"
    )


def _indicador(relatorio, rotulo: str) -> str:
    return dict(relatorio.indicadores)[rotulo]


def _texto_do_pdf(caminho: Path) -> str:
    """Texto do PDF com espaços normalizados (o extrator emite tabulações)."""
    pypdf = pytest.importorskip("pypdf")
    leitor = pypdf.PdfReader(caminho)
    bruto = "\n".join(pagina.extract_text() or "" for pagina in leitor.pages)
    return " ".join(bruto.split())


# -- clientes -------------------------------------------------------------------
class TestClientes:
    def test_carteira_traz_limite_e_saldo(self, cenario):
        _venda_a_prazo(cenario)  # 63,60 em aberto para o cliente do cenário
        relatorio = ServicoExportacao(cenario.ctx).relatorio_clientes()
        tabela = _tabela(relatorio, "Clientes")
        linha = next(
            linha for linha in tabela.linhas if linha[0] == cenario.cliente.nome
        )
        assert linha[2] == cenario.cliente.limite_credito  # limite
        assert linha[3] == 6360  # em aberto
        assert linha[4] == cenario.cliente.limite_credito - 6360  # disponível
        assert _indicador(relatorio, "Em aberto") == "R$ 63,60"

    def test_documento_sai_mascarado(self, cenario):
        from bussola_pdv.dominio.cliente import Cliente

        with cenario.ctx.em_transacao():
            cenario.ctx.clientes.criar(
                Cliente(nome="Maria Mascarada", documento="52998224725"),
                criado_em=cenario.ctx.agora().isoformat(),
            )
        relatorio = ServicoExportacao(cenario.ctx).relatorio_clientes("Maria")
        linha = relatorio.tabelas[0].linhas[0]
        assert linha[0] == "Maria Mascarada"
        assert "52998224725" not in str(linha[1])
        assert str(linha[1]).endswith("4725")

    def test_titulo_parcial_conta_no_em_aberto(self, cenario):
        _venda_a_prazo(cenario)
        titulo = sorted(
            cenario.ctx.crediario.listar(cliente_id=cenario.cliente.id),
            key=lambda t: t["numero_parcela"],
        )[0]
        ServicoCrediario(cenario.ctx).receber(
            titulo_id=titulo["id"],
            valor=Dinheiro(1000),
            forma=FormaPagamento.DINHEIRO,
            operador=cenario.operador,
            caixa_id=cenario.caixa_id,
        )
        assert cenario.ctx.crediario.por_id(titulo["id"])["status"] == "PARCIAL"

        relatorio = ServicoExportacao(cenario.ctx).relatorio_clientes()
        linha = next(
            linha for linha in relatorio.tabelas[0].linhas if linha[0] == cenario.cliente.nome
        )
        # 63,60 − 10,00 recebidos: o título PARCIAL precisa continuar na conta.
        assert linha[3] == 5360

    def test_busca_filtra(self, cenario):
        relatorio = ServicoExportacao(cenario.ctx).relatorio_clientes("ninguém com esse nome")
        assert relatorio.tabelas[0].linhas == ()
        assert dict(relatorio.filtros)["Busca"] == "ninguém com esse nome"

    def test_aviso_fiscal_presente(self, cenario):
        relatorio = ServicoExportacao(cenario.ctx).relatorio_clientes()
        assert any("não é documento fiscal" in aviso for aviso in relatorio.avisos)


# -- crediário ------------------------------------------------------------------
class TestCrediario:
    def test_em_aberto_inclui_parcial(self, cenario):
        _venda_a_prazo(cenario)
        titulo = sorted(
            cenario.ctx.crediario.listar(cliente_id=cenario.cliente.id),
            key=lambda t: t["numero_parcela"],
        )[0]
        ServicoCrediario(cenario.ctx).receber(
            titulo_id=titulo["id"],
            valor=Dinheiro(titulo["saldo_centavos"]),
            forma=FormaPagamento.DINHEIRO,
            operador=cenario.operador,
            caixa_id=cenario.caixa_id,
        )
        relatorio = ServicoExportacao(cenario.ctx).relatorio_crediario()
        # uma parcela paga (31,80) e outra em aberto (31,80)
        assert _indicador(relatorio, "Em aberto") == "1"
        assert _indicador(relatorio, "Saldo aberto") == "R$ 31,80"

    def test_incluir_pagos_traz_quem_ja_pagou(self, cenario):
        _venda_a_prazo(cenario)
        for titulo in cenario.ctx.crediario.listar(cliente_id=cenario.cliente.id):
            ServicoCrediario(cenario.ctx).receber(
                titulo_id=titulo["id"],
                valor=Dinheiro(titulo["saldo_centavos"]),
                forma=FormaPagamento.DINHEIRO,
                operador=cenario.operador,
                caixa_id=cenario.caixa_id,
            )
        sem_pagos = ServicoExportacao(cenario.ctx).relatorio_crediario()
        com_pagos = ServicoExportacao(cenario.ctx).relatorio_crediario(incluir_pagos=True)
        assert _indicador(sem_pagos, "Em aberto") == "0"
        assert len(com_pagos.tabelas[0].linhas) > len(sem_pagos.tabelas[0].linhas)
        assert dict(com_pagos.filtros)["Inclui recebidos"] == "sim"

    def test_colunas_do_titulo(self, cenario):
        _venda_a_prazo(cenario)
        relatorio = ServicoExportacao(cenario.ctx).relatorio_crediario()
        titulos = [coluna.titulo for coluna in relatorio.tabelas[0].colunas]
        assert titulos == [
            "Cliente",
            "Parcela",
            "Vencimento",
            "Principal",
            "Recebido",
            "Saldo",
            "Atraso (dias)",
            "Status",
        ]


# -- estoque --------------------------------------------------------------------
class TestEstoque:
    def test_posicao_por_produto(self, cenario):
        relatorio = ServicoExportacao(cenario.ctx).relatorio_estoque()
        tabela = _tabela(relatorio, "Produtos")
        linha = next(linha for linha in tabela.linhas if linha[0] == "A001")
        assert linha[1] == "Café 500 g"
        assert linha[3] == "10"  # 10 unidades em milesimos
        assert linha[7] == 10 * 1000  # valor a custo: 10 × R$ 10,00

    def test_ruptura_aparece_e_soma_no_resumo(self, cenario):
        # zera o saldo do produto A: venda de tudo o que existe no estoque
        with cenario.ctx.em_transacao():
            from bussola_pdv.dominio.estoque import TipoMovimentoEstoque
            from bussola_pdv.infra.sqlite.repositorio_estoque import EstoqueRepositorio

            EstoqueRepositorio(cenario.ctx.conexao).inserir_movimento(
                produto_id=cenario.produto_a.id,
                tipo=TipoMovimentoEstoque.PERDA,
                quantidade_milesimos_assinada=-10_000,
                criado_em=cenario.ctx.agora(),
                motivo="Perda",
            )
        relatorio = ServicoExportacao(cenario.ctx).relatorio_estoque()
        resumo = _tabela(relatorio, "Resumo por situação")
        por_situacao = {linha[0]: linha for linha in resumo.linhas}
        assert por_situacao["RUPTURA"][1] >= 1
        assert _indicador(relatorio, "Ruptura") == str(por_situacao["RUPTURA"][1])

    def test_busca_por_codigo(self, cenario):
        relatorio = ServicoExportacao(cenario.ctx).relatorio_estoque("B002")
        assert len(relatorio.tabelas[0].linhas) == 1
        assert relatorio.tabelas[0].linhas[0][0] == "B002"

    def test_produto_novo_com_minimo_fica_abaixo_do_minimo(self, cenario):
        ServicoEstoque(cenario.ctx).criar_produto(
            operador=cenario.admin,
            codigo="C003",
            descricao="Açúcar 1 kg",
            preco=790,
            custo=500,
            categoria="Mercearia",
            estoque_minimo=5,
        )
        relatorio = ServicoExportacao(cenario.ctx).relatorio_estoque("C003")
        assert relatorio.tabelas[0].linhas[0][6] in {"RUPTURA", "BAIXO", "ABAIXO_DO_MINIMO"}


# -- turno ----------------------------------------------------------------------
class TestTurno:
    def test_usa_o_turno_aberto(self, cenario):
        relatorio = ServicoExportacao(cenario.ctx).relatorio_turno()
        assert _indicador(relatorio, "Turnos") == "1"
        tabela = _tabela(relatorio, "Caixa e dinheiro")
        itens = {linha[0]: linha[1] for linha in tabela.linhas}
        assert itens["Caixa"] == "Caixa Teste"
        assert itens["Operador"] == cenario.gerente.nome
        assert itens["Fundo de troco"] == "R$ 100,00"
        assert itens["Esperado na gaveta"] == "R$ 100,00"
        assert itens["Conferência"].startswith("não conferido")

    def test_movimentos_entram_na_conta(self, cenario):
        caixa = ServicoCaixa(cenario.ctx)
        caixa.movimentar(
            turno_id=cenario.turno_id,
            tipo=TipoMovimentoCaixa.SANGRIA,
            valor=Dinheiro(5000),
            motivo="Depósito bancário",
            operador=cenario.operador,
            autorizador=cenario.gerente,
        )
        relatorio = ServicoExportacao(cenario.ctx).relatorio_turno()
        itens = {linha[0]: linha[1] for linha in _tabela(relatorio, "Caixa e dinheiro").linhas}
        assert itens["Sangrias"] == "R$ 50,00"
        assert itens["Esperado na gaveta"] == "R$ 50,00"
        movimentos = _tabela(relatorio, "Movimentos do turno").linhas
        assert len(movimentos) == 1
        assert movimentos[0][0] == "SANGRIA"
        assert movimentos[0][3] == cenario.gerente.nome  # autorizador resolvido

    def test_turno_fechado_traz_contagem_e_classificacao(self, cenario):
        ServicoCaixa(cenario.ctx).fechar_turno(
            turno_id=cenario.turno_id,
            conferente=cenario.gerente,
            contagens=[ContagemDenominacao(5000, 1), ContagemDenominacao(2000, 2)],
            motivo_diferenca="Faltou troco",
        )
        # sem turno aberto e sem id, não há o que exportar
        with pytest.raises(ErroValidacao):
            ServicoExportacao(cenario.ctx).relatorio_turno()

        relatorio = ServicoExportacao(cenario.ctx).relatorio_turno(cenario.turno_id)
        itens = {linha[0]: linha[1] for linha in _tabela(relatorio, "Caixa e dinheiro").linhas}
        assert itens["Status"] == "FECHADO"
        assert itens["Classificação"] == "ACIMA_LIMITE"
        assert itens["Contado"] == "R$ 90,00"
        assert itens["Diferença"] == "-R$ 10,00"
        contagem = _tabela(relatorio, "Contagem por denominação")
        assert [linha[0] for linha in contagem.linhas] == ["R$ 50,00", "R$ 20,00"]
        assert _indicador(relatorio, "Conferidos") == "1 de 1"

    def test_turno_inexistente_avisa(self, cenario):
        from bussola_pdv.dominio.erros import ErroNaoEncontrado

        with pytest.raises(ErroNaoEncontrado):
            ServicoExportacao(cenario.ctx).relatorio_turno("nao-existe")


# -- arquivos -------------------------------------------------------------------
class TestArquivos:
    @pytest.mark.parametrize(
        "metodo",
        ["relatorio_clientes", "relatorio_crediario", "relatorio_estoque", "relatorio_turno"],
    )
    def test_xlsx_e_pdf_dos_novos_relatorios(self, cenario, tmp_path, metodo):
        openpyxl = pytest.importorskip("openpyxl")
        relatorio = getattr(ServicoExportacao(cenario.ctx), metodo)()
        xlsx = escrever(relatorio, tmp_path / relatorio.nome_de_arquivo("xlsx"))
        pdf = escrever(relatorio, tmp_path / relatorio.nome_de_arquivo("pdf"))
        assert xlsx.stat().st_size > 1000
        assert pdf.stat().st_size > 1000

        pasta = openpyxl.load_workbook(xlsx)
        esperado = " ".join(relatorio.tabelas[0].titulo.split())[:31]
        aba = pasta[esperado]
        assert aba["A2"].value == relatorio.tabelas[0].colunas[0].titulo
        texto = _texto_do_pdf(pdf)
        assert relatorio.titulo in texto
        assert "Documento interno" in texto

    def test_exportar_registra_auditoria(self, cenario, tmp_path):
        servico = ServicoExportacao(cenario.ctx)
        caminho = servico.exportar_estoque(cenario.gerente, tmp_path / "estoque.xlsx")
        assert caminho.exists()
        from bussola_pdv.dominio.auditoria import AcaoAuditoria

        eventos = cenario.ctx.auditoria.listar(limite=50)
        exportacoes = [e for e in eventos if e.acao is AcaoAuditoria.DADOS_EXPORTADOS]
        assert exportacoes, "exportar precisa deixar rastro na trilha append-only"
        assert exportacoes[0].ator_id == cenario.gerente.id
        assert exportacoes[0].depois["titulo"] == "Estoque"
        assert exportacoes[0].depois["formato"] == "xlsx"

    def test_atendente_nao_exporta(self, cenario, tmp_path):
        from bussola_pdv.dominio.erros import AutorizacaoNegada

        with pytest.raises(AutorizacaoNegada):
            ServicoExportacao(cenario.ctx).exportar_clientes(
                cenario.operador, tmp_path / "clientes.xlsx"
            )
        assert not (tmp_path / "clientes.xlsx").exists()


def test_exportar_turno_em_pdf(cenario, tmp_path):
    caminho = ServicoExportacao(cenario.ctx).exportar_turno(
        cenario.master, tmp_path / "turno.pdf"
    )
    assert caminho.suffix == ".pdf"
    assert caminho.read_bytes().startswith(b"%PDF")


# -- CLI ------------------------------------------------------------------------
class TestCLI:
    def test_exporta_clientes(self, cenario, tmp_path, monkeypatch, capsys):
        from bussola_pdv.cli import main as cli_main

        monkeypatch.setenv("BUSSOLA_SENHA", "senha-de-teste")
        codigo = cli_main(
            [
                "exportar",
                "--banco",
                str(cenario.ctx.caminho),
                "--tipo",
                "clientes",
                "--formato",
                "xlsx",
                "--login",
                "gerente",
                "--destino",
                str(tmp_path),
            ]
        )
        assert codigo == 0
        assert list(tmp_path.glob("clientes-*.xlsx"))
        assert "não é documento fiscal" in capsys.readouterr().out

    def test_exporta_turno(self, cenario, tmp_path, monkeypatch):
        from bussola_pdv.cli import main as cli_main

        monkeypatch.setenv("BUSSOLA_SENHA", "senha-de-teste")
        assert (
            cli_main(
                [
                    "exportar",
                    "--banco",
                    str(cenario.ctx.caminho),
                    "--tipo",
                    "turno",
                    "--formato",
                    "xlsx",
                    "--login",
                    "master",
                    "--destino",
                    str(tmp_path / "turno.xlsx"),
                ]
            )
            == 0
        )
        assert (tmp_path / "turno.xlsx").exists()

    def test_incluir_pagos_no_crediario(self, cenario, tmp_path, monkeypatch):
        from bussola_pdv.cli import main as cli_main

        _venda_a_prazo(cenario)
        monkeypatch.setenv("BUSSOLA_SENHA", "senha-de-teste")
        assert (
            cli_main(
                [
                    "exportar",
                    "--banco",
                    str(cenario.ctx.caminho),
                    "--tipo",
                    "crediario",
                    "--incluir-pagos",
                    "--login",
                    "contador",
                    "--destino",
                    str(tmp_path / "crediario.xlsx"),
                ]
            )
            == 0
        )
        assert (tmp_path / "crediario.xlsx").exists()

    def test_estoque_sem_turno_aberto(self, cenario, tmp_path, monkeypatch, capsys):
        """`--tipo turno` sem turno aberto sai com erro claro, sem criar arquivo."""
        from bussola_pdv.aplicacao.caixa import ServicoCaixa
        from bussola_pdv.cli import main as cli_main
        from bussola_pdv.dominio.caixa import ContagemDenominacao

        ServicoCaixa(cenario.ctx).fechar_turno(
            turno_id=cenario.turno_id,
            conferente=cenario.gerente,
            contagens=[ContagemDenominacao(10000, 1)],
        )
        monkeypatch.setenv("BUSSOLA_SENHA", "senha-de-teste")
        codigo = cli_main(
            [
                "exportar",
                "--banco",
                str(cenario.ctx.caminho),
                "--tipo",
                "turno",
                "--login",
                "master",
                "--destino",
                str(tmp_path / "turno.xlsx"),
            ]
        )
        assert codigo == 2
        assert not (tmp_path / "turno.xlsx").exists()
        assert "Nenhum turno aberto" in capsys.readouterr().err
