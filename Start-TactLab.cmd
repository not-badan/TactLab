@echo off
setlocal
cd /d "%~dp0" || goto failed
if exist ".venv\Scripts\python.exe" goto dependencies
py -3.12 -m venv ".venv" || goto failed
:dependencies
if not exist ".venv\tactlab-requirements.txt" goto install
fc /b requirements.txt ".venv\tactlab-requirements.txt" >nul 2>&1 && goto launch
:install
".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto failed
copy /y requirements.txt ".venv\tactlab-requirements.txt" >nul || goto failed
:launch
".venv\Scripts\python.exe" start_local.py || goto failed
exit /b 0
:failed
echo.
echo TactLab could not start. Check the error above and README.md.
echo First launch requires Python 3.12 x64 and an Internet connection.
pause
exit /b 1