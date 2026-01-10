import requests
from bs4 import BeautifulSoup
import os
import json
from datetime import datetime
import xml.etree.ElementTree as ET
from dateutil import parser
import functions_framework

# 設定 API 基礎網址，建議透過環境變數設定
INGEST_API_BASE = os.getenv('INGEST_API_BASE', 'https://square-news-632027619686.asia-east1.run.app/ingest')
API_KEY = os.getenv('API_KEY', 'temporary-api-key-123')
SOURCE_CODE = 'LTN'
RSS_URL = 'https://news.ltn.com.tw/rss/all.xml'

def get_new_urls(urls):
    """呼叫後端 API 檢查哪些 URL 尚未爬取"""
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
    """爬取單篇文章內容"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'lxml')

        # 自由時報的選擇器
        title_node = soup.select_one('div.whitecon h1')
        if not title_node:
            title_node = soup.select_one('h1')
        
        title = title_node.get_text(strip=True) if title_node else ""
        
        content_node = soup.select_one('article')
        if not content_node:
            content_node = soup.select_one('div.text')
            
        # 移除不需要的元素
        if content_node:
            for tag in content_node.select('script, style, .article_popular, .apps, .boxTitle, .author, .disclaim, .further_reading'):
                tag.decompose()
            
            # 優先嘗試取得 p 標籤內容
            paragraphs = content_node.find_all('p')
            if paragraphs:
                texts = []
                for p in paragraphs:
                    p_text = p.get_text(strip=True)
                    # 排除一些常見的非內文文字
                    if p_text and "請繼續往下閱讀" not in p_text and "點我下載APP" not in p_text:
                        texts.append(p_text)
                clean_text = "\n".join(texts)
            else:
                clean_text = content_node.get_text("\n", strip=True)
        else:
            clean_text = ""

        # 時間處理
        time_node = soup.select_one('span.time')
        published_at = ""
        if time_node:
            time_str = time_node.get_text(strip=True)
            try:
                # 預期格式: 2026/01/10 14:30
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
    """將爬取的文章送入後端"""
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
    """Cloud Function 入口點"""
    print(f"Starting {SOURCE_CODE} scraper...")
    
    # 鎖定分類：政治、時事(即時)、社會、國際
    CATEGORIES = ['politics', 'society', 'world']
    all_urls = []
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    for cat in CATEGORIES:
        list_url = f'https://news.ltn.com.tw/list/breakingnews/{cat}'
        try:
            resp = requests.get(list_url, headers=headers, timeout=10)
            soup = BeautifulSoup(resp.text, 'lxml')
            # 修改選擇器，不鎖定 tit class
            for a in soup.select('ul.list li a'):
                href = a.get('href', '')
                if '/news/' in href and 'breakingnews' in href:
                    all_urls.append(href)
        except Exception as e:
            print(f"Failed to fetch {cat} list: {e}")

    if not all_urls:
        return "No URLs found in categories", 200

    # 2. 去重檢查
    new_urls = get_new_urls(list(set(all_urls)))
    print(f"Found {len(new_urls)} new URLs out of {len(urls)}")

    # 3. 抓取與送入
    success_count = 0
    for url in new_urls:
        article_data = scrape_article(url)
        if article_data and article_data['cleanText']:
            if ingest_article(article_data):
                success_count += 1
    
    return f"Successfully processed {success_count} articles from {SOURCE_CODE}", 200
