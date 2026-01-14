@echo off
REM Deployment script for radioToolsAutomation
REM Uses PowerShell for reliable process management

echo.
echo ============================================================
echo DEPLOYMENT: radioToolsAutomation
echo ============================================================
echo.

set "ACTIVE_ROOT=%~dp0"
set "ACTIVE_ROOT=%ACTIVE_ROOT:~0,-1%"
set "STABLE_ROOT=%ACTIVE_ROOT% - stable"

echo Active: %ACTIVE_ROOT%
echo Stable: %STABLE_ROOT%
echo.

REM Step 1: Kill running instances using PowerShell
echo [1/3] Stopping running instances...
powershell -Command "if (Get-Process pythonw -ErrorAction SilentlyContinue) { Stop-Process -Name pythonw -Force; Write-Host '      Stopped pythonw.exe'; Start-Sleep -Seconds 2 } else { Write-Host '      No pythonw.exe running' }"
powershell -Command "if (Get-Process python -ErrorAction SilentlyContinue) { Stop-Process -Name python -Force; Write-Host '      Stopped python.exe'; Start-Sleep -Seconds 1 } else { Write-Host '      No python.exe running' }"
echo.

REM Step 2: Run deployment
echo [2/3] Deploying...
cd /d "%ACTIVE_ROOT%"
python deploy.py --full
if errorlevel 1 (
    echo.
    echo ERROR: Deployment failed!
    pause
    exit /b 1
)
echo.

REM Step 3: Start stable version
echo [3/3] Starting stable version...
powershell -Command "Start-Process pythonw -ArgumentList '%STABLE_ROOT%\src\main_app.py' -WorkingDirectory '%STABLE_ROOT%'"
timeout /t 2 /nobreak >nul

REM Verify
powershell -Command "if (Get-Process pythonw -ErrorAction SilentlyContinue) { Write-Host '      App running' } else { Write-Host '      WARNING: App may not have started' }"
echo.

echo ============================================================
echo DEPLOYMENT COMPLETE
echo ============================================================
echo.

exit /b 0
