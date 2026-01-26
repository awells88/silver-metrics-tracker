"""
Fetch silver spot prices from multiple sources.
Primary: Kitco, Backup: Yahoo Finance (yfinance)
"""

import logging
import re
from datetime import datetime
from typing import Optional, Dict, Any

import requests
from bs4 import BeautifulSoup

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False

from scripts.config import (
    KITCO_SPOT_URL, 
    YAHOO_SILVER_SYMBOL,
    REQUEST_HEADERS
)
from scripts.db import insert_spot_price

logger = logging.getLogger(__name__)


def fetch_kitco_spot() -> Optional[Dict[str, Any]]:
    """
    Fetch current silver spot price from Kitco.
    Returns dict with price_usd, change_24h, change_pct_24h, source.
    """
    try:
        response = requests.get(KITCO_SPOT_URL, headers=REQUEST_HEADERS, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Kitco embeds price data in various formats - try multiple selectors
        price_data = None
        
        # Try finding price in common Kitco page structures
        # Look for silver price elements
        price_elements = soup.find_all(['span', 'div'], class_=re.compile(r'price|bid|ask', re.I))
        
        for elem in price_elements:
            text = elem.get_text(strip=True)
            # Look for dollar amounts
            match = re.search(r'\$?([\d,]+\.?\d*)', text)
            if match:
                try:
                    price = float(match.group(1).replace(',', ''))
                    # Silver typically between $15-$150/oz
                    if 15 <= price <= 200:
                        price_data = price
                        break
                except ValueError:
                    continue
        
        # Alternative: look for specific data attributes or script tags
        if price_data is None:
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string:
                    # Look for JSON-like price data
                    match = re.search(r'"silver"[^}]*"price":\s*([\d.]+)', script.string, re.I)
                    if match:
                        price_data = float(match.group(1))
                        break
                    # Alternative pattern
                    match = re.search(r'silver[^{]*bid[^:]*:\s*([\d.]+)', script.string, re.I)
                    if match:
                        price_data = float(match.group(1))
                        break
        
        if price_data:
            logger.info(f"Kitco spot price: ${price_data:.2f}")
            return {
                'source': 'kitco',
                'price_usd': price_data,
                'change_24h': None,  # Would need additional parsing
                'change_pct_24h': None,
                'timestamp': datetime.now().isoformat()
            }
        
        logger.warning("Could not parse Kitco price data")
        return None
        
    except requests.RequestException as e:
        logger.error(f"Error fetching Kitco data: {e}")
        return None
    except Exception as e:
        logger.error(f"Error parsing Kitco data: {e}")
        return None


def fetch_yahoo_spot() -> Optional[Dict[str, Any]]:
    """
    Fetch silver futures price from Yahoo Finance using yfinance library.
    More reliable than scraping, uses SI=F (Silver Futures) symbol.
    """
    if not YFINANCE_AVAILABLE:
        logger.warning("yfinance not available")
        return None
    
    try:
        ticker = yf.Ticker(YAHOO_SILVER_SYMBOL)
        
        # Get current price data
        info = ticker.info
        
        # Try multiple fields for current price
        price = None
        for field in ['regularMarketPrice', 'previousClose', 'ask', 'bid']:
            if field in info and info[field]:
                price = float(info[field])
                break
        
        if price is None:
            # Fallback: get from history
            hist = ticker.history(period='1d')
            if not hist.empty:
                price = float(hist['Close'].iloc[-1])
        
        if price:
            # Get change data
            prev_close = info.get('previousClose') or info.get('regularMarketPreviousClose')
            change_24h = None
            change_pct = None
            
            if prev_close:
                change_24h = price - prev_close
                change_pct = (change_24h / prev_close) * 100
            
            logger.info(f"Yahoo Finance spot price: ${price:.2f}")
            return {
                'source': 'yahoo_finance',
                'price_usd': price,
                'change_24h': round(change_24h, 4) if change_24h else None,
                'change_pct_24h': round(change_pct, 2) if change_pct else None,
                'timestamp': datetime.now().isoformat()
            }
        
        logger.warning("Could not get Yahoo Finance price")
        return None
        
    except Exception as e:
        logger.error(f"Error fetching Yahoo Finance data: {e}")
        return None


def fetch_spot_price() -> Optional[Dict[str, Any]]:
    """
    Fetch spot price from available sources.
    Tries Kitco first, then Yahoo Finance as backup.
    Stores result in database.
    """
    # Try Yahoo Finance first (more reliable programmatic access)
    data = fetch_yahoo_spot()
    
    if data is None:
        # Fallback to Kitco scraping
        data = fetch_kitco_spot()
    
    if data:
        # Store in database
        try:
            insert_spot_price(
                source=data['source'],
                price_usd=data['price_usd'],
                change_24h=data.get('change_24h'),
                change_pct_24h=data.get('change_pct_24h')
            )
            logger.info(f"Stored spot price: ${data['price_usd']:.2f} from {data['source']}")
        except Exception as e:
            logger.error(f"Error storing spot price: {e}")
        
        return data
    
    logger.error("Failed to fetch spot price from all sources")
    return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("Testing spot price fetchers...")
    
    print("\n1. Yahoo Finance:")
    yahoo_data = fetch_yahoo_spot()
    if yahoo_data:
        print(f"   Price: ${yahoo_data['price_usd']:.2f}")
        print(f"   Change: {yahoo_data.get('change_pct_24h', 'N/A')}%")
    else:
        print("   Failed")
    
    print("\n2. Kitco:")
    kitco_data = fetch_kitco_spot()
    if kitco_data:
        print(f"   Price: ${kitco_data['price_usd']:.2f}")
    else:
        print("   Failed")
    
    print("\n3. Combined fetch (with DB storage):")
    from scripts.db import init_database
    init_database()
    combined = fetch_spot_price()
    if combined:
        print(f"   Final price: ${combined['price_usd']:.2f} from {combined['source']}")
