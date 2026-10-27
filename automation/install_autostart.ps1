# Registers SanStudio AutoStart in Windows Task Scheduler.
#
#   .\install_autostart.ps1               start when you log in to Windows (no admin needed)
#   .\install_autostart.ps1 -AtStartup    start when Windows boots, even if nobody logs in
#                                         (run PowerShell as Administrator; asks for your Windows password)
param([switch]$AtStartup)

$ErrorActionPreference = "Stop"
$TaskName = "SanStudio AutoStart"
$Script   = Join-Path $PSScriptRoot "autostart.py"

$pyw = Get-Command pythonw -ErrorAction SilentlyContinue
if (-not $pyw) { throw "pythonw.exe not found. Install Python first (python.org or winget)." }
if (-not (Test-Path (Join-Path $PSScriptRoot "config.json"))) { throw "config.json is missing next to this script." }

$action   = New-ScheduledTaskAction -Execute $pyw.Source -Argument "`"$Script`"" -WorkingDirectory $PSScriptRoot
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
    -MultipleInstances IgnoreNew

if ($AtStartup) {
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $trigger.Delay = "PT1M"   # give the network a minute after boot
    $cred = Get-Credential -UserName "$env:USERDOMAIN\$env:USERNAME" -Message "Your Windows password (needed to run before login)"
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
        -User $cred.UserName -Password $cred.GetNetworkCredential().Password -RunLevel Limited -Force | Out-Null
} else {
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
}

Start-ScheduledTask -TaskName $TaskName
Write-Host ""
Write-Host "Installed and started '$TaskName'." -ForegroundColor Green
Write-Host "Log file: $(Join-Path $PSScriptRoot 'automation.log')"
