@echo off
if "%~1"=="" (
    echo Usage: commit.bat "Your commit message"
    exit /b 1
)

git add .
git commit -m "%~1"
git push

pause
