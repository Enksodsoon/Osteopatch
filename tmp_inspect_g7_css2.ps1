$f = 'app\g7-enterprise\frontend\src\styles.css'
$s = [System.IO.File]::ReadAllText((Join-Path $PWD $f), [System.Text.Encoding]::UTF8)

$marker = '/* ---- Patch review (3 columns)'
$pr = $s.IndexOf($marker)
Write-Output "PATCH_REVIEW_ANNOTATION=$pr"
Write-Output "FILE_LEN=$($s.Length)"

if ($pr -ge 0) {
  Write-Output "--- after annotation (500 chars) ---"
  Write-Output $s.Substring($pr, [Math]::Min(500, $s.Length - $pr))
}

@('.analysis-workspace','.analysis-toolbar','.analysis-main','.analysis-image-col','.analysis-side-col','.analysis-note-hint') | ForEach-Object {
  Write-Output "PRESENT:$($_)=$($s.Contains($_))"
}

# Also confirm whether there is an existing analysis workspace block after the
# ".analysis {" rule, by searching for ".analysis-workspace" again.
Write-Output "ANALYSIS_WORKSPACE_EXISTS=$($s.Contains('.analysis-workspace'))"
Write-Output "ANALYSIS_MAIN_EXISTS=$($s.Contains('.analysis-main'))"
