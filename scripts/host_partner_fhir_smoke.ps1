# 파트너 API FHIR 포맷 스모크 (호스트 curl)
$ErrorActionPreference = "Stop"
$Base = if ($env:MEDI_SMOKE_BASE) { $env:MEDI_SMOKE_BASE } else { "http://127.0.0.1:8001" }
$Img = if ($env:MEDI_SMOKE_IMAGE) { $env:MEDI_SMOKE_IMAGE } else { Join-Path $env:TEMP "medi_smoke_fundus.jpg" }
if (-not (Test-Path $Img)) {
    docker cp medi-iot-api-dev:/tmp/test_fundus_normal.jpg $Img
}

$partnerId = "smoke-fhir-" + (Get-Date -Format "yyyyMMddHHmmss")
$regPath = Join-Path $env:TEMP "medi_fhir_reg.json"
@{ partner_id = $partnerId; name = "FHIR Smoke"; plan = "trial" } | ConvertTo-Json -Compress |
    ForEach-Object { [System.IO.File]::WriteAllText($regPath, $_, [System.Text.UTF8Encoding]::new($false)) }

$reg = curl.exe -s -X POST "$Base/api/v1/partner/register" -H "Content-Type: application/json" --data-binary "@$regPath" | ConvertFrom-Json
$key = $reg.api_key
$b64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($Img))
$bodyPath = Join-Path $env:TEMP "medi_fhir_analyze.json"
@{
    partner_id = $partnerId
    image_base64 = $b64
    return_format = "fhir"
    include_heatmap = $false
    lang = "ko"
} | ConvertTo-Json -Compress | ForEach-Object {
    [System.IO.File]::WriteAllText($bodyPath, $_, [System.Text.UTF8Encoding]::new($false))
}

Write-Host "=== partner analyze (FHIR) ===" -ForegroundColor Cyan
$out = curl.exe -s -X POST "$Base/api/v1/partner/analyze" `
    -H "Content-Type: application/json" -H "X-API-Key: $key" --data-binary "@$bodyPath"
if ($out -notmatch '"resourceType"\s*:\s*"Bundle"') { throw "FHIR Bundle not found: $($out.Substring(0, [Math]::Min(500, $out.Length)))" }
Write-Host "OK FHIR Bundle received ($($out.Length) bytes)"
