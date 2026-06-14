@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%" >nul

if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" -m speeddeploy %*
    set "EXIT_CODE=!ERRORLEVEL!"
    popd >nul
    exit /b !EXIT_CODE!
)

where py >nul 2>nul
if not errorlevel 1 (
    py -m speeddeploy %*
    set "EXIT_CODE=!ERRORLEVEL!"
    popd >nul
    exit /b !EXIT_CODE!
)

echo Python introuvable. Active un virtualenv ou installe Python.
popd >nul
exit /b 1
