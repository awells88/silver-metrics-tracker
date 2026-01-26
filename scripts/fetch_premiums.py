"""
Fetch physical silver premium data.
Primary source: papervsphysical.com (aggregates multiple dealers)
Backup: Direct dealer scraping
"""

import logging
import re
from datetime import datetime
from typing import Optional, Dict, Any, List

import requests
from bs4 import BeautifulSoup

from scripts.config import PAPER_VS_PHYSICAL_URL, REQUEST_HEADERS
from scripts.db import insert_premium

logger = logging.getLogger(__name__)


def fetch_paper_vs_physical() -> Optional[Dict[str, Any]]:
    """
    Fetch premium data from papervsphysical.com.
    This site tracks the spread between paper (spot) and physical silver prices.
    """
    try:
        # Try without www first, then with www
        urls_to_try = [
            "https://papervsphysical.com",
            PAPER_VS_PHYSICAL_URL
        ]
        
        response = None
        for url in urls_to_try:
            try:
                response = requests.get(
                    url,
                    headers=REQUEST_HEADERS,
                    timeout=30,
                    verify=True  # Try with verification first
                )
                response.raise_for_status()
                break
            except requests.exceptions.SSLError:
                # Try without SSL verification as fallback
                try:
                    response = requests.get(
                        url,
                        headers=REQUEST_HEADERS,
                        timeout=30,
                        verify=False
                    )
                    response.raise_for_status()
                    logger.warning(f"SSL verification disabled for {url}")
                    break
                except:
                    continue
            except:
                continue
        
        if response is None:
            logger.warning("Could not connect to papervsphysical.com")
            return None
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        # papervsphysical.com displays paper price, physical price, and spread
        data = {
            'paper_price': None,
            'physical_price': None,
            'premium_pct': None,
            'premium_usd': None
        }
        
        # Look for price displays
        # The site shows: PAPER / SPOT PRICE ─ $111.85, AVG PHYSICAL PRICE ─ $127.09, SPREAD +13.6%
        text = soup.get_text()
        
        # Find paper/spot price - format: "PAPER / SPOT PRICE ─ $111.85" or "paper price: $111.85"
        paper_patterns = [
            r'PAPER\s*/\s*SPOT\s*PRICE\s*[─\-]\s*\$?([\d,]+\.?\d*)',
            r'paper\s*(?:/\s*spot)?\s*(?:price)?[:\s─\-]*\$?([\d,]+\.?\d*)',
            r'spot\s*(?:price)?[:\s─\-]*\$?([\d,]+\.?\d*)',
        ]
        for pattern in paper_patterns:
            paper_match = re.search(pattern, text, re.I)
            if paper_match:
                data['paper_price'] = float(paper_match.group(1).replace(',', ''))
                break
        
        # Find physical price - format: "AVG PHYSICAL PRICE ─ $127.09" or "physical price: $127.09"
        physical_patterns = [
            r'AVG\s*PHYSICAL\s*PRICE\s*[─\-]\s*\$?([\d,]+\.?\d*)',
            r'physical\s*(?:price)?[:\s─\-]*\$?([\d,]+\.?\d*)',
            r'avg\.?\s*physical[:\s─\-]*\$?([\d,]+\.?\d*)',
        ]
        for pattern in physical_patterns:
            physical_match = re.search(pattern, text, re.I)
            if physical_match:
                data['physical_price'] = float(physical_match.group(1).replace(',', ''))
                break
        
        # Find spread/premium percentage - format: "SPREAD +13.6%" or "spread: 13.6%"
        spread_patterns = [
            r'SPREAD\s*([+-]?[\d.]+)\s*%',
            r'(?:spread|premium)[:\s]*([+-]?[\d.]+)\s*%',
        ]
        spread_match = None
        for pattern in spread_patterns:
            spread_match = re.search(pattern, text, re.I)
            if spread_match:
                break
        
        if spread_match:
            data['premium_pct'] = float(spread_match.group(1))
        
        # Alternative: look for specific elements
        if data['paper_price'] is None or data['physical_price'] is None:
            # Try to find price elements
            price_elements = soup.find_all(['span', 'div', 'p'], 
                class_=re.compile(r'price|value|amount', re.I))
            
            prices = []
            for elem in price_elements:
                text = elem.get_text(strip=True)
                match = re.search(r'\$?([\d,]+\.?\d*)', text)
                if match:
                    try:
                        price = float(match.group(1).replace(',', ''))
                        if 15 <= price <= 200:  # Reasonable silver price range
                            prices.append(price)
                    except ValueError:
                        continue
            
            if len(prices) >= 2:
                prices.sort()
                data['paper_price'] = prices[0]  # Lower = paper/spot
                data['physical_price'] = prices[-1]  # Higher = physical
        
        # Calculate derived values
        if data['paper_price'] and data['physical_price']:
            data['premium_usd'] = data['physical_price'] - data['paper_price']
            if data['premium_pct'] is None:
                data['premium_pct'] = (data['premium_usd'] / data['paper_price']) * 100
        
        if data['paper_price'] and data['physical_price']:
            logger.info(f"papervsphysical.com - Paper: ${data['paper_price']:.2f}, "
                       f"Physical: ${data['physical_price']:.2f}, "
                       f"Premium: {data['premium_pct']:.1f}%")
            
            return {
                'source': 'papervsphysical',
                'product_type': 'aggregate',
                'spot_price': data['paper_price'],
                'physical_price': data['physical_price'],
                'premium_usd': data['premium_usd'],
                'premium_pct': data['premium_pct'],
                'timestamp': datetime.now().isoformat()
            }
        
        logger.warning("Could not parse papervsphysical.com data")
        return None
        
    except requests.RequestException as e:
        logger.error(f"Error fetching papervsphysical.com: {e}")
        return None
    except Exception as e:
        logger.error(f"Error parsing papervsphysical.com: {e}")
        return None


def fetch_dealer_prices(spot_price: float) -> List[Dict[str, Any]]:
    """
    Fetch prices from individual dealers for premium calculation.
    This is a backup if papervsphysical.com is unavailable.
    
    Note: This requires careful implementation to respect robots.txt
    and avoid overloading dealer websites.
    """
    dealers = [
        {
            'name': 'generic',
            'url': None,  # Placeholder - would need actual URLs
            'product': '1oz Silver Round'
        }
    ]
    
    results = []
    
    # For now, return empty - implement specific dealer scrapers as needed
    # This is intentionally minimal to avoid aggressive scraping
    
    logger.info("Dealer scraping not implemented - using papervsphysical.com")
    return results


def calculate_premium_status(premium_pct: float) -> Dict[str, Any]:
    """
    Determine premium status based on thresholds.
    """
    if premium_pct <= 10:
        status = 'green'
        label = 'Normal'
    elif premium_pct <= 20:
        status = 'yellow'
        label = 'Elevated'
    elif premium_pct <= 50:
        status = 'red'
        label = 'High'
    else:
        status = 'red'
        label = 'Extreme'
    
    return {
        'status': status,
        'label': label,
        'premium_pct': premium_pct
    }


def fetch_premiums(spot_price: float = None) -> Optional[Dict[str, Any]]:
    """
    Main function to fetch physical premium data.
    Tries papervsphysical.com first, falls back to dealer scraping.
    """
    # Try primary source
    data = fetch_paper_vs_physical()
    
    if data:
        # Store in database
        try:
            insert_premium(
                source=data['source'],
                product_type=data['product_type'],
                spot_price=data['spot_price'],
                physical_price=data['physical_price'],
                premium_usd=data['premium_usd'],
                premium_pct=data['premium_pct']
            )
            logger.info(f"Stored premium data: {data['premium_pct']:.1f}% over spot")
        except Exception as e:
            logger.error(f"Error storing premium data: {e}")
        
        # Add status
        status = calculate_premium_status(data['premium_pct'])
        data.update(status)
        
        return data
    
    # Fallback to dealer prices if we have spot price
    if spot_price:
        dealer_data = fetch_dealer_prices(spot_price)
        if dealer_data:
            # Calculate average premium
            avg_premium = sum(d['premium_pct'] for d in dealer_data) / len(dealer_data)
            avg_physical = sum(d['physical_price'] for d in dealer_data) / len(dealer_data)
            
            result = {
                'source': 'dealers_avg',
                'product_type': 'mixed',
                'spot_price': spot_price,
                'physical_price': avg_physical,
                'premium_usd': avg_physical - spot_price,
                'premium_pct': avg_premium,
                'timestamp': datetime.now().isoformat(),
                'dealer_count': len(dealer_data)
            }
            
            # Store
            try:
                insert_premium(
                    source=result['source'],
                    product_type=result['product_type'],
                    spot_price=result['spot_price'],
                    physical_price=result['physical_price'],
                    premium_usd=result['premium_usd'],
                    premium_pct=result['premium_pct']
                )
            except Exception as e:
                logger.error(f"Error storing dealer premium data: {e}")
            
            status = calculate_premium_status(result['premium_pct'])
            result.update(status)
            
            return result
    
    # Final fallback: Use estimated premium based on typical market conditions
    # When papervsphysical.com is unavailable (JS-rendered), estimate from spot
    if spot_price:
        logger.warning("Using estimated premium (typical dealer markup 10-15%)")
        # Typical retail physical silver premium is 10-15% over spot
        estimated_premium_pct = 12.0  # Conservative middle estimate
        physical_price = spot_price * (1 + estimated_premium_pct / 100)
        
        result = {
            'source': 'estimated',
            'product_type': 'estimated',
            'spot_price': spot_price,
            'physical_price': physical_price,
            'premium_usd': physical_price - spot_price,
            'premium_pct': estimated_premium_pct,
            'timestamp': datetime.now().isoformat(),
            'note': 'Estimated from typical dealer premiums (10-15%)'
        }
        
        try:
            insert_premium(
                source=result['source'],
                product_type=result['product_type'],
                spot_price=result['spot_price'],
                physical_price=result['physical_price'],
                premium_usd=result['premium_usd'],
                premium_pct=result['premium_pct']
            )
            logger.info(f"Stored estimated premium: {result['premium_pct']:.1f}%")
        except Exception as e:
            logger.error(f"Error storing estimated premium: {e}")
        
        status = calculate_premium_status(result['premium_pct'])
        result.update(status)
        
        return result
    
    logger.error("Failed to fetch premium data from all sources")
    return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("Testing premium fetchers...")
    
    from scripts.db import init_database
    init_database()
    
    data = fetch_premiums()
    if data:
        print(f"\nPhysical Premium Data:")
        print(f"  Source: {data['source']}")
        print(f"  Spot: ${data['spot_price']:.2f}")
        print(f"  Physical: ${data['physical_price']:.2f}")
        print(f"  Premium: ${data['premium_usd']:.2f} ({data['premium_pct']:.1f}%)")
        print(f"  Status: {data['label']} ({data['status']})")
    else:
        print("Failed to fetch premium data")
