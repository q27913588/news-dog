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
import urllib3

# 禁用不安全請求警告 (因為 CTI 需要 verify=False)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

INGEST_API_BASE = os.getenv('INGEST_API_BASE', 'https://square-news-632027619686.asia-east1.run.app/ingest')
API_KEY = os.getenv('API_KEY', 'temporary-api-key-123')
SOURCE_CODE = 'CTI'
RSS_URL = 'https://ctinews.com/rss/all.xml'

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
    # CTI 有時會有 SSL 憑證問題
    session.verify = False
    return session

http_session = create_session()

def get_new_urls(urls):
    try:
        # 對於 API 呼叫，我們應該啟用驗證，但 Session 全域關閉了，所以這裡手動開啟
        resp = http_session.post(
            f"{INGEST_API_BASE}/check-urls",
            json={"sourceCode": SOURCE_CODE, "urls": urls},
            headers={"X-API-KEY": API_KEY},
            timeout=15,
            verify=True
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"Error checking URLs: {e}")
    return []

def extract_photographer(text):
    """從圖片說明文字中提取攝影師署名"""
    if not text:
        return None
    patterns = [
        r'記者(.+?)攝',
        r'圖／(.+?)提供',
        r'攝影[：:]\s*(.+?)(?:\s|$|）|】)',
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            return m.group(1).strip()
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
                        image_url = img.get('url') or img.get('contentUrl')
                    elif isinstance(img, list) and img:
                        first = img[0]
                        image_url = first.get('url') or first.get('contentUrl') if isinstance(first, dict) else first
                if image_url:
                    break
        except:
            pass

    # 3. 從 figcaption 提取攝影師（CTI 使用 figure.image + figcaption）
    figcaption = soup.select_one('figure.image figcaption') or soup.select_one('[itemprop="articleBody"] figcaption')
    if figcaption:
        photographer = extract_photographer(figcaption.get_text())

    # 4. 備用：從第一張圖片 alt 提取
    if not photographer:
        content_area = soup.select_one('[itemprop="articleBody"]') or soup.select_one('div.article-content')
        if content_area:
            first_img = content_area.select_one('img')
            if first_img:
                alt_text = first_img.get('alt', '')
                photographer = extract_photographer(alt_text)

    return image_url, photographer

def scrape_article(url):
    try:
        resp = http_session.get(url, timeout=20)
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'lxml')

        # 提取圖片資訊（在清理 content 前提取）
        image_url, photographer = extract_image_info(soup)

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

        # 使用 itemprop="articleBody" 較為穩定
        content_node = soup.select_one('[itemprop="articleBody"]')
        if not content_node:
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

        # 優先從 meta tag 取得時間
        time_node = soup.select_one('meta[property="article:published_time"]')
        published_at = ""
        if time_node and time_node.get('content'):
            time_str = time_node.get('content')
            try:
                dt = parser.parse(time_str)
                published_at = dt.strftime('%Y-%m-%d %H:%M:%S')
            except:
                pass

        if not published_at:
            # 嘗試從 JSON-LD 取得 (CTI 現在主要使用這種方式儲存 metadata)
            try:
                ld_json_node = soup.select_one('script[type="application/ld+json"]')
                if ld_json_node:
                    ld_data = json.loads(ld_json_node.string)
                    if isinstance(ld_data, dict) and ld_data.get('datePublished'):
                        dt = parser.parse(ld_data['datePublished'])
                        published_at = dt.strftime('%Y-%m-%d %H:%M:%S')
            except:
                pass

        if not published_at:
            time_node = soup.select_one('time.pub-date') or soup.select_one('time')
            if time_node:
                # 嘗試取得 datetime 屬性
                time_str = time_node.get('datetime') or time_node.get_text(strip=True)
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
            timeout=15,
            verify=True
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
        resp = http_session.get(LIST_URL, timeout=15)
        # 匹配 /news/items/XXXX
        item_paths = re.findall(r'/news/items/[a-zA-Z0-9]+', resp.text)
        # 規範化 URL：移除 query string 和結尾斜線
        urls = list(set([("https://ctinews.com" + path).split('?')[0].split('#')[0].rstrip('/') for path in item_paths]))
    except Exception as e:
        return f"Failed to fetch list: {e}", 500

    if not urls:
        return "No URLs found in list", 200

    new_urls = get_new_urls(urls)
    print(f"Found {len(new_urls)} new URLs out of {len(urls)}")
    
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
