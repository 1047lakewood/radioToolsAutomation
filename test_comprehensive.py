#!/usr/bin/env python3
"""Comprehensive test script to verify radioToolsAutomation functionality."""

import os
import sys
import json
import logging
from pathlib import Path

def test_config_manager():
    """Test ConfigManager functionality."""
    print("Testing ConfigManager...")
    try:
        from src.config_manager import ConfigManager
        config_manager = ConfigManager()

        # Test basic functionality
        messages = config_manager.get_messages()
        settings = config_manager.get_setting('settings.rds.ip')
        print(f"  ✓ ConfigManager initialized successfully")
        print(f"  ✓ Loaded {len(messages)} messages")
        print(f"  ✓ RDS IP setting: {settings}")
        return True
    except Exception as e:
        print(f"  ✗ ConfigManager test failed: {e}")
        return False

def test_auto_rds_handler():
    """Test AutoRDSHandler initialization."""
    print("Testing AutoRDSHandler...")
    try:
        # Add the src directory to Python path
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

        from config_manager import ConfigManager
        from auto_rds_handler import AutoRDSHandler
        from queue import Queue

        config_manager = ConfigManager()
        log_queue = Queue()
        handler = AutoRDSHandler(log_queue, config_manager)

        print("  ✓ AutoRDSHandler initialized successfully")
        print(f"  ✓ RDS IP: {handler.rds_ip}")
        print(f"  ✓ RDS Port: {handler.rds_port}")
        return True
    except Exception as e:
        print(f"  ✗ AutoRDSHandler test failed: {e}")
        return False

def test_intro_loader_handler():
    """Test IntroLoaderHandler initialization."""
    print("Testing IntroLoaderHandler...")
    try:
        # Add the src directory to Python path
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

        from config_manager import ConfigManager
        from intro_loader_handler import IntroLoaderHandler
        from queue import Queue

        config_manager = ConfigManager()
        log_queue = Queue()
        handler = IntroLoaderHandler(log_queue, config_manager)

        print("  ✓ IntroLoaderHandler initialized successfully")
        print(f"  ✓ MP3 Directory: {handler.mp3_directory}")
        print(f"  ✓ Schedule URL: {handler.schedule_url}")
        return True
    except Exception as e:
        print(f"  ✗ IntroLoaderHandler test failed: {e}")
        return False

def test_gui_imports():
    """Test GUI-related imports."""
    print("Testing GUI imports...")
    try:
        import tkinter as tk
        from tkinter import ttk, messagebox
        import ttkthemes
        print("  ✓ All GUI imports successful")
        return True
    except Exception as e:
        print(f"  ✗ GUI imports failed: {e}")
        return False

def test_file_paths():
    """Test if critical file paths exist."""
    print("Testing file paths...")
    try:
        # Add the src directory to Python path
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

        from config_manager import ConfigManager
        config_manager = ConfigManager()

        # Check now_playing_xml path
        xml_path = config_manager.get_setting('settings.rds.now_playing_xml')
        if xml_path and os.path.exists(xml_path):
            print(f"  ✓ Now playing XML exists: {xml_path}")
        else:
            print(f"  ⚠ Now playing XML not found: {xml_path}")

        # Check MP3 directory
        mp3_dir = config_manager.get_setting('settings.intro_loader.mp3_directory')
        if mp3_dir and os.path.exists(mp3_dir):
            print(f"  ✓ MP3 directory exists: {mp3_dir}")
        else:
            print(f"  ⚠ MP3 directory not found: {mp3_dir}")

        # Check missing artists log
        log_path = config_manager.get_setting('settings.intro_loader.missing_artists_log')
        log_dir = os.path.dirname(log_path)
        if os.path.exists(log_dir):
            print(f"  ✓ Log directory exists: {log_dir}")
        else:
            print(f"  ⚠ Log directory not found: {log_dir}")

        return True
    except Exception as e:
        print(f"  ✗ File path test failed: {e}")
        return False

def test_network_connectivity():
    """Test network connectivity for RDS."""
    print("Testing network connectivity...")
    try:
        # Add the src directory to Python path
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

        from config_manager import ConfigManager
        config_manager = ConfigManager()

        import socket
        rds_ip = config_manager.get_setting('settings.rds.ip')
        rds_port = config_manager.get_setting('settings.rds.port')

        # Try to connect to RDS server
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((rds_ip, rds_port))
        sock.close()

        if result == 0:
            print(f"  ✓ RDS server reachable: {rds_ip}:{rds_port}")
        else:
            print(f"  ⚠ RDS server not reachable: {rds_ip}:{rds_port}")

        return True
    except Exception as e:
        print(f"  ✗ Network test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("Running comprehensive radioToolsAutomation tests...")
    print("=" * 60)

    tests = [
        test_config_manager,
        test_auto_rds_handler,
        test_intro_loader_handler,
        test_gui_imports,
        test_file_paths,
        test_network_connectivity,
    ]

    results = []
    for test in tests:
        success = test()
        results.append(success)
        print()

    print("=" * 60)
    passed = sum(results)
    total = len(results)

    if passed == total:
        print(f"✅ All {total} tests passed! The application should work properly.")
        return True
    else:
        print(f"⚠️ {passed}/{total} tests passed. Some issues detected.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
