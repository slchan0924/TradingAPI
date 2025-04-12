@echo off
cd "..\Python"
start cmd /k "py launcher.py"

rem Wait for the Flask server to start
setlocal enabledelayedexpansion
set url=http://127.0.0.1:5000

:waitForServer
timeout /t 2 >nul
echo Checking if Flask server is up...
curl --silent --fail %url% >nul 2>&1
if errorlevel 1 (
    echo Server not ready, waiting...
    goto waitForServer
)

rem Open the default web browser to the Flask app URL
start %url%