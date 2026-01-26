#!/usr/bin/env python3
"""
Silver Metrics Tracker - Main Runner

This script orchestrates all data fetching, processing, and export operations.
Run this manually or via GitHub Actions to update the dashboard.
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

# Ensure scripts module is importable
sys.path.insert(0, str(Path(__file__).parent))

from scripts.config import LOG_FORMAT, LOG_LEVEL, DATA_DIR
from scripts.db import init_database, get_database_stats
from scripts.fetch_spot_prices import fetch_spot_price
from scripts.fetch_cme_stocks import fetch_cme_stocks
from scripts.fetch_cme_margins import fetch_cme_margins
from scripts.fetch_premiums import fetch_premiums
from scripts.fetch_lease_rates import fetch_lease_rate_proxy
from scripts.fetch_shanghai_premium import fetch_shanghai_premium
from scripts.normalize import get_current_metrics, create_snapshot
from scripts.export_json import export_all, get_export_summary


def setup_logging(verbose: bool = False):
    """Configure logging for the application."""
    level = logging.DEBUG if verbose else getattr(logging, LOG_LEVEL, logging.INFO)
    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)


def fetch_all_data(logger) -> dict:
    """
    Fetch data from all sources.
    Returns dict with results from each fetcher.
    """
    results = {
        'spot_price': None,
        'inventory': None,
        'margins': None,
        'premiums': None,
        'lease_rates': None,
        'shanghai_premium': None,
        'errors': []
    }
    
    # 1. Spot Price
    logger.info("Fetching spot price...")
    try:
        results['spot_price'] = fetch_spot_price()
        if results['spot_price']:
            logger.info(f"✓ Spot price: ${results['spot_price']['price_usd']:.2f}")
        else:
            results['errors'].append("Failed to fetch spot price")
    except Exception as e:
        logger.error(f"✗ Spot price error: {e}")
        results['errors'].append(f"Spot price: {e}")
    
    # 2. CME Inventory
    logger.info("Fetching COMEX inventory...")
    try:
        results['inventory'] = fetch_cme_stocks()
        if results['inventory']:
            total_moz = results['inventory']['total_oz'] / 1_000_000
            logger.info(f"✓ Inventory: {total_moz:.2f}M oz")
        else:
            results['errors'].append("Failed to fetch CME inventory")
    except Exception as e:
        logger.error(f"✗ Inventory error: {e}")
        results['errors'].append(f"Inventory: {e}")
    
    # 3. CME Margins
    logger.info("Fetching CME margins...")
    try:
        results['margins'] = fetch_cme_margins()
        if results['margins']:
            logger.info(f"✓ Margin: ${results['margins']['initial_margin']:,.0f}")
        else:
            results['errors'].append("Failed to fetch CME margins")
    except Exception as e:
        logger.error(f"✗ Margins error: {e}")
        results['errors'].append(f"Margins: {e}")
    
    # 4. Physical Premiums
    logger.info("Fetching physical premiums...")
    try:
        spot = results['spot_price']['price_usd'] if results['spot_price'] else None
        results['premiums'] = fetch_premiums(spot_price=spot)
        if results['premiums']:
            logger.info(f"✓ Premium: {results['premiums']['premium_pct']:.1f}%")
        else:
            results['errors'].append("Failed to fetch premiums")
    except Exception as e:
        logger.error(f"✗ Premiums error: {e}")
        results['errors'].append(f"Premiums: {e}")
    
    # 5. Lease Rate Proxy
    logger.info("Calculating lease rate proxy...")
    try:
        results['lease_rates'] = fetch_lease_rate_proxy()
        if results['lease_rates']:
            logger.info(f"✓ Lease rate proxy: {results['lease_rates']['rate_pct']:.2f}%")
        else:
            results['errors'].append("Failed to calculate lease rate proxy")
    except Exception as e:
        logger.error(f"✗ Lease rate error: {e}")
        results['errors'].append(f"Lease rates: {e}")
    
    # 6. Shanghai Premium
    logger.info("Fetching Shanghai premium...")
    try:
        results['shanghai_premium'] = fetch_shanghai_premium()
        if results['shanghai_premium']:
            logger.info(f"✓ Shanghai premium: +${results['shanghai_premium']['premium_usd']:.2f}/oz "
                       f"({results['shanghai_premium']['premium_pct']:.1f}%)")
        else:
            results['errors'].append("Failed to fetch Shanghai premium")
    except Exception as e:
        logger.error(f"✗ Shanghai premium error: {e}")
        results['errors'].append(f"Shanghai premium: {e}")
    
    return results


def process_and_export(logger) -> bool:
    """
    Process current data and export JSON for dashboard.
    Returns True if successful.
    """
    logger.info("Processing metrics and creating snapshot...")
    
    try:
        # Get normalized metrics
        metrics = get_current_metrics()
        
        # Log composite score
        composite = metrics.get('composite', {})
        logger.info(f"Composite score: {composite.get('score', 0)}/{composite.get('total', 5)} "
                   f"- {composite.get('status_label', 'Unknown')}")
        
        # Create snapshot for historical tracking
        snapshot_id = create_snapshot(metrics)
        logger.info(f"Created snapshot #{snapshot_id}")
        
        # Export all JSON files
        logger.info("Exporting JSON files...")
        files = export_all(create_new_snapshot=False)  # Already created above
        
        for name, path in files.items():
            logger.info(f"  ✓ {name}: {path}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error processing/exporting: {e}")
        return False


def print_summary(logger, fetch_results: dict):
    """Print a summary of the update run."""
    logger.info("\n" + "="*50)
    logger.info("UPDATE SUMMARY")
    logger.info("="*50)
    
    # Count successes
    success_count = sum(1 for k, v in fetch_results.items() 
                       if k not in ['errors'] and v is not None)
    total_count = 5  # Total number of data sources
    
    logger.info(f"Data sources fetched: {success_count}/{total_count}")
    
    if fetch_results['errors']:
        logger.info(f"Errors encountered: {len(fetch_results['errors'])}")
        for error in fetch_results['errors']:
            logger.warning(f"  - {error}")
    
    # Database stats
    try:
        stats = get_database_stats()
        logger.info(f"Database records: {sum(stats.values())} total")
    except Exception:
        pass
    
    # Export summary
    try:
        summary = get_export_summary()
        for filename, info in summary.get('files', {}).items():
            if info.get('exists'):
                logger.info(f"  {filename}: {info['size_bytes']} bytes")
    except Exception:
        pass
    
    logger.info("="*50)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Silver Metrics Tracker - Data Update Script'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose/debug logging'
    )
    parser.add_argument(
        '--fetch-only',
        action='store_true',
        help='Only fetch data, skip export'
    )
    parser.add_argument(
        '--export-only',
        action='store_true',
        help='Only export existing data, skip fetch'
    )
    parser.add_argument(
        '--init-db',
        action='store_true',
        help='Initialize database and exit'
    )
    
    args = parser.parse_args()
    
    # Setup
    logger = setup_logging(args.verbose)
    logger.info(f"Silver Metrics Tracker - Starting update at {datetime.now().isoformat()}")
    
    # Ensure data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Initialize database
    logger.info("Initializing database...")
    init_database()
    
    if args.init_db:
        logger.info("Database initialized. Exiting.")
        return 0
    
    fetch_results = {'errors': []}
    
    # Fetch data
    if not args.export_only:
        fetch_results = fetch_all_data(logger)
    
    # Process and export
    if not args.fetch_only:
        success = process_and_export(logger)
        if not success:
            fetch_results['errors'].append("Export failed")
    
    # Summary
    print_summary(logger, fetch_results)
    
    # Exit code based on errors
    if fetch_results['errors']:
        logger.warning("Completed with errors")
        return 1
    
    logger.info("Update completed successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
