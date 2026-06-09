@echo off
cd /d "%~dp0"
if exist "dist\SFSC.exe" (
    start "" "dist\SFSC.exe"
) else (
    streamlit run app.py --server.port 8502
    pause
)
