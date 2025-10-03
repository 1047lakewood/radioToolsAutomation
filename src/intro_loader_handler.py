import os
import time
import xml.etree.ElementTree as ET
import shutil
import logging
import urllib.request
from datetime import datetime, timedelta
import random
import threading # Re-added threading
import sys
import re # Add missing import
import subprocess
import platform

# Get the specific logger for this handler
logger = logging.getLogger('IntroLoader')

# Attempt to import optional dependencies
try:
    from pydub import AudioSegment
    from pydub.utils import make_chunks
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    # Use the named logger
    logger.error("pydub library not found. MP3 concatenation will fail. Please install it (`pip install pydub`). Requires ffmpeg.")

def _configure_pydub_for_windows():
    """Configure pydub to hide subprocess windows on Windows."""
    if platform.system() == "Windows" and PYDUB_AVAILABLE:
        try:
            # Patch subprocess.Popen to hide windows for all subprocess calls
            import subprocess
            original_popen = subprocess.Popen
            
            class HiddenPopen(original_popen):
                def __init__(self, *args, **kwargs):
                    # Add Windows-specific flags to hide the window
                    if 'startupinfo' not in kwargs:
                        startupinfo = subprocess.STARTUPINFO()
                        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                        startupinfo.wShowWindow = subprocess.SW_HIDE
                        kwargs['startupinfo'] = startupinfo
                    
                    if 'creationflags' not in kwargs:
                        kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
                    
                    super().__init__(*args, **kwargs)
            
            # Replace subprocess.Popen with our hidden version
            subprocess.Popen = HiddenPopen
            
            logger.debug("Configured subprocess to hide CMD windows on Windows")
            
        except Exception as e:
            logger.warning(f"Failed to configure subprocess window hiding: {e}")
    else:
        logger.debug("Subprocess window hiding not needed (not Windows or pydub not available)")

try:
    import setproctitle
    SETPROCTITLE_AVAILABLE = True
except ImportError:
    SETPROCTITLE_AVAILABLE = False
# Use the named logger
# logger.warning("setproctitle library not found. Process title will not be set.") # Removed setproctitle


# --- Constants (Keep external paths as per user confirmation) ---
# XML_FILE_PATH = r"G:\To_RDS\nowplaying.xml"
# MP3_DIRECTORY = r"G:\Shiurim\introsCleanedUp"
# # Place log in the *original* location as per the script, can be changed later
# LOG_DIRECTORY = r"G:\Misc\Dev\CombinedRDSApp"
# MISSING_ARTIST_LOG = os.path.join(LOG_DIRECTORY, "missing_artists.log")

# Files within MP3_DIRECTORY
# CURRENT_ARTIST_FILE = os.path.join(MP3_DIRECTORY, "currentArtist.mp3")
# ACTUAL_CURRENT_ARTIST_FILE = os.path.join(MP3_DIRECTORY, "actualCurrentArtist.mp3")
# BLANK_MP3_FILE = os.path.join(MP3_DIRECTORY, "blank.mp3")
# SILENT_MP3_FILE = os.path.join(MP3_DIRECTORY, "near_silent.mp3") # Renamed from near_silent

# SCHEDULE_URL = "http://192.168.3.11:9000/?pass=bmas220&action=schedule&type=run&id=TBACFNBGJKOMETDYSQYR"
SCHEDULE_DELAY_MINUTES = 15
SCHEDULE_TIMEOUT = 10 # Seconds for URL request
MONITOR_LOOP_SLEEP = 2 # Seconds between XML checks
ERROR_RETRY_DELAY = 10 # Seconds after unexpected loop error
XML_READ_DELAY = 0.1 # Small delay before reading XML after modification detected
POST_UPDATE_DELAY = 40 # Seconds to wait after update before next check (as per original script)
MAX_LOG_LINES = 500 # Maximum number of lines to keep in the missing artists log

class IntroLoaderHandler:
    # Accept log_queue in init, though not directly used here (logger config handles it)
    def __init__(self, log_queue, config_manager):
        self.config_manager = config_manager
        self.running = False
        self.thread = None
        self.next_schedule_run = None
        self.last_modified_time = 0
        self.last_known_current_artist = None
        self.last_known_next_artist = None

        # Load configurable settings from config
        self.reload_configuration()

    def reload_configuration(self):
        """Reload configuration settings from config manager."""
        self.now_playing_xml = self.config_manager.get_setting("settings.intro_loader.now_playing_xml", r"G:\To_RDS\nowplaying.xml")
        self.mp3_directory = self.config_manager.get_setting("settings.intro_loader.mp3_directory", r"G:\Shiurim\introsCleanedUp")
        self.missing_artist_log = self.config_manager.get_setting("settings.intro_loader.missing_artists_log", r"G:\Misc\Dev\CombinedRDSApp\missing_artists.log")
        self.schedule_url = self.config_manager.get_setting("settings.intro_loader.schedule_url", "http://192.168.3.11:9000/?pass=bmas220&action=schedule&type=run&id=TBACFNBGJKOMETDYSQYR")
        self.current_artist_file = os.path.join(self.mp3_directory, "currentArtist.mp3")
        self.actual_current_artist_file = os.path.join(self.mp3_directory, "actualCurrentArtist.mp3")
        self.blank_mp3_file = os.path.join(self.mp3_directory, "blank.mp3")
        self.silent_mp3_file = os.path.join(self.mp3_directory, "near_silent.mp3")

        # Configure pydub to hide subprocess windows on Windows
        _configure_pydub_for_windows()

        # Keep setproctitle commented out/removed
        # if SETPROCTITLE_AVAILABLE:
        #     setproctitle.setproctitle("Intro Loader Handler")

        self._check_required_files()

    def _check_required_files(self):
        """Logs warnings if essential files are missing."""
        logger.debug("Checking required files...")
        if not os.path.exists(self.mp3_directory):
             logger.critical(f"MP3 directory does not exist: {self.mp3_directory}. Intro Loader cannot function.")
        if not os.path.exists(self.blank_mp3_file):
            logger.warning(f"Blank MP3 file not found: {self.blank_mp3_file}. Fallback for missing intros may fail.")
        if not os.path.exists(self.silent_mp3_file):
            logger.warning(f"Silent MP3 file not found: {self.silent_mp3_file}. Concatenation with silence will fail.")
        try:
            os.makedirs(os.path.dirname(self.missing_artist_log), exist_ok=True)
            logger.debug(f"Log directory ensured: {os.path.dirname(self.missing_artist_log)}")
        except Exception as e:
            logger.error(f"Failed to create log directory {os.path.dirname(self.missing_artist_log)}: {e}")


    def _log_missing_artist(self, artist_name, filename, is_current=True):
        """Log missing artist to the external log file."""
        should_log = is_current and artist_name and artist_name.upper().startswith('R')
        logger.debug(f"Checking missing artist log: Artist='{artist_name}', IsCurrent={is_current}, StartsWithR={should_log}")

        if not should_log:
            logger.debug("Skipping missing artist log entry.")
            return

        try:
            os.makedirs(os.path.dirname(self.missing_artist_log), exist_ok=True) # Ensure again just in case
            with open(self.missing_artist_log, 'a', encoding='utf-8') as f:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                log_entry = f"{timestamp} - Current Artist MP3 not found: '{artist_name}', Source FILENAME: '{filename}'\n"
                f.write(log_entry)
                logger.info(f"Logged missing artist to {self.missing_artist_log}: {artist_name}")

            # --- Log Truncation ---
            # Read all lines after appending
            with open(self.missing_artist_log, 'r', encoding='utf-8') as f_read:
                lines = f_read.readlines()

            # If log exceeds max lines, truncate and rewrite
            if len(lines) > MAX_LOG_LINES:
                logger.info(f"Missing artists log exceeds {MAX_LOG_LINES} lines. Truncating...")
                lines_to_keep = lines[-MAX_LOG_LINES:]
                with open(self.missing_artist_log, 'w', encoding='utf-8') as f_write:
                    f_write.writelines(lines_to_keep)
                logger.info(f"Missing artists log truncated to the latest {MAX_LOG_LINES} lines.")

        except Exception as e:
            logger.error(f"Error writing to or truncating missing artist log ({self.missing_artist_log}): {e}")

    def _get_artists_from_xml(self):
        """Extract current/next artists and filenames from XML."""
        logger.debug(f"Attempting to parse XML: {self.now_playing_xml}")
        try:
            time.sleep(XML_READ_DELAY) # Small delay before parsing
            tree = ET.parse(self.now_playing_xml)
            root = tree.getroot()
            logger.debug("XML parsed successfully.")

            current_track_elem = root.find("TRACK")
            current_artist, current_filename = None, None
            if current_track_elem is not None:
                current_artist = current_track_elem.attrib.get("ARTIST", "").strip() or None
                current_filename = current_track_elem.attrib.get("FILENAME", "").strip() or None
                logger.debug(f"Found Current Track: Artist='{current_artist}', Filename='{current_filename}'")
            else:
                 logger.debug("No 'TRACK' element found for current track.")


            next_track_elem = root.find("NEXTTRACK/TRACK")
            next_artist, next_filename = None, None
            if next_track_elem is not None:
                next_artist = next_track_elem.attrib.get("ARTIST", "").strip() or None
                next_filename = next_track_elem.attrib.get("FILENAME", "").strip() or None
                logger.debug(f"Found Next Track: Artist='{next_artist}', Filename='{next_filename}'")
            else:
                 logger.debug("No 'NEXTTRACK/TRACK' element found.")

            return (current_artist, current_filename), (next_artist, next_filename)
        except FileNotFoundError:
            logger.warning(f"XML file not found during parsing: {self.now_playing_xml}")
            return (None, None), (None, None)
        except ET.ParseError as e:
            logger.error(f"Error parsing XML ({self.now_playing_xml}): {e}. Check file.")
            return (None, None), (None, None)
        except Exception as e:
            logger.exception(f"Error reading/parsing XML: {e}")
            return (None, None), (None, None)

    def _concatenate_mp3_files(self, files, output_path):
        """Concatenate multiple MP3 files."""
        logger.debug(f"Attempting to concatenate {len(files)} files to {output_path}")
        if not PYDUB_AVAILABLE:
            logger.error("Cannot concatenate MP3s: pydub library not available.")
            return False
        try:
            if not files:
                logger.warning("Concatenate called with empty file list.")
                return False
            for file_path in files:
                if not os.path.exists(file_path):
                    logger.error(f"Concatenation failed: Input file not found: {file_path}")
                    return False
                logger.debug(f"Concatenation input file exists: {file_path}")

            combined = AudioSegment.empty()
            for file_path in files:
                logger.debug(f"Loading file for concatenation: {file_path}")
                try:
                    sound = AudioSegment.from_mp3(file_path)
                    combined += sound
                    logger.debug(f"Successfully loaded and added: {os.path.basename(file_path)}")
                except Exception as e_load:
                    logger.error(f"Error loading MP3 for concatenation ({os.path.basename(file_path)}): {e_load}")
                    return False

            logger.debug(f"Exporting combined MP3 to: {output_path}")
            combined.export(output_path, format="mp3")
            logger.debug(f"Successfully concatenated files to {os.path.basename(output_path)}")
            return True
        except Exception as e:
            logger.exception(f"Error concatenating MP3 files to {os.path.basename(output_path)}: {e}")
            return False

    def _update_artist_files(self, current_artist_info, next_artist_info, context="Processing"):
        """Update the currentArtist.mp3 and actualCurrentArtist.mp3 files."""
        logger.debug(f"--- Starting file update ({context}) ---")
        current_artist, current_filename = current_artist_info
        next_artist, next_filename = next_artist_info
        logger.debug(f"Current Artist: '{current_artist}', Next Artist: '{next_artist}'")

        # --- Handle actualCurrentArtist.mp3 (based on CURRENT artist) ---
        logger.debug("Processing actualCurrentArtist.mp3...")
        actual_success = False
        if current_artist:
            logger.debug(f"Searching for intro files starting with: '{current_artist}' in {self.mp3_directory}")
            try:
                matching_files = [f for f in os.listdir(self.mp3_directory)
                                  if f.lower().startswith(current_artist.lower()) and f.lower().endswith(".mp3")]
                logger.debug(f"Found {len(matching_files)} matching files: {matching_files}")
            except Exception as e:
                 logger.error(f"Error listing MP3 directory {self.mp3_directory}: {e}")
                 matching_files = []

            if matching_files:
                chosen_file = random.choice(matching_files)
                current_artist_file_path = os.path.join(self.mp3_directory, chosen_file)
                logger.info(f"{context}: Found current artist intro: {chosen_file}")
                try:
                    logger.debug(f"Copying '{current_artist_file_path}' to '{self.actual_current_artist_file}'")
                    shutil.copy2(current_artist_file_path, self.actual_current_artist_file)
                    logger.info(f"{context}: Copied {chosen_file} to actualCurrentArtist.mp3")
                    actual_success = True
                except Exception as e:
                    logger.error(f"Error copying {chosen_file} to actualCurrentArtist.mp3: {e}")
            else:
                # Updated log format
                logger.info(f"{context}: Didn't find {current_artist}.mp3")
                self._log_missing_artist(current_artist, current_filename, is_current=True)
                # Pass no_next_artist=False (default)
                actual_success = self._copy_blank_to_target(self.actual_current_artist_file, context, "actualCurrentArtist.mp3")
        else:
            logger.info(f"{context}: No current artist specified in XML.")
            if current_filename: self._log_missing_artist(current_artist, current_filename, is_current=True)
            # Pass no_next_artist=False (default)
            actual_success = self._copy_blank_to_target(self.actual_current_artist_file, context, "actualCurrentArtist.mp3")
        logger.debug(f"actualCurrentArtist.mp3 update success: {actual_success}")

        # --- Handle currentArtist.mp3 (based on NEXT artist + silence) ---
        logger.debug("Processing currentArtist.mp3...")
        next_success = False
        if next_artist:
            logger.debug(f"Searching for intro files starting with: '{next_artist}' in {self.mp3_directory}")
            try:
                matching_files = [f for f in os.listdir(self.mp3_directory)
                                  if f.lower().startswith(next_artist.lower()) and f.lower().endswith(".mp3")]
                logger.debug(f"Found {len(matching_files)} matching files: {matching_files}")
            except Exception as e:
                 logger.error(f"Error listing MP3 directory {self.mp3_directory}: {e}")
                 matching_files = []

            if matching_files:
                chosen_file = random.choice(matching_files)
                next_artist_file_path = os.path.join(self.mp3_directory, chosen_file)
                logger.info(f"{context}: Found next artist intro: {chosen_file}")

                if os.path.exists(self.silent_mp3_file):
                    logger.debug(f"Silent file found: {self.silent_mp3_file}. Attempting concatenation.")
                    concat_files = [self.silent_mp3_file, next_artist_file_path, self.silent_mp3_file]
                    concat_success = self._concatenate_mp3_files(concat_files, self.current_artist_file)
                    if concat_success:
                        logger.info(f"{context}: Copied SILENCE + {chosen_file} + SILENCE to currentArtist.mp3")
                        next_success = True
                    else:
                        logger.error(f"{context}: Concatenation failed for {chosen_file}, attempting blank copy.")
                        # Pass no_next_artist=False (default)
                        next_success = self._copy_blank_to_target(self.current_artist_file, context, "currentArtist.mp3 (concat fallback)")
                else:
                    logger.warning(f"{context}: Silent MP3 missing ({self.silent_mp3_file}), copying next artist directly.")
                    try:
                        logger.debug(f"Copying '{next_artist_file_path}' directly to '{self.current_artist_file}'")
                        shutil.copy2(next_artist_file_path, self.current_artist_file)
                        logger.info(f"{context}: Copied {chosen_file} directly to currentArtist.mp3")
                        next_success = True
                    except Exception as e:
                        logger.error(f"Error copying next artist file directly: {e}")
                        # Pass no_next_artist=False (default)
                        next_success = self._copy_blank_to_target(self.current_artist_file, context, "currentArtist.mp3 (direct copy fallback)")
            else:
                # Updated log format (though this specific message isn't in the target log, the action is)
                logger.info(f"{context}: Didn't find {next_artist}.mp3")
                # Pass no_next_artist=False (default)
                next_success = self._copy_blank_to_target(self.current_artist_file, context, "currentArtist.mp3")
        else:
            logger.info(f"{context}: No next artist specified in XML.")
            # Pass no_next_artist=True
            next_success = self._copy_blank_to_target(self.current_artist_file, context, "currentArtist.mp3", no_next_artist=True)
        logger.debug(f"currentArtist.mp3 update success: {next_success}")

        overall_success = actual_success and next_success
        logger.debug(f"--- File update ({context}) finished. Overall success: {overall_success} ---")
        return overall_success

    # Add no_next_artist parameter with a default value
    def _copy_blank_to_target(self, target_path, context, target_name_for_log, no_next_artist=False):
        """Copies the blank MP3 to the target path, logging appropriately."""
        logger.debug(f"Attempting to copy blank MP3 to {target_name_for_log}")
        if os.path.exists(self.blank_mp3_file):
            try:
                shutil.copy2(self.blank_mp3_file, target_path)
                # Modify log message based on no_next_artist flag
                log_suffix = " (no next artist)" if no_next_artist and target_name_for_log == "currentArtist.mp3" else ""
                logger.info(f"{context}: Copying {os.path.basename(self.blank_mp3_file)} to {target_name_for_log}{log_suffix}")
                return True
            except Exception as e:
                logger.error(f"Error copying blank MP3 to {target_name_for_log}: {e}")
                return False
        else:
            logger.error(f"Cannot copy blank MP3 to {target_name_for_log}: Source file {self.blank_mp3_file} not found.")
            try:
                logger.warning(f"Attempting to create empty file at {target_name_for_log} as fallback.")
                open(target_path, 'wb').close()
                logger.warning(f"Created empty file at {target_name_for_log} as blank MP3 was missing.")
                return False # Indicate it wasn't a successful blank copy
            except Exception as e_create:
                logger.error(f"Error creating empty file at {target_name_for_log}: {e_create}")
                return False

    def _run_schedule(self):
        """Run the schedule URL."""
        # Updated log format
        logger.info(f"Running schedule URL: {self.schedule_url}")
        try:
            with urllib.request.urlopen(self.schedule_url, timeout=SCHEDULE_TIMEOUT) as response:
                status = response.status
                logger.info(f"Schedule response status: {status}")
            return True
        except Exception as e:
            logger.error(f"Error running schedule: {e}")
            return False

    def _reset_schedule_timer(self):
        """Set the next schedule run time relative to now."""
        self.next_schedule_run = datetime.now() + timedelta(minutes=SCHEDULE_DELAY_MINUTES)
        logger.info(
            f"Schedule set to run next at: {self.next_schedule_run.strftime('%Y-%m-%d %H:%M:%S')}"
        )

    def _perform_initial_check(self):
        """Runs the check and update logic once at startup."""
        logger.info("Performing initial check of XML file...")
        if not os.path.exists(self.now_playing_xml):
            logger.warning(f"Initial check: XML file not found at {self.now_playing_xml}")
            return

        current_artist_info, next_artist_info = self._get_artists_from_xml()
        if current_artist_info == (None, None) and next_artist_info == (None, None) and not os.path.exists(self.now_playing_xml):
             # Avoid logging error if file genuinely doesn't exist yet
             logger.info("Initial check: XML file not found and parsing yielded no data.")
             return
        elif current_artist_info == (None, None) and next_artist_info == (None, None):
             logger.error("Initial check: Failed to read artist info from XML (file might be empty/invalid). Skipping initial update.")
             return


        current_artist_name = current_artist_info[0] if current_artist_info[0] else 'None'
        next_artist_name = next_artist_info[0] if next_artist_info[0] else 'None'
        logger.info(f"Initial check: Current artist='{current_artist_name}', Next artist='{next_artist_name}'")

        self._update_artist_files(current_artist_info, next_artist_info, context="Initial Update")
        # Update last known state after initial check
        self.last_known_current_artist = current_artist_info[0]
        self.last_known_next_artist = next_artist_info[0]
        logger.info("Initial check complete.")


    def run(self):
        """Monitors the XML file for changes and updates artist files."""
        self.running = True
        logger.info("--- Intro Loader Handler Started ---")
        logger.info(f"Monitoring XML: {self.now_playing_xml}")
        logger.info(f"Using MP3 Dir: {self.mp3_directory}")
        logger.info(f"Missing log: {self.missing_artist_log}")

        # Initialize last modified time
        try:
            if os.path.exists(self.now_playing_xml):
                self.last_modified_time = os.path.getmtime(self.now_playing_xml)
                logger.info(f"Initial XML mod time: {datetime.fromtimestamp(self.last_modified_time).strftime('%Y-%m-%d %H:%M:%S')} ({self.last_modified_time})")
            else:
                logger.warning(f"XML file {self.now_playing_xml} does not exist at start.")
                self.last_modified_time = 0 # Treat as non-existent
        except Exception as e:
             logger.error(f"Error getting initial mod time for {self.now_playing_xml}: {e}")
             self.last_modified_time = 0

        # Perform initial check/update outside the loop (already logs inside)
        self._perform_initial_check()

        # Initialize periodic schedule regardless of XML changes
        if self.next_schedule_run is None:
            self._reset_schedule_timer()

        logger.info("Starting XML monitor loop...")
        xml_was_missing = (self.last_modified_time == 0) # Track if we logged missing state

        while self.running:
            logger.debug(f"--- Loop Start (Running: {self.running}) ---")
            try:
                current_time_dt = datetime.now()
                logger.debug(f"Current time: {current_time_dt.strftime('%H:%M:%S')}")

                # --- Check XML Existence ---
                logger.debug(f"Checking existence of: {self.now_playing_xml}")
                xml_exists = os.path.exists(self.now_playing_xml)
                if not xml_exists:
                    if not xml_was_missing:
                        logger.warning(f"XML file {self.now_playing_xml} not found. Waiting...")
                        xml_was_missing = True
                    self.last_modified_time = 0 # Reset mod time while missing
                    logger.debug(f"XML missing, sleeping {MONITOR_LOOP_SLEEP * 2}s...")
                    time.sleep(MONITOR_LOOP_SLEEP * 2) # Wait longer if file is missing
                    continue
                elif xml_was_missing:
                    logger.info(f"XML file {self.now_playing_xml} found again. Resuming normal checks.")
                    xml_was_missing = False
                    # Get the new mod time immediately
                    try:
                        self.last_modified_time = os.path.getmtime(self.now_playing_xml)
                        logger.info(f"XML reappeared, new mod time: {datetime.fromtimestamp(self.last_modified_time).strftime('%H:%M:%S')} ({self.last_modified_time})")
                    except Exception as e:
                         logger.error(f"Error getting mod time after file reappeared: {e}")
                         self.last_modified_time = 0 # Reset if error
                    continue # Skip to next iteration to process normally

                # --- Check XML Modification Time ---
                logger.debug(f"Checking mod time for {self.now_playing_xml}. Last known: {self.last_modified_time}")
                try:
                    current_modified_time = os.path.getmtime(self.now_playing_xml)
                    logger.debug(f"Current mod time: {current_modified_time}")
                except FileNotFoundError:
                    # File disappeared between exists check and getmtime
                    if not xml_was_missing: # Log only once
                        logger.warning(f"XML file {self.now_playing_xml} disappeared during getmtime check. Waiting...")
                        xml_was_missing = True
                    self.last_modified_time = 0 # Reset mod time
                    logger.debug(f"XML disappeared (getmtime), sleeping {MONITOR_LOOP_SLEEP}s...")
                    time.sleep(MONITOR_LOOP_SLEEP)
                    continue
                except Exception as e:
                     logger.error(f"Error getting current mod time for {self.now_playing_xml}: {e}")
                     logger.debug(f"Error getting mod time, sleeping {MONITOR_LOOP_SLEEP}s...")
                     time.sleep(MONITOR_LOOP_SLEEP) # Wait before retrying
                     continue


                # --- Process XML Change ---
                if current_modified_time > self.last_modified_time:
                    logger.info(f"XML file modification detected! New: {current_modified_time}, Old: {self.last_modified_time}")

                    # Get artists *after* detecting change
                    logger.debug("Getting artists from XML...")
                    current_artist_info, next_artist_info = self._get_artists_from_xml()
                    logger.debug(f"Artists from XML: Current={current_artist_info}, Next={next_artist_info}")

                    # Check if artist data actually changed or if XML parsing was successful
                    current_artist = current_artist_info[0]
                    next_artist = next_artist_info[0]
                    # Check if parsing yielded *any* data, even if one artist is None
                    parsing_ok = current_artist is not None or next_artist is not None or \
                                 current_artist_info[1] is not None or next_artist_info[1] is not None
                    data_changed = (current_artist != self.last_known_current_artist or
                                    next_artist != self.last_known_next_artist)
                    logger.debug(f"Parsing OK: {parsing_ok}, Data Changed: {data_changed}")

                    # Update timestamp *before* potential delay/update
                    logger.debug(f"Updating last_modified_time to {current_modified_time}")
                    self.last_modified_time = current_modified_time # Update regardless of data change

                    if parsing_ok:
                        # Log if data actually changed and perform update
                        if data_changed:
                            current_artist_name = current_artist if current_artist else 'None'
                            next_artist_name = next_artist if next_artist else 'None'
                            logger.info(f"XML file changed, current artist is {current_artist_name}, next artist is {next_artist_name}")

                            # Wait before updating files (as per original script)
                            logger.debug(f"Waiting {POST_UPDATE_DELAY}s before updating files...")
                            time.sleep(POST_UPDATE_DELAY)

                            # Perform the update
                            logger.debug("Calling _update_artist_files...")
                            update_success = self._update_artist_files(current_artist_info, next_artist_info, context="Processing Update")
                            logger.debug(f"_update_artist_files success: {update_success}")

                            # Update last known state *after* successful processing attempt
                            logger.debug(f"Updating last known artists: Current='{current_artist}', Next='{next_artist}'")
                            self.last_known_current_artist = current_artist
                            self.last_known_next_artist = next_artist

                            if not update_success:
                                 logger.warning("File update process encountered errors.")
                        else:
                            logger.debug("XML modified, but artist data unchanged. Skipping file update.")

                        # Set schedule *after* processing the modification, regardless of data change
                        self._reset_schedule_timer()

                    else: # parsing not ok
                        logger.warning("XML modified, but failed to read artist info. Check XML content.")
                else:
                     logger.debug(f"No modification detected (Current: {current_modified_time} <= Last: {self.last_modified_time})")


                # --- Check Schedule ---
                if self.next_schedule_run and current_time_dt >= self.next_schedule_run:
                    logger.info("Scheduled time reached. Running schedule...")
                    self._run_schedule()
                    # Schedule the next run
                    self._reset_schedule_timer()
                elif self.next_schedule_run:
                    logger.debug(f"Schedule check: Not time yet (Next run: {self.next_schedule_run.strftime('%H:%M:%S')})")


                # --- Loop Sleep ---
                logger.debug(f"Loop end, sleeping {MONITOR_LOOP_SLEEP}s...")
                time.sleep(MONITOR_LOOP_SLEEP)

            except KeyboardInterrupt:
                logger.info("KeyboardInterrupt received in Intro Loader handler loop.")
                self.running = False
            except Exception as e:
                logger.exception("--- FATAL ERROR in Intro Loader handler loop ---")
                logger.info(f"Attempting to continue after {ERROR_RETRY_DELAY} second delay...")
                time.sleep(ERROR_RETRY_DELAY)

        logger.info("--- Intro Loader Handler Stopped ---")

    def start(self):
        """Starts the handler in a separate thread."""
        if not self.running:
            # Re-check essential files before starting thread
            if not os.path.exists(self.mp3_directory):
                 logger.critical(f"Cannot start Intro Loader: MP3 directory {self.mp3_directory} not found.")
                 return False # Indicate start failure

            self.running = True
            self.thread = threading.Thread(target=self.run, daemon=True, name="IntroLoaderThread") # Name thread
            self.thread.start()
            logger.info("Intro Loader handler thread started.")
            return True
        else:
            logger.warning("Intro Loader handler already running.")
            return False

    def stop(self):
        """Signals the handler thread to stop."""
        if self.running:
            logger.info("Stopping Intro Loader handler thread...")
            self.running = False
            # No need to join daemon thread, just remove reference
            self.thread = None
        else:
            logger.info("Intro Loader handler already stopped.")

    def touch_monitored_xml(self):
        """Updates the modification time of the monitored XML file to trigger a check."""
        logger.info(f"Debug action: Attempting to touch XML file: {self.now_playing_xml}")
        if not os.path.exists(self.now_playing_xml):
            logger.error(f"Cannot touch XML file: Not found at {self.now_playing_xml}")
            return False
        try:
            os.utime(self.now_playing_xml, None) # Update mod time to now
            logger.info(f"Successfully touched XML file: {self.now_playing_xml}")
            return True
        except Exception as e:
            logger.exception(f"Error touching XML file: {e}")
            return False

    def get_missing_artists(self):
        """Reads and parses the missing artists log file."""
        entries = []
        if not os.path.exists(self.missing_artist_log):
            logger.warning(f"Missing artists log file not found: {self.missing_artist_log}")
            return entries # Return empty list

        try:
            with open(self.missing_artist_log, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            for i, line in enumerate(lines):
                line = line.strip()
                if not line: continue

                # Try parsing the standard format first
                # Example: 2025-03-29 22:59:28 - Current Artist MP3 not found: 'Rav Yosef Greenwald', Source FILENAME: 'G:\...'
                # Updated regex to handle internal quotes using non-greedy matching (.*?)
                match = re.match(r"^(?P<ts>\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})\s+-\s+Current Artist MP3 not found:\s+'(?P<artist>.*?)',\s+Source FILENAME:\s+'(?P<path>.*?)'$", line)
                if match:
                    entries.append({
                        "id": i, # Use line number as a temporary ID
                        "timestamp": match.group('ts'),
                        "artist": match.group('artist'),
                        "filepath": match.group('path'),
                        "raw_line": line # Store original line for deletion
                    })
                else:
                    # Handle older format (assume it's just the message part)
                    # Example: Current Artist not found: 'Rav Forscheimer', FILENAME: 'G:\...'
                    # Updated regex to handle internal quotes using non-greedy matching (.*?)
                    match_old = re.match(r"^Current Artist MP3? not found:\s+'(?P<artist>.*?)',\s+(?:Source\s)?FILENAME:\s+'(?P<path>.*?)'$", line)
                    if match_old:
                         entries.append({
                            "id": i,
                            "timestamp": "N/A", # No timestamp in old format
                            "artist": match_old.group('artist'),
                            "filepath": match_old.group('path'),
                            "raw_line": line
                        })
                    else:
                         # Log lines that don't match expected formats
                         logger.warning(f"Could not parse line {i+1} in missing artists log: {line}")
                         # Optionally include unparseable lines with placeholder data
                         # entries.append({"id": i, "timestamp": "N/A", "artist": "Parse Error", "filepath": line, "raw_line": line})

            return entries
        except Exception as e:
             logger.exception(f"Error reading or parsing missing artists log: {e}")
             return [] # Return empty list on error

    def delete_missing_artist_entry(self, raw_lines_to_delete):
        """Removes specific lines from the missing artists log file."""
        if not isinstance(raw_lines_to_delete, list):
            # Handle case where a single string might still be passed (defensive)
            raw_lines_to_delete = [raw_lines_to_delete]
            logger.warning("delete_missing_artist_entry called with a single string, converting to list.")

        if not os.path.exists(self.missing_artist_log):
            logger.error("Cannot delete entries: Missing artists log file not found.")
            return False

        try:
            with open(self.missing_artist_log, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Create a set of lines to delete for efficient lookup
            lines_to_delete_set = {line.strip() for line in raw_lines_to_delete}

            # Create a new list excluding the lines to delete
            new_lines = [line for line in lines if line.strip() not in lines_to_delete_set]

            num_deleted = len(lines) - len(new_lines)

            if num_deleted == 0:
                logger.warning(f"Could not find any of the specified lines to delete in missing artists log.")
                # Consider returning True if the goal is achieved (lines are gone), or False if no action was taken.
                # Returning True seems more appropriate as the state matches the desired outcome.
                return True # Lines weren't found, but they are not in the file.

            # Write the modified content back
            with open(self.missing_artist_log, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)

            logger.info(f"Successfully deleted {num_deleted} entr{'y' if num_deleted == 1 else 'ies'} from missing artists log.")
            return True
        except Exception as e:
            logger.exception(f"Error deleting entries from missing artists log: {e}")
            return False


# Example usage (for testing)
if __name__ == "__main__":
    import re # Import re here for the test parsing
    import queue # Import queue for dummy queue
    # Use logger for test output too
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info("This script needs to be run as part of the main application.")
    # Example (Reverted to threaded execution):
    # import queue
    # import time
    # handler = IntroLoaderHandler(queue.Queue()) # Pass a dummy queue
    # handler.start()
    # try:
    #     # Keep main thread alive
    #     while True: time.sleep(1)
    # except KeyboardInterrupt:
    #     handler.stop()