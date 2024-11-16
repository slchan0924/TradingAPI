@echo off
start cmd /k "python python/launcher.py"
timeout /t 5
start http://127.0.0.1:5000