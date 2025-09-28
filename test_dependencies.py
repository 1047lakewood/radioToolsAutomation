#!/usr/bin/env python3
"""Test script to check if all required dependencies are installed."""

def test_import(module_name, description):
    """Test if a module can be imported."""
    try:
        __import__(module_name)
        print(f"{description}: ✓ OK")
        return True
    except ImportError as e:
        print(f"{description}: ✗ ERROR - {e}")
        return False

def main():
    """Test all required dependencies."""
    print("Testing required dependencies for radioToolsAutomation...")
    print("=" * 50)

    dependencies = [
        ("tkinter", "GUI Framework"),
        ("ttkthemes", "Theming Library"),
        ("pydub", "Audio Processing"),
        ("requests", "HTTP Requests"),
        ("urllib.request", "URL Handling (built-in)"),
        ("xml.etree.ElementTree", "XML Processing (built-in)"),
        ("json", "JSON Processing (built-in)"),
        ("logging", "Logging (built-in)"),
        ("os", "OS Interface (built-in)"),
        ("time", "Time Functions (built-in)"),
        ("datetime", "Date/Time (built-in)"),
        ("threading", "Threading (built-in)"),
        ("socket", "Network Sockets (built-in)"),
    ]

    results = []
    for module, description in dependencies:
        success = test_import(module, description)
        results.append((module, success))

    print("=" * 50)
    failed = [module for module, success in results if not success]

    if failed:
        print(f"❌ {len(failed)} dependencies missing: {', '.join(failed)}")
        print("\nTo fix this, run:")
        print("pip install ttkthemes pydub requests")
        return False
    else:
        print("✅ All required dependencies are installed!")
        return True

if __name__ == "__main__":
    main()
