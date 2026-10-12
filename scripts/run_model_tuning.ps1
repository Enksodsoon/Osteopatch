param(
    [ValidateRange(0.01, 4.0)]
    [double]$BudgetHours = 4.0,
    [ValidateRange(1, 16)]
    [int]$BatchSize = 16,
    [string]$BatchSizeReductionReason = 'none'
)
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$WorktreeParent = Split-Path -Parent $ProjectRoot
$SourceRoot = Split-Path -Parent $WorktreeParent
$RuntimeCandidates = @(
    @(
        $env:OSTEOPATCH_RUNTIME_ARTIFACTS,
        (Join-Path $ProjectRoot 'runtime-artifacts'),
        (Join-Path $SourceRoot 'runtime-artifacts')
    ) | Where-Object { $_ -and (Test-Path (Join-Path $_ 'images')) }
)
if (-not $RuntimeCandidates) { throw 'No runtime-artifacts/images directory found.' }
$RuntimeRoot = (Resolve-Path $RuntimeCandidates[0]).Path
$ImageRoot = Join-Path $RuntimeRoot 'images'
$Weights = Join-Path $RuntimeRoot 'models\torch-hub\hub\checkpoints\mobilenet_v3_small-047dcff4.pth'
if (-not (Test-Path $Weights)) { throw "Cached ImageNet checkpoint missing: $Weights" }
$LogRoot = Join-Path $RuntimeRoot 'scratch\model-tuning'
New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null
$LogPath = Join-Path $LogRoot ("scheduled-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
$UvCommand = Get-Command uv -ErrorAction SilentlyContinue
$Uv = if ($UvCommand) { $UvCommand.Source } else { Join-Path $env:USERPROFILE '.local\bin\uv.exe' }
if (-not (Test-Path $Uv)) { throw "uv executable missing: $Uv" }
$env:OSTEOPATCH_RUNTIME_ARTIFACTS = $RuntimeRoot
$BudgetArgument = $BudgetHours.ToString([System.Globalization.CultureInfo]::InvariantCulture)
$BatchSizeArgument = $BatchSize.ToString([System.Globalization.CultureInfo]::InvariantCulture)
Set-Location $ProjectRoot
& $Uv run --locked --extra dev --extra model python scripts/model_tuning.py `
    --image-root $ImageRoot `
    --pretrained-weights $Weights `
    --runtime-model-dir (Join-Path $RuntimeRoot 'models') `
    --budget-hours $BudgetArgument `
    --batch-size $BatchSizeArgument `
    --batch-size-reduction-reason $BatchSizeReductionReason `
    --seeds '42,43,44' *>&1 | Tee-Object -FilePath $LogPath
$RunExitCode = $LASTEXITCODE
exit $RunExitCode
