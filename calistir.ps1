# ============================================================
#  Stereo Kamera Projesi — PowerShell baslatici
#
#  PATH'teki 'python' base conda ortamini gosteriyor ve orada
#  cv2 yok. Bu script her zaman 'stereo' ortamindaki python'u
#  kullanir.
#
#  Kullanim:
#    .\calistir.ps1                 -> camera_test.py (ana uygulama)
#    .\calistir.ps1 depth_view      -> src\depth_view.py
#    .\calistir.ps1 odak_test
#    .\calistir.ps1 box_output --en 250 --boy 180 --yukseklik 120
# ============================================================
param(
    [string]$Script = "camera_test",
    [Parameter(ValueFromRemainingArguments = $true)]
    $Rest
)

$py = "C:\Users\nvflb\miniconda3\envs\stereo\python.exe"

if (-not (Test-Path $py)) {
    Write-Host "HATA: stereo ortami bulunamadi:" -ForegroundColor Red
    Write-Host "  $py"
    Write-Host "Ortam tasindiysa bu dosyadaki `$py satirini guncelle."
    exit 1
}

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

$target = Join-Path $here "src\$Script.py"
if (-not (Test-Path $target)) {
    Write-Host "HATA: bulunamadi -> $target" -ForegroundColor Red
    Write-Host ""
    Write-Host "Mevcut scriptler:"
    Get-ChildItem (Join-Path $here "src\*.py") | ForEach-Object {
        Write-Host ("  " + $_.BaseName)
    }
    exit 1
}

Write-Host "Baslatiliyor: src\$Script.py  (stereo ortami)" -ForegroundColor Cyan
& $py $target @Rest
