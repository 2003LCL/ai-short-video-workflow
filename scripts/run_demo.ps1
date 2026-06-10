$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$BundledPython = "C:\Users\LCL\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if (Test-Path $BundledPython) {
  $Python = $BundledPython
} else {
  $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
  if (-not $PythonCommand) {
    throw "Python was not found. Install Python or run this inside Codex Desktop."
  }
  $Python = $PythonCommand.Source
}

& $Python .\run_workflow.py --demo-assets --refresh-demo-assets --clean --skip-tts

Write-Host ""
Write-Host "Done. Open output\preview.html or output\preview.gif to inspect the result."
