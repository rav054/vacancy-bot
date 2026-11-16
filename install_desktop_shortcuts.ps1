<#
    Puts three shortcuts on your Desktop:

      Vacancy - Check Now      runs a full check, shows alerts, opens the dashboard
      Vacancy - Dashboard      opens the published dashboard in your browser
      Vacancy - Alerts On/Off  the switch for the twice-daily desktop alerts

    Run it from this folder:

        powershell -ExecutionPolicy Bypass -File .\install_desktop_shortcuts.ps1

    Delete any shortcut you do not want; nothing else depends on them.
#>

param(
    [string] $DashboardUrl = "https://rav054.github.io/vacancy-bot/"
)

$ErrorActionPreference = "Stop"

$projectDir = $PSScriptRoot
# GetFolderPath handles a Desktop that OneDrive has redirected.
$desktop = [Environment]::GetFolderPath("Desktop")
if (-not (Test-Path $desktop)) { throw "Could not locate your Desktop folder" }
Write-Host "desktop: $desktop"

$shell = New-Object -ComObject WScript.Shell

# --- 1. Check now -------------------------------------------------------
$checkCmd = Join-Path $projectDir "run_check.cmd"
if (-not (Test-Path $checkCmd)) { throw "run_check.cmd not found in $projectDir" }

$lnk = $shell.CreateShortcut((Join-Path $desktop "Vacancy - Check Now.lnk"))
$lnk.TargetPath       = $checkCmd
$lnk.WorkingDirectory = $projectDir
$lnk.Description      = "Check all vacancy sources now, show alerts and open the dashboard"
# Use a real executable's icon rather than guessing an index inside shell32.
$python = (Get-Command python.exe -All -ErrorAction SilentlyContinue |
           Where-Object { $_.Source -notlike "*WindowsApps*" } |
           Select-Object -First 1).Source
if ($python) { $lnk.IconLocation = "$python,0" }
$lnk.Save()
Write-Host "created: Vacancy - Check Now"

# --- 2. Dashboard -------------------------------------------------------
# A .url file picks up the browser's own icon, so it looks like a bookmark.
$urlFile = Join-Path $desktop "Vacancy - Dashboard.url"
@"
[InternetShortcut]
URL=$DashboardUrl
"@ | Set-Content -Path $urlFile -Encoding ascii
Write-Host "created: Vacancy - Dashboard"

# --- 3. Alerts on/off switch -------------------------------------------
$toggle = Join-Path $projectDir "toggle_alerts.ps1"
if (-not (Test-Path $toggle)) { throw "toggle_alerts.ps1 not found in $projectDir" }

$lnk = $shell.CreateShortcut((Join-Path $desktop "Vacancy - Alerts On-Off.lnk"))
$lnk.TargetPath       = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$lnk.Arguments        = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}"' -f $toggle
$lnk.WorkingDirectory = $projectDir
$lnk.Description      = "Turn the twice-daily vacancy alerts on or off"
$lnk.IconLocation     = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe,0"
$lnk.Save()
Write-Host "created: Vacancy - Alerts On-Off"

Write-Host ""
Write-Host "Done. Three shortcuts are on your Desktop."
