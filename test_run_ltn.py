import sys
import os

# Add the scrapers/ltn directory to sys.path
sys.path.append(os.path.join(os.getcwd(), 'scrapers', 'ltn'))

import main

class MockRequest:
    def __init__(self):
        pass

if __name__ == "__main__":
    print("Running LTN scraper locally...")
    response_text, status_code = main.run_scraper(MockRequest())
    print(f"Response: {response_text}")
    print(f"Status Code: {status_code}")
