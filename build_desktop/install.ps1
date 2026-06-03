#Requires -Version 5.1
<#
.SYNOPSIS
  Instala o SFSC — Steel Fan Support Calc na máquina do utilizador.

.DESCRIPTION
  - Copia a pasta dist\SFSC para %LOCALAPPDATA%\SFSC
  - Cria atalho no Desktop com ícone
  - Cria atalho no Menu Iniciar
  - Cria entrada no registo para Adicionar/Remover Programas

  Não requer privilégios de administrador (instalação perUser).

.PARAMETER Uninstall
  Se passado, desinstala o SFSC.
#>
param(
    [switch] $Uninstall
)

$ErrorActionPreference = 'Stop'

$AppName    = "SFSC - Steel Fan Support Calc"
$AppVersion = "1.0.0"
$Publisher  = "Tensor - Construcao Civil Lda"
$AppId      = "SFSC_TensorCCL"

$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot   = Split-Path -Parent $ScriptDir
$DistDir    = Join-Path $RepoRoot "dist\SFSC"
$InstallDir = Join-Path $env:LOCALAPPDATA "SFSC"
$ExePath    = Join-Path $InstallDir "SFSC.exe"
$IconPath   = Join-Path $ScriptDir "sfsc.ico"

$DesktopLink  = Join-Path ([Environment]::GetFolderPath("Desktop")) "$AppName.lnk"
$StartMenuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\SFSC"
$StartLink    = Join-Path $StartMenuDir "$AppName.lnk"

$RegKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\$AppId"


function Write-Step([string] $msg) {
    Write-Host ""
    Write-Host "  >> $msg" -ForegroundColor Cyan
}

function New-Shortcut([string] $linkPath, [string] $targetPath, [string] $iconPath, [string] $description) {
    $wsh    = New-Object -ComObject WScript.Shell
    $lnk    = $wsh.CreateShortcut($linkPath)
    $lnk.TargetPath       = $targetPath
    $lnk.WorkingDirectory = Split-Path -Parent $targetPath
    $lnk.IconLocation     = "$iconPath,0"
    $lnk.Description      = $description
    $lnk.Save()
}


# ════════════════════════════════════════════════════════════════════════════
# DESINSTALAR
# ════════════════════════════════════════════════════════════════════════════
if ($Uninstall) {
    Write-Host ""
    Write-Host "  Desinstalando $AppName..." -ForegroundColor Yellow

    # Fechar a aplicação se estiver aberta
    Get-Process -Name "SFSC" -ErrorAction SilentlyContinue | Stop-Process -Force

    # Remover ficheiros
    if (Test-Path $InstallDir) {
        Write-Step "Remover ficheiros de $InstallDir"
        Remove-Item $InstallDir -Recurse -Force
    }

    # Remover atalhos
    if (Test-Path $DesktopLink) { Remove-Item $DesktopLink -Force; Write-Step "Atalho Desktop removido" }
    if (Test-Path $StartMenuDir) { Remove-Item $StartMenuDir -Recurse -Force; Write-Step "Menu Iniciar removido" }

    # Remover registo
    if (Test-Path $RegKey) { Remove-Item $RegKey -Force; Write-Step "Registo removido" }

    Write-Host ""
    Write-Host "  $AppName desinstalado com sucesso." -ForegroundColor Green
    return
}


# ════════════════════════════════════════════════════════════════════════════
# INSTALAR
# ════════════════════════════════════════════════════════════════════════════
Write-Host ""
Write-Host "  Instalando $AppName v$AppVersion" -ForegroundColor Green
Write-Host "  Publisher: $Publisher"
Write-Host ""

# Verificar que o build existe
if (-not (Test-Path $DistDir)) {
    Write-Host "  ERRO: pasta de build nao encontrada: $DistDir" -ForegroundColor Red
    Write-Host "  Execute primeiro: pyinstaller build_desktop/sfsc.spec --noconfirm" -ForegroundColor Yellow
    exit 1
}

# Fechar instâncias em execução
Write-Step "Verificar instâncias em execução"
Get-Process -Name "SFSC" -ErrorAction SilentlyContinue | Stop-Process -Force

# Copiar ficheiros
Write-Step "Copiar ficheiros para $InstallDir"
if (Test-Path $InstallDir) { Remove-Item $InstallDir -Recurse -Force }
Copy-Item $DistDir $InstallDir -Recurse

# Verificar .exe
if (-not (Test-Path $ExePath)) {
    Write-Host "  ERRO: SFSC.exe nao encontrado em $InstallDir" -ForegroundColor Red
    exit 1
}

# Copiar ícone (se não incluído no bundle)
$IconDest = Join-Path $InstallDir "sfsc.ico"
if ((Test-Path $IconPath) -and (-not (Test-Path $IconDest))) {
    Copy-Item $IconPath $IconDest
}

# Criar atalho Desktop
Write-Step "Criar atalho no Desktop"
New-Shortcut -linkPath $DesktopLink -targetPath $ExePath `
             -iconPath $(if (Test-Path $IconDest) { $IconDest } else { $ExePath }) `
             -description $AppName

# Criar atalho Menu Iniciar
Write-Step "Criar atalho no Menu Iniciar"
New-Item -ItemType Directory -Force $StartMenuDir | Out-Null
New-Shortcut -linkPath $StartLink -targetPath $ExePath `
             -iconPath $(if (Test-Path $IconDest) { $IconDest } else { $ExePath }) `
             -description $AppName

# Registar no Adicionar/Remover Programas
Write-Step "Registar em Adicionar/Remover Programas"
$uninstallCmd = "PowerShell.exe -NoProfile -ExecutionPolicy Bypass -File `"$ScriptDir\install.ps1`" -Uninstall"
$regProps = @{
    DisplayName     = $AppName
    DisplayVersion  = $AppVersion
    Publisher       = $Publisher
    InstallLocation = $InstallDir
    UninstallString = $uninstallCmd
    QuietUninstallString = $uninstallCmd
    DisplayIcon     = $ExePath
    NoModify        = 1
    NoRepair        = 1
    EstimatedSize   = [int]((Get-ChildItem $InstallDir -Recurse | Measure-Object -Property Length -Sum).Sum / 1KB)
}
New-Item -Path $RegKey -Force | Out-Null
foreach ($k in $regProps.Keys) {
    $v = $regProps[$k]
    if ($v -is [int]) {
        Set-ItemProperty -Path $RegKey -Name $k -Value $v -Type DWord
    } else {
        Set-ItemProperty -Path $RegKey -Name $k -Value $v -Type String
    }
}

Write-Host ""
Write-Host "  ============================================" -ForegroundColor Green
Write-Host "  Instalacao concluida!" -ForegroundColor Green
Write-Host "  Instalado em: $InstallDir" -ForegroundColor Green
Write-Host "  Atalho no Desktop: $DesktopLink" -ForegroundColor Green
Write-Host "  ============================================" -ForegroundColor Green
Write-Host ""

# Perguntar se lança agora
$resposta = Read-Host "  Lançar o SFSC agora? (s/N)"
if ($resposta -match '^[sS]') {
    Start-Process $ExePath
}
