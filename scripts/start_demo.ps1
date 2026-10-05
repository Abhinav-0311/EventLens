[CmdletBinding()]
param(
    [ValidateRange(1024, 65535)]
    [int]$Port = 8019,
    [switch]$CheckOnly,
    [switch]$SkipBuild
)

# A recording session is local and uses a new database; existing runs are never reset.
$ErrorActionPreference = 'Stop'
$eventlensRoot = Split-Path -Parent $PSScriptRoot
$eventlensPython = Join-Path $eventlensRoot '.venv/Scripts/python.exe'
$eventlensSavedEnvironment = @{}
foreach ($eventlensName in @('EVENTLENS_DATABASE', 'EVENTLENS_PUBLIC', 'EVENTLENS_WRITE_TOKEN', 'EVENTLENS_ALLOWED_HOSTS')) {
    $eventlensSavedEnvironment[$eventlensName] = [Environment]::GetEnvironmentVariable($eventlensName, 'Process')
}

Push-Location $eventlensRoot
try {
    if (-not (Test-Path -LiteralPath $eventlensPython -PathType Leaf)) {
        throw 'Python environment missing. Complete the README Quickstart first.'
    }
    $eventlensListener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
    try {
        $eventlensListener.Start()
    }
    catch {
        throw "Cannot bind 127.0.0.1:$Port. Choose another port with -Port; do not stop another project's server."
    }
    finally {
        $eventlensListener.Stop()
    }

    if (-not $CheckOnly -and -not $SkipBuild) {
        $eventlensNpm = Get-Command npm.cmd -ErrorAction Stop
        Push-Location (Join-Path $eventlensRoot 'frontend')
        try {
            & $eventlensNpm.Source run build
            if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed; server was not started.' }
        }
        finally { Pop-Location }
    }
    if (-not (Test-Path -LiteralPath (Join-Path $eventlensRoot 'frontend/dist/index.html') -PathType Leaf)) {
        throw 'Frontend build missing. Run this launcher without -CheckOnly or -SkipBuild after npm ci.'
    }

    # Load the pinned local model through production verification. No acquisition or diagnostic corpus download.
    & $eventlensPython -c "from eventlens.config import Settings; from eventlens.sentiment import FinBert; m=FinBert(Settings().model_cache); m.load(); print('Pinned offline model ready:', m.ready); raise SystemExit(0 if m.ready else 1)"
    if ($LASTEXITCODE -ne 0) {
        throw 'Pinned local model unavailable. Check THIRD_PARTY_NOTICES.md and README setup; no fallback predictions are used.'
    }
    if ($CheckOnly) {
        Write-Host "Preflight passed: built dashboard, verified offline model, free loopback port $Port. No server or demo database created."
        return
    }

    $eventlensRuntime = Join-Path $eventlensRoot 'runtime'
    New-Item -ItemType Directory -Path $eventlensRuntime -Force | Out-Null
    $eventlensDatabase = Join-Path $eventlensRuntime ('recording-' + [guid]::NewGuid().ToString('N') + '.sqlite3')
    if (Test-Path -LiteralPath $eventlensDatabase) { throw 'Fresh demo path already exists; refusing to reuse it.' }
    [Environment]::SetEnvironmentVariable('EVENTLENS_DATABASE', $eventlensDatabase, 'Process')
    [Environment]::SetEnvironmentVariable('EVENTLENS_PUBLIC', 'false', 'Process')
    [Environment]::SetEnvironmentVariable('EVENTLENS_WRITE_TOKEN', $null, 'Process')
    [Environment]::SetEnvironmentVariable('EVENTLENS_ALLOWED_HOSTS', '127.0.0.1,localhost', 'Process')

    Write-Host "Dashboard: http://127.0.0.1:$Port/"
    Write-Host "Fresh demo database: $eventlensDatabase"
    Write-Host 'Wait for Application startup complete, then open the dashboard and choose Load sample events.'
    Write-Host 'Keep this terminal open. Ctrl+C stops this server; the demo database remains available.'
    & $eventlensPython -m uvicorn eventlens.api:app --host 127.0.0.1 --port $Port --workers 1
    if ($LASTEXITCODE -ne 0) { throw "Demo server exited with code $LASTEXITCODE." }
}
finally {
    foreach ($eventlensName in $eventlensSavedEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($eventlensName, $eventlensSavedEnvironment[$eventlensName], 'Process')
    }
    Pop-Location
}
