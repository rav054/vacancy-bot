<#
    Registers a Windows scheduled task that pulls the latest cloud result and
    pops up desktop notifications for anything new or closing.

    Run it from this folder:

        powershell -ExecutionPolicy Bypass -File .\install_alert_task.ps1

    It needs no administrator rights: the task is registered for the current
    user only, which is also what makes the toasts appear (a task running as
    SYSTEM has no desktop to show them on).

    Remove it again with:

        Unregister-ScheduledTask -TaskName "Vacancy alerts" -Confirm:$false
#>

param(
    [string] $TaskName = "Vacancy alerts",
    [string] $DashboardUrl = "https://rav054.github.io/vacancy-bot",
    # 15 minutes after each cloud run (which is 08:00 and 16:30 IST).
    [string[]] $Times = @("08:15", "16:45")
)

$ErrorActionPreference = "Stop"

$projectDir = $PSScriptRoot
$script = Join-Path $projectDir "notify_local.py"
if (-not (Test-Path $script)) {
    throw "notify_local.py not found next to this script ($projectDir)"
}

# Prefer the real python.exe over the Microsoft Store alias, which cannot be
# launched by Task Scheduler.
$python = $null
foreach ($candidate in (Get-Command python.exe -All -ErrorAction SilentlyContinue)) {
    if ($candidate.Source -notlike "*WindowsApps*") { $python = $candidate.Source; break }
}
if (-not $python) { throw "Could not find a usable python.exe on PATH" }
Write-Host "python:  $python"
Write-Host "script:  $script"

$logFile = Join-Path $projectDir "data\alerts.log"

# cmd.exe wrapper so stdout and errors land in a log we can read later.
# cmd's rule for /c "..." is: one outer pair, then each path quoted once.
$inner = '"{0}" "{1}" --from-url {2} >> "{3}" 2>&1' -f $python, $script, $DashboardUrl, $logFile
$arguments = '/c "{0}"' -f $inner

$action = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\cmd.exe" `
    -Argument $arguments -WorkingDirectory $projectDir

$triggers = foreach ($t in $Times) {
    New-ScheduledTaskTrigger -Daily -At ([datetime]::ParseExact($t, "HH:mm", $null))
}

# StartWhenAvailable is the important one: if the PC was off or asleep at the
# scheduled time, the check still runs once it comes back, so a deadline is
# never silently missed.
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
    -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive -RunLevel Limited

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Write-Host "replacing the existing '$TaskName' task"
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $triggers `
    -Settings $settings -Principal $principal `
    -Description "Pulls the latest vacancy check from GitHub Pages and shows desktop alerts." | Out-Null

Write-Host ""
Write-Host "Registered '$TaskName' for $($Times -join ' and ') daily."
Write-Host "Log: $logFile"
Write-Host ""
Write-Host "Test it now with:"
Write-Host "    Start-ScheduledTask -TaskName `"$TaskName`""
