"""Testes das receitas de pacote (Windows, Linux e macOS).

O binário de cada sistema só nasce no próprio sistema, então o que se pode provar
aqui é o que apodrece em silêncio: o script existe e é Python válido, o `.icns` do
macOS é um contêiner de verdade, o `.desktop` do Linux é um arquivo de entradas
legível, o `Instalar.sh` não usa sudo e não apaga dados, o `LEIA-ME` que vai dentro
do pacote não tem marcador esquecido, e o workflow matriz aponta para os runners
certos.
"""

from __future__ import annotations

import configparser
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
EMPACOTAMENTO = RAIZ / "empacotamento"
PACOTES = EMPACOTAMENTO / "pacotes"


def test_gerar_pacote_roda_em_todos_os_sistemas():
    """Um script só; o que muda é a plataforma, não a receita."""
    texto = (EMPACOTAMENTO / "gerar_pacote.py").read_text(encoding="utf-8")
    for funcao in ("empacotar_windows", "empacotar_linux", "empacotar_macos"):
        assert f"def {funcao}(" in texto, funcao
    assert '"windows": empacotar_windows' in texto
    assert '"linux": empacotar_linux' in texto
    assert '"macos": empacotar_macos' in texto


def test_gerar_pacote_avisa_que_nao_ha_compilacao_cruzada():
    """A limitação precisa estar escrita, não descoberta na hora de publicar."""
    texto = (EMPACOTAMENTO / "gerar_pacote.py").read_text(encoding="utf-8")
    assert "compilação cruzada" in texto
    assert "só nasce para o sistema" in texto


def test_gerar_pacote_lista_sem_construir():
    """`--lista` tem de ser seguro: nada de rodar PyInstaller só para ver o plano."""
    # Argumentos fixos, sem shell: é o próprio script do repositório sendo testado.
    resultado = subprocess.run(  # noqa: S603
        [sys.executable, str(EMPACOTAMENTO / "gerar_pacote.py"), "--lista"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert resultado.returncode == 0, resultado.stderr
    assert "Geraria" in resultado.stdout
    assert "Bússola PDV" in resultado.stdout


class TestIconeMacOS:
    def test_icns_e_um_continer_valido(self):
        """Cabeçalho `icns` + tamanho declarado igual ao real + blocos PNG."""
        dados = (EMPACOTAMENTO / "bussola.icns").read_bytes()
        assert dados[:4] == b"icns"
        assert struct.unpack(">I", dados[4:8])[0] == len(dados)
        tipos = []
        posicao = 8
        while posicao < len(dados):
            tipo = dados[posicao : posicao + 4].decode("ascii")
            tamanho = struct.unpack(">I", dados[posicao + 4 : posicao + 8])[0]
            assert tamanho >= 8
            assert dados[posicao + 8 : posicao + 12] == b"\x89PNG", tipo
            tipos.append(tipo)
            posicao += tamanho
        assert posicao == len(dados)
        assert {"ic07", "ic08", "ic09"} <= set(tipos)  # 128, 256 e 512 px

    def test_icns_vem_do_logo_oficial(self):
        """Nada de ícone desenhado: o arquivo é derivado de `logo_mini.png`."""
        texto = (EMPACOTAMENTO / "gerar_icone.py").read_text(encoding="utf-8")
        assert "def montar_icns(" in texto
        assert "bussola.icns" in texto
        # O arquivo é escrito byte a byte (struct), sem depender de `iconutil`,
        # que só existe no macOS — o gerador roda em qualquer sistema.
        assert 'destino.write_bytes(b"icns"' in texto


class TestPacoteLinux:
    def test_desktop_e_um_arquivo_de_entradas_valido(self):
        # `Desktop Entry` não tem seção `[Desktop Entry]` nomeada como o
        # configparser espera, mas o formato é INI — dá para ler.
        arquivo = PACOTES / "BussolaPDV.desktop"
        texto = arquivo.read_text(encoding="utf-8")
        assert texto.startswith("[Desktop Entry]")
        parser = configparser.ConfigParser(interpolation=None)
        parser.read_string(texto)
        entrada = parser["Desktop Entry"]
        assert entrada["Type"] == "Application"
        assert entrada["Name"] == "Bússola PDV"
        assert entrada["Terminal"] == "false"
        assert entrada["Icon"] == "bussolapdv"
        assert "Office" in entrada["Categories"]
        assert entrada["Exec"]  # o Instalar.sh reescreve com caminho absoluto

    def test_instalar_nao_pede_sudo_nem_apaga_dados(self):
        texto = (PACOTES / "Instalar.sh").read_text(encoding="utf-8")
        assert "sudo" not in texto.replace("sem sudo", "")
        assert "--remover" in texto
        assert "NÃO foram tocadas" in texto
        # O destino é do usuário, não do sistema.
        assert "$HOME/.local/opt" in texto
        # A base não pode morar dentro da pasta do programa.
        assert "pdv.db" not in texto

    def test_iniciar_roda_sem_instalar(self):
        texto = (PACOTES / "Iniciar.sh").read_text(encoding="utf-8")
        assert 'exec "$AQUI/BussolaPDV/BussolaPDV"' in texto

    @pytest.mark.parametrize("script", ["Instalar.sh", "Iniciar.sh", "Iniciar.command"])
    def test_scripts_de_shell_passam_no_syntax_check(self, script):
        """`sh -n` pega o erro que só apareceria na máquina do usuário."""
        resultado = subprocess.run(  # noqa: S603 - argumentos fixos, sem shell
            [shutil.which("sh") or "/bin/sh", "-n", str(PACOTES / script)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert resultado.returncode == 0, resultado.stderr

    @pytest.mark.parametrize("script", ["Instalar.sh", "Iniciar.sh", "Iniciar.command"])
    def test_scripts_chegam_executaveis_no_pacote(self, script):
        """Zip e tar não preservam modo: o bit tem de estar no arquivo versionado."""
        modo = (PACOTES / script).stat().st_mode
        assert modo & 0o111, f"{script} sem bit de execução"


def _sem_marcador(texto: str) -> bool:
    """`%LOCALAPPDATA%` é texto legítimo; marcador do modelo não pode sobrar."""
    return re.search(r"%(VERSAO|SISTEMA|COMO_[A-Z_]+|ONDE_FICAM_OS_DADOS)%", texto) is None


class TestMontagemDosPacotes:
    """Exercita o empacotamento de verdade, com um `dist/` falso.

    Vale a pena porque é aqui que se erra caminho dentro do zip/tar e texto do
    LEIA-ME — e nenhum desses passos precisa de PyInstaller para ser testado.
    """

    @pytest.fixture
    def montador(self, tmp_path, monkeypatch):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "gerar_pacote", EMPACOTAMENTO / "gerar_pacote.py"
        )
        assert spec is not None
        assert spec.loader is not None
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        monkeypatch.setattr(modulo, "DIST", tmp_path)
        return modulo

    def _programa_falso(self, modulo, *, com_app=False):
        pasta = modulo.DIST / "BussolaPDV"
        pasta.mkdir(parents=True)
        (pasta / "BussolaPDV").write_text("#!/bin/sh\n", encoding="utf-8")
        (pasta / "BussolaPDV.exe").write_text("MZ", encoding="utf-8")
        if com_app:
            macos = modulo.DIST / "BussolaPDV.app" / "Contents" / "MacOS"
            macos.mkdir(parents=True)
            (macos / "BussolaPDV").write_text("#!/bin/sh\n", encoding="utf-8")
        return pasta

    def test_windows_gera_zip_que_abre_sem_instalar(self, montador):
        pasta = self._programa_falso(montador)
        gerados = montador.empacotar_windows(pasta)
        zip_gerado = next(caminho for caminho in gerados if caminho.suffix == ".zip")
        assert zip_gerado.name.endswith("-win64.zip")

        import zipfile

        with zipfile.ZipFile(zip_gerado) as arquivo:
            nomes = arquivo.namelist()
            assert any(nome.endswith("BussolaPDV.exe") for nome in nomes)
            leia_me = arquivo.read(
                next(nome for nome in nomes if nome.endswith("LEIA-ME.txt"))
            ).decode("utf-8")
        assert _sem_marcador(leia_me)
        assert "LOCALAPPDATA" in leia_me
        assert "SmartScreen" in leia_me

    def test_linux_gera_tar_gz_com_instalador_executavel(self, montador):
        pasta = self._programa_falso(montador)
        gerados = montador.empacotar_linux(pasta)
        pacote = next(caminho for caminho in gerados if caminho.name.endswith(".tar.gz"))

        import tarfile

        with tarfile.open(pacote) as arquivo:
            membros = {membro.name.split("/")[-1]: membro for membro in arquivo.getmembers()}
            assert "Instalar.sh" in membros
            assert "Iniciar.sh" in membros
            assert "LEIA-ME.txt" in membros
            # Bit de execução preservado no arquivo empacotado.
            assert membros["Instalar.sh"].mode & 0o111
            leia_me = arquivo.extractfile(membros["LEIA-ME.txt"])
            assert leia_me is not None
            texto = leia_me.read().decode("utf-8")
        assert _sem_marcador(texto)
        assert "./Instalar.sh" in texto

    def test_macos_empacota_o_app(self, montador):
        self._programa_falso(montador, com_app=True)
        gerados = montador.empacotar_macos(montador.DIST / "BussolaPDV")
        pacote = next(caminho for caminho in gerados if caminho.suffix == ".zip")

        import zipfile

        with zipfile.ZipFile(pacote) as arquivo:
            nomes = arquivo.namelist()
            assert any("/BussolaPDV.app/Contents/MacOS/BussolaPDV" in nome for nome in nomes)
            assert any(nome.endswith("LEIA-ME.txt") for nome in nomes)
            assert any(nome.endswith("Iniciar.command") for nome in nomes)

    def test_macos_sem_app_falha_com_mensagem_clara(self, montador):
        pasta = self._programa_falso(montador)  # sem o .app
        with pytest.raises(SystemExit, match="não gerou"):
            montador.empacotar_macos(pasta)


class TestLeiaMe:
    def test_modelo_so_usa_marcadores_conhecidos(self):
        """Marcador com nome torto não é substituído e sai na cara do usuário."""
        modelo = (PACOTES / "LEIA-ME.txt").read_text(encoding="utf-8")
        encontrados = set(re.findall(r"%[A-Z_]+%", modelo))
        assert encontrados == {
            "%VERSAO%",
            "%SISTEMA%",
            "%COMO_INSTALAR%",
            "%COMO_RODAR%",
            "%COMO_REMOVER%",
            "%ONDE_FICAM_OS_DADOS%",
        }
        # E o gerador substitui todos eles.
        gerador = (EMPACOTAMENTO / "gerar_pacote.py").read_text(encoding="utf-8")
        for marca in encontrados:
            assert f'"{marca}":' in gerador, marca

    def test_modelo_diz_onde_ficam_os_dados_e_como_remover(self):
        modelo = (PACOTES / "LEIA-ME.txt").read_text(encoding="utf-8")
        assert "ONDE FICAM SEUS DADOS" in modelo
        assert "DESINSTALAR" in modelo
        assert "NUNCA fica dentro da pasta do programa" in modelo


class TestSpec:
    def test_bundle_do_macos_so_existe_no_macos(self):
        texto = (EMPACOTAMENTO / "bussola.spec").read_text(encoding="utf-8")
        assert 'if sys.platform == "darwin":' in texto
        assert "BUNDLE(" in texto
        assert "bussola.icns" in texto
        assert "BussolaPDV.app" in texto
        # O Info.plist precisa de versão e de identificador de bundle.
        assert "CFBundleShortVersionString" in texto
        assert "bundle_identifier" in texto

    def test_spec_sai_com_icone_das_tres_plataformas(self):
        assert (EMPACOTAMENTO / "bussola.ico").is_file()
        assert (EMPACOTAMENTO / "bussola.icns").is_file()
        assert (EMPACOTAMENTO / "bussola.png").is_file()


class TestWorkflowDosPacotes:
    def test_matriz_cobre_linux_e_macos(self):
        texto = (RAIZ / ".github" / "workflows" / "pacotes.yml").read_text(encoding="utf-8")
        assert "ubuntu-latest" in texto
        assert "macos-latest" in texto
        assert "python empacotamento/gerar_pacote.py" in texto
        # O .exe continua no windows.yml, que também gera o Inno Setup.
        assert "windows-latest" not in texto

    def test_workflow_nao_publica_release_sozinho(self):
        texto = (RAIZ / ".github" / "workflows" / "pacotes.yml").read_text(encoding="utf-8")
        assert "upload-artifact" in texto
        assert "gh release" not in texto
        assert "softprops/action-gh-release" not in texto

    def test_workflow_tem_teste_de_fumaca(self):
        """Artefato que sobe quebrado é pior do que artefato nenhum."""
        texto = (RAIZ / ".github" / "workflows" / "pacotes.yml").read_text(encoding="utf-8")
        assert "--version" in texto
        assert "O binário não respondeu" in texto


class TestDocumentacao:
    def test_pacotes_md_explica_a_regra_da_compilacao_cruzada(self):
        texto = (RAIZ / "docs" / "PACOTES.md").read_text(encoding="utf-8")
        assert "compilação cruzada" in texto
        assert "Windows" in texto
        assert "Linux" in texto
        assert "macOS" in texto

    def test_pacotes_md_tem_o_passo_a_passo_manual_dos_tres(self):
        texto = (RAIZ / "docs" / "PACOTES.md").read_text(encoding="utf-8")
        for comando in (
            "python -m PyInstaller --noconfirm --clean empacotamento/bussola.spec",
            "ISCC.exe",
            "hdiutil",
            "Instalar.sh",
        ):
            assert comando in texto, comando

    def test_pacotes_md_separa_o_verificado_do_nao_verificado(self):
        """A mesma regra do resto do projeto: não afirmar o que não foi rodado."""
        texto = (RAIZ / "docs" / "PACOTES.md").read_text(encoding="utf-8")
        assert "Não verificado" in texto
        assert ".dmg" in texto

    def test_readme_aponta_para_o_documento_de_pacotes(self):
        texto = (RAIZ / "README.md").read_text(encoding="utf-8")
        assert "docs/PACOTES.md" in texto
