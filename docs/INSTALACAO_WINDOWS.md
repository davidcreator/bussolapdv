# Instalação no Windows

Guia para colocar o **Bússola Sistema PDV** em um computador Windows — do zero,
sem pressupor conhecimento de programação — e também para quem quiser **gerar o
próprio `.exe`/instalador**.

> **Antes de tudo, a parte honesta.** Esta é uma versão **pré-alfa**: serve para
> testar, demonstrar e desenvolver. Ela **não** emite documento fiscal (NF-e,
> NFC-e, SAT, cupom fiscal), **não** foi homologada por contador nem por órgão
> fiscal e **não** deve ser o único sistema de uma loja em operação. Use com
> dados fictícios até validar o que você precisa.

Três caminhos possíveis. Escolha **um**:

| Caminho | Para quem | Precisa de | Resultado |
| --- | --- | --- | --- |
| **A. Instalador pronto** (`.exe`) | quem só quer usar | nada instalado | programa no menu Iniciar |
| **B. Rodar do código** | quem vai usar e acompanhar o projeto | Python 3.12 | `bussola-pdv` no PowerShell |
| **C. Compilar o `.exe`/instalador** | quem quer o binário ou distribuir para a loja | Python 3.12 + Inno Setup | `.exe` portátil e instalador |

## Requisitos (valem para os três caminhos)

- **Windows 10 (versão 1903 ou mais recente) ou Windows 11, 64 bits.** Windows 7/8
  e versões 32 bits não são suportados (o PySide6 6.x não publica binário para eles).
- **2 GB de RAM** livres (o programa em si usa ~150 MB).
- **300 MB de disco** para o código + ambiente virtual, ou **~250 MB** para a
  instalação empacotada.
- Não precisa de internet para **usar** o programa: ele é 100 % offline, sem
  telemetria e sem acesso à rede. Internet só é necessária para baixar/instalar.
- Não precisa de servidor de banco: o banco é um arquivo SQLite local.

---

## Caminho A — usar o instalador pronto

1. Baixe da página de *Releases* do repositório oficial
   (<https://github.com/davidcreator/bussolapdv/releases>) **um** destes arquivos:
   - `BussolaPDV-<versão>-setup.exe` — instalador (recomendado);
   - `BussolaPDV-<versão>-win64.zip` — versão portátil, para rodar sem instalar
     (descompacte em uma pasta sua, por exemplo `C:\BussolaPDV`, e dê dois
     cliques em `BussolaPDV.exe`).
2. Se baixou o `setup.exe`, execute-o. Vai aparecer um aviso azul do Windows
   (“O Windows protegeu o computador”) porque **o arquivo não tem assinatura
   digital** — veja [SmartScreen e antivírus](#smartscreen-e-antivírus) antes de
   decidir. O instalador **não pede senha de administrador**: ele instala só para
   o seu usuário.
3. Avance as telas (`Avançar` → `Instalar` → `Concluir`). Marque “Criar atalho na
   Área de Trabalho” se quiser o ícone na área de trabalho.
4. O programa abre sozinho no fim. Na **primeira execução** ele pede:
   - **nome da loja** (aparece na interface e no rodapé do comprovante);
   - **usuário e nome** do responsável (o *Admin Master*, dono da instalação);
   - **senha** (mínimo 8 caracteres).

   Anote a senha. Ela é guardada com Argon2id e **não há como recuperá-la** — só
   redefinir por outro Admin Master.
5. Pronto: entre com o usuário criado e comece a cadastrar produtos em
   *Administração* (ícone de engrenagem na barra lateral).

Instalação em `%LOCALAPPDATA%\Programs\BussolaPDV`; dados em
`%LOCALAPPDATA%\BussolaPDV`. Para desinstalar, veja
[Desinstalação](#desinstalação).

---

## Caminho B — rodar do código-fonte no Windows (passo a passo)

### B.1 Instalar o Python 3.12 (64 bits)

1. Abra o **Prompt de Comando** (tecle `Win`, digite `cmd`, `Enter`) e verifique
   se já existe:

   ```bat
   py -3.12 --version
   ```

   Se responder algo como `Python 3.12.x`, pule para o passo B.2.

2. Baixe em <https://www.python.org/downloads/windows/> o instalador
   **“Windows installer (64-bit)”** da linha 3.12.x.
3. Execute o instalador e **marque a caixa “Add python.exe to PATH”** na primeira
   tela. Depois clique em `Install Now`.
4. Feche e reabra o Prompt de Comando e confirme:

   ```bat
   py -3.12 --version
   where py
   ```

   Se `py` não for reconhecido, use o “Python 3.12” do Menu Iniciar (ele abre um
   terminal com o Python já no PATH) ou reinstale marcando a caixa do PATH.

> Não use o Python 3.13+ para esta versão: o projeto declara `requires-python >=3.12`
> e é testado em 3.12 e 3.13 no Linux, mas o caminho Windows documentado aqui é o
> 3.12, que é o que o build/testes usam.

### B.2 Baixar o código

Com Git instalado (<https://git-scm.com/download/win>):

```bat
cd %USERPROFILE%
git clone https://github.com/davidcreator/bussolapdv.git
cd bussolapdv
```

Sem Git: baixe o ZIP em `Code` → `Download ZIP`, descompacte e entre na pasta
pelo Prompt de Comando com `cd` até ela (a pasta que contém `pyproject.toml`).

### B.3 Criar o ambiente virtual e instalar os pacotes

Dentro da pasta do projeto:

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e .
```

A última linha baixa e instala exatamente **dois** pacotes de execução (o resto é
dependência deles, 0 ou 1 nível):

| Pacote | Versão | Para que serve |
| --- | --- | --- |
| `PySide6-Essentials` | `>=6.6,<7` | interface gráfica (Qt 6). Traz o Qt inteiro nos *wheels*: **não é preciso instalar Qt à parte no Windows** |
| `argon2-cffi` | `>=23.1,<26` | derivação de senha Argon2id (com `cffi`, instalado automaticamente) |

Para desenvolver ou rodar a suíte de testes, acrescente o extra `dev`:

```bat
python -m pip install -e ".[dev]"
```

| Pacote (extra `dev`) | Versão | Para que serve |
| --- | --- | --- |
| `pytest` | `>=8,<10` | testes |
| `pytest-cov` | `>=5` | cobertura |
| `ruff` | `>=0.6` | lint/formatação |
| `mypy` | `>=1.11` | checagem de tipos |

E, só se for gerar o executável (Caminho C), o extra `empacotamento`:

| Pacote (extra `empacotamento`) | Versão | Para que serve |
| --- | --- | --- |
| `pyinstaller` | `>=6.10,<7` | transforma o programa em `.exe` |

**Dependências de sistema:** nenhuma além do próprio Windows. Os *wheels* do
PySide6 para Windows já incluem as DLLs do Qt. Em uma instalação **muito** limpa
pode faltar o *Microsoft Visual C++ Redistributable 2015-2022 (x64)*; se o
programa reclamar de `VCRUNTIME140_1.dll` ou `MSVCP140.dll`, instale-o em
<https://aka.ms/vs/17/release/vc_redist.x64.exe>.

### B.4 Criar a base e abrir o programa

Primeiro uso, criando a base com um Admin Master:

```bat
bussola init --banco dados\pdv.db --admin-login master --admin-nome "Seu Nome"
```

O comando pede a senha (ela não aparece na tela). Alternativa para automação,
sem prompt interativo:

```bat
set BUSSOLA_SENHA_ADMIN=uma-senha-forte-aqui
bussola init --banco dados\pdv.db --admin-login master --admin-nome "Seu Nome"
set BUSSOLA_SENHA_ADMIN=
```

Abra a interface:

```bat
bussola-pdv --banco dados\pdv.db
```

ou, equivalente:

```bat
bussola ui --banco dados\pdv.db
```

Para conhecer o programa antes de cadastrar qualquer coisa, use a base fictícia:

```bat
bussola demo --banco dados\demo.db
bussola ui --banco dados\demo.db
```

Usuários da demonstração: `master`, `admin`, `gerente`, `contabilidade`,
`operador` — senha `Bussola#2026`. **São dados fictícios; não use essa base em
operação real.**

### B.5 Atalho na Área de Trabalho / Menu Iniciar (opcional)

Crie o arquivo `abrir-pdv.cmd` na pasta do projeto:

```bat
@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
bussola-pdv --banco dados\pdv.db
```

Clique com o botão direito nele → **Enviar para** → **Área de trabalho (criar
atalho)**. Nas propriedades do atalho, em *Alterar ícone*, aponte para o
`empacotamento\bussola.ico` do projeto.

### B.6 Atualizar depois

```bat
cd %USERPROFILE%\bussolapdv
git pull
.venv\Scripts\activate
python -m pip install -e . --upgrade
```

As migrações do banco são aplicadas automaticamente ao abrir a base. **Faça uma
cópia de segurança antes** de atualizar (próxima seção).

---

## Caminho C — compilar o `.exe` e o instalador

Isto gera:

```
dist\BussolaPDV\BussolaPDV.exe              ← programa (sem janela de console)
dist\BussolaPDV\BussolaPDV-console.exe      ← mesmo programa, com console (diagnóstico)
dist\BussolaPDV-<versão>-win64.zip          ← versão portátil
dist\instalador\BussolaPDV-<versão>-setup.exe ← instalador (Inno Setup 6)
```

### C.1 Preparar

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install -e ".[empacotamento]"
winget install -e --id JRSoftware.InnoSetup     :: só para o instalador
```

### C.2 Um comando faz tudo

```bat
powershell -ExecutionPolicy Bypass -File empacotamento\build_windows.ps1
```

O script: valida o ambiente, roda testes e lint, gera o ícone
(`empacotamento\gerar_icone.py` → `bussola.ico`), roda o PyInstaller com
`empacotamento\bussola.spec`, cria o `.zip` e chama o Inno Setup. Variações:

```bat
powershell -ExecutionPolicy Bypass -File empacotamento\build_windows.ps1 -SemTestes
powershell -ExecutionPolicy Bypass -File empacotamento\build_windows.ps1 -SemInstalador
```

### C.3 Só o PyInstaller (sem instalador)

```bat
python empacotamento\gerar_icone.py
python -m PyInstaller --noconfirm --clean empacotamento\bussola.spec
```

Escolhas da receita (`empacotamento\bussola.spec`), e por quê:

- **`onedir`** em vez de `--onefile`: `--onefile` descompacta o Qt em uma pasta
  temporária **a cada** execução (abertura lenta, antivírus reclamando de
  auto-extração). Empacotado em `onedir`, o programa abre rápido e o instalador
  cuida da pasta.
- **`console=False`** no executável principal: nada de janela preta atrás do PDV.
  O `-console.exe` existe justamente para quando algo falha em silêncio.
- **`upx=False`**: compressão UPX em binário Qt aumenta muito o falso positivo de
  antivírus.
- **`version=` (`empacotamento\versao_info.txt`)**: preenche as propriedades do
  arquivo no Windows (versão, produto, licença). A versão ali é conferida por
  `tests/test_empacotamento.py`.
- **`icon=` (`empacotamento\bussola.ico`)**: ícone multi-resolução 16→256 px,
  gerado do desenho da própria interface (nenhum arquivo de terceiro).

### C.4 Instalador com Inno Setup

```bat
"%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" /DAppVersion=0.4.0 empacotamento\instalador.iss
```

O `.iss` instala **por usuário** (`PrivilegesRequired=lowest`, em
`%LOCALAPPDATA%\Programs\BussolaPDV`), cria atalhos no Menu Iniciar e na Área de
Trabalho (opcional), registra a desinstalação em *Aplicativos instalados* e
**não apaga a base** ao desinstalar.

**Quero `.msi` em vez de `.exe`.** O `.exe` do Inno Setup é o caminho testado e
documentado aqui. Se o seu ambiente exige MSI, use o WiX Toolset 4
(`dotnet tool install --global wix`) com um manifesto que coloque os arquivos de
`dist\BussolaPDV` em `ProgramFiles64Folder\BussolaPDV`, crie os atalhos e o
`BussolaPDV.exe` como `File` de `Shortcut` — o resultado é equivalente, mas esse
caminho **não** está automatizado neste repositório, e não é possível afirmar que
funciona sem antes rodá-lo em uma máquina Windows com WiX.

### C.5 Compilar pelo GitHub Actions (sem Windows em casa)

O workflow [`.github/workflows/windows.yml`](../.github/workflows/windows.yml)
roda em `windows-latest` a cada push na `main`, tag `v*` ou manualmente
(*Actions* → **Windows** → *Run workflow*). Ele:

1. instala Python 3.12 x64 e as dependências;
2. roda a suíte de testes e o lint;
3. gera o ícone e chama o PyInstaller;
4. faz um teste de fumaça (`BussolaPDV-console.exe --version`);
5. instala o Inno Setup via Chocolatey e compila o `.iss`;
6. publica o **`.zip`** e o **`setup.exe`** como artefato do run (retenção 30 dias).

Baixe em *Actions* → run desejado → **Artifacts** → `bussolapdv-windows`.

### C.6 O que foi de fato gerado e testado

Transparência sobre este repositório:

| Item | Situação |
| --- | --- |
| Receita PyInstaller (`bussola.spec`), ícone, metadados, `.iss`, `build_windows.ps1` | versionados e revisados |
| Ícone `.ico` | **gerado de verdade** por `empacotamento/gerar_icone.py` (validado por teste) |
| Sintaxe do spec/`.iss`, versões sincronizadas, arquivos referenciados | cobertos por `tests/test_empacotamento.py` |
| **Build de fumaça com a mesma receita** | **executado em Linux**: o binário congelado criou a base `demo`, aplicou as migrações, respondeu `info` com integridade OK e `--version`. Foi assim que se descobriu que os `.sql` de migração precisavam entrar em `datas` (corrigido) |
| `BussolaPDV.exe`, `setup.exe`, `.msi` | **não** foram gerados no ambiente de desenvolvimento (Linux, sem Windows/Wine). Saem do workflow `windows.yml` ou de uma máquina Windows rodando o Caminho C |
| Instalação completa em Windows real | **não** executada por quem escreveu este guia; trate o checklist abaixo como roteiro de validação |

---

## Onde ficam os dados (e como não perdê-los)

| O quê | Caminho |
| --- | --- |
| Banco do PDV (SQLite, com WAL) | `%LOCALAPPDATA%\BussolaPDV\pdv.db` |
| Cópias de segurança | `%LOCALAPPDATA%\BussolaPDV\copias\` |
| Programa instalado (Caminho A/C) | `%LOCALAPPDATA%\Programs\BussolaPDV` |
| Código + `.venv` (Caminho B) | onde você clonou, por exemplo `%USERPROFILE%\bussolapdv` |

Para abrir a pasta de dados rapidamente: tecle `Win+R`, cole
`%LOCALAPPDATA%\BussolaPDV` e `Enter`.

Você pode mover a base para outro lugar definindo a variável de ambiente
`BUSSOLA_DADOS` (a pasta indicada passa a ser a raiz dos dados):

```bat
set BUSSOLA_DADOS=D:\BussolaDados
bussola-pdv
```

### Backup

```bat
bussola backup --banco "%LOCALAPPDATA%\BussolaPDV\pdv.db" --destino "%LOCALAPPDATA%\BussolaPDV\copias"
```

O comando copia de forma consistente (usa a API de backup do SQLite, não um
copiar-colar do arquivo com o programa aberto) e verifica a integridade do
destino. **Restaurar** = fechar o programa e substituir `pdv.db` pela cópia
escolhida (renomeie a atual antes, para poder voltar atrás).

Coloque a pasta `copias` em um pendrive ou na nuvem da loja. Três avisos:

- **Não** deixe a base dentro de pastas sincronizadas pelo OneDrive/Google Drive
  enquanto o programa roda: a sincronização briga com os arquivos `-wal`/`-shm`.
  Sincronize a pasta de **cópias**, não a base viva.
- **Não** abra a mesma base por dois computadores em pasta de rede: SQLite com WAL
  não é seguro sobre SMB.
- Faça a cópia no fim do expediente, depois do fechamento do caixa.

---

## SmartScreen e antivírus

O `.exe` e o instalador **não são assinados digitalmente** (assinatura de código
exige certificado pago, adquirido por pessoa jurídica; o projeto não tem um). Duas
consequências previsíveis:

1. **SmartScreen** mostra “O Windows protegeu o computador” na primeira execução.
   Confira que o arquivo veio das *Releases* oficiais do repositório e clique em
   **Mais informações** → **Executar assim mesmo**. O SHA-256 de cada artefato
   fica no corpo da Release; compare com
   `Get-FileHash .\BussolaPDV-0.4.0-setup.exe -Algorithm SHA256`.
2. **Antivírus** pode sinalizar o executável do PyInstaller por heurística
   (“programa desconhecido que cria outros arquivos”). Isso é comportamento
   normal de binário Python congelado sem assinatura. Se a política da sua loja
   exige, adicione a pasta do programa como exceção — ou use o Caminho B (rodar do
   código), que não passa por empacotamento.

Nenhum dos dois casos significa que o programa faça algo escondido: ele não acessa
a rede. O código é público e auditável — essa é a razão de o projeto ser aberto.

---

## Checklist de validação após instalar

Faça isso no computador da loja, antes de usar para valer:

- [ ] O programa abre pelo atalho do Menu Iniciar (sem terminal aparecendo).
- [ ] O nome da loja digitado no primeiro uso aparece na barra lateral.
- [ ] Login com o Admin Master funciona; senha errada é recusada.
- [ ] `Administração` → cadastrar um produto, um cliente e um segundo usuário
      (ex.: perfil `Atendente`).
- [ ] Abrir o caixa, registrar uma venda fictícia de R$ 1,00, finalizar.
- [ ] Fechar a caixa e conferir o relatório de fechamento do dia.
- [ ] `bussola info --banco "%LOCALAPPDATA%\BussolaPDV\pdv.db"` (ou
      `BussolaPDV-console.exe info`) mostra integridade OK.
- [ ] Fazer o backup e conferir o arquivo gerado na pasta `copias`.
- [ ] Reiniciar o Windows e repetir a abertura (confirma que nada depende do
      terminal aberto).
- [ ] Testar a impressão do comprovante **interno** (não é documento fiscal).

---

## Desinstalação

**Instalador (Caminho A/C):** *Configurações* → *Aplicativos* → *Aplicativos
instalados* → **Bússola Sistema PDV** → *Desinstalar*.

A desinstalação remove **o programa** e mantém a base em
`%LOCALAPPDATA%\BussolaPDV`. Para apagar também os dados (irreversível): apague
essa pasta depois de guardar a cópia de segurança. Se quiser zerar a instalação
mantendo o programa, apague apenas `pdv.db`, `pdv.db-wal` e `pdv.db-shm` — na
próxima abertura o programa volta ao assistente de primeiro uso.

**Código (Caminho B):** `deactivate` e apague a pasta do projeto; a base fica em
`%LOCALAPPDATA%\BussolaPDV` (Caminho A) ou em `dados\` dentro do projeto
(Caminho B), dependendo do `--banco` que você escolheu.

---

## Problemas comuns

| Sintoma | Causa provável | O que fazer |
| --- | --- | --- |
| `'py' não é reconhecido...` | Python fora do PATH | reinstale marcando “Add python.exe to PATH”, ou use o atalho *Python 3.12* do Menu Iniciar |
| `'bussola' não é reconhecido...` | ambiente virtual não ativado | `.venv\Scripts\activate` antes de qualquer comando `bussola` |
| `ImportError: DLL load failed while importing QtCore` | falta o *Visual C++ Redistributable* ou wheel corrompido | instale `vc_redist.x64.exe`; depois `python -m pip install --force-reinstall PySide6-Essentials` |
| Duplo clique no `.exe` não abre nada | erro silencioso em app sem console | rode `BussolaPDV-console.exe` no Prompt de Comando e leia a mensagem |
| `database is locked` | outra instância aberta, ou base em pasta sincronizada/rede | feche as outras instâncias; mova a base para disco local |
| “Não há nenhum usuário” na tela de login | base criada mas sem Admin Master | rode `bussola init --forcar` (apaga a base) ou, no executável, apague `pdv.db` e reabra |
| Esqueci a senha do Admin Master | Argon2id não é reversível | entre como outro Admin Master e redefina; se não houver, a base só pode ser recriada (perde-se o histórico) |
| Instalador avisa “não assinado” | sem certificado de assinatura de código | ver [SmartScreen e antivírus](#smartscreen-e-antivírus) |
| Tela cortada em notebook 1366×768 | janela mínima é 803×760 + barra de tarefas | recolha a barra lateral (botão de menu) e use a janela maximizada; a resolução mínima confortável é 1366×768 |
| Impressora térmica sai com caracteres estranhos | driver/acentuação da impressora | teste a impressão de texto puro no Windows; o projeto não homologou modelos de impressora |

Se o problema não estiver aqui, abra uma issue em
<https://github.com/davidcreator/bussolapdv/issues> com: versão (`--version`),
saída do `BussolaPDV-console.exe`, versão do Windows e o que você fez antes.

---

## Resumo em uma tela

**Usar:** baixar `BussolaPDV-<versão>-setup.exe` → executar → “Mais informações /
Executar assim mesmo” → instalar → informar loja, usuário e senha → entrar.

**Rodar do código:**

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install -e .
bussola init --banco dados\pdv.db --admin-login master --admin-nome "Seu Nome"
bussola-pdv --banco dados\pdv.db
```

**Compilar:**

```bat
python -m pip install -e ".[empacotamento]"
powershell -ExecutionPolicy Bypass -File empacotamento\build_windows.ps1
```

Voltar ao [README](../README.md).
