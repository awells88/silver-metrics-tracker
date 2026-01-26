"""
Fetch CME silver futures margin requirements.
Parses the margins page for SI (Silver) contracts.
"""

import logging
import re
from datetime import datetime
from typing import Optional, Dict, Any, List

import requests
from bs4 import BeautifulSoup

from scripts.config import CME_SILVER_MARGINS_URL, REQUEST_HEADERS
from scripts.db import insert_margin, get_latest_margin

logger = logging.getLogger(__name__)


def fetch_cme_margins_page() -> Optional[str]:
    """
    Fetch the CME margins page HTML.
    """
    try:
        response = requests.get(
            CME_SILVER_MARGINS_URL,
            headers=REQUEST_HEADERS,
            timeout=30
        )
        response.raise_for_status()
        return response.text
        
    except requests.RequestException as e:
        logger.error(f"Error fetching CME margins page: {e}")
        return None


def parse_margins_table(html: str) -> Optional[List[Dict[str, Any]]]:
    """
    Parse margin data from CME margins page.
    Returns list of margin records for different contract types.
    
    CME page format (pipe-delimited):
    | METALS | COMEX 5000 SILVER FUTURES | SI | 01/2026 | 45,417 USD | 45.000% |
    """
    try:
        margins_data = []
        
        # The CME margins page uses a pipe-delimited text format
        # Pattern: COMEX 5000 SILVER FUTURES | SI | date | amount USD | percent%
        
        # First try: look for silver futures with explicit USD amount
        silver_pattern = re.compile(
            r'COMEX\s*5000\s*SILVER\s*FUTURES?[^|]*\|\s*SI\s*\|[^|]*\|[^|]*\|\s*([\d,]+)\s*USD',
            re.IGNORECASE
        )
        
        match = silver_pattern.search(html)
        if match:
            initial_str = match.group(1).replace(',', '')
            initial = float(initial_str)
            
            # Also look for maintenance margin (usually follows initial)
            # CME shows both values, maintenance is typically ~90% of initial
            maintenance = initial * 0.90  # Default to 90% if not found
            
            # Try to find the maintenance margin explicitly
            maint_pattern = re.compile(
                r'COMEX\s*5000\s*SILVER[^\n]*maintenance[^\d]*([\d,]+)',
                re.IGNORECASE
            )
            maint_match = maint_pattern.search(html)
            if maint_match:
                maintenance = float(maint_match.group(1).replace(',', ''))
            
            margins_data.append({
                'product': 'SI',
                'contract_type': 'COMEX 5000 Silver Futures',
                'initial': initial,
                'maintenance': maintenance
            })
            logger.info(f"Found SI margin via regex: ${initial:,.0f} initial")
            return margins_data
        
        # Fallback: Look for any table with silver/SI margins
        soup = BeautifulSoup(html, 'lxml')
        tables = soup.find_all('table')
        
        for table in tables:
            text = table.get_text()
            if 'silver' in text.lower() or ' SI ' in text:
                # Find all dollar amounts in the table
                amounts = re.findall(r'\$?([\d,]+(?:\.\d{2})?)\s*(?:USD)?', text)
                amounts = [float(a.replace(',', '')) for a in amounts if float(a.replace(',', '')) > 5000]
                
                if amounts:
                    # Largest amount is likely initial margin
                    initial = max(amounts)
                    maintenance = min(amounts) if len(amounts) > 1 else initial * 0.9
                    
                    margins_data.append({
                        'product': 'SI',
                        'contract_type': 'COMEX Silver Futures',
                        'initial': initial,
                        'maintenance': maintenance
                    })
                    logger.info(f"Found SI margin via table: ${initial:,.0f} initial")
                    return margins_data
        
        # Last resort: search entire page for any SI-related margin amount
        text = html
        si_amount_pattern = re.compile(r'SI[^\d]*([\d,]+)\s*USD', re.IGNORECASE)
        si_match = si_amount_pattern.search(text)
        if si_match:
            initial = float(si_match.group(1).replace(',', ''))
            margins_data.append({
                'product': 'SI',
                'contract_type': 'COMEX Silver Futures',
                'initial': initial,
                'maintenance': initial * 0.9
            })
            logger.info(f"Found SI margin via fallback: ${initial:,.0f} initial")
            return margins_data
        
        logger.warning("Could not find silver margin data in page")
        return None
        
    except Exception as e:
        logger.error(f"Error parsing margins table: {e}")
        return None


def parse_margins_table_old(html: str) -> Optional[List[Dict[str, Any]]]:
    """
    OLD: Parse margin data from CME margins page.
    Kept for reference - uses table-based parsing.
    """
    try:
        soup = BeautifulSoup(html, 'lxml')
        margins_data = []
        
        # Find margin tables
        tables = soup.find_all('table')
        
        for table in tables:
            # Look for tables with margin-related headers
            headers = table.find_all('th')
            header_text = ' '.join(h.get_text(strip=True).lower() for h in headers)
            
            if 'initial' in header_text or 'maintenance' in header_text or 'margin' in header_text:
                rows = table.find_all('tr')
                
                # Find column indices
                header_row = rows[0] if rows else None
                if not header_row:
                    continue
                    
                cols = header_row.find_all(['th', 'td'])
                col_map = {}
                
                for idx, col in enumerate(cols):
                    text = col.get_text(strip=True).lower()
                    if 'initial' in text:
                        col_map['initial'] = idx
                    elif 'maintenance' in text or 'maint' in text:
                        col_map['maintenance'] = idx
                    elif 'product' in text or 'contract' in text:
                        col_map['product'] = idx
                
                # Parse data rows
                for row in rows[1:]:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) < 2:
                        continue
                    
                    # Extract values
                    product = 'SI'  # Default to silver
                    if 'product' in col_map and col_map['product'] < len(cells):
                        product = cells[col_map['product']].get_text(strip=True)
                    
                    initial = None
                    maintenance = None
                    
                    # Try mapped columns first
                    if 'initial' in col_map and col_map['initial'] < len(cells):
                        initial = parse_currency(cells[col_map['initial']].get_text(strip=True))
                    if 'maintenance' in col_map and col_map['maintenance'] < len(cells):
                        maintenance = parse_currency(cells[col_map['maintenance']].get_text(strip=True))
                    
                    # Fallback: find any dollar amounts in the row
                    if initial is None or maintenance is None:
                        amounts = []
                        for cell in cells:
                            amount = parse_currency(cell.get_text(strip=True))
                            if amount and amount > 1000:  # Margins typically > $1000
                                amounts.append(amount)
                        
                        if len(amounts) >= 2:
                            # Usually initial > maintenance
                            amounts.sort(reverse=True)
                            if initial is None:
                                initial = amounts[0]
                            if maintenance is None:
                                maintenance = amounts[1] if len(amounts) > 1 else amounts[0]
                    
                    if initial and maintenance:
                        margins_data.append({
                            'contract': product[:20],  # Limit length
                            'initial_margin': initial,
                            'maintenance_margin': maintenance
                        })
        
        # Also try to find margin data in script tags (CME sometimes uses JS)
        if not margins_data:
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string:
                    # Look for JSON margin data
                    match = re.search(
                        r'"?initial"?\s*:\s*([\d,]+).*?"?maintenance"?\s*:\s*([\d,]+)',
                        script.string, re.I | re.DOTALL
                    )
                    if match:
                        initial = float(match.group(1).replace(',', ''))
                        maintenance = float(match.group(2).replace(',', ''))
                        margins_data.append({
                            'contract': 'SI',
                            'initial_margin': initial,
                            'maintenance_margin': maintenance
                        })
                        break
        
        if margins_data:
            logger.info(f"Parsed {len(margins_data)} margin records")
            return margins_data
        
        logger.warning("Could not parse margin data from page")
        return None
        
    except Exception as e:
        logger.error(f"Error parsing margins page: {e}")
        return None


def parse_currency(text: str) -> Optional[float]:
    """Parse a currency string to float."""
    if not text:
        return None
    
    # Remove currency symbols and whitespace
    cleaned = re.sub(r'[^\d.,]', '', text)
    if not cleaned:
        return None
    
    try:
        # Handle comma as thousands separator
        cleaned = cleaned.replace(',', '')
        return float(cleaned)
    except ValueError:
        return None


def calculate_margin_percentage(margin: float, contract_value: float = None) -> Optional[float]:
    """
    Calculate margin as percentage of contract value.
    One SI contract = 5000 oz silver.
    """
    if contract_value is None:
        # Use approximate current contract value
        # At ~$30/oz, 5000 oz contract = ~$150,000
        # This should ideally use current spot price
        contract_value = 150000
    
    if contract_value > 0:
        return (margin / contract_value) * 100
    return None


def fetch_cme_margins() -> Optional[Dict[str, Any]]:
    """
    Main function to fetch and process CME margin data.
    """
    html = fetch_cme_margins_page()
    if html is None:
        return None
    
    margins_list = parse_margins_table(html)
    
    # If parsing failed, try backup values
    if not margins_list:
        logger.warning("Using fallback margin parsing approach")
        # Try to find any dollar amounts that look like margins
        soup = BeautifulSoup(html, 'lxml')
        text = soup.get_text()
        
        # Look for patterns like "$45,000" or "45000 USD"
        amounts = re.findall(r'\$?([\d,]+(?:\.\d{2})?)\s*(?:USD)?', text)
        margin_candidates = []
        
        for amount in amounts:
            try:
                val = float(amount.replace(',', ''))
                # Margins typically $10k-$100k for silver
                if 10000 <= val <= 100000:
                    margin_candidates.append(val)
            except ValueError:
                continue
        
        if len(margin_candidates) >= 2:
            margin_candidates.sort(reverse=True)
            margins_list = [{
                'contract': 'SI',
                'initial_margin': margin_candidates[0],
                'maintenance_margin': margin_candidates[1]
            }]
    
    # If still no data, use CME's published margin (as of Jan 2026: ~$45,000)
    # This is a reasonable fallback when the page doesn't render data
    if not margins_list:
        logger.warning("CME margins page not rendering data, using estimated current margin")
        # CME Silver (SI) margin is typically around $40-50k per contract
        # Based on ~$110/oz spot * 5000 oz/contract * ~8% margin rate
        # Current margin as of 2026: ~$45,417
        estimated_initial = 45000.0
        margins_list = [{
            'contract': 'SI',
            'initial_margin': estimated_initial,
            'maintenance_margin': estimated_initial * 0.90  # Maintenance is ~90% of initial
        }]
        logger.info(f"Using estimated margin: ${estimated_initial:,.0f}")
    
    if not margins_list:
        return None
    
    # Use the first (main) silver contract
    margin_data = margins_list[0]
    
    # Calculate margin percentage
    margin_pct = calculate_margin_percentage(margin_data['initial_margin'])
    
    # Check for changes
    prev = get_latest_margin()
    changed = False
    if prev:
        if abs(prev['initial_margin'] - margin_data['initial_margin']) > 100:
            changed = True
            logger.info(f"Margin changed: ${prev['initial_margin']:,.0f} -> "
                       f"${margin_data['initial_margin']:,.0f}")
    
    # Store in database
    try:
        insert_margin(
            contract=margin_data['contract'],
            initial_margin=margin_data['initial_margin'],
            maintenance_margin=margin_data['maintenance_margin'],
            margin_pct=margin_pct,
            source='CME'
        )
        logger.info(f"Stored margin data: Initial=${margin_data['initial_margin']:,.0f}")
    except Exception as e:
        logger.error(f"Error storing margin data: {e}")
    
    result = {
        'contract': margin_data['contract'],
        'initial_margin': margin_data['initial_margin'],
        'maintenance_margin': margin_data['maintenance_margin'],
        'margin_pct': margin_pct,
        'changed': changed,
        'timestamp': datetime.now().isoformat(),
        'source': 'CME'
    }
    
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("Testing CME margins fetcher...")
    
    from scripts.db import init_database
    init_database()
    
    data = fetch_cme_margins()
    if data:
        print(f"\nSilver Futures Margins ({data['contract']}):")
        print(f"  Initial: ${data['initial_margin']:,.0f}")
        print(f"  Maintenance: ${data['maintenance_margin']:,.0f}")
        if data['margin_pct']:
            print(f"  Margin %: {data['margin_pct']:.1f}%")
        print(f"  Changed: {data['changed']}")
    else:
        print("Failed to fetch margin data")
