@echo off
echo.
echo  ============================================
echo   SFSC - Steel Fan Support Calc
echo   Instalador
echo  ============================================
echo.
PowerShell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
if %ERRORLEVEL% neq 0 (
    echo.
    echo  ERRO na instalacao. Verifique as mensagens acima.
    pause
)
