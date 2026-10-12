$f = 'app\g6\frontend\src\styles.css'
$s = [System.IO.File]::ReadAllText((Join-Path $PWD $f), [System.Text.Encoding]::UTF8)
$idx1 = $s.IndexOf('/* ---- Image viewer ---- */')
$idx2 = $s.IndexOf('/* ---- right panel ---- */')
$idxG8 = $s.IndexOf('Professional editorial UI layer')
Write-Output "BASE_DIR=$PWD"
Write-Output "FILE=$f"
Write-Output "LENGTH=$($s.Length)"
Write-Output "VIEWER_START=$idx1"
Write-Output "RIGHT_PANEL_START=$idx2"
Write-Output "G8_START=$idxG8"
if ($idx1 -ge 0) {
  Write-Output "--- VIEWER..RIGHTPANEL ({0} chars) ---" -f ($idx2 - $idx1)
  Write-Output $s.Substring($idx1, [Math]::Min(700, [Math]::Max(0, $idx2 - $idx1)))
}
if ($idxG8 -ge 0) {
  Write-Output "--- G8 BLOCK HEADER + NEXT 1200 chars ---"
  Write-Output $s.Substring($idxG8, [Math]::Min(1300, [Math]::Max(0, $s.Length - $idxG8)))
}
