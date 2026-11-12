"""Primeiro uso: a instalação nasce pela tela, sem terminal.

O que importa aqui: (1) o diálogo cria o Admin Master usando os mesmos casos de
uso do `init`, (2) grava o nome da loja e o caixa, (3) recusa dados inválidos sem
deixar base pela metade e (4) `precisa_de_configuracao` distingue base nova, base
vazia e base pronta.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError, reason="Qt ausente")

from bussola_pdv.aplicacao.contexto import Contexto
from bussola_pdv.aplicacao.marca import ServicoMarca
from bussola_pdv.dominio.usuario import Perfil
from bussola_pdv.ui.primeiro_uso import DialogoPrimeiroUso, precisa_de_configuracao

pytestmark = pytest.mark.ui


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication(["teste-primeiro-uso"])


def _preencher(dialogo: DialogoPrimeiroUso, *, senha2: str | None = None) -> None:
    dialogo.campo_loja.setText("Mercadinho Bússola")
    dialogo.campo_login.setText("master")
    dialogo.campo_nome.setText("Maria Souza")
    dialogo.campo_senha.setText("Bussola#2026")
    dialogo.campo_senha2.setText(senha2 if senha2 is not None else "Bussola#2026")


class TestDeteccao:
    def test_banco_ausente_pede_configuracao(self, tmp_path):
        assert precisa_de_configuracao(tmp_path / "nao_existe.db") is True

    def test_banco_recem_criado_sem_usuario_pede_configuracao(self, tmp_path):
        caminho = tmp_path / "vazio.db"
        Contexto.abrir(caminho).fechar()
        assert precisa_de_configuracao(caminho) is True

    def test_banco_com_usuario_dispensa_configuracao(self, tmp_path):
        from bussola_pdv.aplicacao.autenticacao import ServicoAutenticacao

        caminho = tmp_path / "pronto.db"
        ctx = Contexto.abrir(caminho)
        ServicoAutenticacao(ctx).criar_usuario(
            login="chefe",
            nome="Chefe",
            senha="Bussola#2026",
            perfil=Perfil.ADMIN_MASTER,
            criar_admin_inicial=True,
        )
        ctx.fechar()
        assert precisa_de_configuracao(caminho) is False

    def test_arquivo_corrompido_nao_impede_o_usuario_de_tentar(self, tmp_path):
        caminho = tmp_path / "lixo.db"
        caminho.write_bytes(b"isto nao e um banco sqlite")
        assert precisa_de_configuracao(caminho) is True


class TestDialogo:
    def test_cria_master_caixa_e_nome_da_loja(self, app, tmp_path):
        banco = tmp_path / "dados" / "pdv.db"
        dialogo = DialogoPrimeiroUso(banco)
        _preencher(dialogo)
        dialogo._criar()

        assert dialogo.result() == DialogoPrimeiroUso.DialogCode.Accepted
        assert dialogo.usuario is not None
        assert dialogo.usuario.perfil is Perfil.ADMIN_MASTER
        assert dialogo.usuario.login == "master"

        ctx = Contexto.abrir(banco)
        try:
            assert [u.login for u in ctx.usuarios.listar()] == ["master"]
            assert [c["nome"] for c in ctx.caixas.listar_caixas()] == ["Caixa 1"]
            assert ServicoMarca(ctx).obter().nome_fantasia == "Mercadinho Bússola"
        finally:
            ctx.fechar()
        dialogo.deleteLater()

    def test_senhas_diferentes_mostram_erro_e_nao_criam_base(self, app, tmp_path):
        banco = tmp_path / "pdv.db"
        dialogo = DialogoPrimeiroUso(banco)
        _preencher(dialogo, senha2="outra-coisa")
        dialogo._criar()

        assert dialogo.result() != DialogoPrimeiroUso.DialogCode.Accepted
        assert "não conferem" in dialogo.mensagem.text()
        assert not banco.exists()
        dialogo.deleteLater()

    @pytest.mark.parametrize(
        ("campo", "texto"),
        [("campo_loja", ""), ("campo_login", ""), ("campo_nome", "")],
    )
    def test_campo_obrigatorio_vazio(self, app, tmp_path, campo, texto):
        dialogo = DialogoPrimeiroUso(tmp_path / "pdv.db")
        _preencher(dialogo)
        getattr(dialogo, campo).setText(texto)
        dialogo._criar()

        assert dialogo.mensagem.text() != ""
        assert dialogo.result() != DialogoPrimeiroUso.DialogCode.Accepted
        dialogo.deleteLater()

    def test_senha_curta_e_recusada_pela_politica_do_dominio(self, app, tmp_path):
        banco = tmp_path / "pdv.db"
        dialogo = DialogoPrimeiroUso(banco)
        _preencher(dialogo)
        dialogo.campo_senha.setText("curta")
        dialogo.campo_senha2.setText("curta")
        dialogo._criar()

        assert dialogo.mensagem.text() != ""
        assert dialogo.result() != DialogoPrimeiroUso.DialogCode.Accepted
        dialogo.deleteLater()


# -- pasta dos dados e falhas visíveis (v0.6.1) ---------------------------------
@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    """Isola configuração e dados: escolher pasta não pode tocar a máquina real."""
    monkeypatch.delenv("BUSSOLA_DADOS", raising=False)
    monkeypatch.setenv("BUSSOLA_CONFIG", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    return tmp_path


class TestPastaDosDados:
    def test_campo_ja_vem_com_a_pasta_do_banco(self, app, tmp_path):
        dialogo = DialogoPrimeiroUso(tmp_path / "dados" / "pdv.db")
        assert dialogo.campo_pasta.text() == str(tmp_path / "dados")
        assert "pdv.db" in dialogo.caminho.text()
        dialogo.deleteLater()

    def test_escolher_outra_pasta_cria_a_base_la_e_grava_a_escolha(self, app, ambiente):
        from bussola_pdv import caminhos

        outra = ambiente / "outra_unidade" / "PDV"
        dialogo = DialogoPrimeiroUso(caminhos.banco_padrao())
        _preencher(dialogo)
        dialogo.campo_pasta.setText(str(outra))
        dialogo._criar()

        assert dialogo.result() == DialogoPrimeiroUso.DialogCode.Accepted
        assert (outra / "pdv.db").exists()
        assert caminhos.banco_padrao() == (outra / "pdv.db").resolve()
        assert caminhos.origem_do_diretorio() == "configuracao"
        dialogo.deleteLater()

    def test_pasta_vazia_e_recusada_com_mensagem(self, app, ambiente):
        from bussola_pdv import caminhos

        dialogo = DialogoPrimeiroUso(caminhos.banco_padrao())
        _preencher(dialogo)
        dialogo.campo_pasta.setText("   ")
        dialogo._criar()

        assert dialogo.result() != DialogoPrimeiroUso.DialogCode.Accepted
        assert "pasta" in dialogo.mensagem.text().lower()
        dialogo.deleteLater()

    def test_pasta_sem_permissao_mostra_erro_sem_criar_base(self, app, ambiente):
        import os
        import sys

        if sys.platform.startswith("win") or os.geteuid() == 0:
            pytest.skip("permissão de pasta é outro mecanismo nesta plataforma")
        travada = ambiente / "travada"
        travada.mkdir()
        travada.chmod(0o500)
        try:
            dialogo = DialogoPrimeiroUso(travada / "pdv.db")
            _preencher(dialogo)
            dialogo._criar()
            assert dialogo.result() != DialogoPrimeiroUso.DialogCode.Accepted
            assert "gravar" in dialogo.mensagem.text().lower()
            assert not (travada / "pdv.db").exists()
            dialogo.deleteLater()
        finally:
            travada.chmod(0o700)


class TestFalhaVisivel:
    """O bug relatado: exceção fora de `ErroBussola` deixava o botão "morto"."""

    def test_erro_inesperado_aparece_na_tela_e_no_log(self, app, ambiente, monkeypatch):
        from bussola_pdv.aplicacao import contexto as modulo_contexto
        from bussola_pdv.diagnostico import arquivo_de_log

        def explodir(*_args, **_kwargs):
            raise OSError(13, "unable to open database file")

        monkeypatch.setattr(modulo_contexto.Contexto, "abrir", staticmethod(explodir))
        banco = ambiente / "pdv.db"
        dialogo = DialogoPrimeiroUso(banco)
        _preencher(dialogo)
        dialogo.botao_criar.click()  # o clique do operador, não o método direto

        assert dialogo.result() != DialogoPrimeiroUso.DialogCode.Accepted
        texto = dialogo.mensagem.text()
        assert "unable to open database file" in texto
        assert "PermissionError" in texto or "OSError" in texto
        assert str(arquivo_de_log()) in texto
        assert "Traceback" in arquivo_de_log().read_text(encoding="utf-8")
        # o botão volta a funcionar depois da falha
        assert dialogo.botao_criar.isEnabled()
        assert dialogo.botao_criar.text() == "Criar instalação"
        dialogo.deleteLater()

    def test_base_sem_esquema_avisa_instalacao_incompleta(self, app, ambiente, monkeypatch):
        """Instalação incompleta (sem os .sql de migração) não pode parecer "nada acontece"."""
        import sqlite3

        from bussola_pdv.aplicacao import contexto as modulo_contexto

        banco = ambiente / "vazio.db"
        sqlite3.connect(banco).close()  # arquivo existe, sem schema nenhum
        monkeypatch.setattr(modulo_contexto, "migrar", lambda *_a, **_k: [])

        dialogo = DialogoPrimeiroUso(banco)
        _preencher(dialogo)
        dialogo._criar()
        assert dialogo.result() != DialogoPrimeiroUso.DialogCode.Accepted
        assert "esquema" in dialogo.mensagem.text().lower()
        dialogo.deleteLater()

    def test_botao_mostra_estado_ocupado(self, app, ambiente, monkeypatch):
        """Argon2 leva ~1 s; sem rótulo de progresso o clique parece não funcionar."""
        from bussola_pdv.ui import primeiro_uso as modulo

        vistos: list[str] = []
        original = modulo.DialogoPrimeiroUso._ocupado

        def espiao(self, estado):
            original(self, estado)
            vistos.append(self.botao_criar.text())

        monkeypatch.setattr(modulo.DialogoPrimeiroUso, "_ocupado", espiao)
        dialogo = DialogoPrimeiroUso(ambiente / "pdv.db")
        _preencher(dialogo)
        dialogo._criar()
        assert "Criando instalação…" in vistos
        assert vistos[-1] == "Criar instalação"
        dialogo.deleteLater()


class TestEntradaDoApp:
    def test_usa_a_base_nova_depois_de_escolher_a_pasta(self, ambiente, monkeypatch):
        """`entrada.main` recalculava o banco antes do diálogo e ignorava a escolha."""
        from bussola_pdv import caminhos
        from bussola_pdv.ui import app as modulo_app
        from bussola_pdv.ui import entrada, primeiro_uso

        escolhida = ambiente / "PDV_escolhido"
        caminhos.definir_diretorio_de_dados(escolhida)

        monkeypatch.setattr(primeiro_uso, "precisa_de_configuracao", lambda caminho: True)

        class DialogoFalso:
            DialogCode = type("DialogCode", (), {"Accepted": 1})
            result = 1

            def __init__(self, *_args, **_kwargs):
                pass

            def exec(self):
                return 1

        abertos: list = []
        monkeypatch.setattr(primeiro_uso, "DialogoPrimeiroUso", DialogoFalso)
        monkeypatch.setattr(modulo_app, "criar_aplicacao", lambda: None)
        monkeypatch.setattr(modulo_app, "executar", lambda banco: abertos.append(banco) or 0)
        monkeypatch.setattr(
            "bussola_pdv.diagnostico.instalar_captura_de_erros", lambda: None
        )

        assert entrada.main([]) == 0
        assert abertos == [escolhida / "pdv.db"]


class TestRecomeco:
    def test_base_corrompida_e_guardada_de_lado_e_instalacao_recomeca(self, app, ambiente):
        """Quem morreu no meio da instalação não fica preso num pdv.db quebrado."""
        banco = ambiente / "pdv.db"
        banco.write_bytes(b"isto nao e um banco sqlite")

        dialogo = DialogoPrimeiroUso(banco)
        _preencher(dialogo)
        dialogo._criar()

        assert dialogo.result() == DialogoPrimeiroUso.DialogCode.Accepted
        antigos = list(ambiente.glob("pdv.db.antigo-*"))
        assert len(antigos) == 1
        assert antigos[0].read_bytes() == b"isto nao e um banco sqlite"
        assert "guardada como" in dialogo.mensagem.text()
        from bussola_pdv.aplicacao.contexto import Contexto

        contexto = Contexto.abrir(banco)
        try:
            assert [u.login for u in contexto.usuarios.listar()] == ["master"]
        finally:
            contexto.fechar()
        dialogo.deleteLater()

    def test_erro_que_nao_e_do_banco_nao_move_a_base(self, app, ambiente, monkeypatch):
        """O bug relatado: falha de fuso (ZoneInfo) era tratada como base corrompida.

        A base boa ia para `pdv.db.antigo-…` e a tela mostrava `WinError 32`
        (arquivo em uso) em vez do motivo real. Só `sqlite3.DatabaseError` e
        esquema ausente autorizam o recomeço.
        """
        from zoneinfo import ZoneInfoNotFoundError

        from bussola_pdv.aplicacao import contexto as modulo_contexto

        banco = ambiente / "pdv.db"
        banco.write_bytes(b"base boa, so o fuso quebrou")

        def explodir(*_args, **_kwargs):
            raise ZoneInfoNotFoundError("No time zone found with key America/Sao_Paulo")

        monkeypatch.setattr(modulo_contexto, "RelogioSistema", explodir)

        dialogo = DialogoPrimeiroUso(banco)
        _preencher(dialogo)
        dialogo._criar()

        assert dialogo.result() != DialogoPrimeiroUso.DialogCode.Accepted
        assert list(ambiente.glob("pdv.db.antigo-*")) == []
        assert banco.read_bytes() == b"base boa, so o fuso quebrou"
        texto = dialogo.mensagem.text()
        assert "America/Sao_Paulo" in texto
        assert "guardada como" not in texto
        dialogo.deleteLater()

    def test_base_presa_por_outro_processo_explica_o_que_fazer(self, app, ambiente, monkeypatch):
        """`WinError 32` cru não diz nada ao operador da loja."""
        from pathlib import Path as Caminho

        from bussola_pdv.ui import primeiro_uso as modulo

        banco = ambiente / "pdv.db"
        banco.write_bytes(b"isto nao e um banco sqlite")

        def sempre_preso(self, alvo):
            raise PermissionError(32, "O arquivo já está sendo usado por outro processo")

        monkeypatch.setattr(Caminho, "replace", sempre_preso)
        monkeypatch.setattr(modulo.time, "sleep", lambda _s: None)

        dialogo = DialogoPrimeiroUso(banco)
        _preencher(dialogo)
        dialogo._criar()

        texto = dialogo.mensagem.text()
        assert "outras janelas do Bússola PDV" in texto
        assert dialogo.result() != DialogoPrimeiroUso.DialogCode.Accepted
        dialogo.deleteLater()

    def test_base_valida_nao_e_tocada(self, app, ambiente):
        from bussola_pdv.aplicacao.autenticacao import ServicoAutenticacao
        from bussola_pdv.aplicacao.contexto import Contexto
        from bussola_pdv.dominio.usuario import Perfil

        banco = ambiente / "pdv.db"
        contexto = Contexto.abrir(banco)
        ServicoAutenticacao(contexto).criar_usuario(
            login="ja_existe",
            nome="Já Existe",
            senha="Bussola#2026",
            perfil=Perfil.ADMIN_MASTER,
            criar_admin_inicial=True,
        )
        contexto.fechar()

        dialogo = DialogoPrimeiroUso(banco)
        _preencher(dialogo)
        dialogo._criar()
        assert dialogo.result() != DialogoPrimeiroUso.DialogCode.Accepted
        assert list(ambiente.glob("pdv.db.antigo-*")) == []
        dialogo.deleteLater()
