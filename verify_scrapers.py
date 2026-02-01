import sys
import os
import requests
from bs4 import BeautifulSoup

def test_source(name, path, url, verify=True):
    print(f"--- Testing {name} ---")
    if path not in sys.path:
        sys.path.append(path)
    import main
    # Ensure we use the latest version of main
    import importlib
    importlib.reload(main)
    
    try:
        import urllib3
        urllib3.disable_warnings()
        data = main.scrape_article(url)
        if data:
            print(f"Title: {data['title']}")
            print(f"Date: {data['publishedAt']}")
            print(f"Content Length: {len(data['cleanText'])}")
            if len(data['cleanText']) < 50:
                print("⚠️ Warning: Content too short!")
        else:
            print("❌ Failed to scrape article")
    except Exception as e:
        print(f"❌ Error: {e}")
    print()

if __name__ == "__main__":
    base_dir = os.getcwd()
    
    # Test SET
    test_source("SET", os.path.join(base_dir, 'scrapers', 'set'), 
                "https://www.setn.com/News.aspx?NewsID=1782549")
    
    # Test LTN
    test_source("LTN", os.path.join(base_dir, 'scrapers', 'ltn'), 
                "https://news.ltn.com.tw/news/politics/breakingnews/5313436")
    
    # Test CTI
    test_source("CTI", os.path.join(base_dir, 'scrapers', 'cti'), 
                "https://ctinews.com/news/items/6BalmdN3xQ")
