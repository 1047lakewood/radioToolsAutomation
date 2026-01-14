# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Important Workflow Rule

**Always run the application after making any code changes** so the user can test it:
```bash
python src/main_app.py
```

## Project Overview

radioToolsAutomation is a Python desktop application for automating Radio Data System (RDS) messaging and audio intro loading for radio broadcasting. It supports dual-station operation (104.7 FM and 88.7 FM) with intelligent ad scheduling and lecture detection.

**Stack:** Python 3.8+ (tested on 3.12.3), Tkinter + ttkthemes, Windows-only

## Running the Application

```bash
# Run directly
python src/main_app.py

# Run headless (no console window)
START RDS AND INTRO.bat

# Diagnostic scripts (in tests/ folder)
python tests/check_status.py
python tests/check_xml.py
python tests/check_blacklist.py
python tests/test_xml_monitor.py
python tests/run_with_monitor.py
```

## Dependencies

Core dependencies (install via pip):
- `ttkthemes` - GUI theming
- `pydub` - Audio manipulation (requires FFmpeg installed)
- `reportlab` - PDF report generation (optional)

## Architecture

### Threading Model

The app runs 6 daemon threads (3 per station) alongside the main Tkinter GUI:
- **AutoRDSHandler** - RDS message rotation via socket communication
- **IntroLoaderHandler** - Audio intro management from XML track data
- **AdSchedulerHandler** - Intelligent hourly ad scheduling

Each handler has a Queue for logging; the GUI processes all queues every 500ms via `process_queues()`.

### Key Design Patterns

**Observer Pattern:** ConfigManager notifies registered handlers when config changes, triggering automatic reload via `reload_configuration()`.

**Dual-Station Architecture:** Everything is keyed by `station_1047` or `station_887` in config.json. Access settings via `config_manager.get_station_setting(station_id, category, key)`.

**Thread Safety:** ConfigManager and AdPlayLogger use RLock for concurrent access.

### Core Modules

| Module | Purpose |
|--------|---------|
| `src/main_app.py` | MainApp class - Tkinter root, spawns handlers |
| `src/config_manager.py` | JSON config with observer pattern, auto-backup |
| `src/auto_rds_handler.py` | RDS message cycling, placeholder replacement |
| `src/intro_loader_handler.py` | XML monitoring, MP3 intro copying |
| `src/ad_scheduler_handler.py` | Hourly ad scheduling with lecture detection |
| `src/nowplaying_reader.py` | Robust XML reading with retry logic |
| `src/lecture_detector.py` | Rule-based track classification |
| `src/ad_inserter_service.py` | Ad concatenation and URL triggering |
| `src/ad_play_logger.py` | XML-confirmed ad tracking |

### UI Windows

Modal windows in `src/ui_*.py`:
- `ui_config_window.py` - RDS message configuration (dual-station tabs)
- `ui_options_window.py` - Whitelist/blacklist management, debug tools
- `ui_ad_inserter_window.py` - Ad configuration
- `ui_ad_statistics_window.py` - Ad play statistics and report generation

## Project Structure

```
radioToolsAutomation/
├── src/                      # Application source code
│   ├── main_app.py          # Main application
│   ├── config_manager.py    # Configuration management
│   ├── ad_scheduler_handler.py
│   ├── auto_rds_handler.py
│   ├── intro_loader_handler.py
│   └── ...other modules
├── tests/                    # Test and diagnostic scripts
│   ├── check_status.py
│   ├── check_xml.py
│   ├── test_xml_monitor.py
│   └── ...other diagnostics
├── user_data/               # User configuration and statistics (gitignored)
│   ├── config.json          # Application configuration
│   ├── ad_plays_1047.json   # Ad play statistics for 104.7 FM
│   ├── ad_plays_887.json    # Ad play statistics for 88.7 FM
│   ├── ad_failures_1047.json
│   ├── ad_failures_887.json
│   └── config_backup_*.json # Auto-created backups
└── ...other files
```

## Configuration

**user_data/config.json** (auto-created in user_data/, gitignored):
```
stations.station_1047.settings.rds.ip/port  - RDS encoder connection
stations.station_1047.settings.intro_loader.now_playing_xml  - XML path
stations.station_1047.Messages[]  - RDS message array
shared.whitelist/blacklist  - Lecture detection overrides
```

Backups are auto-created as `user_data/config_backup_YYYYMMDD_HHMMSS.json` on each save.

**Ad Statistics:**
- `user_data/ad_plays_*.json` - Successful ad insertions (ultra-compact format)
- `user_data/ad_failures_*.json` - Failed ad insertion attempts for debugging

## Lecture Detection Logic

Tracks are classified as lectures based on:
1. Artist name starts with 'R' → lecture (unless whitelisted)
2. Whitelist → a lecture
3. Blacklist → not a lecture

See `src/lecture_detector.py` for implementation.

## Ad Scheduling Logic

Ad scheduler runs hourly checks with:
- 3-minute safety margin before hour end
- Track-change detection for opportunistic scheduling
- Lecture detection integration (tries to play ad before lectures)
- XML confirmation polling (waits for ARTIST=="adRoll")

See `AD_SCHEDULER_LOGIC.md` for detailed decision flow.

## Debugging

Use Options → Debug tab for:
- XML "touch" to force track change checks
- Simulate hour start for ad scheduler testing

Diagnostic scripts are located in `tests/` folder:
- `tests/check_status.py` - Check handler status
- `tests/check_xml.py` - Validate XML file format
- `tests/check_blacklist.py` - Review lecture detection rules
- `tests/test_xml_monitor.py` - Monitor XML updates in real-time
- `tests/run_with_monitor.py` - Run app with XML monitoring

## Version Updates

**Workflow Rule:** When you request "update version" (without specifying a new version), automatically:
1. Increment the last number (patch version) by one in `src/version.py`
2. Update the release date to today
3. Commit with message: `v{new_version}: {description of changes}`
4. Push to remote

**Example:** If current version is 2.5.5 and you say "update version", it becomes 2.5.6.

If you need a specific version, just specify it: "update version to 2.6.0"
