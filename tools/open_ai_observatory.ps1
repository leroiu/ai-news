$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Url = "http://127.0.0.1:8765/"
$Uv = Join-Path $env:USERPROFILE ".local\bin\uv.exe"

function Test-AiObservatory {
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 500
    }
    catch {
        return $false
    }
}

if (-not (Test-AiObservatory)) {
    if (-not (Test-Path -LiteralPath $Uv)) {
        Add-Type -AssemblyName PresentationFramework
        [System.Windows.MessageBox]::Show("uv was not found: $Uv", "AI Observatory") | Out-Null
        exit 1
    }

    Start-Process `
        -FilePath $Uv `
        -ArgumentList @("run", "uvicorn", "src.api.api:app", "--host", "127.0.0.1", "--port", "8765") `
        -WorkingDirectory $ProjectRoot `
        -WindowStyle Hidden

    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Milliseconds 500
        if (Test-AiObservatory) {
            $ready = $true
            break
        }
    }

    if (-not $ready) {
        Add-Type -AssemblyName PresentationFramework
        [System.Windows.MessageBox]::Show("The service did not start in time. Check the project environment.", "AI Observatory") | Out-Null
        exit 1
    }
}

Start-Process $Url
