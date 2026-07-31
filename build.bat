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
    echo [1/7] Cleaning old build...
    rmdir /s /q "%DIST%"
)

:: Step 2: Build Tauri frontend
echo [2/7] Building frontend (Tauri)...
cd /d "%ROOT%\app"
call npx tauri build
if %ERRORLEVEL% neq 0 (
    echo Frontend build failed!
    exit /b 1
)

:: Step 3: Build the graphical launcher
echo [3/7] Building launcher (Tauri)...
cd /d "%ROOT%\launcher"
call "%ROOT%\app\node_modules\.bin\tauri.cmd" build
if %ERRORLEVEL% neq 0 (
    echo Launcher build failed!
    exit /b 1
)

:: Step 4: Build backend with PyInstaller
echo [4/7] Building backend (PyInstaller)...
cd /d "%ROOT%"
call .venv\Scripts\python.exe -m PyInstaller pyinstaller.spec --distpath "%DIST%" --workpath "%DIST%\build-temp" --clean --noconfirm
if %ERRORLEVEL% neq 0 (
    echo Backend build failed!
    exit /b 1
)

:: Step 5: Collect output
echo [5/7] Collecting build output...

set "TAURI_EXE=%ROOT%\app\src-tauri\target\release\app.exe"
set "LAUNCHER_EXE=%ROOT%\launcher\src-tauri\target\release\hsl-launcher.exe"

if exist "%TAURI_EXE%" (
    copy /y "%TAURI_EXE%" "%DIST%\hsl-app.exe" >nul
    echo   - hsl-app.exe - frontend
) else (
    echo   WARNING: Tauri exe not found
)

if exist "%LAUNCHER_EXE%" (
    copy /y "%LAUNCHER_EXE%" "%DIST%\HSL2-Launcher.exe" >nul
    echo   - HSL2-Launcher.exe - graphical launcher
) else (
    echo   ERROR: Launcher exe not found
    exit /b 1
)

:: Copy USAGE
if exist "%ROOT%\USAGE.md" (
    copy /y "%ROOT%\USAGE.md" "%DIST%\USAGE.md" >nul
    echo   - USAGE.md - usage guide
)

:: Copy LICENSE
if exist "%ROOT%\LICENSE" (
    copy /y "%ROOT%\LICENSE" "%DIST%\LICENSE" >nul
    echo   - LICENSE - GPL v3
)

:: Clean up build temp directory
if exist "%DIST%\build-temp" (
    echo   Cleaning build temp...
    rmdir /s /q "%DIST%\build-temp"
)

:: Step 6: Package as zip
echo [6/7] Packaging to zip...
set "ZIP_NAME=HSL2-Release.zip"
cd /d "%ROOT%"
if exist "%ZIP_NAME%" del /q "%ZIP_NAME%"
powershell -Command "Compress-Archive -Path '%DIST%\*' -DestinationPath '%ZIP_NAME%' -Force"
echo   - %ZIP_NAME%

:: Step 7: Build the Windows installer when Inno Setup is available
echo [7/7] Building Windows installer...
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if exist "%ISCC%" (
    call "%ISCC%" "%ROOT%\installer_build.iss"
    if !ERRORLEVEL! neq 0 (
        echo Installer build failed!
        exit /b 1
    )
) else (
    echo   WARNING: Inno Setup 6 was not found; installer generation was skipped.
)

echo.
echo ============================================
echo  Build complete!
echo  Output: %DIST%
echo  Run "%DIST%\HSL2-Launcher.exe" to launch
echo ============================================

endlocal
