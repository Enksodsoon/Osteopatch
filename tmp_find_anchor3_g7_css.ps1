$f = 'app\g7-enterprise\frontend\src\styles.css'
$s = [System.IO.File]::ReadAllText((Join-Path $PWD $f), [System.Text.Encoding]::UTF8)

$targets = @(
  '.viewer-stage { background: #171514; }',
  '.viewer-stage img {',
  '.analysis-workspace',
  '.analysis-main',
  '.analysis {',
  '/* ---- analysis surface',
  '/* ---- model card / attribution',
)
$targets | ForEach-Object { Write-Output "T=$($_) => $($s.IndexOf($_))" }

$pr = $s.IndexOf('/* ---- Patch review (3 columns)')
if ($pr -ge 0) {
  $seg = $s.Substring($pr, [Math]::Max(0, $s.Length - $pr))
  $where = $seg.IndexOf('.viewer-stage img {')
  Write-Output "VIEWER_STAGE_IMG_IN_SEG=$where"
  if ($where -ge 0) {
    Write-Output "--- 900 chars around viewer-stage img in seg ---"
    Write-Output $seg.Substring([Math]::Max(0, $where - 120), [Math]::Min(900, $seg.Length - [Math]::Max(0, $where - 120)))
  }
}
