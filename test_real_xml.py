#!/usr/bin/env python3
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from config_manager import ConfigManager
from lecture_detector import LectureDetector

config = ConfigManager()
detector = LectureDetector(r'G:\To_RDS\nowplaying.xml', config)

print("=== ACTUAL XML FILE TEST ===")
current_info = detector.get_current_track_info()
print(f"Current track: '{current_info['artist']}' - '{current_info['title']}'")
print(f"Current is lecture: {detector.is_current_track_lecture()}")

print(f"Next is lecture: {detector.is_next_track_lecture()}")

# Let's manually check the next track artist
import xml.etree.ElementTree as ET
tree = ET.parse(r'G:\To_RDS\nowplaying.xml')
root = tree.getroot()
next_track = root.find('NEXTTRACK/TRACK')
if next_track is not None:
    next_artist = next_track.get('ARTIST', '').strip()
    next_title = next_track.get('TITLE', '').strip()
    print(f"Next track (manual parse): '{next_artist}' - '{next_title}'")
    print(f"Next artist starts with 'R': {next_artist.lower().startswith('r') if next_artist else False}")
    print(f"Next artist in blacklist: {next_artist.lower() in detector.blacklist if next_artist else False}")

print()
print(f"Blacklist: {detector.blacklist}")
print(f"Whitelist: {detector.whitelist}")

# Test the specific artists from the XML
test_artists = ['Rav Ezer Shwalbe', 'Avremi Roth']
for artist in test_artists:
    is_lecture = detector._is_artist_lecture(artist)
    in_blacklist = artist.lower() in detector.blacklist
    starts_with_r = artist.lower().startswith('r')
    print(f"'{artist}': is_lecture={is_lecture}, in_blacklist={in_blacklist}, starts_with_r={starts_with_r}")
