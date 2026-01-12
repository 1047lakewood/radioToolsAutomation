import tkinter as tk
from tkinter import ttk, messagebox
import ttkthemes
import logging
import os
import threading
import time
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
from utils import configure_hidden_subprocess
from version import get_full_version

class MainApp(tk.Tk):
    """Main application window with GUI for monitoring and configuration - Dual Station Support."""

    def __init__(self):
        # Configure subprocess to hide windows on Windows before any subprocess usage
        configure_hidden_subprocess()

        super().__init__()
        self.title("radioToolsAutomation")
        self.geometry("900x700")
        self.minsize(800, 600)
        self.themed_style = ttkthemes.ThemedStyle(self)
        self.themed_style.set_theme("arc")  # Modern theme; options: 'arc', 'equilux', etc.

        # Create menu bar
        self.create_menu_bar()

        # Initialize logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

        # Initialize components
        try:
            self.config_manager = ConfigManager()
            
            # Apply debug logging setting from config
            enable_debug = self.config_manager.get_shared_setting("debug.enable_debug_logs", False)
            if enable_debug:
                logging.getLogger().setLevel(logging.DEBUG)
                logging.info("Debug logging enabled from config")
            
            logging.info("ConfigManager initialized successfully.")
        except Exception as e:
            logging.error(f"Failed to initialize ConfigManager: {e}")
            messagebox.showerror("Initialization Error", f"Failed to load configuration: {e}")
            self.destroy()
            return

        # Create 6 queues (3 per station)
        self.rds_1047_queue = Queue()
        self.intro_1047_queue = Queue()
        self.ad_1047_queue = Queue()
        self.rds_887_queue = Queue()
        self.intro_887_queue = Queue()
        self.ad_887_queue = Queue()

        # Setup logging for all handlers
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        enable_debug = self.config_manager.get_shared_setting("debug.enable_debug_logs", False)
        log_level = logging.DEBUG if enable_debug else logging.INFO

        # Station 1047 loggers
        rds_1047_qh = QueueHandler(self.rds_1047_queue)
        rds_1047_qh.setFormatter(formatter)
        rds_1047_logger = logging.getLogger('AutoRDS_1047')
        rds_1047_logger.setLevel(log_level)
        rds_1047_logger.propagate = False
        rds_1047_logger.addHandler(rds_1047_qh)

        intro_1047_qh = QueueHandler(self.intro_1047_queue)
        intro_1047_qh.setFormatter(formatter)
        intro_1047_logger = logging.getLogger('IntroLoader_1047')
        intro_1047_logger.setLevel(log_level)
        intro_1047_logger.propagate = False
        intro_1047_logger.addHandler(intro_1047_qh)

        ad_1047_qh = QueueHandler(self.ad_1047_queue)
        ad_1047_qh.setFormatter(formatter)
        ad_1047_logger = logging.getLogger('AdScheduler_1047')
        ad_1047_logger.setLevel(log_level)
        ad_1047_logger.propagate = False
        ad_1047_logger.addHandler(ad_1047_qh)

        # Station 887 loggers
        rds_887_qh = QueueHandler(self.rds_887_queue)
        rds_887_qh.setFormatter(formatter)
        rds_887_logger = logging.getLogger('AutoRDS_887')
        rds_887_logger.setLevel(log_level)
        rds_887_logger.propagate = False
        rds_887_logger.addHandler(rds_887_qh)

        intro_887_qh = QueueHandler(self.intro_887_queue)
        intro_887_qh.setFormatter(formatter)
        intro_887_logger = logging.getLogger('IntroLoader_887')
        intro_887_logger.setLevel(log_level)
        intro_887_logger.propagate = False
        intro_887_logger.addHandler(intro_887_qh)

        ad_887_qh = QueueHandler(self.ad_887_queue)
        ad_887_qh.setFormatter(formatter)
        ad_887_logger = logging.getLogger('AdScheduler_887')
        ad_887_logger.setLevel(log_level)
        ad_887_logger.propagate = False
        ad_887_logger.addHandler(ad_887_qh)

        # Initialize handlers for both stations
        try:
            # Station 1047 handlers
            self.rds_1047_handler = AutoRDSHandler(self.rds_1047_queue, self.config_manager, station_id='station_1047')
            logging.info("Station 104.7 FM AutoRDSHandler initialized successfully.")
            
            self.intro_1047_handler = IntroLoaderHandler(self.intro_1047_queue, self.config_manager, station_id='station_1047')
            logging.info("Station 104.7 FM IntroLoaderHandler initialized successfully.")
            
            self.ad_1047_handler = AdSchedulerHandler(self.ad_1047_queue, self.config_manager, station_id='station_1047')
            logging.info("Station 104.7 FM AdSchedulerHandler initialized successfully.")

            # Station 887 handlers
            self.rds_887_handler = AutoRDSHandler(self.rds_887_queue, self.config_manager, station_id='station_887')
            logging.info("Station 88.7 FM AutoRDSHandler initialized successfully.")
            
            self.intro_887_handler = IntroLoaderHandler(self.intro_887_queue, self.config_manager, station_id='station_887')
            logging.info("Station 88.7 FM IntroLoaderHandler initialized successfully.")
            
            self.ad_887_handler = AdSchedulerHandler(self.ad_887_queue, self.config_manager, station_id='station_887')
            logging.info("Station 88.7 FM AdSchedulerHandler initialized successfully.")

            # Register all handlers as config observers for automatic reload on config changes
            self._register_config_observers()
            logging.info("All handlers registered as config observers.")
            
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

        # Initialize auto-scroll tracking (enabled by default)
        self.auto_scroll_enabled = True

        # Start all 6 handlers in threads
        try:
            self.rds_1047_thread = threading.Thread(target=self.rds_1047_handler.run, daemon=True, name="RDS_1047")
            self.intro_1047_thread = threading.Thread(target=self.intro_1047_handler.run, daemon=True, name="Intro_1047")
            self.ad_1047_thread = threading.Thread(target=self.ad_1047_handler.run, daemon=True, name="Ad_1047")
            self.rds_887_thread = threading.Thread(target=self.rds_887_handler.run, daemon=True, name="RDS_887")
            self.intro_887_thread = threading.Thread(target=self.intro_887_handler.run, daemon=True, name="Intro_887")
            self.ad_887_thread = threading.Thread(target=self.ad_887_handler.run, daemon=True, name="Ad_887")
            
            self.rds_1047_thread.start()
            self.intro_1047_thread.start()
            self.ad_1047_thread.start()
            self.rds_887_thread.start()
            self.intro_887_thread.start()
            self.ad_887_thread.start()

            logging.info("All handler threads started successfully.")
            logging.info("RDS 104.7 thread alive: " + str(self.rds_1047_thread.is_alive()))
            logging.info("Intro 104.7 thread alive: " + str(self.intro_1047_thread.is_alive()))
            logging.info("Ad 104.7 thread alive: " + str(self.ad_1047_thread.is_alive()))
            logging.info("RDS 88.7 thread alive: " + str(self.rds_887_thread.is_alive()))
            logging.info("Intro 88.7 thread alive: " + str(self.intro_887_thread.is_alive()))
            logging.info("Ad 88.7 thread alive: " + str(self.ad_887_thread.is_alive()))
        except Exception as e:
            logging.error(f"Failed to start handler threads: {e}")
            messagebox.showerror("Thread Error", f"Failed to start handler threads: {e}")
            self.destroy()
            return

        # Start periodic GUI updates
        self.after(500, self.process_queues)

        # Start background thread for message cycle updates
        self.message_update_thread = threading.Thread(target=self._message_update_worker, daemon=True, name="MessageUpdate")
        self.message_update_running = True
        self.message_update_thread.start()

        # Initialize connectivity status cache (checked in background thread)
        self._radioboss_1047_connected = None
        self._radioboss_887_connected = None
        self._connectivity_lock = threading.Lock()

        # Start background thread for connectivity checks (separate from UI updates)
        self.connectivity_thread = threading.Thread(target=self._connectivity_check_worker, daemon=True, name="ConnectivityCheck")
        self.connectivity_thread.start()

        # Initialize status indicators
        self._update_status_indicators()

    def _register_config_observers(self):
        """Register all handlers as config observers for automatic reload on config changes."""
        # Define a wrapper that safely reloads all handlers
        def reload_all_handlers():
            logging.info("Config changed - reloading all handler configurations...")
            
            # Reload RDS handlers
            for handler, name in [
                (self.rds_1047_handler, "RDS 104.7"),
                (self.rds_887_handler, "RDS 88.7")
            ]:
                try:
                    handler.reload_configuration()
                    handler.reload_lecture_detector()
                    logging.debug(f"{name} handler configuration reloaded.")
                except Exception as e:
                    logging.error(f"Failed to reload {name} handler: {e}")
            
            # Reload Intro Loader handlers
            for handler, name in [
                (self.intro_1047_handler, "Intro Loader 104.7"),
                (self.intro_887_handler, "Intro Loader 88.7")
            ]:
                try:
                    handler.reload_configuration()
                    logging.debug(f"{name} handler configuration reloaded.")
                except Exception as e:
                    logging.error(f"Failed to reload {name} handler: {e}")
            
            # Reload Ad Scheduler handlers
            for handler, name in [
                (self.ad_1047_handler, "Ad Scheduler 104.7"),
                (self.ad_887_handler, "Ad Scheduler 88.7")
            ]:
                try:
                    handler.reload_configuration()
                    logging.debug(f"{name} handler configuration reloaded.")
                except Exception as e:
                    logging.error(f"Failed to reload {name} handler: {e}")
            
            logging.info("All handler configurations reloaded successfully.")
        
        # Register the combined reload function as a config observer
        self.config_manager.register_observer(reload_all_handlers)

    def create_menu_bar(self):
        """Create the application menu bar."""
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label="Show Missing Artists", command=self.open_missing_artists_window)
        tools_menu.add_command(label="Options", command=self.open_options_window)
        tools_menu.add_command(label="Ad Statistics", command=self.open_ad_statistics_window)
        menubar.add_cascade(label="Tools", menu=tools_menu)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

    def show_about(self):
        """Show the about dialog with version information."""
        about_message = f"""{get_full_version()}

Dual Station RDS and Intro Automation System
Enhanced with XML-Confirmed Ad Reporting

© 2025 - Radio Tools Automation
"""
        messagebox.showinfo("About radioToolsAutomation", about_message)

    def on_close(self):
        """Handle window close event."""
        try:
            # Stop message update and connectivity threads
            self.message_update_running = False
            if hasattr(self, 'message_update_thread') and self.message_update_thread.is_alive():
                self.message_update_thread.join(timeout=2)
            if hasattr(self, 'connectivity_thread') and self.connectivity_thread.is_alive():
                self.connectivity_thread.join(timeout=2)

            # Stop all handlers
            handlers = [
                ('rds_1047_handler', 'rds_1047_thread'),
                ('intro_1047_handler', 'intro_1047_thread'),
                ('ad_1047_handler', 'ad_1047_thread'),
                ('rds_887_handler', 'rds_887_thread'),
                ('intro_887_handler', 'intro_887_thread'),
                ('ad_887_handler', 'ad_887_thread')
            ]

            for handler_name, thread_name in handlers:
                if hasattr(self, handler_name):
                    handler = getattr(self, handler_name)
                    if handler:
                        handler.stop()

                if hasattr(self, thread_name):
                    thread = getattr(self, thread_name)
                    if thread and thread.is_alive():
                        thread.join(timeout=2)

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
        ttk.Button(toolbar, text="Mini Playlist Editor", command=self.open_playlist_editor_window).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Ad Inserter", command=self.open_ad_inserter_window).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Pause Scroll", command=self._pause_scroll).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Jump to Bottom", command=self._jump_to_bottom).pack(side=tk.LEFT, padx=5)

        # Logs Section with 6 tabs (3 per station)
        log_pane = ttk.PanedWindow(main_frame, orient=tk.VERTICAL)
        log_pane.pack(fill=tk.BOTH, expand=True)

        # Create tabbed notebook for logs
        log_notebook = ttk.Notebook(log_pane)

        # Station 104.7 FM Logs
        rds_1047_frame = ttk.Frame(log_notebook)
        log_notebook.add(rds_1047_frame, text="104.7 AutoRDS")
        self.rds_1047_log_text = tk.Text(rds_1047_frame, wrap=tk.WORD, state=tk.DISABLED, height=10, font=("Consolas", 9))
        rds_1047_scroll = ttk.Scrollbar(rds_1047_frame, orient=tk.VERTICAL, command=self.rds_1047_log_text.yview)
        self.rds_1047_log_text.config(yscrollcommand=rds_1047_scroll.set)
        rds_1047_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.rds_1047_log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        intro_1047_frame = ttk.Frame(log_notebook)
        log_notebook.add(intro_1047_frame, text="104.7 Intro Loader")
        self.intro_1047_log_text = tk.Text(intro_1047_frame, wrap=tk.WORD, state=tk.DISABLED, height=10, font=("Consolas", 9))
        intro_1047_scroll = ttk.Scrollbar(intro_1047_frame, orient=tk.VERTICAL, command=self.intro_1047_log_text.yview)
        self.intro_1047_log_text.config(yscrollcommand=intro_1047_scroll.set)
        intro_1047_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.intro_1047_log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        ad_1047_frame = ttk.Frame(log_notebook)
        log_notebook.add(ad_1047_frame, text="104.7 Ad Scheduler")
        self.ad_1047_log_text = tk.Text(ad_1047_frame, wrap=tk.WORD, state=tk.DISABLED, height=10, font=("Consolas", 9))
        ad_1047_scroll = ttk.Scrollbar(ad_1047_frame, orient=tk.VERTICAL, command=self.ad_1047_log_text.yview)
        self.ad_1047_log_text.config(yscrollcommand=ad_1047_scroll.set)
        ad_1047_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.ad_1047_log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Station 88.7 FM Logs
        rds_887_frame = ttk.Frame(log_notebook)
        log_notebook.add(rds_887_frame, text="88.7 AutoRDS")
        self.rds_887_log_text = tk.Text(rds_887_frame, wrap=tk.WORD, state=tk.DISABLED, height=10, font=("Consolas", 9))
        rds_887_scroll = ttk.Scrollbar(rds_887_frame, orient=tk.VERTICAL, command=self.rds_887_log_text.yview)
        self.rds_887_log_text.config(yscrollcommand=rds_887_scroll.set)
        rds_887_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.rds_887_log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        intro_887_frame = ttk.Frame(log_notebook)
        log_notebook.add(intro_887_frame, text="88.7 Intro Loader")
        self.intro_887_log_text = tk.Text(intro_887_frame, wrap=tk.WORD, state=tk.DISABLED, height=10, font=("Consolas", 9))
        intro_887_scroll = ttk.Scrollbar(intro_887_frame, orient=tk.VERTICAL, command=self.intro_887_log_text.yview)
        self.intro_887_log_text.config(yscrollcommand=intro_887_scroll.set)
        intro_887_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.intro_887_log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        ad_887_frame = ttk.Frame(log_notebook)
        log_notebook.add(ad_887_frame, text="88.7 Ad Scheduler")
        self.ad_887_log_text = tk.Text(ad_887_frame, wrap=tk.WORD, state=tk.DISABLED, height=10, font=("Consolas", 9))
        ad_887_scroll = ttk.Scrollbar(ad_887_frame, orient=tk.VERTICAL, command=self.ad_887_log_text.yview)
        self.ad_887_log_text.config(yscrollcommand=ad_887_scroll.set)
        ad_887_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.ad_887_log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Add the notebook to the paned window
        log_pane.add(log_notebook, weight=1)

        # Current RDS Messages Cycle - Side by Side
        msg_container = ttk.Frame(main_frame)
        msg_container.pack(fill=tk.X, pady=(10, 0))

        # 104.7 FM Messages
        msg_1047_frame = ttk.LabelFrame(msg_container, text="104.7 FM - Current RDS Messages")
        msg_1047_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        self.msg_1047_listbox = tk.Listbox(msg_1047_frame, height=4, font=("Segoe UI", 9))
        msg_1047_scroll = ttk.Scrollbar(msg_1047_frame, orient=tk.VERTICAL, command=self.msg_1047_listbox.yview)
        self.msg_1047_listbox.config(yscrollcommand=msg_1047_scroll.set)
        msg_1047_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.msg_1047_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 88.7 FM Messages
        msg_887_frame = ttk.LabelFrame(msg_container, text="88.7 FM - Current RDS Messages")
        msg_887_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))
        self.msg_887_listbox = tk.Listbox(msg_887_frame, height=4, font=("Segoe UI", 9))
        msg_887_scroll = ttk.Scrollbar(msg_887_frame, orient=tk.VERTICAL, command=self.msg_887_listbox.yview)
        self.msg_887_listbox.config(yscrollcommand=msg_887_scroll.set)
        msg_887_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.msg_887_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Current RDS Message labels - Side by Side
        rds_container = ttk.Frame(main_frame)
        rds_container.pack(fill=tk.X, pady=5)

        # 104.7 FM Current Message
        rds_1047_frame = ttk.LabelFrame(rds_container, text="104.7 FM - Current RDS", padding="5")
        rds_1047_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        # RDS Status indicator frame
        rds_1047_status_frame = ttk.Frame(rds_1047_frame)
        rds_1047_status_frame.pack(fill=tk.X, pady=(0, 2))

        self.rds_1047_status_canvas = tk.Canvas(rds_1047_status_frame, width=16, height=16, bg=self.cget('bg'), highlightthickness=0)
        self.rds_1047_status_canvas.pack(side=tk.LEFT, padx=(0, 5))
        self.rds_1047_status_canvas.create_oval(2, 2, 14, 14, fill='gray', outline='')

        ttk.Label(rds_1047_status_frame, text="RDS:", font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self.current_rds_1047_var = tk.StringVar(value="Waiting for first message...")
        rds_1047_label = ttk.Label(rds_1047_status_frame, textvariable=self.current_rds_1047_var, font=("Segoe UI", 10, "bold"), anchor=tk.W)
        rds_1047_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # RadioBoss connectivity indicator frame
        radioboss_1047_status_frame = ttk.Frame(rds_1047_frame)
        radioboss_1047_status_frame.pack(fill=tk.X, pady=(2, 0))

        self.radioboss_1047_status_canvas = tk.Canvas(radioboss_1047_status_frame, width=16, height=16, bg=self.cget('bg'), highlightthickness=0)
        self.radioboss_1047_status_canvas.pack(side=tk.LEFT, padx=(0, 5))
        self.radioboss_1047_status_canvas.create_oval(2, 2, 14, 14, fill='gray', outline='')

        ttk.Label(radioboss_1047_status_frame, text="RadioBoss:", font=("Segoe UI", 9)).pack(side=tk.LEFT)
        ttk.Label(radioboss_1047_status_frame, text="Connection Status", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 88.7 FM Current Message
        rds_887_frame = ttk.LabelFrame(rds_container, text="88.7 FM - Current RDS", padding="5")
        rds_887_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))

        # RDS Status indicator frame
        rds_887_status_frame = ttk.Frame(rds_887_frame)
        rds_887_status_frame.pack(fill=tk.X, pady=(0, 2))

        self.rds_887_status_canvas = tk.Canvas(rds_887_status_frame, width=16, height=16, bg=self.cget('bg'), highlightthickness=0)
        self.rds_887_status_canvas.pack(side=tk.LEFT, padx=(0, 5))
        self.rds_887_status_canvas.create_oval(2, 2, 14, 14, fill='gray', outline='')

        ttk.Label(rds_887_status_frame, text="RDS:", font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self.current_rds_887_var = tk.StringVar(value="Waiting for first message...")
        rds_887_label = ttk.Label(rds_887_status_frame, textvariable=self.current_rds_887_var, font=("Segoe UI", 10, "bold"), anchor=tk.W)
        rds_887_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # RadioBoss connectivity indicator frame
        radioboss_887_status_frame = ttk.Frame(rds_887_frame)
        radioboss_887_status_frame.pack(fill=tk.X, pady=(2, 0))

        self.radioboss_887_status_canvas = tk.Canvas(radioboss_887_status_frame, width=16, height=16, bg=self.cget('bg'), highlightthickness=0)
        self.radioboss_887_status_canvas.pack(side=tk.LEFT, padx=(0, 5))
        self.radioboss_887_status_canvas.create_oval(2, 2, 14, 14, fill='gray', outline='')

        ttk.Label(radioboss_887_status_frame, text="RadioBoss:", font=("Segoe UI", 9)).pack(side=tk.LEFT)
        ttk.Label(radioboss_887_status_frame, text="Connection Status", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, fill=tk.X, expand=True)

    def open_config_window(self):
        """Open the message configuration window."""
        ConfigWindow(self, self.config_manager)

    def open_missing_artists_window(self):
        MissingArtistsWindow(self, self.intro_1047_handler, self.intro_887_handler, self.config_manager)

    def open_options_window(self):
        OptionsWindow(self, self.config_manager,
                     self.intro_1047_handler, self.intro_887_handler,
                     self.rds_1047_handler, self.rds_887_handler,
                     self.ad_1047_handler, self.ad_887_handler)

    def open_playlist_editor_window(self):
        PlaylistEditorWindow(self, self.config_manager)

    def open_ad_inserter_window(self):
        """Open the ad inserter window with tabs for both stations."""
        AdInserterWindow(self, self.config_manager)

    def open_ad_statistics_window(self):
        """Open the ad statistics window with tabs for both stations."""
        from ui_ad_statistics_window import AdStatisticsWindow
        AdStatisticsWindow(self, self.config_manager)

    def process_queues(self):
        """Processes messages from all queues to update GUI."""
        # Collect messages for batch processing
        log_batches = {
            self.rds_1047_log_text: [],
            self.intro_1047_log_text: [],
            self.ad_1047_log_text: [],
            self.rds_887_log_text: [],
            self.intro_887_log_text: [],
            self.ad_887_log_text: []
        }

        updated = False

        # Station 1047 queues
        while not self.rds_1047_queue.empty():
            message = self.rds_1047_queue.get()
            log_batches[self.rds_1047_log_text].append(message)
            updated = True

        while not self.intro_1047_queue.empty():
            message = self.intro_1047_queue.get()
            log_batches[self.intro_1047_log_text].append(message)
            updated = True

        while not self.ad_1047_queue.empty():
            message = self.ad_1047_queue.get()
            log_batches[self.ad_1047_log_text].append(message)
            updated = True

        # Station 887 queues
        while not self.rds_887_queue.empty():
            message = self.rds_887_queue.get()
            log_batches[self.rds_887_log_text].append(message)
            updated = True

        while not self.intro_887_queue.empty():
            message = self.intro_887_queue.get()
            log_batches[self.intro_887_log_text].append(message)
            updated = True

        while not self.ad_887_queue.empty():
            message = self.ad_887_queue.get()
            log_batches[self.ad_887_log_text].append(message)
            updated = True

        # Batch update all log widgets
        if updated:
            for widget, messages in log_batches.items():
                if messages:
                    self._log_messages_batch(widget, messages)

            # Only auto-scroll if enabled (not paused by user scrolling)
            if self.auto_scroll_enabled:
                for widget in [self.rds_1047_log_text, self.intro_1047_log_text, self.ad_1047_log_text,
                               self.rds_887_log_text, self.intro_887_log_text, self.ad_887_log_text]:
                    widget.see(tk.END)

        self.after(500, self.process_queues)

    def _message_update_worker(self):
        """Background worker thread that periodically updates message cycles."""
        while self.message_update_running:
            try:
                # Update message cycles for both stations
                messages_1047 = self.rds_1047_handler.get_current_display_messages()
                messages_887 = self.rds_887_handler.get_current_display_messages()

                # Schedule UI update on main thread
                self.after(0, lambda: self._update_message_lists(messages_1047, messages_887))

                # Also update status indicators more frequently
                self.after(0, lambda: self._update_status_indicators())

            except Exception as e:
                logging.error(f"Error in message update worker: {e}")

            # Sleep for 5 seconds before next update
            time.sleep(5)

    def _connectivity_check_worker(self):
        """Background worker that periodically checks RadioBoss connectivity."""
        import socket
        from urllib.parse import urlparse
        
        while self.message_update_running:
            try:
                # Check Station 1047
                connected_1047 = self._do_connectivity_check('station_1047')
                # Check Station 887
                connected_887 = self._do_connectivity_check('station_887')
                
                # Update cached values thread-safely
                with self._connectivity_lock:
                    self._radioboss_1047_connected = connected_1047
                    self._radioboss_887_connected = connected_887
                    
            except Exception as e:
                logging.error(f"Error in connectivity check worker: {e}")
            
            # Check every 10 seconds (reasonable interval for connectivity monitoring)
            time.sleep(10)
    
    def _do_connectivity_check(self, station_id):
        """Perform the actual connectivity check (runs in background thread)."""
        import socket
        from urllib.parse import urlparse
        
        try:
            # Get the RadioBoss API server URL (e.g., "http://192.168.3.12:9000")
            server_url = self.config_manager.get_station_setting(station_id, "radioboss.server")

            # Parse the URL to extract IP and port
            parsed = urlparse(server_url)
            host = parsed.hostname
            port = parsed.port or 80  # Default to port 80 if not specified

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)  # 3 second timeout (reduced from 5)
            result = sock.connect_ex((host, port))
            sock.close()

            return result == 0  # 0 means connection successful
        except Exception as e:
            logging.debug(f"Connectivity check failed for {station_id}: {e}")
            return False

    def _update_status_indicators(self):
        """Update the status indicator circles for both stations."""
        try:
            # Station 1047
            status_1047 = self.rds_1047_handler.get_current_message_status()
            color_1047 = 'green' if status_1047['status'] == 'success' else 'red' if status_1047['status'] == 'timeout' else 'gray'
            self.rds_1047_status_canvas.itemconfig(1, fill=color_1047)

            if status_1047['message']:
                self.current_rds_1047_var.set(status_1047['message'])
        except Exception as e:
            self.rds_1047_status_canvas.itemconfig(1, fill='gray')
            logging.error(f"Error updating 1047 status indicator: {e}")

        try:
            # Station 887
            status_887 = self.rds_887_handler.get_current_message_status()
            color_887 = 'green' if status_887['status'] == 'success' else 'red' if status_887['status'] == 'timeout' else 'gray'
            self.rds_887_status_canvas.itemconfig(1, fill=color_887)

            if status_887['message']:
                self.current_rds_887_var.set(status_887['message'])
        except Exception as e:
            self.rds_887_status_canvas.itemconfig(1, fill='gray')
            logging.error(f"Error updating 887 status indicator: {e}")

        # Update RadioBoss connectivity indicators (using cached values from background thread)
        try:
            with self._connectivity_lock:
                connected_1047 = self._radioboss_1047_connected
            radioboss_1047_color = 'green' if connected_1047 else 'red' if connected_1047 is False else 'gray'
            self.radioboss_1047_status_canvas.itemconfig(1, fill=radioboss_1047_color)
        except Exception as e:
            self.radioboss_1047_status_canvas.itemconfig(1, fill='gray')
            logging.error(f"Error updating RadioBoss 1047 connectivity indicator: {e}")

        try:
            with self._connectivity_lock:
                connected_887 = self._radioboss_887_connected
            radioboss_887_color = 'green' if connected_887 else 'red' if connected_887 is False else 'gray'
            self.radioboss_887_status_canvas.itemconfig(1, fill=radioboss_887_color)
        except Exception as e:
            self.radioboss_887_status_canvas.itemconfig(1, fill='gray')
            logging.error(f"Error updating RadioBoss 887 connectivity indicator: {e}")

    def _update_message_lists(self, messages_1047, messages_887):
        """Update the message listboxes on the main thread."""
        try:
            # Station 1047
            self.msg_1047_listbox.delete(0, tk.END)
            if messages_1047:
                for msg in messages_1047:
                    self.msg_1047_listbox.insert(tk.END, msg)
            else:
                self.msg_1047_listbox.insert(tk.END, "(No messages)")
        except Exception as e:
            self.msg_1047_listbox.delete(0, tk.END)
            self.msg_1047_listbox.insert(tk.END, f"(Error: {e})")

        try:
            # Station 887
            self.msg_887_listbox.delete(0, tk.END)
            if messages_887:
                for msg in messages_887:
                    self.msg_887_listbox.insert(tk.END, msg)
            else:
                self.msg_887_listbox.insert(tk.END, "(No messages)")
        except Exception as e:
            self.msg_887_listbox.delete(0, tk.END)
            self.msg_887_listbox.insert(tk.END, f"(Error: {e})")

    def _log_messages_batch(self, widget, messages):
        """Insert multiple timestamped messages into the given text widget in a single operation."""
        if not messages:
            return

        widget.config(state=tk.NORMAL)
        for message in messages:
            timestamp = datetime.now().strftime('%I:%M:%S %p').lstrip('0').lower()
            widget.insert(tk.END, f"[{timestamp}] {message}\n")
        widget.config(state=tk.DISABLED)

    def _log_message(self, widget, message):
        """Insert a timestamped message into the given text widget."""
        self._log_messages_batch(widget, [message])

    def _pause_scroll(self):
        """Pause auto-scrolling of log widgets."""
        self.auto_scroll_enabled = False

    def _jump_to_bottom(self):
        """Scroll all log widgets to the bottom and re-enable auto-scroll."""
        self.auto_scroll_enabled = True
        for widget in [self.rds_1047_log_text, self.intro_1047_log_text, self.ad_1047_log_text,
                       self.rds_887_log_text, self.intro_887_log_text, self.ad_887_log_text]:
            widget.see(tk.END)

if __name__ == "__main__":
    app = MainApp()
    app.mainloop()
