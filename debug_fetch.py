#!/usr/bin/env python3
"""
Simple test for fetch_article function debugging.
"""

import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_simple_fetch(url: str):
    """Test simple HTTP fetch without processing."""
    print(f"\nTesting simple fetch for: {url}")
    
    try:
        import requests
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        
        print("Making HTTP request...")
        response = requests.get(url, timeout=15, headers=headers)
        print(f"✅ HTTP {response.status_code} - Content length: {len(response.text)} chars")
        
        return response.text
        
    except Exception as e:
        print(f"❌ HTTP fetch error: {e}")
        return None

def test_trafilatura(html_content: str, url: str):
    """Test trafilatura extraction."""
    print("\nTesting trafilatura extraction...")
    
    try:
        import trafilatura
        
        extracted = trafilatura.extract(
            html_content,
            output_format='json',
            include_comments=False,
            include_tables=True,
            include_images=True,
            url=url
        )
        
        if extracted:
            try:
                content_json = json.loads(extracted)
                text_length = len(content_json.get('text', ''))
                
                print(f"✅ Trafilatura extraction successful")
                print(f"   Title: {content_json.get('title', 'N/A')}")
                print(f"   Text length: {text_length} chars")
                print(f"   Author: {content_json.get('author', 'N/A')}")
                print(f"   Date: {content_json.get('date', 'N/A')}")
                
                if text_length > 200:
                    print("✅ Good content length (>200 chars)")
                    return content_json
                else:
                    print("⚠️  Content too short (<200 chars)")
                    return None
                    
            except json.JSONDecodeError as e:
                print(f"❌ JSON decode error: {e}")
                return None
        else:
            print("❌ Trafilatura returned no content")
            return None
            
    except Exception as e:
        print(f"❌ Trafilatura error: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_readability_fallback(html_content: str):
    """Test readability fallback."""
    print("\nTesting readability fallback...")
    
    try:
        from readability import Document
        from bs4 import BeautifulSoup
        
        doc = Document(html_content)
        title = doc.title()
        content_html = doc.summary()
        
        # Parse content
        soup = BeautifulSoup(content_html, 'html.parser')
        text_content = soup.get_text(separator='\n', strip=True)
        
        print(f"✅ Readability extraction successful")
        print(f"   Title: {title}")
        print(f"   Text length: {len(text_content)} chars")
        
        return {
            'title': title,
            'text': text_content,
            'length': len(text_content)
        }
        
    except Exception as e:
        print(f"❌ Readability error: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    print("FETCH ARTICLE DEBUG TOOL")
    print("=" * 50)
    
    # Step 3: Get URL from user
    if len(sys.argv) > 1:
        test_url = sys.argv[1]
    else:
        test_url = input("\nEnter a news article URL to test: ").strip()
        
    if not test_url:
        print("No URL provided. Exiting.")
        return
    
    print(f"\n🔍 DEBUGGING URL: {test_url}")
    print("=" * 50)
    
    # Step 4: Test simple HTTP fetch
    html_content = test_simple_fetch(test_url)
    if not html_content:
        print("❌ HTTP fetch failed. Cannot continue.")
        return
    
    # Step 5: Test trafilatura
    trafilatura_result = test_trafilatura(html_content, test_url)
    
    # Step 6: Test readability fallback
    readability_result = test_readability_fallback(html_content)
    
    # Step 7: Test the full function
    print("\n" + "=" * 50)
    print("TESTING FULL fetch_article FUNCTION")
    print("=" * 50)
    
    try:
        from news_fetcher.tools import fetch_article
        result = fetch_article(test_url)
        
        print("RESULT:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"❌ Full function error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()