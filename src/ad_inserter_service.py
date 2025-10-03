import os
import logging
import urllib.request
from datetime import datetime

try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    PYDUB_AVAILABLE = False

logger = logging.getLogger('AdService')

class AdInserterService:
    """Combine enabled/scheduled ads into a single MP3 and trigger insertion."""

    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.insertion_url = self.config_manager.get_setting(
            "settings.ad_inserter.insertion_url",
            "http://localhost:8000/insert",
        )
        self.instant_url = self.config_manager.get_setting(
            "settings.ad_inserter.instant_url",
            "http://localhost:8000/play",
        )
        self.output_mp3 = self.config_manager.get_setting(
            "settings.ad_inserter.output_mp3",
            r"G:\\Ads\\newAd.mp3",
        )

        # Initialize ad play logger
        try:
            from ad_play_logger import AdPlayLogger
            self.ad_logger = AdPlayLogger(config_manager)
        except ImportError:
            logger.error("AdPlayLogger not available - ad play tracking disabled")
            self.ad_logger = None

    def run(self):
        """Combine ads and call the scheduled insertion URL."""
        if self._combine_ads():
            return self._call_url(self.insertion_url)
        return False

    def run_instant(self):
        """Combine ads and call the instant-play URL."""
        if self._combine_ads():
            return self._call_url(self.instant_url)
        return False

    def _combine_ads(self):
        ads = self.config_manager.get_ads() or []
        valid_files = []
        now = datetime.now()
        for ad in ads:
            if not ad.get("Enabled", True):
                continue
            if not self._is_scheduled(ad, now):
                continue
            mp3 = ad.get("MP3File")
            if not mp3 or not os.path.exists(mp3):
                logger.warning(f"Ad MP3 not found: {mp3}")
                continue
            valid_files.append(mp3)

        if not valid_files:
            logger.warning("No valid ads to combine.")
            return False

        # Log the ads that will be played
        played_ad_names = [ad.get("Name", "Unknown") for ad in ads
                          if ad.get("Enabled", True) and self._is_scheduled(ad, now)]
        self._log_ad_plays(played_ad_names)

        os.makedirs(os.path.dirname(self.output_mp3), exist_ok=True)
        return self._concatenate_mp3_files(valid_files, self.output_mp3)

    def _is_scheduled(self, ad, now):
        if not ad.get("Scheduled", False):
            return True
        day_name = now.strftime("%A")
        days = ad.get("Days", [])
        if days and day_name not in days:
            return False
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
            if not hour_match:
                return False
        return True

    def _concatenate_mp3_files(self, files, output_path):
        logger.debug(f"Concatenating {len(files)} files to {output_path}")
        if not PYDUB_AVAILABLE:
            logger.error("pydub not available - cannot concatenate MP3 files")
            return False
        try:
            combined = AudioSegment.empty()
            for fp in files:
                if not os.path.exists(fp):
                    logger.error(f"File not found: {fp}")
                    return False
                combined += AudioSegment.from_mp3(fp)
            combined.export(output_path, format="mp3")
            return True
        except Exception as e:  # pragma: no cover - runtime safety
            logger.exception(f"Error concatenating ads: {e}")
            return False

    def _call_url(self, url):
        logger.info(f"Calling ad service URL: {url}")
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                logger.info(f"Ad service response: {resp.status}")
            return True
        except Exception as e:  # pragma: no cover - runtime safety
            logger.error(f"Failed to call ad service URL: {e}")
            return False

    def _log_ad_plays(self, ad_names):
        """
        Log that the specified ads have been played.

        Args:
            ad_names: List of ad names that were played
        """
        if not self.ad_logger or not ad_names:
            return

        try:
            results = self.ad_logger.record_multiple_ad_plays(ad_names)
            successful = sum(results.values())
            total = len(results)

            if successful > 0:
                logger.info(f"Successfully logged {successful}/{total} ad plays")
                for ad_name, success in results.items():
                    if success:
                        logger.debug(f"Ad '{ad_name}' play logged successfully")
                    else:
                        logger.warning(f"Failed to log play for ad '{ad_name}'")
            else:
                logger.warning("No ad plays were successfully logged")

        except Exception as e:
            logger.error(f"Error logging ad plays: {e}")
