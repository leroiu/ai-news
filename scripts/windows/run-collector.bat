@echo off
chcp 65001 > nul
REM ============================================
REM AI News - News Collector (runs every hour)
REM Fetch RSS -> Dedup -> Write inbox
REM ============================================
pushd "%~dp0"

set UV_EXE=%USERPROFILE%\.local\bin\uv.exe
set LOGFILE=%~dp0logs\collector.log
set PYTHONIOENCODING=utf-8

echo ================================== >> "%LOGFILE%"
echo [%date% %time%] COLLECTOR START >> "%LOGFILE%"

"%UV_EXE%" run python collector.py >> "%LOGFILE%" 2>&1
set ERR=%ERRORLEVEL%

echo [%date% %time%] COLLECTOR END (exit=%ERR%) >> "%LOGFILE%"
popd
exit /b %ERR%
