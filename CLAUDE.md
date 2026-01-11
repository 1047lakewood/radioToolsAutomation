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

# Diagnostic scripts
python check_status.py
python check_xml.py
python check_blacklist.py
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

## Configuration

**config.json** (auto-created, gitignored):
```
stations.station_1047.settings.rds.ip/port  - RDS encoder connection
stations.station_1047.settings.intro_loader.now_playing_xml  - XML path
stations.station_1047.Messages[]  - RDS message array
shared.whitelist/blacklist  - Lecture detection overrides
```

Backups are auto-created as `config_backup_YYYYMMDD_HHMMSS.json` on each save.

## Lecture Detection Logic

Tracks are classified as lectures based on:
1. Artist name starts with 'R' → lecture (unless whitelisted)
2. Whitelist → never a lecture
3. Blacklist → always a lecture

See `src/lecture_detector.py` for implementation.

## Ad Scheduling Logic

Ad scheduler runs hourly checks with:
- 3-minute safety margin before hour end
- Track-change detection for opportunistic scheduling
- Lecture detection integration (skips ads during lectures)
- XML confirmation polling (waits for ARTIST=="adRoll")

See `AD_SCHEDULER_LOGIC.md` for detailed decision flow.

## Debugging

Use Options → Debug tab for:
- XML "touch" to force track change checks
- Simulate hour start for ad scheduler testing

Check diagnostic scripts in root: `check_*.py`
