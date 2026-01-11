import requests
import os

# API 設定
API_BASE = 'https://square-news-632027619686.asia-east1.run.app/ingest'
API_KEY = 'temporary-api-key-123'

def check_db():
    print("=== 正在檢查後端資料庫狀態 ===")
    
    # 這裡我們利用 /check-urls 介面來間接測試
    # 我們傳入一些已知的舊網址和一些隨機的新網址，看看後端的反應
    
    test_urls = [
        "https://www.setn.com/News.aspx?NewsID=1779338", # 我剛才存入的
        "https://www.setn.com/News.aspx?NewsID=9999999"  # 隨機網址，理論上不存在
    ]
    
    try:
        resp = requests.post(
            f"{API_BASE}/check-urls",
            json={"sourceCode": "SET", "urls": test_urls},
            headers={"X-API-KEY": API_KEY},
            timeout=15
        )
        
        if resp.status_code == 200:
            missing = resp.json()
            print(f"測試網址檢查結果: {missing}")
            
            if "https://www.setn.com/News.aspx?NewsID=1779338" not in missing:
                print("✅ 確認：網址 1779338 已存在於資料庫中。")
            else:
                print("❌ 警告：網址 1779338 不在資料庫中。")
                
            if "https://www.setn.com/News.aspx?NewsID=9999999" in missing:
                print("✅ 確認：隨機網址 9999999 被識別為『新網址』。")
        else:
            print(f"❌ API 呼叫失敗: {resp.status_code}")
            
    except Exception as e:
        print(f"❌ 發生錯誤: {e}")

if __name__ == "__main__":
    check_db()
