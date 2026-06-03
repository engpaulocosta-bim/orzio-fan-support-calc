; =============================================================================
; SFSC — Steel Fan Support Calc
; Inno Setup 6 script
;
; Para gerar o instalador:
;   1. Instalar Inno Setup 6 em https://jrsoftware.org/isdl.php
;   2. Abrir este ficheiro no Inno Setup IDE
;   3. Ctrl+F9 para compilar  OU  executar:
;       "C:\Program Files (x86)\Inno Setup 6\iscc.exe" sfsc_installer.iss
;
; Pré-requisito: PyInstaller já compilou a pasta dist\SFSC\
; =============================================================================

#define MyAppName       "SFSC - Steel Fan Support Calc"
#define MyAppVersion    "1.0.0"
#define MyAppPublisher  "Tensor - Construcao Civil Lda"
#define MyAppURL        "https://orzio.app"
#define MyAppExeName    "SFSC.exe"
#define MyDistDir       "..\dist\SFSC"
#define MyIconFile      "sfsc.ico"

[Setup]
AppId={{E8A3C1F2-4D57-4B89-9A6E-2C1F3D4E5F60}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\SFSC
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
LicenseFile=
PrivilegesRequired=lowest
OutputDir=..\dist\installer
OutputBaseFilename=SFSC_Setup_v{#MyAppVersion}
SetupIconFile={#MyIconFile}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
WizardResizable=yes
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Installer
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "portuguese"; MessagesFile: "compiler:Languages\Portuguese.isl"

[Tasks]
Name: "desktopicon";     Description: "{cm:CreateDesktopIcon}";     GroupDescription: "{cm:AdditionalIcons}"
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode

[Files]
; Toda a pasta compilada pelo PyInstaller
Source: "{#MyDistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Menu Iniciar
Name: "{group}\{#MyAppName}";            Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"

; Desktop
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Lançar a aplicação após instalação
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "taskkill.exe"; Parameters: "/F /IM {#MyAppExeName}"; Flags: runhidden skipifdoesntexist

[Code]
// Fechar instâncias em execução antes de instalar
function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
begin
  Exec('taskkill.exe', '/F /IM SFSC.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := True;
end;
