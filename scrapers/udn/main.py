import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
import os
import json
import re
from datetime import datetime
import xml.etree.ElementTree as ET
from dateutil import parser
import functions_framework

INGEST_API_BASE = os.getenv('INGEST_API_BASE', 'https://square-news-632027619686.asia-east1.run.app/ingest')
API_KEY = os.getenv('API_KEY', 'temporary-api-key-123')
SOURCE_CODE = 'UDN'
RSS_URL = 'https://udn.com/rssfeed/latest'

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

def extract_photographer(text):
    """從圖片說明文字中提取攝影師或來源署名"""
    if not text:
        return None
    patterns = [
        r'記者(.+?)攝',
        r'攝影[：:]\s*(.+?)(?:\s|$|）|】)',
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            return m.group(1).strip()
    # UDN 常見格式：圖片說明最後的來源（如 "...。路透" 或 "...。美聯社"）
    m = re.search(r'。([^\s。（）]{1,10})$', text.strip())
    if m:
        source = m.group(1).strip()
        # 排除非來源的常見結尾字詞
        if source and len(source) <= 8:
            return source
    return None

def extract_image_info(soup):
    """提取文章主圖 URL 和攝影師"""
    image_url = None
    photographer = None

    # 1. 從 og:image meta tag 取得圖片 URL
    og_img = soup.select_one('meta[property="og:image"]')
    if og_img and og_img.get('content'):
        image_url = og_img['content']

    # 2. 備用：從 JSON-LD 取得
    if not image_url:
        try:
            for ld_node in soup.select('script[type="application/ld+json"]'):
                ld_data = json.loads(ld_node.string)
                if isinstance(ld_data, dict) and ld_data.get('image'):
                    img = ld_data['image']
                    if isinstance(img, str):
                        image_url = img
                    elif isinstance(img, dict):
                        image_url = img.get('contentUrl') or img.get('url')
                    elif isinstance(img, list) and img:
                        first = img[0]
                        image_url = first.get('contentUrl') or first.get('url') if isinstance(first, dict) else first
                if image_url:
                    break
        except:
            pass

    # 3. 從主圖 alt / figcaption 提取攝影師
    # UDN 主圖在 .article-content__cover 或 section.article-content__editor 內
    cover_img = soup.select_one('.article-content__cover img') or soup.select_one('section.article-content__editor img')
    if cover_img:
        alt_text = cover_img.get('alt', '')
        photographer = extract_photographer(alt_text)

    if not photographer:
        figcaption = soup.select_one('.article-content__cover figcaption') or soup.select_one('section.article-content__editor figcaption')
        if figcaption:
            photographer = extract_photographer(figcaption.get_text())

    return image_url, photographer

def scrape_article(url):
    try:
        resp = http_session.get(url, timeout=20)
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'lxml')

        # 提取圖片資訊（在清理 content 前提取）
        image_url, photographer = extract_image_info(soup)

        # 聯合新聞網的選擇器
        title_node = soup.select_one('h1.article-content__title')
        title = title_node.get_text(strip=True) if title_node else ""

        content_node = soup.select_one('section.article-content__editor')
        if content_node:
            for tag in content_node.select('script, style, .inline-ad, .article-content__info'):
                tag.decompose()
            clean_text = content_node.get_text("\n", strip=True)
        else:
            clean_text = ""

        time_node = soup.select_one('time.article-content__time')
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

        result = {
            "source": SOURCE_CODE,
            "url": url,
            "title": title,
            "publishedAt": published_at,
            "rawHtml": "",
            "cleanText": clean_text
        }
        if image_url:
            result["imageUrl"] = image_url
        if photographer:
            result["imagePhotographer"] = photographer
        return result
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
    # 分類代碼：1 (要聞/政治), 2 (社會), 5 (國際)
    CAT_IDS = ['1', '2', '5']
    all_urls = []
    
    for cat_id in CAT_IDS:
        list_url = f'https://udn.com/news/breaknews/1/{cat_id}'
        try:
            resp = http_session.get(list_url, timeout=15)
            soup = BeautifulSoup(resp.text, 'lxml')
            for a in soup.select('div.story-list__text h2 a'):
                href = a['href']
                # 規範化 URL：移除 query string、fragment 和結尾斜線
                full_url = "https://udn.com" + href.split('?')[0].split('#')[0].rstrip('/')
                all_urls.append(full_url)
        except Exception as e:
            print(f"Failed to fetch {cat_id} list: {e}")

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
