"""Onde a instalação guarda dados: precedência, escolha da pasta e log de erros.

O que este arquivo prova:

* `BUSSOLA_DADOS` ganha de tudo, a pasta escolhida na instalação ganha do padrão,
  e o padrão continua sendo o do sistema quando ninguém escolheu nada;
* escolher uma pasta que não aceita escrita **falha na hora**, com mensagem — não
  na primeira venda;
* configuração corrompida não impede o programa de abrir;
* erro inesperado vai para `logs/erros.log` com traceback (é isso que faz o
  executável sem console parar de "não fazer nada").
"""

from __future__ import annotations

import json
import os
import sys

import pytest

from bussola_pdv import caminhos
from bussola_pdv.diagnostico import (
    arquivo_de_log,
    instalar_captura_de_erros,
    registrar_erro,
    resumo_do_erro,
)
from bussola_pdv.dominio.erros import ErroBussola


@pytest.fixture(autouse=True)
def ambiente_isolado(tmp_path, monkeypatch):
    """Nenhum teste toca a pasta real de dados/configuração da máquina."""
    monkeypatch.delenv("BUSSOLA_DADOS", raising=False)
    monkeypatch.setenv("BUSSOLA_CONFIG", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    return tmp_path


class TestPrecedencia:
    def test_sem_escolha_usa_padrao_do_sistema(self, ambiente_isolado):
        assert caminhos.origem_do_diretorio() == "padrao"
        assert caminhos.diretorio_de_dados() == caminhos.diretorio_de_dados_padrao()

    def test_pasta_escolhida_ganha_do_padrao(self, ambiente_isolado):
        escolhida = ambiente_isolado / "D_PDV"
        caminhos.definir_diretorio_de_dados(escolhida)
        assert caminhos.origem_do_diretorio() == "configuracao"
        assert caminhos.diretorio_de_dados() == escolhida.resolve()
        assert caminhos.banco_padrao() == escolhida.resolve() / "pdv.db"

    def test_variavel_de_ambiente_ganha_de_tudo(self, ambiente_isolado, monkeypatch):
        caminhos.definir_diretorio_de_dados(ambiente_isolado / "escolhida")
        altissima = ambiente_isolado / "ambiente"
        monkeypatch.setenv("BUSSOLA_DADOS", str(altissima))
        assert caminhos.origem_do_diretorio() == "BUSSOLA_DADOS"
        assert caminhos.diretorio_de_dados() == altissima

    def test_voltar_ao_padrao_apaga_a_escolha(self, ambiente_isolado):
        caminhos.definir_diretorio_de_dados(ambiente_isolado / "escolhida")
        caminhos.voltar_ao_diretorio_padrao()
        assert caminhos.origem_do_diretorio() == "padrao"

    def test_configuracao_corrompida_cai_no_padrao(self, ambiente_isolado):
        arquivo = caminhos.arquivo_de_configuracao()
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_text("{isto não é json", encoding="utf-8")
        assert caminhos.ler_configuracao() == {}
        assert caminhos.origem_do_diretorio() == "padrao"

    def test_configuracao_e_json_legivel(self, ambiente_isolado):
        escolhida = ambiente_isolado / "PDV"
        caminhos.definir_diretorio_de_dados(escolhida)
        dados = json.loads(caminhos.arquivo_de_configuracao().read_text(encoding="utf-8"))
        assert dados["dados"] == str(escolhida.resolve())
        # o ponteiro NÃO pode morar dentro da pasta de dados
        assert caminhos.diretorio_de_configuracao() != escolhida


class TestEscolhaDaPasta:
    def test_cria_a_pasta_escolhida(self, ambiente_isolado):
        nova = ambiente_isolado / "unidade_d" / "PDV"
        caminhos.definir_diretorio_de_dados(nova)
        assert nova.is_dir()

    def test_pasta_vazia_e_recusada(self):
        with pytest.raises(ErroBussola):
            caminhos.definir_diretorio_de_dados("   ")

    @pytest.mark.skipif(
        sys.platform.startswith("win") or os.geteuid() == 0,
        reason="root ignora permissão de pasta; no Windows o chmod é outro mecanismo",
    )
    def test_pasta_sem_permissao_de_escrita_falha_na_hora(self, ambiente_isolado):
        travada = ambiente_isolado / "travada"
        travada.mkdir()
        travada.chmod(0o500)
        try:
            with pytest.raises(ErroBussola, match="gravar"):
                caminhos.definir_diretorio_de_dados(travada / "PDV")
        finally:
            travada.chmod(0o700)

    def test_banco_em_usa_a_pasta_informada(self, ambiente_isolado):
        assert caminhos.banco_em(ambiente_isolado / "x") == ambiente_isolado / "x" / "pdv.db"

    def test_subpastas_acompanham_a_escolha(self, ambiente_isolado):
        escolhida = ambiente_isolado / "PDV"
        caminhos.definir_diretorio_de_dados(escolhida)
        for funcao in (
            caminhos.pasta_de_relatorios,
            caminhos.pasta_de_copias,
            caminhos.pasta_de_logs,
        ):
            assert funcao().parent == escolhida.resolve()
            assert funcao().is_dir()


class TestDiagnostico:
    def test_registrar_erro_grava_traceback(self, ambiente_isolado):
        try:
            raise OSError("unable to open database file")
        except OSError as exc:
            arquivo = registrar_erro(exc, contexto="teste de log")
        assert arquivo.exists()
        texto = arquivo.read_text(encoding="utf-8")
        assert "unable to open database file" in texto
        assert "OSError" in texto
        assert "teste de log" in texto

    def test_log_fica_na_pasta_de_dados(self, ambiente_isolado):
        caminhos.definir_diretorio_de_dados(ambiente_isolado / "PDV")
        assert arquivo_de_log().parent.parent == (ambiente_isolado / "PDV").resolve()

    def test_resumo_do_erro_e_uma_linha(self):
        assert resumo_do_erro(ValueError("linha 1\nlinha 2")) == "ValueError: linha 1"
        assert resumo_do_erro(ValueError()) == "ValueError"

    def test_rotacao_do_log(self, ambiente_isolado, monkeypatch):
        from bussola_pdv import diagnostico

        monkeypatch.setattr(diagnostico, "LIMITE_LOG_BYTES", 10)
        arquivo = arquivo_de_log()
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_text("x" * 50, encoding="utf-8")
        registrar_erro(ValueError("depois da rotação"))
        assert arquivo.with_suffix(".log.1").exists()
        assert "depois da rotação" in arquivo.read_text(encoding="utf-8")

    def test_hook_de_excecao_nao_tratada_registra_e_e_idempotente(
        self, ambiente_isolado, monkeypatch
    ):
        original = sys.excepthook
        try:
            instalar_captura_de_erros()
            primeiro = sys.excepthook
            instalar_captura_de_erros()
            assert sys.excepthook is primeiro  # não empilha hooks
            assert getattr(sys.excepthook, "_bussola", False) is True
            monkeypatch.setattr(
                "PySide6.QtWidgets.QApplication.instance", staticmethod(lambda: None)
            )
            try:
                raise RuntimeError("falha fora de try")
            except RuntimeError as exc:
                sys.excepthook(type(exc), exc, exc.__traceback__)
            assert "falha fora de try" in arquivo_de_log().read_text(encoding="utf-8")
        finally:
            sys.excepthook = original


class TestTelaDeManutencao:
    """A pasta de dados também é visível/trocável depois da instalação."""

    def test_secao_mostra_pasta_e_permite_trocar(self, cenario, ambiente_isolado, monkeypatch):
        from PySide6.QtWidgets import QApplication, QFileDialog

        from bussola_pdv.ui.admin.manutencao import SecaoManutencao

        QApplication.instance() or QApplication(["teste-pasta"])
        secao = SecaoManutencao(cenario.ctx, cenario.master)
        assert str(caminhos.diretorio_de_dados()) in secao.rotulo_dados.text()
        assert secao.botao_dados.isEnabled()

        nova = ambiente_isolado / "PDV_novo"
        monkeypatch.setattr(
            QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: str(nova))
        )
        secao._alterar_pasta_dados()

        assert caminhos.diretorio_de_dados() == nova.resolve()
        assert "PDV_novo" in secao.rotulo_dados.text() or "pasta nova" in secao.mensagem.text()
        eventos = [
            evento
            for evento in cenario.ctx.auditoria.listar(limite=20)
            if evento.entidade == "pasta_de_dados"
        ]
        assert eventos, "mudar a pasta de dados precisa deixar rastro na auditoria"
        secao.deleteLater()

    def test_nao_master_nao_altera_a_pasta(self, cenario, ambiente_isolado):
        from PySide6.QtWidgets import QApplication

        from bussola_pdv.ui.admin.manutencao import SecaoManutencao

        QApplication.instance() or QApplication(["teste-pasta"])
        secao = SecaoManutencao(cenario.ctx, cenario.gerente)
        assert not secao.botao_dados.isEnabled()
        assert "Admin Master" in secao.botao_dados.toolTip()
        secao.deleteLater()


class TestCliDados:
    def test_mostra_as_pastas_e_a_origem(self, ambiente_isolado, capsys):
        from bussola_pdv.cli import main as cli_main

        assert cli_main(["dados"]) == 0
        saida = capsys.readouterr().out
        assert "Pasta de dados:" in saida
        assert "Origem da escolha: padrao" in saida
        assert "pdv.db" in saida
        assert "erros.log" not in saida  # mostra a pasta de logs, não um arquivo inexistente

    def test_definir_pasta_e_mover_base(self, ambiente_isolado, capsys):
        from bussola_pdv.cli import main as cli_main

        antiga = ambiente_isolado / "padrao"
        cli_main(["demo", "--banco", str(antiga / "pdv.db")])
        (antiga / "copias").mkdir()
        (antiga / "copias" / "c1.db").write_bytes(b"copia ficticia")

        destino = ambiente_isolado / "D_PDV"
        codigo = cli_main(
            ["dados", "--definir", str(destino), "--mover", "--origem", str(antiga)]
        )
        saida = capsys.readouterr().out
        assert codigo == 0
        assert "Dados copiados" in saida
        assert (destino / "pdv.db").exists()
        assert (destino / "copias" / "c1.db").exists()
        assert (antiga / "pdv.db").exists()  # origem preservada
        assert caminhos.banco_padrao() == (destino / "pdv.db").resolve()

        # a cópia é uma base válida e com dados
        from bussola_pdv.aplicacao.contexto import Contexto

        contexto = Contexto.abrir(destino / "pdv.db")
        try:
            assert len(contexto.usuarios.listar()) >= 1
        finally:
            contexto.fechar()

    def test_definir_sem_mover_nao_copia(self, ambiente_isolado, capsys):
        from bussola_pdv.cli import main as cli_main

        destino = ambiente_isolado / "vazia"
        assert cli_main(["dados", "--definir", str(destino)]) == 0
        assert not (destino / "pdv.db").exists()
        assert "Origem da escolha: configuracao" in capsys.readouterr().out

    def test_padrao_descarta_a_escolha(self, ambiente_isolado, capsys):
        from bussola_pdv.cli import main as cli_main

        cli_main(["dados", "--definir", str(ambiente_isolado / "x")])
        assert cli_main(["dados", "--padrao"]) == 0
        assert "Origem da escolha: padrao" in capsys.readouterr().out

    def test_mover_da_pasta_inexistente_falha(self, ambiente_isolado, capsys):
        from bussola_pdv.cli import main as cli_main

        codigo = cli_main(
            [
                "dados",
                "--definir",
                str(ambiente_isolado / "y"),
                "--mover",
                "--origem",
                str(ambiente_isolado / "nao_existe"),
            ]
        )
        assert codigo == 2
        assert "não existe" in capsys.readouterr().err
