import tkinter as tk
from tkinter import ttk, messagebox
import ttkthemes
import logging
import os
import threading
from queue import Queue
from datetime import datetime


class QueueHandler(logging.Handler):
    """Send logging records to a queue."""

    def __init__(self, log_queue: Queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        try:
            msg = self.format(record)
            self.log_queue.put(msg)
        except Exception:
            self.handleError(record)

from config_manager import ConfigManager
from auto_rds_handler import AutoRDSHandler
from intro_loader_handler import IntroLoaderHandler
from hourly_ad_service import HourlyAdService
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
        self.ads_queue = Queue()

        # Route handler loggers to the queues
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        rds_qh = QueueHandler(self.rds_queue)
        rds_qh.setFormatter(formatter)
        loader_qh = QueueHandler(self.intro_queue)
        loader_qh.setFormatter(formatter)
        ads_qh = QueueHandler(self.ads_queue)
        ads_qh.setFormatter(formatter)

        rds_logger = logging.getLogger('AutoRDS')
        rds_logger.setLevel(logging.INFO)
        rds_logger.propagate = False
        rds_logger.addHandler(rds_qh)

        loader_logger = logging.getLogger('IntroLoader')
        loader_logger.setLevel(logging.INFO)
        loader_logger.propagate = False
        loader_logger.addHandler(loader_qh)

        ads_logger = logging.getLogger('HourlyAds')
        ads_logger.setLevel(logging.INFO)
        ads_logger.propagate = False
        ads_logger.addHandler(ads_qh)

        # Initialize handlers
        try:
            # # Ensure correct argument order: queue, config_manager
            self.rds_handler = AutoRDSHandler(self.rds_queue, self.config_manager)
            logging.info("AutoRDSHandler initialized successfully.")
            self.intro_loader_handler = IntroLoaderHandler(self.intro_queue, self.config_manager)
            logging.info("IntroLoaderHandler initialized successfully.")

            self.hourly_ad_service = HourlyAdService(self.config_manager)
            logging.info("HourlyAdService initialized successfully.")
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
            self.ads_thread = threading.Thread(target=self.hourly_ad_service.run, daemon=True)
            self.rds_thread.start()
            self.intro_thread.start()
            self.ads_thread.start()
            logging.info("Handler threads started successfully.")
        except Exception as e:
            logging.error(f"Failed to start handler threads: {e}")
            messagebox.showerror("Thread Error", f"Failed to start handler threads: {e}")
            self.destroy()
            return

        # Start periodic GUI updates
        self.after(100, self.process_queues)
        self.after(5000, self.update_message_cycle)

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

        # Logs Section with dedicated panes
        log_pane = ttk.PanedWindow(main_frame, orient=tk.VERTICAL)
        log_pane.pack(fill=tk.BOTH, expand=True)

        rds_log_frame = ttk.LabelFrame(log_pane, text="AutoRDS Logs")
        self.rds_log_text = tk.Text(rds_log_frame, wrap=tk.WORD, state=tk.DISABLED, height=10, font=("Consolas", 9))
        rds_scroll = ttk.Scrollbar(rds_log_frame, orient=tk.VERTICAL, command=self.rds_log_text.yview)
        self.rds_log_text.config(yscrollcommand=rds_scroll.set)
        rds_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.rds_log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        loader_log_frame = ttk.LabelFrame(log_pane, text="Intro Loader Logs")
        self.loader_log_text = tk.Text(loader_log_frame, wrap=tk.WORD, state=tk.DISABLED, height=10, font=("Consolas", 9))
        loader_scroll = ttk.Scrollbar(loader_log_frame, orient=tk.VERTICAL, command=self.loader_log_text.yview)
        self.loader_log_text.config(yscrollcommand=loader_scroll.set)
        loader_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.loader_log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        ads_log_frame = ttk.LabelFrame(log_pane, text="Hourly Ad Logs")
        self.ads_log_text = tk.Text(ads_log_frame, wrap=tk.WORD, state=tk.DISABLED, height=10, font=("Consolas", 9))
        ads_scroll = ttk.Scrollbar(ads_log_frame, orient=tk.VERTICAL, command=self.ads_log_text.yview)
        self.ads_log_text.config(yscrollcommand=ads_scroll.set)
        ads_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.ads_log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        log_pane.add(rds_log_frame, weight=1)
        log_pane.add(loader_log_frame, weight=1)
        log_pane.add(ads_log_frame, weight=1)

        # Current RDS Messages Cycle
        msg_frame = ttk.LabelFrame(main_frame, text="Current RDS Messages Cycle")
        msg_frame.pack(fill=tk.X, pady=(10, 0))
        self.msg_listbox = tk.Listbox(msg_frame, height=8, font=("Segoe UI", 9))
        msg_scroll = ttk.Scrollbar(msg_frame, orient=tk.VERTICAL, command=self.msg_listbox.yview)
        self.msg_listbox.config(yscrollcommand=msg_scroll.set)
        msg_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.msg_listbox.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)

        # Current RDS Message label
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
            self._log_message(self.rds_log_text, message)
            if "Sent RDS message" in message:
                try:
                    sent_msg = message.split("Sent RDS message: ")[1].strip()
                    self.current_rds_var.set(sent_msg)
                except IndexError:
                    pass
            updated = True

        while not self.intro_queue.empty():
            message = self.intro_queue.get()
            self._log_message(self.loader_log_text, message)
            updated = True

        while not self.ads_queue.empty():
            message = self.ads_queue.get()
            self._log_message(self.ads_log_text, message)
            updated = True

        if updated:
            self.rds_log_text.see(tk.END)
            self.loader_log_text.see(tk.END)
            self.ads_log_text.see(tk.END)

        self.after(100, self.process_queues)

    def update_message_cycle(self):
        """Refresh the list of messages currently eligible for display."""
        try:
            messages = self.rds_handler.get_current_display_messages()
            self.msg_listbox.delete(0, tk.END)
            if messages:
                for msg in messages:
                    self.msg_listbox.insert(tk.END, msg)
            else:
                self.msg_listbox.insert(tk.END, "(No messages currently scheduled/valid)")
        except Exception as e:
            self.msg_listbox.delete(0, tk.END)
            self.msg_listbox.insert(tk.END, f"(Error: {e})")
        finally:
            self.after(5000, self.update_message_cycle)

    def _log_message(self, widget, message):
        """Insert a timestamped message into the given text widget."""
        widget.config(state=tk.NORMAL)
        timestamp = datetime.now().strftime('%H:%M:%S')
        widget.insert(tk.END, f"[{timestamp}] {message}\n")
        widget.config(state=tk.DISABLED)

if __name__ == "__main__":
    app = MainApp()
    app.mainloop()