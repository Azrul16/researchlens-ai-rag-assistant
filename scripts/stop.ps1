$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$statePath = Join-Path $projectRoot '.logs\processes.json'
if (-not (Test-Path -LiteralPath $statePath)) { Write-Output 'No recorded servers.'; return }
$state = Get-Content -LiteralPath $statePath | ConvertFrom-Json
$allProcesses = Get-CimInstance Win32_Process
foreach ($entry in @(@{name='backend'; id=$state.backend}, @{name='frontend'; id=$state.frontend})) {
    $parent = $allProcesses | Where-Object ProcessId -eq $entry.id
    if (-not $parent) { continue }
    $valid = if ($entry.name -eq 'backend') {
        $parent.CommandLine -like "*$projectRoot\.venv\Scripts\python.exe*" -and $parent.CommandLine -like '*uvicorn*app.main:app*'
    } else {
        ($parent.CommandLine -like '*node_modules/next/dist/bin/next*' -or $parent.CommandLine -like "*$projectRoot\frontend\.next\standalone\server.js*") -and $parent.Name -eq 'node.exe'
    }
    if (-not $valid) { throw "Recorded $($entry.name) PID belongs to another process; refusing to stop it." }
    $children = $allProcesses | Where-Object ParentProcessId -eq $parent.ProcessId
    foreach ($child in $children) { Stop-Process -Id $child.ProcessId -Force -ErrorAction SilentlyContinue }
    Stop-Process -Id $parent.ProcessId -Force -ErrorAction SilentlyContinue
}
Remove-Item -LiteralPath $statePath
Write-Output 'ResearchLens servers stopped.'
