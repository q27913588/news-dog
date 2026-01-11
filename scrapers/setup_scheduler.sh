#!/bin/bash

# Cloud Scheduler 自動設定腳本 (每 15 分鐘跑一次)

REGION="asia-east1"
SCRAPERS=("cna" "cti" "ltn" "set" "udn")
PROJECT_NUMBER="632027619686"
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

echo "------------------------------------"
echo "開始設定 Cloud Scheduler 排程..."
echo "------------------------------------"

for SCRAPER in "${SCRAPERS[@]}"; do
    NAME="scraper-$SCRAPER"
    JOB_NAME="job-$NAME"
    
    # 1. 自動獲取該 Function 的 URL
    URL=$(gcloud functions describe $NAME --region=$REGION --gen2 --format='value(serviceConfig.uri)')
    
    if [ -z "$URL" ]; then
        echo "警告: 找不到 $NAME 的 URL，請確認部署是否成功。"
        continue
    fi
    
    echo "正在設定 $NAME 的排程..."
    echo "URL: $URL"

    # 2. 建立或更新排程 (每 15 分鐘執行一次 */15 * * * *)
    # 如果任務已存在，會先刪除再建立以更新設定
    gcloud scheduler jobs delete $JOB_NAME --location=$REGION --quiet 2>/dev/null
    
    gcloud scheduler jobs create http $JOB_NAME \
        --schedule="*/15 * * * *" \
        --uri="$URL" \
        --http-method=GET \
        --oidc-service-account-email="$SERVICE_ACCOUNT" \
        --oidc-token-audience="$URL" \
        --location=$REGION \
        --description="每 15 分鐘執行一次 $NAME 爬蟲"

    echo "✅ $NAME 排程設定完成！"
    echo "------------------------------------"
done

echo -e "\n🎉 所有爬蟲排程設定完成！你可以到 Cloud Console 檢視結果。"
