"""Create test ad and sample event data for testing the calendar feature."""
import json
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from config_manager import ConfigManager

def create_test_data():
    # Initialize config manager
    config_manager = ConfigManager()

    # Create a test ad for station_1047
    test_ad = {
        "Name": "Test Ad",
        "MP3File": "test_ad.mp3",
        "Enabled": True,
        "PlayCount": 15,
        "LastPlayed": "2026-01-10T14:00:00"
    }

    # Get existing ads and add test ad
    existing_ads = config_manager.get_station_ads('station_1047') or []

    # Check if test ad already exists
    if not any(ad.get('Name') == 'Test Ad' for ad in existing_ads):
        existing_ads.append(test_ad)
        config_manager.set_station_ads('station_1047', existing_ads)
        config_manager.save_config()
        print("Added test ad to config")
    else:
        print("Test ad already exists in config")

    # Create sample events file with play history
    events_data = {
        "pending_events": [],
        "confirmed_events": [],
        "unconfirmed_events": [],
        "hourly_confirmed": {
            # January 2026 - various days and hours
            "2026-01-05_10": {"Test Ad": 1},
            "2026-01-05_14": {"Test Ad": 1},
            "2026-01-06_09": {"Test Ad": 1},
            "2026-01-06_11": {"Test Ad": 1},
            "2026-01-06_15": {"Test Ad": 1},
            "2026-01-07_10": {"Test Ad": 1},
            "2026-01-08_08": {"Test Ad": 1},
            "2026-01-08_12": {"Test Ad": 1},
            "2026-01-08_16": {"Test Ad": 1},
            "2026-01-08_18": {"Test Ad": 1},
            "2026-01-09_09": {"Test Ad": 1},
            "2026-01-09_13": {"Test Ad": 1},
            "2026-01-10_10": {"Test Ad": 1},
            "2026-01-10_14": {"Test Ad": 1},
            "2026-01-10_17": {"Test Ad": 1},
        },
        "daily_confirmed": {
            "2026-01-05": {"Test Ad": 2},
            "2026-01-06": {"Test Ad": 3},
            "2026-01-07": {"Test Ad": 1},
            "2026-01-08": {"Test Ad": 4},
            "2026-01-09": {"Test Ad": 2},
            "2026-01-10": {"Test Ad": 3},
        },
        "confirmed_ad_totals": {
            "Test Ad": 15
        }
    }

    events_file = os.path.join(os.path.dirname(__file__), 'src', 'ad_play_events_1047.json')
    with open(events_file, 'w', encoding='utf-8') as f:
        json.dump(events_data, f, indent=2)
    print(f"Created events file: {events_file}")

    print("\nTest data created successfully!")
    print("Now restart the app and open Ad Statistics to test the calendar.")

if __name__ == '__main__':
    create_test_data()
