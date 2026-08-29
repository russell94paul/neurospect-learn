# Start the remote-access tunnel on the STABLE hostname (2026-08-20).
#
#   .\scripts\tunnel.ps1            # start it
#   .\scripts\tunnel.ps1 -Status    # is it up, and on what URL
#   .\scripts\tunnel.ps1 -Stop      # stop it
#   .\scripts\tunnel.ps1 -Install   # run automatically at logon (Task Scheduler)
#   .\scripts\tunnel.ps1 -Uninstall # remove that
#
# Replaced the `cloudflared tunnel --url` quick tunnel, whose hostname was random
# and changed on every restart. ngrok's free plan includes ONE reserved domain,
# which is what makes the URL stable; the hostname lives in `.tunnel-domain`
# (gitignored — it is this machine's front door, not source).
#
# It points at :5175, the Basic-auth listener, NEVER :5174. :5174 is the desk
# stack with no password on it. See app/nginx.conf.

[CmdletBinding()]
param(
    [switch]$Status,
    [switch]$Stop,
    [switch]$Install,
    [switch]$Uninstall
)

$ErrorActionPreference = 'Stop'

$repo       = Split-Path -Parent $PSScriptRoot
$domainFile = Join-Path $repo '.tunnel-domain'
$logFile    = Join-Path $repo '.tunnel.log'
$errFile    = Join-Path $repo '.tunnel.out.log'
$taskName   = 'neurospect-learn-tunnel'
$ngrok      = Join-Path $env:APPDATA 'npm\node_modules\ngrok\bin\ngrok.exe'
$port       = 5175

function Get-Domain {
    if (-not (Test-Path $domainFile)) {
        throw "No .tunnel-domain file. Claim the free static domain at https://dashboard.ngrok.com/domains and write it (e.g. neurospect-learn.ngrok-free.app) into $domainFile"
    }
    $d = (Get-Content $domainFile | Where-Object { $_.Trim() -and -not $_.StartsWith('#') } | Select-Object -First 1).Trim()
    if (-not $d) { throw "$domainFile is empty." }
    # Accept a pasted URL as well as a bare hostname.
    return ($d -replace '^https?://', '').TrimEnd('/')
}

function Get-TunnelProcess {
    Get-CimInstance Win32_Process -Filter "Name = 'ngrok.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match [regex]::Escape($port) }
}

if ($Status) {
    $p = Get-TunnelProcess
    if ($p) { "UP   pid $($p.ProcessId)  https://$(Get-Domain)  ->  localhost:$port" }
    else    { "DOWN (start it with .\scripts\tunnel.ps1)" }
    return
}

if ($Stop) {
    $p = Get-TunnelProcess
    if (-not $p) { "Not running."; return }
    # Scoped to the ngrok process serving THIS port on purpose — never a blanket
    # `Stop-Process -Name ngrok`, which would take out another project's tunnel.
    Stop-Process -Id $p.ProcessId -Force
    "Stopped pid $($p.ProcessId)."
    return
}

if ($Uninstall) {
    if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
        "Removed the logon task '$taskName'."
    } else { "No logon task '$taskName' registered." }
    return
}

if ($Install) {
    $domain = Get-Domain   # fail before registering anything if it is missing
    $action  = New-ScheduledTaskAction -Execute 'powershell.exe' `
                 -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$PSCommandPath`"" `
                 -WorkingDirectory $repo
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
    # Runs as the logged-in user, no elevation, and is allowed to run on battery —
    # the default power settings would otherwise stop the tunnel when unplugged,
    # which is exactly when access-away-from-the-desk matters.
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
                  -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
    "Registered '$taskName' — https://$domain comes up at logon."
    return
}

# --- start ---------------------------------------------------------------
$domain = Get-Domain

if (Get-TunnelProcess) { "Already running. .\scripts\tunnel.ps1 -Status"; return }
if (-not (Test-Path $ngrok)) { throw "ngrok not found at $ngrok" }

# Refuse to publish a port that is not answering — an ngrok endpoint in front of
# a dead nginx is a public 502, and the failure would look like the tunnel's.
try {
    $probe = Invoke-WebRequest "http://localhost:$port/" -UseBasicParsing -TimeoutSec 5
} catch [System.Net.WebException] {
    $probe = $_.Exception.Response
}
if (-not $probe) { throw "Nothing answering on localhost:$port — start the stack first (docker compose up -d)." }

Start-Process -FilePath $ngrok `
    -ArgumentList 'http', $port, '--url', "https://$domain", '--log', 'stdout' `
    -RedirectStandardOutput $logFile -RedirectStandardError $errFile `
    -WindowStyle Hidden | Out-Null

Start-Sleep -Seconds 3
$p = Get-TunnelProcess
if ($p) { "UP   pid $($p.ProcessId)  https://$domain" }
else    { "FAILED to start — see $logFile"; Get-Content $logFile -Tail 15 }
