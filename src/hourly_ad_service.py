import logging
import time
from datetime import datetime

from ad_inserter_service import AdInserterService
from lecture_detector import LectureDetector

logger = logging.getLogger('HourlyAds')

class HourlyAdService:
    """Service that triggers ads once every hour based on lecture schedule."""

    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.running = False
        self.flag_run_on_next_track = False
        self.last_track_signature = None

        now_playing_xml = self.config_manager.get_setting(
            "settings.rds.now_playing_xml", r"G:\\To_RDS\\nowplaying.xml"
        )
        self.lecture_detector = LectureDetector(
            xml_path=now_playing_xml, config_manager=config_manager
        )
        self.ad_service = AdInserterService(config_manager)

    def run(self):
        """Main loop that checks every second for hourly triggers and track changes."""
        logger.info("HourlyAdService started")
        self.running = True
        last_hour_handled = None
        while self.running:
            now = datetime.now()
            if now.minute == 0 and now.hour != last_hour_handled:
                self._handle_top_of_hour(now)
                last_hour_handled = now.hour

            if self.flag_run_on_next_track:
                self._check_for_track_change()

            time.sleep(1)

    def stop(self):  # pragma: no cover - graceful shutdown hook
        self.running = False

    # --- Internal helpers -------------------------------------------------
    def _current_track_signature(self):
        """Return a tuple uniquely identifying the currently playing track."""
        info = self.lecture_detector.get_current_track_info()
        started = self.lecture_detector.get_current_track_started()
        if not started:
            started = str(self.lecture_detector.get_xml_mtime())
        return (info.get('artist', ''), info.get('title', ''), started)

    def _handle_top_of_hour(self, now):
        logger.info("Top-of-hour ad check")
        try:
            if self.lecture_detector.is_next_track_lecture():
                logger.info("Next track is lecture - scheduling ads")
                self.ad_service.run()
                return

            if self.lecture_detector.next_lecture_starts_within_hour(now):
                logger.info(
                    "Next track not lecture but lecture within hour - will schedule on next track start"
                )
                self.flag_run_on_next_track = True
                self.last_track_signature = self._current_track_signature()
            else:
                logger.info("No lecture within next hour - playing ads instantly")
                self.ad_service.run_instant()
        except Exception as e:  # pragma: no cover - runtime safety
            logger.exception(f"Hourly ad check failed: {e}")

    def _check_for_track_change(self):
        signature = self._current_track_signature()
        if self.last_track_signature is None:
            self.last_track_signature = signature
            return
        if signature != self.last_track_signature:
            logger.info("Detected new track - scheduling ads")
            self.ad_service.run()
            self.flag_run_on_next_track = False
            self.last_track_signature = signature
