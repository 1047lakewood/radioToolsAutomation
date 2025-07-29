import tkinter as tk
from tkinter import ttk, messagebox
import ttkthemes
import logging
import os
import threading
from queue import Queue
from datetime import datetime

from config_manager import ConfigManager
from auto_rds_handler import AutoRDSHandler
from intro_loader_handler import IntroLoaderHandler
from ui_config_window import ConfigWindow
from ui_missing_artists_window import MissingArtistsWindow
from ui_options_window import OptionsWindow
from ui_playlist_editor_window import PlaylistEditorWindow
from ui_ad_inserter_window import AdInserterWindow

class MainApp(tk.Tk):
    """Main application window with GUI for monitoring and configuration."""

    def __init__(self):
        super().__init__()
        self.title("radioToolsAutomation")
        self.geometry("800x600")
        self.minsize(700, 500)
        self.themed_style = ttkthemes.ThemedStyle(self)
        self.themed_style.set_theme("arc")  # Modern theme; options: 'arc', 'equilux', etc.
        
        # Initialize logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

        # Initialize components
        try:
            self.config_manager = ConfigManager()
            
            logging.info("ConfigManager initialized successfully.")
        except Exception as e:
            logging.error(f"Failed to initialize ConfigManager: {e}")
            messagebox.showerror("Initialization Error", f"Failed to load configuration: {e}")
            self.destroy()
            return

        self.rds_queue = Queue()
        self.intro_queue = Queue()

        # Initialize handlers
        try:
            # # Ensure correct argument order: queue, config_manager
            self.rds_handler = AutoRDSHandler(self.rds_queue, self.config_manager)
            logging.info("AutoRDSHandler initialized successfully.")
            self.intro_loader_handler = IntroLoaderHandler(self.intro_queue, self.config_manager)
            
            logging.info("IntroLoaderHandler initialized successfully.")
        except AttributeError as e:
            logging.error(f"AttributeError during handler initialization: {e}")
            messagebox.showerror("Initialization Error", f"Failed to initialize handlers: {e}")
            self.destroy()
            return
        except Exception as e:
            logging.error(f"Unexpected error during handler initialization: {e}")
            messagebox.showerror("Initialization Error", f"Failed to initialize handlers: {e}")
            self.destroy()
            return

        self.create_widgets()

        # Start handlers in threads
        try:
            self.rds_thread = threading.Thread(target=self.rds_handler.run, daemon=True)
            self.intro_thread = threading.Thread(target=self.intro_loader_handler.run, daemon=True)
            self.rds_thread.start()
            self.intro_thread.start()
            logging.info("Handler threads started successfully.")
        except Exception as e:
            logging.error(f"Failed to start handler threads: {e}")
            messagebox.showerror("Thread Error", f"Failed to start handler threads: {e}")
            self.destroy()
            return

        # Start processing queues for GUI updates
        self.after(100, self.process_queues)

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Toolbar
        toolbar = ttk.Frame(main_frame)
        toolbar.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(toolbar, text="Configure Messages", command=self.open_config_window).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Show Missing Artists", command=self.open_missing_artists_window).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Options", command=self.open_options_window).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Mini Playlist Editor", command=self.open_playlist_editor_window).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Ad Inserter", command=self.open_ad_inserter_window).pack(side=tk.LEFT, padx=5)

        # Logs Section
        logs_frame = ttk.LabelFrame(main_frame, text="Logs", padding="5")
        logs_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.log_text = tk.Text(logs_frame, wrap=tk.WORD, height=15, font=("Segoe UI", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.config(state=tk.DISABLED)  # Read-only

        # Current RDS Message
        rds_frame = ttk.LabelFrame(main_frame, text="Current RDS Message", padding="5")
        rds_frame.pack(fill=tk.X, pady=5)

        self.current_rds_var = tk.StringVar(value="Waiting for first message...")
        rds_label = ttk.Label(rds_frame, textvariable=self.current_rds_var, font=("Segoe UI", 10, "bold"), anchor=tk.W)
        rds_label.pack(fill=tk.X)

    def open_config_window(self):
        """Open the message configuration window."""
        ConfigWindow(self, self.config_manager)

    def open_missing_artists_window(self):
        MissingArtistsWindow(self, self.intro_loader_handler)

    def open_options_window(self):
        OptionsWindow(self, self.config_manager, self.intro_loader_handler)

    def open_playlist_editor_window(self):
        PlaylistEditorWindow(self, self.config_manager)

    def open_ad_inserter_window(self):
        AdInserterWindow(self, self.config_manager)

    def process_queues(self):
        """Processes messages from queues to update GUI."""
        updated = False
        while not self.rds_queue.empty():
            message = self.rds_queue.get()
            self._log_message("RDS", message)
            if "Sent RDS message" in message:
                try:
                    sent_msg = message.split("Sent RDS message: ")[1].strip()
                    self.current_rds_var.set(sent_msg)
                except IndexError:
                    pass
            updated = True

        while not self.intro_queue.empty():
            message = self.intro_queue.get()
            self._log_message("Intro", message)
            updated = True

        if updated:
            self.log_text.see(tk.END)  # Auto-scroll to bottom

        self.after(100, self.process_queues)

    def _log_message(self, handler, message):
        """Inserts a formatted log message into the text widget."""
        self.log_text.config(state=tk.NORMAL)
        timestamp = datetime.now().strftime('%H:%M:%S')
        formatted = f"[{timestamp}] [{handler}] {message}\n"
        self.log_text.insert(tk.END, formatted)
        self.log_text.config(state=tk.DISABLED)

if __name__ == "__main__":
    app = MainApp()
    app.mainloop()