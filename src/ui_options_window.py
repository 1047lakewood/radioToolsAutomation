
import tkinter as tk
from tkinter import ttk, messagebox, Toplevel, filedialog
import logging

# Placeholders for managers/handlers if needed directly (passed in constructor)
# from config_manager import ConfigManager
# from intro_loader_handler import IntroLoaderHandler

class OptionsWindow(Toplevel):
    """Window for application options (Whitelist, Blacklist, Debug)."""
    def __init__(self, parent, config_manager, intro_loader_handler):
        super().__init__(parent)
        self.transient(parent)
        self.grab_set()
        self.title("Options")
        self.geometry("600x450") # Adjust size as needed

        self.config_manager = config_manager
        self.intro_loader_handler = intro_loader_handler

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
        touch_help = ttk.Label(debug_frame, text="Updates the XML file's modification time to force the Intro Loader to re-check it.", wraplength=380)
        touch_help.pack(pady=2)

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
        self.loader_url_var = tk.StringVar(value=self.config_manager.get_setting("settings.intro_loader.schedule_url", "http://192.168.3.11:9000/?pass=bmas220&action=schedule&type=run&id=TBACFNBGJKOMETDYSQYR"))
        ttk.Entry(loader_frame, textvariable=self.loader_url_var, width=40).grid(row=3, column=1, sticky=tk.W, padx=5)

        # --- Ad Inserter Settings Section ---
        ad_label = ttk.Label(settings_frame, text="Ad Inserter Settings", font=("Segoe UI", 10, "bold"))
        ad_label.pack(anchor=tk.W, pady=(10,5))

        ad_frame = ttk.Frame(settings_frame)
        ad_frame.pack(fill=tk.X, pady=5)

        ttk.Label(ad_frame, text="Insertion URL:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.ad_url_var = tk.StringVar(value=self.config_manager.get_setting("settings.ad_inserter.insertion_url", "http://localhost:8000/insert"))
        ttk.Entry(ad_frame, textvariable=self.ad_url_var, width=40).grid(row=0, column=1, sticky=tk.W, padx=5)

        ttk.Label(ad_frame, text="New Ad MP3:").grid(row=1, column=0, sticky=tk.W, padx=5)
        self.ad_mp3_var = tk.StringVar(value=self.config_manager.get_setting("settings.ad_inserter.output_mp3", r"G:\Ads\newAd.mp3"))
        ttk.Entry(ad_frame, textvariable=self.ad_mp3_var, width=40).grid(row=1, column=1, sticky=tk.W, padx=5)
        ttk.Button(ad_frame, text="Browse", command=lambda: self.browse_file(self.ad_mp3_var)).grid(row=1, column=2, padx=5)

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
        self.config_manager.update_setting("settings.ad_inserter.output_mp3", self.ad_mp3_var.get())

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