"""Cópias de segurança: manifesto, rotação, recuperação e a ferramenta externa.

O pedido do usuário tem duas metades e os testes seguem essa divisão:

* **reinstalar sem perder dados** — `ServicoBackup.criar` grava a base e um
  manifesto legível, `automatico` cria uma por dia, `podar` mantém as N últimas;
* **backup com o programa quebrado** — `ferramentas/backup_externo.py` é
  executado como processo separado, sem `bussola_pdv` no `PYTHONPATH`, para provar
  que ele não depende do aplicativo.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from bussola_pdv.aplicacao.autenticacao import ServicoAutenticacao
from bussola_pdv.aplicacao.backup import (
    SUFIXO_MANIFESTO,
    ServicoBackup,
    inspecionar,
)
from bussola_pdv.aplicacao.contexto import Contexto
from bussola_pdv.dominio.erros import ErroNaoEncontrado, ErroValidacao
from bussola_pdv.dominio.usuario import Perfil

RAIZ = Path(__file__).resolve().parent.parent
EXTERNO = RAIZ / "ferramentas" / "backup_externo.py"


@pytest.fixture
def servico(cenario):
    return ServicoBackup(cenario.ctx)


class TestCriar:
    def test_copia_tem_manifesto_legivel(self, cenario, servico, tmp_path):
        copia = servico.criar(destino=tmp_path / "copias")
        assert copia.arquivo.is_file()
        assert copia.integro
        assert copia.bytes > 0
        manifesto = json.loads(copia.manifesto.read_text(encoding="utf-8"))
        assert manifesto["sha256"] == copia.sha256
        assert manifesto["versao_esquema"] == copia.versao_esquema
        assert manifesto["contagens"]["produtos"] >= 1
        # o manifesto precisa ser útil sozinho, sem o programa
        assert "pdv.db" in manifesto["como_restaurar"]

    def test_manifesto_guarda_a_versao_do_aplicativo(self, cenario, servico, tmp_path):
        from bussola_pdv import __version__

        copia = servico.criar(destino=tmp_path)
        manifesto = json.loads(copia.manifesto.read_text(encoding="utf-8"))
        assert manifesto["versao_aplicativo"] == __version__
        assert manifesto["formato"] == 1

    def test_duas_copias_no_mesmo_segundo_nao_se_sobrescrevem(self, cenario, servico, tmp_path):
        pasta = tmp_path / "copias"
        primeira = servico.criar(destino=pasta)
        segunda = servico.criar(destino=pasta)
        assert primeira.arquivo != segunda.arquivo
        assert len(list(pasta.glob("*.db"))) == 2

    def test_copia_de_base_em_memoria_e_recusada(self, cenario, tmp_path):
        contexto = Contexto.em_memoria(relogio=cenario.ctx.relogio)
        try:
            with pytest.raises(ErroValidacao):
                ServicoBackup(contexto).criar(destino=tmp_path)
        finally:
            contexto.fechar()


class TestListarEPodar:
    def test_lista_da_mais_nova_para_a_mais_antiga(self, cenario, servico, tmp_path):
        pasta = tmp_path / "copias"
        primeira = servico.criar(destino=pasta)
        cenario.ctx.relogio.avancar(seconds=5)
        segunda = servico.criar(destino=pasta)
        nomes = [c.nome for c in servico.listar(pasta)]
        assert nomes == [segunda.nome, primeira.nome]

    def test_rotacao_mantem_as_ultimas_e_preserva_as_manuais(self, cenario, servico, tmp_path):
        pasta = tmp_path / "copias"
        manual = servico.criar(rotulo="manual", destino=pasta)
        for _ in range(5):
            cenario.ctx.relogio.avancar(hours=1)
            servico.criar(rotulo="automática", destino=pasta, automatico=True)

        removidas = servico.podar(manter=2, destino=pasta)

        restantes = {c.nome for c in servico.listar(pasta)}
        assert len(removidas) == 3
        assert manual.nome in restantes  # manual nunca é apagada pelo programa
        assert len([n for n in restantes if n.startswith("pdv-")]) == 3  # manual + 2 automáticas

    def test_manter_zero_e_recusado(self, cenario, servico, tmp_path):
        with pytest.raises(ErroValidacao):
            servico.podar(manter=0, destino=tmp_path)


class TestAutomatico:
    def test_cria_uma_por_intervalo(self, cenario, servico, tmp_path):
        pasta = tmp_path / "copias"
        primeira = servico.automatico(destino=pasta)
        assert primeira is not None
        assert primeira.automatico
        assert servico.automatico(destino=pasta) is None  # mesmo dia

        cenario.ctx.relogio.avancar(hours=25)
        segunda = servico.automatico(destino=pasta)
        assert segunda is not None
        assert segunda.nome != primeira.nome

    def test_automatica_aparece_como_tal_na_listagem(self, cenario, servico, tmp_path):
        pasta = tmp_path / "copias"
        servico.automatico(destino=pasta)
        assert servico.ultima_automatica(pasta) is not None
        assert "automática" in servico.listar(pasta)[0].resumo()


class TestVerificar:
    def test_arquivo_que_nao_e_banco_e_reprovado(self, tmp_path):
        falso = tmp_path / "pdv-quebrado.db"
        falso.write_bytes(b"isto nao e sqlite")
        copia = inspecionar(falso)
        assert not copia.integro
        assert "SQLite válido" in copia.detalhe

    def test_arquivo_inexistente(self, tmp_path):
        with pytest.raises(ErroNaoEncontrado):
            inspecionar(tmp_path / "nao-existe.db")

    def test_copia_sem_tabelas_do_pdv_e_reprovada(self, tmp_path):
        vazio = tmp_path / "vazio.db"
        conexao = sqlite3.connect(vazio)
        conexao.execute("CREATE TABLE qualquer (x INTEGER)")
        conexao.commit()
        conexao.close()
        copia = inspecionar(vazio)
        assert not copia.integro
        assert "Faltam tabelas" in copia.detalhe


class TestRecuperar:
    def test_base_danificada_vira_base_nova_com_os_dados(self, cenario, servico, tmp_path):
        original = cenario.ctx.caminho
        assert original is not None
        produtos_antes = len(cenario.ctx.produtos.listar(apenas_ativos=False, limite=1000))
        copia_boa = servico.criar(destino=tmp_path / "copias")

        recuperado = servico.recuperar(copia_boa.arquivo, tmp_path / "recuperado.db")

        assert recuperado.integro
        assert recuperado.contagens["produtos"] == produtos_antes
        outra = Contexto.abrir(tmp_path / "recuperado.db")
        try:
            assert len(outra.produtos.listar(apenas_ativos=False, limite=1000)) == produtos_antes
        finally:
            outra.fechar()

    def test_arquivo_sem_nada_de_sqlite_e_recusado(self, cenario, servico, tmp_path):
        quebrado = tmp_path / "quebrado.db"
        quebrado.write_bytes(b"lixo" * 100)
        with pytest.raises(ErroValidacao):
            servico.recuperar(quebrado, tmp_path / "saida.db")
        assert not (tmp_path / "saida.db").exists()


class TestRestaurarArquivo:
    def test_restaura_e_guarda_a_base_anterior(self, cenario, tmp_path):
        ctx_copia = Contexto.abrir(tmp_path / "origem.db", relogio=cenario.ctx.relogio)
        try:
            ServicoAutenticacao(ctx_copia).criar_usuario(
                login="dono",
                nome="Dono",
                senha="Bussola#2026",
                perfil=Perfil.ADMIN_MASTER,
                criar_admin_inicial=True,
            )
            copia = ServicoBackup(ctx_copia).criar(destino=tmp_path / "copias")
        finally:
            ctx_copia.fechar()

        alvo = tmp_path / "alvo.db"
        ctx_alvo = Contexto.abrir(alvo, relogio=cenario.ctx.relogio)
        ServicoAutenticacao(ctx_alvo).criar_usuario(
            login="outro",
            nome="Outro",
            senha="Bussola#2026",
            perfil=Perfil.ADMIN_MASTER,
            criar_admin_inicial=True,
        )
        seguranca = ServicoBackup(ctx_alvo).restaurar_arquivo(copia.arquivo)

        assert seguranca.is_file()  # base anterior preservada
        restaurado = Contexto.abrir(alvo)
        try:
            assert [u.login for u in restaurado.usuarios.listar()] == ["dono"]
        finally:
            restaurado.fechar()


class TestFerramentaExterna:
    """`ferramentas/backup_externo.py` não pode depender do pacote instalado."""

    def _rodar(self, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
        ambiente = {
            "PATH": "/usr/bin:/bin:/usr/local/bin",
            "PYTHONPATH": "",  # de propósito: sem o pacote
            "PYTHONIOENCODING": "utf-8",
        }
        return subprocess.run(  # noqa: S603 - comando fixo, sem shell
            [sys.executable, str(EXTERNO), *args],
            capture_output=True,
            text=True,
            cwd=cwd,
            env=ambiente,
            timeout=120,
            check=False,
        )

    @pytest.fixture
    def pasta(self, cenario, tmp_path):
        """Pasta de dados com uma cópia *consistente* da base do cenário.

        `read_bytes()` do `.db` não serve: a base roda em WAL e o arquivo sozinho
        pode vir sem as últimas transações — foi assim que o teste antigo via
        "faltam tabelas". Cópia de arquivo aberto é justamente o que a API de
        backup do SQLite evita.
        """
        pasta = tmp_path / "dados"
        pasta.mkdir()
        origem = cenario.ctx.caminho
        assert origem is not None
        destino = sqlite3.connect(pasta / "pdv.db")
        try:
            cenario.ctx.conexao.backup(destino)
        finally:
            destino.close()
        return pasta

    def test_cria_copia_com_manifesto(self, pasta, tmp_path):
        resultado = self._rodar("criar", "--pasta", str(pasta), cwd=tmp_path)
        assert resultado.returncode == 0, resultado.stderr
        assert "Cópia criada" in resultado.stdout
        copias = list((pasta / "copias").glob("*.db"))
        assert len(copias) == 1
        manifesto = json.loads(
            copias[0].with_name(f"{copias[0].name}{SUFIXO_MANIFESTO}").read_text(encoding="utf-8")
        )
        assert manifesto["gerado_por"] == "ferramentas/backup_externo.py"
        assert manifesto["integro"] is True

    def test_lista_e_verifica(self, pasta, tmp_path):
        self._rodar("criar", "--pasta", str(pasta), cwd=tmp_path)
        listado = self._rodar("listar", "--pasta", str(pasta), cwd=tmp_path)
        assert "íntegra" in listado.stdout
        arquivo = next((pasta / "copias").glob("*.db"))
        verificado = self._rodar("verificar", str(arquivo), "--pasta", str(pasta), cwd=tmp_path)
        assert verificado.returncode == 0
        assert "Integridade: OK" in verificado.stdout

    def test_verificar_arquivo_quebrado_devolve_codigo_2(self, pasta, tmp_path):
        quebrado = pasta / "pdv-quebrado.db"
        quebrado.write_bytes(b"nao e sqlite")
        resultado = self._rodar("verificar", str(quebrado), "--pasta", str(pasta), cwd=tmp_path)
        assert resultado.returncode == 2
        assert "FALHA" in resultado.stdout

    def test_restaura_a_copia_sobre_a_base(self, pasta, tmp_path):
        self._rodar("criar", "--pasta", str(pasta), cwd=tmp_path)
        copia = next((pasta / "copias").glob("*.db"))
        antes = (pasta / "pdv.db").read_bytes()

        # a base atual é substituída por lixo: a cópia é a única saída
        (pasta / "pdv.db").write_bytes(b"base estragada")
        resultado = self._rodar("restaurar", str(copia), "--pasta", str(pasta), cwd=tmp_path)

        assert resultado.returncode == 0, resultado.stderr
        assert "Base anterior guardada" in resultado.stdout
        assert (pasta / "pdv.db").read_bytes() == antes
        assert list(pasta.glob("pdv.db.antes-de-restaurar-*"))

    def test_recupera_base_danificada(self, pasta, tmp_path):
        copia = pasta / "pdv.db"
        saudavel = copia.read_bytes()
        danificada = pasta / "danificada.db"
        danificada.write_bytes(b"lixo" * 200)  # não é SQLite: não há o que recuperar
        falha = self._rodar("recuperar", str(danificada), "--pasta", str(pasta), cwd=tmp_path)
        assert falha.returncode != 0
        assert "não pôde ser lida" in falha.stderr or "inutilizável" in falha.stderr

        ok = self._rodar("recuperar", str(copia), "--pasta", str(pasta), cwd=tmp_path)
        assert ok.returncode == 0, ok.stderr
        recuperado = pasta / "pdv-recuperado.db"
        assert recuperado.is_file()
        assert len(recuperado.read_bytes()) >= len(saudavel) // 2

    def test_sem_python_no_pc_o_bat_explica_o_que_fazer(self):
        """O `.bat` é a última linha de defesa de quem não tem Python instalado."""
        texto = (RAIZ / "ferramentas" / "backup_externo.bat").read_text(encoding="utf-8")
        assert "pdv.db" in texto
        assert "Python nao encontrado" in texto
        assert "LOCALAPPDATA" in texto
