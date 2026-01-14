@echo off
REM Deployment script for radioToolsAutomation
REM Handles: Kill old process, deploy, start new version hidden

setlocal enabledelayedexpansion

echo.
echo ============================================================
echo DEPLOYMENT: radioToolsAutomation
echo ============================================================
echo.

REM Get the active path (where this script is)
set "ACTIVE_ROOT=%~dp0"
set "ACTIVE_ROOT=%ACTIVE_ROOT:~0,-1%"

REM Get stable path from config or use default
set "STABLE_ROOT=%ACTIVE_ROOT% - stable"

echo Active folder: %ACTIVE_ROOT%
echo Stable folder: %STABLE_ROOT%
echo.

REM Kill old processes
echo [1/3] Terminating old process...
taskkill /F /IM python.exe >nul 2>&1
if errorlevel 1 (
    echo         (No processes to terminate)
) else (
    echo         Process terminated successfully
    timeout /t 2 /nobreak >nul
)
echo.

REM Run deployment
echo [2/3] Deploying active to stable...
cd /d "%ACTIVE_ROOT%"
python deploy.py --full
if errorlevel 1 (
    echo ERROR: Deployment failed!
    pause
    exit /b 1
)
echo.

REM Start new stable version hidden
echo [3/3] Starting stable version...
cscript.exe //nologo "%ACTIVE_ROOT%\start_hidden.vbs" "%STABLE_ROOT%\START RDS AND INTRO.bat"
timeout /t 1 /nobreak >nul
echo         Stable version started successfully
echo.

echo ============================================================
echo DEPLOYMENT COMPLETE
echo ============================================================
echo Stable version is now running in the background.
echo.

exit /b 0
