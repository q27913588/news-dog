import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
import os
import json
from datetime import datetime
import xml.etree.ElementTree as ET
from dateutil import parser
import functions_framework

INGEST_API_BASE = os.getenv('INGEST_API_BASE', 'https://square-news-632027619686.asia-east1.run.app/ingest')
API_KEY = os.getenv('API_KEY', 'temporary-api-key-123')
SOURCE_CODE = 'CNA'
RSS_URL = 'https://www.cna.com.tw/rss/aall.xml'

# 建立全域 Session 以便重用連線
def create_session():
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
        raise_on_status=False
    )
    adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=10)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    })
    return session

http_session = create_session()

def get_new_urls(urls):
    try:
        resp = http_session.post(
            f"{INGEST_API_BASE}/check-urls",
            json={"sourceCode": SOURCE_CODE, "urls": urls},
            headers={"X-API-KEY": API_KEY},
            timeout=15
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"Error checking URLs: {e}")
    return []

def scrape_article(url):
    try:
        resp = http_session.get(url, timeout=20)
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'lxml')

        # 中央社的選擇器
        title_node = soup.select_one('h1 span')
        if not title_node:
            title_node = soup.select_one('h1')
        title = title_node.get_text(strip=True) if title_node else ""
        
        content_node = soup.select_one('div.paragraph')
        if content_node:
            for tag in content_node.select('script, style, .article-ads, .more-news'):
                tag.decompose()
            clean_text = content_node.get_text("\n", strip=True)
        else:
            clean_text = ""

        time_node = soup.select_one('div.updatetime span')
        if not time_node:
            time_node = soup.select_one('time')
            
        published_at = ""
        if time_node:
            time_str = time_node.get_text(strip=True)
            try:
                dt = parser.parse(time_str)
                published_at = dt.strftime('%Y-%m-%d %H:%M:%S')
            except:
                published_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        else:
            published_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        return {
            "source": SOURCE_CODE,
            "url": url,
            "title": title,
            "publishedAt": published_at,
            "rawHtml": "",
            "cleanText": clean_text
        }
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return None

def ingest_article(data):
    try:
        resp = http_session.post(
            f"{INGEST_API_BASE}/articles",
            json=data,
            headers={"X-API-KEY": API_KEY},
            timeout=15
        )
        return resp.status_code == 202
    except Exception as e:
        print(f"Error ingesting article: {e}")
        return False

@functions_framework.http
def run_scraper(request):
    print(f"Starting {SOURCE_CODE} scraper...")
    # aipl: 政治, asoc: 社會, aopl: 國際
    CAT_CODES = ['aipl', 'asoc', 'aopl']
    all_urls = []
    
    for code in CAT_CODES:
        list_url = f'https://www.cna.com.tw/list/{code}.aspx'
        try:
            resp = http_session.get(list_url, timeout=15)
            soup = BeautifulSoup(resp.text, 'lxml')
            for a in soup.select('ul.mainList li a'):
                href = a.get('href', '')
                if '/news/' in href:
                    full_url = href if href.startswith('http') else "https://www.cna.com.tw" + href
                    all_urls.append(full_url.split('?')[0])
        except Exception as e:
            print(f"Failed to fetch {code} list: {e}")

    if not all_urls:
        return "No URLs found in categories", 200

    unique_urls = list(set(all_urls))
    new_urls = get_new_urls(unique_urls)
    
    print(f"Found {len(unique_urls)} total URLs, {len(new_urls)} are new.")
    
    success_count = 0
    for url in new_urls:
        article_data = scrape_article(url)
        if not article_data:
            continue
            
        # 檢查必填欄位
        if not article_data.get('title'):
            print(f"Skipping {url}: Missing title")
            continue
        if not article_data.get('cleanText'):
            print(f"Skipping {url}: Missing cleanText")
            continue
            
        if ingest_article(article_data):
            success_count += 1
        else:
            print(f"Failed to ingest: {url}")
    
    return f"Successfully processed {success_count} articles from {SOURCE_CODE}", 200
