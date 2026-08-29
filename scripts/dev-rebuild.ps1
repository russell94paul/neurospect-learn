# Starts the rebuild helper the Settings -> Developer button talks to.
#
# Runs on the HOST on purpose: rebuilding containers from inside a container
# would mean mounting the Docker socket, which is root on this machine, into a
# service that is published through the tunnel. See scripts/dev-rebuild.mjs.
#
#   .\scripts\dev-rebuild.ps1
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
Write-Host "Starting dev-rebuild helper on http://127.0.0.1:5199 ..." -ForegroundColor Cyan
node scripts/dev-rebuild.mjs
