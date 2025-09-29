#!/usr/bin/env python3
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from lecture_detector import LectureDetector
from config_manager import ConfigManager
import time

print("=== TESTING FORCED REFRESH ===")

config = ConfigManager()
detector = LectureDetector(r'G:\To_RDS\nowplaying.xml', config)

# Check initial state
print("Initial check:")
current_info = detector.get_current_track_info()
print(f"  Current: '{current_info['artist']}' - '{current_info['title']}'")
print(f"  Current is lecture: {detector.is_current_track_lecture()}")
print(f"  Next is lecture: {detector.is_next_track_lecture()}")

# Force refresh
print("\nForcing refresh...")
detector.force_refresh()

# Wait a moment
time.sleep(1)

# Check again
print("After forced refresh:")
current_info = detector.get_current_track_info()
print(f"  Current: '{current_info['artist']}' - '{current_info['title']}'")
print(f"  Current is lecture: {detector.is_current_track_lecture()}")
print(f"  Next is lecture: {detector.is_next_track_lecture()}")

# Check file modification time
xml_path = r'G:\To_RDS\nowplaying.xml'
if os.path.exists(xml_path):
    mod_time = os.path.getmtime(xml_path)
    print(f"  File modification time: {mod_time}")
else:
    print("  XML file not found!")
