"""Exportação: modelo do relatório, escritores `.xlsx`/`.pdf`, serviço e CLI.

O que este arquivo prova — e o que ele **não** prova:

* prova que o `.xlsx` gerado é lido por um leitor de verdade (openpyxl, quando
  instalado) e que moeda vira número, data vira data e texto é escapado;
* prova que o `.pdf` tem cabeçalho `%PDF`, fim `%%EOF`, paginação e o texto do
  título, lido por `pypdf` (quando instalado);
* **não** prova que o arquivo fica bonito no Excel do cliente nem que a
  impressora da loja aceita o PDF. Isso é conferência humana, e está no
  checklist de `docs/EXPORTACAO.md`.
"""

from __future__ import annotations

import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from bussola_pdv.aplicacao.exportacao import ServicoExportacao
from bussola_pdv.aplicacao.pdv import ServicoPDV, SolicitacaoVenda
from bussola_pdv.cli import main as cli_main
from bussola_pdv.dominio.erros import AutorizacaoNegada, ErroValidacao
from bussola_pdv.dominio.pagamentos import PlanoPagamento, pagamento_dinheiro
from bussola_pdv.dominio.relatorio import (
    DOCUMENTO_INTERNO,
    Coluna,
    Relatorio,
    Tabela,
    TipoColuna,
    criar_tabela,
    slug,
)
from bussola_pdv.dominio.venda import Carrinho
from bussola_pdv.infra.exportacao import FORMATOS, escrever, nome_sugerido
from bussola_pdv.infra.exportacao import formato as fmt

SENHA_TESTE = "senha-de-teste"


# -- dados de apoio -------------------------------------------------------------
def relatorio_exemplo(linhas: int = 3) -> Relatorio:
    tabela = criar_tabela(
        "Por forma de pagamento",
        [
            ("Forma", TipoColuna.TEXTO, 24),
            ("Aplicado", TipoColuna.MOEDA, 14),
            ("Lançamentos", TipoColuna.INTEIRO, 12),
            ("Data", TipoColuna.DATA, 12),
        ],
        [
            (f"Forma {indice} & cia", 16449 + indice, indice, "2026-11-11")
            for indice in range(1, linhas + 1)
        ],
        nota="Valor aplicado compõe faturamento; troco não é receita.",
    )
    return Relatorio(
        titulo="Fechamento do caixa",
        subtitulo="Conferência aritmética do dia",
        loja="Mercadinho Bússola & Cia",
        identificacao=(("Loja", "Mercadinho Bússola & Cia"), ("CNPJ", "12.345.678/0001-90")),
        filtros=(("Data de negócio", "2026-11-11"),),
        indicadores=(("Cupons", "5"), ("Faturamento", "R$ 164,49")),
        tabelas=(tabela,),
        avisos=("Documento interno: não é documento fiscal.",),
        escopo="Filtro: data comercial e status CONCLUIDA.",
        gerado_em=datetime(2026, 11, 11, 12, 0, tzinfo=UTC),
    )


def vender_dinheiro(cenario, quantidade: str = "2") -> None:
    carrinho = Carrinho()
    carrinho.adicionar(cenario.produto_a, quantidade)
    total = carrinho.totais().total
    ServicoPDV(cenario.ctx).finalizar_venda(
        SolicitacaoVenda(
            operador=cenario.operador,
            caixa_id=cenario.caixa_id,
            carrinho=carrinho,
            plano=PlanoPagamento.de_pagamentos(pagamento_dinheiro(total, total)),
        )
    )


# -- modelo --------------------------------------------------------------------
class TestModelo:
    def test_tabela_valida_quantidade_de_colunas(self):
        with pytest.raises(ErroValidacao, match=r"valor\(es\)"):
            Tabela("X", (Coluna("A"), Coluna("B")), (("só um",),))

    def test_coluna_sem_titulo_e_recusada(self):
        with pytest.raises(ErroValidacao):
            Coluna("   ")

    def test_relatorio_sem_titulo_e_recusado(self):
        with pytest.raises(ErroValidacao):
            Relatorio(titulo="  ")

    def test_contagem_de_linhas_soma_as_tabelas(self):
        tabela = criar_tabela("T", [("A", TipoColuna.TEXTO)], [("1",), ("2",)])
        relatorio = Relatorio(titulo="R", tabelas=(tabela, tabela))
        assert relatorio.linhas == 4

    def test_nome_de_arquivo_usa_a_data_do_filtro(self):
        assert nome_sugerido(relatorio_exemplo(), "xlsx") == "fechamento-do-caixa-2026-11-11.xlsx"
        assert nome_sugerido(relatorio_exemplo(), ".pdf") == "fechamento-do-caixa-2026-11-11.pdf"

    def test_nome_de_arquivo_sem_data_usa_carimbo(self):
        relatorio = relatorio_exemplo()
        sem_data = Relatorio(
            titulo="Catálogo", gerado_em=relatorio.gerado_em, filtros=(("Busca", "café"),)
        )
        assert sem_data.nome_de_arquivo("pdf") == "catalogo-20261111-1200.pdf"

    def test_slug_remove_acento_e_pontuacao(self):
        assert slug("Período 01/11 a 11/11/2026") == "periodo-01-11-a-11-11-2026"
        assert slug("!!!") == "relatorio"

    def test_tipo_coluna_numerica(self):
        assert Coluna("A", TipoColuna.MOEDA).numerica
        assert Coluna("A", TipoColuna.INTEIRO).numerica
        assert not Coluna("A", TipoColuna.TEXTO).numerica
        assert not Coluna("A", TipoColuna.DATA).numerica


class TestFormato:
    def test_moeda_brasileira(self):
        assert fmt.moeda(16449) == "R$ 164,49"
        assert fmt.moeda(0) == "R$ 0,00"
        assert fmt.moeda(123456789) == "R$ 1.234.567,89"
        assert fmt.moeda(-150) == "-R$ 1,50"

    def test_reais_arredonda_sem_float_sujo(self):
        assert fmt.reais(16449) == 164.49
        assert fmt.reais(1) == 0.01
        assert fmt.reais(None) == 0.0

    def test_data_aceita_iso_e_date(self):
        assert fmt.data_br("2026-11-11") == "11/11/2026"
        assert fmt.data_br(datetime(2026, 11, 11).date()) == "11/11/2026"
        assert fmt.data_br("texto") == "texto"

    def test_texto_trata_bool_e_none(self):
        assert fmt.texto(None) == ""
        assert fmt.texto(True) == "Sim"
        assert fmt.texto(False) == "Não"

    def test_celula_por_tipo(self):
        assert fmt.celula(1000, TipoColuna.MOEDA) == "R$ 10,00"
        assert fmt.celula(7, TipoColuna.INTEIRO) == "7"
        assert fmt.celula("2026-01-02", TipoColuna.DATA) == "02/01/2026"


# -- xlsx ----------------------------------------------------------------------
class TestXlsx:
    def test_abas_e_partes_do_pacote(self, tmp_path):
        destino = escrever(relatorio_exemplo(), tmp_path / "f.xlsx")
        with zipfile.ZipFile(destino) as pacote:
            nomes = set(pacote.namelist())
        assert {
            "[Content_Types].xml",
            "_rels/.rels",
            "xl/workbook.xml",
            "xl/worksheets/sheet1.xml",
            "xl/worksheets/sheet2.xml",
            "xl/styles.xml",
            "docProps/core.xml",
        } <= nomes

    def test_leitura_por_biblioteca_de_verdade(self, tmp_path):
        openpyxl = pytest.importorskip("openpyxl", reason="openpyxl é dependência de teste")
        destino = escrever(relatorio_exemplo(), tmp_path / "f.xlsx")
        pasta = openpyxl.load_workbook(destino)
        assert pasta.sheetnames == ["Resumo", "Por forma de pagamento"]
        resumo = pasta["Resumo"]
        assert resumo["A1"].value == "Fechamento do caixa"
        assert resumo["B1"].value is None

        aba = pasta["Por forma de pagamento"]
        assert aba["A1"].value == "Por forma de pagamento"
        assert [celula.value for celula in aba[2]] == [
            "Forma",
            "Aplicado",
            "Lançamentos",
            "Data",
        ]
        primeira = [celula.value for celula in aba[3]]
        assert primeira[0] == "Forma 1 & cia"  # escapado e devolvido inteiro
        assert primeira[1] == pytest.approx(164.50)  # moeda é número, não texto
        assert primeira[2] == 1
        assert primeira[3].strftime("%Y-%m-%d") == "2026-11-11"  # data de verdade

    def test_moeda_tem_formato_de_real_e_data_formato_brasileiro(self, tmp_path):
        openpyxl = pytest.importorskip("openpyxl")
        destino = escrever(relatorio_exemplo(), tmp_path / "f.xlsx")
        aba = openpyxl.load_workbook(destino)["Por forma de pagamento"]
        assert "R$" in aba["B3"].number_format
        assert aba["D3"].number_format == "dd/mm/yyyy"

    def test_cabecalho_congelado_com_filtro_e_larguras(self, tmp_path):
        openpyxl = pytest.importorskip("openpyxl")
        destino = escrever(relatorio_exemplo(), tmp_path / "f.xlsx")
        aba = openpyxl.load_workbook(destino)["Por forma de pagamento"]
        assert aba.freeze_panes == "A3"
        assert aba.auto_filter.ref == "A2:D5"
        assert aba.column_dimensions["A"].width == 24

    def test_sem_linhas_nao_cria_filtro(self, tmp_path):
        openpyxl = pytest.importorskip("openpyxl")
        vazio = Relatorio(
            titulo="Vendas",
            tabelas=(criar_tabela("Cupons", [("Cupom", TipoColuna.TEXTO)], []),),
        )
        destino = escrever(vazio, tmp_path / "vazio.xlsx")
        aba = openpyxl.load_workbook(destino)["Cupons"]
        assert aba.auto_filter.ref is None
        assert aba.max_row <= 3

    def test_nome_de_aba_e_saneado_e_unico(self, tmp_path):
        longa = "R" * 40 + ":relatório/inválido"
        tabela = criar_tabela("Cupons", [("A", TipoColuna.TEXTO)], [("1",)])
        relatorio = Relatorio(
            titulo="R",
            tabelas=(
                Tabela(longa, tabela.colunas, tabela.linhas),
                Tabela(longa, tabela.colunas, tabela.linhas),
            ),
        )
        destino = escrever(relatorio, tmp_path / "f.xlsx")
        with zipfile.ZipFile(destino) as pacote:
            livro = pacote.read("xl/workbook.xml").decode()
        nomes = [trecho.split('"')[0] for trecho in livro.split('name="')[1:]]
        assert len(nomes) == 3
        assert all(len(nome) <= 31 for nome in nomes)
        assert not any(caractere in nome for nome in nomes for caractere in "[]:*?/\\")
        assert len({nome.lower() for nome in nomes}) == 3

    def test_cria_pasta_e_grava_atomico(self, tmp_path):
        destino = escrever(relatorio_exemplo(), tmp_path / "a" / "b" / "f.xlsx")
        assert destino.is_file()
        assert not list(destino.parent.glob("*.tmp"))

    def test_extensao_desconhecida_e_recusada(self, tmp_path):
        with pytest.raises(ErroValidacao, match="não suportado"):
            escrever(relatorio_exemplo(), tmp_path / "f.docx")
        assert FORMATOS == {".xlsx": "Excel", ".pdf": "PDF"}

    def test_valor_invalido_em_coluna_numerica(self, tmp_path):
        """Coluna MOEDA com texto é erro de quem monta, e a mensagem diz onde."""
        tabela = criar_tabela("X", [("Valor", TipoColuna.MOEDA)], [("não é número",)])
        with pytest.raises(ErroValidacao, match="não é numérico"):
            escrever(Relatorio(titulo="R", tabelas=(tabela,)), tmp_path / "f.xlsx")


# -- pdf -----------------------------------------------------------------------
class TestPdf:
    def test_arquivo_pdf_valido(self, tmp_path):
        destino = escrever(relatorio_exemplo(), tmp_path / "f.pdf")
        conteudo = destino.read_bytes()
        assert conteudo.startswith(b"%PDF-")
        assert conteudo.rstrip().endswith(b"%%EOF")

    def test_texto_do_relatorio_aparece(self, tmp_path):
        pypdf = pytest.importorskip("pypdf", reason="pypdf é dependência de teste")
        destino = escrever(relatorio_exemplo(), tmp_path / "f.pdf")
        leitor = pypdf.PdfReader(str(destino))
        texto = "\n".join(pagina.extract_text() for pagina in leitor.pages)
        assert "Fechamento" in texto
        assert "Docu" in texto  # rodapé/aviso presente
        assert "página 1 de" in texto.replace("\t", " ")

    def test_muitas_linhas_geram_varias_paginas(self, tmp_path):
        pypdf = pytest.importorskip("pypdf")
        destino = escrever(relatorio_exemplo(linhas=400), tmp_path / "grande.pdf")
        leitor = pypdf.PdfReader(str(destino))
        assert len(leitor.pages) > 1

    def test_html_escapa_conteudo_do_banco(self):
        from bussola_pdv.infra.exportacao import pdf

        tabela = criar_tabela(
            "Descrições", [("Descrição", TipoColuna.TEXTO)], [("<script>alert(1)</script>",)]
        )
        html = pdf.montar_html(Relatorio(titulo="R & <b>", tabelas=(tabela,)))
        assert "<script>" not in html
        assert "&lt;script&gt;" in html
        assert "&amp;" in html

    def test_colunas_numericas_vem_alinhadas_a_direita(self):
        from bussola_pdv.infra.exportacao import pdf

        html = pdf.montar_html(relatorio_exemplo())
        assert html.count('align="right"') >= 2


# -- serviço de aplicação -------------------------------------------------------
class TestServico:
    def test_fechamento_exportado_bate_com_o_relatorio_da_tela(self, cenario, tmp_path):
        vender_dinheiro(cenario)
        servico = ServicoExportacao(cenario.ctx)
        from bussola_pdv.aplicacao.relatorios import ServicoRelatorios

        dados = ServicoRelatorios(cenario.ctx).fechamento_dia("2026-11-11")
        relatorio = servico.relatorio_fechamento("2026-11-11")

        assert ("Cupons", str(dados["resumo"]["cupons"])) in relatorio.indicadores
        resumo_tabela = relatorio.tabelas[0]
        faturamento = dict(resumo_tabela.linhas)["Faturamento líquido"]
        assert fmt.moeda(dados["resumo"]["faturamento_centavos"]) == faturamento

        destino = servico.exportar_fechamento(
            cenario.gerente, "2026-11-11", tmp_path / "fechamento.xlsx"
        )
        assert destino.is_file()
        assert destino.stat().st_size > 1000

    def test_exportacao_registra_evento_e_mantem_cadeia(self, cenario, tmp_path):
        servico = ServicoExportacao(cenario.ctx)
        servico.exportar_fechamento(cenario.gerente, "2026-11-11", tmp_path / "f.pdf")

        eventos = cenario.ctx.auditoria.listar(limite=1)
        assert eventos[0].acao.value == "DADOS_EXPORTADOS"
        assert eventos[0].entidade == "relatorio"
        assert eventos[0].entidade_id == "f.pdf"
        assert eventos[0].depois["formato"] == "pdf"
        assert eventos[0].depois.get("data_negocio", True)
        assert eventos[0].data_negocio == "2026-11-11"
        assert eventos[0].ator_id == cenario.gerente.id
        assert cenario.ctx.auditoria.verificar().integro

    def test_atendente_nao_exporta(self, cenario, tmp_path):
        with pytest.raises(AutorizacaoNegada, match="EXPORTAR_DADOS"):
            ServicoExportacao(cenario.ctx).exportar_fechamento(
                cenario.operador, "2026-11-11", tmp_path / "x.xlsx"
            )
        assert not (tmp_path / "x.xlsx").exists()

    def test_contabilidade_exporta(self, cenario, tmp_path):
        # A contabilidade não opera caixa, mas precisa levar o fechamento.
        destino = ServicoExportacao(cenario.ctx).exportar_fechamento(
            cenario.contabilidade, "2026-11-11", tmp_path / "cont.xlsx"
        )
        assert destino.is_file()

    def test_outros_relatorios(self, cenario, tmp_path):
        vender_dinheiro(cenario)
        servico = ServicoExportacao(cenario.ctx)
        assert servico.relatorio_vendas("2026-11-01", "2026-11-11").tabelas[0].linhas
        assert servico.relatorio_catalogo().tabelas[0].linhas
        assert servico.relatorio_auditoria(limite=5).tabelas[0].linhas
        assert servico.relatorio_crediario().titulo == "Crediário"
        for nome in ("vendas.xlsx", "catalogo.pdf", "auditoria.xlsx", "crediario.pdf"):
            assert servico.exportar(
                cenario.gerente,
                {
                    "vendas.xlsx": servico.relatorio_vendas("2026-11-01", "2026-11-11"),
                    "catalogo.pdf": servico.relatorio_catalogo(),
                    "auditoria.xlsx": servico.relatorio_auditoria(limite=5),
                    "crediario.pdf": servico.relatorio_crediario(),
                }[nome],
                tmp_path / nome,
            ).is_file()

    def test_loja_aparece_no_relatorio(self, cenario, tmp_path):
        from bussola_pdv.aplicacao.marca import ServicoMarca
        from bussola_pdv.dominio.marca import Marca

        ServicoMarca(cenario.ctx).salvar(
            cenario.master, Marca(nome_fantasia="Mercadinho Bússola", cnpj="12.345.678/0001-90")
        )
        relatorio = ServicoExportacao(cenario.ctx).relatorio_fechamento("2026-11-11")
        assert relatorio.loja == "Mercadinho Bússola"
        assert ("CNPJ", "12.345.678/0001-90") in relatorio.identificacao

    def test_todos_os_relatorios_carregam_o_aviso_fiscal(self, cenario):
        servico = ServicoExportacao(cenario.ctx)
        relatorios = [
            servico.relatorio_fechamento("2026-11-11"),
            servico.relatorio_vendas("2026-11-01", "2026-11-11"),
            servico.relatorio_catalogo(),
            servico.relatorio_auditoria(limite=3),
            servico.relatorio_crediario(),
        ]
        for relatorio in relatorios:
            assert any("não é documento fiscal" in aviso for aviso in relatorio.avisos)
            assert relatorio.documento == DOCUMENTO_INTERNO


# -- linha de comando -----------------------------------------------------------
class TestCli:
    def test_exporta_pdf_pelo_cli(self, cenario, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("BUSSOLA_SENHA", SENHA_TESTE)
        destino = tmp_path / "cli" / "fechamento.pdf"
        codigo = cli_main(
            [
                "exportar",
                "--banco",
                str(cenario.ctx.caminho),
                "--tipo",
                "fechamento",
                "--data",
                "2026-11-11",
                "--formato",
                "pdf",
                "--login",
                "gerente",
                "--destino",
                str(destino),
            ]
        )
        assert codigo == 0
        assert destino.is_file()
        saida = capsys.readouterr().out
        assert "Fechamento do caixa" in saida
        assert "não é documento fiscal" in saida

    def test_destino_pasta_usa_nome_sugerido(self, cenario, tmp_path, monkeypatch):
        monkeypatch.setenv("BUSSOLA_SENHA", SENHA_TESTE)
        pasta = tmp_path / "relatorios"
        pasta.mkdir()
        assert (
            cli_main(
                [
                    "exportar",
                    "--banco",
                    str(cenario.ctx.caminho),
                    "--data",
                    "2026-11-11",
                    "--login",
                    "gerente",
                    "--destino",
                    str(pasta),
                ]
            )
            == 0
        )
        assert [arquivo.name for arquivo in pasta.iterdir()] == [
            "fechamento-do-caixa-2026-11-11.xlsx"
        ]

    def test_senha_errada_nao_gera_arquivo(self, cenario, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("BUSSOLA_SENHA", "senha-errada")
        codigo = cli_main(
            [
                "exportar",
                "--banco",
                str(cenario.ctx.caminho),
                "--data",
                "2026-11-11",
                "--login",
                "gerente",
                "--destino",
                str(tmp_path / "x.xlsx"),
            ]
        )
        assert codigo == 2
        assert not (tmp_path / "x.xlsx").exists()
        assert "inválidos" in capsys.readouterr().err

    def test_perfil_sem_permissao_sai_com_erro(self, cenario, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("BUSSOLA_SENHA", SENHA_TESTE)
        codigo = cli_main(
            [
                "exportar",
                "--banco",
                str(cenario.ctx.caminho),
                "--data",
                "2026-11-11",
                "--login",
                "operador",
                "--destino",
                str(tmp_path / "x.xlsx"),
            ]
        )
        assert codigo == 2
        assert "EXPORTAR_DADOS" in capsys.readouterr().err

    def test_fechamento_sem_data_e_recusado(self, cenario, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("BUSSOLA_SENHA", SENHA_TESTE)
        codigo = cli_main(
            [
                "exportar",
                "--banco",
                str(cenario.ctx.caminho),
                "--login",
                "gerente",
                "--destino",
                str(tmp_path / "x.xlsx"),
            ]
        )
        assert codigo == 2
        assert "--data" in capsys.readouterr().err

    def test_banco_inexistente(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("BUSSOLA_SENHA", SENHA_TESTE)
        codigo = cli_main(
            [
                "exportar",
                "--banco",
                str(tmp_path / "nao_existe.db"),
                "--login",
                "gerente",
                "--destino",
                str(tmp_path / "x.xlsx"),
            ]
        )
        assert codigo == 2
        assert "Banco não encontrado" in capsys.readouterr().err


def test_caminho_de_relatorios_do_usuario(tmp_path, monkeypatch):
    from bussola_pdv import caminhos

    monkeypatch.setenv("BUSSOLA_DADOS", str(tmp_path))
    pasta = caminhos.pasta_de_relatorios()
    assert pasta == tmp_path / "relatorios"
    assert pasta.is_dir()
    assert nome_sugerido(relatorio_exemplo(), "pdf").endswith(".pdf")
    assert Path(nome_sugerido(relatorio_exemplo(), "pdf")).suffix == ".pdf"
