import os
import logging
import urllib.request
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, List, Optional, Tuple

try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    PYDUB_AVAILABLE = False

try:
    from nowplaying_reader import NowPlayingReader
    NOWPLAYING_READER_AVAILABLE = True
except ImportError:
    NOWPLAYING_READER_AVAILABLE = False

# Logger will be set in __init__ based on station_id

# Configuration constants
XML_POLL_INTERVAL = 2  # seconds between XML checks
XML_POLL_TIMEOUT = 60  # max seconds to wait for XML confirmation
CONCAT_DURATION_TOLERANCE_MS = 500  # allowed deviation in ms for duration validation


class AdInserterService:
    """Combine enabled/scheduled ads into a single MP3 and trigger insertion.
    
    This service validates concatenation and confirms playback via XML before
    recording ad plays for accurate reporting.
    """

    def __init__(self, config_manager, station_id):
        """
        Initialize the AdInserterService.

        Args:
            config_manager: ConfigManager instance
            station_id: Station identifier (e.g., 'station_1047' or 'station_887')
        """
        self.config_manager = config_manager
        self.station_id = station_id

        # Set up logger based on station_id
        logger_name = f'AdService_{station_id.split("_")[1]}'  # e.g., 'AdService_1047'
        self.logger = logging.getLogger(logger_name)
        self.insertion_url = self.config_manager.get_ad_inserter_insertion_url(station_id)
        self.instant_url = self.config_manager.get_ad_inserter_instant_url(station_id)
        self.output_mp3 = self.config_manager.get_station_setting(
            station_id,
            "settings.ad_inserter.output_mp3",
            r"G:\\Ads\\newAd.mp3",
        )

        # Station ID settings for hour-start prepend
        self.station_id_enabled = self.config_manager.get_station_setting(
            station_id,
            "ad_inserter.station_id_enabled",
            False
        )
        self.station_id_file = self.config_manager.get_station_setting(
            station_id,
            "ad_inserter.station_id_file",
            ""
        )

        # Get XML path for confirmation
        self.xml_path = self.config_manager.get_xml_path(station_id)
        
        # Initialize robust XML reader if available
        if NOWPLAYING_READER_AVAILABLE:
            self._xml_reader = NowPlayingReader(self.xml_path, self.logger)
        else:
            self._xml_reader = None

        # Initialize ad play logger
        try:
            from ad_play_logger import AdPlayLogger
            self.ad_logger = AdPlayLogger(config_manager, station_id)
        except ImportError:
            self.logger.error("AdPlayLogger not available - ad play tracking disabled")
            self.ad_logger = None

        # Initialize lecture detector for playlist-end detection
        try:
            from lecture_detector import LectureDetector
            self.lecture_detector = LectureDetector(self.xml_path, config_manager, station_id)
            self.logger.debug("LectureDetector initialized for playlist-end detection")
        except ImportError:
            self.logger.warning("LectureDetector not available - playlist-end detection disabled")
            self.lecture_detector = None
        except Exception as e:
            self.logger.error(f"Error initializing LectureDetector: {e}")
            self.lecture_detector = None

    def run(self):
        """Combine ads and call the scheduled insertion URL with confirmation."""
        return self._run_with_confirmation(self.insertion_url, "scheduled")

    def run_instant(self, is_hour_start=False):
        """Combine ads and call the instant-play URL with confirmation.

        Args:
            is_hour_start: If True and station ID is enabled, prepend station ID audio
        """
        return self._run_with_confirmation(self.instant_url, "instant", is_hour_start=is_hour_start)

    def _seconds_until_hour_end(self) -> int:
        """
        Calculate seconds remaining until the end of the current hour.
        
        Used to set dynamic timeout for XML confirmation polling, since
        scheduled ads may not play until the end of the current song
        (which could be up to ~59 minutes away).
        
        Returns:
            int: Seconds until hour end, with a minimum of 60 seconds
        """
        now = datetime.now()
        hour_end = now.replace(minute=59, second=59, microsecond=999999)
        seconds_remaining = int((hour_end - now).total_seconds())
        # Ensure minimum timeout of 60 seconds for instant ads
        return max(seconds_remaining, 60)

    def _run_with_confirmation(self, url: str, mode: str, is_hour_start: bool = False) -> bool:
        """
        Execute the ad insertion workflow with validation and confirmation.

        Args:
            url: The insertion URL to call
            mode: 'scheduled' or 'instant' for logging
            is_hour_start: If True and station ID is enabled, prepend station ID audio

        Returns:
            bool: True if ads were confirmed as played, False otherwise
        """
        # Step 1: Select and validate ads
        ads_result = self._select_valid_ads()
        if not ads_result:
            return False

        valid_files, ad_names, expected_duration_ms = ads_result
        attempt_hour = datetime.now().hour

        # Determine if we should prepend station ID
        prepend_station_id = (
            is_hour_start and
            self.station_id_enabled and
            self.station_id_file and
            os.path.exists(self.station_id_file)
        )
        if is_hour_start:
            if prepend_station_id:
                self.logger.info(f"Hour start: will prepend station ID from {self.station_id_file}")
            elif not self.station_id_enabled:
                self.logger.debug("Hour start: station ID prepend disabled")
            elif not self.station_id_file:
                self.logger.debug("Hour start: no station ID file configured")
            elif not os.path.exists(self.station_id_file):
                self.logger.warning(f"Hour start: station ID file not found: {self.station_id_file}")

        self.logger.info(f"Starting {mode} ad insertion ({len(ad_names)} ads: {ad_names})")

        # Step 2: Concatenate MP3 files (with optional station ID prepend)
        concat_result = self._concatenate_and_validate(valid_files, expected_duration_ms, prepend_station_id=prepend_station_id)

        if not concat_result["ok"]:
            error_msg = concat_result.get('error', 'unknown')
            self.logger.error(f"Concatenation failed: {error_msg}")
            if self.ad_logger:
                self.ad_logger.log_failure(ad_names, f"concat:{error_msg[:20]}")
            return False

        self.logger.info(f"Concatenation successful: {concat_result['actual_ms']:.0f}ms (expected {concat_result['expected_ms']:.0f}ms)")

        # Step 3: Call insertion URL
        insertion_result = self._call_url_with_result(url)

        if not insertion_result["ok"]:
            error_msg = insertion_result.get('error', 'unknown')
            self.logger.error(f"Insertion URL call failed: {error_msg}")
            if self.ad_logger:
                self.ad_logger.log_failure(ad_names, f"http:{error_msg[:20]}")
            return False

        self.logger.info(f"Insertion URL called successfully (status={insertion_result.get('status_code')})")

        # Step 4: Poll XML for confirmation (skip for INSTANT ads - they play immediately)
        if mode == "instant":
            # For INSTANT ads, log as played immediately without polling
            # INSTANT ads are already in the playback queue, XML confirmation is unnecessary
            self.logger.info(f"INSTANT ad insertion successful - logging plays (XML polling skipped for immediate playback)")
            if self.ad_logger:
                for ad_name in ad_names:
                    self.ad_logger.log_play(ad_name)
            return True

        # For SCHEDULED ads, poll for XML confirmation
        timeout = self._seconds_until_hour_end()
        self.logger.info(f"Waiting for XML confirmation with timeout={timeout}s (SCHEDULED mode - until hour end)")
        confirmation = self._poll_for_xml_confirmation(attempt_hour, timeout=timeout)

        if confirmation["ok"]:
            self.logger.info(f"XML confirmation received: ARTIST='{confirmation['artist']}' at {confirmation.get('xml_started_at')}")

            # Log successful plays (ultra-compact storage)
            if self.ad_logger:
                for ad_name in ad_names:
                    self.ad_logger.log_play(ad_name)
            return True
        else:
            reason = confirmation.get('reason', 'unknown')
            self.logger.warning(f"XML confirmation failed: {reason}")
            if self.ad_logger:
                self.ad_logger.log_failure(ad_names, f"xml:{reason[:20]}")
            return False

    def _select_valid_ads(self) -> Optional[Tuple[List[str], List[str], float]]:
        """
        Select valid ads for insertion.
        
        Returns:
            Tuple of (file_paths, ad_names, expected_duration_ms) or None if no valid ads
        """
        # Safety check: Don't insert ads if playlist has ended
        if self.lecture_detector:
            try:
                has_next = self.lecture_detector.has_next_track()
                if not has_next:
                    self.logger.warning("Playlist has ended (no next track) - skipping ad insertion.")
                    return None
                self.logger.debug("Playlist continues - proceeding with ad insertion.")
            except Exception as e:
                self.logger.error(f"Error checking for next track: {e}")
                self.logger.warning("Unable to verify playlist status - proceeding with ad insertion.")
        
        ads = self.config_manager.get_station_ads(self.station_id) or []
        valid_files = []
        ad_names = []
        expected_duration_ms = 0.0
        now = datetime.now()
        
        for ad in ads:
            ad_name = ad.get("Name", "Unknown")
            
            if not ad.get("Enabled", True):
                self.logger.debug(f"Ad '{ad_name}' excluded: not enabled")
                continue
            if not self._is_scheduled(ad, now):
                self.logger.debug(f"Ad '{ad_name}' excluded: not scheduled for current time")
                continue
            mp3 = ad.get("MP3File")
            if not mp3 or not os.path.exists(mp3):
                self.logger.warning(f"Ad '{ad_name}' excluded: MP3 not found: {mp3}")
                continue
            
            # Calculate expected duration
            try:
                if PYDUB_AVAILABLE:
                    audio = AudioSegment.from_mp3(mp3)
                    expected_duration_ms += len(audio)
            except Exception as e:
                self.logger.warning(f"Could not get duration for '{ad_name}': {e}")
            
            self.logger.info(f"Ad '{ad_name}' included in roll")
            valid_files.append(mp3)
            ad_names.append(ad_name)

        if not valid_files:
            self.logger.info("No ads scheduled.")
            return None

        return (valid_files, ad_names, expected_duration_ms)

    def _is_scheduled(self, ad, now):
        ad_name = ad.get("Name", "Unknown")
        
        # If not scheduled, always play (when enabled)
        if not ad.get("Scheduled", False):
            self.logger.debug(f"Ad '{ad_name}': unscheduled, allowing at any time")
            return True
        
        # Check day schedule
        day_name = now.strftime("%A")
        days = ad.get("Days", [])
        if days and day_name not in days:
            self.logger.debug(f"Ad '{ad_name}': scheduled but not for {day_name} (only {days})")
            return False
        
        # Check hour schedule - prioritize Hours (list of ints) over legacy Times (list of dicts)
        hours = ad.get("Hours", [])
        
        if hours:
            # New format: Hours is a list of integers [0, 1, 2, ..., 23]
            if now.hour in hours:
                self.logger.debug(f"Ad '{ad_name}': scheduled and current hour {now.hour} is in Hours list")
                return True
            else:
                self.logger.debug(f"Ad '{ad_name}': scheduled but hour {now.hour} not in Hours list {hours}")
                return False
        
        # Fallback to legacy Times format for backward compatibility
        times = ad.get("Times", [])
        if times:
            hour_match = False
            for t in times:
                if isinstance(t, dict) and "hour" in t:
                    try:
                        if int(t.get("hour")) == now.hour:
                            hour_match = True
                            break
                    except (ValueError, TypeError):
                        continue
            if hour_match:
                self.logger.debug(f"Ad '{ad_name}': scheduled and current hour {now.hour} matches Times (legacy)")
                return True
            else:
                self.logger.debug(f"Ad '{ad_name}': scheduled but hour {now.hour} not in Times list")
                return False
        
        # If scheduled but no hours/times specified, allow at any time
        self.logger.debug(f"Ad '{ad_name}': scheduled with no specific hours, allowing")
        return True

    def _concatenate_and_validate(self, files: List[str], expected_duration_ms: float, prepend_station_id: bool = False) -> Dict:
        """
        Concatenate MP3 files and validate the output.

        Args:
            files: List of MP3 file paths
            expected_duration_ms: Expected total duration in milliseconds
            prepend_station_id: If True, prepend station ID audio at the beginning

        Returns:
            Dict with 'ok', 'expected_ms', 'actual_ms', and optionally 'error'
        """
        result = {
            "ok": False,
            "expected_ms": expected_duration_ms,
            "actual_ms": 0
        }

        if not PYDUB_AVAILABLE:
            result["error"] = "pydub not available"
            self.logger.error("pydub not available - cannot concatenate MP3 files")
            return result

        try:
            # Create output directory if needed
            os.makedirs(os.path.dirname(self.output_mp3), exist_ok=True)

            # Start with station ID if requested
            combined = AudioSegment.empty()
            if prepend_station_id and self.station_id_file and os.path.exists(self.station_id_file):
                try:
                    station_id_audio = AudioSegment.from_mp3(self.station_id_file)
                    combined += station_id_audio
                    # Update expected duration to include station ID
                    expected_duration_ms += len(station_id_audio)
                    result["expected_ms"] = expected_duration_ms
                    self.logger.info(f"Prepended station ID audio ({len(station_id_audio)}ms)")
                except Exception as e:
                    self.logger.error(f"Failed to load station ID file: {e}")
                    result["error"] = f"Station ID file error: {e}"
                    return result

            # Concatenate ad files
            for fp in files:
                if not os.path.exists(fp):
                    result["error"] = f"File not found: {fp}"
                    self.logger.error(result["error"])
                    return result
                combined += AudioSegment.from_mp3(fp)

            # Export with adRoll artist tag
            combined.export(self.output_mp3, format="mp3", tags={"artist": "adRoll"})
            
            # Validate output exists
            if not os.path.exists(self.output_mp3):
                result["error"] = "Output file not created"
                return result
            
            # Validate output is readable and get actual duration
            try:
                output_audio = AudioSegment.from_mp3(self.output_mp3)
                result["actual_ms"] = len(output_audio)
            except Exception as e:
                result["error"] = f"Output file not readable: {e}"
                return result
            
            # Validate duration is within tolerance
            duration_diff = abs(result["actual_ms"] - expected_duration_ms)
            if duration_diff > CONCAT_DURATION_TOLERANCE_MS:
                result["error"] = f"Duration mismatch: expected {expected_duration_ms}ms, got {result['actual_ms']}ms"
                self.logger.warning(result["error"])
                # Still mark as OK if file is readable - duration may vary due to encoding
            
            result["ok"] = True
            return result
            
        except Exception as e:
            result["error"] = str(e)
            self.logger.exception(f"Error concatenating ads: {e}")
            return result

    def _call_url_with_result(self, url: str) -> Dict:
        """
        Call the insertion URL and return detailed result.
        
        Args:
            url: The URL to call
            
        Returns:
            Dict with 'ok', 'status_code', and optionally 'error'
        """
        result = {"ok": False}
        
        self.logger.info(f"Calling ad service URL: {url}")
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                result["status_code"] = resp.status
                result["ok"] = (200 <= resp.status < 300)
                self.logger.info(f"Ad service response: {resp.status}")
        except Exception as e:
            result["error"] = str(e)
            self.logger.error(f"Failed to call ad service URL: {e}")
        
        return result

    def _poll_for_xml_confirmation(self, attempt_hour: int, timeout: int = None) -> Dict:
        """
        Poll the nowplaying XML for ARTIST=="adRoll" confirmation.
        
        Uses the robust NowPlayingReader if available for reliable detection.
        
        Args:
            attempt_hour: The hour when the insertion was attempted
            timeout: Custom timeout in seconds (defaults to XML_POLL_TIMEOUT if not specified)
            
        Returns:
            Dict with 'ok', 'artist', 'xml_started_at', and optionally 'reason'
        """
        # Use default timeout if not specified
        if timeout is None:
            timeout = XML_POLL_TIMEOUT
        
        # Use robust reader if available
        if self._xml_reader:
            self.logger.info(f"Polling XML for adRoll confirmation using NowPlayingReader (timeout={timeout}s)...")
            result = self._xml_reader.wait_for_artist(
                target_artist="adRoll",
                timeout=timeout,
                poll_interval=XML_POLL_INTERVAL,
                same_hour_required=False,  # We handle this ourselves
                attempt_hour=attempt_hour
            )
            
            if result.get("ok"):
                self.logger.info(f"XML confirmation received: ARTIST='{result['artist']}' at {result.get('started_at')}")
            else:
                self.logger.warning(f"XML confirmation failed: {result.get('reason', 'unknown')}")
            
            return result
        
        # Fallback to manual polling
        result = {"ok": False}
        
        self.logger.info(f"Polling XML for adRoll confirmation (timeout={timeout}s)...")
        
        start_time = time.time()
        last_artist = None
        
        while (time.time() - start_time) < timeout:
            try:
                xml_info = self._read_xml_track_info()
                
                if xml_info:
                    artist = xml_info.get("artist", "")
                    started_at = xml_info.get("started_at")
                    
                    # Log when artist changes
                    if artist != last_artist:
                        self.logger.debug(f"XML artist: '{artist}' (started: {started_at})")
                        last_artist = artist
                    
                    # Check if it's adRoll (case-insensitive)
                    if artist.lower() == "adroll":
                        # Verify it's in the same hour as the attempt
                        current_hour = datetime.now().hour
                        if current_hour == attempt_hour:
                            result["ok"] = True
                            result["artist"] = artist
                            result["xml_started_at"] = started_at
                            result["same_hour"] = True
                            return result
                        else:
                            # Still confirm but note the hour mismatch
                            self.logger.warning(f"adRoll found but hour changed ({attempt_hour} -> {current_hour})")
                            result["ok"] = True
                            result["artist"] = artist
                            result["xml_started_at"] = started_at
                            result["same_hour"] = False
                            return result
                
            except Exception as e:
                self.logger.debug(f"Error reading XML during poll: {e}")
            
            time.sleep(XML_POLL_INTERVAL)
        
        result["reason"] = "timeout"
        result["last_artist"] = last_artist
        self.logger.warning(f"XML confirmation timeout after {timeout}s (last artist: {last_artist})")
        return result

    def _read_xml_track_info(self) -> Optional[Dict]:
        """
        Read current track info from the nowplaying XML file.
        
        Uses fresh file reading to avoid caching issues.
        
        Returns:
            Dict with 'artist', 'title', 'started_at' or None on error
        """
        if not os.path.exists(self.xml_path):
            return None
        
        try:
            # Force fresh read by reading content directly
            with open(self.xml_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            root = ET.fromstring(content)
            track = root.find("TRACK")
            
            if track is not None:
                return {
                    "artist": (track.get("ARTIST") or "").strip(),
                    "title": (track.findtext("TITLE") or "").strip(),
                    "started_at": track.get("STARTED")
                }
        except ET.ParseError as e:
            self.logger.debug(f"XML parse error: {e}")
        except Exception as e:
            self.logger.debug(f"Error reading XML: {e}")
        
        return None

    # =========================================================================
    # Legacy methods (kept for backward compatibility but deprecated)
    # =========================================================================

    def _combine_ads(self):
        """DEPRECATED: Use _run_with_confirmation instead."""
        # Safety check: Don't insert ads if playlist has ended
        if self.lecture_detector:
            try:
                has_next = self.lecture_detector.has_next_track()
                if not has_next:
                    self.logger.warning("Playlist has ended (no next track) - skipping ad insertion.")
                    return False
                self.logger.debug("Playlist continues - proceeding with ad insertion.")
            except Exception as e:
                self.logger.error(f"Error checking for next track: {e}")
                self.logger.warning("Unable to verify playlist status - proceeding with ad insertion.")
        
        ads = self.config_manager.get_station_ads(self.station_id) or []
        valid_files = []
        now = datetime.now()
        for ad in ads:
            ad_name = ad.get("Name", "Unknown")
            
            if not ad.get("Enabled", True):
                self.logger.debug(f"Ad '{ad_name}' excluded: not enabled")
                continue
            if not self._is_scheduled(ad, now):
                self.logger.debug(f"Ad '{ad_name}' excluded: not scheduled for current time")
                continue
            mp3 = ad.get("MP3File")
            if not mp3 or not os.path.exists(mp3):
                self.logger.warning(f"Ad '{ad_name}' excluded: MP3 not found: {mp3}")
                continue
            
            self.logger.info(f"Ad '{ad_name}' included in roll")
            valid_files.append(mp3)

        if not valid_files:
            self.logger.info("No ads scheduled.")
            return False

        os.makedirs(os.path.dirname(self.output_mp3), exist_ok=True)
        return self._concatenate_mp3_files(valid_files, self.output_mp3)

    def _concatenate_mp3_files(self, files, output_path):
        """DEPRECATED: Use _concatenate_and_validate instead."""
        self.logger.debug(f"Concatenating {len(files)} files to {output_path}")
        if not PYDUB_AVAILABLE:
            self.logger.error("pydub not available - cannot concatenate MP3 files")
            return False
        try:
            combined = AudioSegment.empty()
            for fp in files:
                if not os.path.exists(fp):
                    self.logger.error(f"File not found: {fp}")
                    return False
                combined += AudioSegment.from_mp3(fp)
            combined.export(output_path, format="mp3", tags={"artist": "adRoll"})
            return True
        except Exception as e:
            self.logger.exception(f"Error concatenating ads: {e}")
            return False

    def _call_url(self, url):
        """DEPRECATED: Use _call_url_with_result instead."""
        self.logger.info(f"Calling ad service URL: {url}")
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                self.logger.info(f"Ad service response: {resp.status}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to call ad service URL: {e}")
            return False

    def _log_ad_plays(self, ad_names):
        """DEPRECATED: Ad plays are now logged via confirmation flow."""
        # This method is no longer used - plays are recorded through confirm_roll_playback
        pass
