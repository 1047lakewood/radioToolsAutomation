import os
import ad_inserter_service
from ad_inserter_service import AdInserterService


class DummyConfigManager:
    def __init__(self, ads):
        self._ads = ads

    def get_ads(self):
        return self._ads

    def get_setting(self, key, default=None):
        return default


def test_combine_ads_respects_schedule(monkeypatch):
    ads = [
        {"Enabled": True, "Scheduled": True, "Days": ["Monday"], "Times": [{"hour": 10}], "MP3File": "a.mp3"},
        {"Enabled": True, "Scheduled": True, "Days": ["Tuesday"], "Times": [{"hour": 10}], "MP3File": "b.mp3"},
        {"Enabled": True, "Scheduled": False, "MP3File": "c.mp3"},
        {"Enabled": False, "Scheduled": False, "MP3File": "d.mp3"},
    ]
    config = DummyConfigManager(ads)
    service = AdInserterService(config)

    class FixedDateTime:
        @classmethod
        def now(cls):
            from datetime import datetime as _dt
            return _dt(2024, 8, 5, 10, 0, 0)  # Monday 10 AM

    monkeypatch.setattr(ad_inserter_service, "datetime", FixedDateTime)
    monkeypatch.setattr(os.path, "exists", lambda p: True)
    monkeypatch.setattr(os, "makedirs", lambda *args, **kwargs: None)

    captured = {}

    def fake_concat(self, files, output):
        captured["files"] = files
        captured["output"] = output
        return True

    monkeypatch.setattr(AdInserterService, "_concatenate_mp3_files", fake_concat)

    assert service._combine_ads() is True
    assert captured["files"] == ["a.mp3", "c.mp3"]


def test_combine_ads_handles_string_flags(monkeypatch):
    ads = [
        {
            "Enabled": "True",
            "Scheduled": "True",
            "Days": ["Monday"],
            "Times": [{"hour": 10}],
            "MP3File": "a.mp3",
        },
        {"Enabled": "True", "Scheduled": "False", "MP3File": "b.mp3"},
        {"Enabled": "False", "Scheduled": "False", "MP3File": "c.mp3"},
    ]
    config = DummyConfigManager(ads)
    service = AdInserterService(config)

    class FixedDateTime:
        @classmethod
        def now(cls):
            from datetime import datetime as _dt
            return _dt(2024, 8, 5, 10, 0, 0)  # Monday 10 AM

    monkeypatch.setattr(ad_inserter_service, "datetime", FixedDateTime)
    monkeypatch.setattr(os.path, "exists", lambda p: True)
    monkeypatch.setattr(os, "makedirs", lambda *args, **kwargs: None)

    captured = {}

    def fake_concat(self, files, output):
        captured["files"] = files
        return True

    monkeypatch.setattr(AdInserterService, "_concatenate_mp3_files", fake_concat)

    assert service._combine_ads() is True
    assert captured["files"] == ["a.mp3", "b.mp3"]
