@echo off
REM Odswieza dane z folderu CFO i otwiera dashboard (dwuklik)
cd /d "%~dp0"
set PY=python
where python >nul 2>nul || set PY=py
%PY% -m cfo przetworz
if errorlevel 1 (
  echo.
  echo Wystapil blad - sprawdz komunikat powyzej.
  pause
  exit /b 1
)
%PY% -m cfo dashboard
