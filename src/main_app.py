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
from ad_scheduler_handler import AdSchedulerHandler
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
            
            # Apply debug logging setting from config
            enable_debug = self.config_manager.get_setting("settings.debug.enable_debug_logs", False)
            if enable_debug:
                logging.getLogger().setLevel(logging.DEBUG)
                logging.info("Debug logging enabled from config")
            
            logging.info("ConfigManager initialized successfully.")
        except Exception as e:
            logging.error(f"Failed to initialize ConfigManager: {e}")
            messagebox.showerror("Initialization Error", f"Failed to load configuration: {e}")
            self.destroy()
            return

        self.rds_queue = Queue()
        self.intro_queue = Queue()
        self.ad_scheduler_queue = Queue()

        # Route handler loggers to the queues
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        rds_qh = QueueHandler(self.rds_queue)
        rds_qh.setFormatter(formatter)
        loader_qh = QueueHandler(self.intro_queue)
        loader_qh.setFormatter(formatter)
        ad_scheduler_qh = QueueHandler(self.ad_scheduler_queue)
        ad_scheduler_qh.setFormatter(formatter)

        # Get debug setting to determine log level
        enable_debug = self.config_manager.get_setting("settings.debug.enable_debug_logs", False)
        log_level = logging.DEBUG if enable_debug else logging.INFO

        rds_logger = logging.getLogger('AutoRDS')
        rds_logger.setLevel(log_level)
        rds_logger.propagate = False
        rds_logger.addHandler(rds_qh)

        loader_logger = logging.getLogger('IntroLoader')
        loader_logger.setLevel(log_level)
        loader_logger.propagate = False
        loader_logger.addHandler(loader_qh)

        ad_scheduler_logger = logging.getLogger('AdScheduler')
        ad_scheduler_logger.setLevel(log_level)
        ad_scheduler_logger.propagate = False
        ad_scheduler_logger.addHandler(ad_scheduler_qh)

        # Initialize handlers
        try:
            # # Ensure correct argument order: queue, config_manager
            self.rds_handler = AutoRDSHandler(self.rds_queue, self.config_manager)
            logging.info("AutoRDSHandler initialized successfully.")
            self.intro_loader_handler = IntroLoaderHandler(self.intro_queue, self.config_manager)

            logging.info("IntroLoaderHandler initialized successfully.")
            self.ad_scheduler_handler = AdSchedulerHandler(self.ad_scheduler_queue, self.config_manager)
            logging.info("AdSchedulerHandler initialized successfully.")
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
            self.ad_scheduler_thread = threading.Thread(target=self.ad_scheduler_handler.run, daemon=True)
            self.rds_thread.start()
            self.intro_thread.start()
            self.ad_scheduler_thread.start()
            logging.info("Handler threads started successfully.")
        except Exception as e:
            logging.error(f"Failed to start handler threads: {e}")
            messagebox.showerror("Thread Error", f"Failed to start handler threads: {e}")
            self.destroy()
            return

        # Start periodic GUI updates
        self.after(100, self.process_queues)
        self.after(5000, self.update_message_cycle)

    def on_close(self):
        """Handle window close event."""
        try:
            # Stop all handlers
            if hasattr(self, 'rds_handler') and self.rds_handler:
                self.rds_handler.stop()
            if hasattr(self, 'intro_loader_handler') and self.intro_loader_handler:
                self.intro_loader_handler.stop()
            if hasattr(self, 'ad_scheduler_handler') and self.ad_scheduler_handler:
                self.ad_scheduler_handler.stop()

            # Stop threads
            if hasattr(self, 'rds_thread') and self.rds_thread and self.rds_thread.is_alive():
                self.rds_thread.join(timeout=2)
            if hasattr(self, 'intro_thread') and self.intro_thread and self.intro_thread.is_alive():
                self.intro_thread.join(timeout=2)
            if hasattr(self, 'ad_scheduler_thread') and self.ad_scheduler_thread and self.ad_scheduler_thread.is_alive():
                self.ad_scheduler_thread.join(timeout=2)

        except Exception as e:
            logging.error(f"Error stopping handlers: {e}")
        finally:
            self.destroy()

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
        ttk.Button(toolbar, text="Ad Statistics", command=self.open_ad_statistics_window).pack(side=tk.LEFT, padx=5)

        # Logs Section with dedicated panes
        log_pane = ttk.PanedWindow(main_frame, orient=tk.VERTICAL)
        log_pane.pack(fill=tk.BOTH, expand=True)

        # Create tabbed notebook for logs
        log_notebook = ttk.Notebook(log_pane)

        # AutoRDS Logs Tab
        rds_log_frame = ttk.Frame(log_notebook)
        log_notebook.add(rds_log_frame, text="AutoRDS")
        self.rds_log_text = tk.Text(rds_log_frame, wrap=tk.WORD, state=tk.DISABLED, height=10, font=("Consolas", 9))
        rds_scroll = ttk.Scrollbar(rds_log_frame, orient=tk.VERTICAL, command=self.rds_log_text.yview)
        self.rds_log_text.config(yscrollcommand=rds_scroll.set)
        rds_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.rds_log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Intro Loader Logs Tab
        loader_log_frame = ttk.Frame(log_notebook)
        log_notebook.add(loader_log_frame, text="Intro Loader")
        self.loader_log_text = tk.Text(loader_log_frame, wrap=tk.WORD, state=tk.DISABLED, height=10, font=("Consolas", 9))
        loader_scroll = ttk.Scrollbar(loader_log_frame, orient=tk.VERTICAL, command=self.loader_log_text.yview)
        self.loader_log_text.config(yscrollcommand=loader_scroll.set)
        loader_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.loader_log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Ad Scheduler Logs Tab
        ad_scheduler_log_frame = ttk.Frame(log_notebook)
        log_notebook.add(ad_scheduler_log_frame, text="Ad Scheduler")
        self.ad_scheduler_log_text = tk.Text(ad_scheduler_log_frame, wrap=tk.WORD, state=tk.DISABLED, height=10, font=("Consolas", 9))
        ad_scheduler_scroll = ttk.Scrollbar(ad_scheduler_log_frame, orient=tk.VERTICAL, command=self.ad_scheduler_log_text.yview)
        self.ad_scheduler_log_text.config(yscrollcommand=ad_scheduler_scroll.set)
        ad_scheduler_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.ad_scheduler_log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Add the notebook to the paned window
        log_pane.add(log_notebook, weight=1)

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
        OptionsWindow(self, self.config_manager, self.intro_loader_handler, self.rds_handler, self.ad_scheduler_handler)

    def open_playlist_editor_window(self):
        PlaylistEditorWindow(self, self.config_manager)

    def open_ad_inserter_window(self):
        AdInserterWindow(self, self.config_manager)

    def open_ad_statistics_window(self):
        """Open the ad statistics window."""
        from ui_ad_statistics_window import AdStatisticsWindow
        AdStatisticsWindow(self, self.config_manager)

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

        while not self.ad_scheduler_queue.empty():
            message = self.ad_scheduler_queue.get()
            self._log_message(self.ad_scheduler_log_text, message)
            updated = True

        if updated:
            self.rds_log_text.see(tk.END)
            self.loader_log_text.see(tk.END)
            self.ad_scheduler_log_text.see(tk.END)

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