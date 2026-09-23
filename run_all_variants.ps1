param(
    [string]$Config = "config.yaml",
    [string[]]$Variants = @("V1", "V2", "V3", "V4", "V5", "V6"),
    [string[]]$Stages = @("generate_queries", "run_llm", "match_and_eval", "audit_results"),
    [string]$PythonExe = "",
    [switch]$StopOnError
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    if ($env:CONDA_PREFIX) {
        $candidate = Join-Path $env:CONDA_PREFIX "python.exe"
        if (Test-Path $candidate) {
            $PythonExe = $candidate
        }
    }
}

if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    $PythonExe = "python"
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logDir = Join-Path "output" "full_metadata_model_comparison"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$transcriptPath = Join-Path $logDir "run_all_variants_$timestamp.log"

Start-Transcript -Path $transcriptPath | Out-Null

try {
    Write-Host "Config: $Config"
    Write-Host "Variants: $($Variants -join ', ')"
    Write-Host "Stages: $($Stages -join ', ')"
    Write-Host "Python: $PythonExe"
    Write-Host "Transcript: $transcriptPath"

    foreach ($variant in $Variants) {
        Write-Host ""
        Write-Host "===== Variant $variant ====="

        foreach ($stage in $Stages) {
            Write-Host ""
            Write-Host "----- $stage / $variant -----"

            $module = "src.$stage"
            $args = @("-m", $module, "--config", $Config, "-V", $variant)

            & $PythonExe @args
            $exitCode = $LASTEXITCODE

            if ($exitCode -ne 0) {
                $message = "Stage failed: $stage variant=$variant exit_code=$exitCode"
                Write-Host $message
                if ($StopOnError) {
                    throw $message
                }
            }
        }
    }
}
finally {
    Stop-Transcript | Out-Null
}
