#!/usr/bin/env python3
"""Test script for ConfigWindow dual-station functionality."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from config_manager import ConfigManager
from ui_config_window import ConfigWindow

def test_config_window():
    """Test that ConfigWindow opens with dual-station tabs."""
    print("Testing ConfigWindow dual-station functionality...")

    # Create config manager
    config_manager = ConfigManager()

    # Create a minimal Tkinter root for testing
    try:
        import tkinter as tk
        root = tk.Tk()
        root.title("Test Root")
        root.geometry("200x100")

        # Create ConfigWindow
        config_window = ConfigWindow(root, config_manager)

        print("PASS: ConfigWindow created successfully")

        # Check that we have station-specific data
        assert "station_1047" in config_window.station_messages
        assert "station_887" in config_window.station_messages
        print("PASS: Station messages loaded")

        # Check that we have station-specific UI widgets
        assert "station_1047" in config_window.station_message_vars
        assert "station_887" in config_window.station_message_vars
        print("PASS: Station-specific UI widgets created")

        # Check that tabs exist
        assert len(config_window.station_frames) == 2
        assert "station_1047" in config_window.station_frames
        assert "station_887" in config_window.station_frames
        print("PASS: Station tabs created")

        # Simulate tab change
        config_window.current_station = "station_887"
        config_window.load_messages_into_tree()
        print("PASS: Tab switching works")

        print("All tests passed!")
        return True

    except Exception as e:
        print(f"FAIL: Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        try:
            root.destroy()
        except:
            pass

if __name__ == "__main__":
    test_config_window()
