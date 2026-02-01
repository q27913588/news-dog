import sys
import os
import json

# Add the scrapers/ltn directory to sys.path
sys.path.append(os.path.join(os.getcwd(), 'scrapers', 'ltn'))

import main

class MockRequest:
    def __init__(self):
        pass

if __name__ == "__main__":
    print("Testing LTN scraper locally...")
    # Override INGEST_API_BASE to avoid actual ingestion during testing if needed
    # For now, let's just see if it finds URLs and scrapes
    
    # We will mock get_new_urls and ingest_article to avoid calling the real backend
    original_get_new_urls = main.get_new_urls
    original_ingest_article = main.ingest_article
    
    def mock_get_new_urls(urls):
        print(f"Mocked: Found {len(urls)} total URLs")
        print(f"First 5 URLs: {urls[:5]}")
        return urls[:2] # Just return first 2 as 'new' for testing
        
    def mock_ingest_article(data):
        print(f"Mocked: Ingesting article: {data['title']}")
        return True
        
    main.get_new_urls = mock_get_new_urls
    main.ingest_article = mock_ingest_article
    
    try:
        response_text, status_code = main.run_scraper(MockRequest())
        print(f"Response: {response_text}")
        print(f"Status Code: {status_code}")
    except Exception as e:
        print(f"Scraper failed with error: {e}")
