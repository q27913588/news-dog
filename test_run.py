import sys
import os

# Add the scrapers/set directory to sys.path
sys.path.append(os.path.join(os.getcwd(), 'scrapers', 'set'))

import main

class MockRequest:
    def __init__(self):
        pass

if __name__ == "__main__":
    print("Running SET scraper locally...")
    # Use the default production URL and API Key from the main.py
    # or override if needed for local testing
    # os.environ['INGEST_API_BASE'] = 'http://localhost:8080/ingest'
    
    response_text, status_code = main.run_scraper(MockRequest())
    print(f"Response: {response_text}")
    print(f"Status Code: {status_code}")
