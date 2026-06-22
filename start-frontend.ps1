# Frontend dev server (Windows 11, PowerShell). Run after start-backend.ps1, in a 2nd terminal.
$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\frontend"

npm install
Write-Host ""
Write-Host "  Frontend running ->  http://localhost:3000"
Write-Host ""
npm run dev
