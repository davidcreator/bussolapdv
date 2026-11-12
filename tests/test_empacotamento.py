"""Testes do que dá para verificar sem Windows: caminhos, ícone e receita de build.

O `.exe` em si não é gerado nem testado aqui — só em runner `windows-latest`. O
que estes testes garantem é que a receita versionada não apodrece em silêncio:
a versão do metadado do executável bate com o pacote, o `.ico` é um ICO válido e
o spec/instalador continuam apontando para arquivos que existem.
"""

from __future__ import annotations

import ast
import re
import struct
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
EMPACOTAMENTO = RAIZ / "empacotamento"


def test_versao_do_exe_bate_com_o_pacote():
    from bussola_pdv import __version__

    texto = (EMPACOTAMENTO / "versao_info.txt").read_text(encoding="utf-8")
    assert f'StringStruct("FileVersion", "{__version__}")' in texto
    assert f'StringStruct("ProductVersion", "{__version__}")' in texto
    maior, menor, correcao = (int(p) for p in __version__.split(".")[:3])
    assert f"filevers=({maior}, {menor}, {correcao}, 0)" in texto

    pyproject = (RAIZ / "pyproject.toml").read_text(encoding="utf-8")
    assert f'version = "{__version__}"' in pyproject


def test_versao_do_instalador_bate_com_o_pacote():
    from bussola_pdv import __version__

    texto = (EMPACOTAMENTO / "instalador.iss").read_text(encoding="utf-8")
    assert f'#define AppVersion "{__version__}"' in texto


def test_icone_e_um_ico_multirresolucao_valido():
    dados = (EMPACOTAMENTO / "bussola.ico").read_bytes()
    reservado, tipo, quantidade = struct.unpack("<HHH", dados[:6])
    assert (reservado, tipo) == (0, 1)
    assert quantidade >= 5
    tamanhos = []
    for indice in range(quantidade):
        inicio = 6 + 16 * indice
        largura, altura, _, _, planos, bits, tamanho, deslocamento = struct.unpack(
            "<BBBBHHII", dados[inicio : inicio + 16]
        )
        assert (planos, bits) == (1, 32)
        assert dados[deslocamento : deslocamento + 8] == b"\x89PNG\r\n\x1a\n"
        assert len(dados[deslocamento : deslocamento + tamanho]) == tamanho
        tamanhos.append(largura or 256)
        assert (altura or 256) == (largura or 256)
    assert max(tamanhos) == 256


def test_spec_aponta_para_entrada_e_icone_existentes():
    from bussola_pdv import __version__

    texto = (EMPACOTAMENTO / "bussola.spec").read_text(encoding="utf-8")
    assert "bussola_pdv.ui.primeiro_uso" in texto  # primeiro uso empacotado
    assert 'name="BussolaPDV"' in texto
    assert "console=False" in texto
    assert "console=True" in texto  # versão de diagnóstico
    assert (EMPACOTAMENTO / "entrada.py").is_file()
    assert (EMPACOTAMENTO / "bussola.ico").is_file()
    assert __version__ in (EMPACOTAMENTO / "versao_info.txt").read_text(encoding="utf-8")


def test_spec_carrega_as_migracoes_sql():
    """Regressão: sem os .sql no bundle o executável abre e não cria tabela nenhuma."""
    texto = (EMPACOTAMENTO / "bussola.spec").read_text(encoding="utf-8")
    assert "migracoes" in texto
    assert "bussola_pdv/infra/sqlite/migracoes" in texto
    sql = list((RAIZ / "src" / "bussola_pdv" / "infra" / "sqlite" / "migracoes").glob("*.sql"))
    assert sql, "as migrações versionadas sumiram"


def test_diretorio_de_migracoes_e_o_que_o_spec_copia():
    """O spec copia o caminho que `migrador.DIR_MIGRACOES` lê em tempo de execução."""
    from bussola_pdv.infra.sqlite import migrador

    assert migrador.DIR_MIGRACOES == (
        RAIZ / "src" / "bussola_pdv" / "infra" / "sqlite" / "migracoes"
    )
    versoes = [versao for versao, _descricao, _arquivo in migrador.migracoes_disponiveis()]
    assert versoes == sorted(versoes)
    assert len(versoes) >= 3


def test_spec_leva_a_base_de_fusos_horarios():
    """Sem `tzdata` dentro do pacote o exe do Windows morre em `ZoneInfo`.

    O Windows não tem base IANA; `zoneinfo` lê o pacote PyPI. Foi o erro que
    impediu o primeiro uso de concluir (ZoneInfoNotFoundError: America/Sao_Paulo).
    """
    texto = (EMPACOTAMENTO / "bussola.spec").read_text(encoding="utf-8")
    assert "collect_data_files(\"tzdata\")" in texto
    assert '"tzdata",' in texto


def test_tzdata_e_dependencia_de_execucao():
    texto = (RAIZ / "pyproject.toml").read_text(encoding="utf-8")
    cabecalho = texto.split("[project.optional-dependencies]")[0]
    assert "tzdata" in cabecalho


def test_instalacao_windows_avisa_do_tzdata():
    texto = (RAIZ / "docs" / "INSTALACAO_WINDOWS.md").read_text(encoding="utf-8")
    assert "tzdata" in texto


def test_spec_e_python_valido():
    ast.parse((EMPACOTAMENTO / "bussola.spec").read_text(encoding="utf-8"))


def test_instalador_copia_arquivos_que_existem():
    texto = (EMPACOTAMENTO / "instalador.iss").read_text(encoding="utf-8")
    for nome in re.findall(r'Source: "([^"]+)"', texto):
        # Caminhos do .iss são relativos à pasta do script.
        relativo = Path(nome.replace("\\", "/"))
        if "dist" in relativo.parts:
            continue  # produzido pelo PyInstaller
        assert (EMPACOTAMENTO / relativo).resolve().exists(), nome


def test_instalador_nao_apaga_dados_do_usuario_na_desinstalacao():
    texto = (EMPACOTAMENTO / "instalador.iss").read_text(encoding="utf-8")
    secao = texto.split("[UninstallDelete]", 1)[1].split("[Code]", 1)[0]
    linhas = [linha for linha in secao.splitlines() if linha.strip().startswith("Type:")]
    assert linhas == []


def test_workflow_windows_publica_os_dois_artefatos():
    texto = (RAIZ / ".github" / "workflows" / "windows.yml").read_text(encoding="utf-8")
    assert "runs-on: windows-latest" in texto
    assert "BussolaPDV-*-win64.zip" in texto
    assert "BussolaPDV-*-setup.exe" in texto
    assert "innosetup" in texto


class TestCaminhos:
    def test_variavel_de_ambiente_manda(self, tmp_path, monkeypatch):
        from bussola_pdv import caminhos

        monkeypatch.setenv("BUSSOLA_DADOS", str(tmp_path / "minha-loja"))
        pasta = caminhos.diretorio_de_dados()
        assert pasta == tmp_path / "minha-loja"
        assert pasta.is_dir()
        assert caminhos.banco_padrao() == pasta / "pdv.db"
        assert caminhos.pasta_de_copias().is_dir()

    def test_localappdata_no_windows(self, tmp_path, monkeypatch):
        from bussola_pdv import caminhos

        monkeypatch.delenv("BUSSOLA_DADOS", raising=False)
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        assert caminhos.diretorio_de_dados() == tmp_path / "BussolaPDV"

    def test_windows_sem_localappdata_nao_quebra(self, monkeypatch):
        from bussola_pdv import caminhos

        monkeypatch.delenv("BUSSOLA_DADOS", raising=False)
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.delenv("LOCALAPPDATA", raising=False)
        monkeypatch.delenv("APPDATA", raising=False)
        monkeypatch.setenv("HOME", str(Path.home()))
        caminho = caminhos.diretorio_de_dados()
        assert caminho.name == "BussolaPDV"
        assert caminho.is_dir()

    def test_linux_usa_xdg(self, tmp_path, monkeypatch):
        from bussola_pdv import caminhos

        monkeypatch.delenv("BUSSOLA_DADOS", raising=False)
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        assert caminhos.diretorio_de_dados() == tmp_path / "bussola-pdv"


class TestEntrada:
    def test_argumento_devolve_controle_ao_cli(self, capsys):
        from bussola_pdv import __version__
        from bussola_pdv.ui import entrada

        with pytest.raises(SystemExit) as saida:
            entrada.main(["--version"])
        assert saida.value.code == 0
        assert __version__ in capsys.readouterr().out

    def test_modulo_executavel_existe(self):
        assert (RAIZ / "src" / "bussola_pdv" / "__main__.py").is_file()


@pytest.mark.parametrize("arquivo", ["AVISO.txt", "LEIA-ME.txt", "bussola.spec", "instalador.iss"])
def test_arquivos_de_empacotamento_versionados(arquivo):
    assert (EMPACOTAMENTO / arquivo).is_file()


def test_readme_documenta_o_caminho_windows():
    texto = (RAIZ / "README.md").read_text(encoding="utf-8")
    assert "INSTALACAO_WINDOWS.md" in texto
