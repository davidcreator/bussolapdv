"""Um comando, um pacote de instalação simples — no sistema em que você está.

Por que isto existe: montar pacote à mão (PyInstaller + zip + atalho + `.desktop`
ou `.dmg`) é onde se erra nome de arquivo, se esquece o logo e se publica pacote
que não abre. Aqui o caminho é um só, o nome do arquivo é previsível e o que vai
dentro dele é conferido antes de fechar:

    python empacotamento/gerar_pacote.py

Saída por sistema (em `dist/`):

========================  ==========================================================
Windows                   `BussolaPDV-<v>-win64.zip` (portátil, abre direto) e, se o
                          Inno Setup estiver instalado, `instalador/BussolaPDV-<v>-setup.exe`
Linux                     `BussolaPDV-<v>-linux-x86_64.tar.gz` com `Instalar.sh`,
                          `Iniciar.sh` e atalho de menu
macOS                     `BussolaPDV-<v>-macos.zip` com `BussolaPDV.app` e, se
                          `hdiutil` existir, `BussolaPDV-<v>-macos.dmg`
========================  ==========================================================

**O binário só nasce para o sistema em que o script roda.** PyInstaller não faz
compilação cruzada: `.exe` sai em Windows, `.app` sai em macOS e o binário Linux
sai em Linux. O script diz isso em vez de fingir — e é por isso que existem três
receitas no CI (`.github/workflows/windows.yml` para o `.exe`; este script para
os outros dois).

Opções:

    --sem-pyinstaller   reaproveita o `dist/` que já existe (iterar no empacote)
    --sem-teste         não roda a suíte antes de empacotar (não recomendado)
    --lista             só mostra o que faria, sem construir nada
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import time
import zipfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
DIST = RAIZ / "dist"
PACOTES = AQUI / "pacotes"
SPEC = AQUI / "bussola.spec"

#: Nome do executável produzido pelo `bussola.spec`.
EXECUTAVEL = "BussolaPDV"


# -- utilidades ---------------------------------------------------------------
def versao() -> str:
    """Versão do pacote, lida do próprio código (nunca digitada à mão)."""
    sys.path.insert(0, str(RAIZ / "src"))
    from bussola_pdv import __version__

    return __version__


def sistema() -> str:
    """`windows`, `macos` ou `linux` — os três nomes que os pacotes usam."""
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def _executar(comando: list[str], *, descricao: str) -> None:
    print(f"\n=== {descricao} ===")
    print("$", " ".join(comando))
    # Lista de argumentos, sem shell: nada aqui vem de entrada do usuário.
    resultado = subprocess.run(comando, cwd=RAIZ, check=False)  # noqa: S603
    if resultado.returncode != 0:
        raise SystemExit(
            f"Falhou: {descricao} (código {resultado.returncode}). "
            "Nada foi publicado; o erro acima é do passo, não do pacote."
        )


def _texto_do_leia_me(*, como_instalar: str, como_rodar: str, como_remover: str, dados: str) -> str:
    modelo = (PACOTES / "LEIA-ME.txt").read_text(encoding="utf-8")
    trocas = {
        "%VERSAO%": versao(),
        "%SISTEMA%": f"{platform.system()} {platform.machine()}",
        "%COMO_INSTALAR%": como_instalar.strip(),
        "%COMO_RODAR%": como_rodar.strip(),
        "%COMO_REMOVER%": como_remover.strip(),
        "%ONDE_FICAM_OS_DADOS%": dados.strip(),
    }
    for marca, valor in trocas.items():
        modelo = modelo.replace(marca, valor)
    return modelo


def _copiar_modelo(nome: str, destino: Path) -> Path:
    origem = PACOTES / nome
    if not origem.is_file():
        raise SystemExit(f"Modelo ausente no repositório: {origem}")
    destino.write_bytes(origem.read_bytes())
    destino.chmod(0o755)
    return destino


def _zipar(pasta: Path, destino: Path, *, raiz_no_zip: str) -> Path:
    """Zip com uma pasta-raiz só, para não espalhar arquivo ao extrair."""
    if destino.exists():
        destino.unlink()
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as arquivo:
        for caminho in sorted(pasta.rglob("*")):
            if caminho.is_file():
                arquivo.write(caminho, Path(raiz_no_zip) / caminho.relative_to(pasta))
    return destino


def _tarizar(pasta: Path, destino: Path, *, raiz_no_tar: str) -> Path:
    """`.tar.gz` preservando o bit de execução (zip não garante isso no Linux)."""
    if destino.exists():
        destino.unlink()
    with tarfile.open(destino, "w:gz") as arquivo:
        arquivo.add(pasta, arcname=raiz_no_tar)
    return destino


def _mb(caminho: Path) -> str:
    return f"{caminho.stat().st_size / (1024 * 1024):.1f} MB"


# -- passos comuns ------------------------------------------------------------
def rodar_testes() -> None:
    """Teste antes de empacotar: pacote quebrado não chega em `dist/`."""
    _executar([sys.executable, "-m", "pytest", "tests", "-q"], descricao="Testes")
    _executar([sys.executable, "-m", "ruff", "check", "src", "tests"], descricao="Lint")


def rodar_pyinstaller() -> Path:
    if not SPEC.is_file():
        raise SystemExit(f"Receita do PyInstaller não encontrada: {SPEC}")
    _executar(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", str(SPEC)],
        descricao="PyInstaller (onedir, sem console)",
    )
    saida = DIST / EXECUTAVEL
    if not saida.is_dir():
        raise SystemExit(f"O PyInstaller não produziu {saida}")
    return saida


# -- Windows ------------------------------------------------------------------
def empacotar_windows(pasta: Path) -> list[Path]:
    """Zip portátil + instalador Inno Setup, se ele estiver instalado."""
    gerados: list[Path] = []
    leia_me = pasta / "LEIA-ME.txt"
    leia_me.write_text(
        _texto_do_leia_me(
            como_instalar="""
Este pacote NÃO precisa de instalador: abra a pasta e execute BussolaPDV.exe.
Se preferir o programa no menu Iniciar, use o instalador (BussolaPDV-<versão>-setup.exe)
que acompanha a mesma versão no GitHub.
""",
            como_rodar="""
BussolaPDV.exe. Se o Windows mostrar "O Windows protegeu o computador", clique em
"Mais informações" > "Executar assim mesmo". O aviso existe porque o programa não
tem assinatura digital paga — não porque ele faça algo suspeito.
""",
            como_remover="""
Apague a pasta. Se você usou o instalador, use "Aplicativos e recursos".
""",
            dados="%LOCALAPPDATA%\\BussolaPDV (ou a pasta escolhida no primeiro uso).",
        ),
        encoding="utf-8",
    )
    zip_portatil = DIST / f"{EXECUTAVEL}-{versao()}-win64.zip"
    _zipar(pasta, zip_portatil, raiz_no_zip=f"{EXECUTAVEL}-{versao()}")
    gerados.append(zip_portatil)

    iscc = _procurar_iscc()
    if iscc is None:
        print(
            "\nInno Setup não encontrado: o .zip portátil foi gerado e já é utilizável.\n"
            "Para ter o setup.exe: winget install -e --id JRSoftware.InnoSetup e rode de novo."
        )
        return gerados
    _executar(
        [str(iscc), f"/DAppVersion={versao()}", str(AQUI / "instalador.iss")],
        descricao="Inno Setup",
    )
    setup = DIST / "instalador" / f"{EXECUTAVEL}-{versao()}-setup.exe"
    if not setup.is_file():
        raise SystemExit(f"O Inno Setup não gerou {setup}")
    gerados.append(setup)
    return gerados


def _procurar_iscc() -> Path | None:
    candidatos = [
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
        / "Inno Setup 6"
        / "ISCC.exe",
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
    ]
    for candidato in candidatos:
        if candidato.is_file():
            return candidato
    return None


# -- Linux --------------------------------------------------------------------
def empacotar_linux(pasta: Path) -> list[Path]:
    """`.tar.gz` com o programa, um instalador de usuário e o atalho de menu."""
    nome = f"{EXECUTAVEL}-{versao()}-linux-{_arquitetura()}"
    palco = DIST / nome
    if palco.exists():
        shutil.rmtree(palco)
    palco.mkdir(parents=True)
    shutil.copytree(pasta, palco / EXECUTAVEL)
    # Ícone de 256 px para o menu: o PyInstaller não leva o PNG "solto", e o
    # Instalar.sh copia daqui para o tema do usuário.
    icone = AQUI / "bussola.png"
    if icone.is_file():
        shutil.copy2(icone, palco / "bussola.png")

    _copiar_modelo("Instalar.sh", palco / "Instalar.sh")
    _copiar_modelo("Iniciar.sh", palco / "Iniciar.sh")
    # O `.desktop` fica aqui como modelo: o Instalar.sh grava o caminho absoluto
    # do Exec, que só é conhecido depois de copiar o programa.
    _copiar_modelo("BussolaPDV.desktop", palco / "BussolaPDV.desktop")
    (palco / "LEIA-ME.txt").write_text(
        _texto_do_leia_me(
            como_instalar="""
1. Extraia o pacote inteiro (não rode nada de dentro do .tar.gz):
       tar -xzf BussolaPDV-<versão>-linux-x86_64.tar.gz
2. Entre na pasta extraída e rode:
       ./Instalar.sh
   Isso copia o programa para ~/.local/opt/bussolapdv, instala o ícone e cria o
   atalho no menu de aplicativos. Não pede senha de administrador.
Sem instalar nada: ./Iniciar.sh roda direto da pasta (bom para testar num pendrive).
""",
            como_rodar="""
Pelo menu de aplicativos (ícone do Bússola) ou pelo comando bussolapdv, se
existe ~/.local/bin no seu PATH. Alternativa: ~/.local/opt/bussolapdv/BussolaPDV.

Se o programa não abrir em ambiente sem X11/Wayland (servidor), isso é esperado:
ele é uma interface gráfica.
""",
            como_remover="""
       ./Instalar.sh --remover       (na pasta extraída, a mesma que você instalou)

Isso apaga o programa, o ícone e o atalho — e deixa a base de dados intacta.""",
            dados="""
~/.local/share/bussola-pdv (ou $XDG_DATA_HOME/bussola-pdv), ou a pasta
escolhida no primeiro uso. As cópias de segurança ficam em copias/, ao lado da
base.
""",
        ),
        encoding="utf-8",
    )

    pacote = DIST / f"{nome}.tar.gz"
    _tarizar(palco, pacote, raiz_no_tar=nome)
    gerados = [pacote]
    appimage = _tentar_appimage(palco, nome)
    if appimage is not None:
        gerados.append(appimage)
    return gerados


def _arquitetura() -> str:
    maquina = platform.machine().lower()
    return {"x86_64": "x86_64", "amd64": "x86_64", "aarch64": "aarch64", "arm64": "aarch64"}.get(
        maquina, maquina
    )


def _tentar_appimage(palco: Path, nome: str) -> Path | None:
    """AppImage de verdade é opcional: precisa do `appimagetool` baixado.

    Sem ele o `.tar.gz` continua sendo o pacote — este passo é conveniência, não
    requisito. O comando está em `docs/PACOTES.md`.
    """
    ferramenta = os.environ.get("APPIMAGETOOL", "") or shutil.which("appimagetool")
    if not ferramenta:
        print(
            "\nAppImage não gerado: `appimagetool` não está no PATH nem em APPIMAGETOOL.\n"
            "O .tar.gz com Instalar.sh já é o pacote desta plataforma (ver docs/PACOTES.md)."
        )
        return None
    raiz = palco / "AppDir"
    if raiz.exists():
        shutil.rmtree(raiz)
    (raiz / "usr" / "bin").mkdir(parents=True)
    shutil.copytree(palco / EXECUTAVEL, raiz / "usr" / "bin" / EXECUTAVEL)
    icone = AQUI / "bussola.png"
    if icone.is_file():
        shutil.copy2(icone, raiz / "bussolapdv.png")
        shutil.copy2(icone, raiz / "usr" / "bin" / "bussolapdv.png")
    (raiz / "BussolaPDV.desktop").write_text(
        (PACOTES / "BussolaPDV.desktop").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (raiz / "AppRun").write_text(
        "#!/bin/sh\nexec \"$APPDIR/usr/bin/BussolaPDV\" \"$@\"\n", encoding="utf-8"
    )
    (raiz / "AppRun").chmod(0o755)
    destino = DIST / f"{nome}.AppImage"
    _executar([str(ferramenta), str(raiz), str(destino)], descricao="AppImage")
    if destino.is_file():
        destino.chmod(0o755)
        return destino
    return None


# -- macOS --------------------------------------------------------------------
def empacotar_macos(pasta: Path) -> list[Path]:
    """`.zip` (e `.dmg`, se houver `hdiutil`) com o `BussolaPDV.app`."""
    aplicativo = DIST / f"{EXECUTAVEL}.app"
    if not aplicativo.is_dir():
        raise SystemExit(
            f"O PyInstaller não gerou {aplicativo}. No macOS o `bussola.spec` cria o bundle "
            "`.app`; se você rodou com outro espec, gere de novo com este script."
        )
    nome = f"{EXECUTAVEL}-{versao()}-macos"
    palco = DIST / nome
    if palco.exists():
        shutil.rmtree(palco)
    palco.mkdir(parents=True)
    shutil.copytree(aplicativo, palco / aplicativo.name, symlinks=True)
    _copiar_modelo("Iniciar.command", palco / "Iniciar.command")
    (palco / "LEIA-ME.txt").write_text(
        _texto_do_leia_me(
            como_instalar="""
1. Descompacte o .zip (duplo clique).
2. Arraste o BussolaPDV.app para a pasta Aplicativos.

O macOS bloqueia programas baixados da internet sem assinatura. Na primeira vez:
clique com o botão direito no BussolaPDV.app > Abrir > Abrir. Ou, no Terminal:
       xattr -dr com.apple.quarantine /Applications/BussolaPDV.app
""",
            como_rodar="""
Pelo Launchpad/Spotlight (Bússola PDV) ou por Iniciar.command, que abre sem
instalar nada.
""",
            como_remover="""
Arraste o BussolaPDV.app da pasta Aplicativos para a Lixeira.
""",
            dados="""
~/Library/Application Support/BussolaPDV (ou a pasta escolhida no primeiro uso).
""",
        ),
        encoding="utf-8",
    )
    pacote = DIST / f"{nome}.zip"
    _zipar(palco, pacote, raiz_no_zip=nome)
    gerados = [pacote]

    hdiutil = shutil.which("hdiutil")
    if hdiutil is None:
        print("\nhdiutil não encontrado: sem .dmg (só existe no macOS). O .zip já abre e instala.")
        return gerados
    dmg = DIST / f"{nome}.dmg"
    if dmg.exists():
        dmg.unlink()
    _executar(
        [hdiutil, "create", "-volname", f"Bússola PDV {versao()}", "-srcfolder", str(palco), str(dmg)],
        descricao="hdiutil (.dmg)",
    )
    gerados.append(dmg)
    return gerados


# -- entrada ------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Gera o pacote de instalação simples do Bússola PDV para o sistema atual."
    )
    parser.add_argument(
        "--sem-pyinstaller",
        action="store_true",
        help="reaproveita o dist/ existente (não recompila o executável)",
    )
    parser.add_argument(
        "--sem-teste", action="store_true", help="não roda a suíte antes de empacotar"
    )
    parser.add_argument(
        "--lista", action="store_true", help="só mostra o que seria feito, sem construir"
    )
    argumentos = parser.parse_args(argv)

    alvo = sistema()
    print(f"Bússola PDV {versao()} — pacote para {alvo} ({platform.machine()})")

    if alvo == "windows" and argumentos.lista:
        print("\nGeraria: dist/BussolaPDV-<v>-win64.zip e, com Inno Setup, o setup.exe.")
        return 0
    if alvo == "linux" and argumentos.lista:
        print(
            "\nGeraria: dist/BussolaPDV-<v>-linux-<arch>.tar.gz (com Instalar.sh) "
            "e AppImage, se houver appimagetool."
        )
        return 0
    if alvo == "macos" and argumentos.lista:
        print("\nGeraria: dist/BussolaPDV-<v>-macos.zip (com BussolaPDV.app) e .dmg se houver hdiutil.")
        return 0

    inicio = time.monotonic()
    if not argumentos.sem_teste:
        rodar_testes()
    if argumentos.sem_pyinstaller:
        pasta = DIST / EXECUTAVEL
        if not pasta.is_dir():
            raise SystemExit(f"--sem-pyinstaller pedido, mas {pasta} não existe.")
        print(f"\nReaproveitando {pasta}")
    else:
        pasta = rodar_pyinstaller()

    empacotadores = {
        "windows": empacotar_windows,
        "linux": empacotar_linux,
        "macos": empacotar_macos,
    }
    gerados = empacotadores[alvo](pasta)

    print("\n=== Pronto ===")
    for caminho in gerados:
        print(f"  {caminho}  ({_mb(caminho)})")
    print(f"\nTempo: {time.monotonic() - inicio:.0f}s. Nada foi publicado: os arquivos estão em dist/.")
    if alvo != "windows":
        print(
            "Lembrete: este pacote só roda em "
            f"{'Linux' if alvo == 'linux' else 'macOS'}. Para Windows, gere no Windows "
            "(ou use o workflow .github/workflows/windows.yml)."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
