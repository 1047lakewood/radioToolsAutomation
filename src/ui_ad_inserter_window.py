import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import logging
import os
import copy

class AdInserterWindow(tk.Toplevel):
    """Dialog for configuring advertisement insertions."""
    def __init__(self, parent, config_manager):
        super().__init__(parent)
        self.transient(parent)
        self.grab_set()
        self.title("Ad Inserter")
        self.geometry("800x600")
        self.minsize(700, 500)

        self.config_manager = config_manager
        self.ads = copy.deepcopy(self.config_manager.get_ads() or [])  # Assume get_ads() method in ConfigManager
        self.initial_ads = copy.deepcopy(self.ads)  # For detecting changes
        self.current_index = None

        self.create_widgets()
        self.populate_ad_list()

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Left: Ad List
        left_frame = ttk.LabelFrame(main_frame, text="Advertisements", padding="5")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 10))

        self.ad_listbox = tk.Listbox(left_frame, width=30, height=20, font=("Segoe UI", 10))
        self.ad_listbox.pack(fill=tk.BOTH, expand=True)
        self.ad_listbox.bind("<<ListboxSelect>>", self.on_ad_select)

        # Buttons for list management
        list_buttons = ttk.Frame(left_frame)
        list_buttons.pack(fill=tk.X, pady=5)
        ttk.Button(list_buttons, text="Add New", command=self.add_new_ad).pack(side=tk.LEFT, padx=2)
        ttk.Button(list_buttons, text="Delete", command=self.delete_ad).pack(side=tk.LEFT, padx=2)

        # Right: Options
        right_frame = ttk.LabelFrame(main_frame, text="Ad Details", padding="5")
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Name
        name_label = ttk.Label(right_frame, text="Name:", font=("Segoe UI", 10, "bold"))
        name_label.grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_var = tk.StringVar()
        ttk.Entry(right_frame, textvariable=self.name_var, width=50, font=("Segoe UI", 10)).grid(row=0, column=1, sticky=tk.W, pady=5, padx=5)

        # Enabled
        self.enabled_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(right_frame, text="Enabled", variable=self.enabled_var, style="Toggle.TCheckbutton").grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=5)

        # MP3 File
        mp3_label = ttk.Label(right_frame, text="MP3 File:", font=("Segoe UI", 10, "bold"))
        mp3_label.grid(row=2, column=0, sticky=tk.W, pady=5)
        self.mp3_var = tk.StringVar()
        ttk.Entry(right_frame, textvariable=self.mp3_var, width=40, font=("Segoe UI", 10)).grid(row=2, column=1, sticky=tk.W, pady=5, padx=5)
        ttk.Button(right_frame, text="Browse", command=self.browse_mp3).grid(row=2, column=2, sticky=tk.W, pady=5)

        # Scheduled
        self.scheduled_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(right_frame, text="Scheduled", variable=self.scheduled_var, command=self.toggle_schedule, style="Toggle.TCheckbutton").grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=5)

        # Days
        days_label = ttk.Label(right_frame, text="Days:", font=("Segoe UI", 10, "bold"))
        days_label.grid(row=4, column=0, sticky=tk.W, pady=5)
        days_frame = ttk.Frame(right_frame)
        days_frame.grid(row=4, column=1, columnspan=2, sticky=tk.W, pady=5)
        self.day_vars = {}
        days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        for i, day in enumerate(days):
            self.day_vars[day] = tk.BooleanVar()
            ttk.Checkbutton(days_frame, text=day[:3], variable=self.day_vars[day]).pack(side=tk.LEFT, padx=2)

        # Hours
        hours_label = ttk.Label(right_frame, text="Hours:", font=("Segoe UI", 10, "bold"))
        hours_label.grid(row=5, column=0, sticky=tk.NW, pady=5)
        hours_frame = ttk.Frame(right_frame)
        hours_frame.grid(row=5, column=1, columnspan=2, sticky=tk.W, pady=5)
        self.hour_vars = {}
        for h in range(24):
            self.hour_vars[h] = tk.BooleanVar()
            row, col = divmod(h, 6)
            ttk.Checkbutton(hours_frame, text=f"{h:02d}", variable=self.hour_vars[h], width=4).grid(row=row, column=col, padx=2, pady=2)

        # Only widgets that support the ``state`` option should be toggled.
        # Frames themselves do not have a ``state`` attribute, which caused a
        # ``TclError`` when ``toggle_schedule`` attempted to configure them.
        # Collect only the checkbuttons contained within the day and hour frames
        # so they can be enabled/disabled without errors.
        self.schedule_widgets = (
            list(days_frame.winfo_children()) +
            list(hours_frame.winfo_children())
        )
        self.toggle_schedule()  # Initial state

        # Bottom Buttons
        button_frame = ttk.Frame(self, padding="10")
        button_frame.pack(fill=tk.X, side=tk.BOTTOM)
        ttk.Button(button_frame, text="Save and Close", command=self.save_and_close).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Close", command=self.on_close).pack(side=tk.RIGHT, padx=5)

    def populate_ad_list(self):
        self.ad_listbox.delete(0, tk.END)
        for ad in self.ads:
            self.ad_listbox.insert(tk.END, ad.get('Name', 'Unnamed Ad'))

    def on_ad_select(self, event):
        if self.current_index is not None:
            self.save_current_ad()
        selection = self.ad_listbox.curselection()
        if selection:
            self.current_index = selection[0]
            self.load_ad(self.current_index)
        else:
            self.current_index = None
            self.clear_fields()

    def load_ad(self, index):
        ad = self.ads[index]
        self.name_var.set(ad.get('Name', ''))
        self.enabled_var.set(ad.get('Enabled', True))
        self.scheduled_var.set(ad.get('Scheduled', False))
        self.mp3_var.set(ad.get('MP3File', ''))
        for day in self.day_vars:
            self.day_vars[day].set(day in ad.get('Days', []))
        for h in range(24):
            self.hour_vars[h].set(h in [t.get('hour', -1) for t in ad.get('Times', [])])
        self.toggle_schedule()

    def clear_fields(self):
        self.name_var.set('')
        self.enabled_var.set(True)
        self.scheduled_var.set(False)
        self.mp3_var.set('')
        for var in self.day_vars.values():
            var.set(False)
        for var in self.hour_vars.values():
            var.set(False)
        self.toggle_schedule()

    def toggle_schedule(self):
        state = 'normal' if self.scheduled_var.get() else 'disabled'
        for widget in self.schedule_widgets:
            widget.config(state=state)

    def browse_mp3(self):
        path = filedialog.askopenfilename(title="Select Ad MP3", filetypes=[("MP3 Files", "*.mp3"), ("All Files", "*.*")])
        if path:
            self.mp3_var.set(path)
            if not self.name_var.get():
                self.name_var.set(os.path.splitext(os.path.basename(path))[0])

    def add_new_ad(self):
        if self.current_index is not None:
            self.save_current_ad()
        new_ad = {
            'Name': 'New Ad',
            'Enabled': True,
            'Scheduled': False,
            'MP3File': '',
            'Days': [],
            'Times': []
        }
        self.ads.append(new_ad)
        self.ad_listbox.insert(tk.END, 'New Ad')
        self.ad_listbox.select_clear(0, tk.END)
        self.ad_listbox.select_set(tk.END)
        self.current_index = self.ad_listbox.size() - 1
        self.load_ad(self.current_index)

    def delete_ad(self):
        if self.current_index is None:
            messagebox.showwarning("No Selection", "Select an ad to delete.", parent=self)
            return
        if messagebox.askyesno("Confirm Delete", "Delete the selected ad?", parent=self):
            del self.ads[self.current_index]
            self.ad_listbox.delete(self.current_index)
            self.clear_fields()
            self.current_index = None

    def save_current_ad(self):
        if self.current_index is None:
            return
        self.ads[self.current_index]['Name'] = self.name_var.get() or 'Unnamed Ad'
        self.ads[self.current_index]['Enabled'] = self.enabled_var.get()
        self.ads[self.current_index]['Scheduled'] = self.scheduled_var.get()
        self.ads[self.current_index]['MP3File'] = self.mp3_var.get()
        self.ads[self.current_index]['Days'] = [day for day, var in self.day_vars.items() if var.get()]
        selected_hours = [h for h, var in self.hour_vars.items() if var.get()]
        self.ads[self.current_index]['Times'] = [{'hour': h} for h in sorted(selected_hours)]
        # Update listbox display
        self.ad_listbox.delete(self.current_index)
        self.ad_listbox.insert(self.current_index, self.ads[self.current_index]['Name'])
        self.ad_listbox.select_set(self.current_index)

    def save_and_close(self):
        self.save_current_ad()
        try:
            self.config_manager.set_ads(self.ads)  # Assume set_ads() method in ConfigManager
            self.config_manager.save_config()
            logging.info("Ad Inserter settings saved.")
            self.destroy()
        except Exception as e:
            logging.exception("Failed to save Ad Inserter settings.")
            messagebox.showerror("Save Error", f"Failed to save:\n{e}", parent=self)

    def on_close(self):
        self.save_current_ad()
        if self.ads != self.initial_ads:
            response = messagebox.askyesnocancel("Unsaved Changes", "You have unsaved changes. Save before closing?", parent=self)
            if response is True:
                self.save_and_close()
            elif response is False:
                self.destroy()
            # Cancel does nothing
        else:
            self.destroy()