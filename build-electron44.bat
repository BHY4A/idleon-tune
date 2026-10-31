@echo off
cd /d "%~dp0"
python runtime.py build %*
pause
