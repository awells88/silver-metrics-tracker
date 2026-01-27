#!/usr/bin/env python3
"""
Test script to scrape SGE silver prices using Playwright.
Tests if we can extract the actual CNY/kg price from the rendered page.
"""

from playwright.sync_api import sync_playwright
from datetime import datetime
import time
import re

def test_sge_scrape():
    """Test scraping SGE with Playwright"""
    
    url = "https://en.sge.com.cn/h5_data_SilverBenchmarkPrice"
    today = datetime.now().strftime('%Y%m%d')
    
    print(f"Testing Playwright scrape of SGE silver prices...")
    print(f"Target date: {today}")
    print(f"URL: {url}")
    print("=" * 80)
    
    with sync_playwright() as p:
        # Launch browser (headless - no UI)
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Set timeout for page loads
        page.set_default_timeout(30000)
        
        try:
            print(f"Loading page...")
            page.goto(url)
            
            # Wait for table to load
            print(f"Waiting for table to render...")
            page.wait_for_selector("table", timeout=10000)
            time.sleep(2)  # Extra wait for JS to finish rendering
            
            # Get all table text
            table_content = page.content()
            
            # Print first 2000 chars of table to see structure
            print(f"\nTable HTML (first 1500 chars):")
            print(table_content[:1500])
            print("\n" + "=" * 80)
            
            # Try to find price data
            # Look for SHAG in the table
            if "SHAG" in table_content:
                print("✓ Found SHAG in page content")
                
                # Extract lines with SHAG
                lines = table_content.split('\n')
                shag_lines = [line for line in lines if 'SHAG' in line]
                print(f"\nLines containing SHAG ({len(shag_lines)} found):")
                for i, line in enumerate(shag_lines[:5]):
                    print(f"  {i+1}: {line[:200]}")
            else:
                print("✗ SHAG not found in page content")
            
            # Try different selectors to get text content
            print(f"\n" + "=" * 80)
            print("Attempting to extract prices using different methods...")
            
            # Method 1: Get all table rows
            rows = page.query_selector_all("tr")
            print(f"\nFound {len(rows)} table rows")
            
            if rows:
                for i, row in enumerate(rows[:5]):
                    cells = row.query_selector_all("td")
                    if cells:
                        cell_texts = [cell.inner_text() for cell in cells]
                        print(f"Row {i+1}: {cell_texts}")
                        
                        # Check if this row has today's date and SHAG
                        if len(cell_texts) > 2 and today[:4] in cell_texts[0]:
                            print(f"  → Found date row: {cell_texts}")
            
            # Method 2: Search for date pattern
            print(f"\n" + "=" * 80)
            print(f"Searching for price patterns...")
            
            # Get all text content
            all_text = page.inner_text("body")
            
            # Look for date followed by SHAG and price
            pattern = rf'{today}\s+SHAG\s+([\d]+)'
            matches = re.findall(pattern, all_text)
            
            if matches:
                print(f"✓ Found prices matching pattern: {pattern}")
                for match in matches:
                    print(f"  Price: {match} CNY/kg")
                    
                    # Convert to USD/oz
                    cny_per_kg = float(match)
                    cny_per_oz = cny_per_kg / 32.1507
                    usd_per_oz = cny_per_oz / 7.25
                    print(f"  Converted: ${usd_per_oz:.2f}/oz")
            else:
                print(f"✗ No prices found matching pattern: {pattern}")
                print(f"\nSearching for any numeric patterns near SHAG...")
                
                # Find SHAG positions
                shag_matches = re.finditer(r'SHAG', all_text)
                for match in list(shag_matches)[:3]:
                    start = max(0, match.start() - 100)
                    end = min(len(all_text), match.end() + 100)
                    context = all_text[start:end]
                    print(f"\nContext around SHAG:\n{context}\n---")
            
            browser.close()
            print("\n✓ Test completed successfully")
            
        except Exception as e:
            print(f"✗ Error: {e}")
            browser.close()
            return False
    
    return True

if __name__ == "__main__":
    success = test_sge_scrape()
    exit(0 if success else 1)
