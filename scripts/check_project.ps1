$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "Checking for likely API keys..."
if (Get-Command rg -ErrorAction SilentlyContinue) {
  rg "sk-[A-Za-z0-9_-]{20,}" .
  if ($LASTEXITCODE -eq 0) {
    throw "Potential API key found. Review before committing."
  }
} else {
  Write-Host "ripgrep not found; skipping key scan."
}

Write-Host "Running workflow smoke test..."
.\scripts\run_demo.ps1

Write-Host "Checking Git status..."
git status --short
