# Pacotes de instalação (Windows, Linux e macOS)

Este documento responde a duas perguntas: **qual é o jeito simples** de gerar o
pacote e **qual é o passo a passo manual**, para quando o script não servir ou você
quiser entender o que ele faz.

## A regra que não dá para contornar

O PyInstaller **não faz compilação cruzada**. Ele empacota o Python e as
bibliotecas da máquina em que roda:

| O que você quer | Onde precisa rodar |
|---|---|
| `BussolaPDV-<v>-win64.zip` e `setup.exe` | Windows |
| `BussolaPDV-<v>-linux-<arch>.tar.gz` / `.AppImage` | Linux |
| `BussolaPDV-<v>-macos.zip` / `.dmg` | macOS |

Gerar `.exe` em Linux exigiria Wine e um Python Windows dentro dele — não é
suportado, e o resultado tende a ser um executável que abre e falha. Quem tem só
Windows (o caso deste projeto) consegue os pacotes de Linux e macOS de outro jeito:
**pelos runners do GitHub Actions** (seção [CI](#ci-gerar-os-três-pelo-github)).
Está pronto em `.github/workflows/pacotes.yml`.

## Caminho simples: um comando por sistema

Na raiz do repositório, no sistema em que você está:

```bash
python empacotamento/gerar_pacote.py
```

Ele roda a suíte de testes, chama o PyInstaller com a receita única
(`empacotamento/bussola.spec`), monta o pacote da plataforma e diz o tamanho do
que gerou, em `dist/`. Opções:

| Opção | Para quê |
|---|---|
| `--sem-pyinstaller` | reaproveita `dist/` existente (iterar no empacotamento sem recompilar) |
| `--sem-teste` | não roda a suíte antes de empacotar (não recomendado) |
| `--lista` | mostra o que faria, sem construir nada |

O que cada pacote entrega:

| Sistema | Arquivo | O que o usuário faz |
|---|---|---|
| Windows | `BussolaPDV-<v>-win64.zip` | extrai e dá duplo clique em `BussolaPDV.exe` |
| Windows | `instalador/BussolaPDV-<v>-setup.exe` | duplo clique → *Avançar* → escolhe a pasta → *Instalar* |
| Linux | `BussolaPDV-<v>-linux-<arch>.tar.gz` | extrai e roda `./Instalar.sh` (sem sudo) |
| macOS | `BussolaPDV-<v>-macos.zip` / `.dmg` | arrasta `BussolaPDV.app` para *Aplicativos* |

Todos os pacotes levam um `LEIA-ME.txt` com instalar, abrir, desinstalar e onde
ficam os dados — escrito para quem nunca viu o programa.

## Passo a passo manual

Serve para quando você quiser reproduzir o que o script faz, ou corrigir um passo
que falhou. Em todos os sistemas, o começo é o mesmo:

```bash
python -m pip install -e ".[empacotamento]"
```

### Windows

```powershell
# 1. (uma vez) dependências de build — inclui o PyInstaller
python -m pip install -e ".[empacotamento]"

# 2. ícone (.ico + os BMP do assistente) — idempotente, sai do logo oficial
python empacotamento\gerar_icone.py

# 3. executável: gera dist\BussolaPDV\ com BussolaPDV.exe e BussolaPDV-console.exe
python -m PyInstaller --noconfirm --clean empacotamento\bussola.spec

# 4. pacote portátil (zip)
Compress-Archive -Path "dist\BussolaPDV\*" -DestinationPath "dist\BussolaPDV-0.12.0-win64.zip"

# 5. instalador .exe (precisa do Inno Setup 6)
winget install -e --id JRSoftware.InnoSetup
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /DAppVersion=0.12.0 empacotamento\instalador.iss
# saída: dist\instalador\BussolaPDV-0.12.0-setup.exe
```

Há um atalho que faz 1→5 (e roda testes e lint): `build_windows.ps1`.

```powershell
powershell -ExecutionPolicy Bypass -File empacotamento\build_windows.ps1
```

**Teste antes de entregar:** rode `dist\BussolaPDV\BussolaPDV.exe`. Se ele abrir
uma janela preta e fechar, rode `BussolaPDV-console.exe` — é a mesma coisa, com
mensagem de erro visível.

### Linux

```bash
python -m pip install -e ".[empacotamento]"

# 1. (opcional) ícone — o .ico/.icns não são usados no Linux, mas o script é o
#    mesmo e não custa; o PNG 256 é o que vai para o menu
QT_QPA_PLATFORM=offscreen python empacotamento/gerar_icone.py

# 2. executável
python -m PyInstaller --noconfirm --clean empacotamento/bussola.spec

# 3. pacote com instalador de usuário
python empacotamento/gerar_pacote.py --sem-pyinstaller --sem-teste

# ou tudo de uma vez:
python empacotamento/gerar_pacote.py
```

Saída: `dist/BussolaPDV-<v>-linux-<arch>.tar.gz`. Dentro dele:

```
BussolaPDV-0.12.0-linux-x86_64/
├── BussolaPDV/            programa (PyInstaller onedir)
├── Instalar.sh            copia para ~/.local/opt/bussolapdv e cria o atalho
├── Iniciar.sh             roda sem instalar nada
├── BussolaPDV.desktop     modelo do atalho (o Instalar.sh grava o caminho real)
├── bussola.png            ícone 256 px
└── LEIA-ME.txt
```

O `Instalar.sh` **não usa sudo**: copia para `~/.local/opt/bussolapdv`, instala o
ícone no tema do usuário e cria o atalho em `~/.local/share/applications`. Para
remover o programa: `./Instalar.sh --remover` (a base de dados fica intacta).

**AppImage (opcional).** É um arquivo único que roda com duplo clique, sem instalar
nada de verdade:

```bash
# baixe o appimagetool em https://github.com/AppImage/appimagetool/releases
chmod +x appimagetool-x86_64.AppImage
APPIMAGETOOL=$PWD/appimagetool-x86_64.AppImage python empacotamento/gerar_pacote.py --sem-pyinstaller --sem-teste
```

Sem a variável `APPIMAGETOOL` (ou o binário no `PATH`), o script avisa e segue com o
`.tar.gz` — que já é um pacote completo.

### macOS

```bash
python -m pip install -e ".[empacotamento]"

# 1. ícone .icns (o mesmo script, só a saída muda)
QT_QPA_PLATFORM=offscreen python empacotamento/gerar_icone.py

# 2. bundle .app — o spec cria a pasta .app quando roda no macOS
python -m PyInstaller --noconfirm --clean empacotamento/bussola.spec

# 3. zip (+ dmg, se houver hdiutil)
python empacotamento/gerar_pacote.py --sem-pyinstaller --sem-teste
```

Manual, sem o script:

```bash
cd dist
ditto -c -k --sequesterRsrc --keepParent BussolaPDV.app BussolaPDV-0.12.0-macos.zip
hdiutil create -volname "Bússola PDV 0.12.0" -srcfolder BussolaPDV.app -ov BussolaPDV-0.12.0-macos.dmg
```

**Gatekeeper.** Sem assinatura (Apple Developer, US$ 99/ano) e sem notarização, o
macOS diz que o app é de "desenvolvedor não identificado". O usuário contorna com
clique direito → *Abrir*, ou:

```bash
xattr -dr com.apple.quarantine /Applications/BussolaPDV.app
```

Se um dia houver certificado: `codesign --deep --force --sign "Developer ID Application: ..." BussolaPDV.app`
e depois `xcrun notarytool submit ... --wait`.

## CI: gerar os três pelo GitHub

`.github/workflows/pacotes.yml` roda em `ubuntu-latest`, `windows-latest` e
`macos-latest`, compila o pacote de cada sistema e sobe como artefato do run
(*Actions → run → Artifacts*). É o caminho para quem tem só uma máquina: você não
precisa de Mac nem de Linux em casa.

Não publica *release* sozinho: baixe o artefato e anexe à release quando quiser.

## O que foi verificado, e o que não foi

Verificado nesta máquina (Linux x86_64, 2026-11-14):

- `python empacotamento/gerar_pacote.py` completo — suíte de testes, PyInstaller e
  `.tar.gz` — em **~58 s**;
- o binário empacotado responde `BussolaPDV-console --version`
  (`Bússola Sistema PDV Open Source 0.12.0`);
- as migrações `.sql`, o `tzdata` e os dois logos estão dentro do pacote
  (`_internal/bussola_pdv/recursos/…`);
- `Instalar.sh` num `HOME` vazio: copiou o programa, criou o ícone e o atalho com
  caminho absoluto, o programa instalado respondeu `--version`, e `--remover`
  apagou programa + atalho deixando o resto;
- tamanho do `.tar.gz`: **100,3 MB**.

**Não verificado** (e por isso não afirmado): o `.exe`, o `setup.exe`, o `.app` e o
`.dmg` não foram gerados nem executados aqui — dependem de Windows e de macOS. A
receita é a mesma que o CI do Windows já usa (verde no GitHub), mas quem confirma
é o run.
