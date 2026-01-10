#!/bin/bash

# Google Cloud Functions 批次部署腳本 (Linux/Mac/Git Bash)

# --- 請修改以下設定 ---
INGEST_API_BASE="https://square-news-632027619686.asia-east1.run.app//ingest"
API_KEY="temporary-api-key-123"
REGION="asia-east1"
# --------------------

SCRAPERS=("cna" "cti" "ltn" "set" "udn")

for SCRAPER in "${SCRAPERS[@]}"; do
    echo "------------------------------------"
    echo "正在部署爬蟲: $SCRAPER"
    echo "------------------------------------"
    
    cd $SCRAPER
    
    gcloud functions deploy "scraper-$SCRAPER" \
        --gen2 \
        --runtime python311 \
        --trigger-http \
        --entry-point run_scraper \
        --allow-unauthenticated \
        --region $REGION \
        --set-env-vars INGEST_API_BASE=$INGEST_API_BASE,API_KEY=$API_KEY \
        --memory 256Mi \
        --timeout 60s
        
    cd ..
done

echo -e "\n所有爬蟲部署完成！"
