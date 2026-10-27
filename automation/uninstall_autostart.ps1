# Stops and removes SanStudio AutoStart from Task Scheduler.
$TaskName = "SanStudio AutoStart"

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed '$TaskName'."
} else {
    Write-Host "'$TaskName' is not installed."
}

# Stopping the task kills only autostart itself; also stop the server/tunnel it started.
$pidsFile = Join-Path $PSScriptRoot "pids.json"
if (Test-Path $pidsFile) {
    $pids = Get-Content $pidsFile -Raw | ConvertFrom-Json
    foreach ($p in $pids.PSObject.Properties) {
        $proc = Get-Process -Id ([int]$p.Name) -ErrorAction SilentlyContinue
        if ($proc -and ($proc.Name + ".exe") -ieq $p.Value) {
            Stop-Process -Id $proc.Id -Force
            Write-Host "Stopped $($p.Value) (pid $($p.Name))"
        }
    }
    Remove-Item $pidsFile
}
