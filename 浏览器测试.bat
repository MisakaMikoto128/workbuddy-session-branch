@echo off
chcp 65001 >nul
title 会话分支管理器 - 浏览器测试服务
setlocal

set PY=C:\Users\liuyu\.workbuddy-ai\binaries\python\envs\default\Scripts\python.exe
if not exist "%PY%" set PY=python

echo 服务已启动，浏览器打开： http://127.0.0.1:8777/
echo 测试完成后关闭此窗口即可。
start "" http://127.0.0.1:8777/
"%PY%" "%~dp0src\serve.py" --port 8777
endlocal
