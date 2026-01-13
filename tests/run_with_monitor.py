#!/usr/bin/env python3
"""
Convenience script to run the main app with XML monitoring.
"""

import subprocess
import time
import os
import sys

def main():
    print("\n" + "="*80)
    print("  STARTING: Main App + XML Monitor")
    print("="*80 + "\n")

    # Start main app in background
    print("🚀 Starting main application...")
    main_process = subprocess.Popen(
        [sys.executable, "src/main_app.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    # Give app time to start
    time.sleep(3)
    print("✅ Main app started (PID: {})".format(main_process.pid))

    # Start XML monitor
    print("\n📊 Starting XML monitor in 2 seconds...\n")
    time.sleep(2)

    monitor_process = subprocess.Popen(
        [sys.executable, "test_xml_monitor.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    print("✅ XML monitor started (PID: {})\n".format(monitor_process.pid))

    print("="*80)
    print("BOTH PROCESSES RUNNING")
    print("="*80)
    print("\n📝 Instructions:")
    print("   1. Look at the XML Monitor output below")
    print("   2. In the main app, go to Options → Debug tab")
    print("   3. Click 'Play Ad Now' to trigger an instant ad")
    print("   4. Watch the monitor output for 'AD DETECTED!' message")
    print("   5. Press Ctrl+C here to stop both processes\n")

    try:
        # Display monitor output in real-time
        while monitor_process.poll() is None:
            line = monitor_process.stdout.readline()
            if line:
                print(line, end='')
            time.sleep(0.1)

        # Get any remaining output
        remaining = monitor_process.stdout.read()
        if remaining:
            print(remaining)

    except KeyboardInterrupt:
        print("\n\n⏸  Stopping processes...")
        monitor_process.terminate()
        main_process.terminate()

        # Wait for termination
        try:
            monitor_process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            monitor_process.kill()

        try:
            main_process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            main_process.kill()

        print("✅ All processes stopped")

    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    main()
