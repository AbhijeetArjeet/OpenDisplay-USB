@echo off
:: OpenDisplay USB - Phase 4 Virtual Display Driver Installer
:: Requires Administrator privileges to install the virtual monitor driver into Windows

net session >nul 2>&1
if %errorLevel% == 0 (
    echo [OK] Running with Administrator privileges.
) else (
    echo Requesting Administrator elevation...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"

echo ========================================================
echo   OpenDisplay USB - Phase 4 Virtual Display Installer
echo ========================================================
echo.
echo Installing signed Virtual Display Driver (IddCx)...
start /wait "" "%~dp0Virtual.Display.Driver-v25.05.03-setup-x64.exe" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART

:: Update settings to include 2000x1200 native tablet resolution
if not exist "C:\VirtualDisplayDriver" (
    mkdir "C:\VirtualDisplayDriver"
)
copy /Y "%~dp0driver\vdd_settings.xml" "C:\VirtualDisplayDriver\vdd_settings.xml" >nul 2>&1

:: Create device node and install driver
if exist "C:\VirtualDisplayDriver\nefconw.exe" (
    cd /d "C:\VirtualDisplayDriver"
    nefconw.exe --create-device-node --hardware-id Root\MttVDD --class-name Display --class-guid 4D36E968-E325-11CE-BFC1-08002BE10318
    nefconw.exe --install-driver --inf-path "C:\VirtualDisplayDriver\MttVDD.inf"
)

echo.
echo ========================================================
echo   [SUCCESS] Virtual Display Driver Installed!
echo.
echo   Press Win + P and choose "Extend" to enable your
echo   tablet as an independent secondary desktop!
echo ========================================================
echo.
pause
