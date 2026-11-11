<#
.SYNOPSIS
    Compila o Bússola PDV para Windows (executável + instalador).

.DESCRIPTION
    Faz o caminho completo em uma máquina Windows com Python 3.12 x64:

      1. cria/atualiza .venv
      2. instala o pacote com as dependências de empacotamento
      3. gera o ícone (bussola.ico) — idempotente
      4. roda PyInstaller com empacotamento/bussola.spec  -> dist\BussolaPDV\
      5. roda o Inno Setup (se instalado)                  -> dist\instalador\
         BussolaPDV-<versão>-setup.exe

    Requisitos: Python 3.12 x64 (python.org ou Microsoft Store) e, para o
    instalador, Inno Setup 6 (`winget install -e --id JRSoftware.InnoSetup`).
    O PyInstaller só produz binário para a plataforma em que roda: gerar o .exe
    em Linux exigiria Wine e não é suportado aqui.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File empacotamento\build_windows.ps1
    powershell -ExecutionPolicy Bypass -File empacotamento\build_windows.ps1 -SemInstalador
#>
[CmdletBinding()]
param(
    [switch]$SemInstalador,
    [switch]$SemTestes,
    [string]$Python = "py -3.12"
)

$ErrorActionPreference = "Stop"
$Raiz = Split-Path -Parent $PSScriptRoot
Set-Location $Raiz

function Passo($texto) { Write-Host "`n=== $texto ===" -ForegroundColor Cyan }

Passo "Ambiente virtual"
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Invoke-Expression "$Python -m venv .venv"
}
$Py = Join-Path $Raiz ".venv\Scripts\python.exe"
& $Py -m pip install --upgrade pip wheel | Out-Null
& $Py -m pip install -e ".[empacotamento]"

Passo "Versão do pacote"
$versao = (& $Py -c "import bussola_pdv; print(bussola_pdv.__version__)").Trim()
Write-Host "Versão: $versao"

if (-not $SemTestes) {
    Passo "Testes e análise estática"
    & $Py -m pip install -e ".[dev]" | Out-Null
    & $Py -m pytest tests -q
    & $Py -m ruff check src tests
}

Passo "Ícone"
& $Py empacotamento\gerar_icone.py

Passo "PyInstaller"
& $Py -m PyInstaller --noconfirm --clean empacotamento\bussola.spec
if (-not (Test-Path "dist\BussolaPDV\BussolaPDV.exe")) {
    throw "PyInstaller não produziu dist\BussolaPDV\BussolaPDV.exe"
}

Passo "Pacote portátil (.zip)"
$zip = "dist\BussolaPDV-$versao-win64.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path "dist\BussolaPDV\*" -DestinationPath $zip
Write-Host "Gerado: $zip"

if ($SemInstalador) {
    Write-Host "`nInstalador ignorado (-SemInstalador)." -ForegroundColor Yellow
    return
}

Passo "Inno Setup"
$iscc = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $iscc) {
    Write-Warning "Inno Setup 6 não encontrado. Instale com:"
    Write-Warning "  winget install -e --id JRSoftware.InnoSetup"
    Write-Warning "O .zip portátil acima já foi gerado e é utilizável."
    return
}

& $iscc "/DAppVersion=$versao" "empacotamento\instalador.iss"
$setup = "dist\instalador\BussolaPDV-$versao-setup.exe"
if (Test-Path $setup) {
    Passo "Pronto"
    Write-Host "Executável: dist\BussolaPDV\BussolaPDV.exe"
    Write-Host "Portátil:   $zip"
    Write-Host "Instalador: $setup"
    Write-Host "`nLembrete: sem assinatura digital o SmartScreen vai avisar." -ForegroundColor Yellow
} else {
    throw "O Inno Setup não gerou $setup"
}
