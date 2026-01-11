import json
import logging
import os
import uuid
from datetime import datetime
import threading
from typing import Dict, List, Optional, Any


class AdPlayLogger:
    """Handles tracking and logging of ad play counts with XML confirmation support.
    
    Ad plays are only counted when confirmed via XML (ARTIST == "adRoll").
    All play data is stored in ad_play_events_{station}.json.
    """

    def __init__(self, config_manager, station_id):
        """
        Initialize the AdPlayLogger.

        Args:
            config_manager: ConfigManager instance to access and update ad configurations
            station_id: Station identifier (e.g., 'station_1047' or 'station_887')
        """
        self.config_manager = config_manager
        self.station_id = station_id

        # Thread safety lock
        self._lock = threading.RLock()

        # Set up logger based on station_id
        logger_name = f'AdPlayLogger_{station_id.split("_")[1]}'  # e.g., 'AdPlayLogger_1047'
        self.logger = logging.getLogger(logger_name)

        # Get project root (parent of src/ directory) for consistent file paths
        # This matches ConfigManager's approach to ensure files are always in the same location
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)

        # Station-specific confirmed events file - use absolute path
        station_number = station_id.split("_")[1]  # e.g., '1047' or '887'
        self.ad_events_file = os.path.join(project_root, f"ad_play_events_{station_number}.json")

    def generate_roll_id(self) -> str:
        """Generate a unique roll ID for tracking an ad roll attempt."""
        return str(uuid.uuid4())[:8]

    def record_roll_attempt(self, roll_id: str, ad_names: List[str], 
                           concat_validation: Optional[Dict] = None,
                           insertion_result: Optional[Dict] = None) -> bool:
        """
        Record an ad roll attempt (before XML confirmation).
        
        This creates a pending event that will be confirmed or marked as unconfirmed
        when XML confirmation is checked.

        Args:
            roll_id: Unique identifier for this roll attempt
            ad_names: List of ad names included in the roll
            concat_validation: Dict with keys 'ok', 'expected_ms', 'actual_ms'
            insertion_result: Dict with keys 'ok', 'status_code', 'message'

        Returns:
            bool: True if successfully recorded
        """
        with self._lock:
            try:
                events_data = self._load_events_file()
                
                # Create the pending event
                event = {
                    "roll_id": roll_id,
                    "attempted_at": datetime.now().isoformat(),
                    "attempted_hour": datetime.now().hour,
                    "ad_names": ad_names,
                    "concat_validation": concat_validation or {"ok": False},
                    "insertion_result": insertion_result or {"ok": False},
                    "xml_confirmation": {"ok": False},
                    "status": "pending"
                }
                
                events_data["pending_events"].append(event)
                self._save_events_file(events_data)
                
                self.logger.debug(f"Recorded roll attempt {roll_id} with {len(ad_names)} ads")
                return True
                
            except Exception as e:
                self.logger.error(f"Error recording roll attempt: {e}")
                return False

    def confirm_roll_playback(self, roll_id: str, xml_artist: str, 
                              xml_started_at: Optional[str] = None) -> bool:
        """
        Confirm that an ad roll was actually played based on XML evidence.
        
        This moves the event from pending to confirmed and updates statistics.

        Args:
            roll_id: The roll ID to confirm
            xml_artist: The ARTIST value from the XML (should be "adRoll")
            xml_started_at: The STARTED timestamp from the XML

        Returns:
            bool: True if successfully confirmed and stats updated
        """
        with self._lock:
            try:
                events_data = self._load_events_file()
                
                # Find the pending event
                pending_event = None
                pending_index = None
                for i, event in enumerate(events_data["pending_events"]):
                    if event["roll_id"] == roll_id:
                        pending_event = event
                        pending_index = i
                        break
                
                if pending_event is None:
                    self.logger.warning(f"No pending event found for roll_id {roll_id}")
                    return False
                
                # Verify XML confirmation (artist must be "adRoll", case-insensitive)
                is_adroll = xml_artist.lower() == "adroll"
                confirmed_at = datetime.now()
                
                if not is_adroll:
                    self.logger.warning(f"XML artist '{xml_artist}' is not 'adRoll' - cannot confirm")
                    return False
                
                # Check if confirmation is in the same hour as the attempt
                attempt_hour = pending_event.get("attempted_hour")
                current_hour = confirmed_at.hour
                same_hour = (attempt_hour == current_hour)
                
                if not same_hour:
                    self.logger.warning(f"Confirmation hour ({current_hour}) differs from attempt hour ({attempt_hour})")
                    # Still allow confirmation but log the discrepancy
                
                # Update the event with confirmation details
                pending_event["xml_confirmation"] = {
                    "ok": True,
                    "confirmed_at": confirmed_at.isoformat(),
                    "xml_started_at": xml_started_at,
                    "artist": xml_artist,
                    "same_hour": same_hour
                }
                pending_event["status"] = "confirmed"
                pending_event["confirmed_at"] = confirmed_at.isoformat()
                
                # Move from pending to confirmed
                events_data["pending_events"].pop(pending_index)
                events_data["confirmed_events"].append(pending_event)
                
                # Update confirmed statistics (hourly and daily)
                self._update_confirmed_stats(events_data, pending_event)
                
                self._save_events_file(events_data)
                
                # Update UI-visible PlayCount/LastPlayed in config
                self._update_config_play_counts(pending_event["ad_names"], confirmed_at)
                
                self.logger.info(f"Confirmed roll {roll_id} with {len(pending_event['ad_names'])} ads")
                return True
                
            except Exception as e:
                self.logger.error(f"Error confirming roll playback: {e}")
                return False

    def mark_roll_unconfirmed(self, roll_id: str, reason: str = "timeout") -> bool:
        """
        Mark a pending roll as unconfirmed (failed to get XML confirmation).
        
        This moves the event to unconfirmed_events for diagnostics but does NOT
        update play counts or statistics used in reports.

        Args:
            roll_id: The roll ID to mark as unconfirmed
            reason: Reason for not confirming (e.g., "timeout", "wrong_artist", "xml_error")

        Returns:
            bool: True if successfully marked
        """
        with self._lock:
            try:
                events_data = self._load_events_file()
                
                # Find the pending event
                pending_event = None
                pending_index = None
                for i, event in enumerate(events_data["pending_events"]):
                    if event["roll_id"] == roll_id:
                        pending_event = event
                        pending_index = i
                        break
                
                if pending_event is None:
                    self.logger.warning(f"No pending event found for roll_id {roll_id}")
                    return False
                
                # Update the event
                pending_event["xml_confirmation"] = {
                    "ok": False,
                    "reason": reason,
                    "checked_at": datetime.now().isoformat()
                }
                pending_event["status"] = "unconfirmed"
                
                # Move from pending to unconfirmed
                events_data["pending_events"].pop(pending_index)
                events_data["unconfirmed_events"].append(pending_event)
                
                self._save_events_file(events_data)
                
                self.logger.warning(f"Marked roll {roll_id} as unconfirmed: {reason}")
                return True
                
            except Exception as e:
                self.logger.error(f"Error marking roll as unconfirmed: {e}")
                return False

    def _update_confirmed_stats(self, events_data: Dict, event: Dict):
        """Update confirmed statistics from a confirmed event."""
        confirmed_at = datetime.fromisoformat(event["confirmed_at"])
        date_str = confirmed_at.strftime("%Y-%m-%d")
        hour = confirmed_at.hour
        hour_key = f"{date_str}_{hour:02d}"
        
        # Update hourly confirmed plays
        if hour_key not in events_data["hourly_confirmed"]:
            events_data["hourly_confirmed"][hour_key] = {}
        
        for ad_name in event["ad_names"]:
            events_data["hourly_confirmed"][hour_key][ad_name] = \
                events_data["hourly_confirmed"][hour_key].get(ad_name, 0) + 1
        
        # Update daily confirmed plays
        if date_str not in events_data["daily_confirmed"]:
            events_data["daily_confirmed"][date_str] = {}
        
        for ad_name in event["ad_names"]:
            events_data["daily_confirmed"][date_str][ad_name] = \
                events_data["daily_confirmed"][date_str].get(ad_name, 0) + 1
        
        # Update ad totals (confirmed only)
        for ad_name in event["ad_names"]:
            events_data["confirmed_ad_totals"][ad_name] = \
                events_data["confirmed_ad_totals"].get(ad_name, 0) + 1

    def _update_config_play_counts(self, ad_names: List[str], played_at: datetime):
        """Update PlayCount and LastPlayed in config for confirmed plays."""
        try:
            ads = self.config_manager.get_station_ads(self.station_id)
            if not ads:
                return
            
            updated = False
            for ad in ads:
                if ad.get("Name") in ad_names:
                    ad["PlayCount"] = ad.get("PlayCount", 0) + 1
                    ad["LastPlayed"] = played_at.isoformat()
                    updated = True
            
            if updated:
                self.config_manager.set_station_ads(self.station_id, ads)
                self.config_manager.save_config()
                
        except Exception as e:
            self.logger.error(f"Error updating config play counts: {e}")

    def _load_events_file(self) -> Dict:
        """Load the events file, creating structure if needed."""
        if os.path.exists(self.ad_events_file):
            try:
                with open(self.ad_events_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Ensure all required keys exist
                    data.setdefault("pending_events", [])
                    data.setdefault("confirmed_events", [])
                    data.setdefault("unconfirmed_events", [])
                    data.setdefault("hourly_confirmed", {})
                    data.setdefault("daily_confirmed", {})
                    data.setdefault("confirmed_ad_totals", {})
                    return data
            except json.JSONDecodeError:
                self.logger.warning("Could not load events file, creating new one")
        
        return {
            "pending_events": [],
            "confirmed_events": [],
            "unconfirmed_events": [],
            "hourly_confirmed": {},
            "daily_confirmed": {},
            "confirmed_ad_totals": {}
        }

    def _save_events_file(self, data: Dict):
        """Save the events file."""
        with open(self.ad_events_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_confirmed_events(self, start_date: Optional[str] = None, 
                            end_date: Optional[str] = None) -> List[Dict]:
        """
        Get confirmed play events, optionally filtered by date range.

        Args:
            start_date: Start date in YYYY-MM-DD format (inclusive)
            end_date: End date in YYYY-MM-DD format (inclusive)

        Returns:
            List of confirmed event dictionaries
        """
        with self._lock:
            events_data = self._load_events_file()
            confirmed = events_data.get("confirmed_events", [])
            
            if not start_date and not end_date:
                return confirmed
            
            filtered = []
            for event in confirmed:
                confirmed_at = event.get("confirmed_at", "")
                if confirmed_at:
                    event_date = confirmed_at[:10]  # YYYY-MM-DD
                    if self._is_date_in_range(event_date, start_date, end_date):
                        filtered.append(event)
            
            return filtered

    def get_hourly_confirmed_stats(self, start_date: Optional[str] = None,
                                   end_date: Optional[str] = None) -> Dict[str, Dict[str, int]]:
        """
        Get hourly confirmed play statistics.

        Args:
            start_date: Start date in YYYY-MM-DD format (inclusive)
            end_date: End date in YYYY-MM-DD format (inclusive)

        Returns:
            Dict mapping hour_key (YYYY-MM-DD_HH) to {ad_name: count}
        """
        with self._lock:
            events_data = self._load_events_file()
            hourly = events_data.get("hourly_confirmed", {})
            
            if not start_date and not end_date:
                return hourly
            
            filtered = {}
            for hour_key, ad_counts in hourly.items():
                # hour_key format: YYYY-MM-DD_HH
                date_part = hour_key[:10]
                if self._is_date_in_range(date_part, start_date, end_date):
                    filtered[hour_key] = ad_counts
            
            return filtered

    def get_daily_confirmed_stats(self, start_date: Optional[str] = None,
                                  end_date: Optional[str] = None) -> Dict[str, Dict[str, int]]:
        """
        Get daily confirmed play statistics.

        Args:
            start_date: Start date in YYYY-MM-DD format (inclusive)
            end_date: End date in YYYY-MM-DD format (inclusive)

        Returns:
            Dict mapping date (YYYY-MM-DD) to {ad_name: count}
        """
        with self._lock:
            events_data = self._load_events_file()
            daily = events_data.get("daily_confirmed", {})
            
            if not start_date and not end_date:
                return daily
            
            filtered = {}
            for date_str, ad_counts in daily.items():
                if self._is_date_in_range(date_str, start_date, end_date):
                    filtered[date_str] = ad_counts
            
            return filtered

    def get_confirmed_ad_totals(self, start_date: Optional[str] = None,
                                end_date: Optional[str] = None) -> Dict[str, int]:
        """
        Get total confirmed plays per ad, optionally filtered by date range.

        Args:
            start_date: Start date in YYYY-MM-DD format (inclusive)
            end_date: End date in YYYY-MM-DD format (inclusive)

        Returns:
            Dict mapping ad_name to total confirmed plays
        """
        if not start_date and not end_date:
            with self._lock:
                events_data = self._load_events_file()
                return events_data.get("confirmed_ad_totals", {})
        
        # Calculate from daily stats for filtered range
        daily = self.get_daily_confirmed_stats(start_date, end_date)
        totals = {}
        for date_str, ad_counts in daily.items():
            for ad_name, count in ad_counts.items():
                totals[ad_name] = totals.get(ad_name, 0) + count
        return totals

    def get_ad_statistics(self):
        """
        Get comprehensive ad play statistics.

        Returns:
            Dict containing ad statistics
        """
        try:
            ads = self.config_manager.get_station_ads(self.station_id)
            stats = {
                "total_ads": len(ads),
                "enabled_ads": sum(1 for ad in ads if ad.get("Enabled", False)),
                "total_plays": sum(ad.get("PlayCount", 0) for ad in ads),
                "ads_with_plays": sum(1 for ad in ads if ad.get("PlayCount", 0) > 0),
                "ad_details": []
            }

            for ad in ads:
                ad_detail = {
                    "name": ad.get("Name", "Unknown"),
                    "enabled": ad.get("Enabled", False),
                    "play_count": ad.get("PlayCount", 0),
                    "last_played": ad.get("LastPlayed"),
                    "mp3_file": ad.get("MP3File", ""),
                    "scheduled": ad.get("Scheduled", False)
                }
                stats["ad_details"].append(ad_detail)

            # Sort by play count (most played first)
            stats["ad_details"].sort(key=lambda x: x["play_count"], reverse=True)

            return stats

        except Exception as e:
            self.logger.error(f"Error getting ad statistics: {e}")
            return {"error": str(e)}

    def reset_all_play_counts(self):
        """
        Reset all ad play counts to zero.

        Returns:
            bool: True if successfully reset, False otherwise
        """
        try:
            ads = self.config_manager.get_station_ads(self.station_id)
            for ad in ads:
                ad["PlayCount"] = 0
                ad["LastPlayed"] = None

            self.config_manager.set_station_ads(self.station_id, ads)
            self.config_manager.save_config()

            self.logger.info("Reset all ad play counts")
            return True

        except Exception as e:
            self.logger.error(f"Error resetting play counts: {e}")
            return False

    def get_most_played_ads(self, limit=10):
        """
        Get the most played ads.

        Args:
            limit: Maximum number of ads to return

        Returns:
            List of ad dictionaries sorted by play count
        """
        stats = self.get_ad_statistics()
        return stats.get("ad_details", [])[:limit]

    def get_ad_statistics_filtered(self, start_date=None, end_date=None):
        """
        Get ad play statistics filtered by date range.

        Args:
            start_date: Start date in YYYY-MM-DD format (inclusive)
            end_date: End date in YYYY-MM-DD format (inclusive)

        Returns:
            Dict containing filtered ad statistics
        """
        try:
            # Get filtered daily confirmed stats from events file
            daily_confirmed = self.get_daily_confirmed_stats(start_date, end_date)
            
            # Calculate totals from filtered daily data
            filtered_totals = {}
            for date_str, ad_counts in daily_confirmed.items():
                for ad_name, count in ad_counts.items():
                    filtered_totals[ad_name] = filtered_totals.get(ad_name, 0) + count
            
            # Get current ads for structure
            ads = self.config_manager.get_station_ads(self.station_id)
            
            # Build ad details with filtered play counts
            ad_details = []
            total_plays = 0
            ads_with_plays = 0
            
            for ad in ads:
                ad_name = ad.get("Name", "Unknown")
                filtered_count = filtered_totals.get(ad_name, 0)
                
                if filtered_count > 0:
                    ads_with_plays += 1
                    total_plays += filtered_count
                
                ad_details.append({
                    "name": ad_name,
                    "enabled": ad.get("Enabled", False),
                    "play_count": filtered_count,
                    "last_played": ad.get("LastPlayed"),
                    "mp3_file": ad.get("MP3File", ""),
                    "scheduled": ad.get("Scheduled", False)
                })
            
            ad_details.sort(key=lambda x: x["play_count"], reverse=True)
            
            return {
                "total_ads": len(ads),
                "enabled_ads": sum(1 for ad in ads if ad.get("Enabled", False)),
                "total_plays": total_plays,
                "ads_with_plays": ads_with_plays,
                "ad_details": ad_details,
                "date_filter": {
                    "start_date": start_date,
                    "end_date": end_date,
                    "days_filtered": len(daily_confirmed)
                }
            }

        except Exception as e:
            self.logger.error(f"Error getting filtered ad statistics: {e}")
            return {"error": str(e)}

    def _is_date_in_range(self, date_str, start_date, end_date):
        """
        Check if a date string falls within the specified range.

        Args:
            date_str: Date string in YYYY-MM-DD format
            start_date: Start date in YYYY-MM-DD format (inclusive)
            end_date: End date in YYYY-MM-DD format (inclusive)

        Returns:
            bool: True if date is in range, False otherwise
        """
        try:
            # Parse the date string
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()

            # Check start date
            if start_date:
                start_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
                if date_obj < start_obj:
                    return False

            # Check end date
            if end_date:
                end_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
                if date_obj > end_obj:
                    return False

            return True

        except Exception as e:
            self.logger.error(f"Error checking date range for {date_str}: {e}")
            return False

