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
SOURCE_CODE = 'SET'
RSS_URL = 'https://www.setn.com/rss.aspx'

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

    # 3. 從 figcaption 提取攝影師（SET 使用 figure + figcaption）
    figcaption = soup.select_one('#ckuse figcaption') or soup.select_one('[itemprop="articleBody"] figcaption')
    if figcaption:
        photographer = extract_photographer(figcaption.get_text())

    # 4. 備用：從第一張圖片 alt 提取
    if not photographer:
        content_area = soup.select_one('#ckuse') or soup.select_one('[itemprop="articleBody"]')
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

        # 三立新聞的選擇器
        title_node = soup.select_one('h1.news-title')
        if not title_node:
            title_node = soup.select_one('h1')
        title = title_node.get_text(strip=True) if title_node else ""

        # 使用 itemprop="articleBody" 較為穩定
        content_node = soup.select_one('[itemprop="articleBody"]')
        if not content_node:
            content_node = soup.select_one('div#Content1')
        if not content_node:
            content_node = soup.select_one('article')

        if content_node:
            for tag in content_node.select('script, style, .article-ads, .fb-quote'):
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
            # 三立新聞的新選擇器 time.page_date
            time_node = soup.select_one('time.page_date') or soup.select_one('time.page-date') or soup.select_one('span.date')
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
    all_urls = []
    
    # 方法1: 使用分類頁面
    # PageGroupID: 6 (政治), 41 (社會), 5 (國際)
    GROUP_IDS = ['6', '41', '5']
    
    for group_id in GROUP_IDS:
        list_url = f'https://www.setn.com/ViewAll.aspx?PageGroupID={group_id}'
        try:
            resp = http_session.get(list_url, timeout=15)
            soup = BeautifulSoup(resp.text, 'lxml')
            
            # 嘗試多個選擇器
            links = soup.select('h3.view-li-title a')
            if not links:
                # 備用選擇器
                links = soup.select('div.view-li-title a')
            if not links:
                links = soup.select('div.newsItems h3 a')
            if not links:
                # 最後嘗試所有包含 /News.aspx 的連結
                links = soup.select('a[href*="/News.aspx"]')
            
            print(f"Found {len(links)} links in group {group_id} using selector")
            
            for a in links:
                href = a.get('href', '')
                if not href or '/News.aspx' not in href:
                    continue
                    
                if href.startswith('http'):
                    full_url = href
                else:
                    full_url = "https://www.setn.com" + href
                
                # 修正雙重 prefix 的問題 (如果有)
                if "https://www.setn.comhttps://" in full_url:
                    full_url = full_url.replace("https://www.setn.comhttps://", "https://")
                
                # 三立特殊處理：保留 NewsID 參數，但移除其他參數
                if '?' in full_url and 'NewsID=' in full_url:
                    # 提取 NewsID
                    match = re.search(r'NewsID=(\d+)', full_url)
                    if match:
                        news_id = match.group(1)
                        full_url = f"https://www.setn.com/News.aspx?NewsID={news_id}"
                else:
                    # 沒有 NewsID 的情況，移除所有參數
                    full_url = full_url.split('?')[0].split('#')[0].rstrip('/')
                    
                all_urls.append(full_url)
        except Exception as e:
            print(f"Failed to fetch {group_id} list: {e}")
    
    # 方法2: 如果分類頁抓不到，嘗試從首頁抓取
    if len(all_urls) < 5:
        print(f"Warning: Only found {len(all_urls)} URLs from categories, trying homepage...")
        try:
            resp = http_session.get('https://www.setn.com/', timeout=15)
            soup = BeautifulSoup(resp.text, 'lxml')
            import re
            # 使用正則表達式找出所有新聞連結
            news_links = re.findall(r'NewsID=(\d+)', resp.text)
            print(f"Found {len(news_links)} news links from homepage")
            for news_id in set(news_links):
                full_url = f"https://www.setn.com/News.aspx?NewsID={news_id}"
                all_urls.append(full_url)
        except Exception as e:
            print(f"Failed to fetch homepage: {e}")

    if not all_urls:
        return "No URLs found in categories", 200

    unique_urls = list(set(all_urls))
    new_urls = get_new_urls(unique_urls)
    print(f"Found {len(new_urls)} new URLs out of {len(unique_urls)}")
    
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
