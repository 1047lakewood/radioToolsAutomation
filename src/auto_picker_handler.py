"""
Auto Picker Handler - XML-triggered song selector with RadioBoss API integration.
Monitors an XML file and queues songs from two folders (A/B) with dynamic ratio logic.
"""

import logging
import os
import random
import time
import urllib.parse
import xml.etree.ElementTree as ET
from collections import deque
from datetime import datetime

try:
    import requests
except ImportError:
    requests = None

try:
    from mutagen import File as MutagenFile
except ImportError:
    MutagenFile = None

# Audio file extensions to search for
AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a", ".aiff", ".alac"}

# Pending song timeout - re-sync if pending song doesn't match within this time
PENDING_SONG_TIMEOUT = 300  # 5 minutes


class AutoPickerHandler:
    """Handles automatic song picking and queuing for a station via RadioBoss API."""

    def __init__(self, log_queue, config_manager, station_id='station_887'):
        self.log_queue = log_queue
        self.config_manager = config_manager
        self.station_id = station_id
        self.logger = logging.getLogger(f'AutoPicker_{station_id.split("_")[1]}')

        # Thread control
        self.running = False       # Thread loop running
        self.picking = False       # Actively picking songs

        # Picking state
        self.song_cycle_position = 0
        self.dynamic_a_remaining = 0
        self.recently_played = deque(maxlen=50)
        self.recently_played_artists = deque(maxlen=5)
        self.recently_played_artists_b = deque(maxlen=5)
        self.pending_song = None
        self.pending_song_time = 0
        self.was_stopped = False
        self.last_known_track = None
        self.last_trigger_time = 0
        self.scheduled_stop_active = False
        self.scheduled_stop_fired_date = None

        # Folder indexing
        self.folder_a_files = []
        self.folder_b_files = []
        self.indexing_in_progress = False

        # Poll interval
        self.poll_interval = 5  # seconds between XML checks
        self.last_xml_mtime = 0

        # Load config
        self._load_config()

    def _load_config(self):
        """Load configuration from config manager."""
        self.folder_a = self.config_manager.get_station_setting(
            self.station_id, 'auto_picker.folder_a', '')
        self.folder_b = self.config_manager.get_station_setting(
            self.station_id, 'auto_picker.folder_b', '')
        self.trigger_delay = self.config_manager.get_station_setting(
            self.station_id, 'auto_picker.trigger_delay_seconds', 3.0)
        self.sched_stop_enabled = self.config_manager.get_station_setting(
            self.station_id, 'auto_picker.scheduled_stop.enabled', False)
        self.sched_stop_day = self.config_manager.get_station_setting(
            self.station_id, 'auto_picker.scheduled_stop.day', 'Friday')
        self.sched_stop_time = self.config_manager.get_station_setting(
            self.station_id, 'auto_picker.scheduled_stop.time', '17:00')

        # Reuse 887 RadioBoss server/password and XML path
        self.xml_path = self.config_manager.get_xml_path(self.station_id)
        self.api_server = self.config_manager.get_radioboss_server(self.station_id)
        self.api_password = self.config_manager.get_radioboss_password(self.station_id)

    def reload_configuration(self):
        """Reload config from config manager (called by observer)."""
        self._load_config()
        self.logger.info("Configuration reloaded.")

    def run(self):
        """Main polling loop - runs as daemon thread."""
        self.running = True
        self.logger.info("Auto Picker thread started.")

        while self.running:
            try:
                if self.picking:
                    self._poll_xml()
                    self._check_scheduled_stop()
            except Exception as e:
                self.logger.error(f"Error in polling loop: {e}")

            time.sleep(self.poll_interval)

        self.logger.info("Auto Picker thread stopped.")

    def stop(self):
        """Stop the handler thread."""
        self.picking = False
        self.running = False

    def start_picking(self):
        """Start actively picking songs."""
        if not self.folder_a or not os.path.isdir(self.folder_a):
            self.logger.warning("Cannot start: Song Folder not configured or invalid.")
            return False
        if not self.folder_b or not os.path.isdir(self.folder_b):
            self.logger.warning("Cannot start: Shiur Folder not configured or invalid.")
            return False
        if not self.xml_path or not os.path.isfile(self.xml_path):
            self.logger.warning("Cannot start: XML file not configured or invalid.")
            return False

        self.picking = True
        self.pending_song = None
        self.was_stopped = False
        self.scheduled_stop_active = False
        self.last_xml_mtime = 0

        # Save was_running state
        self.config_manager.update_station_setting(
            self.station_id, 'auto_picker.was_running', True)
        self.config_manager.save_config(notify_observers=False)

        # Start background indexing
        self.reindex()

        self.logger.info("Auto Picker started.")

        # Bootstrap: check what's playing and queue
        current_track = self._get_current_track_filename()
        if current_track:
            self.logger.info("Track already playing, queuing next song.")
            self._submit_next_song()
        else:
            self.logger.info("Nothing playing, queuing two songs.")
            self._submit_next_song()
            self._submit_next_song()

        return True

    def stop_picking(self):
        """Stop picking songs."""
        self.picking = False
        self.pending_song = None
        self.scheduled_stop_active = False
        self.recently_played_artists.clear()
        self.recently_played_artists_b.clear()

        # Save was_running state
        self.config_manager.update_station_setting(
            self.station_id, 'auto_picker.was_running', False)
        self.config_manager.save_config(notify_observers=False)

        self.logger.info("Auto Picker stopped.")

    def test_pick(self):
        """Test picking a random song without sending to API."""
        if not self.folder_a_files and not self.folder_b_files:
            self.reindex()
            # Wait briefly for indexing
            time.sleep(1)

        song, folder = self._get_next_song()
        if song:
            song_name = os.path.basename(song)
            self.logger.info(f"[TEST] [{folder}] {song_name}")
        else:
            self.logger.warning("[TEST] No songs available to pick.")

    def reindex(self):
        """Rescan folders for audio files."""
        if self.indexing_in_progress:
            self.logger.warning("Indexing already in progress.")
            return

        self.indexing_in_progress = True
        self.logger.info("Indexing folders...")

        try:
            new_a = self._index_folder(self.folder_a) if self.folder_a else []
            new_b = self._index_folder(self.folder_b) if self.folder_b else []
            self.folder_a_files = new_a
            self.folder_b_files = new_b
            self.logger.info(f"Indexing complete: Songs={len(new_a)}, Shiurim={len(new_b)}")
        except Exception as e:
            self.logger.error(f"Indexing error: {e}")
        finally:
            self.indexing_in_progress = False

    def get_status(self):
        """Return current status dict for UI updates."""
        return {
            'running': self.picking,
            'next_cycle_text': self._get_cycle_text(),
            'folder_a_count': len(self.folder_a_files),
            'folder_b_count': len(self.folder_b_files),
        }

    # ==================== INTERNAL METHODS ====================

    def _poll_xml(self):
        """Check if XML file has changed since last poll."""
        if not self.xml_path or not os.path.isfile(self.xml_path):
            return

        try:
            current_mtime = os.path.getmtime(self.xml_path)
        except OSError:
            return

        if current_mtime != self.last_xml_mtime:
            self.last_xml_mtime = current_mtime
            self._on_xml_changed()

    def _on_xml_changed(self):
        """Called when XML file modification is detected."""
        current_time = time.time()
        if current_time - self.last_trigger_time < self.trigger_delay:
            return
        self.last_trigger_time = current_time

        # Check if pending song has been stale for too long
        if self.pending_song is not None and self.pending_song_time > 0:
            time_waiting = current_time - self.pending_song_time
            if time_waiting > PENDING_SONG_TIMEOUT:
                self.logger.warning(f"Pending song stale ({int(time_waiting)}s), re-syncing...")
                self._submit_next_song()
                return

        # If no pending song, bootstrap by submitting the first pick
        if self.pending_song is None:
            self._submit_next_song()
            return

        # Parse the XML to see what's currently playing
        current_filename = self._get_current_track_filename()
        self.last_known_track = current_filename

        if current_filename is None:
            if self.scheduled_stop_active:
                self.was_stopped = True
                return
            if self.pending_song is not None:
                # Track failed to play - auto-recover
                failed_name = os.path.basename(self.pending_song)
                self.logger.error(f"Track failed to play: {failed_name}, recovering...")
                self.pending_song = None
                self.was_stopped = False
                self._insert_and_play()
            else:
                self.was_stopped = True
            return

        # If we were stopped and now something is playing
        if self.was_stopped:
            self.was_stopped = False
            if self.scheduled_stop_active:
                self.scheduled_stop_active = False
                self.logger.info("Playback resumed after scheduled stop")
            else:
                song_name = os.path.basename(current_filename)
                self.logger.info(f"Resumed: {song_name}")
            self._submit_next_song()
            return

        # Check if the currently playing track matches what we submitted
        if current_filename == self.pending_song:
            song_name = os.path.basename(current_filename)
            self.logger.info(f"Now Playing: {song_name}")
            self._submit_next_song()

    def _submit_next_song(self):
        """Pick the next song, send to API, and store as pending."""
        if self.scheduled_stop_active:
            return

        song, folder = self._get_next_song()
        if song is None:
            self.pending_song = None
            return

        success = self._send_song_to_api(song)
        song_name = os.path.basename(song)

        if success:
            self.pending_song = self._normalize_path(song)
            self.pending_song_time = time.time()
            self.logger.info(f"[Queued] [{folder}] {song_name}")
        else:
            self.pending_song = None
            self.logger.error(f"[FAILED] [{folder}] {song_name}")

    def _get_next_song(self):
        """Get the next song based on dynamic A/B rotation."""
        if self.dynamic_a_remaining > 0:
            song = self._pick_random_song_from_folder(self.folder_a, self.folder_a_files, self.recently_played_artists)
            folder = "Song"
            if not song:
                self.logger.error("No songs found in Song Folder")
                return None, None
            self.dynamic_a_remaining -= 1
        else:
            song = self._pick_random_song_from_folder(self.folder_b, self.folder_b_files, self.recently_played_artists_b)
            folder = "Shiur"
            if not song:
                self.logger.error("No songs found in Shiur Folder")
                return None, None
            duration = self._get_song_duration(song)
            self.dynamic_a_remaining = self._duration_to_a_count(duration)
            dur_str = self._format_duration(duration)
            self.logger.info(f"  ({dur_str} \u2192 {self.dynamic_a_remaining}\u00d7 Song next)")

        self.recently_played.append(song)
        self.song_cycle_position += 1
        return song, folder

    def _get_cycle_text(self):
        """Return string showing dynamic cycle state like 'Next: [A] A B'."""
        if not self.picking:
            return "Stopped"

        remaining = self.dynamic_a_remaining
        parts = []
        for _ in range(remaining):
            parts.append("Song")
        parts.append("Shiur")
        if parts:
            parts[0] = f"[{parts[0]}]"
        return f"Next: {' '.join(parts)}"

    def _pick_random_song_from_folder(self, folder_path, file_list, artist_deque):
        """Pick a random song using indexed file list with dedup."""
        if not folder_path or not os.path.isdir(folder_path):
            return None

        if not file_list:
            return self._pick_random_song_walk(folder_path)

        # Filter out recently played songs
        candidates = [f for f in file_list if f not in self.recently_played]

        # Filter out recently played artists
        if artist_deque:
            artist_filtered = []
            for f in candidates:
                artist = self._get_artist_from_song(f)
                if artist is None or artist not in artist_deque:
                    artist_filtered.append(f)
            if artist_filtered:
                candidates = artist_filtered

        if not candidates:
            candidates = list(file_list)

        if candidates:
            for _ in range(10):
                if not candidates:
                    break
                selected = random.choice(candidates)
                if self._validate_audio_file(selected):
                    artist = self._get_artist_from_song(selected)
                    if artist:
                        artist_deque.append(artist)
                    return selected
                self.logger.warning(f"Skipping corrupt file: {os.path.basename(selected)}")
                candidates.remove(selected)

        return None

    def _pick_random_song_walk(self, folder_path):
        """Fallback: Pick a random song by randomly traversing the directory tree."""
        if not folder_path or not os.path.isdir(folder_path):
            return None

        for _ in range(50):
            current_dir = folder_path
            while True:
                try:
                    entries = os.listdir(current_dir)
                except (PermissionError, OSError):
                    break
                if not entries:
                    break

                dirs = []
                audio_files = []
                for entry in entries:
                    full_path = os.path.join(current_dir, entry)
                    if os.path.isdir(full_path):
                        dirs.append(full_path)
                    elif os.path.isfile(full_path):
                        ext = os.path.splitext(entry)[1].lower()
                        if ext in AUDIO_EXTENSIONS:
                            audio_files.append(full_path)

                if audio_files:
                    if not dirs or random.random() < 0.7:
                        candidates = [f for f in audio_files if f not in self.recently_played]
                        if candidates:
                            return random.choice(candidates)
                        break

                if dirs:
                    current_dir = random.choice(dirs)
                else:
                    break

        return None

    def _send_song_to_api(self, song_path, pos=-2):
        """Send the song path to the RadioBoss API endpoint."""
        if requests is None:
            self.logger.error("requests module not installed")
            return False

        try:
            encoded_path = urllib.parse.quote(song_path, safe='')
            server = self.api_server.rstrip('/')
            url = f"{server}/?pass={self.api_password}&action=inserttrack&filename={encoded_path}&pos={pos}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return True
            else:
                self.logger.error(f"API error {response.status_code}: {response.text[:80]}")
                return False
        except Exception as e:
            self.logger.error(f"API error: {str(e)[:100]}")
            return False

    def _insert_and_play(self):
        """Insert a track and start playback, then queue another."""
        try:
            song_path, folder = self._get_next_song()
            if not song_path:
                self.logger.error("No song available to insert")
                return

            if not self._send_song_to_api(song_path, pos=1):
                self.logger.error("Failed to insert track")
                return

            # Send play command
            server = self.api_server.rstrip('/')
            play_url = f"{server}/?pass={self.api_password}&cmd=play"
            try:
                response = requests.get(play_url, timeout=10)
                if response.status_code == 200:
                    self.logger.info("Playback started")
                else:
                    self.logger.error(f"Play command failed: {response.status_code}")
            except Exception as e:
                self.logger.error(f"Play command error: {e}")

            # Queue next track
            next_song, next_folder = self._get_next_song()
            if next_song:
                if self._send_song_to_api(next_song):
                    self.pending_song = self._normalize_path(next_song)
                    self.pending_song_time = time.time()
                    self.logger.info("Next track queued")
                else:
                    self.logger.error("Failed to queue next track")

        except Exception as e:
            self.logger.error(f"Insert and play error: {e}")

    def _check_scheduled_stop(self):
        """Check if the scheduled stop time has arrived."""
        if not self.picking or not self.sched_stop_enabled or self.scheduled_stop_active:
            return

        now = datetime.now()
        current_day = now.strftime("%A")
        today_date = now.date()

        if current_day == self.sched_stop_day and self.scheduled_stop_fired_date != today_date:
            try:
                target_h, target_m = self.sched_stop_time.split(":")
                target_h, target_m = int(target_h), int(target_m)
            except (ValueError, AttributeError):
                return

            if now.hour == target_h and now.minute == target_m:
                self.scheduled_stop_active = True
                self.scheduled_stop_fired_date = today_date
                self.pending_song = None

                # Send stop command to API
                try:
                    server = self.api_server.rstrip('/')
                    stop_url = f"{server}/?pass={self.api_password}&cmd=stop"
                    if requests is not None:
                        requests.get(stop_url, timeout=10)
                except Exception as e:
                    self.logger.error(f"Stop API error: {e}")

                self.logger.warning("Scheduled stop executed")

    def _get_current_track_filename(self):
        """Parse the XML file and return the normalized FILENAME of the current track."""
        if not self.xml_path:
            return None
        try:
            tree = ET.parse(self.xml_path)
            root = tree.getroot()
            player = root.find("PLAYER")
            if player is None:
                if root.tag == "PLAYER":
                    player = root
                else:
                    return None
            track = player.find("TRACK")
            if track is None:
                return None
            filename = track.get("FILENAME")
            if filename:
                return self._normalize_path(filename)
            return None
        except (ET.ParseError, OSError, IOError):
            return None

    def _index_folder(self, folder_path):
        """Recursively scan folder for all audio files."""
        files = []
        if not folder_path or not os.path.isdir(folder_path):
            return files

        for root, dirs, filenames in os.walk(folder_path):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            try:
                for filename in filenames:
                    ext = os.path.splitext(filename)[1].lower()
                    if ext in AUDIO_EXTENSIONS:
                        files.append(os.path.join(root, filename))
            except (PermissionError, OSError):
                continue

        return files

    def _get_artist_from_song(self, song_path):
        """Extract artist from audio file metadata."""
        if MutagenFile is None:
            return None
        try:
            audio = MutagenFile(song_path, easy=True)
            if audio and 'artist' in audio:
                return audio['artist'][0].strip().lower()
        except Exception:
            pass
        return None

    def _get_song_duration(self, song_path):
        """Get song duration in seconds."""
        if MutagenFile is None:
            return None
        try:
            audio = MutagenFile(song_path)
            if audio and audio.info:
                return audio.info.length
        except Exception:
            pass
        return None

    def _validate_audio_file(self, song_path):
        """Check if an audio file appears valid."""
        try:
            if os.path.getsize(song_path) == 0:
                return False
            if MutagenFile is not None:
                audio = MutagenFile(song_path)
                if audio is None:
                    return False
            return True
        except Exception:
            return False

    def _duration_to_a_count(self, duration_seconds):
        """Determine how many Song picks to play based on Shiur duration."""
        if duration_seconds is None:
            return 2
        if duration_seconds < 240:
            return 1
        elif duration_seconds <= 600:
            return 2
        else:
            return 3

    def _format_duration(self, seconds):
        """Format seconds as M:SS string."""
        if seconds is None:
            return "??:??"
        m = int(seconds) // 60
        s = int(seconds) % 60
        return f"{m}:{s:02d}"

    def _normalize_path(self, path):
        """Normalize a file path for comparison."""
        return os.path.normcase(os.path.normpath(path))
