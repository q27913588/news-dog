# Google Cloud Functions 批次部署腳本 (Windows PowerShell)

# --- 請修改以下設定 ---
$INGEST_API_BASE = "https://square-news-632027619686.asia-east1.run.app/ingest"
$API_KEY = "temporary-api-key-123"
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
        --no-allow-unauthenticated `
        --region $REGION `
        --set-env-vars INGEST_API_BASE=$INGEST_API_BASE,API_KEY=$API_KEY `
        --memory 256Mi `
        --timeout 300s `
        --max-instances 1
        
    Pop-Location
}

Write-Host "`n所有爬蟲部署完成！" -ForegroundColor Green
