; Instalador do Bússola PDV para Windows — Inno Setup 6.
;
; Gera um único `BussolaPDV-<versão>-setup.exe` que instala a pasta produzida
; pelo PyInstaller (dist\BussolaPDV), cria atalhos e registra a desinstalação em
; "Aplicativos e recursos". É instalador .exe; para .msi existe o caminho
; alternativo com WiX descrito em docs/INSTALACAO_WINDOWS.md.
;
; Compilar:
;   ISCC.exe /DAppVersion=0.4.0 empacotamento\instalador.iss
;
; Decisões:
;  * Instalação por usuário (PrivilegesRequired=lowest): não pede senha de
;    administrador, o que é a realidade de balcão de loja. Instala em
;    %LOCALAPPDATA%\Programs, que não exige UAC.
;  * A pasta do programa é ESCOLHIDA na tela "Selecionar pasta de destino"
;    (DisableDirPage=no). O padrão continua sendo %LOCALAPPDATA%\Programs, mas
;    quem quiser outra unidade (D:\Programas\BussolaPDV) troca ali.
;  * Os dados NUNCA ficam na pasta do programa: ficam em %LOCALAPPDATA%\BussolaPDV.
;    Por isso a desinstalação não apaga a base por padrão — só remove o programa.
;  * Sem tarefa agendada, sem serviço, sem acesso à rede: o app é offline.

#ifndef AppVersion
  #define AppVersion "0.6.1"
#endif
#define AppName "Bússola Sistema PDV"
#define AppShortName "BussolaPDV"
#define AppPublisher "Bússola Sistema PDV Open Source"
#define AppUrl "https://github.com/davidcreator/bussolapdv"
#define AppExe "BussolaPDV.exe"

[Setup]
AppId={{5C0F1F6B-5B72-4E32-9F5E-6C31D0A4B701}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppUrl}
AppSupportURL={#AppUrl}/issues
AppUpdatesURL={#AppUrl}/releases
VersionInfoVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription=Instalador do {#AppName}
VersionInfoCopyright=GPL-2.0-or-later
DefaultDirName={localappdata}\Programs\{#AppShortName}
; Escolher onde o PROGRAMA fica é decisão de quem instala (outra unidade, por
; exemplo). Onde ficam os DADOS é escolhido no primeiro uso do app — e é lá que
; ficam base, cópias, relatórios e logs.
DisableDirPage=no
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist\instalador
OutputBaseFilename={#AppShortName}-{#AppVersion}-setup
SetupIconFile=bussola.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
LicenseFile=..\LICENSE
InfoBeforeFile=AVISO.txt
; Sem assinatura digital: o SmartScreen vai avisar no primeiro uso. Ver docs.

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na &Área de Trabalho"; GroupDescription: "Atalhos:"; Flags: unchecked
Name: "quicklaunchicon"; Description: "Criar atalho na barra de &tarefas"; GroupDescription: "Atalhos:"; Flags: unchecked

[Files]
Source: "..\dist\{#AppShortName}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "AVISO.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "LEIA-ME.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"; Comment: "Abrir o PDV"
Name: "{group}\Pasta de dados (banco e cópias)"; Filename: "%LOCALAPPDATA%\BussolaPDV"
Name: "{group}\Desinstalar {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: quicklaunchicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Abrir o {#AppName} agora"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Nada da base do usuário é apagado aqui de propósito. Ver "Desinstalação" no
; docs/INSTALACAO_WINDOWS.md: a cópia de segurança é responsabilidade da loja.

[Code]
// Aviso honesto na primeira tela: o programa não é fiscal e não está homologado.
procedure InitializeWizard();
begin
  WizardForm.WelcomeLabel2.Caption :=
    'Este assistente instala o Bússola Sistema PDV (versão {#AppVersion}) no seu usuário.' + #13#10 + #13#10 +
    'O programa é offline, não emite documento fiscal e ainda está em pré-alfa: ' +
    'não use como único sistema de uma loja em operação.' + #13#10 + #13#10 +
    'A base de dados fica em %LOCALAPPDATA%\BussolaPDV e sobrevive à desinstalação.';
end;
