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
