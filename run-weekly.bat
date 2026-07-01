@echo off
chcp 65001 > nul
REM ============================================
REM AI News - Weekly Report (runs every Sunday)
REM Summarize 7 days -> AI trend analysis -> weekly report
REM ============================================
pushd "%~dp0"

set UV_EXE=%USERPROFILE%\.local\bin\uv.exe
set LOGFILE=%~dp0logs\task.log
set PYTHONIOENCODING=utf-8

echo ================================== >> "%LOGFILE%"
echo [%date% %time%] WEEKLY START >> "%LOGFILE%"

"%UV_EXE%" run python pipeline.py --weekly >> "%LOGFILE%" 2>&1
set ERR=%ERRORLEVEL%

echo [%date% %time%] Generating knowledge graph... >> "%LOGFILE%"
"%UV_EXE%" run python pipeline.py --graph >> "%LOGFILE%" 2>&1

echo [%date% %time%] WEEKLY END (exit=%ERR%) >> "%LOGFILE%"
popd
exit /b %ERR%
