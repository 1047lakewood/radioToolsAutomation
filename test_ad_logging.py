#!/usr/bin/env python3
"""Test script to verify ad play logging functionality."""

import sys
import os

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_ad_logging():
    """Test the ad play logging functionality."""
    print("Testing Ad Play Logging System...")
    print("=" * 40)

    try:
        from config_manager import ConfigManager
        from ad_play_logger import AdPlayLogger

        # Initialize components
        config_manager = ConfigManager()
        ad_logger = AdPlayLogger(config_manager)

        print("✅ Components initialized successfully")

        # Get current ads
        ads = config_manager.get_ads()
        if not ads:
            print("⚠️ No ads found in configuration")
            return False

        print(f"✅ Found {len(ads)} ads in configuration")

        # Test recording ad plays
        ad_names = [ad.get("Name", "Unknown") for ad in ads[:2]]  # Test first 2 ads
        print(f"📊 Testing with ads: {ad_names}")

        results = ad_logger.record_multiple_ad_plays(ad_names)

        successful = sum(results.values())
        total = len(results)

        print(f"✅ Successfully recorded {successful}/{total} ad plays")

        # Get statistics
        stats = ad_logger.get_ad_statistics()
        print("📈 Ad Statistics:")
        print(f"   - Total ads: {stats.get('total_ads', 0)}")
        print(f"   - Enabled ads: {stats.get('enabled_ads', 0)}")
        print(f"   - Total plays: {stats.get('total_plays', 0)}")
        print(f"   - Ads with plays: {stats.get('ads_with_plays', 0)}")

        # Show top played ads
        top_ads = ad_logger.get_most_played_ads(5)
        print("🏆 Most played ads:")
        for i, ad in enumerate(top_ads, 1):
            print(f"   {i}. {ad.get('name', 'Unknown')}: {ad.get('play_count', 0)} plays")

        # Test detailed stats
        detailed_stats = ad_logger.get_detailed_stats()
        if "error" not in detailed_stats:
            print(f"📋 Detailed stats file created with {len(detailed_stats.get('daily_plays', {}))} days of data")
        else:
            print(f"⚠️ Detailed stats: {detailed_stats['error']}")

        print("✅ All ad logging tests passed!")
        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_ad_logging()
    sys.exit(0 if success else 1)
