$f = 'app\g7-enterprise\frontend\src\styles.css'
$s = [System.IO.File]::ReadAllText((Join-Path $PWD $f), [System.Text.Encoding]::UTF8)

$pr = $s.IndexOf('/* ---- Patch review (3 columns)')
if ($pr -ge 0) {
  $tail = $s.Substring($pr, [Math]::Max(0, $s.Length - $pr))
  Write-Output "PATCH_REVIEW_START=$pr"
  Write-Output "TAIL_LEN=$($tail.Length)"
  $head = $tail.Substring(0, [Math]::Min(2600, $tail.Length))
  Write-Output "--- tail from patch-review annotation (first 2600 chars) ---"
  Write-Output $head
}

@('.analysis-workspace','.analysis-main','.analysis-toolbar','.analysis-image-col','.analysis-side-col','.analysis-note-hint') | ForEach-Object {
  Write-Output "PRESENT:$($_)=$($s.Contains($_))"
}
