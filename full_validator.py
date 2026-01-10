import importlib.util
import os
import sys
import requests
from bs4 import BeautifulSoup
import re
import json
import time
from datetime import datetime

# 停用 SSL 警告 (中天需要)
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def test_scraper_full(source_name, folder):
    print(f"--- 正在執行 {source_name} 完整抓取測試 ({folder}) ---", flush=True)
    
    # 動態匯入該爬蟲的 main.py
    module_path = os.path.abspath(os.path.join("scrapers", folder, "main.py"))
    spec = importlib.util.spec_from_file_location(f"{folder}_main", module_path)
    module = importlib.util.module_from_spec(spec)
    
    # 設定模擬環境變數
    os.environ['INGEST_API_BASE'] = 'http://mock-api/ingest'
    os.environ['API_KEY'] = 'temporary-api-key-123'
    
    spec.loader.exec_module(module)
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    
    target_urls = []
    
    try:
        # 1. 獲取分類清單
        if source_name == "LTN":
            CATEGORIES = ['politics', 'society', 'world']
            for cat in CATEGORIES:
                list_url = f'https://news.ltn.com.tw/list/breakingnews/{cat}'
                resp = requests.get(list_url, headers=headers, timeout=10)
                soup = BeautifulSoup(resp.text, 'lxml')
                for a in soup.select('ul.list li a'):
                    href = a.get('href', '')
                    if '/news/' in href and 'breakingnews' in href:
                        target_urls.append(href)

        elif source_name == "UDN":
            CAT_IDS = ['1', '2', '5']
            for cat_id in CAT_IDS:
                list_url = f'https://udn.com/news/breaknews/1/{cat_id}'
                resp = requests.get(list_url, headers=headers, timeout=10)
                soup = BeautifulSoup(resp.text, 'lxml')
                for a in soup.select('div.story-list__text h2 a'):
                    target_urls.append("https://udn.com" + a['href'].split('?')[0])

        elif source_name == "SET":
            GROUP_IDS = ['6', '41', '5']
            for group_id in GROUP_IDS:
                list_url = f'https://www.setn.com/ViewAll.aspx?PageGroupID={group_id}'
                resp = requests.get(list_url, headers=headers, timeout=10)
                soup = BeautifulSoup(resp.text, 'lxml')
                for a in soup.select('h3.view-li-title a'):
                    href = a['href']
                    full_url = href if href.startswith('http') else "https://www.setn.com" + href
                    if "https://www.setn.comhttps://" in full_url:
                        full_url = full_url.replace("https://www.setn.comhttps://", "https://")
                    if 'utm_' in full_url:
                        full_url = re.sub(r'&utm_[^&]+', '', full_url)
                        full_url = re.sub(r'\?utm_[^&]+&?', '?', full_url).rstrip('?')
                    target_urls.append(full_url)

        elif source_name == "CNA":
            CAT_CODES = ['aipl', 'asoc', 'aopl']
            for code in CAT_CODES:
                list_url = f'https://www.cna.com.tw/list/{code}.aspx'
                resp = requests.get(list_url, headers=headers, timeout=10)
                soup = BeautifulSoup(resp.text, 'lxml')
                for a in soup.select('ul.mainList li a'):
                    href = a.get('href', '')
                    if '/news/' in href:
                        full_url = href if href.startswith('http') else "https://www.cna.com.tw" + href
                        target_urls.append(full_url.split('?')[0])

        elif source_name == "CTI":
            list_url = 'https://ctinews.com/'
            resp = requests.get(list_url, headers=headers, timeout=10, verify=False)
            item_paths = re.findall(r'/news/items/[a-zA-Z0-9]+', resp.text)
            target_urls = list(set(["https://ctinews.com" + path for path in item_paths]))

        target_urls = list(set(target_urls))
        total = len(target_urls)
        print(f"找到 {total} 則網址，開始抓取內文...", flush=True)
        
        articles = []
        for i, url in enumerate(target_urls):
            print(f"  [{i+1}/{total}] 正在抓取: {url}", flush=True)
            try:
                data = module.scrape_article(url)
                if data:
                    if 'rawHtml' in data: del data['rawHtml'] # 移除 HTML 以減小 JSON 體積
                    articles.append(data)
                else:
                    print(f"  !! 跳過或抓取失敗: {url}")
            except Exception as e:
                print(f"  !! 錯誤: {url} - {e}")
            
            # 稍微延遲避免被封鎖
            time.sleep(0.5)
            
        return articles

    except Exception as e:
        print(f"ERROR: {source_name} 列表獲取失敗 - {e}", flush=True)
        return []

if __name__ == "__main__":
    start_time = time.time()
    scrapers = [
        ("LTN", "ltn"),
        ("UDN", "udn"),
        ("SET", "set"),
        ("CNA", "cna"),
        ("CTI", "cti")
    ]
    
    final_report = {}
    
    for name, folder in scrapers:
        results = test_scraper_full(name, folder)
        final_report[name] = {
            "total_found": len(results),
            "data": results
        }
    
    output_path = "full_test_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final_report, f, ensure_ascii=False, indent=2)
    
    duration = time.time() - start_time
    print(f"\n========================================")
    print(f"完整測試完成！")
    print(f"總耗時: {duration:.2f} 秒")
    print(f"測試結果已儲存至: {output_path}")
    print(f"========================================")
