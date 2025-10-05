#!/usr/bin/env python
"""Test script to check handler initialization with station_id"""

from config_manager import ConfigManager
from queue import Queue

print("=" * 60)
print("Testing Handler Initialization")
print("=" * 60)

# Test ConfigManager
print("\n1. Testing ConfigManager...")
try:
    cm = ConfigManager()
    print(f"   [OK] ConfigManager loaded")
    print(f"   [OK] Stations: {cm.STATIONS}")
    print(f"   [OK] Station 1047: {cm.get_station_name('station_1047')}")
    print(f"   [OK] Station 887: {cm.get_station_name('station_887')}")
except Exception as e:
    print(f"   [FAIL] Error: {e}")
    import sys
    sys.exit(1)

# Test AutoRDSHandler
print("\n2. Testing AutoRDSHandler...")
try:
    from auto_rds_handler import AutoRDSHandler
    q = Queue()
    handler = AutoRDSHandler(q, cm, station_id='station_1047')
    print(f"   [OK] AutoRDSHandler initialized with station_id")
except TypeError as e:
    print(f"   [FAIL] TypeError: {e}")
    print(f"   --> Handler needs to be updated to accept station_id parameter")
except Exception as e:
    print(f"   [FAIL] Error: {e}")

# Test IntroLoaderHandler
print("\n3. Testing IntroLoaderHandler...")
try:
    from intro_loader_handler import IntroLoaderHandler
    q = Queue()
    handler = IntroLoaderHandler(q, cm, station_id='station_1047')
    print(f"   [OK] IntroLoaderHandler initialized with station_id")
except TypeError as e:
    print(f"   [FAIL] TypeError: {e}")
    print(f"   --> Handler needs to be updated to accept station_id parameter")
except Exception as e:
    print(f"   [FAIL] Error: {e}")

# Test AdSchedulerHandler
print("\n4. Testing AdSchedulerHandler...")
try:
    from ad_scheduler_handler import AdSchedulerHandler
    q = Queue()
    handler = AdSchedulerHandler(q, cm, station_id='station_1047')
    print(f"   [OK] AdSchedulerHandler initialized with station_id")
except TypeError as e:
    print(f"   [FAIL] TypeError: {e}")
    print(f"   --> Handler needs to be updated to accept station_id parameter")
except Exception as e:
    print(f"   [FAIL] Error: {e}")

print("\n" + "=" * 60)
print("Test Complete")
print("=" * 60)


