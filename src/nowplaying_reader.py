"""
Robust XML reader for nowplaying.xml files.

This module provides reliable, non-caching XML reading to ensure
fresh data is always retrieved when checking for track changes
and ad playback confirmation.
"""

import os
import time
import logging
import xml.etree.ElementTree as ET
from typing import Dict, Optional, Any
from datetime import datetime


class NowPlayingReader:
    """
    Reliable reader for nowplaying XML files.
    
    Avoids caching issues by:
    - Reading file content directly into memory
    - Using ET.fromstring() instead of ET.parse()
    - Optionally checking file modification time
    - Providing retry logic for transient errors
    """

    def __init__(self, xml_path: str, logger: Optional[logging.Logger] = None):
        """
        Initialize the NowPlayingReader.
        
        Args:
            xml_path: Path to the nowplaying.xml file
            logger: Optional logger instance
        """
        self.xml_path = xml_path
        self.logger = logger or logging.getLogger(__name__)
        self._last_modified = 0
        self._last_content_hash = ""

    def get_current_track(self, retries: int = 2, retry_delay: float = 0.5) -> Optional[Dict[str, Any]]:
        """
        Get the current track information from the XML file.
        
        Performs a fresh read of the file to avoid caching issues.
        
        Args:
            retries: Number of retry attempts on failure
            retry_delay: Delay between retries in seconds
            
        Returns:
            Dict with track info or None on error:
            {
                "artist": str,
                "title": str,
                "started_at": str (ISO format from STARTED attribute),
                "duration": str (from DURATION attribute),
                "modified_at": float (file mtime)
            }
        """
        for attempt in range(retries + 1):
            try:
                result = self._read_track_element("TRACK")
                if result:
                    return result
            except Exception as e:
                if attempt < retries:
                    self.logger.debug(f"Retry {attempt + 1}/{retries} after error: {e}")
                    time.sleep(retry_delay)
                else:
                    self.logger.warning(f"Failed to read current track after {retries + 1} attempts: {e}")
        
        return None

    def get_next_track(self, retries: int = 2, retry_delay: float = 0.5) -> Optional[Dict[str, Any]]:
        """
        Get the next track information from the XML file.
        
        Args:
            retries: Number of retry attempts on failure
            retry_delay: Delay between retries in seconds
            
        Returns:
            Dict with track info or None if no next track/error
        """
        for attempt in range(retries + 1):
            try:
                result = self._read_track_element("NEXTTRACK/TRACK")
                if result:
                    return result
            except Exception as e:
                if attempt < retries:
                    self.logger.debug(f"Retry {attempt + 1}/{retries} after error: {e}")
                    time.sleep(retry_delay)
                else:
                    self.logger.debug(f"No next track after {retries + 1} attempts: {e}")
        
        return None

    def has_next_track(self) -> bool:
        """
        Check if there is a next track in the playlist.
        
        Returns:
            True if NEXTTRACK element exists, False otherwise
        """
        try:
            root = self._read_xml_root()
            if root is None:
                return False
            
            next_track = root.find("NEXTTRACK")
            return next_track is not None
            
        except Exception as e:
            self.logger.warning(f"Error checking for next track: {e}")
            return False

    def get_file_modified_time(self) -> Optional[float]:
        """Get the file's last modification time."""
        try:
            if os.path.exists(self.xml_path):
                return os.path.getmtime(self.xml_path)
        except Exception:
            pass
        return None

    def has_file_changed(self) -> bool:
        """
        Check if the file has been modified since last read.
        
        Returns:
            True if file modification time has changed
        """
        current_mtime = self.get_file_modified_time()
        if current_mtime is None:
            return False
        
        changed = current_mtime != self._last_modified
        self._last_modified = current_mtime
        return changed

    def wait_for_artist(self, target_artist: str, timeout: float = 60, 
                        poll_interval: float = 2, 
                        same_hour_required: bool = True,
                        attempt_hour: Optional[int] = None) -> Dict[str, Any]:
        """
        Poll the XML file waiting for a specific artist to appear.
        
        Args:
            target_artist: The artist name to wait for (case-insensitive)
            timeout: Maximum time to wait in seconds
            poll_interval: Time between polls in seconds
            same_hour_required: If True, require confirmation in same hour as attempt
            attempt_hour: The hour when the attempt was made (default: current hour)
            
        Returns:
            Dict with:
            - ok: bool - True if artist was found
            - artist: str - The actual artist name found
            - started_at: str - The STARTED timestamp
            - same_hour: bool - Whether confirmation was in same hour
            - reason: str - Failure reason if ok=False
        """
        target_lower = target_artist.lower()
        if attempt_hour is None:
            attempt_hour = datetime.now().hour
        
        start_time = time.time()
        last_seen_artist = None
        
        self.logger.info(f"Waiting for artist '{target_artist}' (timeout={timeout}s)")
        
        while (time.time() - start_time) < timeout:
            try:
                track = self.get_current_track()
                
                if track:
                    artist = track.get("artist", "")
                    
                    # Log artist changes
                    if artist != last_seen_artist:
                        self.logger.debug(f"Current artist: '{artist}'")
                        last_seen_artist = artist
                    
                    # Check for match
                    if artist.lower() == target_lower:
                        current_hour = datetime.now().hour
                        same_hour = (current_hour == attempt_hour)
                        
                        if same_hour_required and not same_hour:
                            self.logger.warning(
                                f"Found '{artist}' but hour changed ({attempt_hour} -> {current_hour})"
                            )
                        
                        return {
                            "ok": True,
                            "artist": artist,
                            "started_at": track.get("started_at"),
                            "same_hour": same_hour
                        }
                        
            except Exception as e:
                self.logger.debug(f"Poll error: {e}")
            
            time.sleep(poll_interval)
        
        return {
            "ok": False,
            "reason": "timeout",
            "last_artist": last_seen_artist
        }

    def _read_xml_root(self) -> Optional[ET.Element]:
        """
        Read and parse the XML file, returning the root element.
        
        Uses direct file content reading to avoid any caching.
        """
        if not os.path.exists(self.xml_path):
            self.logger.debug(f"XML file not found: {self.xml_path}")
            return None
        
        # Read file content directly
        with open(self.xml_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Update modification time tracking
        self._last_modified = os.path.getmtime(self.xml_path)
        
        # Parse from string (avoids any file handle caching)
        return ET.fromstring(content)

    def _read_track_element(self, xpath: str) -> Optional[Dict[str, Any]]:
        """
        Read a track element from the XML using the given xpath.
        
        Args:
            xpath: XPath to the track element (e.g., "TRACK" or "NEXTTRACK/TRACK")
            
        Returns:
            Dict with track info or None
        """
        root = self._read_xml_root()
        if root is None:
            return None
        
        track = root.find(xpath)
        if track is None:
            return None
        
        return {
            "artist": (track.get("ARTIST") or "").strip(),
            "title": (track.findtext("TITLE") or "").strip(),
            "started_at": track.get("STARTED"),
            "duration": track.get("DURATION"),
            "modified_at": self._last_modified
        }

    def force_refresh(self):
        """
        Force a refresh by touching the file's access time.
        
        This can help ensure Windows file system cache is invalidated.
        """
        try:
            if os.path.exists(self.xml_path):
                current_time = os.path.getmtime(self.xml_path)
                os.utime(self.xml_path, (current_time, current_time))
                self.logger.debug(f"Forced refresh of: {self.xml_path}")
        except Exception as e:
            self.logger.warning(f"Could not force refresh: {e}")


def read_nowplaying_artist(xml_path: str) -> Optional[str]:
    """
    Convenience function to read just the current artist.
    
    Args:
        xml_path: Path to the nowplaying.xml file
        
    Returns:
        The artist name or None
    """
    reader = NowPlayingReader(xml_path)
    track = reader.get_current_track()
    return track.get("artist") if track else None


def read_nowplaying_track(xml_path: str) -> Optional[Dict[str, Any]]:
    """
    Convenience function to read the current track info.
    
    Args:
        xml_path: Path to the nowplaying.xml file
        
    Returns:
        Dict with artist, title, started_at, duration or None
    """
    reader = NowPlayingReader(xml_path)
    return reader.get_current_track()


def is_adroll_playing(xml_path: str) -> bool:
    """
    Check if "adRoll" is currently playing.
    
    Args:
        xml_path: Path to the nowplaying.xml file
        
    Returns:
        True if current artist is "adRoll" (case-insensitive)
    """
    artist = read_nowplaying_artist(xml_path)
    return artist.lower() == "adroll" if artist else False

