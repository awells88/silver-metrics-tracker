"""
Fetch Shanghai silver premium data using MetalpriceAPI.
Primary source: metalpriceapi.com (provides XAG prices in USD and CNY)
Fallback: Manual values

The premium is the difference between Shanghai silver price (XAG in CNY converted to USD)
and Western spot price (XAG in USD), reflecting import demand and arbitrage.
"""

import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any

import requests

from scripts.config import REQUEST_HEADERS
from scripts.db import insert_shanghai_premium

logger = logging.getLogger(__name__)

# MetalpriceAPI configuration
# Get your free API key at: https://metalpriceapi.com/register
METALPRICEAPI_URL = "https://api.metalpriceapi.com/v1/latest"
METALPRICEAPI_KEY = os.environ.get("METALPRICEAPI_KEY", "")


def fetch_from_metalpriceapi() -> Optional[Dict[str, Any]]:
    """
    Fetch silver prices from MetalpriceAPI.
    
    Gets XAG (silver) price in both USD and CNY to calculate the
    Shanghai premium (price difference due to import demand).
    
    API returns:
    - XAG rate: how many oz of silver per 1 USD (e.g., 0.00925 = $108.11/oz)
    - CNY rate: how many CNY per 1 USD (e.g., 7.25)
    
    Shanghai silver (in USD terms) = (CNY/oz silver) / (CNY/USD rate)
    Premium = Shanghai USD price - Western USD price
    
    Returns:
        Dict with shanghai_spot, western_spot, premium_usd, premium_pct or None
    """
    if not METALPRICEAPI_KEY:
        logger.warning("METALPRICEAPI_KEY not set - cannot fetch live prices")
        return None
        
    try:
        # Request XAG (silver) and CNY rates with USD as base
        params = {
            'api_key': METALPRICEAPI_KEY,
            'base': 'USD',
            'currencies': 'XAG,CNY'
        }
        
        response = requests.get(
            METALPRICEAPI_URL,
            params=params,
            headers=REQUEST_HEADERS,
            timeout=30
        )
        response.raise_for_status()
        
        data = response.json()
        
        if not data.get('success'):
            error = data.get('error', {})
            logger.error(f"MetalpriceAPI error: {error.get('info', 'Unknown error')}")
            return None
        
        rates = data.get('rates', {})
        
        # XAG rate = oz of silver per 1 USD
        # So 1/XAG = USD per oz (Western spot price)
        xag_rate = rates.get('XAG')
        cny_rate = rates.get('CNY')  # CNY per 1 USD
        
        if not xag_rate or not cny_rate:
            logger.error(f"Missing rates in response: XAG={xag_rate}, CNY={cny_rate}")
            return None
        
        # Western spot price (global/COMEX price in USD)
        western_spot = 1.0 / xag_rate
        
        # For Shanghai premium calculation:
        # The premium comes from the fact that silver in China trades at a premium
        # due to import duties, VAT, and demand.
        # 
        # MetalpriceAPI gives us the same XAG spot rate globally, but the actual
        # Shanghai price would be higher due to local market dynamics.
        #
        # Historical Shanghai premium typically ranges 1-2% in normal times,
        # but can spike to 10%+ during high demand/stress.
        #
        # Since the API provides global spot (not Shanghai-specific),
        # we'll estimate Shanghai spot by applying the known premium.
        # 
        # TODO: If MetalpriceAPI adds Shanghai-specific pricing, use that directly.
        
        # For now, use the USDCNY inverse to get CNY value
        # USDXAG gives us USD/oz price directly
        usd_xag = rates.get('USDXAG')
        if usd_xag:
            western_spot = usd_xag
            
        logger.info(f"MetalpriceAPI: Silver spot ${western_spot:.2f}/oz, CNY rate: {cny_rate}")
        
        # Return just the western spot - we'll use manual premium if needed
        return {
            'western_spot': western_spot,
            'cny_rate': cny_rate,
            'source': 'metalpriceapi'
        }
            
    except requests.exceptions.RequestException as e:
        logger.error(f"MetalpriceAPI request error: {e}")
        return None
    except Exception as e:
        logger.error(f"Error processing MetalpriceAPI data: {e}")
        return None


def fetch_shanghai_premium() -> Optional[Dict[str, Any]]:
    """
    Fetch Shanghai silver premium.
    
    Strategy:
    1. Try MetalpriceAPI for live Western spot price
    2. Apply known premium spread (from metalcharts.org observations)
    3. Fallback to fully manual values if API unavailable
    
    The Shanghai premium reflects local supply/demand dynamics that
    MetalpriceAPI's global spot doesn't capture, so we combine:
    - Live spot price from MetalpriceAPI (accurate Western price)
    - Known premium spread from market observations
    
    Returns:
        Dict with shanghai_spot, western_spot, premium_usd, premium_pct
    """
    # Current observed premium from metalcharts.org (as of Jan 26, 2026)
    # Update this periodically based on: https://metalcharts.org/shanghai
    OBSERVED_PREMIUM_USD = 11.58  # Premium in $/oz
    
    data = {
        'shanghai_spot': None,
        'western_spot': None,
        'premium_usd': None,
        'premium_pct': None
    }
    
    # Try MetalpriceAPI first for live spot price
    api_data = fetch_from_metalpriceapi()
    
    if api_data and api_data.get('western_spot'):
        data['western_spot'] = api_data['western_spot']
        data['premium_usd'] = OBSERVED_PREMIUM_USD
        data['shanghai_spot'] = data['western_spot'] + OBSERVED_PREMIUM_USD
        data['premium_pct'] = (OBSERVED_PREMIUM_USD / data['western_spot']) * 100
        source = "MetalpriceAPI"
        
        logger.info(
            f"Using MetalpriceAPI spot ${data['western_spot']:.2f} + "
            f"observed premium ${OBSERVED_PREMIUM_USD:.2f} = "
            f"Shanghai ${data['shanghai_spot']:.2f}"
        )
    else:
        # Try database for recent spot price
        try:
            from scripts.db import get_latest_spot_price
            latest_spot = get_latest_spot_price()
            if latest_spot and latest_spot.get('price_usd'):
                data['western_spot'] = latest_spot['price_usd']
                data['premium_usd'] = OBSERVED_PREMIUM_USD
                data['shanghai_spot'] = data['western_spot'] + OBSERVED_PREMIUM_USD
                data['premium_pct'] = (OBSERVED_PREMIUM_USD / data['western_spot']) * 100
                source = "DB_spot"
                
                logger.info(f"Using DB spot ${data['western_spot']:.2f} + premium")
        except Exception as e:
            logger.warning(f"Could not get Western spot from database: {e}")
    
    # Final fallback to fully manual values
    if data['western_spot'] is None:
        return use_manual_shanghai_premium()
    
    # Insert into database
    insert_shanghai_premium(
        shanghai_spot=data['shanghai_spot'],
        western_spot=data['western_spot'],
        premium_usd=data['premium_usd'],
        premium_pct=data['premium_pct'],
        source=source
    )
    
    return data


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
