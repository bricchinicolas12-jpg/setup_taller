@echo off
REM Ir a la carpeta del proyecto
cd /d "%~dp0"
start http://192.168.100.49:5000
REM Ejecutar Flask con el Python REAL
"C:\Users\nicolas\AppData\Local\Python\pythoncore-3.14-64\python.exe" app.py

REM Cuando cierres Flask, la consola se queda para ver mensajes
pause

