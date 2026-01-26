"""
Export data to JSON for the static frontend dashboard.
Generates latest.json and historical.json files for GitHub Pages.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List

from scripts.config import DOCS_DATA_DIR
from scripts.db import (
    get_historical_data,
    get_latest_snapshot,
    get_database_stats
)
from scripts.normalize import get_current_metrics, create_snapshot

logger = logging.getLogger(__name__)


def ensure_output_dir():
    """Create output directory if it doesn't exist."""
    DOCS_DATA_DIR.mkdir(parents=True, exist_ok=True)


def format_historical_for_charts(data: List[Dict], 
                                  value_key: str,
                                  label: str = None) -> Dict[str, Any]:
    """
    Format historical data for Chart.js consumption.
    Returns dict with labels (timestamps) and datasets.
    """
    if not data:
        return {'labels': [], 'datasets': []}
    
    labels = []
    values = []
    
    for record in data:
        # Parse timestamp
        ts = record.get('timestamp', '')
        if isinstance(ts, str):
            try:
                dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                labels.append(dt.strftime('%Y-%m-%d %H:%M'))
            except ValueError:
                labels.append(ts[:16])
        else:
            labels.append(str(ts))
        
        # Get value
        values.append(record.get(value_key))
    
    return {
        'labels': labels,
        'datasets': [{
            'label': label or value_key,
            'data': values
        }]
    }


def export_latest_json(metrics: Dict[str, Any] = None) -> Path:
    """
    Export current metrics to latest.json for dashboard display.
    """
    ensure_output_dir()
    
    if metrics is None:
        metrics = get_current_metrics()
    
    # Add metadata
    output = {
        'generated_at': datetime.now().isoformat(),
        'version': '1.0',
        'metrics': metrics
    }
    
    filepath = DOCS_DATA_DIR / 'latest.json'
    
    with open(filepath, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    
    logger.info(f"Exported latest metrics to {filepath}")
    return filepath


def export_historical_json(days: int = 90) -> Path:
    """
    Export historical data to historical.json for trend charts.
    """
    ensure_output_dir()
    
    # Get historical data from each table
    historical = {
        'generated_at': datetime.now().isoformat(),
        'days_included': days,
        'data': {}
    }
    
    # Snapshots (primary historical source)
    snapshots = get_historical_data('metrics_snapshot', days=days)
    if snapshots:
        historical['data']['snapshots'] = {
            'records': snapshots,
            'charts': {
                'spot_price': format_historical_for_charts(
                    snapshots, 'spot_price', 'Spot Price (USD)'
                ),
                'premium_pct': format_historical_for_charts(
                    snapshots, 'premium_pct', 'Premium (%)'
                ),
                'inventory_total': format_historical_for_charts(
                    snapshots, 'inventory_total_moz', 'Total Inventory (M oz)'
                ),
                'margin_initial': format_historical_for_charts(
                    snapshots, 'margin_initial', 'Initial Margin (USD)'
                ),
                'lease_rate': format_historical_for_charts(
                    snapshots, 'lease_rate_proxy', 'Lease Rate Proxy (%)'
                ),
                'composite_score': format_historical_for_charts(
                    snapshots, 'composite_score', 'Composite Score'
                )
            }
        }
    
    # Individual table history (for detailed views)
    for table in ['spot_prices', 'premiums', 'inventory', 'margins']:
        data = get_historical_data(table, days=days)
        if data:
            historical['data'][table] = {
                'count': len(data),
                'records': data[-100:]  # Limit to last 100 for file size
            }
    
    filepath = DOCS_DATA_DIR / 'historical.json'
    
    with open(filepath, 'w') as f:
        json.dump(historical, f, indent=2, default=str)
    
    logger.info(f"Exported historical data ({days} days) to {filepath}")
    return filepath


def export_status_badge_json(metrics: Dict[str, Any] = None) -> Path:
    """
    Export minimal status data for shields.io badge generation.
    """
    ensure_output_dir()
    
    if metrics is None:
        metrics = get_current_metrics()
    
    composite = metrics.get('composite', {})
    score = composite.get('score', 0)
    total = composite.get('total', 4)
    color = composite.get('status_color', 'gray')
    
    # Map colors to shields.io format
    color_map = {
        'green': 'brightgreen',
        'yellow': 'yellow',
        'orange': 'orange',
        'red': 'red',
        'gray': 'lightgrey'
    }
    
    badge = {
        'schemaVersion': 1,
        'label': 'Silver Market',
        'message': f'{score}/{total} normalizing',
        'color': color_map.get(color, 'lightgrey')
    }
    
    filepath = DOCS_DATA_DIR / 'badge.json'
    
    with open(filepath, 'w') as f:
        json.dump(badge, f)
    
    logger.info(f"Exported badge data to {filepath}")
    return filepath


def export_all(create_new_snapshot: bool = True) -> Dict[str, Path]:
    """
    Export all JSON files for the dashboard.
    """
    # Get current metrics
    metrics = get_current_metrics()
    
    # Create snapshot for historical tracking
    if create_new_snapshot:
        try:
            snapshot_id = create_snapshot(metrics)
            logger.info(f"Created snapshot #{snapshot_id}")
        except Exception as e:
            logger.error(f"Error creating snapshot: {e}")
    
    # Export all files
    files = {
        'latest': export_latest_json(metrics),
        'historical': export_historical_json(days=90),
        'badge': export_status_badge_json(metrics)
    }
    
    logger.info(f"Exported {len(files)} JSON files")
    return files


def get_export_summary() -> Dict[str, Any]:
    """
    Get summary of exported data for logging/debugging.
    """
    stats = get_database_stats()
    
    latest_file = DOCS_DATA_DIR / 'latest.json'
    historical_file = DOCS_DATA_DIR / 'historical.json'
    
    summary = {
        'database_stats': stats,
        'files': {}
    }
    
    if latest_file.exists():
        summary['files']['latest.json'] = {
            'exists': True,
            'size_bytes': latest_file.stat().st_size,
            'modified': datetime.fromtimestamp(
                latest_file.stat().st_mtime
            ).isoformat()
        }
    
    if historical_file.exists():
        summary['files']['historical.json'] = {
            'exists': True,
            'size_bytes': historical_file.stat().st_size,
            'modified': datetime.fromtimestamp(
                historical_file.stat().st_mtime
            ).isoformat()
        }
    
    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("Testing JSON export...")
    
    from scripts.db import init_database
    init_database()
    
    # Export all
    files = export_all(create_new_snapshot=False)
    
    print(f"\nExported files:")
    for name, path in files.items():
        print(f"  {name}: {path}")
    
    # Show summary
    summary = get_export_summary()
    print(f"\nDatabase stats: {summary['database_stats']}")
    print(f"File info: {summary['files']}")
