<#
    The on/off switch for the twice-daily desktop alerts.

    Run it once to turn the alerts off, again to turn them back on. It reports
    the new state in a dialog box, so a click always tells you where you stand.

    The cloud checks keep running either way - this only controls whether your
    PC pops up notifications. Nothing is lost while alerts are off; the
    dashboard stays current and you will be told about anything still open the
    next time you switch them on.
#>

param([string] $TaskName = "Vacancy alerts")

Add-Type -AssemblyName System.Windows.Forms

function Show-Result {
    param([string] $Text, [string] $Title, [string] $Icon)
    [System.Windows.Forms.MessageBox]::Show(
        $Text, $Title,
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::$Icon) | Out-Null
}

$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $task) {
    Show-Result -Title "Vacancy alerts" -Icon Warning -Text @"
The scheduled task "$TaskName" does not exist.

Register it by running this in the project folder:

    powershell -ExecutionPolicy Bypass -File .\install_alert_task.ps1
"@
    exit 1
}

try {
    if ($task.State -eq "Disabled") {
        Enable-ScheduledTask -TaskName $TaskName | Out-Null
        $times = ($task.Triggers | ForEach-Object {
            ([datetime]$_.StartBoundary).ToString("HH:mm")
        }) -join " and "
        Show-Result -Title "Vacancy alerts" -Icon Information -Text @"
Alerts are now ON.

You will get a desktop notification at $times daily whenever a vacancy is
new or a deadline is approaching.

Click this switch again to turn them off.
"@
    }
    else {
        Disable-ScheduledTask -TaskName $TaskName | Out-Null
        Show-Result -Title "Vacancy alerts" -Icon Information -Text @"
Alerts are now OFF.

No more desktop notifications until you switch them back on. The twice-daily
cloud check keeps running, so the dashboard stays up to date:

    https://rav054.github.io/vacancy-bot/

Click this switch again to turn alerts back on.
"@
    }
}
catch {
    Show-Result -Title "Vacancy alerts" -Icon Error -Text @"
Could not change the task state.

$($_.Exception.Message)
"@
    exit 1
}
