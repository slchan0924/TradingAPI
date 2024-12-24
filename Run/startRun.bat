@echo off
start cmd /k "python ..\Python\launcher:app"
timeout /t 5
start http://127.0.0.1:5000