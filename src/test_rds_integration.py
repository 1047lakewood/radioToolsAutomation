#!/usr/bin/env python3
"""
Test script to verify LectureDetector integration with AutoRDSHandler
"""
import logging
import sys
import os

# Add current directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config_manager import ConfigManager
from auto_rds_handler import AutoRDSHandler
from lecture_detector import LectureDetector
import queue

# Setup basic logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

def test_lecture_detector_integration():
    """Test the LectureDetector integration with AutoRDSHandler"""
    print("🧪 Testing LectureDetector Integration with AutoRDSHandler")
    print("=" * 60)
    
    try:
        # Initialize components
        config_manager = ConfigManager()
        log_queue = queue.Queue()
        
        # Create AutoRDSHandler (this should initialize LectureDetector)
        # Note: AutoRDSHandler expects log_queue as the first argument
        rds_handler = AutoRDSHandler(log_queue, config_manager)
        
        print("✅ AutoRDSHandler initialized successfully")
        print(f"   - LectureDetector instance: {rds_handler.lecture_detector}")
        print(f"   - XML path: {rds_handler.lecture_detector.xml_path}")
        
        # Test lecture detection
        print("\n📻 Testing lecture detection...")
        is_current_lecture = rds_handler.lecture_detector.is_current_track_lecture()
        is_next_lecture = rds_handler.lecture_detector.is_next_track_lecture()
        
        print(f"   - Current track is lecture: {is_current_lecture}")
        print(f"   - Next track is lecture: {is_next_lecture}")
        
        # Test current track info
        track_info = rds_handler.lecture_detector.get_current_track_info()
        print(f"   - Current track info: {track_info}")
        
        # Test message filtering
        print("\n📝 Testing message filtering...")
        
        # Create test messages
        test_messages = [
            {
                "Text": "Test message without artist placeholder",
                "Enabled": True,
                "Message Time": 10
            },
            {
                "Text": "Now playing: {artist} - {title}",
                "Enabled": True,
                "Message Time": 10
            },
            {
                "Text": "Call 732-901-7777 for more info",
                "Enabled": True,
                "Message Time": 10
            }
        ]
        
        # Test each message
        now_playing = rds_handler._load_now_playing()
        print(f"   - Now playing: {now_playing}")
        
        for i, message in enumerate(test_messages):
            should_display = rds_handler._should_display_message(message, now_playing)
            print(f"   - Message {i+1}: '{message['Text']}' -> Should display: {should_display}")
        
        # Test current display messages
        print("\n📋 Testing current display messages...")
        current_messages = rds_handler.get_current_display_messages()
        print(f"   - Current display messages: {current_messages}")
        
        print("\n✅ Integration test completed successfully!")
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_lecture_detector_integration()
