@echo off
chcp 65001 >nul
title 会话分支管理器
setlocal

set PY=C:\Users\liuyu\.workbuddy-ai\binaries\python\envs\default\Scripts\pythonw.exe
if not exist "%PY%" set PY=pythonw

start "" "%PY%" "%~dp0src\app.py"
endlocal
