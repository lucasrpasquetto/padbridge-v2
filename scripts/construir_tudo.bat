@echo off
setlocal
cd /d "%~dp0\.."
title PadBridge - gerar o pacote completo
echo.
echo === PadBridge: gerando o pacote completo (decks + pads num exe so) ===
echo (feche o PadBridge e o PadBridge2 antes, se estiverem abertos)
echo.

set V1=..\PadBridge
if not exist "padbridge2\servidor.py" ( echo ERRO: rode este script dentro do repositorio PadBridge-v2. & goto :erro )
if not exist "%V1%\padbridge\app.py" ( echo ERRO: nao achei o PadBridge v1 em %V1% . Ele precisa estar ao lado desta pasta. & goto :erro )
if not exist "%V1%\padbridge\web\index.html" (
  echo Gerando a tela e o mapeamento do v1...
  pushd "%V1%" & py -3 tools\gerar.py & popd
)

set VENV=.venv
if not exist "%VENV%\Scripts\python.exe" (
  echo Criando o ambiente virtual, so na primeira vez...
  py -3.12 -m venv %VENV%
)
if not exist "%VENV%\Scripts\python.exe" ( echo ERRO: nao consegui criar o ambiente. Python 3.12 instalado? & goto :erro )

echo Instalando as dependencias...
"%VENV%\Scripts\python.exe" -m pip install --upgrade pip
"%VENV%\Scripts\python.exe" -m pip install -r requirements-build.txt
if errorlevel 1 ( echo ERRO ao instalar as dependencias. & goto :erro )

echo Atualizando a tela de pads embutida no v2...
"%VENV%\Scripts\python.exe" tools\gera_pads.py "%V1%\padbridge\web\index.html"
if errorlevel 1 goto :erro

set OUT=dist\PadBridge-Completo
if exist "%OUT%" rmdir /s /q "%OUT%"
mkdir "%OUT%"

echo Gerando PadBridge.exe (decks + ponte MIDI + pads, tudo num programa so)...
"%VENV%\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --noconsole --name PadBridge --distpath "%OUT%" --workpath build\exe --specpath build ^
  --paths . --paths "%V1%" --add-data "%CD%\padbridge2\web;padbridge2\web" --add-data "%CD%\%V1%\padbridge\web\index.html;web" ^
  --collect-all pyrekordbox --collect-all pywinauto --collect-all comtypes --collect-submodules sqlcipher3 --collect-submodules sqlalchemy ^
  --hidden-import mido.backends.rtmidi --hidden-import pystray._win32 --hidden-import PIL --collect-submodules mido ^
  tools\lancador.py
if errorlevel 1 ( echo ERRO ao gerar o PadBridge.exe. & goto :erro )

copy /y "%V1%\mapping\PadBridge.midi.csv" "%OUT%\" >nul 2>nul
copy /y scripts\Testar-banco.bat "%OUT%\Testar-banco.bat" >nul
copy /y scripts\LEIA-ME.txt "%OUT%\LEIA-ME.txt" >nul

echo.
echo PRONTO: %OUT%
echo Copie a pasta inteira para o notebook e abra o PadBridge.exe (veja o LEIA-ME.txt).
explorer "%OUT%"
pause
exit /b 0

:erro
echo.
echo Nao foi possivel concluir. Copie a mensagem acima.
pause
exit /b 1
