from unittest.mock import Mock

from hourly_ad_service import HourlyAdService


class DummyConfig:
    def get_setting(self, key, default=None):
        return default

    def get_blacklist(self):
        return []

    def get_whitelist(self):
        return []


def test_ads_run_when_track_started_changes():
    service = HourlyAdService(DummyConfig())
    service.flag_run_on_next_track = True
    # Mock lecture detector to return same artist/title but different STARTED times
    detector = Mock()
    service.lecture_detector = detector
    # initial signature
    detector.get_current_track_info.return_value = {"artist": "A", "title": "Song"}
    detector.get_current_track_started.return_value = "2024-01-01 12:00:00"
    service.last_track_signature = ("A", "Song", "2024-01-01 12:00:00")

    # Next call simulates same song replayed but new start time
    detector.get_current_track_info.return_value = {"artist": "A", "title": "Song"}
    detector.get_current_track_started.return_value = "2024-01-01 12:03:00"

    service.ad_service = Mock()
    service._check_for_track_change()
    service.ad_service.run.assert_called_once()
    assert service.flag_run_on_next_track is False
