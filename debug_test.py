import sys
import os

# 將 scraper 目錄加入路徑以便匯入
sys.path.append(os.path.join(os.getcwd(), 'scrapers', 'set'))

import main
import requests
import json

def debug_local_test():
    print("=== 開始本地除錯測試 (三立新聞 SET) ===")
    
    # 1. 取得網址列表
    print("1. 正在獲取網址列表...")
    # 模擬 run_scraper 的一部分
    GROUP_IDS = ['6'] # 只測一個分類
    all_urls = []
    for group_id in GROUP_IDS:
        list_url = f'https://www.setn.com/ViewAll.aspx?PageGroupID={group_id}'
        resp = main.http_session.get(list_url, timeout=15)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, 'lxml')
        import re
        for a in soup.select('h3.view-li-title a'):
            href = a['href']
            full_url = href if href.startswith('http') else "https://www.setn.com" + href
            all_urls.append(full_url)
    
    if not all_urls:
        print("沒有找到網址，結束測試")
        return

    # 2. 檢查去重 API 找出一個真正的新網址
    print("\n2. 呼叫 /check-urls 找出新網址...")
    new_urls = main.get_new_urls(all_urls)
    print(f"找到 {len(new_urls)} 個新網址")
    
    if not new_urls:
        print("沒有新網址可供測試")
        return
        
    test_url = new_urls[0]
    unique_urls = [test_url]
    print(f"選用測試網址: {test_url}")

    # 3. 測試爬取與送入
    print(f"\n3. 正在爬取內容並送入: {test_url}")
    article_data = main.scrape_article(test_url)
    if article_data:
        print("Article Data sample:")
        print(f"  Title: {article_data['title']}")
        print(f"  PublishedAt: {article_data['publishedAt']}")
        print(f"  Source: {article_data['source']}")
        print(f"  CleanText Length: {len(article_data['cleanText'])}")
        
        resp = main.http_session.post(
            f"{main.INGEST_API_BASE}/articles",
            json=article_data,
            headers={"X-API-KEY": main.API_KEY},
            timeout=15
        )
        print(f"Ingest 回應狀態碼: {resp.status_code}")
        if resp.status_code != 202:
            print(f"Ingest 回應內容: {resp.text}")
    else:
        print("爬取失敗")
        return

    # 4. 第二次檢查去重 API
    print("\n4. 再次呼叫 /check-urls (預期應該回傳 0)...")
    new_urls_2 = main.get_new_urls(unique_urls)
    print(f"再次回傳新網址數量: {len(new_urls_2)}")
    
    if len(new_urls_2) == 0:
        print("Deduplication logic is working: Second check found URL exists.")
    else:
        print("Deduplication logic FAILED: URL still not found in DB.")

if __name__ == "__main__":
    debug_local_test()
