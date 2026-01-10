# Google Cloud Functions 批次部署腳本 (Windows PowerShell)

# --- 請修改以下設定 ---
$INGEST_API_BASE = "你的後端API地址/ingest"
$API_KEY = "你的API_KEY"
$REGION = "asia-east1"
# --------------------

$scrapers = @("cna", "cti", "ltn", "set", "udn")

foreach ($scraper in $scrapers) {
    Write-Host "------------------------------------" -ForegroundColor Cyan
    Write-Host "正在部署爬蟲: $scraper" -ForegroundColor Cyan
    Write-Host "------------------------------------"
    
    Push-Location $scraper
    
    gcloud functions deploy "scraper-$scraper" `
        --gen2 `
        --runtime python311 `
        --trigger-http `
        --entry-point run_scraper `
        --allow-unauthenticated `
        --region $REGION `
        --set-env-vars INGEST_API_BASE=$INGEST_API_BASE,API_KEY=$API_KEY `
        --memory 256Mi `
        --timeout 60s
        
    Pop-Location
}

Write-Host "`n所有爬蟲部署完成！" -ForegroundColor Green
