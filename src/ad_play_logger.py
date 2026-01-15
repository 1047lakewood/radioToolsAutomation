import json
import logging
import os
from datetime import datetime
import threading
from typing import Dict, List, Optional


class AdPlayLogger:
    """Handles tracking and logging of ad plays with ultra-compact storage.

    Storage format for plays (ad_plays_{station}.json):
    {
        "Ad Name": {
            "01-11-26": [14, 16, 19],
            "01-12-26": [9, 11]
        }
    }

    Storage format for failures (ad_failures_{station}.json):
    [
        {"t": "01-11-26 14:05", "ads": ["Ad1"], "err": "concat_failed"}
    ]
    """

    MAX_FAILURES = 50  # Keep only last 50 failures

    def __init__(self, config_manager, station_id):
        """Initialize the AdPlayLogger."""
        self.config_manager = config_manager
        self.station_id = station_id
        self._lock = threading.RLock()

        # Set up logger
        logger_name = f'AdPlayLogger_{station_id.split("_")[1]}'
        self.logger = logging.getLogger(logger_name)

        # Get project root for file paths
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        user_data_dir = os.path.join(project_root, "user_data")

        # Ensure user_data directory exists
        os.makedirs(user_data_dir, exist_ok=True)

        station_number = station_id.split("_")[1]
        self.plays_file = os.path.join(user_data_dir, f"ad_plays_{station_number}.json")
        self.failures_file = os.path.join(user_data_dir, f"ad_failures_{station_number}.json")

        # Old format file for migration
        self.old_events_file = os.path.join(project_root, f"ad_play_events_{station_number}.json")

        # Migrate from old format if needed
        self._migrate_if_needed()

    def _migrate_if_needed(self):
        """Migrate from old verbose format to new compact format."""
        if not os.path.exists(self.old_events_file):
            return

        # Check if new file already exists
        if os.path.exists(self.plays_file):
            return

        try:
            with open(self.old_events_file, 'r', encoding='utf-8') as f:
                old_data = json.load(f)

            # Check if it's old format
            if 'hourly_confirmed' not in old_data and 'confirmed_events' not in old_data:
                return

            self.logger.info("Migrating from old ad events format to compact format...")

            new_plays = {}

            # Migrate from hourly_confirmed (format: "2026-01-11_14": {"Ad Name": 1})
            hourly = old_data.get('hourly_confirmed', {})
            for hour_key, ad_counts in hourly.items():
                # Parse "2026-01-11_14" -> date "01-11-26", hour 14
                parts = hour_key.split('_')
                if len(parts) != 2:
                    continue
                date_part = parts[0]  # "2026-01-11"
                hour = int(parts[1])

                # Convert to compact date format "MM-DD-YY"
                try:
                    dt = datetime.strptime(date_part, "%Y-%m-%d")
                    compact_date = dt.strftime("%m-%d-%y")
                except:
                    continue

                for ad_name, count in ad_counts.items():
                    if ad_name not in new_plays:
                        new_plays[ad_name] = {}
                    if compact_date not in new_plays[ad_name]:
                        new_plays[ad_name][compact_date] = []

                    # Add the hour (count times, usually 1)
                    for _ in range(count):
                        if hour not in new_plays[ad_name][compact_date]:
                            new_plays[ad_name][compact_date].append(hour)

            # Sort hours in each date
            for ad_name in new_plays:
                for date in new_plays[ad_name]:
                    new_plays[ad_name][date].sort()

            # Save new format
            self._save_plays(new_plays)

            # Backup old file
            backup_name = self.old_events_file.replace('.json', '_migrated.json')
            os.rename(self.old_events_file, backup_name)

            self.logger.info(f"Migration complete. Old file backed up to {backup_name}")

        except Exception as e:
            self.logger.error(f"Migration failed: {e}")

    def _load_plays(self) -> Dict:
        """Load the plays file."""
        if os.path.exists(self.plays_file):
            try:
                with open(self.plays_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                self.logger.warning("Could not load plays file, creating new one")
        return {}

    def _save_plays(self, data: Dict):
        """Save the plays file."""
        with open(self.plays_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, separators=(',', ':'))

    def _load_failures(self) -> List:
        """Load the failures file."""
        if os.path.exists(self.failures_file):
            try:
                with open(self.failures_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                self.logger.warning("Could not load failures file, creating new one")
        return []

    def _save_failures(self, data: List):
        """Save the failures file."""
        with open(self.failures_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, separators=(',', ':'))

    def log_play(self, ad_name: str) -> bool:
        """Record a successful ad play. Ultra-compact storage."""
        with self._lock:
            try:
                now = datetime.now()
                date_str = now.strftime("%m-%d-%y")
                hour = now.hour

                plays = self._load_plays()

                if ad_name not in plays:
                    plays[ad_name] = {}
                if date_str not in plays[ad_name]:
                    plays[ad_name][date_str] = []

                plays[ad_name][date_str].append(hour)

                self._save_plays(plays)
                self.logger.info(f"Logged play for '{ad_name}' at {date_str} hour {hour}")
                return True

            except Exception as e:
                self.logger.error(f"Error logging play: {e}")
                return False

    def log_failure(self, ad_names: List[str], error: str) -> bool:
        """Record a failure for debugging. Keeps last MAX_FAILURES entries."""
        with self._lock:
            try:
                now = datetime.now()
                timestamp = now.strftime("%m-%d-%y %H:%M")

                failures = self._load_failures()

                failures.append({
                    "t": timestamp,
                    "ads": ad_names,
                    "err": error
                })

                # Keep only last MAX_FAILURES
                if len(failures) > self.MAX_FAILURES:
                    failures = failures[-self.MAX_FAILURES:]

                self._save_failures(failures)
                self.logger.warning(f"Logged failure for {ad_names}: {error}")
                return True

            except Exception as e:
                self.logger.error(f"Error logging failure: {e}")
                return False

    def get_ad_statistics(self) -> Dict:
        """Get comprehensive ad statistics from plays file (single source of truth)."""
        try:
            plays = self._load_plays()
            ads = self.config_manager.get_station_ads(self.station_id) or []

            # Build ad details
            ad_details = []
            total_plays = 0
            ads_with_plays = 0

            for ad in ads:
                ad_name = ad.get("Name", "Unknown")
                ad_plays = plays.get(ad_name, {})

                # Calculate total plays for this ad
                play_count = sum(len(hours) for hours in ad_plays.values())
                total_plays += play_count

                if play_count > 0:
                    ads_with_plays += 1

                # Calculate last played
                last_played = self._get_last_played(ad_name, ad_plays)

                ad_details.append({
                    "name": ad_name,
                    "enabled": ad.get("Enabled", False),
                    "play_count": play_count,
                    "last_played": last_played,
                    "mp3_file": ad.get("MP3File", ""),
                    "scheduled": ad.get("Scheduled", False)
                })

            # Sort by play count (most played first)
            ad_details.sort(key=lambda x: x["play_count"], reverse=True)

            return {
                "total_ads": len(ads),
                "enabled_ads": sum(1 for ad in ads if ad.get("Enabled", False)),
                "total_plays": total_plays,
                "ads_with_plays": ads_with_plays,
                "ad_details": ad_details
            }

        except Exception as e:
            self.logger.error(f"Error getting ad statistics: {e}")
            return {"error": str(e)}

    def _get_last_played(self, ad_name: str, ad_plays: Dict = None) -> Optional[str]:
        """Get the last played datetime for an ad."""
        if ad_plays is None:
            plays = self._load_plays()
            ad_plays = plays.get(ad_name, {})

        if not ad_plays:
            return None

        # Find the most recent date and hour
        latest_date = None
        latest_hour = None

        for date_str, hours in ad_plays.items():
            if not hours:
                continue
            max_hour = max(hours)

            try:
                dt = datetime.strptime(date_str, "%m-%d-%y")
                if latest_date is None or dt > latest_date or (dt == latest_date and max_hour > latest_hour):
                    latest_date = dt
                    latest_hour = max_hour
            except:
                continue

        if latest_date and latest_hour is not None:
            latest_date = latest_date.replace(hour=latest_hour)
            return latest_date.isoformat()

        return None

    def get_ad_statistics_filtered(self, start_date: str = None, end_date: str = None) -> Dict:
        """Get ad statistics filtered by date range."""
        try:
            plays = self._load_plays()
            ads = self.config_manager.get_station_ads(self.station_id) or []

            # Parse date range
            start_dt = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
            end_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else None

            ad_details = []
            total_plays = 0
            ads_with_plays = 0

            for ad in ads:
                ad_name = ad.get("Name", "Unknown")
                ad_plays = plays.get(ad_name, {})

                # Calculate filtered plays
                play_count = 0
                for date_str, hours in ad_plays.items():
                    try:
                        dt = datetime.strptime(date_str, "%m-%d-%y")
                        if start_dt and dt < start_dt:
                            continue
                        if end_dt and dt > end_dt:
                            continue
                        play_count += len(hours)
                    except:
                        continue

                total_plays += play_count
                if play_count > 0:
                    ads_with_plays += 1

                last_played = self._get_last_played(ad_name, ad_plays)

                ad_details.append({
                    "name": ad_name,
                    "enabled": ad.get("Enabled", False),
                    "play_count": play_count,
                    "last_played": last_played,
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
                    "end_date": end_date
                }
            }

        except Exception as e:
            self.logger.error(f"Error getting filtered ad statistics: {e}")
            return {"error": str(e)}

    def get_play_hours_for_date(self, ad_name: str, date_str: str) -> List[int]:
        """Get hours an ad played on a specific date.

        Args:
            ad_name: Name of the ad
            date_str: Date in MM-DD-YY format

        Returns:
            List of hours (0-23) the ad played
        """
        with self._lock:
            plays = self._load_plays()
            ad_plays = plays.get(ad_name, {})
            return sorted(ad_plays.get(date_str, []))

    def get_daily_play_counts(self, ad_name: str) -> Dict[str, int]:
        """Get play counts per day for an ad.

        Returns:
            Dict mapping date (MM-DD-YY) to play count
        """
        with self._lock:
            plays = self._load_plays()
            ad_plays = plays.get(ad_name, {})
            return {date: len(hours) for date, hours in ad_plays.items()}

    def was_ad_played_this_hour(self) -> bool:
        """Check if any ad was played in the current hour.

        Returns:
            True if at least one ad was played this hour, False otherwise.
        """
        with self._lock:
            try:
                now = datetime.now()
                date_str = now.strftime("%m-%d-%y")
                current_hour = now.hour

                plays = self._load_plays()

                # Check all ads for a play in the current hour
                for ad_name, ad_plays in plays.items():
                    if date_str in ad_plays:
                        hours = ad_plays[date_str]
                        if current_hour in hours:
                            self.logger.debug(f"Ad '{ad_name}' was played this hour ({current_hour}:00)")
                            return True

                self.logger.debug(f"No ads played this hour ({date_str} hour {current_hour})")
                return False

            except Exception as e:
                self.logger.error(f"Error checking if ad played this hour: {e}")
                return False

    def get_failures(self) -> List[Dict]:
        """Get the failure log."""
        with self._lock:
            return self._load_failures()

    def reset_all(self) -> bool:
        """Clear all play data and failures."""
        with self._lock:
            try:
                # Clear plays file
                self._save_plays({})

                # Clear failures file
                self._save_failures([])

                self.logger.info("Reset all ad play data")
                return True

            except Exception as e:
                self.logger.error(f"Error resetting play data: {e}")
                return False

    # Legacy method aliases for compatibility during transition
    def reset_all_play_counts(self) -> bool:
        """Legacy alias for reset_all()."""
        return self.reset_all()

    def get_most_played_ads(self, limit: int = 10) -> List[Dict]:
        """Get the most played ads."""
        stats = self.get_ad_statistics()
        return stats.get("ad_details", [])[:limit]

    # Methods needed by ad_report_generator.py
    def get_daily_confirmed_stats(self, start_date: str = None, end_date: str = None) -> Dict[str, Dict[str, int]]:
        """Get daily play counts for all ads.

        Returns format for report generator: {"YYYY-MM-DD": {"Ad Name": count}}
        """
        with self._lock:
            plays = self._load_plays()
            result = {}

            start_dt = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
            end_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else None

            for ad_name, ad_plays in plays.items():
                for date_str, hours in ad_plays.items():
                    try:
                        # Convert MM-DD-YY to YYYY-MM-DD for report format
                        dt = datetime.strptime(date_str, "%m-%d-%y")

                        if start_dt and dt < start_dt:
                            continue
                        if end_dt and dt > end_dt:
                            continue

                        full_date = dt.strftime("%Y-%m-%d")

                        if full_date not in result:
                            result[full_date] = {}
                        result[full_date][ad_name] = len(hours)
                    except:
                        continue

            return result

    def get_hourly_confirmed_stats(self, start_date: str = None, end_date: str = None) -> Dict[str, Dict[str, int]]:
        """Get hourly play counts for all ads.

        Returns format: {"YYYY-MM-DD_HH": {"Ad Name": count}}
        """
        with self._lock:
            plays = self._load_plays()
            result = {}

            start_dt = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
            end_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else None

            for ad_name, ad_plays in plays.items():
                for date_str, hours in ad_plays.items():
                    try:
                        dt = datetime.strptime(date_str, "%m-%d-%y")

                        if start_dt and dt < start_dt:
                            continue
                        if end_dt and dt > end_dt:
                            continue

                        full_date = dt.strftime("%Y-%m-%d")

                        # Count plays per hour
                        from collections import Counter
                        hour_counts = Counter(hours)

                        for hour, count in hour_counts.items():
                            hour_key = f"{full_date}_{hour:02d}"
                            if hour_key not in result:
                                result[hour_key] = {}
                            result[hour_key][ad_name] = count
                    except:
                        continue

            return result

    def get_confirmed_ad_totals(self, start_date: str = None, end_date: str = None) -> Dict[str, int]:
        """Get total play counts per ad.

        Returns: {"Ad Name": total_count}
        """
        with self._lock:
            plays = self._load_plays()
            result = {}

            start_dt = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
            end_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else None

            for ad_name, ad_plays in plays.items():
                total = 0
                for date_str, hours in ad_plays.items():
                    try:
                        dt = datetime.strptime(date_str, "%m-%d-%y")

                        if start_dt and dt < start_dt:
                            continue
                        if end_dt and dt > end_dt:
                            continue

                        total += len(hours)
                    except:
                        continue

                if total > 0:
                    result[ad_name] = total

            return result
