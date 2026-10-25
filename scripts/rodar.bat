@echo off
rem Roda o PadBridge (decks + ponte MIDI + pads) direto do codigo, sem gerar o .exe.
rem Precisa da pasta PadBridge (v1) ao lado desta. Feche o PadBridge.exe antes.
cd /d "%~dp0\.."
if not exist ".venv\Scripts\python.exe" (
  py -3.12 -m venv .venv
  ".venv\Scripts\python.exe" -m pip install -r requirements-build.txt
)
set PYTHONPATH=%CD%\..\PadBridge
".venv\Scripts\python.exe" -m padbridge2 --python-db "%CD%\.venv\Scripts\python.exe" %*
pause
