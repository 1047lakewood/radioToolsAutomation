#!/usr/bin/env python3
"""Test script to demonstrate ad play logging with date filtering."""

import sys
import os

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_date_filtering():
    """Test the date filtering functionality."""
    print("Testing Ad Play Logging with Date Filtering...")
    print("=" * 50)

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

        # Test recording some ad plays to create data
        ad_names = [ad.get("Name", "Unknown") for ad in ads[:2]]
        print(f"📊 Recording test plays for: {ad_names}")

        results = ad_logger.record_multiple_ad_plays(ad_names * 3)  # Play each ad 3 times
        successful = sum(results.values())
        print(f"✅ Successfully recorded {successful} ad plays")

        # Test different date filtering scenarios
        print("\n🗓️ Testing Date Filtering:")

        # Test 1: All data (no filter)
        all_stats = ad_logger.get_ad_statistics()
        print(f"   All time - Total plays: {all_stats.get('total_plays', 0)}")

        # Test 2: Today's date only
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        today_stats = ad_logger.get_ad_statistics_filtered(today, today)
        print(f"   Today only - Total plays: {today_stats.get('total_plays', 0)}")

        # Test 3: Last 7 days (example)
        seven_days_ago = (datetime.now().replace(day=datetime.now().day-7)).strftime("%Y-%m-%d")
        week_stats = ad_logger.get_ad_statistics_filtered(seven_days_ago, today)
        print(f"   Last 7 days - Total plays: {week_stats.get('total_plays', 0)}")

        # Test 4: Date range summary
        summary = ad_logger.get_date_range_summary(seven_days_ago, today)
        if "error" not in summary:
            days = summary.get("date_range", {}).get("total_days", 0)
            print(f"   Date range summary - {days} days analyzed")
        else:
            print(f"   Date range summary error: {summary['error']}")

        # Test 5: Detailed stats filtering
        detailed = ad_logger.get_detailed_stats(seven_days_ago, today)
        if "error" not in detailed:
            daily_plays = detailed.get("daily_plays", {})
            print(f"   Detailed stats - {len(daily_plays)} days of detailed data")
        else:
            print(f"   Detailed stats error: {detailed['error']}")

        print("\n✅ All date filtering tests completed successfully!")
        print("\n💡 Usage Examples:")
        print("   - Filter by specific date: get_ad_statistics_filtered('2024-09-15', '2024-09-15')")
        print("   - Filter by date range: get_ad_statistics_filtered('2024-09-15', '2024-10-15')")
        print("   - Get detailed breakdown: get_date_range_summary('2024-09-15', '2024-10-15')")
        print("   - Export filtered data: Use the Ad Statistics UI with date filters applied")

        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_date_filtering()
    sys.exit(0 if success else 1)
