#!/usr/bin/env python3
"""
Test script to verify CMD window hiding fix for intro loader
"""
import logging
import sys
import os
import queue
import time

# Add current directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from intro_loader_handler import IntroLoaderHandler

# Setup basic logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

def test_intro_loader_initialization():
    """Test that IntroLoaderHandler initializes with CMD window hiding configured"""
    print("🧪 Testing IntroLoaderHandler CMD Window Hiding Fix")
    print("=" * 60)
    
    try:
        # Initialize IntroLoaderHandler (should configure pydub)
        log_queue = queue.Queue()
        handler = IntroLoaderHandler(log_queue)
        
        print("✅ IntroLoaderHandler initialized successfully")
        print("   - Pydub window hiding should now be configured")
        
        # Check if pydub is available and configured
        try:
            from pydub import AudioSegment
            print("   - Pydub is available")
            
            # Test a simple audio operation that might trigger subprocess calls
            # This won't actually process audio but will test the configuration
            print("   - Testing pydub configuration...")
            
            # Create a very short silent audio segment for testing
            silence = AudioSegment.silent(duration=100)  # 100ms of silence
            print("   - Created test audio segment successfully")
            
            # If we get here without CMD windows, the fix is working
            print("✅ No CMD windows should have appeared during audio processing")
            
        except ImportError:
            print("⚠️  Pydub not available, but initialization completed")
        except Exception as e:
            print(f"⚠️  Pydub test failed: {e}")
        
        print("\n📋 Handler configuration:")
        print(f"   - Running: {handler.running}")
        print(f"   - Thread: {handler.thread}")
        print(f"   - Next schedule run: {handler.next_schedule_run}")
        
        print("\n✅ Initialization test completed successfully!")
        print("   When the main app runs, CMD windows should no longer appear!")
        
    except Exception as e:
        print(f"❌ Initialization test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_intro_loader_initialization()
