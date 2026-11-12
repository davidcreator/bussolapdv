# `empacotamento/` — como o programa vira `.exe`

Guia de uso para quem instala e para quem compila: [`docs/INSTALACAO_WINDOWS.md`](../docs/INSTALACAO_WINDOWS.md).

| Arquivo | O que é |
| --- | --- |
| `bussola.spec` | receita do PyInstaller (**onedir**, executável sem console + versão com console, `upx=False`) |
| `entrada.py` | ponto de entrada congelado: `freeze_support` + AppUserModelID; delega para `bussola_pdv.ui.entrada` |
| `versao_info.txt` | metadados do `.exe` (produto, versão, licença); conferido por teste contra `__version__` |
| `bussola.ico` / `bussola.png` | ícone 16→256 px, gerado do desenho da interface |
| `gerar_icone.py` | gera o acima com QPainter + `struct` (sem Pillow, sem arquivo de terceiro) |
| `instalador.iss` | Inno Setup 6: instala por usuário, atalhos, desinstalação preservando a base |
| `AVISO.txt` / `LEIA-ME.txt` | textos que ficam ao lado do programa e no instalador |
| `build_windows.ps1` | build completo (venv → testes → ícone → PyInstaller → `.zip` → `.iss`) |

```powershell
python -m pip install -e ".[empacotamento]"
powershell -ExecutionPolicy Bypass -File empacotamento\build_windows.ps1
```

Saída em `dist/`: `BussolaPDV\BussolaPDV.exe`, `BussolaPDV-<versão>-win64.zip` e
`instalador\BussolaPDV-<versão>-setup.exe`.

## O que não pode faltar no bundle

- **Migrações `.sql`** (`bussola_pdv/infra/sqlite/migracoes`): são lidas por caminho relativo a
  `migrador.py`. Sem elas o programa abre e falha com `no such table: usuarios`. Estão em `datas` no
  spec e têm teste de regressão.
- Nada mais: ícones e folha de estilo são strings dentro do pacote Python.

## Exportação

Os escritores `.xlsx` (biblioteca padrão) e `.pdf` (Qt) entram no bundle sozinhos: são módulos Python
puros e um import tardio do PySide6, que o PyInstaller já empacota. Depois de um build, vale conferir:

```powershell
.\dist\BussolaPDV\BussolaPDV-console.exe exportar --banco %LOCALAPPDATA%\BussolaPDV\pdv.db `
    --tipo fechamento --data 2026-11-11 --formato pdf --login master --destino .\teste.pdf
```

Se o PDF sair com 0 byte, o plugin do Qt não foi coletado — veja os avisos do PyInstaller.

## Limites

- Binário Windows só é produzido **em Windows** (ou no runner `windows-latest` do workflow
  `.github/workflows/windows.yml`). No Linux, rodar o mesmo spec gera um binário Linux — útil como
  fumaça, não como entrega.
- Sem assinatura digital o SmartScreen avisa no primeiro uso; ver
  [SmartScreen e antivírus](../docs/INSTALACAO_WINDOWS.md#smartscreen-e-antivírus).
