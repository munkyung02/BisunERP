@echo off
chcp 65001 > nul
cd /d "%~dp0"
python bisun_preflight_check.py
pause
