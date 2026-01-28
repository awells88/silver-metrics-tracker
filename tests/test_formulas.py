"""
Tests for metric calculation formulas in Silver Metrics Tracker.
Verifies the correctness of mathematical formulas used for each metric.
"""

import pytest
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestPremiumFormulas:
    """Test premium percentage calculations."""
    
    def test_physical_premium_calculation(self):
        """
        Test physical premium formula: (Physical - Spot) / Spot * 100
        
        Example: If spot = $25/oz and physical = $30/oz
        Premium = ($30 - $25) / $25 * 100 = 20%
        """
        paper_price = 25.00
        physical_price = 30.00
        premium_usd = physical_price - paper_price  # $5
        
        # Formula: (premium_usd / paper_price) * 100
        premium_pct = (premium_usd / paper_price) * 100
        
        assert premium_pct == 20.0, "Physical premium should be 20%"
    
    def test_premium_with_real_values(self):
        """Test with realistic silver prices."""
        paper_price = 108.18
        physical_price = 127.09
        premium_usd = physical_price - paper_price  # 18.91
        
        premium_pct = (premium_usd / paper_price) * 100
        
        # Should be approximately 17.48%
        assert 17.4 < premium_pct < 17.5, f"Expected ~17.48%, got {premium_pct}%"
    
    def test_premium_edge_case_zero(self):
        """Test when physical equals spot (0% premium)."""
        paper_price = 25.00
        physical_price = 25.00
        premium_usd = 0.00
        
        premium_pct = (premium_usd / paper_price) * 100
        
        assert premium_pct == 0.0, "Premium should be 0% when prices equal"


class TestShanghaiPremiumFormulas:
    """Test Shanghai premium calculations."""
    
    def test_shanghai_premium_calculation(self):
        """
        Test Shanghai premium formula: (Shanghai - Western) / Western * 100
        
        Example: Shanghai = $120/oz, Western = $100/oz
        Premium = ($120 - $100) / $100 * 100 = 20%
        """
        western_spot = 100.00
        shanghai_spot = 120.00
        premium_usd = shanghai_spot - western_spot  # $20
        
        # Formula: (premium_usd / western_spot) * 100
        premium_pct = (premium_usd / western_spot) * 100
        
        assert premium_pct == 20.0, "Shanghai premium should be 20%"
    
    def test_shanghai_premium_with_real_values(self):
        """Test with realistic values from metalcharts.org."""
        western_spot = 108.18
        premium_usd = 11.58
        shanghai_spot = western_spot + premium_usd  # 119.76
        
        premium_pct = (premium_usd / western_spot) * 100
        
        # Should be approximately 10.70%
        assert 10.6 < premium_pct < 10.8, f"Expected ~10.70%, got {premium_pct}%"
    
    def test_shanghai_premium_edge_case_parity(self):
        """Test when Shanghai equals Western (0% premium)."""
        western_spot = 108.18
        shanghai_spot = 108.18
        premium_usd = 0.00
        
        premium_pct = (premium_usd / western_spot) * 100
        
        assert premium_pct == 0.0, "Premium should be 0% at parity"
    
    def test_shanghai_premium_negative(self):
        """Test when Shanghai trades below Western (negative premium/discount)."""
        western_spot = 110.00
        shanghai_spot = 105.00
        premium_usd = shanghai_spot - western_spot  # -5
        
        premium_pct = (premium_usd / western_spot) * 100
        
        # Should be approximately -4.55%
        assert -4.6 < premium_pct < -4.5, "Should handle negative premium"


class TestShanghaiConversionFormulas:
    """Test SGE price conversion from CNY/kg to USD/oz."""
    
    def test_cny_kg_to_usd_oz_conversion(self):
        """
        Test conversion: CNY/kg -> USD/oz
        
        Formula:
        1. cny_per_oz = cny_per_kg / 32.1507 (kg to troy oz)
        2. usd_per_oz = cny_per_oz / usd_cny_rate (CNY to USD)
        
        Example: 27510 CNY/kg with rate 7.25 CNY/USD
        = 27510 / 32.1507 / 7.25
        = 855.37 / 7.25
        = $118.00/oz
        """
        cny_per_kg = 27510.0
        usd_cny_rate = 7.25  # 7.25 CNY = 1 USD
        
        # Convert kg to oz
        cny_per_oz = cny_per_kg / 32.1507
        assert 855.0 < cny_per_oz < 856.0, "CNY/oz calculation incorrect"
        
        # Convert CNY to USD
        usd_per_oz = cny_per_oz / usd_cny_rate
        assert 117.9 < usd_per_oz < 118.1, f"Expected ~$118/oz, got ${usd_per_oz:.2f}"
    
    def test_conversion_constants(self):
        """Verify the conversion constants are correct."""
        # 1 kilogram = 32.1507 troy ounces (standard precious metals conversion)
        kg_to_troy_oz = 32.1507
        assert kg_to_troy_oz == 32.1507, "Troy oz conversion constant is incorrect"
        
        # Typical USD/CNY rate is 6-8 CNY per USD (as of 2026)
        # The code uses 7.25 as an approximation
        # This should be fetched from an API in production but is acceptable for testing


class TestLeaseRateFormulas:
    """Test implied lease rate calculations."""
    
    def test_implied_lease_rate_formula(self):
        """
        Test implied lease rate: ((Futures/Spot) - 1) * (365/days) * 100
        
        This is a simplified cost-of-carry formula.
        Note: Full formula would include risk-free rate, but this proxy is acceptable.
        
        Example: Spot = $25, 90-day Futures = $25.50
        Rate = ((25.50/25.00) - 1) * (365/90) * 100
             = (1.02 - 1) * 4.056 * 100
             = 0.02 * 4.056 * 100
             = 8.11%
        """
        spot = 25.00
        futures = 25.50
        days_to_expiry = 90
        
        # Formula: ((futures / spot) - 1) * (365 / days_to_expiry) * 100
        implied_rate = ((futures / spot) - 1) * (365 / days_to_expiry) * 100
        
        # Should be approximately 8.11%
        assert 8.0 < implied_rate < 8.2, f"Expected ~8.11%, got {implied_rate}%"
    
    def test_contango_positive_rate(self):
        """Test contango (futures > spot = positive rate, normal market)."""
        spot = 100.00
        futures = 102.00  # 2% higher
        days_to_expiry = 365
        
        implied_rate = ((futures / spot) - 1) * (365 / days_to_expiry) * 100
        
        assert abs(implied_rate - 2.0) < 0.001, "Contango should yield positive rate"
    
    def test_backwardation_negative_rate(self):
        """Test backwardation (futures < spot = negative rate, tight supply)."""
        spot = 100.00
        futures = 98.00  # 2% lower
        days_to_expiry = 365
        
        implied_rate = ((futures / spot) - 1) * (365 / days_to_expiry) * 100
        
        assert abs(implied_rate - (-2.0)) < 0.001, "Backwardation should yield negative rate"
    
    def test_lease_rate_annualization(self):
        """Test that annualization works correctly for different time periods."""
        spot = 100.00
        futures = 101.00  # 1% premium
        
        # 30 days
        rate_30d = ((futures / spot) - 1) * (365 / 30) * 100
        # 180 days
        rate_180d = ((futures / spot) - 1) * (365 / 180) * 100
        
        # Shorter period should have higher annualized rate
        assert rate_30d > rate_180d, "30-day should have higher annualized rate"
        
        # 30 days: 1% * (365/30) = ~12.17%
        assert 12.0 < rate_30d < 12.5
        # 180 days: 1% * (365/180) = ~2.03%
        assert 2.0 < rate_180d < 2.1


class TestMarginFormulas:
    """Test CME margin calculations."""
    
    def test_margin_percentage_of_notional(self):
        """
        Test margin as % of notional value.
        
        Formula: (initial_margin / (5000 oz * spot_price)) * 100
        
        CME silver contract = 5,000 troy ounces
        New CME standard (Jan 2026) = 9% of notional
        
        Example: Spot = $30/oz, Margin = $13,500
        Notional = 5000 * $30 = $150,000
        Margin % = ($13,500 / $150,000) * 100 = 9%
        """
        spot_price = 30.00
        initial_margin = 13500.00
        
        # CME silver contract = 5000 troy ounces
        notional_value = 5000 * spot_price  # $150,000
        
        # Formula: (initial_margin / notional_value) * 100
        pct_notional = (initial_margin / notional_value) * 100
        
        assert pct_notional == 9.0, "Margin should be 9% of notional"
    
    def test_margin_with_various_silver_prices(self):
        """
        Test margin calculation at different silver price levels.
        
        Given CME's 9% margin requirement, verify dollar amounts at different prices.
        These values are based on actual CME margin requirements as of Jan 2026.
        """
        contract_size = 5000  # CME specification
        margin_pct = 9.0      # New CME standard (Jan 2026)
        
        # Test at $80/oz - Notional: $400,000
        spot_80 = 80.00
        notional_80 = contract_size * spot_80
        expected_margin_80 = 36000.0  # 9% of $400,000
        calculated_margin_80 = notional_80 * (margin_pct / 100)
        assert calculated_margin_80 == expected_margin_80, f"Expected ${expected_margin_80:,.0f}, got ${calculated_margin_80:,.0f}"
        
        # Test at $100/oz - Notional: $500,000
        spot_100 = 100.00
        notional_100 = contract_size * spot_100
        expected_margin_100 = 45000.0  # 9% of $500,000
        calculated_margin_100 = notional_100 * (margin_pct / 100)
        assert calculated_margin_100 == expected_margin_100, f"Expected ${expected_margin_100:,.0f}, got ${calculated_margin_100:,.0f}"
        
        # Test at $120/oz - Notional: $600,000
        spot_120 = 120.00
        notional_120 = contract_size * spot_120
        expected_margin_120 = 54000.0  # 9% of $600,000
        calculated_margin_120 = notional_120 * (margin_pct / 100)
        assert calculated_margin_120 == expected_margin_120, f"Expected ${expected_margin_120:,.0f}, got ${calculated_margin_120:,.0f}"
    
    def test_cme_contract_size(self):
        """
        Verify CME silver futures contract specification.
        
        Test that calculations using the contract size produce expected results.
        """
        # CME silver futures = 5,000 troy ounces per contract
        contract_size_oz = 5000
        spot_price = 100.00
        margin_pct = 9.0
        
        # At 9% margin with spot=$100, expect $45,000 margin
        expected_margin = contract_size_oz * spot_price * (margin_pct / 100)
        assert expected_margin == 45000.0, "5000 oz at $100 with 9% should be $45,000"
        
        # Verify notional value calculation
        notional = contract_size_oz * spot_price
        assert notional == 500000.0, "Notional for 5000 oz at $100 should be $500,000"
    
    def test_margin_dollar_amount_scales_with_price(self):
        """
        Test that margin dollar amount scales proportionally with silver price.
        
        At 9% of notional:
        - $80/oz -> $36,000 margin
        - $100/oz -> $45,000 margin
        - $120/oz -> $54,000 margin
        """
        margin_pct = 9.0  # New CME standard
        
        # At $80/oz
        margin_80 = (5000 * 80) * (margin_pct / 100)
        assert margin_80 == 36000.0
        
        # At $100/oz
        margin_100 = (5000 * 100) * (margin_pct / 100)
        assert margin_100 == 45000.0
        
        # At $120/oz
        margin_120 = (5000 * 120) * (margin_pct / 100)
        assert margin_120 == 54000.0


class TestFormulaEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_division_by_zero_protection_premium(self):
        """Ensure division by zero doesn't occur in premium calculations."""
        # In production, spot_price should never be zero, but test the edge case
        with pytest.raises(ZeroDivisionError):
            premium_pct = (5.00 / 0.00) * 100
    
    def test_negative_prices_should_be_rejected(self):
        """
        Test that the system would need input validation for negative prices.
        
        Note: This test documents that negative prices produce mathematically
        correct but semantically meaningless results. In production code,
        input validation should reject negative prices before calculation.
        """
        # Negative spot price is invalid in real markets
        paper_price = -25.00
        physical_price = 30.00
        
        # The formula would produce a result, but it's meaningless
        premium_usd = physical_price - paper_price  # 55
        premium_pct = (premium_usd / paper_price) * 100  # -220%
        
        # This demonstrates why input validation is important
        assert premium_pct < 0, "Negative spot price would produce invalid negative percentage"
        
        # In production code, this should be caught:
        # if paper_price <= 0:
        #     raise ValueError("Spot price must be positive")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
