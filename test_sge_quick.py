#!/usr/bin/env python3
"""
Quick test: Check if SGE page loads and what content we get
"""

from playwright.sync_api import sync_playwright
import sys

url = "https://en.sge.com.cn/h5_data_SilverBenchmarkPrice"

print(f"Testing page load...")
print(f"URL: {url}")

try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(30000)  # 30 sec timeout for operations
        
        print(f"Navigating to page (with 30s timeout)...")
        try:
            response = page.goto(url, wait_until="domcontentloaded")  # Don't wait for full load
            print(f"Response status: {response.status if response else 'None'}")
        except Exception as e:
            print(f"Navigation timeout, but continuing with what we have...")
        
        print(f"Waiting 10 seconds for JavaScript to render...")
        import time
        time.sleep(10)
        
        print(f"Page title: {page.title()}")
        
        # Check if SHAG exists on initial load (before JS)
        content = page.content()
        
        if "SHAG" in content:
            print(f"✓ SHAG found in initial HTML")
        else:
            print(f"✗ SHAG not in initial HTML (JS rendering needed)")
        
        # Try waiting for any table
        try:
            page.wait_for_selector("table", timeout=5000)
            print(f"✓ Table appeared after waiting")
            
            # Get content again
            content = page.content()
            if "SHAG" in content:
                print(f"✓ SHAG now visible in HTML")
                # Extract a snippet
                idx = content.find("SHAG")
                print(f"\nContent around SHAG:")
                print(content[max(0, idx-200):idx+200])
            else:
                print(f"✗ SHAG still not visible")
        except:
            print(f"✗ Table didn't appear (timeout)")
        
        browser.close()
        print(f"\n✓ Test completed")
        
except Exception as e:
    print(f"✗ Error: {type(e).__name__}: {e}")
    sys.exit(1)
