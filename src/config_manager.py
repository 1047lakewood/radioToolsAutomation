import json
import os
from datetime import datetime
import logging

class ConfigManager:
    """Manages loading, saving, and accessing configuration from JSON."""

    def __init__(self, config_file='messages.json', backup_prefix='messages_backup_'):
        self.config_file = config_file
        self.backup_prefix = backup_prefix
        self.config = self.load_config()

    def load_config(self):
        """Loads the JSON configuration or returns a default structure if file doesn't exist."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                logging.info(f"Configuration loaded from {self.config_file}.")
                return config
            except json.JSONDecodeError as e:
                logging.error(f"Error decoding JSON from {self.config_file}: {e}")
                return self._default_config()
        else:
            logging.warning(f"Config file {self.config_file} not found. Using default configuration.")
            return self._default_config()

    def _default_config(self):
        """Returns the default configuration structure."""
        return {
            "Messages": [],
            "Whitelist": [],
            "Blacklist": [],
            "playlist_presets": {},
            "Ads": [],
            "settings": {
                "rds": {
                    "ip": "50.208.125.83",
                    "port": 10001,
                    "now_playing_xml": r"G:\To_RDS\nowplaying.xml",
                    "default_message": "732.901.7777 to SUPPORT and hear this program!"
                },
                "intro_loader": {
                    "now_playing_xml": r"G:\To_RDS\nowplaying.xml",
                    "mp3_directory": r"G:\Shiurim\introsCleanedUp",
                    "missing_artists_log": r"G:\Misc\Dev\CombinedRDSApp\missing_artists.log",
                    "schedule_url": "http://192.168.3.11:9000/?pass=bmas220&action=schedule&type=run&id=TBACFNBGJKOMETDYSQYR"
                },
                "ad_inserter": {
                    "insertion_url": "http://localhost:8000/insert",
                    "output_mp3": r"G:\Ads\newAd.mp3"
                }
            }
        }

    def save_config(self, make_backup=True):
        """Saves the current configuration to JSON, optionally creating a backup."""
        if make_backup:
            self._backup_config()

        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
            logging.info(f"Configuration saved to {self.config_file}.")
        except Exception as e:
            logging.error(f"Error saving configuration to {self.config_file}: {e}")

    def _backup_config(self):
        """Creates a timestamped backup of the current config file."""
        if os.path.exists(self.config_file):
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = f"{self.backup_prefix}{timestamp}.json"
            try:
                os.rename(self.config_file, backup_file)
                logging.info(f"Backup created: {backup_file}")
            except OSError as e:
                logging.error(f"Error creating backup {backup_file}: {e}")

    def get_messages(self):
        """Returns the list of messages."""
        return self.config.get('Messages', [])

    def set_messages(self, messages):
        """Sets the list of messages."""
        self.config['Messages'] = messages

    def get_whitelist(self):
        """Returns the whitelist."""
        return self.config.get('Whitelist', [])

    def set_whitelist(self, whitelist):
        """Sets the whitelist."""
        self.config['Whitelist'] = whitelist

    def get_blacklist(self):
        """Returns the blacklist."""
        return self.config.get('Blacklist', [])

    def set_blacklist(self, blacklist):
        """Sets the blacklist."""
        self.config['Blacklist'] = blacklist

    def get_playlist_presets(self):
        """Returns the playlist presets dictionary."""
        return self.config.get('playlist_presets', {})

    def set_playlist_presets(self, presets):
        """Sets the playlist presets dictionary."""
        self.config['playlist_presets'] = presets

    def get_ads(self):
        """Returns the list of ads."""
        return self.config.get('Ads', [])

    def set_ads(self, ads):
        """Sets the list of ads."""
        self.config['Ads'] = ads

    def get_setting(self, key, default=None):
        """Generic getter for nested settings using dot notation."""
        try:
            keys = key.split('.')
            value = self.config
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            logging.warning(f"Setting '{key}' not found in configuration. Returning default: {default}")
            return default

    def update_setting(self, key, value):
        """Generic setter for nested settings using dot notation."""
        try:
            keys = key.split('.')
            d = self.config
            for k in keys[:-1]:
                if k not in d:
                    d[k] = {}
                d = d[k]
            d[keys[-1]] = value
            logging.info(f"Updated setting '{key}' to {value}")
        except Exception as e:
            logging.error(f"Error updating setting '{key}': {e}")

if __name__ == "__main__":
    print("This script defines the ConfigManager class.")