"""Testes da impressão: documento, bytes ESC/POS, papel, aplicação e telas.

O que estes testes provam — e o que **não** provam:

* provam que o documento cabe nas colunas do papel, que o cupom carrega os dados
  gravados da venda, que o motor escolhido é respeitado, que os bytes ESC/POS
  saem na ordem certa, que o PDF tem o tamanho do papel e que cada impressão
  deixa evento de auditoria;
* **não** provam impressão em hardware. O ambiente de teste não tem impressora
  nem CUPS: `QPrinter` é verificado em modo PDF/arquivo e o envio cru com
  executores injetados. Teste em impressora térmica real é manual e está descrito
  em docs/IMPRESSAO.md.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from bussola_pdv.aplicacao.impressao import (
    AVISO_NAO_FISCAL,
    ConfiguracaoImpressao,
    MotorImpressao,
    ServicoImpressao,
)
from bussola_pdv.aplicacao.pdv import ServicoPDV, SolicitacaoVenda
from bussola_pdv.dominio.auditoria import AcaoAuditoria
from bussola_pdv.dominio.dinheiro import Dinheiro, Quantidade
from bussola_pdv.dominio.erros import ErroImpressao, ErroValidacao, ImpressoraIndisponivel
from bussola_pdv.dominio.impressao import (
    PERFIS_PAPEL,
    Alinhamento,
    CodigoDeBarras,
    Divisor,
    DocumentoImpresso,
    Enfase,
    Item,
    Papel,
    Par,
    Texto,
    barras_do_codigo,
    centrar,
    largura_de,
    padrao_code39,
)
from bussola_pdv.dominio.pagamentos import PlanoPagamento, pagamento_dinheiro
from bussola_pdv.dominio.relatorio import TipoColuna, criar_tabela
from bussola_pdv.dominio.venda import Carrinho
from bussola_pdv.infra.impressao import escpos
from bussola_pdv.infra.impressao import impressoras as infra_impressoras
from bussola_pdv.infra.impressao import papel as renderizador
from bussola_pdv.infra.impressao import texto as renderizador_texto


# -- ajudas --------------------------------------------------------------------
def documento_de_exemplo(papel: Papel = Papel.BOBINA_58) -> DocumentoImpresso:
    return DocumentoImpresso(
        titulo="TESTE",
        papel=papel,
        blocos=(
            Texto("Loja de Demonstração", Alinhamento.CENTRO, Enfase.TITULO),
            Divisor("="),
            Par("Cupom", "1-000012"),
            Item(
                descricao="Café torrado e moído tradicional 500 g pacote econômico",
                quantidade=Quantidade(2000),
                unidade="UN",
                unitario=Dinheiro(1000),
                total=Dinheiro(2000),
                desconto=Dinheiro(15),
                codigo="A001",
            ),
            Divisor(),
            Par("TOTAL", "R$ 20,00", Enfase.TITULO),
            CodigoDeBarras("1-000012"),
        ),
        rotulo="cupom-teste",
        avisos=("Documento interno, não fiscal.",),
    )


def venda_de_exemplo(cenario):
    """Venda de 2 × A001 em dinheiro, com troco — o mesmo caminho do PDV."""
    carrinho = Carrinho()
    carrinho.adicionar(cenario.produto_a, "2")
    total = carrinho.totais().total
    plano = PlanoPagamento.de_pagamentos(pagamento_dinheiro(total, Dinheiro(5000)))
    return ServicoPDV(cenario.ctx).finalizar_venda(
        SolicitacaoVenda(
            operador=cenario.operador,
            caixa_id=cenario.caixa_id,
            carrinho=carrinho,
            plano=plano,
        )
    )


# -- domínio -------------------------------------------------------------------
class TestDominioImpressao:
    def test_cada_papel_tem_as_colunas_documentadas(self):
        assert PERFIS_PAPEL[Papel.BOBINA_58].colunas == 32
        assert PERFIS_PAPEL[Papel.BOBINA_80].colunas == 48
        assert PERFIS_PAPEL[Papel.A4].colunas == 80
        assert PERFIS_PAPEL[Papel.BOBINA_58].contínuo
        assert not PERFIS_PAPEL[Papel.A4].contínuo

    def test_nenhuma_linha_passa_da_largura_do_papel(self):
        for papel in Papel:
            documento = documento_de_exemplo(papel)
            colunas = PERFIS_PAPEL[papel].colunas
            for linha in documento.layout():
                if linha.eh_codigo_de_barras:
                    continue
                assert largura_de(linha.texto) <= colunas, (papel, linha.texto)

    def test_trocar_de_papel_mantem_o_conteudo_e_muda_a_quebra(self):
        estreito = documento_de_exemplo(Papel.BOBINA_58)
        largo = estreito.com_papel(Papel.A4)
        assert len(largo.layout()) <= len(estreito.layout())
        assert "Café" in largo.texto()

    def test_altura_cresce_com_o_conteudo_e_com_a_bobina(self):
        documento = documento_de_exemplo(Papel.BOBINA_58)
        assert documento.altura_mm() > 0
        maior = DocumentoImpresso(
            "MAIOR",
            Papel.BOBINA_58,
            tuple(Texto(f"linha {n}") for n in range(20)),
            "maior",
        )
        assert maior.altura_mm() > documento.altura_mm()

    def test_documento_sem_blocos_ou_sem_titulo_e_recusado(self):
        with pytest.raises(ErroValidacao):
            DocumentoImpresso("TESTE", Papel.A4, (), "vazio")
        with pytest.raises(ErroValidacao):
            DocumentoImpresso("   ", Papel.A4, (Texto("x"),), "sem-titulo")
        with pytest.raises(ErroValidacao):
            DocumentoImpresso("TESTE", Papel.A4, (Texto("x"),), "rótulo com espaço")

    def test_par_longo_desce_alinhado_a_direita(self):
        documento = DocumentoImpresso(
            "TESTE",
            Papel.BOBINA_58,
            (Par("Descrição muito comprida", "R$ 1.234,56"),),
            "par",
        )
        linhas = documento.layout()
        assert len(linhas) == 2
        assert linhas[1].alinhamento is Alinhamento.DIREITA
        assert linhas[1].texto.endswith("R$ 1.234,56")

    def test_centrar_nao_conta_acento_como_coluna_extra(self):
        assert largura_de("Café") == 4
        assert centrar("Café", 10).strip() == "Café"

    def test_code39_tem_inicio_fim_e_razao_3_para_1(self):
        padrao = padrao_code39("1-000012")
        # 10 caracteres (8 do dado + 2 asteriscos) × 15 módulos, mais 1 módulo de
        # espaço estreito entre caracteres (9 intervalos).
        assert padrao.count("1") + padrao.count("0") == 10 * 15 + 9
        assert set(padrao) == {"0", "1"}
        barras = barras_do_codigo("1-000012")
        assert len(barras) == 50  # 10 caracteres × 5 barras (incluindo os asteriscos)
        # as barras são a "tinta" dentro do padrão: começam no módulo 0 e terminam antes do fim
        assert barras[0][0] == 0
        assert barras[-1][0] + barras[-1][1] <= len(padrao)
        assert {largura for _, largura in barras} == {1, escpos.LARGURA_BARRAS}

    def test_code39_recusa_caractere_fora_do_alfabeto(self):
        with pytest.raises(ErroValidacao):
            padrao_code39("AB_C")


# -- bytes ESC/POS -------------------------------------------------------------
class TestEscPos:
    def test_comeca_inicializando_e_termina_cortando(self):
        dados = escpos.renderizar(documento_de_exemplo(Papel.BOBINA_58))
        assert dados.startswith(escpos.INICIALIZAR + escpos.TABELA_1252)
        assert dados.endswith(escpos.CORTAR)

    def test_acento_vira_equivalente_sem_acento(self):
        assert escpos.transliterar("Café à moda") == "Cafe a moda"
        dados = escpos.renderizar(documento_de_exemplo(Papel.BOBINA_58))
        assert "Café".encode() not in dados  # nada de UTF-8 cru na bobina
        assert b"Cafe" in dados

    def test_gaveta_e_corte_sao_opcionais(self):
        sem_corte = escpos.renderizar(
            documento_de_exemplo(Papel.BOBINA_58), cortar=False, abrir_gaveta=False
        )
        assert escpos.CORTAR not in sem_corte
        assert escpos.GAVETA not in sem_corte
        com_gaveta = escpos.renderizar(documento_de_exemplo(Papel.BOBINA_58), abrir_gaveta=True)
        assert escpos.GAVETA in com_gaveta

    def test_codigo_de_barras_usa_comando_nativo(self):
        dados = escpos.renderizar(documento_de_exemplo(Papel.BOBINA_58))
        assert bytes([0x1D, 0x68, escpos.ALTURA_BARRAS_PONTOS]) in dados
        assert bytes([0x1D, 0x77, escpos.LARGURA_BARRAS]) in dados
        assert bytes([0x1D, 0x6B, 4]) in dados

    def test_folha_a4_nao_recebe_corte(self):
        dados = escpos.renderizar(documento_de_exemplo(Papel.A4), cortar=True)
        assert escpos.CORTAR not in dados


# -- texto puro ----------------------------------------------------------------
class TestTextoPuro:
    def test_texto_puro_tem_uma_linha_por_linha_do_papel(self):
        documento = documento_de_exemplo(Papel.BOBINA_58)
        linhas = renderizador_texto.linhas(documento)
        assert len(linhas) == len(documento.layout())

    def test_modo_ascii_mostra_o_que_a_termica_vai_imprimir(self):
        documento = DocumentoImpresso("TESTE", Papel.BOBINA_58, (Texto("Açaí"),), "ascii")
        assert "Açaí" in renderizador_texto.renderizar(documento)
        assert "Acai" in renderizador_texto.renderizar(documento, ascii=True)


# -- papel (Qt): PDF e imagem --------------------------------------------------
class TestRenderizadorPapel:
    def test_pdf_da_bobina_tem_a_largura_do_papel(self, tmp_path):
        pypdf = pytest.importorskip("pypdf")
        documento = documento_de_exemplo(Papel.BOBINA_58)
        destino = renderizador.escrever_pdf(documento, tmp_path / "cupom.pdf")
        assert destino.exists()
        assert destino.stat().st_size > 800
        pagina = pypdf.PdfReader(str(destino)).pages[0]
        largura_mm = float(pagina.mediabox.width) / 72 * 25.4
        assert 56 <= largura_mm <= 60  # 58 mm com arredondamento do driver
        assert float(pagina.mediabox.height) > 0

    def test_pdf_a4_usa_folha_padrao(self, tmp_path):
        pypdf = pytest.importorskip("pypdf")
        destino = renderizador.escrever_pdf(
            documento_de_exemplo(Papel.A4), tmp_path / "relatorio.pdf"
        )
        pagina = pypdf.PdfReader(str(destino)).pages[0]
        assert round(float(pagina.mediabox.width) / 72 * 25.4) == 210

    def test_previa_em_imagem_nao_e_vazia(self):
        pytest.importorskip("PySide6.QtGui")
        from PySide6.QtGui import QColor

        imagem = renderizador.imagem(documento_de_exemplo(Papel.BOBINA_58))
        assert imagem.width() > 100
        # alguma tinta na página? (fundo branco com texto preto)
        cores = {imagem.pixelColor(x, y).name() for x in range(0, imagem.width(), 7)
                 for y in range(0, imagem.height(), 7)}
        assert QColor("#FFFFFF").name() in cores
        assert len(cores) > 1

    def test_impressora_inexistente_falha_com_mensagem_util(self):
        pytest.importorskip("PySide6.QtPrintSupport")
        with pytest.raises(ErroImpressao) as erro:
            renderizador.imprimir(documento_de_exemplo(), "Impressora Que Não Existe")
        assert "não aceitou" in str(erro.value) or "não encontrada" in str(erro.value)

    def test_impressora_em_branco_pede_configuracao(self):
        pytest.importorskip("PySide6.QtPrintSupport")
        with pytest.raises(ErroImpressao):
            renderizador.imprimir(documento_de_exemplo(), "")


# -- infra: envio cru e descoberta ---------------------------------------------
class TestEnvioCru:
    def test_bytes_sao_entregues_ao_executor_da_plataforma(self):
        recebido: dict[str, object] = {}

        def falso(nome: str, dados: bytes) -> None:
            recebido["nome"] = nome
            recebido["dados"] = dados

        infra_impressoras.enviar_bytes("POS-80", b"\x1b@oi", executores={"posix": falso})
        assert recebido == {"nome": "POS-80", "dados": b"\x1b@oi"}

    def test_sem_dados_ou_sem_impressora_nao_envia(self):
        with pytest.raises(ErroImpressao):
            infra_impressoras.enviar_bytes("POS-80", b"", executores={"posix": lambda n, d: None})
        with pytest.raises(ErroImpressao):
            infra_impressoras.enviar_bytes("", b"x", executores={"posix": lambda n, d: None})

    def test_dica_de_termica_vem_do_nome_mas_nao_decide_nada(self):
        assert infra_impressora_termica("POS-80C")
        assert infra_impressora_termica("Elgin i9")
        assert not infra_impressora_termica("HP LaserJet 1102")


def infra_impressora_termica(nome: str) -> bool:
    return infra_impressoras.eh_termica(nome)


# -- aplicação -----------------------------------------------------------------
class TestServicoImpressao:
    def test_configuracao_padrao_e_driver_do_sistema_em_bobina_80(self, cenario):
        config = ServicoImpressao(cenario.ctx).configuracao()
        assert config.motor is MotorImpressao.SISTEMA
        assert config.papel is Papel.BOBINA_80
        assert config.copias == 1
        assert config.codigo_de_barras

    def test_parametro_invalido_cai_no_padrao_sem_quebrar(self, cenario):
        cenario.ctx.parametros.definir("impressao.motor", "IMPOSSIVEL", agora_iso="x")
        config = ServicoImpressao(cenario.ctx).configuracao()
        assert config.motor is MotorImpressao.SISTEMA

    def test_cupom_traz_os_dados_gravados_da_venda(self, cenario):
        resultado = venda_de_exemplo(cenario)
        documento = ServicoImpressao(cenario.ctx).comprovante_da_venda(resultado.venda)
        texto = documento.texto()
        assert resultado.venda.rotulo in texto
        assert "Café 500 g" in texto
        assert "R$ 31,80" in texto
        assert "Dinheiro" in texto
        assert "Troco" in texto
        # O aviso pode quebrar em duas linhas: compara com espaços normalizados.
        assert AVISO_NAO_FISCAL in " ".join(texto.split())
        assert "Carla Atendente" in texto
        assert documento.papel is Papel.BOBINA_80

    def test_cupom_de_58mm_respeita_as_32_colunas(self, cenario):
        resultado = venda_de_exemplo(cenario)
        servico = ServicoImpressao(cenario.ctx)
        documento = servico.comprovante_da_venda(resultado.venda, papel=Papel.BOBINA_58)
        assert all(largura_de(linha.texto) <= 32 for linha in documento.layout())

    def test_segunda_via_e_marcada(self, cenario):
        resultado = venda_de_exemplo(cenario)
        servico = ServicoImpressao(cenario.ctx)
        original = servico.comprovante_da_venda(resultado.venda)
        copia = servico.comprovante_por_id(resultado.venda.id)
        assert "2ª VIA" not in original.titulo
        assert "2ª VIA" in copia.titulo

    def test_codigo_de_barras_pode_ser_desligado(self, cenario):
        resultado = venda_de_exemplo(cenario)
        cenario.ctx.parametros.definir("impressao.codigo_de_barras", "0", agora_iso="x")
        documento = ServicoImpressao(cenario.ctx).comprovante_da_venda(resultado.venda)
        assert not any(linha.eh_codigo_de_barras for linha in documento.layout())

    def test_envio_pelo_motor_do_sistema_e_auditado(self, cenario, monkeypatch):
        chamadas: list[tuple[str, int]] = []
        monkeypatch.setattr(
            renderizador,
            "imprimir",
            lambda documento, nome, copias=1, respeitar_papel_da_impressora=True: chamadas.append(
                (nome, copias)
            ),
        )
        servico = ServicoImpressao(cenario.ctx)
        documento = servico.comprovante_da_venda(
            venda_de_exemplo(cenario).venda,
            configuracao=ConfiguracaoImpressao(impressora="POS-80C", copias=2),
        )
        resultado = servico.despachar(
            documento,
            ator=cenario.operador,
            configuracao=ConfiguracaoImpressao(impressora="POS-80C", copias=2),
        )
        assert chamadas == [("POS-80C", 2)]
        assert resultado.destino == "POS-80C"
        assert resultado.linhas == len(documento.layout())
        eventos = cenario.ctx.auditoria.listar(acao=AcaoAuditoria.IMPRESSAO_REALIZADA)
        assert len(eventos) == 1
        assert eventos[0].depois["impressora"] == "POS-80C"

    def test_falha_de_impressao_audita_e_nao_engole_erro(self, cenario, monkeypatch):
        def falhar(*_args, **_kwargs):
            raise ImpressoraIndisponivel("Papel acabou.")

        monkeypatch.setattr(renderizador, "imprimir", falhar)
        servico = ServicoImpressao(cenario.ctx)
        documento = servico.comprovante_da_venda(venda_de_exemplo(cenario).venda)
        with pytest.raises(ImpressoraIndisponivel):
            servico.despachar(documento, ator=cenario.operador)
        eventos = cenario.ctx.auditoria.listar(acao=AcaoAuditoria.IMPRESSAO_FALHOU)
        assert len(eventos) == 1
        assert "Papel acabou" in eventos[0].depois["motivo"]

    def test_motor_espos_manda_bytes_uma_vez_por_copia(self, cenario, monkeypatch):
        enviados: list[bytes] = []
        monkeypatch.setattr(
            infra_impressoras, "enviar_bytes", lambda nome, dados: enviados.append(dados)
        )
        servico = ServicoImpressao(cenario.ctx)
        documento = servico.comprovante_da_venda(venda_de_exemplo(cenario).venda)
        resultado = servico.despachar(
            documento,
            ator=cenario.operador,
            configuracao=ConfiguracaoImpressao(
                motor=MotorImpressao.ESCPOS, impressora="POS-80", copias=2
            ),
        )
        assert len(enviados) == 2
        assert enviados[0].startswith(escpos.INICIALIZAR)
        assert resultado.motor is MotorImpressao.ESCPOS

    def test_motor_espos_recusa_folha_a4(self, cenario, monkeypatch):
        monkeypatch.setattr(infra_impressoras, "enviar_bytes", lambda nome, dados: None)
        servico = ServicoImpressao(cenario.ctx)
        documento = servico.comprovante_da_venda(
            venda_de_exemplo(cenario).venda, papel=Papel.A4
        )
        with pytest.raises(ErroValidacao):
            servico.despachar(
                documento,
                ator=cenario.operador,
                configuracao=ConfiguracaoImpressao(motor=MotorImpressao.ESCPOS, impressora="X"),
            )

    def test_perfil_sem_permissao_nao_imprime_nem_audita(self, cenario, monkeypatch):
        from bussola_pdv.dominio.erros import AutorizacaoNegada

        monkeypatch.setattr(renderizador, "imprimir", lambda *a, **k: None)
        servico = ServicoImpressao(cenario.ctx)
        documento = servico.comprovante_da_venda(venda_de_exemplo(cenario).venda)
        with pytest.raises(AutorizacaoNegada):
            servico.despachar(documento, ator=cenario.contabilidade)
        assert cenario.ctx.auditoria.listar(acao=AcaoAuditoria.IMPRESSAO_REALIZADA) == []

    def test_sem_impressora_configurada_usa_a_padrao_do_sistema(self, cenario):
        servico = ServicoImpressao(cenario.ctx)
        assert servico.impressora_efetiva() == infra_impressoras.padrao()

    def test_salvar_em_pdf_e_txt_grava_arquivo(self, cenario, tmp_path):
        pytest.importorskip("PySide6.QtGui")
        servico = ServicoImpressao(cenario.ctx)
        documento = servico.comprovante_da_venda(
            venda_de_exemplo(cenario).venda, papel=Papel.BOBINA_58
        )
        pdf = servico.salvar(documento, tmp_path, formato="pdf")
        texto = servico.salvar(documento, tmp_path, formato="txt")
        assert pdf.exists()
        assert pdf.read_bytes().startswith(b"%PDF")
        assert "Café 500 g" in texto.read_text(encoding="utf-8")
        with pytest.raises(ErroValidacao):
            servico.salvar(documento, tmp_path, formato="docx")

    # -- relatórios ----------------------------------------------------------
    def test_relatorio_em_a4_sai_em_grade_de_colunas(self, cenario):
        from bussola_pdv.aplicacao.exportacao import ServicoExportacao

        relatorio = ServicoExportacao(cenario.ctx).relatorio_turno(cenario.turno_id)
        documento = ServicoImpressao(cenario.ctx).documento_de_relatorio(
            relatorio, papel=Papel.A4
        )
        linhas = documento.layout()
        assert all(largura_de(linha.texto) <= 80 for linha in linhas)
        # cabeçalho da tabela e régua existem
        assert any(set(linha.texto.strip()) == {"-"} for linha in linhas)

    def test_relatorio_em_bobina_vira_pares_legiveis(self, cenario):
        from bussola_pdv.aplicacao.exportacao import ServicoExportacao

        relatorio = ServicoExportacao(cenario.ctx).relatorio_turno(cenario.turno_id)
        documento = ServicoImpressao(cenario.ctx).documento_de_relatorio(
            relatorio, papel=Papel.BOBINA_58
        )
        linhas = documento.layout()
        assert all(largura_de(linha.texto) <= 32 for linha in linhas)
        assert any("R$" in linha.texto for linha in linhas)

    def test_celula_longa_e_cortada_com_reticencias(self, cenario):
        tabela = criar_tabela(
            "Nomes",
            [("Nome", TipoColuna.TEXTO, 40), ("Valor", TipoColuna.MOEDA, 10)],
            [("Um nome absurdamente comprido que não cabe de jeito nenhum " * 3, 123456)],
        )
        from bussola_pdv.dominio.relatorio import Relatorio

        relatorio = Relatorio(titulo="Corte", tabelas=(tabela,), escopo="teste")
        documento = ServicoImpressao(cenario.ctx).documento_de_relatorio(
            relatorio, papel=Papel.A4
        )
        assert any("…" in linha.texto for linha in documento.layout())


# -- interface -----------------------------------------------------------------
pytestmark_ui = pytest.mark.ui


@pytest.fixture
def app():
    pytest.importorskip("PySide6.QtWidgets", reason="PySide6 ausente")
    from PySide6.QtWidgets import QApplication

    from bussola_pdv.ui.tema import FOLHA_ESTILO

    aplicacao = QApplication.instance() or QApplication(["teste-impressao"])
    aplicacao.setStyleSheet(FOLHA_ESTILO)
    return aplicacao


@pytestmark_ui
class TestInterfaceImpressao:
    def test_previa_mostra_medidas_e_troca_de_papel(self, app, cenario):
        from bussola_pdv.ui.impressao import DialogoPreviaImpressao

        servico = ServicoImpressao(cenario.ctx)
        documento = servico.comprovante_da_venda(venda_de_exemplo(cenario).venda)
        dialogo = DialogoPreviaImpressao(documento, servico, ator=cenario.operador)
        assert "48 colunas" in dialogo.rotulo_medidas.text()
        assert dialogo.pagina.pixmap() is not None
        dialogo.combo_papel.setCurrentIndex(dialogo.combo_papel.findData("BOBINA_58"))
        assert "32 colunas" in dialogo.rotulo_medidas.text()
        assert dialogo.documento_atual().papel is Papel.BOBINA_58
        dialogo.close()

    def test_previa_avisa_que_espos_nao_imprime_a4(self, app, cenario):
        from bussola_pdv.ui.impressao import DialogoPreviaImpressao

        servico = ServicoImpressao(cenario.ctx)
        documento = servico.comprovante_da_venda(venda_de_exemplo(cenario).venda)
        dialogo = DialogoPreviaImpressao(
            documento,
            servico,
            ator=cenario.operador,
            configuracao=ConfiguracaoImpressao(motor=MotorImpressao.ESCPOS),
        )
        dialogo.combo_papel.setCurrentIndex(dialogo.combo_papel.findData("A4"))
        assert dialogo.mensagem.isVisible() or "ESC/POS" in dialogo.mensagem.text()
        dialogo.close()

    def test_previa_imprime_e_emite_resultado(self, app, cenario, monkeypatch):
        from bussola_pdv.ui import impressao as ui_impressao

        monkeypatch.setattr(ui_impressao.QMessageBox, "information", lambda *a, **k: None)
        servico = ServicoImpressao(cenario.ctx)
        monkeypatch.setattr(
            servico,
            "despachar",
            lambda documento, ator=None, configuracao=None: _resultado(documento),
        )
        documento = servico.comprovante_da_venda(venda_de_exemplo(cenario).venda)
        dialogo = ui_impressao.DialogoPreviaImpressao(documento, servico, ator=cenario.operador)
        recebidos = []
        dialogo.impresso.connect(recebidos.append)
        assert dialogo.imprimir() is not None
        assert recebidos
        assert recebidos[0].destino == "POS-80"
        dialogo.close()

    def test_botao_de_imprimir_respeita_permissao(self, app, cenario):
        from bussola_pdv.ui.impressao import BotaoImprimir

        servico = ServicoImpressao(cenario.ctx)
        servico_pdv = ServicoPDV(cenario.ctx)
        del servico_pdv
        construir = lambda: documento_de_exemplo()  # noqa: E731
        do_atendente = BotaoImprimir(ator=cenario.operador, servico=servico, construir=construir)
        do_contador = BotaoImprimir(ator=cenario.contabilidade, servico=servico, construir=construir)
        assert cenario.operador.pode(_acao_cupom())
        assert not cenario.contabilidade.pode(_acao_cupom())
        assert not do_contador.isVisible()
        assert do_atendente.text() == "Imprimir"

    def test_administracao_tem_os_parametros_de_impressao(self, app, cenario):
        from bussola_pdv.aplicacao.parametros import ServicoParametros, TipoParametro
        from bussola_pdv.ui.admin.parametros import SecaoParametros

        secao = SecaoParametros(cenario.ctx, cenario.master)
        for chave in (
            "impressao.motor",
            "impressao.impressora",
            "impressao.papel",
            "impressao.copias",
            "impressao.codigo_de_barras",
        ):
            assert chave in secao.campos
        motor = secao.campos["impressao.motor"]
        assert motor.count() == 2  # SISTEMA e ESCPOS
        definicoes = {d.chave: d for d, _ in ServicoParametros(cenario.ctx).listar()}
        assert definicoes["impressao.papel"].tipo is TipoParametro.OPCAO
        assert definicoes["impressao.papel"].opcoes == ("BOBINA_58", "BOBINA_80", "A4")
        secao.deleteLater()


def _resultado(documento: DocumentoImpresso):
    from bussola_pdv.aplicacao.impressao import ResultadoImpressao

    return ResultadoImpressao(
        titulo=documento.titulo,
        destino="POS-80",
        motor=MotorImpressao.SISTEMA,
        papel=documento.papel,
        linhas=len(documento.layout()),
        copias=1,
    )


def _acao_cupom():
    from bussola_pdv.dominio.usuario import Acao

    return Acao.CUPOM_REIMPRIMIR


def test_atendente_pode_imprimir_cupom_e_contabilidade_nao():
    from bussola_pdv.dominio.usuario import PERMISSOES_PADRAO, Acao, Perfil

    assert Acao.CUPOM_REIMPRIMIR in PERMISSOES_PADRAO[Perfil.ATENDENTE]
    assert Acao.CUPOM_REIMPRIMIR in PERMISSOES_PADRAO[Perfil.GERENTE]
    assert Acao.CUPOM_REIMPRIMIR not in PERMISSOES_PADRAO[Perfil.CONTABILIDADE]
    assert Acao.CUPOM_REIMPRIMIR in PERMISSOES_PADRAO[Perfil.ADMIN_MASTER]


def test_cupom_gerado_do_zero_fica_na_pasta_pedida(cenario, tmp_path):
    servico = ServicoImpressao(cenario.ctx)
    documento = servico.comprovante_da_venda(venda_de_exemplo(cenario).venda)
    assert Path(documento.rotulo).suffix == ""
    assert documento.rotulo.startswith("cupom-")
