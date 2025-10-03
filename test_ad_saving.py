#!/usr/bin/env python3
"""
Test script to verify ad saving functionality.
"""
import sys
import os
sys.path.append('src')

from config_manager import ConfigManager

def test_ad_saving():
    """Test that ads are being saved and loaded correctly."""
    print("Testing ad saving functionality...")

    # Initialize config manager
    config_manager = ConfigManager()

    # Get current ads
    ads = config_manager.get_ads()
    print(f"Currently loaded {len(ads) if ads else 0} ads")

    if ads:
        print("Current ads:")
        for i, ad in enumerate(ads):
            print(f"  {i+1}. {ad.get('Name', 'Unnamed')} - {ad.get('MP3File', 'No file')}")

    # Test saving a new ad
    test_ad = {
        'Name': 'Test Ad',
        'Enabled': True,
        'Scheduled': False,
        'MP3File': 'test.mp3',
        'Days': [],
        'Times': []
    }

    print("\nAdding test ad...")
    if not ads:
        ads = []
    ads.append(test_ad)

    # Save the ads
    config_manager.set_ads(ads)
    config_manager.save_config()
    print("Test ad saved to config")

    # Load ads again to verify
    reloaded_ads = config_manager.get_ads()
    print(f"After reload: {len(reloaded_ads) if reloaded_ads else 0} ads")

    if reloaded_ads:
        print("Reloaded ads:")
        for i, ad in enumerate(reloaded_ads):
            print(f"  {i+1}. {ad.get('Name', 'Unnamed')} - {ad.get('MP3File', 'No file')}")

    # Check if test ad exists
    test_found = any(ad.get('Name') == 'Test Ad' for ad in reloaded_ads)
    print(f"\nTest ad found in reloaded config: {test_found}")

    if test_found:
        print("✅ Ad saving functionality is working correctly!")
    else:
        print("❌ Ad saving functionality is NOT working!")

if __name__ == "__main__":
    test_ad_saving()
