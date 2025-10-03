#  --- Ad Inserter Settings Section ---.*?ttk.Button(ad_frame, text="Browse".*?
import tkinter as tk
from tkinter import ttk, messagebox, Toplevel, filedialog
import logging
import urllib.request
import xml.etree.ElementTree as ET

from ad_inserter_service import AdInserterService

# Placeholders for managers/handlers if needed directly (passed in constructor)
# from config_manager import ConfigManager
# from intro_loader_handler import IntroLoaderHandler

class OptionsWindow(Toplevel):
    """Window for application options (Whitelist, Blacklist, Debug)."""
    def __init__(self, parent, config_manager, intro_loader_handler, auto_rds_handler=None, ad_scheduler_handler=None):
        super().__init__(parent)
        self.transient(parent)
        self.grab_set()
        self.title("Options")
        self.geometry("750x700")  # Open larger so all settings are visible

        self.config_manager = config_manager
        self.intro_loader_handler = intro_loader_handler
        self.auto_rds_handler = auto_rds_handler
        self.ad_scheduler_handler = ad_scheduler_handler

        # Store initial lists to detect changes
        self.initial_whitelist = self.config_manager.get_whitelist().copy()
        self.initial_blacklist = self.config_manager.get_blacklist().copy()
        self.changes_pending = False # Track if lists were modified

        self.create_widgets()

        self.protocol("WM_DELETE_WINDOW", self.on_close)


    def create_widgets(self):
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=5)

        # --- Whitelist Tab ---
        whitelist_frame = ttk.Frame(notebook, padding="10")
        notebook.add(whitelist_frame, text="Artist Whitelist")
        self.whitelist_listbox = self.create_list_editor(
            whitelist_frame,
            "Whitelist",
            self.initial_whitelist # Pass initial list
        )

        # --- Blacklist Tab ---
        blacklist_frame = ttk.Frame(notebook, padding="10")
        notebook.add(blacklist_frame, text="Artist Blacklist")
        self.blacklist_listbox = self.create_list_editor(
            blacklist_frame,
            "Blacklist",
            self.initial_blacklist # Pass initial list
        )

        # --- Debug Tab (Re-added) ---
        debug_frame = ttk.Frame(notebook, padding="10")
        notebook.add(debug_frame, text="Debug")
        debug_label = ttk.Label(debug_frame, text="Debug Tools", font=("Segoe UI", 10, "bold"))
        debug_label.pack(pady=(0,10))

        # Add button to "touch" the XML file
        touch_button = ttk.Button(debug_frame, text="Touch XML File", command=self.touch_xml_file_action)
        touch_button.pack(pady=5)
        touch_help = ttk.Label(
            debug_frame,
            text="Updates the XML file's modification time to force the Intro Loader to re-check it.",
            wraplength=380,
        )
        touch_help.pack(pady=2)

        # Button to combine ads and trigger the ad inserter URL
        ad_button = ttk.Button(debug_frame, text="Run Ad Service", command=self.run_ad_service_action)
        ad_button.pack(pady=5)
        ad_help = ttk.Label(
            debug_frame,
            text="Combine enabled ads into one MP3 and call the ad inserter URL.",
            wraplength=380,
        )
        ad_help.pack(pady=2)

        # Button to instantly play ads via the instant URL
        instant_button = ttk.Button(debug_frame, text="Play Ad Now", command=self.run_instant_ad_service_action)
        instant_button.pack(pady=5)
        instant_help = ttk.Label(
            debug_frame,
            text="Combine enabled ads and trigger immediate playback.",
            wraplength=380,
        )
        instant_help.pack(pady=2)

        # Button to simulate start of hour for AdScheduler testing
        hour_button = ttk.Button(debug_frame, text="Simulate Hour Start", command=self.simulate_hour_start)
        hour_button.pack(pady=5)
        hour_help = ttk.Label(
            debug_frame,
            text="Triggers the AdScheduler's hourly check logic to test ad insertion timing.",
            wraplength=380,
        )
        hour_help.pack(pady=2)

        # Separator
        ttk.Separator(debug_frame, orient='horizontal').pack(fill=tk.X, pady=10)

        # Logging Level Controls
        logging_label = ttk.Label(debug_frame, text="Logging Level", font=("Segoe UI", 10, "bold"))
        logging_label.pack(pady=(5, 10))

        self.enable_debug_logs_var = tk.BooleanVar(
            value=self.config_manager.get_setting("settings.debug.enable_debug_logs", False)
        )
        
        debug_checkbox = ttk.Checkbutton(
            debug_frame,
            text="Enable Debug Logs (Shows detailed DEBUG messages)",
            variable=self.enable_debug_logs_var,
            command=self.toggle_debug_logging
        )
        debug_checkbox.pack(pady=5)
        
        debug_note = ttk.Label(
            debug_frame,
            text="Note: Debug logs provide detailed information useful for troubleshooting.\nDisabling this will only show INFO, WARNING, and ERROR messages.",
            wraplength=380,
            foreground="gray"
        )
        debug_note.pack(pady=2)

        # --- Settings Tab (New) ---
        settings_frame = ttk.Frame(notebook, padding="10")
        notebook.add(settings_frame, text="Settings")

        # RDS Settings Section
        rds_label = ttk.Label(settings_frame, text="RDS Settings", font=("Segoe UI", 10, "bold"))
        rds_label.pack(anchor=tk.W, pady=(0,5))

        rds_frame = ttk.Frame(settings_frame)
        rds_frame.pack(fill=tk.X, pady=5)

        # RDS IP
        ttk.Label(rds_frame, text="RDS IP:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.rds_ip_var = tk.StringVar(value=self.config_manager.get_setting("settings.rds.ip", "50.208.125.83"))
        ttk.Entry(rds_frame, textvariable=self.rds_ip_var, width=40).grid(row=0, column=1, sticky=tk.W, padx=5)

        # RDS Port
        ttk.Label(rds_frame, text="RDS Port:").grid(row=1, column=0, sticky=tk.W, padx=5)
        self.rds_port_var = tk.IntVar(value=self.config_manager.get_setting("settings.rds.port", 10001))
        ttk.Entry(rds_frame, textvariable=self.rds_port_var, width=40).grid(row=1, column=1, sticky=tk.W, padx=5)

        # Now Playing XML
        ttk.Label(rds_frame, text="Now Playing XML:").grid(row=2, column=0, sticky=tk.W, padx=5)
        self.rds_xml_var = tk.StringVar(value=self.config_manager.get_setting("settings.rds.now_playing_xml", r"G:\To_RDS\nowplaying.xml"))
        ttk.Entry(rds_frame, textvariable=self.rds_xml_var, width=40).grid(row=2, column=1, sticky=tk.W, padx=5)
        ttk.Button(rds_frame, text="Browse", command=lambda: self.browse_file(self.rds_xml_var)).grid(row=2, column=2, padx=5)

        # Default Message
        ttk.Label(rds_frame, text="Default Message:").grid(row=3, column=0, sticky=tk.W, padx=5)
        self.rds_default_var = tk.StringVar(value=self.config_manager.get_setting("settings.rds.default_message", "732.901.7777 to SUPPORT and hear this program!"))
        ttk.Entry(rds_frame, textvariable=self.rds_default_var, width=40).grid(row=3, column=1, sticky=tk.W, padx=5)

        # Intro Loader Settings Section
        loader_label = ttk.Label(settings_frame, text="Intro Loader Settings", font=("Segoe UI", 10, "bold"))
        loader_label.pack(anchor=tk.W, pady=(10,5))

        loader_frame = ttk.Frame(settings_frame)
        loader_frame.pack(fill=tk.X, pady=5)

        # Now Playing XML (shared with RDS, but allow separate if needed)
        ttk.Label(loader_frame, text="Now Playing XML:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.loader_xml_var = tk.StringVar(value=self.config_manager.get_setting("settings.intro_loader.now_playing_xml", r"G:\To_RDS\nowplaying.xml"))
        ttk.Entry(loader_frame, textvariable=self.loader_xml_var, width=40).grid(row=0, column=1, sticky=tk.W, padx=5)
        ttk.Button(loader_frame, text="Browse", command=lambda: self.browse_file(self.loader_xml_var)).grid(row=0, column=2, padx=5)

        # MP3 Directory
        ttk.Label(loader_frame, text="MP3 Directory:").grid(row=1, column=0, sticky=tk.W, padx=5)
        self.loader_mp3_dir_var = tk.StringVar(value=self.config_manager.get_setting("settings.intro_loader.mp3_directory", r"G:\Shiurim\introsCleanedUp"))
        ttk.Entry(loader_frame, textvariable=self.loader_mp3_dir_var, width=40).grid(row=1, column=1, sticky=tk.W, padx=5)
        ttk.Button(loader_frame, text="Browse", command=lambda: self.browse_directory(self.loader_mp3_dir_var)).grid(row=1, column=2, padx=5)

        # Missing Artists Log
        ttk.Label(loader_frame, text="Missing Artists Log:").grid(row=2, column=0, sticky=tk.W, padx=5)
        self.loader_log_var = tk.StringVar(value=self.config_manager.get_setting("settings.intro_loader.missing_artists_log", r"G:\Misc\Dev\CombinedRDSApp\missing_artists.log"))
        ttk.Entry(loader_frame, textvariable=self.loader_log_var, width=40).grid(row=2, column=1, sticky=tk.W, padx=5)
        ttk.Button(loader_frame, text="Browse", command=lambda: self.browse_file(self.loader_log_var, save=True)).grid(row=2, column=2, padx=5)

        # Schedule URL
        ttk.Label(loader_frame, text="Schedule URL:").grid(row=3, column=0, sticky=tk.W, padx=5)
        self.loader_url_var = tk.StringVar(
            value=self.config_manager.get_setting(
                "settings.intro_loader.schedule_url",
                "http://192.168.3.11:9000/?pass=bmas220&action=schedule&type=run&id=TBACFNBGJKOMETDYSQYR",
            )
        )
        ttk.Entry(loader_frame, textvariable=self.loader_url_var, width=40).grid(row=3, column=1, sticky=tk.W, padx=5)

        # --- Ad Settings Tab ---
        ads_tab = ttk.Frame(notebook, padding="10")
        notebook.add(ads_tab, text="Ad Settings")

        ad_label = ttk.Label(ads_tab, text="Ad Inserter Settings", font=("Segoe UI", 10, "bold"))
        ad_label.pack(anchor=tk.W, pady=(0,5))

        ad_frame = ttk.Frame(ads_tab)
        ad_frame.pack(fill=tk.X, pady=5)

        ttk.Label(ad_frame, text="Schedule URL:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.ad_url_var = tk.StringVar(value=self.config_manager.get_setting("settings.ad_inserter.insertion_url", "http://localhost:8000/insert"))
        ttk.Entry(ad_frame, textvariable=self.ad_url_var, width=40).grid(row=0, column=1, sticky=tk.W, padx=5)

        ttk.Label(ad_frame, text="Instant URL:").grid(row=1, column=0, sticky=tk.W, padx=5)
        self.ad_instant_url_var = tk.StringVar(value=self.config_manager.get_setting("settings.ad_inserter.instant_url", "http://localhost:8000/play"))
        ttk.Entry(ad_frame, textvariable=self.ad_instant_url_var, width=40).grid(row=1, column=1, sticky=tk.W, padx=5)

        ttk.Label(ad_frame, text="New Ad MP3:").grid(row=2, column=0, sticky=tk.W, padx=5)
        self.ad_mp3_var = tk.StringVar(value=self.config_manager.get_setting("settings.ad_inserter.output_mp3", r"G:\\Ads\\newAd.mp3"))
        ttk.Entry(ad_frame, textvariable=self.ad_mp3_var, width=40).grid(row=2, column=1, sticky=tk.W, padx=5)
        ttk.Button(ad_frame, text="Browse", command=lambda: self.browse_file(self.ad_mp3_var)).grid(row=2, column=2, padx=5)

        # Separator
        ttk.Separator(ads_tab, orient='horizontal').pack(fill=tk.X, pady=10)

        # mAirList Event Fetcher Section
        events_label = ttk.Label(ads_tab, text="mAirList Events", font=("Segoe UI", 10, "bold"))
        events_label.pack(anchor=tk.W, pady=(5,5))

        events_help = ttk.Label(
            ads_tab,
            text="Fetch events from mAirList to easily get event IDs for the URLs above.",
            wraplength=700,
            foreground="gray"
        )
        events_help.pack(anchor=tk.W, pady=(0,5))

        # Server configuration
        server_frame = ttk.Frame(ads_tab)
        server_frame.pack(fill=tk.X, pady=5)

        ttk.Label(server_frame, text="Server:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.mairlist_server_var = tk.StringVar(value=self.config_manager.get_setting("settings.mairlist.server", "localhost:9000"))
        ttk.Entry(server_frame, textvariable=self.mairlist_server_var, width=30).grid(row=0, column=1, sticky=tk.W, padx=5)

        ttk.Label(server_frame, text="Password:").grid(row=0, column=2, sticky=tk.W, padx=(20,5))
        self.mairlist_password_var = tk.StringVar(value=self.config_manager.get_setting("settings.mairlist.password", "bmas220"))
        ttk.Entry(server_frame, textvariable=self.mairlist_password_var, width=20, show="*").grid(row=0, column=3, sticky=tk.W, padx=5)

        ttk.Button(server_frame, text="Fetch Events", command=self.fetch_mairlist_events).grid(row=0, column=4, padx=(20,5))

        # Events list
        events_list_frame = ttk.Frame(ads_tab)
        events_list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # Create Treeview with columns
        columns = ("Task Name", "Event ID", "Enabled", "Type")
        self.events_tree = ttk.Treeview(events_list_frame, columns=columns, show="headings", height=8)
        
        self.events_tree.heading("Task Name", text="Task Name")
        self.events_tree.heading("Event ID", text="Event ID")
        self.events_tree.heading("Enabled", text="Enabled")
        self.events_tree.heading("Type", text="Type")
        
        self.events_tree.column("Task Name", width=200)
        self.events_tree.column("Event ID", width=200)
        self.events_tree.column("Enabled", width=70)
        self.events_tree.column("Type", width=100)

        # Scrollbar for tree
        tree_scrollbar = ttk.Scrollbar(events_list_frame, orient=tk.VERTICAL, command=self.events_tree.yview)
        self.events_tree.configure(yscrollcommand=tree_scrollbar.set)
        
        self.events_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Buttons for actions
        events_button_frame = ttk.Frame(ads_tab)
        events_button_frame.pack(fill=tk.X, pady=5)

        ttk.Button(events_button_frame, text="Set as Scheduled URL", command=self.set_as_scheduled_url).pack(side=tk.LEFT, padx=5)
        ttk.Button(events_button_frame, text="Set as Instant URL", command=self.set_as_instant_url).pack(side=tk.LEFT, padx=5)
        ttk.Button(events_button_frame, text="Copy URL to Clipboard", command=self.copy_event_url).pack(side=tk.LEFT, padx=5)

        # --- Bottom Buttons ---
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(button_frame, text="Save & Close", command=self.save_and_close).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.on_close).pack(side=tk.RIGHT, padx=5)

    def browse_file(self, var, save=False):
        """Opens a file dialog to select a file path and sets the variable."""
        if save:
            path = filedialog.asksaveasfilename(title="Select File", defaultextension=".log")
        else:
            path = filedialog.askopenfilename(title="Select File")
        if path:
            var.set(path)

    def browse_directory(self, var):
        """Opens a directory dialog to select a folder path and sets the variable."""
        path = filedialog.askdirectory(title="Select Directory")
        if path:
            var.set(path)

    def create_list_editor(self, parent_frame, list_name, initial_list):
        """Helper to create the listbox, entry, and buttons for Whitelist/Blacklist."""
        ttk.Label(parent_frame, text=f"Enter artist name exactly as it appears in XML (case-insensitive match):").pack(anchor=tk.W)

        list_container = ttk.Frame(parent_frame)
        list_container.pack(fill=tk.BOTH, expand=True, pady=5)

        # Listbox with Scrollbar
        listbox_frame = ttk.Frame(list_container)
        listbox_frame.pack(fill=tk.BOTH, expand=True, side=tk.LEFT, padx=(0, 5))

        scrollbar = ttk.Scrollbar(listbox_frame, orient=tk.VERTICAL)
        listbox = tk.Listbox(listbox_frame, yscrollcommand=scrollbar.set, exportselection=False, height=10)
        scrollbar.config(command=listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Populate Listbox
        for item in initial_list:
            listbox.insert(tk.END, item)

        # Entry and Buttons Frame
        entry_button_frame = ttk.Frame(list_container)
        entry_button_frame.pack(fill=tk.Y, side=tk.LEFT)

        entry_var = tk.StringVar()
        entry = ttk.Entry(entry_button_frame, textvariable=entry_var, width=30)
        entry.pack(pady=(0, 5))

        def mark_change_flag():
            self.changes_pending = True

        def add_item():
            item = entry_var.get().strip()
            if item and item not in listbox.get(0, tk.END):
                listbox.insert(tk.END, item)
                entry_var.set("")
                mark_change_flag() # Mark changes when item added
        ttk.Button(entry_button_frame, text="Add", command=add_item).pack(fill=tk.X, pady=2)

        def delete_item():
            selected_indices = listbox.curselection()
            if selected_indices:
                # Delete from bottom up to avoid index issues
                for i in reversed(selected_indices):
                    listbox.delete(i)
                mark_change_flag() # Mark changes when item deleted
        ttk.Button(entry_button_frame, text="Delete", command=delete_item).pack(fill=tk.X, pady=2)

        # Return the listbox widget so it can be accessed for saving
        return listbox

    def touch_xml_file_action(self):
        """Calls the handler method to touch the XML file, without confirmation."""
        logging.debug("Touch XML File button clicked.")
        try:
            # Call the new method in the handler
            success = self.intro_loader_handler.touch_monitored_xml()
            if success:
                logging.info("Debug touch XML successful via Options window.")
                # Optionally provide non-modal feedback, e.g., update a status label if one existed here
            else:
                logging.error("Debug touch XML failed via Options window. Check logs.")
                # Optionally show error, but user requested no alerts
        except Exception as e:
             logging.exception("Exception calling touch_monitored_xml.")
             # Avoid showing error popup as requested

    def run_ad_service_action(self):
        """Combine ads and trigger the ad inserter URL."""
        logging.debug("Run Ad Service button clicked.")
        try:
            service = AdInserterService(self.config_manager)
            success = service.run()
            if success:
                logging.info("Ad service executed successfully via Options window.")
            else:
                logging.error("Ad service failed via Options window. Check logs.")
        except Exception:
            logging.exception("Exception running AdInserterService.")

    def run_instant_ad_service_action(self):
        """Combine ads and trigger the instant ad URL."""
        logging.debug("Play Ad Now button clicked.")
        try:
            service = AdInserterService(self.config_manager)
            success = service.run_instant()
            if success:
                logging.info("Instant ad executed successfully via Options window.")
            else:
                logging.error("Instant ad failed via Options window. Check logs.")
        except Exception:
            logging.exception("Exception running AdInserterService instant.")

    def simulate_hour_start(self):
        """Simulate the start of an hour for AdScheduler testing."""
        logging.debug("Simulate Hour Start button clicked.")
        try:
            if self.ad_scheduler_handler:
                # Trigger the hourly check logic
                self.ad_scheduler_handler._perform_hourly_check()
                logging.info("AdScheduler hourly check triggered successfully.")
            else:
                logging.error("AdScheduler handler not available.")
                messagebox.showerror("Error", "AdScheduler handler not available.", parent=self)
        except Exception as e:
            logging.exception("Exception triggering AdScheduler hourly check.")
            messagebox.showerror("Error", f"Failed to trigger AdScheduler check:\n{e}", parent=self)

    def toggle_debug_logging(self):
        """Toggle debug logging on or off immediately."""
        enable_debug = self.enable_debug_logs_var.get()
        
        # Set logging level for all loggers
        log_level = logging.DEBUG if enable_debug else logging.INFO
        
        # Update root logger
        logging.getLogger().setLevel(log_level)
        
        # Update specific loggers
        logging.getLogger('AutoRDS').setLevel(log_level)
        logging.getLogger('IntroLoader').setLevel(log_level)
        logging.getLogger('AdScheduler').setLevel(log_level)
        logging.getLogger('AdService').setLevel(log_level)
        logging.getLogger('AdPlayLogger').setLevel(log_level)
        logging.getLogger('AdStatisticsUI').setLevel(log_level)
        
        status = "enabled" if enable_debug else "disabled"
        logging.info(f"Debug logging {status}")
        
        # Save setting to config
        self.config_manager.update_setting("settings.debug.enable_debug_logs", enable_debug)
        try:
            self.config_manager.save_config()
        except Exception as e:
            logging.error(f"Failed to save debug logging setting: {e}")

    def fetch_mairlist_events(self):
        """Fetch events from mAirList server and display them."""
        server = self.mairlist_server_var.get().strip()
        password = self.mairlist_password_var.get().strip()

        if not server:
            messagebox.showerror("Error", "Please enter mAirList server address.", parent=self)
            return

        # Build the URL
        if not server.startswith("http://") and not server.startswith("https://"):
            server = f"http://{server}"
        
        url = f"{server}/?pass={password}&action=schedule&type=list"

        try:
            logging.info(f"Fetching mAirList events from: {url}")
            
            # Fetch the XML
            with urllib.request.urlopen(url, timeout=10) as response:
                xml_data = response.read().decode('utf-8')
            
            # Parse the XML
            root = ET.fromstring(xml_data)
            
            # Clear existing items
            for item in self.events_tree.get_children():
                self.events_tree.delete(item)
            
            # Parse events
            event_count = 0
            for item in root.findall('item'):
                task_name = item.get('TaskName', '(No Name)')
                event_id = item.get('Id', '')
                enabled = item.get('EnabledEvent', 'False')
                is_immediate = item.get('Imm', 'False') == 'True'
                
                # Determine type
                if is_immediate:
                    event_type = "Immediate"
                else:
                    event_type = "Scheduled"
                
                # Only show events with task names and IDs
                if event_id:
                    self.events_tree.insert('', tk.END, values=(task_name, event_id, enabled, event_type))
                    event_count += 1
            
            logging.info(f"Successfully fetched {event_count} events from mAirList")
            messagebox.showinfo("Success", f"Fetched {event_count} events from mAirList.", parent=self)
            
            # Save server settings
            self.config_manager.update_setting("settings.mairlist.server", self.mairlist_server_var.get())
            self.config_manager.update_setting("settings.mairlist.password", self.mairlist_password_var.get())
            
        except urllib.error.URLError as e:
            logging.error(f"Failed to fetch mAirList events: {e}")
            messagebox.showerror("Connection Error", f"Failed to connect to mAirList:\n{e}", parent=self)
        except ET.ParseError as e:
            logging.error(f"Failed to parse mAirList XML: {e}")
            messagebox.showerror("Parse Error", f"Failed to parse response from mAirList:\n{e}", parent=self)
        except Exception as e:
            logging.exception("Error fetching mAirList events")
            messagebox.showerror("Error", f"An error occurred:\n{e}", parent=self)

    def get_selected_event_url(self):
        """Get the URL for the selected event."""
        selection = self.events_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an event from the list.", parent=self)
            return None
        
        item = self.events_tree.item(selection[0])
        values = item['values']
        event_id = values[1]  # Event ID is in column 1
        
        # Build URL
        server = self.mairlist_server_var.get().strip()
        password = self.mairlist_password_var.get().strip()
        
        if not server.startswith("http://") and not server.startswith("https://"):
            server = f"http://{server}"
        
        url = f"{server}/?pass={password}&action=schedule&type=run&id={event_id}"
        return url

    def set_as_scheduled_url(self):
        """Set the selected event as the scheduled URL."""
        url = self.get_selected_event_url()
        if url:
            self.ad_url_var.set(url)
            selection = self.events_tree.selection()
            item = self.events_tree.item(selection[0])
            task_name = item['values'][0]
            logging.info(f"Set scheduled URL to event: {task_name}")
            messagebox.showinfo("URL Set", f"Scheduled URL set to:\n{task_name}", parent=self)

    def set_as_instant_url(self):
        """Set the selected event as the instant URL."""
        url = self.get_selected_event_url()
        if url:
            self.ad_instant_url_var.set(url)
            selection = self.events_tree.selection()
            item = self.events_tree.item(selection[0])
            task_name = item['values'][0]
            logging.info(f"Set instant URL to event: {task_name}")
            messagebox.showinfo("URL Set", f"Instant URL set to:\n{task_name}", parent=self)

    def copy_event_url(self):
        """Copy the selected event URL to clipboard."""
        url = self.get_selected_event_url()
        if url:
            self.clipboard_clear()
            self.clipboard_append(url)
            self.update()  # Required for clipboard to work
            
            selection = self.events_tree.selection()
            item = self.events_tree.item(selection[0])
            task_name = item['values'][0]
            logging.info(f"Copied URL for event: {task_name}")
            messagebox.showinfo("Copied", f"URL copied to clipboard:\n{task_name}", parent=self)

    def save_and_close(self):
        """Saves the whitelist/blacklist if changed and closes."""
        # Get current lists from listboxes
        new_whitelist = list(self.whitelist_listbox.get(0, tk.END))
        new_blacklist = list(self.blacklist_listbox.get(0, tk.END))

        # Check if changes were actually made (or if flag was set)
        if self.changes_pending or new_whitelist != self.initial_whitelist or new_blacklist != self.initial_blacklist:
            try:
                self.config_manager.set_whitelist(new_whitelist)
                self.config_manager.set_blacklist(new_blacklist)
                self.config_manager.save_config()
                logging.info("Whitelist/Blacklist changes saved.")
                messagebox.showinfo("Saved", "Whitelist/Blacklist settings saved.", parent=self)
                self.changes_pending = False # Reset flag after successful save
            except Exception as e:
                 logging.exception("Failed to save Whitelist/Blacklist.")
                 messagebox.showerror("Save Error", f"Failed to save settings:\n{e}", parent=self)
                 return # Don't close if save failed

        # Save settings from the new tab
        self.config_manager.update_setting("settings.rds.ip", self.rds_ip_var.get())
        self.config_manager.update_setting("settings.rds.port", self.rds_port_var.get())
        self.config_manager.update_setting("settings.rds.now_playing_xml", self.rds_xml_var.get())
        self.config_manager.update_setting("settings.rds.default_message", self.rds_default_var.get())
        self.config_manager.update_setting("settings.intro_loader.now_playing_xml", self.loader_xml_var.get())
        self.config_manager.update_setting("settings.intro_loader.mp3_directory", self.loader_mp3_dir_var.get())
        self.config_manager.update_setting("settings.intro_loader.missing_artists_log", self.loader_log_var.get())
        self.config_manager.update_setting("settings.intro_loader.schedule_url", self.loader_url_var.get())
        self.config_manager.update_setting("settings.ad_inserter.insertion_url", self.ad_url_var.get())
        self.config_manager.update_setting("settings.ad_inserter.instant_url", self.ad_instant_url_var.get())
        self.config_manager.update_setting("settings.ad_inserter.output_mp3", self.ad_mp3_var.get())

        # Save all settings changes to file
        try:
            self.config_manager.save_config()
            logging.info("Settings changes saved.")
        except Exception as e:
            logging.exception("Failed to save settings.")
            messagebox.showerror("Save Error", f"Failed to save settings:\n{e}", parent=self)
            return # Don't close if save failed

        # Reload configuration in handlers to apply changes immediately
        try:
            self.intro_loader_handler.reload_configuration()
            logging.info("Intro Loader configuration reloaded.")
        except Exception as e:
            logging.warning(f"Failed to reload Intro Loader configuration: {e}")

        if self.auto_rds_handler:
            try:
                self.auto_rds_handler.reload_configuration()
                self.auto_rds_handler.reload_lecture_detector()
                logging.info("RDS Handler configuration reloaded.")
            except Exception as e:
                logging.warning(f"Failed to reload RDS Handler configuration: {e}")

        self.destroy()

    def on_close(self):
        """Checks for unsaved changes on close."""
        new_whitelist = list(self.whitelist_listbox.get(0, tk.END))
        new_blacklist = list(self.blacklist_listbox.get(0, tk.END))

        # Check flag first, then compare lists as backup
        if self.changes_pending or new_whitelist != self.initial_whitelist or new_blacklist != self.initial_blacklist:
            response = messagebox.askyesnocancel("Unsaved Changes", "Whitelist or Blacklist has been modified. Save changes before closing?", parent=self)
            if response is True: # Yes
                self.save_and_close()
            elif response is False: # No
                self.destroy() # Close without saving
            # else: Cancel, do nothing
        else:
            self.destroy() # No changes, just close

# Example usage for testing
if __name__ == "__main__":
    print("This script defines the OptionsWindow UI component.")
    # root = tk.Tk()
    # class MockConfig: # Define mocks if needed for standalone testing
    #     def get_whitelist(self): return ["Artist A"]
    #     def get_blacklist(self): return ["Artist B"]
    #     def set_whitelist(self, l): pass
    #     def set_blacklist(self, l): pass
    #     def save_config(self): print("Mock Save")
    # class MockLoader:
    #     def trigger_xml_change(self): print("Mock Trigger XML"); return True
    # mock_cfg = MockConfig()
    # mock_ldr = MockLoader()
    # OptionsWindow(root, mock_cfg, mock_ldr)
    # root.mainloop()