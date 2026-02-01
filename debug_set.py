import sys
import os
import json
import re

# Add the scrapers/set directory to sys.path
sys.path.append(os.path.join(os.getcwd(), 'scrapers', 'set'))

import main

class MockRequest:
    def __init__(self):
        pass

if __name__ == "__main__":
    print("Testing SET scraper locally...")
    
    # Mocking
    def mock_get_new_urls(urls):
        print(f"Mocked: Found {len(urls)} total URLs")
        print(f"First 5 URLs: {urls[:5]}")
        return urls[:2]
        
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
