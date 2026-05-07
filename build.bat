@echo off
setlocal enabledelayedexpansion

echo ============================================
echo  Hikari Server Launcher - Build Script
echo ============================================
echo.

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "DIST=%ROOT%\dist"

:: Step 1: Clean previous build
if exist "%DIST%" (
    echo [1/5] Cleaning old build...
    rmdir /s /q "%DIST%"
)

:: Step 2: Build Tauri frontend
echo [2/5] Building frontend (Tauri)...
cd /d "%ROOT%\app"
call npx tauri build
if %ERRORLEVEL% neq 0 (
    echo Frontend build failed!
    exit /b 1
)

:: Step 3: Build backend with PyInstaller
echo [3/5] Building backend (PyInstaller)...
cd /d "%ROOT%"
call .venv\Scripts\python.exe -m PyInstaller pyinstaller.spec --distpath "%DIST%" --workpath "%DIST%\build-temp" --clean --noconfirm
if %ERRORLEVEL% neq 0 (
    echo Backend build failed!
    exit /b 1
)

:: Step 4: Collect output
echo [4/5] Collecting build output...

set "TAURI_EXE=%ROOT%\app\src-tauri\target\release\app.exe"

if exist "%TAURI_EXE%" (
    copy /y "%TAURI_EXE%" "%DIST%\hsl-app.exe" >nul
    echo   - hsl-app.exe (frontend)
) else (
    echo   WARNING: Tauri exe not found
)

:: Copy launcher
if exist "%ROOT%\launcher.bat" (
    copy /y "%ROOT%\launcher.bat" "%DIST%\start.bat" >nul
    echo   - start.bat (launcher)
)

:: Copy USAGE
if exist "%ROOT%\USAGE.md" (
    copy /y "%ROOT%\USAGE.md" "%DIST%\USAGE.md" >nul
    echo   - USAGE.md (usage guide)
)

:: Clean up build temp directory
if exist "%DIST%\build-temp" (
    echo   Cleaning build temp...
    rmdir /s /q "%DIST%\build-temp"
)

:: Step 5: Package as zip
echo [5/5] Packaging to zip...
set "ZIP_NAME=HSL2-Release.zip"
cd /d "%ROOT%"
if exist "%ZIP_NAME%" del /q "%ZIP_NAME%"
powershell -Command "Compress-Archive -Path '%DIST%\*' -DestinationPath '%ZIP_NAME%' -Force"
echo   - %ZIP_NAME%

echo.
echo ============================================
echo  Build complete!
echo  Output: %DIST%
echo  Run "%DIST%\start.bat" to launch
echo ============================================

endlocal
