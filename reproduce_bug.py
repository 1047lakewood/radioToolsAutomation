#!/usr/bin/env python3
"""
Script to reproduce the bug where scheduled hours disappear when selecting a message for the first time.
This script will simulate the user interaction with the ConfigWindow.
"""

import tkinter as tk
from tkinter import ttk
import json
import logging
from config_manager import ConfigManager
from ui_config_window import ConfigWindow
import time

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_messages_from_file():
    """Load messages from the JSON file to verify current state."""
    try:
        with open('../messages.json', 'r') as f:
            data = json.load(f)
            return data.get('Messages', [])
    except Exception as e:
        logging.error(f"Error loading messages: {e}")
        return []

def find_message_with_scheduled_hours(messages):
    """Find a message that has scheduled hours configured."""
    for i, msg in enumerate(messages):
        scheduled = msg.get('Scheduled', {})
        if scheduled.get('Enabled', False) and scheduled.get('Times', []):
            return i, msg
    return None, None

def reproduce_bug():
    """Reproduce the bug by simulating user interaction."""
    
    print("=== Bug Reproduction Test ===")
    print("Step 1: Loading current messages configuration...")
    
    # Load current messages
    messages = load_messages_from_file()
    print(f"Loaded {len(messages)} messages")
    
    # Find a message with scheduled hours
    msg_index, message = find_message_with_scheduled_hours(messages)
    if message is None:
        print("ERROR: No message found with scheduled hours. Cannot reproduce bug.")
        return False
    
    print(f"Step 2: Found message with scheduled hours at index {msg_index}:")
    print(f"  Text: {message['Text']}")
    print(f"  Scheduled Days: {message['Scheduled']['Days']}")
    print(f"  Scheduled Times: {message['Scheduled']['Times']}")
    
    # Store original times for comparison
    original_times = message['Scheduled']['Times'].copy()
    print(f"  Original times count: {len(original_times)}")
    
    # Create a minimal Tkinter app to test the ConfigWindow
    print("\nStep 3: Creating test application...")
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    
    try:
        # Initialize ConfigManager
        config_manager = ConfigManager()
        
        # Create ConfigWindow (this simulates opening the configuration)
        print("Step 4: Opening ConfigWindow...")
        config_window = ConfigWindow(root, config_manager)
        
        # Simulate selecting the message with scheduled hours
        print(f"Step 5: Simulating selection of message at index {msg_index}...")
        
        # Find the treeview item and select it
        item_id = f"item{msg_index}"
        if config_window.tree.exists(item_id):
            config_window.tree.selection_set(item_id)
            config_window.tree.see(item_id)
            
            # Trigger the selection event
            config_window.on_message_select(None)
            
            # Check if the times are still there
            current_times_text = config_window.time_entry.get()
            print(f"  Times in entry field: '{current_times_text}'")
            
            # Check the actual message data
            current_message = config_manager.get_messages()[msg_index]
            current_times = current_message['Scheduled']['Times']
            print(f"  Current times in data: {current_times}")
            print(f"  Current times count: {len(current_times)}")
            
            # Compare with original
            if len(current_times) != len(original_times):
                print(f"🐛 BUG REPRODUCED: Times count changed from {len(original_times)} to {len(current_times)}")
                print(f"   Original: {original_times}")
                print(f"   Current:  {current_times}")
                
                # Check if the time entry field is empty
                if not current_times_text.strip():
                    print("🐛 BUG CONFIRMED: Time entry field is empty!")
                
                bug_reproduced = True
            else:
                print("✅ No bug detected - times preserved")
                bug_reproduced = False
                
        else:
            print(f"ERROR: Could not find tree item {item_id}")
            bug_reproduced = False
            
        # Close the window
        config_window.destroy()
        
    except Exception as e:
        logging.exception(f"Error during bug reproduction: {e}")
        bug_reproduced = False
    finally:
        root.destroy()
    
    print(f"\nStep 6: Bug reproduction result: {'SUCCESS' if bug_reproduced else 'FAILED'}")
    
    # Save the current state for later comparison
    if bug_reproduced:
        print("\nStep 7: Saving current state for later verification...")
        with open('bug_reproduction_state.json', 'w') as f:
            json.dump({
                'message_index': msg_index,
                'original_times': original_times,
                'current_times': current_times,
                'bug_reproduced': True,
                'timestamp': time.time()
            }, f, indent=2)
        print("Bug state saved to bug_reproduction_state.json")
    
    return bug_reproduced

if __name__ == "__main__":
    success = reproduce_bug()
    exit(0 if success else 1)
