"""
Normalization logic for Silver Metrics Tracker.
Compares current values to historical thresholds and determines status.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple

from scripts.config import THRESHOLDS
from scripts.db import (
    get_latest_spot_price,
    get_latest_premium,
    get_latest_inventory,
    get_latest_margin,
    get_margin_last_change_date,
    get_inventory_trend,
    get_historical_data,
    insert_metrics_snapshot
)

logger = logging.getLogger(__name__)


def determine_status(value: float, thresholds: Dict[str, float], 
                     higher_is_worse: bool = True) -> Tuple[str, str]:
    """
    Determine status color based on value and thresholds.
    
    Args:
        value: Current metric value
        thresholds: Dict with threshold levels
        higher_is_worse: If True, higher values = more stress
        
    Returns:
        Tuple of (status_color, status_label)
    """
    if higher_is_worse:
        if 'extreme' in thresholds and value >= thresholds['extreme']:
            return ('red', 'Extreme')
        elif 'stressed' in thresholds and value >= thresholds['stressed']:
            return ('red', 'Stressed')
        elif 'normal_high' in thresholds and value > thresholds['normal_high']:
            return ('yellow', 'Elevated')
        else:
            return ('green', 'Normal')
    else:
        # Lower is worse (e.g., inventory)
        if 'critical' in thresholds and value <= thresholds['critical']:
            return ('red', 'Critical')
        elif 'stressed' in thresholds and value <= thresholds['stressed']:
            return ('red', 'Stressed')
        elif 'normal_low' in thresholds and value < thresholds['normal_low']:
            return ('yellow', 'Low')
        else:
            return ('green', 'Healthy')


def normalize_lease_rate(rate_pct: float) -> Dict[str, Any]:
    """
    Normalize lease rate data.
    Lower rates = normalizing market (green)
    Higher rates = tighter market (red)
    """
    thresholds = THRESHOLDS['lease_rate']
    color, label = determine_status(rate_pct, thresholds, higher_is_worse=True)
    
    # Determine if normalizing (trending toward normal)
    is_normalizing = rate_pct <= thresholds['normal_high']
    
    return {
        'metric': 'lease_rate',
        'value': rate_pct,
        'unit': '%',
        'status_color': color,
        'status_label': label,
        'is_normalizing': is_normalizing,
        'threshold_normal': f"{thresholds['normal_low']}-{thresholds['normal_high']}%",
        'description': 'Cost to borrow physical silver'
    }


def normalize_premium(premium_pct: float) -> Dict[str, Any]:
    """
    Normalize physical premium data.
    Lower premiums = closing gap (green)
    Higher premiums = supply tightness (red)
    """
    thresholds = THRESHOLDS['premium_pct']
    color, label = determine_status(premium_pct, thresholds, higher_is_worse=True)
    
    is_normalizing = premium_pct <= thresholds['normal_high']
    
    return {
        'metric': 'premium',
        'value': premium_pct,
        'unit': '% over spot',
        'status_color': color,
        'status_label': label,
        'is_normalizing': is_normalizing,
        'threshold_normal': f"{thresholds['normal_low']}-{thresholds['normal_high']}%",
        'description': 'Physical silver price vs paper/spot'
    }


def normalize_inventory(total_moz: float, registered_moz: float = None) -> Dict[str, Any]:
    """
    Normalize COMEX inventory data.
    Higher inventory = recovering (green)
    Lower inventory = depleting (red)
    """
    thresholds = THRESHOLDS['inventory_total']
    color, label = determine_status(total_moz, thresholds, higher_is_worse=False)
    
    is_recovering = total_moz >= thresholds['healthy']
    
    # Check trend
    trend = get_inventory_trend(days=14)
    trend_label = trend.get('trend', 'unknown')
    
    # Adjust status based on trend
    if trend_label == 'recovering' and color != 'green':
        label = f"{label} (Recovering)"
    elif trend_label == 'declining' and color == 'green':
        color = 'yellow'
        label = 'Declining'
    
    result = {
        'metric': 'inventory',
        'value': total_moz,
        'unit': 'M oz',
        'status_color': color,
        'status_label': label,
        'is_normalizing': is_recovering or trend_label == 'recovering',
        'threshold_normal': f">{thresholds['healthy']}M oz",
        'trend': trend_label,
        'trend_change_moz': trend.get('change_moz', 0),
        'description': 'COMEX warehouse silver stocks'
    }
    
    # Add registered breakdown if available
    if registered_moz is not None:
        reg_thresholds = THRESHOLDS['inventory_registered']
        reg_color, reg_label = determine_status(
            registered_moz, reg_thresholds, higher_is_worse=False
        )
        result['registered_moz'] = registered_moz
        result['registered_status'] = reg_label
    
    return result


def normalize_margin(initial_margin: float, last_change_date: datetime = None) -> Dict[str, Any]:
    """
    Normalize margin data.
    Stability (no changes) = normalizing (green)
    Recent hikes = volatile market (red)
    """
    thresholds = THRESHOLDS['margin_stability_days']
    
    # Calculate days since last change
    if last_change_date is None:
        last_change_date = get_margin_last_change_date()
    
    if last_change_date:
        days_stable = (datetime.now() - last_change_date).days
    else:
        # No change history = assume stable
        days_stable = 30
    
    # Determine status based on stability
    if days_stable >= thresholds['stable']:
        color = 'green'
        label = 'Stable'
        is_normalizing = True
    elif days_stable >= thresholds['normalizing']:
        color = 'yellow'
        label = 'Stabilizing'
        is_normalizing = True
    else:
        color = 'red'
        label = 'Volatile'
        is_normalizing = False
    
    return {
        'metric': 'margin',
        'value': initial_margin,
        'unit': 'USD',
        'days_since_change': days_stable,
        'status_color': color,
        'status_label': label,
        'is_normalizing': is_normalizing,
        'threshold_stable': f"{thresholds['stable']}+ days unchanged",
        'description': 'CME initial margin for silver futures'
    }


def calculate_composite_score(metrics: Dict[str, Dict]) -> Dict[str, Any]:
    """
    Calculate overall market stress composite score.
    Score = number of metrics that are normalizing (green).
    """
    normalizing_count = 0
    total_metrics = 0
    
    for name, data in metrics.items():
        if data and 'is_normalizing' in data:
            total_metrics += 1
            if data['is_normalizing']:
                normalizing_count += 1
    
    # Overall status
    if total_metrics == 0:
        return {
            'score': 0,
            'total': 0,
            'status_color': 'gray',
            'status_label': 'No Data',
            'description': 'Insufficient data'
        }
    
    ratio = normalizing_count / total_metrics
    
    if ratio >= 0.75:
        color = 'green'
        label = 'Market Normalizing'
    elif ratio >= 0.5:
        color = 'yellow'
        label = 'Mixed Signals'
    elif ratio >= 0.25:
        color = 'orange'
        label = 'Elevated Stress'
    else:
        color = 'red'
        label = 'High Stress'
    
    return {
        'score': normalizing_count,
        'total': total_metrics,
        'percentage': round(ratio * 100, 1),
        'status_color': color,
        'status_label': label,
        'description': f'{normalizing_count}/{total_metrics} indicators normalizing'
    }


def get_current_metrics() -> Dict[str, Any]:
    """
    Get all current metrics from database and normalize them.
    Returns complete dashboard data structure.
    """
    metrics = {}
    
    # Spot price (baseline, not a stress indicator itself)
    spot = get_latest_spot_price()
    if spot:
        metrics['spot_price'] = {
            'value': spot['price_usd'],
            'change_24h': spot.get('change_pct_24h'),
            'source': spot['source'],
            'timestamp': spot['timestamp']
        }
    
    # Premiums
    premium = get_latest_premium()
    if premium:
        metrics['premium'] = normalize_premium(premium['premium_pct'])
        metrics['premium']['raw'] = {
            'spot': premium['spot_price'],
            'physical': premium['physical_price'],
            'usd': premium['premium_usd']
        }
    
    # Inventory
    inventory = get_latest_inventory()
    if inventory:
        total_moz = inventory['total_oz'] / 1_000_000
        registered_moz = inventory['registered_oz'] / 1_000_000
        metrics['inventory'] = normalize_inventory(total_moz, registered_moz)
        metrics['inventory']['raw'] = {
            'total_oz': inventory['total_oz'],
            'registered_oz': inventory['registered_oz'],
            'eligible_oz': inventory['eligible_oz']
        }
    
    # Margins
    margin = get_latest_margin()
    if margin:
        metrics['margin'] = normalize_margin(margin['initial_margin'])
        metrics['margin']['raw'] = {
            'initial': margin['initial_margin'],
            'maintenance': margin['maintenance_margin']
        }
    
    # Lease rates (using proxy for now)
    # In real implementation, would fetch from lease_rates table
    # Using a placeholder/proxy value
    lease_data = get_historical_data('lease_rates', days=1)
    if lease_data:
        latest_lease = lease_data[-1]
        metrics['lease_rate'] = normalize_lease_rate(latest_lease['rate_pct'])
        metrics['lease_rate']['raw'] = {
            'rate': latest_lease['rate_pct'],
            'source': latest_lease['source']
        }
    else:
        # Placeholder if no lease data
        metrics['lease_rate'] = normalize_lease_rate(2.5)
        metrics['lease_rate']['raw'] = {'rate': 2.5, 'source': 'placeholder'}
    
    # Composite score
    stress_metrics = {
        k: v for k, v in metrics.items() 
        if k in ['premium', 'inventory', 'margin', 'lease_rate']
    }
    metrics['composite'] = calculate_composite_score(stress_metrics)
    
    # Add timestamp
    metrics['last_updated'] = datetime.now().isoformat()
    
    return metrics


def create_snapshot(metrics: Dict[str, Any]) -> int:
    """
    Create a metrics snapshot for historical tracking.
    """
    snapshot_data = {
        'spot_price': metrics.get('spot_price', {}).get('value'),
        'premium_pct': metrics.get('premium', {}).get('value'),
        'inventory_total_moz': metrics.get('inventory', {}).get('value'),
        'inventory_registered_moz': metrics.get('inventory', {}).get('registered_moz'),
        'margin_initial': metrics.get('margin', {}).get('value'),
        'margin_days_stable': metrics.get('margin', {}).get('days_since_change'),
        'lease_rate_proxy': metrics.get('lease_rate', {}).get('value'),
        'status_premiums': metrics.get('premium', {}).get('status_color'),
        'status_inventory': metrics.get('inventory', {}).get('status_color'),
        'status_margins': metrics.get('margin', {}).get('status_color'),
        'status_lease': metrics.get('lease_rate', {}).get('status_color'),
        'composite_score': metrics.get('composite', {}).get('score')
    }
    
    return insert_metrics_snapshot(snapshot_data)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("Testing normalization logic...")
    
    # Test individual normalizations
    print("\n1. Lease Rate Tests:")
    for rate in [0.5, 3.0, 8.0, 25.0]:
        result = normalize_lease_rate(rate)
        print(f"   {rate}% -> {result['status_color']}: {result['status_label']}")
    
    print("\n2. Premium Tests:")
    for prem in [5.0, 12.0, 30.0, 60.0]:
        result = normalize_premium(prem)
        print(f"   {prem}% -> {result['status_color']}: {result['status_label']}")
    
    print("\n3. Inventory Tests:")
    for inv in [450, 350, 270, 180]:
        result = normalize_inventory(inv)
        print(f"   {inv}M oz -> {result['status_color']}: {result['status_label']}")
    
    print("\n4. Composite Score Tests:")
    test_metrics = {
        'premium': {'is_normalizing': True},
        'inventory': {'is_normalizing': True},
        'margin': {'is_normalizing': False},
        'lease_rate': {'is_normalizing': True}
    }
    result = calculate_composite_score(test_metrics)
    print(f"   3/4 normalizing -> {result['status_color']}: {result['status_label']}")
