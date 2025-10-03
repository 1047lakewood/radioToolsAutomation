import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import logging
import os

logger = logging.getLogger('AdStatisticsUI')

class AdStatisticsWindow:
    """Window to display ad play statistics and manage ad tracking."""

    def __init__(self, parent, config_manager):
        """
        Initialize the Ad Statistics window.

        Args:
            parent: Parent tkinter window
            config_manager: ConfigManager instance
        """
        self.parent = parent
        self.config_manager = config_manager

        # Initialize ad logger
        try:
            from ad_play_logger import AdPlayLogger
            self.ad_logger = AdPlayLogger(config_manager)
        except ImportError:
            logger.error("AdPlayLogger not available")
            self.ad_logger = None

        # Initialize report generator
        try:
            from ad_report_generator import AdReportGenerator
            self.report_generator = AdReportGenerator(self.ad_logger) if self.ad_logger else None
        except ImportError:
            logger.error("AdReportGenerator not available")
            self.report_generator = None

        # Date filtering state (must be initialized before create_widgets)
        self.start_date_var = tk.StringVar()
        self.end_date_var = tk.StringVar()
        self.date_filter_active = False

        self.window = tk.Toplevel(parent)
        self.window.title("Ad Play Statistics")
        self.window.geometry("1000x700")
        self.window.minsize(900, 600)

        # Make window modal
        self.window.transient(parent)
        self.window.grab_set()

        # Center the window
        self._center_window()

        self.create_widgets()
        self.refresh_stats()

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

        # Title
        title_label = ttk.Label(
            main_frame,
            text="Ad Play Statistics",
            font=("Segoe UI", 16, "bold")
        )
        title_label.pack(pady=(0, 20))

        # Control buttons and date filters
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill=tk.X, pady=(0, 10))

        # Use grid layout for controls_frame for better control
        controls_frame.grid_columnconfigure(0, weight=1)  # Filter section can expand
        controls_frame.grid_columnconfigure(1, weight=0)  # Buttons stay fixed width
        controls_frame.grid_rowconfigure(0, weight=0)  # Single row layout

        # Date filter section - clean horizontal layout
        filter_frame = ttk.LabelFrame(controls_frame, text="Date Filter", padding="10")
        filter_frame.grid(row=0, column=0, sticky=tk.EW, padx=(0, 10))

        # Configure columns for proper expansion
        filter_frame.grid_columnconfigure(1, weight=2)  # Entry fields get more space
        filter_frame.grid_columnconfigure(3, weight=2)  # Entry fields get more space
        filter_frame.grid_columnconfigure(0, weight=0)  # Labels stay fixed
        filter_frame.grid_columnconfigure(2, weight=0)  # Labels stay fixed
        filter_frame.grid_columnconfigure(4, weight=0)  # Buttons stay fixed
        filter_frame.grid_columnconfigure(5, weight=0)  # Buttons stay fixed

        # From date section
        ttk.Label(filter_frame, text="From:").grid(row=0, column=0, sticky=tk.W, padx=(10, 0))
        self.start_date_entry = ttk.Entry(filter_frame, textvariable=self.start_date_var)
        self.start_date_entry.grid(row=0, column=1, sticky=tk.EW, padx=(5, 15))
        self.start_date_entry.insert(0, "YYYY-MM-DD")
        self.start_date_entry.configure(foreground="gray")

        # To date section
        ttk.Label(filter_frame, text="To:").grid(row=0, column=2, sticky=tk.W, padx=(10, 0))
        self.end_date_entry = ttk.Entry(filter_frame, textvariable=self.end_date_var)
        self.end_date_entry.grid(row=0, column=3, sticky=tk.EW, padx=(5, 15))
        self.end_date_entry.insert(0, "YYYY-MM-DD")
        self.end_date_entry.configure(foreground="gray")

        # Action buttons
        ttk.Button(
            filter_frame,
            text="Apply",
            command=self.apply_date_filter,
            width=8
        ).grid(row=0, column=4, padx=(10, 5))

        ttk.Button(
            filter_frame,
            text="Clear",
            command=self.clear_date_filter,
            width=8
        ).grid(row=0, column=5)

        # Add focus events for placeholder behavior
        self.start_date_entry.bind("<FocusIn>", lambda e: self._on_date_entry_focus_in(self.start_date_entry))
        self.start_date_entry.bind("<FocusOut>", lambda e: self._on_date_entry_focus_out(self.start_date_entry))
        self.end_date_entry.bind("<FocusIn>", lambda e: self._on_date_entry_focus_in(self.end_date_entry))
        self.end_date_entry.bind("<FocusOut>", lambda e: self._on_date_entry_focus_out(self.end_date_entry))

        # Action buttons - stack them vertically if needed
        button_frame = ttk.Frame(controls_frame)
        button_frame.grid(row=0, column=1, sticky=tk.NE, padx=(10, 0))

        # Row 1 of buttons
        button_row1 = ttk.Frame(button_frame)
        button_row1.pack(fill=tk.X, pady=(0, 5))

        ttk.Button(
            button_row1,
            text="Refresh Stats",
            command=self.refresh_stats,
            width=15
        ).pack(side=tk.LEFT, padx=2)

        ttk.Button(
            button_row1,
            text="Reset All Counts",
            command=self.reset_counts,
            width=15
        ).pack(side=tk.LEFT, padx=2)

        # Row 2 of buttons
        button_row2 = ttk.Frame(button_frame)
        button_row2.pack(fill=tk.X)

        ttk.Button(
            button_row2,
            text="Export Stats",
            command=self.export_stats,
            width=15
        ).pack(side=tk.LEFT, padx=2)

        ttk.Button(
            button_row2,
            text="Generate Report",
            command=self.generate_advertiser_report,
            width=15
        ).pack(side=tk.LEFT, padx=2)

        # Statistics summary
        summary_frame = ttk.LabelFrame(main_frame, text="Summary", padding="10")
        summary_frame.pack(fill=tk.X, pady=(0, 10))

        # Create summary labels
        self.summary_labels = {}
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
            self.summary_labels[key] = value_label

        # Ad details table
        table_frame = ttk.LabelFrame(main_frame, text="Ad Details", padding="10")
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        # Create treeview for ad details
        columns = ("Name", "Status", "Play Count", "Last Played", "File")
        self.ad_tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            height=15
        )

        # Define column headings
        for col in columns:
            self.ad_tree.heading(col, text=col, command=lambda c=col: self.sort_column(c))
            self.ad_tree.column(col, width=120, minwidth=80)

        # Add scrollbars
        v_scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.ad_tree.yview)
        h_scrollbar = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.ad_tree.xview)
        self.ad_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        # Pack scrollbars and treeview
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.ad_tree.pack(fill=tk.BOTH, expand=True)

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(
            main_frame,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor=tk.W
        )
        status_bar.pack(fill=tk.X, pady=(10, 0))

        # Sorting state
        self.sort_column_name = None
        self.sort_reverse = False

    def refresh_stats(self):
        """Refresh and display current ad statistics."""
        if not self.ad_logger:
            messagebox.showerror("Error", "Ad logging system not available")
            return

        try:
            self.status_var.set("Refreshing statistics...")
            self.window.update()

            # Use filtered or unfiltered stats based on current filter state
            if self.date_filter_active:
                start_date = self.start_date_var.get().strip()
                end_date = self.end_date_var.get().strip()

                if not start_date or not end_date:
                    messagebox.showerror("Error", "Please enter both start and end dates for filtering.")
                    return

                stats = self.ad_logger.get_ad_statistics_filtered(start_date, end_date)
            else:
                stats = self.ad_logger.get_ad_statistics()

            if "error" in stats:
                messagebox.showerror("Error", f"Failed to get statistics: {stats['error']}")
                return

            # Update summary labels
            self.summary_labels["total_ads"].config(text=str(stats.get("total_ads", 0)))
            self.summary_labels["enabled_ads"].config(text=str(stats.get("enabled_ads", 0)))
            self.summary_labels["total_plays"].config(text=str(stats.get("total_plays", 0)))
            self.summary_labels["ads_with_plays"].config(text=str(stats.get("ads_with_plays", 0)))

            # Clear existing items
            for item in self.ad_tree.get_children():
                self.ad_tree.delete(item)

            # Add ad details
            for ad in stats.get("ad_details", []):
                status = "Enabled" if ad.get("enabled", False) else "Disabled"
                last_played = ad.get("last_played", "Never")
                if last_played and last_played != "null":
                    try:
                        # Try to parse and format the datetime
                        dt = datetime.fromisoformat(last_played.replace('Z', '+00:00'))
                        last_played = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        pass  # Keep original format if parsing fails

                self.ad_tree.insert("", tk.END, values=(
                    ad.get("name", "Unknown"),
                    status,
                    str(ad.get("play_count", 0)),
                    last_played,
                    os.path.basename(ad.get("mp3_file", "")) if ad.get("mp3_file") else ""
                ))

            # Update status with filter info if applicable
            ad_count = len(stats.get('ad_details', []))
            filter_info = ""
            if self.date_filter_active and "date_filter" in stats:
                filter_info = f" (filtered: {stats['date_filter']['days_filtered']} days)"

            self.status_var.set(f"Statistics updated - {ad_count} ads shown{filter_info}")

        except Exception as e:
            logger.error(f"Error refreshing statistics: {e}")
            messagebox.showerror("Error", f"Failed to refresh statistics: {e}")
            self.status_var.set("Error refreshing statistics")

    def reset_counts(self):
        """Reset all ad play counts."""
        if not self.ad_logger:
            messagebox.showerror("Error", "Ad logging system not available")
            return

        if messagebox.askyesno("Confirm Reset",
                             "Are you sure you want to reset all ad play counts to zero?"):
            try:
                if self.ad_logger.reset_all_play_counts():
                    messagebox.showinfo("Success", "All ad play counts have been reset.")
                    self.refresh_stats()
                else:
                    messagebox.showerror("Error", "Failed to reset play counts.")
            except Exception as e:
                logger.error(f"Error resetting counts: {e}")
                messagebox.showerror("Error", f"Failed to reset counts: {e}")

    def _get_default_date(self):
        """Get today's date as default."""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d")

    def _on_date_entry_focus_in(self, entry):
        """Handle focus in event for date entries."""
        if entry.get() == "YYYY-MM-DD":
            entry.delete(0, tk.END)
            entry.configure(foreground="black")

    def _on_date_entry_focus_out(self, entry):
        """Handle focus out event for date entries."""
        if not entry.get().strip():
            entry.insert(0, "YYYY-MM-DD")
            entry.configure(foreground="gray")

    def apply_date_filter(self):
        """Apply date filter to statistics."""
        start_date = self.start_date_var.get().strip()
        end_date = self.end_date_var.get().strip()

        # Handle placeholder text
        if start_date == "YYYY-MM-DD" or not start_date:
            messagebox.showerror("Error", "Please enter a start date.")
            return

        if end_date == "YYYY-MM-DD" or not end_date:
            messagebox.showerror("Error", "Please enter an end date.")
            return

        # Validate date format (YYYY-MM-DD)
        try:
            from datetime import datetime
            datetime.strptime(start_date, "%Y-%m-%d")
            datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Error", "Please enter dates in YYYY-MM-DD format.\n\nExamples:\n• 2024-09-15\n• 2024-12-31\n• 2024-01-01\n\nTip: Click on the date field to edit, then type the date.")
            return

        # Validate date range
        if start_date > end_date:
            messagebox.showerror("Error", "Start date must be before or equal to end date.")
            return

        self.date_filter_active = True
        self.refresh_stats()

    def clear_date_filter(self):
        """Clear date filter and show all statistics."""
        self.start_date_var.set("")
        self.end_date_var.set("")
        self.date_filter_active = False

        # Restore placeholder text
        self.start_date_entry.delete(0, tk.END)
        self.start_date_entry.insert(0, "YYYY-MM-DD")
        self.start_date_entry.configure(foreground="gray")
        self.end_date_entry.delete(0, tk.END)
        self.end_date_entry.insert(0, "YYYY-MM-DD")
        self.end_date_entry.configure(foreground="gray")

        self.refresh_stats()

    def export_stats(self):
        """Export statistics to a file."""
        if not self.ad_logger:
            messagebox.showerror("Error", "Ad logging system not available")
            return

        try:
            from tkinter import filedialog
            import json

            filename = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                title="Export Ad Statistics"
            )

            if not filename:
                return

            # Get stats based on current filter state
            if self.date_filter_active:
                start_date = self.start_date_var.get().strip()
                end_date = self.end_date_var.get().strip()
                basic_stats = self.ad_logger.get_ad_statistics_filtered(start_date, end_date)
                detailed_stats = self.ad_logger.get_detailed_stats(start_date, end_date)
            else:
                basic_stats = self.ad_logger.get_ad_statistics()
                detailed_stats = self.ad_logger.get_detailed_stats()

            # Combine stats for export
            export_data = {
                "export_timestamp": datetime.now().isoformat(),
                "date_filter_applied": self.date_filter_active,
                "basic_stats": basic_stats,
                "detailed_stats": detailed_stats
            }

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)

            filter_info = f" (filtered {start_date} to {end_date})" if self.date_filter_active else ""
            messagebox.showinfo("Success", f"Statistics exported to {filename}{filter_info}")
            self.status_var.set(f"Exported to {filename}")

        except Exception as e:
            logger.error(f"Error exporting statistics: {e}")
            messagebox.showerror("Error", f"Failed to export statistics: {e}")

    def sort_column(self, col):
        """Sort the treeview by the specified column."""
        # Get current items
        items = [(self.ad_tree.set(child, col), child) for child in self.ad_tree.get_children('')]

        # Sort items
        if col in ("Play Count",):
            # Numeric sort for play count
            items.sort(key=lambda x: int(x[0]), reverse=self.sort_reverse)
        else:
            # String sort for other columns
            items.sort(key=lambda x: x[0].lower(), reverse=self.sort_reverse)

        # Rearrange items
        for index, (val, child) in enumerate(items):
            self.ad_tree.move(child, '', index)

        # Toggle sort direction for next click
        self.sort_reverse = not self.sort_reverse

        # Update column heading to show sort direction
        for column in self.ad_tree['columns']:
            if column == col:
                current_text = self.ad_tree.heading(column, 'text')
                if self.sort_reverse:
                    new_text = current_text + " ↓"
                else:
                    new_text = current_text + " ↑"
                self.ad_tree.heading(column, text=new_text)
            else:
                # Remove sort indicators from other columns
                current_text = self.ad_tree.heading(column, 'text')
                if " ↑" in current_text or " ↓" in current_text:
                    self.ad_tree.heading(column, text=current_text.replace(" ↑", "").replace(" ↓", ""))

    def generate_advertiser_report(self):
        """Open dialog to generate an advertiser report."""
        if not self.report_generator:
            messagebox.showerror("Error", "Report generator not available")
            return

        # Create report dialog
        ReportGeneratorDialog(self.window, self.config_manager, self.report_generator)

    def on_close(self):
        """Handle window close event."""
        self.window.grab_release()
        self.window.destroy()


class ReportGeneratorDialog:
    """Dialog for generating advertiser reports."""

    def __init__(self, parent, config_manager, report_generator):
        """
        Initialize the report generator dialog.

        Args:
            parent: Parent tkinter window
            config_manager: ConfigManager instance
            report_generator: AdReportGenerator instance
        """
        self.config_manager = config_manager
        self.report_generator = report_generator

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Generate Advertiser Report")
        self.dialog.geometry("600x700")
        self.dialog.resizable(True, True)

        # Make modal
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Center the dialog
        self._center_dialog()

        self.create_widgets()

    def _center_dialog(self):
        """Center the dialog on the screen."""
        self.dialog.update_idletasks()
        width = self.dialog.winfo_width()
        height = self.dialog.winfo_height()
        x = (self.dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (height // 2)
        self.dialog.geometry(f'+{x}+{y}')

    def create_widgets(self):
        """Create and arrange all widgets."""
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(
            main_frame,
            text="Generate Advertiser Report",
            font=("Segoe UI", 14, "bold")
        )
        title_label.pack(pady=(0, 20))

        # Report type selection
        type_frame = ttk.LabelFrame(main_frame, text="Report Type", padding="10")
        type_frame.pack(fill=tk.X, pady=(0, 15))

        self.report_type_var = tk.StringVar(value="single")
        ttk.Radiobutton(
            type_frame,
            text="Single Ad Report",
            variable=self.report_type_var,
            value="single",
            command=self.on_report_type_changed
        ).pack(anchor=tk.W, pady=2)

        ttk.Radiobutton(
            type_frame,
            text="Multi-Ad Report",
            variable=self.report_type_var,
            value="multi",
            command=self.on_report_type_changed
        ).pack(anchor=tk.W, pady=2)

        # Ad selection
        ad_frame = ttk.LabelFrame(main_frame, text="Ad Selection", padding="10")
        ad_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        # Single ad selection
        self.single_ad_frame = ttk.Frame(ad_frame)
        self.single_ad_frame.pack(fill=tk.X)

        ttk.Label(self.single_ad_frame, text="Select Ad:").pack(anchor=tk.W, pady=(0, 5))

        ads = self.config_manager.get_ads() or []
        ad_names = [ad.get("Name", "Unknown") for ad in ads]

        self.ad_var = tk.StringVar()
        self.ad_combo = ttk.Combobox(
            self.single_ad_frame,
            textvariable=self.ad_var,
            values=ad_names,
            state="readonly"
        )
        self.ad_combo.pack(fill=tk.X, pady=(0, 10))
        if ad_names:
            self.ad_combo.current(0)

        # Multi-ad selection (hidden initially)
        self.multi_ad_frame = ttk.Frame(ad_frame)

        ttk.Label(self.multi_ad_frame, text="Select Ads (check all that apply):").pack(anchor=tk.W, pady=(0, 5))

        # Scrollable frame for checkboxes
        canvas = tk.Canvas(self.multi_ad_frame, height=150)
        scrollbar = ttk.Scrollbar(self.multi_ad_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        self.ad_check_vars = {}
        for ad_name in ad_names:
            var = tk.BooleanVar()
            ttk.Checkbutton(
                scrollable_frame,
                text=ad_name,
                variable=var
            ).pack(anchor=tk.W, pady=2)
            self.ad_check_vars[ad_name] = var

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Date range
        date_frame = ttk.LabelFrame(main_frame, text="Date Range", padding="10")
        date_frame.pack(fill=tk.X, pady=(0, 15))

        date_grid = ttk.Frame(date_frame)
        date_grid.pack(fill=tk.X)

        ttk.Label(date_grid, text="From:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.start_date_var = tk.StringVar()
        self.start_date_entry = ttk.Entry(date_grid, textvariable=self.start_date_var, width=15)
        self.start_date_entry.grid(row=0, column=1, sticky=tk.W, padx=(0, 20))
        self.start_date_entry.insert(0, "YYYY-MM-DD")

        ttk.Label(date_grid, text="To:").grid(row=0, column=2, sticky=tk.W, padx=(0, 5))
        self.end_date_var = tk.StringVar()
        self.end_date_entry = ttk.Entry(date_grid, textvariable=self.end_date_var, width=15)
        self.end_date_entry.grid(row=0, column=3, sticky=tk.W)
        self.end_date_entry.insert(0, "YYYY-MM-DD")

        # Format selection
        format_frame = ttk.LabelFrame(main_frame, text="Output Format", padding="10")
        format_frame.pack(fill=tk.X, pady=(0, 15))

        self.format_var = tk.StringVar(value="pdf")
        ttk.Radiobutton(
            format_frame,
            text="PDF (Professional, recommended for advertisers)",
            variable=self.format_var,
            value="pdf"
        ).pack(anchor=tk.W, pady=2)

        ttk.Radiobutton(
            format_frame,
            text="CSV (Spreadsheet format)",
            variable=self.format_var,
            value="csv"
        ).pack(anchor=tk.W, pady=2)

        # Optional details for PDF
        self.details_frame = ttk.LabelFrame(main_frame, text="Optional Details (PDF only)", padding="10")
        self.details_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(self.details_frame, text="Advertiser Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.advertiser_name_var = tk.StringVar()
        ttk.Entry(self.details_frame, textvariable=self.advertiser_name_var, width=40).grid(
            row=0, column=1, sticky=tk.EW, padx=(10, 0), pady=5
        )

        ttk.Label(self.details_frame, text="Company Name:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.company_name_var = tk.StringVar()
        ttk.Entry(self.details_frame, textvariable=self.company_name_var, width=40).grid(
            row=1, column=1, sticky=tk.EW, padx=(10, 0), pady=5
        )

        self.details_frame.grid_columnconfigure(1, weight=1)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(
            button_frame,
            text="Generate Report",
            command=self.generate_report
        ).pack(side=tk.RIGHT, padx=(5, 0))

        ttk.Button(
            button_frame,
            text="Cancel",
            command=self.dialog.destroy
        ).pack(side=tk.RIGHT)

    def on_report_type_changed(self):
        """Handle report type selection change."""
        if self.report_type_var.get() == "single":
            self.multi_ad_frame.pack_forget()
            self.single_ad_frame.pack(fill=tk.X)
        else:
            self.single_ad_frame.pack_forget()
            self.multi_ad_frame.pack(fill=tk.BOTH, expand=True)

    def generate_report(self):
        """Generate the report based on user selections."""
        try:
            # Validate dates
            start_date = self.start_date_var.get().strip()
            end_date = self.end_date_var.get().strip()

            if not start_date or start_date == "YYYY-MM-DD":
                messagebox.showerror("Error", "Please enter a start date.")
                return

            if not end_date or end_date == "YYYY-MM-DD":
                messagebox.showerror("Error", "Please enter an end date.")
                return

            try:
                datetime.strptime(start_date, "%Y-%m-%d")
                datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("Error", "Please enter dates in YYYY-MM-DD format.")
                return

            if start_date > end_date:
                messagebox.showerror("Error", "Start date must be before or equal to end date.")
                return

            # Get selected format
            report_format = self.format_var.get()
            file_ext = "pdf" if report_format == "pdf" else "csv"

            # Get file save location
            from tkinter import filedialog
            default_filename = f"ad_report_{start_date}_to_{end_date}.{file_ext}"

            file_types = [
                ("PDF files", "*.pdf"),
                ("All files", "*.*")
            ] if report_format == "pdf" else [
                ("CSV files", "*.csv"),
                ("All files", "*.*")
            ]

            output_file = filedialog.asksaveasfilename(
                defaultextension=f".{file_ext}",
                filetypes=file_types,
                initialfile=default_filename,
                title="Save Report As"
            )

            if not output_file:
                return

            # Generate appropriate report
            success = False
            if self.report_type_var.get() == "single":
                ad_name = self.ad_var.get()
                if not ad_name:
                    messagebox.showerror("Error", "Please select an ad.")
                    return

                if report_format == "pdf":
                    success = self.report_generator.generate_pdf_report(
                        ad_name=ad_name,
                        start_date=start_date,
                        end_date=end_date,
                        output_file=output_file,
                        advertiser_name=self.advertiser_name_var.get().strip() or None,
                        company_name=self.company_name_var.get().strip() or None
                    )
                else:
                    success = self.report_generator.generate_csv_report(
                        ad_name=ad_name,
                        start_date=start_date,
                        end_date=end_date,
                        output_file=output_file
                    )
            else:
                # Multi-ad report
                selected_ads = [name for name, var in self.ad_check_vars.items() if var.get()]
                if not selected_ads:
                    messagebox.showerror("Error", "Please select at least one ad.")
                    return

                success = self.report_generator.generate_multi_ad_report(
                    ad_names=selected_ads,
                    start_date=start_date,
                    end_date=end_date,
                    output_file=output_file,
                    format=report_format
                )

            if success:
                result = messagebox.askyesno(
                    "Success",
                    f"Report generated successfully!\n\nSaved to:\n{output_file}\n\nWould you like to open it?",
                    icon="info"
                )
                if result:
                    import os
                    os.startfile(output_file)
                self.dialog.destroy()
            else:
                messagebox.showerror("Error", "Failed to generate report. Check logs for details.")

        except Exception as e:
            logger.error(f"Error in generate_report: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to generate report: {e}")
