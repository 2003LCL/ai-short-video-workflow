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

Write-Host "Running LLM generation tests..."
$BundledPython = "C:\Users\LCL\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if (Test-Path $BundledPython) {
  & $BundledPython .\tests\test_llm_generate.py
} else {
  python .\tests\test_llm_generate.py
}

Write-Host "Running TTS generation tests..."
if (Test-Path $BundledPython) {
  & $BundledPython .\tests\test_tts_generate.py
} else {
  python .\tests\test_tts_generate.py
}

Write-Host "Running MP4 render tests..."
if (Test-Path $BundledPython) {
  & $BundledPython .\tests\test_render_mp4.py
} else {
  python .\tests\test_render_mp4.py
}

Write-Host "Checking Git status..."
git status --short
