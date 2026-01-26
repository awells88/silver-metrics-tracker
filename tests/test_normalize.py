"""
Tests for Silver Metrics Tracker.
"""

import pytest
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.config import THRESHOLDS
from scripts.db import init_database
from scripts.normalize import (
    normalize_lease_rate,
    normalize_premium,
    normalize_inventory,
    normalize_margin,
    calculate_composite_score,
    determine_status
)


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Initialize database before running tests."""
    init_database()


class TestNormalization:
    """Tests for normalization logic."""
    
    def test_lease_rate_normal(self):
        """Test that low lease rates are classified as normal."""
        result = normalize_lease_rate(1.5)
        assert result['status_color'] == 'green'
        assert result['is_normalizing'] == True
    
    def test_lease_rate_elevated(self):
        """Test that elevated lease rates are classified as yellow."""
        result = normalize_lease_rate(5.0)
        assert result['status_color'] == 'yellow'
    
    def test_lease_rate_stressed(self):
        """Test that high lease rates are classified as stressed."""
        result = normalize_lease_rate(15.0)
        assert result['status_color'] == 'red'
    
    def test_premium_normal(self):
        """Test normal premium levels."""
        result = normalize_premium(5.0)
        assert result['status_color'] == 'green'
        assert result['is_normalizing'] == True
    
    def test_premium_elevated(self):
        """Test elevated premium levels."""
        result = normalize_premium(15.0)
        assert result['status_color'] == 'yellow'
    
    def test_premium_extreme(self):
        """Test extreme premium levels."""
        result = normalize_premium(60.0)
        assert result['status_color'] == 'red'
    
    def test_inventory_healthy(self):
        """Test healthy inventory levels."""
        result = normalize_inventory(450.0)
        assert result['status_color'] == 'green'
        assert result['is_normalizing'] == True
    
    def test_inventory_low(self):
        """Test low inventory levels."""
        result = normalize_inventory(280.0)
        assert result['status_color'] == 'yellow'
    
    def test_inventory_critical(self):
        """Test critical inventory levels."""
        result = normalize_inventory(180.0)
        assert result['status_color'] == 'red'
    
    def test_composite_all_green(self):
        """Test composite score when all metrics are normalizing."""
        metrics = {
            'lease_rate': {'is_normalizing': True},
            'premium': {'is_normalizing': True},
            'inventory': {'is_normalizing': True},
            'margin': {'is_normalizing': True}
        }
        result = calculate_composite_score(metrics)
        assert result['score'] == 4
        assert result['total'] == 4
        assert result['status_color'] == 'green'
    
    def test_composite_mixed(self):
        """Test composite score with mixed signals."""
        metrics = {
            'lease_rate': {'is_normalizing': True},
            'premium': {'is_normalizing': False},
            'inventory': {'is_normalizing': False},
            'margin': {'is_normalizing': True}
        }
        result = calculate_composite_score(metrics)
        assert result['score'] == 2
        assert result['total'] == 4
        assert result['status_color'] == 'yellow'
    
    def test_composite_all_stressed(self):
        """Test composite score when all metrics are stressed."""
        metrics = {
            'lease_rate': {'is_normalizing': False},
            'premium': {'is_normalizing': False},
            'inventory': {'is_normalizing': False},
            'margin': {'is_normalizing': False}
        }
        result = calculate_composite_score(metrics)
        assert result['score'] == 0
        assert result['status_color'] == 'red'


class TestThresholds:
    """Tests for threshold configuration."""
    
    def test_lease_rate_thresholds_exist(self):
        """Verify lease rate thresholds are configured."""
        assert 'lease_rate' in THRESHOLDS
        assert 'normal_low' in THRESHOLDS['lease_rate']
        assert 'normal_high' in THRESHOLDS['lease_rate']
    
    def test_premium_thresholds_exist(self):
        """Verify premium thresholds are configured."""
        assert 'premium_pct' in THRESHOLDS
        assert 'normal_low' in THRESHOLDS['premium_pct']
        assert 'normal_high' in THRESHOLDS['premium_pct']
    
    def test_inventory_thresholds_exist(self):
        """Verify inventory thresholds are configured."""
        assert 'inventory_total' in THRESHOLDS
        assert 'healthy' in THRESHOLDS['inventory_total']
        assert 'stressed' in THRESHOLDS['inventory_total']
    
    def test_threshold_ordering(self):
        """Verify thresholds are in correct order."""
        lease = THRESHOLDS['lease_rate']
        assert lease['normal_low'] < lease['normal_high'] < lease['stressed'] < lease['extreme']
        
        premium = THRESHOLDS['premium_pct']
        assert premium['normal_low'] < premium['normal_high'] < premium['stressed'] < premium['extreme']


class TestDetermineStatus:
    """Tests for the determine_status helper function."""
    
    def test_higher_is_worse_extreme(self):
        """Test extreme value when higher is worse."""
        thresholds = {'normal_high': 10, 'stressed': 20, 'extreme': 50}
        color, label = determine_status(60, thresholds, higher_is_worse=True)
        assert color == 'red'
        assert label == 'Extreme'
    
    def test_higher_is_worse_normal(self):
        """Test normal value when higher is worse."""
        thresholds = {'normal_high': 10, 'stressed': 20, 'extreme': 50}
        color, label = determine_status(5, thresholds, higher_is_worse=True)
        assert color == 'green'
        assert label == 'Normal'
    
    def test_lower_is_worse_critical(self):
        """Test critical value when lower is worse (inventory)."""
        thresholds = {'normal_low': 300, 'stressed': 250, 'critical': 200}
        color, label = determine_status(180, thresholds, higher_is_worse=False)
        assert color == 'red'
        assert label == 'Critical'
    
    def test_lower_is_worse_healthy(self):
        """Test healthy value when lower is worse."""
        thresholds = {'healthy': 400, 'normal_low': 300, 'stressed': 250, 'critical': 200}
        color, label = determine_status(450, thresholds, higher_is_worse=False)
        assert color == 'green'
        assert label == 'Healthy'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
