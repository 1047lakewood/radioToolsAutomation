#!/usr/bin/env python3
"""
Test script to monitor XML file updates and track ad insertion.
This helps verify if the nowplaying.xml file is being updated when ads are inserted.
"""

import os
import sys
import time
import json
import threading
from datetime import datetime
import xml.etree.ElementTree as ET

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from config_manager import ConfigManager

class XMLMonitor:
    def __init__(self, xml_path, station_id):
        self.xml_path = xml_path
        self.station_id = station_id
        self.last_artist = None
        self.last_mtime = 0
        self.ad_detections = []
        self.running = False

    def read_xml(self):
        """Read current track info from XML."""
        try:
            if not os.path.exists(self.xml_path):
                return None

            # Get file modification time
            mtime = os.path.getmtime(self.xml_path)

            with open(self.xml_path, 'r', encoding='utf-8') as f:
                content = f.read()

            root = ET.fromstring(content)
            track = root.find("TRACK")

            if track is not None:
                artist = (track.get("ARTIST") or "").strip()
                title = (track.findtext("TITLE") or "").strip()
                started = track.get("STARTED")

                return {
                    "artist": artist,
                    "title": title,
                    "started": started,
                    "mtime": mtime
                }
        except Exception as e:
            print("  [ERROR] Error reading XML: {}".format(e))

        return None

    def monitor(self, interval=1, duration=60):
        """Monitor XML file for changes."""
        print("\n[MONITOR] XML Monitor Started")
        print("[MONITOR] Station: {}".format(self.station_id))
        print("[MONITOR] XML Path: {}".format(self.xml_path))
        print("[MONITOR] Monitoring for {}s (checking every {}s)".format(duration, interval))
        print("[MONITOR] Looking for ARTIST='adRoll' (ad confirmation)\n")

        if not os.path.exists(self.xml_path):
            print("[MONITOR] [ERROR] XML file not found: {}".format(self.xml_path))
            return False

        self.running = True
        start_time = time.time()
        last_mtime = os.path.getmtime(self.xml_path)

        print("[MONITOR] [TIME]        [ARTIST]              [TITLE]                    [STATUS]")
        print("[MONITOR] " + "=" * 80)

        while self.running and (time.time() - start_time) < duration:
            try:
                track_info = self.read_xml()

                if track_info:
                    artist = track_info.get("artist", "")
                    title = track_info.get("title", "")
                    mtime = track_info.get("mtime", 0)

                    # Check if file changed
                    file_changed = mtime != last_mtime
                    if file_changed:
                        last_mtime = mtime

                    # Check for artist change
                    artist_changed = artist != self.last_artist

                    # Format output
                    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                    artist_display = artist[:20].ljust(20)
                    title_display = title[:25].ljust(25)

                    status = ""
                    if artist_changed:
                        if self.last_artist is None:
                            status = "INITIAL"
                        else:
                            status = "CHANGED"
                            if artist.lower() == "adroll":
                                status = "[AD DETECTED!]"
                                self.ad_detections.append({
                                    "time": timestamp,
                                    "artist": artist,
                                    "title": title
                                })

                    if file_changed or artist_changed:
                        print("[MONITOR] {}  {}  {}  {}".format(timestamp, artist_display, title_display, status))

                    self.last_artist = artist

                time.sleep(interval)

            except KeyboardInterrupt:
                print("\n[MONITOR] Monitoring paused by user")
                break
            except Exception as e:
                print("[MONITOR] [ERROR] {}".format(e))
                time.sleep(interval)

        self.running = False

        # Print summary
        print("[MONITOR] " + "=" * 80)
        print("\n[SUMMARY] Monitor Summary:")
        print("[SUMMARY] Duration: {:.1f}s".format(time.time() - start_time))
        print("[SUMMARY] Final Artist: {}".format(self.last_artist))
        print("[SUMMARY] Ad Detections: {}".format(len(self.ad_detections)))

        if self.ad_detections:
            print("\n[SUMMARY] SUCCESS - Ad insertions detected:")
            for ad in self.ad_detections:
                print("[SUMMARY]   - {}: {} - {}".format(ad['time'], ad['artist'], ad['title']))
            return True
        else:
            print("\n[SUMMARY] NOTE - No ad insertions detected")
            return False

    def stop(self):
        """Stop monitoring."""
        self.running = False


def main():
    print("\n" + "="*80)
    print("  XML File Monitor - Track Ad Insertions")
    print("="*80)

    # Load config
    try:
        config_manager = ConfigManager()
        print("[OK] Config loaded successfully\n")
    except Exception as e:
        print("[ERROR] Failed to load config: {}".format(e))
        return

    # Get XML paths for both stations
    xml_1047 = config_manager.get_station_setting("station_1047", "settings.intro_loader.now_playing_xml", "G:\\To_RDS\\nowplaying.xml")
    xml_887 = config_manager.get_station_setting("station_887", "settings.intro_loader.now_playing_xml", "G:\\To_RDS\\nowplaying_test.xml")

    print("Station 104.7 FM: {}".format(xml_1047))
    print("Station 88.7 FM:  {}".format(xml_887))
    print("")

    # Check which XML exists
    if os.path.exists(xml_1047):
        print("[OK] Using Station 104.7 FM XML\n")
        monitor = XMLMonitor(xml_1047, "station_1047")
    elif os.path.exists(xml_887):
        print("[OK] Using Station 88.7 FM XML\n")
        monitor = XMLMonitor(xml_887, "station_887")
    else:
        print("[ERROR] No XML file found!")
        print("  Checked: {}".format(xml_1047))
        print("  Checked: {}".format(xml_887))
        return

    # Run monitor in background thread
    def monitor_thread():
        monitor.monitor(interval=0.5, duration=120)  # Monitor for 2 minutes

    thread = threading.Thread(target=monitor_thread, daemon=True)
    thread.start()

    print("\n[INSTRUCTIONS]")
    print("  1. The main app should be running")
    print("  2. Trigger an ad insertion using Options > Debug > 'Play Ad Now'")
    print("  3. Watch for '[AD DETECTED!]' message when ARTIST changes to 'adRoll'")
    print("  4. This confirms the XML is updating when ads play")
    print("  5. Press Ctrl+C to stop monitoring\n")

    try:
        while monitor.running:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[STOPPING] Stopping monitor...")
        monitor.stop()
        thread.join(timeout=2)

    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    main()
