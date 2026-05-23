# Fundus Lab + SaMD 파트너 API — 호스트 curl.exe 검증 (:8001)
$ErrorActionPreference = "Stop"
$Base = if ($env:MEDI_SMOKE_BASE) { $env:MEDI_SMOKE_BASE } else { "http://127.0.0.1:8001" }
$Img = if ($env:MEDI_SMOKE_IMAGE) { $env:MEDI_SMOKE_IMAGE } else { Join-Path $env:TEMP "medi_smoke_fundus.jpg" }

if (-not (Test-Path $Img)) {
    Write-Host "pull test image from medi-iot-api-dev container..."
    docker cp medi-iot-api-dev:/tmp/test_fundus_normal.jpg $Img 2>$null
    if (-not (Test-Path $Img)) {
        throw "smoke image missing: set MEDI_SMOKE_IMAGE or run e2e_fundus_smoke.py in container first"
    }
}

Write-Host "=== health ===" -ForegroundColor Cyan
curl.exe -s "$Base/health"
Write-Host ""

Write-Host "=== Fundus Lab comprehensive ===" -ForegroundColor Cyan
$compOut = Join-Path $env:TEMP "medi_comp_out.json"
$code = curl.exe -s -o $compOut -w "%{http_code}" -X POST "$Base/api/v1/lab/fundus/comprehensive" `
    -F "file=@$Img;filename=normal.jpg;type=image/jpeg" `
    -F "lang=ko" -F "lat=37.5665" -F "lng=126.9780" -F "include_heatmap=true"
Write-Host "HTTP $code"
if (Test-Path $compOut) {
    $txt = Get-Content $compOut -Raw -Encoding UTF8
    if ($txt.Length -gt 2500) { $txt.Substring(0, 2500) + "...(truncated)" } else { $txt }
}
if ($code -ne "200") { throw "comprehensive failed HTTP $code" }

$partnerId = "smoke-host-" + (Get-Date -Format "yyyyMMddHHmmss")
$regPath = Join-Path $env:TEMP "medi_partner_reg.json"
@{
    partner_id = $partnerId
    name       = "Host Smoke Partner"
    plan       = "trial"
} | ConvertTo-Json -Compress | ForEach-Object {
    [System.IO.File]::WriteAllText($regPath, $_, [System.Text.UTF8Encoding]::new($false))
}

Write-Host "`n=== partner register ($partnerId) ===" -ForegroundColor Cyan
$regJson = curl.exe -s -X POST "$Base/api/v1/partner/register" `
    -H "Content-Type: application/json" `
    --data-binary "@$regPath"
Write-Host $regJson
$reg = $regJson | ConvertFrom-Json
$key = $reg.api_key
if (-not $key) { throw "partner register failed: $regJson" }

$b64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($Img))
$analyzePath = Join-Path $env:TEMP "medi_partner_analyze.json"
@{
    partner_id      = $partnerId
    image_base64    = $b64
    return_format   = "json"
    include_heatmap = $true
    lang            = "ko"
} | ConvertTo-Json -Compress | ForEach-Object {
    [System.IO.File]::WriteAllText($analyzePath, $_, [System.Text.UTF8Encoding]::new($false))
}

Write-Host "`n=== partner analyze ===" -ForegroundColor Cyan
$paOut = Join-Path $env:TEMP "medi_partner_analyze_out.json"
$pcode = curl.exe -s -o $paOut -w "%{http_code}" -X POST "$Base/api/v1/partner/analyze" `
    -H "Content-Type: application/json" `
    -H "X-API-Key: $key" `
    --data-binary "@$analyzePath"
Write-Host "HTTP $pcode"
if (Test-Path $paOut) {
    $ptxt = Get-Content $paOut -Raw -Encoding UTF8
    if ($ptxt -match 'heatmap_base64') {
        $ptxt = $ptxt -replace '"heatmap_base64"\s*:\s*"[^"]{80}[^"]*"', '"heatmap_base64":"<truncated>"'
    }
    if ($ptxt.Length -gt 2000) { $ptxt.Substring(0, 2000) + "...(truncated)" } else { $ptxt }
}
if ($pcode -ne "200") { throw "partner analyze failed HTTP $pcode" }

Write-Host "`nOK host smoke (base=$Base partner=$partnerId)" -ForegroundColor Green
