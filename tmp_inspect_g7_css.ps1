$f = 'app\g7-enterprise\frontend\src\styles.css'
$s = [System.IO.File]::ReadAllText((Join-Path $PWD $f), [System.Text.Encoding]::UTF8)

@(
  '/* ---- Patch review (3 columns)',
  'G6 review surface styles - ported',
  '.patch-review {',
  '.viewer {',
  '.analysis-workspace',
  '.analysis-main',
  '.analysis-toolbar',
  '.analysis-image-col',
  '.analysis-side-col',
  '.analysis-note-hint',
  '/* ---- model card / attribution',
  '.analysis {',
) | ForEach-Object {
  Write-Output "MARKER=$_ => $($s.IndexOf($_))"
}

$pr = $s.IndexOf('/* ---- Patch review (3 columns)')
if ($pr -ge 0) {
  Write-Output "--- after patch-review block marker (first 500 chars) ---"
  Write-Output $s.Substring($pr, [Math]::Min(500, $s.Length - $pr))
}

@('.analysis-workspace','.analysis-toolbar','.analysis-main','.analysis-image-col','.analysis-side-col','.analysis-note-hint') | ForEach-Object {
  Write-Output "PRESENT:$_ => $($s.Contains($_))"
}
