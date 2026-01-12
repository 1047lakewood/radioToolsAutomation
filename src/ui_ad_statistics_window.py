import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
import calendar
import logging
import os
import json
from tkcalendar import DateEntry

class AdStatisticsWindow:
    """Window to display ad play statistics with tabs for each station."""

    def __init__(self, parent, config_manager):
        """
        Initialize the Ad Statistics window.

        Args:
            parent: Parent tkinter window
            config_manager: ConfigManager instance
        """
        self.parent = parent
        self.config_manager = config_manager
        
        # Dictionary to store station-specific data
        now = datetime.now()
        self.stations = {
            'station_1047': {
                'name': '104.7 FM',
                'ad_logger': None,
                'report_generator': None,
                'widgets': {},
                'date_filter_active': False,
                'sort_column_name': None,
                'sort_reverse': False,
                'calendar_year': now.year,
                'calendar_month': now.month,
                'selected_ad': None,
                'daily_stats_cache': {}
            },
            'station_887': {
                'name': '88.7 FM',
                'ad_logger': None,
                'report_generator': None,
                'widgets': {},
                'date_filter_active': False,
                'sort_column_name': None,
                'sort_reverse': False,
                'calendar_year': now.year,
                'calendar_month': now.month,
                'selected_ad': None,
                'daily_stats_cache': {}
            }
        }
        
        # Initialize ad loggers for both stations
        try:
            from ad_play_logger import AdPlayLogger
            from ad_report_generator import AdReportGenerator
            
            for station_id in self.stations.keys():
                self.stations[station_id]['ad_logger'] = AdPlayLogger(config_manager, station_id)
                self.stations[station_id]['report_generator'] = AdReportGenerator(
                    self.stations[station_id]['ad_logger'], station_id
                )
        except ImportError as e:
            logging.error(f"Failed to import ad modules: {e}")

        self.window = tk.Toplevel(parent)
        self.window.title("Ad Play Statistics")
        self.window.geometry("1050x920")
        self.window.minsize(950, 820)

        # Make window modal
        self.window.transient(parent)
        self.window.grab_set()

        # Center the window
        self._center_window()

        self.create_widgets()
        
        # Refresh stats and populate calendar for both stations
        for station_id in self.stations.keys():
            self.refresh_stats(station_id)
            self.populate_calendar_ad_list(station_id)

        # Handle window close
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)

    def _center_window(self):
        """Center the window on the screen."""
        self.window.update_idletasks()
        width = self.window.winfo_width()
        height = self.window.winfo_height()
        x = (self.window.winfo_screenwidth() // 2) - (width // 2)
        y = (self.window.winfo_screenheight() // 2) - (height // 2)
        self.window.geometry(f'+{x}+{y}')

    def create_widgets(self):
        """Create and arrange all widgets."""
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create notebook for tabs
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Create a tab for each station
        for station_id, station_data in self.stations.items():
            tab_frame = ttk.Frame(notebook, padding="10")
            notebook.add(tab_frame, text=station_data['name'])
            self.create_station_tab(tab_frame, station_id)
        
        # Close button at bottom
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        ttk.Button(button_frame, text="Close", command=self.on_close).pack(side=tk.RIGHT, padx=5)

    def create_station_tab(self, parent_frame, station_id):
        """Create the statistics interface for a specific station."""
        station_data = self.stations[station_id]
        widgets = station_data['widgets']
        
        # Control buttons and date filters
        controls_frame = ttk.Frame(parent_frame)
        controls_frame.pack(fill=tk.X, pady=(0, 10))

        # Date filter section
        filter_frame = ttk.LabelFrame(controls_frame, text="Date Filter", padding="10")
        filter_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        ttk.Label(filter_frame, text="From:").grid(row=0, column=0, sticky=tk.W, padx=5)
        widgets['start_date_entry'] = DateEntry(filter_frame, width=12, date_pattern='yyyy-mm-dd')
        widgets['start_date_entry'].grid(row=0, column=1, padx=5)

        ttk.Label(filter_frame, text="To:").grid(row=0, column=2, sticky=tk.W, padx=5)
        widgets['end_date_entry'] = DateEntry(filter_frame, width=12, date_pattern='yyyy-mm-dd')
        widgets['end_date_entry'].grid(row=0, column=3, padx=5)

        ttk.Button(filter_frame, text="Apply", command=lambda: self.apply_date_filter(station_id), width=8).grid(row=0, column=4, padx=5)
        ttk.Button(filter_frame, text="Clear", command=lambda: self.clear_date_filter(station_id), width=8).grid(row=0, column=5, padx=5)

        # Action buttons
        button_frame = ttk.Frame(controls_frame)
        button_frame.pack(side=tk.RIGHT)

        button_row1 = ttk.Frame(button_frame)
        button_row1.pack(fill=tk.X, pady=(0, 5))
        ttk.Button(button_row1, text="Refresh Stats", command=lambda: self.refresh_stats(station_id), width=14).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_row1, text="Reset Counts", command=lambda: self.reset_counts(station_id), width=14).pack(side=tk.LEFT, padx=2)

        button_row2 = ttk.Frame(button_frame)
        button_row2.pack(fill=tk.X, pady=(0, 5))
        ttk.Button(button_row2, text="Export Stats", command=lambda: self.export_stats(station_id), width=14).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_row2, text="Generate Report", command=lambda: self.generate_advertiser_report(station_id), width=14).pack(side=tk.LEFT, padx=2)

        button_row3 = ttk.Frame(button_frame)
        button_row3.pack(fill=tk.X)
        ttk.Button(button_row3, text="View Failures", command=lambda: self.show_failures(station_id), width=14).pack(side=tk.LEFT, padx=2)

        # Statistics summary
        summary_frame = ttk.LabelFrame(parent_frame, text="Summary", padding="10")
        summary_frame.pack(fill=tk.X, pady=(0, 10))

        widgets['summary_labels'] = {}
        summary_grid = [
            ("Total Ads:", "total_ads"),
            ("Enabled Ads:", "enabled_ads"),
            ("Total Plays:", "total_plays"),
            ("Ads with Plays:", "ads_with_plays"),
        ]

        for i, (label_text, key) in enumerate(summary_grid):
            label = ttk.Label(summary_frame, text=label_text)
            label.grid(row=i//2, column=(i%2)*2, sticky=tk.W, padx=5, pady=2)

            value_label = ttk.Label(summary_frame, text="0", font=("Segoe UI", 10, "bold"))
            value_label.grid(row=i//2, column=(i%2)*2 + 1, sticky=tk.W, padx=5, pady=2)
            widgets['summary_labels'][key] = value_label

        # Ad details table
        table_frame = ttk.LabelFrame(parent_frame, text="Ad Details", padding="10")
        table_frame.pack(fill=tk.X, pady=(10, 0))

        # Create treeview for ad details
        columns = ("Name", "Status", "Play Count", "Last Played", "File")
        widgets['ad_tree'] = ttk.Treeview(table_frame, columns=columns, show="headings", height=6)

        # Define column headings
        for col in columns:
            widgets['ad_tree'].heading(col, text=col, command=lambda c=col, s=station_id: self.sort_column(s, c))
            widgets['ad_tree'].column(col, width=120, minwidth=80)

        # Add scrollbars
        v_scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=widgets['ad_tree'].yview)
        h_scrollbar = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=widgets['ad_tree'].xview)
        widgets['ad_tree'].configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        # Pack scrollbars and treeview
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        widgets['ad_tree'].pack(fill=tk.BOTH, expand=True)

        # Calendar section
        self.create_calendar_section(parent_frame, station_id)

        # Status bar
        widgets['status_var'] = tk.StringVar(value="Ready")
        status_bar = ttk.Label(parent_frame, textvariable=widgets['status_var'], relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(fill=tk.X, pady=(10, 0))

    def refresh_stats(self, station_id):
        """Refresh and display current ad statistics for a specific station."""
        station_data = self.stations[station_id]
        ad_logger = station_data['ad_logger']
        widgets = station_data['widgets']
        
        if not ad_logger:
            messagebox.showerror("Error", "Ad logging system not available", parent=self.window)
            return

        try:
            widgets['status_var'].set("Refreshing statistics...")
            self.window.update()

            # Use filtered or unfiltered stats based on current filter state
            if station_data['date_filter_active']:
                # Get dates and format as YYYY-MM-DD strings
                start_date = widgets['start_date_entry'].get_date().strftime('%Y-%m-%d')
                end_date = widgets['end_date_entry'].get_date().strftime('%Y-%m-%d')

                stats = ad_logger.get_ad_statistics_filtered(start_date, end_date)
            else:
                stats = ad_logger.get_ad_statistics()

            if "error" in stats:
                messagebox.showerror("Error", f"Failed to get statistics: {stats['error']}", parent=self.window)
                return

            # Update summary labels
            widgets['summary_labels']["total_ads"].config(text=str(stats.get("total_ads", 0)))
            widgets['summary_labels']["enabled_ads"].config(text=str(stats.get("enabled_ads", 0)))
            widgets['summary_labels']["total_plays"].config(text=str(stats.get("total_plays", 0)))
            widgets['summary_labels']["ads_with_plays"].config(text=str(stats.get("ads_with_plays", 0)))

            # Clear existing items
            for item in widgets['ad_tree'].get_children():
                widgets['ad_tree'].delete(item)

            # Add ad details
            for ad in stats.get("ad_details", []):
                name = ad.get("name", "Unknown")
                status = "Enabled" if ad.get("enabled", False) else "Disabled"
                play_count = ad.get("play_count", 0)
                last_played = ad.get("last_played", "Never")
                if last_played and last_played != "Never":
                    try:
                        last_played = datetime.fromisoformat(last_played).strftime("%Y-%m-%d %H:%M")
                    except:
                        pass
                mp3_file = os.path.basename(ad.get("mp3_file", ""))

                widgets['ad_tree'].insert("", tk.END, values=(name, status, play_count, last_played, mp3_file))

            widgets['status_var'].set(f"Loaded {len(stats.get('ad_details', []))} ads")

        except Exception as e:
            logging.error(f"Error refreshing statistics for {station_id}: {e}")
            messagebox.showerror("Error", f"Failed to refresh statistics: {e}", parent=self.window)
            widgets['status_var'].set("Error loading statistics")

    def apply_date_filter(self, station_id):
        """Apply date filter for a specific station."""
        station_data = self.stations[station_id]
        station_data['date_filter_active'] = True
        self.refresh_stats(station_id)

    def clear_date_filter(self, station_id):
        """Clear date filter for a specific station."""
        station_data = self.stations[station_id]
        widgets = station_data['widgets']
        
        station_data['date_filter_active'] = False
        # Reset date entries to today's date
        today = datetime.now().date()
        widgets['start_date_entry'].set_date(today)
        widgets['end_date_entry'].set_date(today)
        self.refresh_stats(station_id)

    def reset_counts(self, station_id):
        """Reset all play counts for a specific station."""
        station_data = self.stations[station_id]
        ad_logger = station_data['ad_logger']
        
        if not ad_logger:
            return

        if messagebox.askyesno("Confirm Reset", "Are you sure you want to reset all play counts? This cannot be undone.", parent=self.window):
            if ad_logger.reset_all_play_counts():
                self.refresh_stats(station_id)
            else:
                messagebox.showerror("Error", "Failed to reset play counts.", parent=self.window)

    def export_stats(self, station_id):
        """Export statistics to JSON file for a specific station."""
        station_data = self.stations[station_id]
        ad_logger = station_data['ad_logger']
        
        if not ad_logger:
            return

        filename = filedialog.asksaveasfilename(
            title="Export Statistics",
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            parent=self.window
        )
        if filename:
            try:
                stats = ad_logger.get_ad_statistics()
                with open(filename, 'w') as f:
                    json.dump(stats, f, indent=2)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export statistics: {e}", parent=self.window)

    def generate_advertiser_report(self, station_id):
        """Generate advertiser report for a specific station."""
        station_data = self.stations[station_id]
        report_generator = station_data['report_generator']
        
        if not report_generator:
            messagebox.showerror("Error", "Report generator not available", parent=self.window)
            return

        # Use date filter if active
        start_date = None
        end_date = None
        if station_data['date_filter_active']:
            widgets = station_data['widgets']
            start_date = widgets['start_date_entry'].get_date().strftime('%Y-%m-%d')
            end_date = widgets['end_date_entry'].get_date().strftime('%Y-%m-%d')

        try:
            csv_path, pdf_path = report_generator.generate_report(start_date, end_date)
        except Exception as e:
            logging.error(f"Error generating report for {station_id}: {e}")
            messagebox.showerror("Error", f"Failed to generate report: {e}", parent=self.window)

    def sort_column(self, station_id, col):
        """Sort table by column for a specific station."""
        station_data = self.stations[station_id]
        widgets = station_data['widgets']
        tree = widgets['ad_tree']
        
        # Toggle sort direction
        if station_data['sort_column_name'] == col:
            station_data['sort_reverse'] = not station_data['sort_reverse']
        else:
            station_data['sort_reverse'] = False
            station_data['sort_column_name'] = col

        # Get all items
        items = [(tree.set(item, col), item) for item in tree.get_children('')]

        # Sort items
        col_index = {"Name": 0, "Status": 1, "Play Count": 2, "Last Played": 3, "File": 4}
        if col == "Play Count":
            items.sort(key=lambda x: int(x[0]) if x[0].isdigit() else 0, reverse=station_data['sort_reverse'])
        else:
            items.sort(key=lambda x: x[0], reverse=station_data['sort_reverse'])

        # Rearrange items
        for index, (val, item) in enumerate(items):
            tree.move(item, '', index)

    def create_calendar_section(self, parent_frame, station_id):
        """Create the calendar view section for a station."""
        station_data = self.stations[station_id]
        widgets = station_data['widgets']

        # Calendar frame
        calendar_frame = ttk.LabelFrame(parent_frame, text="Play Calendar", padding="10")
        calendar_frame.pack(fill=tk.X, pady=(10, 0))

        # Top row: Ad selector and month navigation
        top_row = ttk.Frame(calendar_frame)
        top_row.pack(fill=tk.X, pady=(0, 10))

        # Ad selector
        ttk.Label(top_row, text="Ad:").pack(side=tk.LEFT, padx=(0, 5))
        widgets['calendar_ad_var'] = tk.StringVar()
        widgets['calendar_ad_combo'] = ttk.Combobox(
            top_row,
            textvariable=widgets['calendar_ad_var'],
            state='readonly',
            width=30
        )
        widgets['calendar_ad_combo'].pack(side=tk.LEFT, padx=(0, 20))
        widgets['calendar_ad_combo'].bind('<<ComboboxSelected>>', lambda e: self.on_calendar_ad_selected(station_id))

        # Month navigation
        nav_frame = ttk.Frame(top_row)
        nav_frame.pack(side=tk.LEFT, padx=20)

        ttk.Button(nav_frame, text="<", width=3, command=lambda: self.calendar_prev_month(station_id)).pack(side=tk.LEFT)
        widgets['calendar_month_label'] = ttk.Label(nav_frame, text="", width=20, anchor=tk.CENTER, font=("Segoe UI", 10, "bold"))
        widgets['calendar_month_label'].pack(side=tk.LEFT, padx=10)
        ttk.Button(nav_frame, text=">", width=3, command=lambda: self.calendar_next_month(station_id)).pack(side=tk.LEFT)

        # Calendar grid and detail panel side by side
        content_frame = ttk.Frame(calendar_frame)
        content_frame.pack(fill=tk.X)

        # Calendar grid
        grid_frame = ttk.Frame(content_frame)
        grid_frame.pack(side=tk.LEFT, padx=(0, 20))

        # Day headers (Sun-Sat)
        day_names = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
        for col, day_name in enumerate(day_names):
            lbl = ttk.Label(grid_frame, text=day_name, width=7, anchor=tk.CENTER, font=("Segoe UI", 11, "bold"))
            lbl.grid(row=0, column=col, padx=2, pady=2)

        # Day cells (6 rows x 7 columns)
        widgets['calendar_day_frames'] = []
        widgets['calendar_day_labels'] = []
        widgets['calendar_dot_labels'] = []

        for row in range(6):
            row_frames = []
            row_labels = []
            row_dots = []
            for col in range(7):
                # Frame for each day cell
                cell_frame = ttk.Frame(grid_frame, width=60, height=45)
                cell_frame.grid(row=row+1, column=col, padx=2, pady=2)
                cell_frame.grid_propagate(False)

                # Day number label
                day_label = ttk.Label(cell_frame, text="", anchor=tk.CENTER, font=("Segoe UI", 12))
                day_label.place(relx=0.5, rely=0.3, anchor=tk.CENTER)

                # Play count indicator label (shows number of plays as dots or count)
                dot_label = ttk.Label(cell_frame, text="", foreground="#28a745", font=("Segoe UI", 11, "bold"))
                dot_label.place(relx=0.5, rely=0.72, anchor=tk.CENTER)

                row_frames.append(cell_frame)
                row_labels.append(day_label)
                row_dots.append(dot_label)

            widgets['calendar_day_frames'].append(row_frames)
            widgets['calendar_day_labels'].append(row_labels)
            widgets['calendar_dot_labels'].append(row_dots)

        # Day detail panel
        detail_frame = ttk.LabelFrame(content_frame, text="Play Details", padding="10", width=200)
        detail_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        widgets['calendar_detail_label'] = ttk.Label(detail_frame, text="Select an ad and click a day to see play times.", wraplength=250, justify=tk.LEFT)
        widgets['calendar_detail_label'].pack(anchor=tk.NW)

        # Initialize calendar display
        self.update_calendar_month_label(station_id)

    def populate_calendar_ad_list(self, station_id):
        """Populate the ad selector dropdown with ad names."""
        station_data = self.stations[station_id]
        widgets = station_data['widgets']

        # Get ad names from config using get_station_ads method
        ads = self.config_manager.get_station_ads(station_id) or []
        ad_names = [ad.get('Name', '') for ad in ads if ad.get('Name')]

        widgets['calendar_ad_combo']['values'] = ad_names
        if ad_names:
            widgets['calendar_ad_combo'].set('')

    def on_calendar_ad_selected(self, station_id):
        """Handle ad selection in calendar."""
        station_data = self.stations[station_id]
        widgets = station_data['widgets']
        ad_logger = station_data['ad_logger']

        selected_ad = widgets['calendar_ad_var'].get()
        station_data['selected_ad'] = selected_ad

        # Cache the play data for this ad (compact format: MM-DD-YY -> [hours])
        if ad_logger:
            station_data['daily_stats_cache'] = ad_logger.get_daily_play_counts(selected_ad) or {}

        # Refresh calendar display
        self.refresh_calendar_grid(station_id)

        # Clear detail panel
        widgets['calendar_detail_label'].config(text=f"Selected: {selected_ad}\nClick a day with a dot to see play times.")

    def calendar_prev_month(self, station_id):
        """Navigate to previous month."""
        station_data = self.stations[station_id]

        if station_data['calendar_month'] == 1:
            station_data['calendar_month'] = 12
            station_data['calendar_year'] -= 1
        else:
            station_data['calendar_month'] -= 1

        self.update_calendar_month_label(station_id)
        self.refresh_calendar_grid(station_id)

    def calendar_next_month(self, station_id):
        """Navigate to next month."""
        station_data = self.stations[station_id]

        if station_data['calendar_month'] == 12:
            station_data['calendar_month'] = 1
            station_data['calendar_year'] += 1
        else:
            station_data['calendar_month'] += 1

        self.update_calendar_month_label(station_id)
        self.refresh_calendar_grid(station_id)

    def update_calendar_month_label(self, station_id):
        """Update the month/year display label."""
        station_data = self.stations[station_id]
        widgets = station_data['widgets']

        month_name = calendar.month_name[station_data['calendar_month']]
        year = station_data['calendar_year']
        widgets['calendar_month_label'].config(text=f"{month_name} {year}")

    def refresh_calendar_grid(self, station_id):
        """Refresh the calendar grid with dots for days the selected ad played."""
        station_data = self.stations[station_id]
        widgets = station_data['widgets']

        year = station_data['calendar_year']
        month = station_data['calendar_month']
        selected_ad = station_data['selected_ad']
        daily_stats = station_data['daily_stats_cache']  # Format: MM-DD-YY -> play_count

        # Get calendar for this month (Sunday start)
        cal = calendar.Calendar(firstweekday=6)
        month_days = cal.monthdayscalendar(year, month)

        # Clear all cells first
        for row in range(6):
            for col in range(7):
                widgets['calendar_day_labels'][row][col].config(text="")
                widgets['calendar_dot_labels'][row][col].config(text="")
                # Remove old bindings
                widgets['calendar_day_frames'][row][col].unbind('<Button-1>')
                widgets['calendar_day_labels'][row][col].unbind('<Button-1>')
                widgets['calendar_dot_labels'][row][col].unbind('<Button-1>')

        # Fill in the days
        for row, week in enumerate(month_days):
            if row >= 6:
                break
            for col, day in enumerate(week):
                if day == 0:
                    continue

                # Set day number
                widgets['calendar_day_labels'][row][col].config(text=str(day))

                # Check if this ad played on this day (compact format: MM-DD-YY)
                date_str = f"{month:02d}-{day:02d}-{year % 100:02d}"
                has_plays = False
                play_count = 0

                if selected_ad and date_str in daily_stats:
                    play_count = daily_stats[date_str]
                    if play_count > 0:
                        has_plays = True
                        # Show dots for play count (up to 5 dots, then show number)
                        if play_count <= 5:
                            widgets['calendar_dot_labels'][row][col].config(text="●" * play_count)
                        else:
                            widgets['calendar_dot_labels'][row][col].config(text=f"●{play_count}")

                # Bind click handler
                click_handler = lambda e, d=day, dp=has_plays: self.on_calendar_day_click(station_id, d, dp)
                widgets['calendar_day_frames'][row][col].bind('<Button-1>', click_handler)
                widgets['calendar_day_labels'][row][col].bind('<Button-1>', click_handler)
                widgets['calendar_dot_labels'][row][col].bind('<Button-1>', click_handler)

    def on_calendar_day_click(self, station_id, day, has_plays):
        """Handle click on a calendar day."""
        station_data = self.stations[station_id]
        widgets = station_data['widgets']
        ad_logger = station_data['ad_logger']

        year = station_data['calendar_year']
        month = station_data['calendar_month']
        selected_ad = station_data['selected_ad']

        if not selected_ad:
            widgets['calendar_detail_label'].config(text="Please select an ad first.")
            return

        month_name = calendar.month_name[month]

        if not has_plays:
            widgets['calendar_detail_label'].config(text=f"{month_name} {day}, {year}\n\nNo plays for {selected_ad}")
            return

        # Get hours when this ad played (compact format: MM-DD-YY)
        date_str = f"{month:02d}-{day:02d}-{year % 100:02d}"
        hours_played = ad_logger.get_play_hours_for_date(selected_ad, date_str) if ad_logger else []

        # Format hours as 12-hour time
        play_hours = []
        for hour in hours_played:
            if hour == 0:
                time_str = "12:00 AM"
            elif hour < 12:
                time_str = f"{hour}:00 AM"
            elif hour == 12:
                time_str = "12:00 PM"
            else:
                time_str = f"{hour-12}:00 PM"
            play_hours.append(time_str)

        # Build detail text
        detail_text = f"{month_name} {day}, {year}\n\nPlayed at:\n"
        for time_str in play_hours:
            detail_text += f"  {time_str}\n"
        detail_text += f"\nTotal: {len(play_hours)} play{'s' if len(play_hours) != 1 else ''}"

        widgets['calendar_detail_label'].config(text=detail_text)

    def show_failures(self, station_id):
        """Show the failure log for a specific station."""
        station_data = self.stations[station_id]
        ad_logger = station_data['ad_logger']

        if not ad_logger:
            messagebox.showerror("Error", "Ad logging system not available", parent=self.window)
            return

        failures = ad_logger.get_failures()

        # Create a simple dialog to show failures
        dialog = tk.Toplevel(self.window)
        dialog.title(f"Ad Insertion Failures - {station_data['name']}")
        dialog.geometry("500x400")
        dialog.transient(self.window)
        dialog.grab_set()

        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (250)
        y = (dialog.winfo_screenheight() // 2) - (200)
        dialog.geometry(f'+{x}+{y}')

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=f"Last {len(failures)} failures (most recent first):", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)

        # Text widget with scrollbar
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 10))

        text_widget = tk.Text(text_frame, wrap=tk.WORD, font=("Consolas", 9))
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        if not failures:
            text_widget.insert(tk.END, "No failures recorded.")
        else:
            # Show most recent first
            for failure in reversed(failures):
                timestamp = failure.get("t", "?")
                ads = ", ".join(failure.get("ads", ["?"]))
                error = failure.get("err", "unknown")
                text_widget.insert(tk.END, f"{timestamp}  {ads}\n  Error: {error}\n\n")

        text_widget.config(state=tk.DISABLED)

        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT)

    def on_close(self):
        """Handle window close event."""
        self.window.destroy()

