# 新聞爬蟲部署指南 (Cloud Functions)

這份專案包含五個獨立的新聞爬蟲，分別針對：
- `CTI`: 中天
- `UDN`: 聯合
- `LTN`: 自由
- `SET`: 三立
- `CNA`: 中央社

## 專案結構
每個目錄都是一個獨立的 Cloud Function 專案：
```
scrapers/
├── cna/
│   ├── main.py
│   └── requirements.txt
├── cti/
│   ├── main.py
│   └── requirements.txt
├── ltn/
│   ├── main.py
│   └── requirements.txt
├── set/
│   ├── main.py
│   └── requirements.txt
└── udn/
    ├── main.py
    └── requirements.txt
```

## 部署方式
你可以使用 Google Cloud SDK (`gcloud`) 進行部署。進入各個目錄後執行：

```bash
gcloud functions deploy run_scraper \
--runtime python311 \
--trigger-http \
--allow-unauthenticated \
--set-env-vars INGEST_API_BASE="https://square-news-632027619686.asia-east1.run.app/ingest",API_KEY="your-api-key-here" \
--region asia-east1
```

## 環境變數
- `INGEST_API_BASE`: 後端 API 的基礎路徑 (例如 `https://square-news-632027619686.asia-east1.run.app/ingest`)。預設為 `https://square-news-632027619686.asia-east1.run.app/ingest`。
- `API_KEY`: API 認證金鑰。預設為 `temporary-api-key-123`。

## 定期執行 (Cloud Scheduler)
建議配合 **Cloud Scheduler** 設定每 30 分鐘或每小時觸發一次 URL。

1. 在 Cloud Console 搜尋 "Cloud Scheduler"。
2. 建立新作業。
3. 頻率設定 (Cron): `0 * * * *` (每小時執行一次)。
4. 目標類型: **HTTP**。
5. URL: 填入部署後獲得的 Cloud Function 網址。
6. HTTP 方法: **GET**。
