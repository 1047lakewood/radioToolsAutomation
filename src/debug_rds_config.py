import sys
import os
import socket
import logging
from datetime import datetime
import xml.etree.ElementTree as ET

# Ensure we can import from the current directory
sys.path.append(os.getcwd())

from config_manager import ConfigManager

# Configure logging to stdout
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def check_xml(xml_path):
    print(f"\nChecking XML: {xml_path}")
    if not os.path.exists(xml_path):
        print("  [FAILURE] File does not exist!")
        return {"artist": "", "title": ""}
    
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        current_track = root.find("TRACK")
        if current_track is not None:
            artist = current_track.get("ARTIST", "").strip()
            title = current_track.findtext("TITLE", "").strip()
            print(f"  [SUCCESS] Parsed XML. Artist: '{artist}', Title: '{title}'")
            return {"artist": artist, "title": title}
        else:
            print("  [WARNING] No TRACK element found.")
            return {"artist": "", "title": ""}
    except Exception as e:
        print(f"  [FAILURE] Error parsing XML: {e}")
        return {"artist": "", "title": ""}

def simulate_logic(messages, now_playing, station_name):
    print(f"\n--- Simulating Logic for {station_name} ---")
    valid_count = 0
    now = datetime.now()
    current_hour = now.hour
    day_mapping = {"Sun": "Sunday", "Mon": "Monday", "Tue": "Tuesday",
                   "Wed": "Wednesday", "Thu": "Thursday", "Fri": "Friday",
                   "Sat": "Saturday"}
    full_day_name = day_mapping.get(now.strftime("%a"))
    
    print(f"Current Time: {full_day_name} {current_hour}:XX")
    
    for i, msg in enumerate(messages):
        text = msg.get("Text", "(No Text)")
        prefix = f"Msg [{i}] '{text[:20]}...'"
        
        # 1. Enabled
        if not msg.get("Enabled", True):
            print(f"  {prefix} -> SKIP (Disabled)")
            continue
            
        # 2. Placeholders
        if "{artist}" in text and not now_playing.get("artist"):
             print(f"  {prefix} -> SKIP (Need artist)")
             continue
        if "{title}" in text and not now_playing.get("title"):
             print(f"  {prefix} -> SKIP (Need title)")
             continue
             
        # 3. Schedule
        schedule_info = msg.get("Scheduled", {})
        if schedule_info.get("Enabled", False):
            scheduled_days = schedule_info.get("Days", [])
            if scheduled_days and full_day_name not in scheduled_days:
                print(f"  {prefix} -> SKIP (Wrong Day: {scheduled_days})")
                continue
                
            scheduled_times = schedule_info.get("Times", [])
            if scheduled_times:
                hour_match = False
                for time_obj in scheduled_times:
                    if isinstance(time_obj, dict) and "hour" in time_obj:
                         if int(time_obj.get("hour")) == current_hour:
                             hour_match = True
                             break
                if not hour_match:
                    print(f"  {prefix} -> SKIP (Wrong Hour)")
                    continue
        
        print(f"  {prefix} -> VALID")
        valid_count += 1
        
    print(f"Total Valid Messages: {valid_count} / {len(messages)}")

def main():
    print("--- RDS Logic Debugger ---")
    cm = ConfigManager()
    
    # Analyze Station 104.7
    print("\nView Station 104.7")
    xml_path_1047 = cm.get_station_setting("station_1047", "settings.rds.now_playing_xml", "MISSING")
    default_msg_1047 = cm.get_station_setting("station_1047", "settings.rds.default_message", "MISSING")
    print(f"Default Message: {default_msg_1047}")
    
    now_playing_1047 = check_xml(xml_path_1047)
    msgs_1047 = cm.get_station_messages("station_1047")
    simulate_logic(msgs_1047, now_playing_1047, "Station 104.7")
    
    # Analyze Station 88.7
    print("\nView Station 88.7")
    xml_path_887 = cm.get_station_setting("station_887", "settings.rds.now_playing_xml", "MISSING")
    default_msg_887 = cm.get_station_setting("station_887", "settings.rds.default_message", "MISSING")
    print(f"Default Message: {default_msg_887}")
    
    now_playing_887 = check_xml(xml_path_887)
    msgs_887 = cm.get_station_messages("station_887")
    simulate_logic(msgs_887, now_playing_887, "Station 88.7")

if __name__ == "__main__":
    main()
