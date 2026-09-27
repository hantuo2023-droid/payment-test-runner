$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $ProjectRoot
$PythonExe = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $PythonExe)) { throw 'Create .venv and install backend/requirements.txt first. See README.md.' }
if (Test-Path -LiteralPath (Join-Path $ProjectRoot 'test-output\browsers')) { $env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $ProjectRoot 'test-output\browsers' }
New-Item -ItemType Directory -Force -Path (Join-Path $ProjectRoot 'data') | Out-Null
& $PythonExe -m backend.cli migrate
& $PythonExe -c "from backend.store import rows; raise SystemExit(0 if rows('SELECT 1 FROM settings WHERE key=CHAR(97,100,109,105,110,95,112,97,115,115,119,111,114,100)') else 1)"
if ($LASTEXITCODE -ne 0) { & $PythonExe -m backend.cli init-admin }
if ($LASTEXITCODE -ne 0) { throw 'Administrator initialization failed.' }
$NodeExe = (Get-Command node).Source
$Backend = Start-Process -FilePath $PythonExe -ArgumentList '-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','8000' -WorkingDirectory $ProjectRoot -WindowStyle Hidden -PassThru
$Sandbox = Start-Process -FilePath $PythonExe -ArgumentList '-m','uvicorn','sandbox.app:app','--host','127.0.0.1','--port','8080' -WorkingDirectory $ProjectRoot -WindowStyle Hidden -PassThru
$Frontend = Start-Process -FilePath $NodeExe -ArgumentList 'node_modules/next/dist/bin/next','dev','--hostname','127.0.0.1','--port','3000' -WorkingDirectory (Join-Path $ProjectRoot 'frontend') -WindowStyle Hidden -PassThru
Write-Host "Web URL: http://127.0.0.1:3000"
Write-Host "Process IDs: backend=$($Backend.Id), sandbox=$($Sandbox.Id), frontend=$($Frontend.Id)"
Write-Host 'Press Enter to stop all three services.'
Read-Host | Out-Null
foreach ($ServiceProcess in @($Frontend,$Backend,$Sandbox)) { if (-not $ServiceProcess.HasExited) { & taskkill /PID $ServiceProcess.Id /T /F | Out-Null } }
