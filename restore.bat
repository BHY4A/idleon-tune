@echo off
cd /d "%~dp0"
python patcher.py restore %*
pause
