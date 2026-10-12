$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$outDir = Join-Path $repo 'docs\visualizations'
$env:Path = "C:\Program Files\Graphviz\bin;C:\Program Files\D2;$env:APPDATA\npm;$env:Path"
Get-ChildItem -LiteralPath $outDir -Filter '*.mmd' | ForEach-Object {
    $svg = [IO.Path]::ChangeExtension($_.FullName, '.svg')
    & mmdc.cmd -i $_.FullName -o $svg -b '#f7f5ef' -q
    if ($LASTEXITCODE -ne 0) { throw "Mermaid render failed: $($_.Name)" }
}
$model = Join-Path $outDir 'model-g4-pipeline.mmd'
& mmdc.cmd -i $model -o (Join-Path $outDir 'model-g4-pipeline.png') -b '#f7f5ef' -s 2 -q
if ($LASTEXITCODE -ne 0) { throw 'Mermaid PNG render failed: model-g4-pipeline.mmd' }
$d2 = Join-Path $outDir 'software-architecture-local.d2'
& 'C:\Program Files\D2\d2.exe' $d2 (Join-Path $outDir 'software-architecture-local.svg')
if ($LASTEXITCODE -ne 0) { throw 'D2 render failed: software-architecture-local.d2' }
Write-Output "Rendered Mermaid and D2 sources in $outDir"
