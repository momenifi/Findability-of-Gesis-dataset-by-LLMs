param(
    [string]$Config = "config.yaml",
    [string[]]$Variants = @("V1", "V2", "V3", "V4", "V5"),
    [string[]]$Stages = @("generate_queries", "run_llm", "match_and_eval", "audit_results"),
    [switch]$StopOnError
)

$ErrorActionPreference = "Stop"

if (-not $env:OPENWEBUI_API_KEY) {
    throw "Set OPENWEBUI_API_KEY before running this script."
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
    Write-Host "Transcript: $transcriptPath"

    foreach ($variant in $Variants) {
        Write-Host ""
        Write-Host "===== Variant $variant ====="

        foreach ($stage in $Stages) {
            Write-Host ""
            Write-Host "----- $stage / $variant -----"

            $module = "src.$stage"
            $args = @("-m", $module, "--config", $Config, "-V", $variant)

            & python @args
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
