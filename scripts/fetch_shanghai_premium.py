"""
Fetch Shanghai silver premium data using Playwright + SGE official source.
Primary source: en.sge.com.cn (official SGE benchmark price in CNY/kg)
Fallback: Manual values

The premium is the difference between Shanghai silver price (SGE in CNY/kg converted to USD)
and Western spot price (from MetalpriceAPI in USD), reflecting import demand and arbitrage.
"""

import logging
import os
import re
import time
from datetime import datetime
from typing import Optional, Dict, Any

import requests

from scripts.config import REQUEST_HEADERS
from scripts.db import insert_shanghai_premium

logger = logging.getLogger(__name__)

# Data sources
SGE_OFFICIAL_URL = "https://en.sge.com.cn/h5_data_SilverBenchmarkPrice"

# MetalpriceAPI configuration (for Western spot price)
METALPRICEAPI_URL = "https://api.metalpriceapi.com/v1/latest"
METALPRICEAPI_KEY = os.environ.get("METALPRICEAPI_KEY", "")


def fetch_sge_official_with_playwright() -> Optional[Dict[str, Any]]:
    """
    Fetch official SGE silver benchmark price using Playwright.
    Price is in CNY/kg and needs conversion to USD/oz.
    
    Waits 10 seconds for JavaScript to render the price data.
    
    Returns:
        Dict with shanghai_spot in USD/oz or None
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("Playwright not installed - cannot scrape SGE. Install with: pip install playwright")
        return None
    
    try:
        today = datetime.now().strftime('%Y%m%d')
        
        with sync_playwright() as p:
            # Launch browser
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_default_timeout(30000)
            
            try:
                # Navigate to SGE page
                logger.debug(f"Loading SGE price page...")
                page.goto(SGE_OFFICIAL_URL, wait_until="domcontentloaded", timeout=30000)
                
                # Wait for JavaScript to render the data table
                logger.debug(f"Waiting 10 seconds for JavaScript rendering...")
                time.sleep(10)
                
                # Get page content
                content = page.content()
                
                # Parse the price from HTML
                # Format in table: <td>20260126</td><td>SHAG</td><td>27510</td><td>27417</td>
                pattern = rf'{today}\s*</td>\s*<td>\s*SHAG\s*</td>\s*<td>\s*([\d]+)\s*</td>'
                match = re.search(pattern, content)
                
                if match:
                    cny_per_kg = float(match.group(1))
                    logger.debug(f"Found SGE silver price: {cny_per_kg} CNY/kg")
                    
                    # Convert CNY/kg to USD/oz
                    # 1 kg = 32.1507 troy oz
                    # USD/CNY exchange rate (approximate)
                    usd_cny_rate = 7.25
                    
                    cny_per_oz = cny_per_kg / 32.1507
                    usd_per_oz = cny_per_oz / usd_cny_rate
                    
                    logger.info(f"SGE official: {cny_per_kg} CNY/kg = ${usd_per_oz:.2f}/oz")
                    
                    return {
                        'shanghai_spot': usd_per_oz,
                        'source': 'sge_official'
                    }
                else:
                    logger.warning(f"Could not find SGE price pattern for {today}")
                    return None
                    
            finally:
                browser.close()
            
    except ImportError:
        logger.warning("Playwright not installed")
        return None
    except Exception as e:
        logger.error(f"Error fetching SGE with Playwright: {e}")
        return None


def fetch_shanghai_premium() -> Optional[Dict[str, Any]]:
    """
    Fetch Shanghai silver premium.
    
    Strategy:
    1. Try SGE official source via Playwright (actual SGE price in CNY/kg)
    2. Fallback to MetalpriceAPI for Western spot + manual premium
    3. Final fallback to fully manual values
    
    Returns:
        Dict with shanghai_spot, western_spot, premium_usd, premium_pct
    """
    data = {
        'shanghai_spot': None,
        'western_spot': None,
        'premium_usd': None,
        'premium_pct': None
    }
    
    # Try SGE official first
    sge_data = fetch_sge_official_with_playwright()
    
    if sge_data and sge_data.get('shanghai_spot'):
        # Got SGE price, now need Western spot for comparison
        try:
            from scripts.db import get_latest_spot_price
            latest_spot = get_latest_spot_price()
            if latest_spot and latest_spot.get('price_usd'):
                data['western_spot'] = latest_spot['price_usd']
                data['shanghai_spot'] = sge_data['shanghai_spot']
                data['premium_usd'] = data['shanghai_spot'] - data['western_spot']
                data['premium_pct'] = (data['premium_usd'] / data['western_spot']) * 100
                source = "SGE_official"
                
                logger.info(
                    f"Using SGE official: Shanghai ${data['shanghai_spot']:.2f}, "
                    f"Western ${data['western_spot']:.2f}, "
                    f"Premium +${data['premium_usd']:.2f} ({data['premium_pct']:.2f}%)"
                )
                
                # Insert into database
                insert_shanghai_premium(
                    shanghai_spot=data['shanghai_spot'],
                    western_spot=data['western_spot'],
                    premium_usd=data['premium_usd'],
                    premium_pct=data['premium_pct'],
                    source=source
                )
                
                return data
        except Exception as e:
            logger.warning(f"Could not get Western spot for SGE comparison: {e}")
    
    # Fallback: Use observed premium + Western spot
    observed_premium_usd = 11.58  # From metalcharts.org (Jan 26, 2026)
    
    try:
        from scripts.db import get_latest_spot_price
        latest_spot = get_latest_spot_price()
        if latest_spot and latest_spot.get('price_usd'):
            data['western_spot'] = latest_spot['price_usd']
            data['premium_usd'] = observed_premium_usd
            data['shanghai_spot'] = data['western_spot'] + observed_premium_usd
            data['premium_pct'] = (observed_premium_usd / data['western_spot']) * 100
            source = "DB_spot"
            
            logger.info(
                f"Using DB spot ${data['western_spot']:.2f} + "
                f"observed premium ${observed_premium_usd:.2f}"
            )
            
            insert_shanghai_premium(
                shanghai_spot=data['shanghai_spot'],
                western_spot=data['western_spot'],
                premium_usd=data['premium_usd'],
                premium_pct=data['premium_pct'],
                source=source
            )
            
            return data
    except Exception as e:
        logger.warning(f"Could not get Western spot from database: {e}")
    
    # Final fallback to fully manual values
    return use_manual_shanghai_premium()


def use_manual_shanghai_premium() -> Optional[Dict[str, Any]]:
    """
    Use manually-set Shanghai premium when API is unavailable.
    
    Update these values periodically based on: https://metalcharts.org/shanghai
    
    Current values (as of Jan 26, 2026):
    - Shanghai Spot: ~$119.76/oz
    - Western Spot: ~$108.18/oz  
    - Premium: +$11.58 (10.70%)
    """
    # MANUAL UPDATE: Set these values from https://metalcharts.org/shanghai
    manual_premium_usd = 11.58  # Updated Jan 26, 2026
    
    # Try to get actual Western spot from database
    try:
        from scripts.db import get_latest_spot_price
        latest_spot = get_latest_spot_price()
        if latest_spot and latest_spot.get('price_usd'):
            western_spot = latest_spot['price_usd']
            shanghai_spot = western_spot + manual_premium_usd
            premium_pct = (manual_premium_usd / western_spot) * 100
        else:
            # Fully manual fallback
            western_spot = 108.18
            shanghai_spot = 119.76
            premium_pct = 10.70
    except:
        western_spot = 108.18
        shanghai_spot = 119.76
        premium_pct = 10.70
    
    data = {
        'shanghai_spot': shanghai_spot,
        'western_spot': western_spot,
        'premium_usd': manual_premium_usd,
        'premium_pct': premium_pct
    }
    
    logger.warning(
        f"Using MANUAL Shanghai premium: +${manual_premium_usd:.2f}/oz "
        f"({premium_pct:.2f}%)"
    )
    
    # Insert manual data
    insert_shanghai_premium(
        shanghai_spot=data['shanghai_spot'],
        western_spot=data['western_spot'],
        premium_usd=data['premium_usd'],
        premium_pct=data['premium_pct'],
        source="MANUAL"
    )
    
    return data


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    result = fetch_shanghai_premium()
    if result:
        print(f"Shanghai Spot: ${result['shanghai_spot']:.2f}")
        print(f"Western Spot: ${result['western_spot']:.2f}")
        print(f"Premium: +${result['premium_usd']:.2f} ({result['premium_pct']:.2f}%)")
    else:
        print("Failed to fetch Shanghai premium data")
