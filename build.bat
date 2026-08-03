@echo off
setlocal enabledelayedexpansion

echo ============================================
echo  Hikari Server Launcher - Build Script
echo ============================================
echo.

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "DIST=%ROOT%\dist"

:: Step 1: Refuse to package source that fails the release quality gates.
echo [1/8] Running release preflight checks...
cd /d "%ROOT%"
if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Python virtual environment not found. Create .venv and install requirements.txt first.
    exit /b 1
)
call .venv\Scripts\python.exe -m ruff check . --exclude .venv --exclude app --exclude launcher --exclude dist --exclude build
if !ERRORLEVEL! neq 0 (
    echo Backend lint failed!
    exit /b 1
)
call .venv\Scripts\python.exe -m pytest -q
if !ERRORLEVEL! neq 0 (
    echo Backend tests failed!
    exit /b 1
)
cd /d "%ROOT%\app"
call npm run lint
if !ERRORLEVEL! neq 0 (
    echo Frontend lint failed!
    exit /b 1
)
cd /d "%ROOT%\app\src-tauri"
call cargo test --locked
if !ERRORLEVEL! neq 0 (
    echo Frontend native tests failed!
    exit /b 1
)
cd /d "%ROOT%\launcher"
call node --check ui\main.js
if !ERRORLEVEL! neq 0 (
    echo Launcher JavaScript validation failed!
    exit /b 1
)

:: Step 2: Clean previous build
if exist "%DIST%" (
    echo [2/8] Cleaning old build...
    rmdir /s /q "%DIST%"
)

:: Step 3: Build Tauri frontend
echo [3/8] Building frontend (Tauri)...
cd /d "%ROOT%\app"
call npx tauri build --no-bundle
if %ERRORLEVEL% neq 0 (
    echo Frontend build failed!
    exit /b 1
)

:: Step 4: Build the graphical launcher
echo [4/8] Building launcher (Tauri)...
cd /d "%ROOT%\launcher"
call "%ROOT%\app\node_modules\.bin\tauri.cmd" build --no-bundle
if %ERRORLEVEL% neq 0 (
    echo Launcher build failed!
    exit /b 1
)

:: Step 5: Build backend with PyInstaller
echo [5/8] Building backend (PyInstaller)...
cd /d "%ROOT%"
call .venv\Scripts\python.exe -m PyInstaller pyinstaller.spec --distpath "%DIST%" --workpath "%DIST%\build-temp" --clean --noconfirm
if %ERRORLEVEL% neq 0 (
    echo Backend build failed!
    exit /b 1
)

:: Step 6: Collect output
echo [6/8] Collecting build output...

set "TAURI_EXE=%ROOT%\app\src-tauri\target\release\app.exe"
set "LAUNCHER_EXE=%ROOT%\launcher\src-tauri\target\release\hsl-launcher.exe"

if exist "%TAURI_EXE%" (
    copy /y "%TAURI_EXE%" "%DIST%\hsl-app.exe" >nul
    echo   - hsl-app.exe - frontend
) else (
    echo   ERROR: Tauri frontend executable not found: %TAURI_EXE%
    exit /b 1
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

:: Refuse to package a partial or malformed release tree.
if not exist "%DIST%\HSL2-Launcher.exe" (
    echo   ERROR: Release validation failed: launcher is missing
    exit /b 1
)
if not exist "%DIST%\hsl-app.exe" (
    echo   ERROR: Release validation failed: frontend is missing
    exit /b 1
)
if not exist "%DIST%\hsl-server\hsl-server.exe" (
    echo   ERROR: Release validation failed: backend is missing
    exit /b 1
)
if not exist "%DIST%\LICENSE" (
    echo   ERROR: Release validation failed: license is missing
    exit /b 1
)

:: Clean up build temp directory
if exist "%DIST%\build-temp" (
    echo   Cleaning build temp...
    rmdir /s /q "%DIST%\build-temp"
)

:: Step 7: Package as zip
echo [7/8] Packaging to zip...
set "ZIP_NAME=HSL2-Release.zip"
cd /d "%ROOT%"
if exist "%ZIP_NAME%" del /q "%ZIP_NAME%"
powershell -Command "Compress-Archive -Path '%DIST%\*' -DestinationPath '%ZIP_NAME%' -Force"
echo   - %ZIP_NAME%

:: Step 8: Build the Windows installer when Inno Setup is available
echo [8/8] Building Windows installer...
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if exist "%ISCC%" (
    call "%ISCC%" "%ROOT%\installer_build.iss"
    if !ERRORLEVEL! neq 0 (
        echo Installer build failed!
        exit /b 1
    )
) else (
    echo   ERROR: Inno Setup 6 was not found; a complete release installer cannot be generated.
    exit /b 1
)

echo.
echo ============================================
echo  Build complete!
echo  Output: %DIST%
echo  Run "%DIST%\HSL2-Launcher.exe" to launch
echo ============================================

endlocal
