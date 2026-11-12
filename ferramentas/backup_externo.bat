@echo off
REM ---------------------------------------------------------------------------
REM Copia de seguranca do Bussola PDV SEM abrir o programa.
REM
REM Existe porque o dia em que mais se precisa de backup e o dia em que o
REM programa nao abre. Este atalho chama ferramentas\backup_externo.py, que usa
REM apenas a biblioteca padrao do Python.
REM
REM Uso:
REM   backup_externo.bat               cria a copia do dia
REM   backup_externo.bat listar        mostra as copias
REM   backup_externo.bat recuperar     tenta salvar uma base danificada
REM
REM Duplo clique sem argumento = criar copia.
REM ---------------------------------------------------------------------------
setlocal
set AQUI=%~dp0

REM 1) Python do PATH
where py >nul 2>nul
if %ERRORLEVEL%==0 (
    py -3 "%AQUI%backup_externo.py" %*
    goto fim
)

REM 2) python.exe do PATH
where python >nul 2>nul
if %ERRORLEVEL%==0 (
    python "%AQUI%backup_externo.py" %*
    goto fim
)

echo.
echo Python nao encontrado neste computador.
echo.
echo Alternativa sem Python: feche o Bussola PDV e copie a pasta de dados inteira
echo (por padrao %%LOCALAPPDATA%%\BussolaPDV) para um pen drive. O arquivo que
echo importa e o pdv.db; o resto sao relatorios e logs.
echo.
pause

:fim
if "%~1"=="" pause
endlocal
