import requests
from bs4 import BeautifulSoup
import os
import json
from datetime import datetime
import xml.etree.ElementTree as ET
from dateutil import parser
import functions_framework

INGEST_API_BASE = os.getenv('INGEST_API_BASE', 'https://square-news-632027619686.asia-east1.run.app/ingest')
API_KEY = os.getenv('API_KEY', 'temporary-api-key-123')
SOURCE_CODE = 'CTI'
RSS_URL = 'https://ctinews.com/rss/all.xml'

def get_new_urls(urls):
    try:
        resp = requests.post(
            f"{INGEST_API_BASE}/check-urls",
            json={"sourceCode": SOURCE_CODE, "urls": urls},
            headers={"X-API-KEY": API_KEY},
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"Error checking URLs: {e}")
    return []

def scrape_article(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # CTI 有時會有 SSL 憑證問題，加上 verify=False
        resp = requests.get(url, headers=headers, timeout=15, verify=False)
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'lxml')

        # 檢查分類是否符合要求 (政治, 社會, 國際, 要聞)
        cat_node = soup.select_one('a.category-name') or soup.select_one('.category')
        cat_name = cat_node.get_text(strip=True) if cat_node else ""
        
        ALLOWED_CATS = ['政治', '社會', '國際', '要聞', '全球']
        is_allowed = any(c in cat_name for c in ALLOWED_CATS)
        
        # 如果分類不匹配，則跳過
        if cat_name and not is_allowed:
            print(f"Skipping {url} due to category: {cat_name}")
            return None

        # 中天新聞的選擇器
        title_node = soup.select_one('h1.article-title')
        if not title_node:
            title_node = soup.select_one('h1')
        title = title_node.get_text(strip=True) if title_node else ""
        
        content_node = soup.select_one('div.article-content')
        if not content_node:
            content_node = soup.select_one('div.article-body')
        if not content_node:
            content_node = soup.select_one('div.text')
            
        if content_node:
            for tag in content_node.select('script, style, .ad-container, .related-news'):
                tag.decompose()
            clean_text = content_node.get_text("\n", strip=True)
        else:
            clean_text = ""

        time_node = soup.select_one('time.pub-date')
        if not time_node:
            time_node = soup.select_one('time')
            
        published_at = ""
        if time_node:
            # 嘗試取得 datetime 屬性
            time_str = time_node.get('datetime') or time_node.get_text(strip=True)
            try:
                dt = parser.parse(time_str)
                published_at = dt.isoformat()
            except:
                published_at = datetime.now().isoformat()
        else:
            published_at = datetime.now().isoformat()

        return {
            "source": SOURCE_CODE,
            "url": url,
            "title": title,
            "publishedAt": published_at,
            "rawHtml": resp.text,
            "cleanText": clean_text
        }
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return None

def ingest_article(data):
    try:
        resp = requests.post(
            f"{INGEST_API_BASE}/articles",
            json=data,
            headers={"X-API-KEY": API_KEY},
            timeout=10
        )
        return resp.status_code == 202
    except Exception as e:
        print(f"Error ingesting article: {e}")
        return False

@functions_framework.http
def run_scraper(request):
    print(f"Starting {SOURCE_CODE} scraper...")
    LIST_URL = 'https://ctinews.com/'
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # 加上 verify=False
        resp = requests.get(LIST_URL, headers=headers, timeout=10, verify=False)
        import re
        # 匹配 /news/items/XXXX
        item_paths = re.findall(r'/news/items/[a-zA-Z0-9]+', resp.text)
        urls = list(set(["https://ctinews.com" + path for path in item_paths]))
    except Exception as e:
        return f"Failed to fetch list: {e}", 500

    if not urls:
        return "No URLs found in list", 200

    new_urls = get_new_urls(urls)
    success_count = 0
    for url in new_urls:
        article_data = scrape_article(url)
        if article_data and article_data['cleanText']:
            if ingest_article(article_data):
                success_count += 1
    
    return f"Successfully processed {success_count} articles from {SOURCE_CODE}", 200
