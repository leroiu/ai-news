@echo off
chcp 65001 > nul
REM ============================================
REM AI News - Daily Report (runs once per day)
REM Default: reads from inbox.jsonl (filled by collector every hour)
REM ============================================
pushd "%~dp0"

set UV_EXE=%USERPROFILE%\.local\bin\uv.exe
set LOGFILE=%~dp0logs\task.log
set PYTHONIOENCODING=utf-8

echo ================================== >> "%LOGFILE%"
echo [%date% %time%] DAILY START >> "%LOGFILE%"

"%UV_EXE%" run python pipeline.py >> "%LOGFILE%" 2>&1
set ERR=%ERRORLEVEL%

echo [%date% %time%] Running inbox maintenance... >> "%LOGFILE%"
"%UV_EXE%" run python -c "from src.utils import cleanup_inbox; kept, archived = cleanup_inbox(); print(f'Inbox: {kept} kept, {archived} archived')" >> "%LOGFILE%" 2>&1

echo [%date% %time%] DAILY END (exit=%ERR%) >> "%LOGFILE%"
popd
exit /b %ERR%
