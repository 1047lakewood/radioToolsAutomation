import time
import logging
import threading
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from lecture_detector import LectureDetector
from ad_inserter_service import AdInserterService

# Get the specific logger for this handler
logger = logging.getLogger('AdScheduler')

# Constants
LOOP_SLEEP = 60  # Check every minute
HOUR_CHECK_INTERVAL = 3600  # Check for hour boundaries every hour
ERROR_RETRY_DELAY = 300  # 5 minutes after errors

class AdSchedulerHandler:
    """Intelligent ad scheduler that runs ads based on lecture detection and timing."""

    def __init__(self, log_queue, config_manager):
        """
        Initialize the AdScheduler handler.

        Args:
            log_queue: Log queue for logging
            config_manager: ConfigManager instance
        """
        logger.info("AdSchedulerHandler __init__ called")
        self.config_manager = config_manager
        self.running = False
        self.thread = None
        self.last_hour_check = time.time()  # Initialize to current time
        self.waiting_for_track_boundary = False
        self.pending_lecture_check = False
        logger.debug(f"AdSchedulerHandler initialized with running={self.running}")

        # Initialize components
        self.lecture_detector = None
        self.ad_service = None
        self.reload_components()

        logger.info("AdSchedulerHandler initialized successfully.")
        logger.debug(f"Initial state: running={self.running}, last_hour_check={self.last_hour_check}")

    def reload_components(self):
        """Reload configuration-dependent components."""
        try:
            # Get XML path from config
            xml_path = self.config_manager.get_setting("settings.intro_loader.now_playing_xml", r"G:\To_RDS\nowplaying.xml")
            logger.debug(f"Using XML path: {xml_path}")

            # Initialize lecture detector
            try:
                self.lecture_detector = LectureDetector(xml_path, self.config_manager)
                logger.debug("Lecture detector initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize lecture detector: {e}")
                self.lecture_detector = None

            # Initialize ad service
            try:
                logger.debug("Attempting to initialize AdInserterService...")
                self.ad_service = AdInserterService(self.config_manager)
                logger.debug("Ad service initialized successfully.")
            except ImportError as e:
                logger.error(f"Import error initializing ad service: {e}")
                logger.error("AdPlayLogger import failed - this may be expected if dependencies are missing")
                self.ad_service = None
            except Exception as e:
                logger.error(f"Failed to initialize ad service: {e}")
                logger.error(f"Error type: {type(e).__name__}")
                self.ad_service = None

            if self.lecture_detector and self.ad_service:
                logger.debug("AdScheduler components reloaded successfully.")
            else:
                logger.warning("Some AdScheduler components failed to initialize - handler may not function properly.")
        except Exception as e:
            logger.error(f"Error reloading AdScheduler components: {e}")
            logger.error(f"Error details: {type(e).__name__}: {str(e)}")
            # Don't raise - allow handler to continue with partial functionality

    def run(self):
        """Main scheduler loop."""
        logger.info("AdScheduler handler run() method called!")
        self.running = True  # Set running state when run() starts
        logger.info("AdScheduler handler started.")
        logger.debug("AdScheduler run() method executing in thread")
        iteration_count = 0

        try:
            logger.debug(f"Starting main loop. Running state: {self.running}")
            while self.running:
                logger.debug(f"Loop condition check: self.running = {self.running}")
                try:
                    iteration_count += 1
                    current_time = time.time()
                    time_since_last_check = current_time - self.last_hour_check

                    logger.debug(f"Loop iteration {iteration_count}, time since last check: {time_since_last_check:.1f}s")
                    logger.debug(f"Current running state: {self.running}")

                    # Check if it's time for hourly evaluation
                    if time_since_last_check >= HOUR_CHECK_INTERVAL:
                        logger.debug(f"Hourly check triggered after {time_since_last_check:.1f}s")
                        try:
                            self._perform_hourly_check()
                            self.last_hour_check = current_time
                        except Exception as e:
                            logger.error(f"Error in hourly check: {e}")
                            # Reset last_hour_check to avoid immediate retry
                            self.last_hour_check = current_time
                    else:
                        logger.debug(f"Not time for hourly check yet. Sleeping for {LOOP_SLEEP}s")

                    # Brief sleep between checks
                    time.sleep(LOOP_SLEEP)

                except Exception as e:
                    logger.error(f"Error in AdScheduler main loop iteration {iteration_count}: {e}")
                    logger.error(f"Error type: {type(e).__name__}")
                    logger.info(f"Retrying in {ERROR_RETRY_DELAY} seconds...")
                    time.sleep(ERROR_RETRY_DELAY)

        except KeyboardInterrupt:
            logger.info("AdScheduler handler interrupted.")
        except Exception as e:
            logger.error(f"Fatal error in AdScheduler handler: {e}")
        finally:
            logger.info(f"AdScheduler handler stopped after {iteration_count} iterations.")

    def _perform_hourly_check(self):
        """Perform the hourly ad scheduling check."""
        try:
            logger.debug("Performing hourly ad scheduling check.")

            # Check if components are available
            if not self.lecture_detector:
                logger.warning("Lecture detector not available - skipping hourly check.")
                return

            if not self.ad_service:
                logger.warning("Ad service not available - skipping hourly check.")
                return

            logger.debug("Both components available - proceeding with lecture detection.")

            # Check if next track is a lecture
            try:
                next_is_lecture = self._is_next_track_lecture()
                logger.debug(f"Next track is lecture: {next_is_lecture}")
            except Exception as e:
                logger.error(f"Error checking if next track is lecture: {e}")
                next_is_lecture = False

            if next_is_lecture:
                logger.debug("Next track is a lecture - evaluating timing.")

                # Check if it will start within current hour
                try:
                    will_start_within_hour = self._will_lecture_start_within_hour()
                    logger.debug(f"Lecture will start within hour: {will_start_within_hour}")
                except Exception as e:
                    logger.error(f"Error checking lecture timing: {e}")
                    will_start_within_hour = False

                if will_start_within_hour:
                    logger.info("Next lecture will start within current hour - running schedule service.")
                    self._run_schedule_service()
                else:
                    logger.info("Next lecture will not start within current hour - running instant service.")
                    self._run_instant_service()
            else:
                logger.debug("Next track is not a lecture - waiting for track boundary.")
                self.waiting_for_track_boundary = True
                self.pending_lecture_check = True

        except Exception as e:
            logger.error(f"Error in hourly check: {e}")
            logger.error(f"Error details: {type(e).__name__}: {str(e)}")
            # Fallback to instant service on errors
            try:
                self._run_instant_service()
            except Exception as e2:
                logger.error(f"Failed to run fallback instant service: {e2}")

    def _is_next_track_lecture(self):
        """Check if the next track is a lecture."""
        try:
            return self.lecture_detector.is_next_track_lecture()
        except Exception as e:
            logger.error(f"Error checking if next track is lecture: {e}")
            return False

    def _will_lecture_start_within_hour(self):
        """Check if the next lecture will start within the current hour."""
        try:
            current_time = datetime.now()
            logger.debug(f"Current time: {current_time}")

            # Get current track duration
            current_duration = self.lecture_detector.get_current_track_duration()
            logger.debug(f"Current track duration: {current_duration}")
            if not current_duration:
                logger.warning("Could not get current track duration.")
                return False

            # Parse duration (format: "MM:SS")
            try:
                minutes, seconds = map(int, current_duration.split(':'))
                duration_seconds = minutes * 60 + seconds
                logger.debug(f"Parsed duration: {minutes}m {seconds}s = {duration_seconds}s")
            except (ValueError, AttributeError) as e:
                logger.error(f"Invalid duration format: {current_duration}, error: {e}")
                return False

            # Calculate when current track will end
            current_start_time = self._get_current_track_start_time()
            logger.debug(f"Current track start time: {current_start_time}")
            if not current_start_time:
                logger.warning("Could not get current track start time.")
                return False

            track_end_time = current_start_time + timedelta(seconds=duration_seconds)
            logger.debug(f"Calculated track end time: {track_end_time}")

            # Check if end time is within current hour
            current_hour_end = (current_time + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            logger.debug(f"Current hour end: {current_hour_end}")

            within_hour = track_end_time <= current_hour_end
            logger.debug(f"Track ends at {track_end_time}, hour ends at {current_hour_end}")
            logger.debug(f"Within hour calculation: {track_end_time} <= {current_hour_end} = {within_hour}")

            return within_hour

        except Exception as e:
            logger.error(f"Error checking lecture timing: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            return False

    def _get_current_track_start_time(self):
        """Get the start time of the current track from XML."""
        try:
            logger.debug(f"Getting current track start time from XML: {self.lecture_detector.xml_path}")

            # Parse the XML to get the STARTED attribute from the TRACK element
            if not os.path.exists(self.lecture_detector.xml_path):
                logger.warning(f"XML file not found: {self.lecture_detector.xml_path}")
                return None

            tree = ET.parse(self.lecture_detector.xml_path)
            root = tree.getroot()

            # Find the TRACK element and get its STARTED attribute
            track_element = root.find('TRACK')
            if track_element is None:
                logger.warning("TRACK element not found in XML")
                return None

            started_str = track_element.get('STARTED')
            logger.debug(f"Found STARTED attribute: {started_str}")
            if not started_str:
                logger.warning("STARTED attribute not found in TRACK element")
                return None

            # Parse the datetime string (format: "2025-09-29 11:05:15")
            try:
                start_time = datetime.strptime(started_str, "%Y-%m-%d %H:%M:%S")
                logger.debug(f"Parsed start time: {start_time}")
                return start_time
            except ValueError as e:
                logger.error(f"Error parsing start time '{started_str}': {e}")
                return None

        except ET.ParseError as e:
            logger.error(f"Error parsing XML file: {e}")
            return None
        except Exception as e:
            logger.error(f"Error getting current track start time: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            return None

    def _run_schedule_service(self):
        """Run the ad service in schedule mode."""
        try:
            if not self.ad_service:
                logger.warning("Ad service not available - cannot run schedule service.")
                return

            logger.info("Running ad service in schedule mode.")
            success = self.ad_service.run()
            if success:
                logger.info("Schedule service completed successfully.")
            else:
                logger.warning("Schedule service completed with errors.")
        except Exception as e:
            logger.error(f"Error running schedule service: {e}")

    def _run_instant_service(self):
        """Run the ad service in instant mode."""
        try:
            if not self.ad_service:
                logger.warning("Ad service not available - cannot run instant service.")
                return

            logger.info("Running ad service in instant mode.")
            success = self.ad_service.run_instant()
            if success:
                logger.info("Instant service completed successfully.")
            else:
                logger.warning("Instant service completed with errors.")
        except Exception as e:
            logger.error(f"Error running instant service: {e}")

    def stop(self):
        """Stop the scheduler."""
        logger.info("Stopping AdScheduler handler.")
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)

    def start(self):
        """Start the scheduler in a thread."""
        logger.info(f"AdScheduler start() called. Current running state: {self.running}")
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self.run, daemon=True, name="AdSchedulerThread")
            logger.info("Starting AdScheduler thread...")
            self.thread.start()
            logger.info("AdScheduler handler thread started.")
            logger.debug(f"Thread started: {self.thread.is_alive()}")
            logger.debug(f"Thread name: {self.thread.name}")
        else:
            logger.warning("AdScheduler handler already running.")
