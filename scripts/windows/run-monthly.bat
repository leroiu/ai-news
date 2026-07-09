@echo off
chcp 65001 > nul
REM ============================================
REM AI News - Monthly Report (runs 1st of each month)
REM Summarize 30 days -> AI trend analysis -> monthly report
REM ============================================
pushd "%~dp0"

set UV_EXE=%USERPROFILE%\.local\bin\uv.exe
set LOGFILE=%~dp0logs\task.log
set PYTHONIOENCODING=utf-8

echo ================================== >> "%LOGFILE%"
echo [%date% %time%] MONTHLY START >> "%LOGFILE%"

"%UV_EXE%" run python pipeline.py --monthly >> "%LOGFILE%" 2>&1
set ERR=%ERRORLEVEL%

echo [%date% %time%] MONTHLY END (exit=%ERR%) >> "%LOGFILE%"
popd
exit /b %ERR%
