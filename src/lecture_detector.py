"""
Lecture detector for radio automation.

Detects whether tracks are lectures based on artist names and configurable rules.
Uses robust XML reading to avoid caching issues.
"""

import xml.etree.ElementTree as ET
import logging
import os
from typing import Dict, Optional, Set, List, Any

# Try to import the new NowPlayingReader for robust XML reading
try:
    from nowplaying_reader import NowPlayingReader
    NOWPLAYING_READER_AVAILABLE = True
except ImportError:
    NOWPLAYING_READER_AVAILABLE = False


class LectureDetector:
    """Detects whether tracks are lectures based on artist names and configurable rules.
    
    This class analyzes XML track data to determine if the current playing track
    or the next upcoming track should be classified as a lecture.
    
    Methods:
        - is_current_track_lecture(): Check if the currently playing track is a lecture
        - is_next_track_lecture(): Check if the next upcoming track is a lecture
        - get_current_track_info(): Get artist and title of current track
        - get_current_track_duration(): Get duration of current track
        - get_next_track_duration(): Get duration of next track
        - has_next_track(): Check if there is a next track (False when playlist ends)
    """

    def __init__(self, xml_path: str, config_manager=None, station_id: Optional[str] = None,
                 blacklist: Optional[List[str]] = None, whitelist: Optional[List[str]] = None):
        """Initialize the LectureDetector.

        Args:
            xml_path: Path to the XML file containing track information
            config_manager: Configuration manager for blacklist/whitelist
            station_id: Station identifier for station-specific config
            blacklist: List of artists to never classify as lectures (overrides 'R' detection)
            whitelist: List of artists to always classify as lectures
        """
        self.xml_path = xml_path
        self.config_manager = config_manager
        self.station_id = station_id
        self.logger = logging.getLogger(__name__)
        
        # Initialize the robust XML reader if available
        if NOWPLAYING_READER_AVAILABLE:
            self._reader = NowPlayingReader(xml_path, self.logger)
        else:
            self._reader = None
        
        # Initialize blacklist and whitelist (case-insensitive) - shared across stations
        if config_manager:
            self.blacklist: Set[str] = set(x.lower() for x in config_manager.get_shared_blacklist())
            self.whitelist: Set[str] = set(x.lower() for x in config_manager.get_shared_whitelist())
        else:
            self.blacklist = set(x.lower() for x in blacklist) if blacklist else set()
            self.whitelist = set(x.lower() for x in whitelist) if whitelist else set()

    def is_current_track_lecture(self) -> bool:
        """Check if the currently playing track is a lecture.
        
        Returns:
            True if current track is a lecture, False otherwise
        """
        return self._is_track_lecture(['TRACK'])

    def is_next_track_lecture(self) -> bool:
        """Check if the next upcoming track is a lecture.
        
        Returns:
            True if next track is a lecture, False otherwise
        """
        return self._is_track_lecture(['NEXTTRACK', 'TRACK'])

    def _is_track_lecture(self, path_list: List[str]) -> bool:
        """Internal method to check if a track at the given XML path is a lecture.

        Args:
            path_list: List of XML tags to navigate to the track

        Returns:
            True if track is a lecture, False otherwise
        """
        try:
            # Use robust reader if available
            if self._reader:
                if path_list == ['TRACK']:
                    track = self._reader.get_current_track()
                elif path_list == ['NEXTTRACK', 'TRACK']:
                    track = self._reader.get_next_track()
                else:
                    track = None
                
                if track:
                    artist = track.get("artist", "")
                    return self._is_artist_lecture(artist)
                return False
            
            # Fallback to direct XML parsing
            root = self._read_xml_fresh()
            if root is None:
                return False
            
            artist = self._get_track_artist(root, path_list)
            return self._is_artist_lecture(artist)

        except ET.ParseError as e:
            self.logger.error(f"Error parsing XML file ({self.xml_path}): {e}")
            return False
        except Exception as e:
            self.logger.exception(f"Error while checking for lecture: {e}")
            return False

    def _read_xml_fresh(self) -> Optional[ET.Element]:
        """Read XML file with fresh content (no caching).
        
        Returns:
            XML root element or None on error
        """
        if not os.path.exists(self.xml_path):
            self.logger.warning(f"XML file not found: {self.xml_path}")
            return None

        try:
            # Touch file to help invalidate Windows file cache
            current_time = os.path.getmtime(self.xml_path)
            os.utime(self.xml_path, (current_time, current_time))
        except Exception:
            pass

        # Read content directly and parse from string (avoids ET.parse caching)
        with open(self.xml_path, 'r', encoding='utf-8') as f:
            content = f.read()

        return ET.fromstring(content)

    def _is_artist_lecture(self, artist: str) -> bool:
        """Determine if an artist should be classified as a lecture.
        
        Args:
            artist: The artist name to check
            
        Returns:
            True if artist represents a lecture, False otherwise
        """
        if not artist:
            return False

        artist_lower = artist.lower()

        # Blacklist takes precedence - never classify as lecture (overrides 'R' detection)
        if artist_lower in self.blacklist:
            return False

        # Whitelist - always classify as lecture
        if artist_lower in self.whitelist:
            return True

        # Check for lecture indicators (artist starts with 'r')
        if artist_lower.startswith('r'):
            return True

        return False

    def _get_track_artist(self, xml_root: ET.Element, path_list: List[str]) -> str:
        """Extract artist name from XML by following the specified path.
        
        Args:
            xml_root: The root XML element
            path_list: List of tag names to navigate
            
        Returns:
            The artist name (stripped) or empty string if not found
        """
        current_element = xml_root
        
        for tag in path_list:
            current_element = current_element.find(tag)
            if current_element is None:
                return ""
        
        artist = current_element.get("ARTIST", "")
        return artist.strip()

    def update_lists(self):
        """Updates the blacklist and whitelist from the config manager."""
        if self.config_manager:
            self.blacklist = set(x.lower() for x in self.config_manager.get_shared_blacklist())
            self.whitelist = set(x.lower() for x in self.config_manager.get_shared_whitelist())

    def force_refresh(self):
        """Force refresh the XML file reading to avoid caching issues."""
        if self._reader:
            self._reader.force_refresh()
        else:
            try:
                if os.path.exists(self.xml_path):
                    current_time = os.path.getmtime(self.xml_path)
                    os.utime(self.xml_path, (current_time, current_time))
                    self.logger.debug(f"Forced refresh of XML file: {self.xml_path}")
            except Exception as e:
                self.logger.warning(f"Could not force refresh XML file: {e}")

    def get_current_track_info(self) -> Dict[str, str]:
        """Returns the current track information from the XML file.
        
        Returns:
            Dict with 'artist' and 'title' keys
        """
        try:
            if self._reader:
                track = self._reader.get_current_track()
                if track:
                    return {
                        "artist": track.get("artist", ""),
                        "title": track.get("title", "")
                    }
                return {"artist": "", "title": ""}
            
            # Fallback
            root = self._read_xml_fresh()
            if root is None:
                return {"artist": "", "title": ""}
            
            current_track = root.find("TRACK")
            if current_track is not None:
                artist = current_track.get("ARTIST", "").strip()
                title = current_track.findtext("TITLE", "").strip()
                return {"artist": artist, "title": title}
            
            return {"artist": "", "title": ""}

        except Exception as e:
            self.logger.exception(f"Error getting current track info: {e}")
            return {"artist": "", "title": ""}

    def get_current_track_duration(self) -> str:
        """Returns the duration of the current track from the XML file.
        
        Returns:
            The duration as a string (e.g., '3:45') or empty string if not found
        """
        return self._get_track_duration(['TRACK'])

    def get_next_track_duration(self) -> str:
        """Returns the duration of the next track from the XML file.
        
        Returns:
            The duration as a string (e.g., '3:45') or empty string if not found
        """
        return self._get_track_duration(['NEXTTRACK', 'TRACK'])

    def has_next_track(self) -> bool:
        """Check if there is a next track in the playlist.
        
        When the playlist ends, the NEXTTRACK element is missing from the XML file.
        This method detects that condition.
        
        Returns:
            True if there is a next track, False if playlist has ended
        """
        try:
            if self._reader:
                return self._reader.has_next_track()
            
            # Fallback
            root = self._read_xml_fresh()
            if root is None:
                return False
            
            next_track_element = root.find('NEXTTRACK')
            
            if next_track_element is None:
                self.logger.debug("NEXTTRACK element not found - playlist has ended")
                return False
            
            self.logger.debug("NEXTTRACK element found - playlist continues")
            return True

        except Exception as e:
            self.logger.exception(f"Error checking for next track: {e}")
            return False

    def _get_track_duration(self, path_list: List[str]) -> str:
        """Internal method to extract duration from a track at the given XML path.
        
        Args:
            path_list: List of XML tags to navigate to the track
            
        Returns:
            The duration (stripped) or empty string if not found
        """
        try:
            if self._reader:
                if path_list == ['TRACK']:
                    track = self._reader.get_current_track()
                elif path_list == ['NEXTTRACK', 'TRACK']:
                    track = self._reader.get_next_track()
                else:
                    track = None
                
                if track:
                    return track.get("duration", "") or ""
                return ""
            
            # Fallback
            root = self._read_xml_fresh()
            if root is None:
                return ""
            
            current_element = root
            for tag in path_list:
                current_element = current_element.find(tag)
                if current_element is None:
                    return ""
            
            duration = current_element.get("DURATION", "").strip()
            return duration

        except Exception as e:
            self.logger.exception(f"Error getting track duration: {e}")
            return ""

    def get_current_artist(self) -> str:
        """Get just the current track's artist name.
        
        Returns:
            The artist name or empty string
        """
        info = self.get_current_track_info()
        return info.get("artist", "")

    def is_adroll_playing(self) -> bool:
        """Check if 'adRoll' is currently playing.
        
        Returns:
            True if current artist is 'adRoll' (case-insensitive)
        """
        artist = self.get_current_artist()
        return artist.lower() == "adroll" if artist else False


# Example usage
if __name__ == "__main__":
    from config_manager import ConfigManager
    
    config_manager = ConfigManager()
    detector = LectureDetector(
        xml_path=r"G:\To_RDS\nowplaying.xml",
        config_manager=config_manager
    )
    
    print("LECTURE DETECTOR - Track Analysis")
    print("=" * 50)
    
    # Get current track info for display
    track_info = detector.get_current_track_info()
    print(f"Current track: {track_info['artist']} - {track_info['title']}")
    print(f"Current duration: {detector.get_current_track_duration()}")
    print()
    
    # Check if CURRENT track is a lecture
    print("CURRENT TRACK Analysis:")
    if detector.is_current_track_lecture():
        print("  Currently playing track is a LECTURE")
    else:
        print("  Currently playing track is NOT a lecture")
    
    # Check if NEXT track is a lecture
    print("\nNEXT TRACK Analysis:")
    if detector.is_next_track_lecture():
        print("  Next upcoming track is a LECTURE")
    else:
        print("  Next upcoming track is NOT a lecture")
    
    print("\n" + "=" * 50)
    print("Summary:")
    print(f"  Current track is lecture: {detector.is_current_track_lecture()}")
    print(f"  Next track is lecture:    {detector.is_next_track_lecture()}")
    print(f"  Current track duration:   {detector.get_current_track_duration()}")
    print(f"  Next track duration:      {detector.get_next_track_duration()}")
    print(f"  Has next track:           {detector.has_next_track()}")
    print(f"  Is adRoll playing:        {detector.is_adroll_playing()}")
