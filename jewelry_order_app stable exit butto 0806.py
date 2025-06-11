import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
import os
from tkcalendar import DateEntry
from PIL import Image, ImageTk
import sqlite3
import pandas as pd
import shutil

# --- Global Constants ---
DB_PATH = "orders.db"
BACKUP_FOLDER = "backups"
SPLASH_LOGO_DEFAULT = "default_splash_logo.png" # Placeholder for a default logo if none is set
INITIAL_ADMIN_PASSWORD = "admin123"

# --- Dark Theme Colors and Fonts ---
BG_COLOR = "#121212" # Dark background
FG_COLOR = "#ffffff" # White foreground (for labels and general text)
INPUT_TEXT_COLOR = "#FFFF00" # Yellow for input fields
BTN_COLOR = "#1f1f1f" # Dark button color
ENTRY_BG = "#2a2a2a" # Darker entry background
FONT_NORMAL = ("Cambria", 11, "bold") # Changed to Cambria, bold
FONT_LARGE = ("Cambria", 12, "bold") # Changed to Cambria, bold
FONT_BOLD_LARGE = ("Segoe UI", 14, "bold") # Retained as Segoe UI for specific bold labels
FONT_TITLE = ("Segoe UI", 18, "bold") # Retained as Segoe UI for titles
FONT_TAB_TITLE = ("Segoe UI", 11, "bold") # Retained as Segoe UI for tab titles

# --- Database Connection and Schema Setup ---
def connect_db():
    """Establishes a connection to the SQLite database and creates tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    conn.isolation_level = None # Autocommit mode
    return conn

def init_db():
    """Initializes the main application database schema, adding new columns if missing."""
    conn = connect_db()
    cur = conn.cursor()
    
    # Create 'orders' table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            serial_no INTEGER, -- NEW: Added serial_no column
            customer_name TEXT NOT NULL,
            phone_number TEXT,
            order_form_no TEXT UNIQUE NOT NULL,
            order_date TEXT,
            item_ordered TEXT,
            image_path TEXT,
            customer_delivery_date TEXT,
            worker_delivery_date TEXT,
            issued_to TEXT,
            order_status TEXT,
            financial_year TEXT
        )
    """)
    
    # Add 'serial_no' column to 'orders' table if it doesn't exist
    try:
        cur.execute("PRAGMA table_info(orders)")
        columns = [info[1] for info in cur.fetchall()]
        if 'serial_no' not in columns:
            cur.execute("ALTER TABLE orders ADD COLUMN serial_no INTEGER")
            print("Added 'serial_no' column to 'orders' table.")
    except sqlite3.OperationalError as e:
        print(f"Error adding serial_no to orders table: {e}")


    # Create 'workers' table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS workers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            serial_no INTEGER, -- NEW: Added serial_no column
            name TEXT UNIQUE NOT NULL,
            alias TEXT,
            company_name TEXT,
            address TEXT,
            work_type TEXT,
            contact TEXT
        )
    """)

    # Add 'serial_no' column to 'workers' table if it doesn't exist
    try:
        cur.execute("PRAGMA table_info(workers)")
        columns = [info[1] for info in cur.fetchall()]
        if 'serial_no' not in columns:
            cur.execute("ALTER TABLE workers ADD COLUMN serial_no INTEGER")
            print("Added 'serial_no' column to 'workers' table.")
    except sqlite3.OperationalError as e:
        print(f"Error adding serial_no to workers table: {e}")


    # Create 'settings' table for app configurations
    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    # Initialize default settings if not present
    cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", ('admin_password', INITIAL_ADMIN_PASSWORD))
    cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", ('splash_logo_path', SPLASH_LOGO_DEFAULT))
    
    # Initialize financial years - add current and next two as defaults if none exist
    current_year_for_fy = datetime.now().year
    current_month_for_fy = datetime.now().month
    if current_month_for_fy >= 4:
        initial_fy1 = f"{current_year_for_fy}-{str(current_year_for_fy + 1)[2:]}"
    else:
        initial_fy1 = f"{current_year_for_fy - 1}-{str(current_year_for_fy)[2:]}"
    initial_fy2 = f"{current_year_for_fy}-{str(current_year_for_fy + 1)[2:]}"

    # Ensure unique and sorted list of financial years
    existing_fys_str = load_setting('financial_years', '')
    existing_fys = [f.strip() for f in existing_fys_str.split(',') if f.strip()]
    
    all_fys = sorted(list(set(existing_fys + [initial_fy1, initial_fy2]))) # Ensure unique and sorted
    cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ('financial_years', ','.join(all_fys)))

    conn.commit()
    conn.close() # Close connection after init_db

def load_setting(key, default=None):
    """Loads a setting from the database."""
    conn = sqlite3.connect(DB_PATH) # Connect using DB_PATH for settings
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key=?", (key,))
    result = cur.fetchone()
    conn.close()
    return result[0] if result else default

def save_setting(key, value):
    """Saves a setting to the database."""
    conn = sqlite3.connect(DB_PATH) # Connect using DB_PATH for settings
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def get_financial_years():
    """Retrieves the list of financial years from settings."""
    fys_str = load_setting('financial_years', '')
    return [fy.strip() for fy in fys_str.split(',') if fy.strip()]

def add_financial_year(new_fy):
    """Adds a new financial year to the settings."""
    fys = get_financial_years()
    if new_fy not in fys:
        fys.append(new_fy)
        save_setting('financial_years', ','.join(sorted(fys)))
        return True
    return False

def get_next_serial_number(table_name):
    """Generates the next sequential serial number for a given table."""
    conn = connect_db()
    cur = conn.cursor()
    # Check if 'serial_no' column exists before querying
    cur.execute(f"PRAGMA table_info({table_name})")
    columns = [info[1] for info in cur.fetchall()]
    
    if 'serial_no' in columns:
        cur.execute(f"SELECT MAX(serial_no) FROM {table_name}")
        max_serial = cur.fetchone()[0]
        conn.close()
        return (max_serial if max_serial is not None else 0) + 1
    else:
        print(f"Warning: 'serial_no' column not found in {table_name}. Falling back to MAX(id).")
        cur.execute(f"SELECT MAX(id) FROM {table_name}")
        max_id = cur.fetchone()[0]
        conn.close()
        return (max_id if max_id is not None else 0) + 1


# --- Dark Theme Application ---
def apply_dark_theme(root):
    """Applies a dark theme to the Tkinter application."""
    style = ttk.Style(root)
    root.tk_setPalette(background=BG_COLOR, foreground=FG_COLOR)

    style.theme_use('clam') # 'clam' is a good base for customization
    
    # Base styles for all widgets
    style.configure('.', font=FONT_NORMAL, background=BG_COLOR, foreground=FG_COLOR)
    
    # Specific widget styles
    style.configure('TFrame', background=BG_COLOR)
    style.configure('TLabel', background=BG_COLOR, foreground=FG_COLOR)
    style.configure('TButton', background=BTN_COLOR, foreground=FG_COLOR, borderwidth=1, focusthickness=3, focuscolor='none')
    style.map('TButton', background=[('active', '#333333'), ('pressed', '#000000')],
                                     foreground=[('active', FG_COLOR)])
    
    # Updated TEntry style for yellow input text
    style.configure('TEntry', fieldbackground=ENTRY_BG, foreground=INPUT_TEXT_COLOR, borderwidth=1, insertbackground=INPUT_TEXT_COLOR)
    style.map('TEntry', fieldbackground=[('focus', '#3a3a3a')])    
    
    # Updated TCombobox style for yellow input text
    style.configure('TCombobox', fieldbackground=ENTRY_BG, foreground=INPUT_TEXT_COLOR, 
                    background=ENTRY_BG, selectbackground=ENTRY_BG, selectforeground=INPUT_TEXT_COLOR,
                    arrowcolor=INPUT_TEXT_COLOR) # Arrow color for combobox
    style.map('TCombobox', fieldbackground=[('readonly', ENTRY_BG)],
                                     selectbackground=[('readonly', ENTRY_BG)])
    
    style.configure('TNotebook', background=BG_COLOR, borderwidth=0)
    style.configure('TNotebook.Tab', background=BTN_COLOR, foreground=FG_COLOR, borderwidth=0, padding=[10, 5], font=FONT_TAB_TITLE)
    style.map('TNotebook.Tab', background=[('selected', BG_COLOR)],
                                     foreground=[('selected', FG_COLOR)])
    
    # Updated DateEntry style for yellow input text
    style.configure('DateEntry', fieldbackground=ENTRY_BG, foreground=INPUT_TEXT_COLOR, 
                    background=BTN_COLOR, selectbackground=BTN_COLOR, selectforeground=INPUT_TEXT_COLOR)
    style.configure('Calendar.TButton', background=BTN_COLOR, foreground=FG_COLOR) # Buttons within calendar popup
    style.map('Calendar.TButton', background=[('active', '#333333')])

    style.configure('TScrollbar', troughcolor=BG_COLOR, background=BTN_COLOR)
    style.map('TScrollbar', background=[('active', '#333333')])

    # Custom fonts for specific elements
    style.configure('Large.TLabel', font=FONT_LARGE)
    style.configure('BoldLarge.TLabel', font=FONT_BOLD_LARGE)
    style.configure('Title.TLabel', font=FONT_TITLE)

    # Define Accent.TButton style for edit/cancel toggle
    style.configure('Accent.TButton', background='#4CAF50', foreground='white', borderwidth=1)
    style.map('Accent.TButton', background=[('active', '#45a049'), ('pressed', '#397d3a')])
    
    style.configure('Danger.TButton', background='#F44336', foreground='white') # Red
    style.map('Danger.TButton',
              background=[('active', '#F44336'), ('pressed', '#D32F2F')],
              foreground=[('active', 'white'), ('pressed', 'white')])

    # NEW: Style for the Exit Button
    style.configure('Exit.TButton', background='#CC0000', foreground='white', font=('Segoe UI', 12, 'bold'), borderwidth=1)
    style.map('Exit.TButton',
              background=[('active', '#990000'), ('pressed', '#660000')],
              foreground=[('active', 'white'), ('pressed', 'white')])


# --- Focus Traversal Logic ---
def bind_tab_traversal(parent_widget, widgets_in_order):
    """
    Binds the Enter key to move focus to the next widget in the provided list.
    Args:
        parent_widget: The frame or root widget containing the widgets.
        widgets_in_order: A list of Tkinter widget instances in the desired tab order.
    """
    def focus_next_widget(event):
        # Filter out widgets that are currently disabled (state='readonly')
        active_focusable_widgets = [w for w in widgets_in_order if w.cget('state') != 'readonly' or w == event.widget]

        if not active_focusable_widgets:
            return "break" # No active widgets to focus

        try:
            current_index = active_focusable_widgets.index(event.widget)
            next_widget = active_focusable_widgets[(current_index + 1) % len(active_focusable_widgets)]
            next_widget.focus_set()
            return "break" # Prevents default Enter key behavior (e.g., newline in Text widget)
        except ValueError:
            # Widget not found in the list, ignore
            pass
        except IndexError:
            # Last widget, loop back to first
            if active_focusable_widgets:
                active_focusable_widgets[0].focus_set()
                return "break"

    for widget in widgets_in_order:
        # Only bind to Entry, Text, DateEntry, and Combobox widgets for <Return>
        if isinstance(widget, (ttk.Entry, tk.Text, DateEntry, ttk.Combobox)):
            widget.bind("<Return>", focus_next_widget)
        # For Combobox, also handle the dropdown selection (though Enter typically selects already)
        if isinstance(widget, ttk.Combobox):
            widget.bind("<<ComboboxSelected>>", lambda e, next_w=widgets_in_order[(widgets_in_order.index(widget) + 1) % len(widgets_in_order)]: next_w.focus_set())


# --- Helper for Entry capitalization ---
def capitalize_entry_on_keyrelease(event):
    current_text = event.widget.get()
    capitalized_text = current_text.upper()
    if current_text != capitalized_text:
        cursor_pos = event.widget.index(tk.INSERT)
        event.widget.delete(0, tk.END)
        event.widget.insert(0, capitalized_text)
        event.widget.icursor(cursor_pos) # Restore cursor position

# --- Helper for Text widget capitalization ---
def capitalize_text_on_keyrelease(event):
    widget = event.widget
    current_index = widget.index(tk.INSERT)
    
    # Get the text content, excluding the final newline if it's there
    text_content = widget.get("1.0", "end-1c") 
    capitalized_text = text_content.upper()

    if text_content != capitalized_text:
        widget.delete("1.0", tk.END) # Delete all content
        widget.insert("1.0", capitalized_text) # Insert capitalized content
        
        # Try to restore the cursor position
        try:
            widget.mark_set(tk.INSERT, current_index)
            widget.see(tk.INSERT) # Ensure the cursor is visible
        except tk.TclError:
            # Fallback if the original index is no longer valid
            widget.mark_set(tk.INSERT, tk.END)
            widget.see(tk.END)


# --- Splash Screen ---
class SplashScreen(tk.Toplevel):
    def __init__(self, parent, duration_ms=2000):
        super().__init__(parent)
        self.parent = parent
        self.duration_ms = duration_ms
        self.title("Loading...")
        self.overrideredirect(True) # Removes window decorations

        # Center the splash screen
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        splash_width = 400
        splash_height = 250
        x = (screen_width // 2) - (splash_width // 2)
        y = (screen_height // 2) - (splash_height // 2)
        self.geometry(f"{splash_width}x{splash_height}+{x}+{y}")
        self.configure(background=BG_COLOR)

        self.label_title = ttk.Label(self, text="Jewelry Order System", style='Title.TLabel', anchor='center')
        self.label_title.pack(pady=(20, 10), fill="x")

        logo_path = load_setting('splash_logo_path', SPLASH_LOGO_DEFAULT)
        self.logo_img = None
        if os.path.exists(logo_path):
            try:
                img = Image.open(logo_path)
                img.thumbnail((150, 150))
                self.logo_img = ImageTk.PhotoImage(img)
                self.label_logo = ttk.Label(self, image=self.logo_img, background=BG_COLOR)
                self.label_logo.pack(pady=10)
            except Exception as e:
                print(f"Error loading splash logo: {e}")
                self.label_logo = ttk.Label(self, text="Logo Not Found", style='BoldLarge.TLabel', background=BG_COLOR)
                self.label_logo.pack(pady=10)
        else:
            self.label_logo = ttk.Label(self, text="No Logo Set", style='BoldLarge.TLabel', background=BG_COLOR)
            self.label_logo.pack(pady=10)

        self.progress_bar = ttk.Progressbar(self, mode='indeterminate', length=200, style='TProgressbar')
        self.progress_bar.pack(pady=10)
        self.progress_bar.start(10) # Start animating

        self.parent.withdraw() # Hide the main window until splash is done
        self.after(self.duration_ms, self.destroy_splash)

    def destroy_splash(self):
        self.destroy()
        self.parent.deiconify() # Show the main window
        self.parent.event_generate("<<SplashScreenClosed>>") # Custom event to trigger login

# --- Login Screen ---
class LoginScreen(tk.Toplevel):
    def __init__(self, parent, on_login_success):
        super().__init__(parent)
        self.parent = parent
        self.on_login_success = on_login_success
        self.title("Login")
        self.geometry("500x350")
        self.configure(background=BG_COLOR)
        self.resizable(False, False) # Login screen not resizable

        # Center the login screen
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - (500 // 2)
        y = (screen_height // 2) - (350 // 2)
        self.geometry(f"+{x}+{y}")

        self.protocol("WM_DELETE_WINDOW", self.on_closing) # Handle window close button

        login_frame = ttk.Frame(self)
        login_frame.pack(expand=True, fill="both", padx=30, pady=30)
        login_frame.columnconfigure(1, weight=1)

        ttk.Label(login_frame, text="ADMIN LOGIN", style='Title.TLabel').grid(row=0, columnspan=2, pady=20)

        ttk.Label(login_frame, text="Password:", style='Large.TLabel').grid(row=1, column=0, sticky='e', padx=10, pady=10)
        self.password_entry = ttk.Entry(login_frame, show='*', width=30, font=FONT_LARGE)
        self.password_entry.grid(row=1, column=1, sticky='ew', pady=10)
        # No capitalization for password entry
        self.password_entry.focus_set()

        ttk.Label(login_frame, text="Financial Year:", style='Large.TLabel').grid(row=2, column=0, sticky='e', padx=1, pady=10)
        self.fy_combo = ttk.Combobox(login_frame, values=get_financial_years(), state="readonly", width=28, font=FONT_LARGE)
        self.fy_combo.grid(row=2, column=1, sticky='ew', pady=10)
        # No capitalization for fy combo (readonly anyway)
        
        # Set default FY to current or first available
        current_year = datetime.now().year
        current_month = datetime.now().month
        if current_month >= 4:
            default_fy = f"{current_year}-{str(current_year + 1)[2:]}"
        else:
            default_fy = f"{current_year - 1}-{str(current_year)[2:]}"
        
        if default_fy in get_financial_years():
            self.fy_combo.set(default_fy)
        elif get_financial_years():
            self.fy_combo.set(get_financial_years()[0]) # Set to the first available FY

        login_button = ttk.Button(login_frame, text="LOGIN", command=self.attempt_login, style='TButton')
        login_button.grid(row=3, columnspan=2, pady=20, sticky='w', padx=100)

        # Bind Enter key for navigation
        self.password_entry.bind("<Return>", lambda e: self.fy_combo.focus_set())
        self.fy_combo.bind("<Return>", lambda e: self.attempt_login())
        
    def attempt_login(self):
        entered_password = self.password_entry.get()
        selected_fy = self.fy_combo.get()
        
        stored_password = load_setting('admin_password', INITIAL_ADMIN_PASSWORD) # Default for first run
        
        if entered_password == stored_password and selected_fy:
            self.destroy()
            self.on_login_success(selected_fy)
        else:
            messagebox.showerror("Login Failed", "Invalid Password or Financial Year not selected.")
            self.password_entry.delete(0, tk.END)
            self.password_entry.focus_set()

    def on_closing(self):
        if messagebox.askokcancel("Quit", "Do you want to quit the application?"):
            self.parent.destroy()

# --- Main Application Window Setup ---
def main_app_window(root_instance, financial_year):
    """Sets up the main application window with tabs after successful login."""
    root_instance.title(f"Jewelry Order Management System - FY: {financial_year}")
    root_instance.state('zoomed') # Start maximized

    # Clear previous widgets if any (useful if login re-opens main_app)
    for widget in root_instance.winfo_children():
        widget.destroy()

    notebook = ttk.Notebook(root_instance)
    notebook.pack(expand=True, fill="both", padx=10, pady=10)

    # Create tab frames
    tab1 = ttk.Frame(notebook)
    tab2 = ttk.Frame(notebook)
    tab3 = ttk.Frame(notebook)
    tab4 = ttk.Frame(notebook)
    tab6 = ttk.Frame(notebook) # New tab for Order Management
    tab5 = ttk.Frame(notebook) # Settings tab (renamed from tab5 to tab6 in snippet)

    # Add tabs to the notebook (text changed to UPPERCASE as requested)
    notebook.add(tab1, text="ORDERS INWARD")
    notebook.add(tab2, text="WORKER MASTER")
    notebook.add(tab3, text="STATUS UPDATE")
    notebook.add(tab4, text="STATUS CHECK")
    notebook.add(tab6, text="ORDER MANAGEMENT") # New tab
    notebook.add(tab5, text="SETTINGS") # Settings tab

    # Implement content for each tab
    refresh_orders_workers_callback = implement_orders_tab(tab1, financial_year)
    implement_worker_tab(tab2, refresh_orders_workers_callback) # Pass the callback here
    implement_status_update_tab(tab3, financial_year)
    implement_status_check_tab(tab4)
    implement_order_management_tab(tab6, financial_year)
    implement_settings_tab(tab5)

    # NEW: Add Exit Button in the top right corner
    def confirm_exit():
        if messagebox.askokcancel("Exit Application", "Are you sure you want to exit?"):
            root_instance.destroy() # Close the main window and exit the application

    exit_button = ttk.Button(root_instance, text="EXIT", command=confirm_exit, style='Exit.TButton')
    # Place the button in the top right corner, with some padding
    exit_button.place(relx=1.0, rely=0.0, x=-20, y=10, anchor='ne')


# --- Tab 1: Orders Inward ---
def implement_orders_tab(tab, fy):
    tab.columnconfigure(1, weight=1) # Allow column 1 to expand
    for i in range(10): # Adjusted to make space for serial number and buttons
        tab.rowconfigure(i, weight=0) # Set to 0 initially, specific rows might get weight 1 later
    
    fields = {}
    # Focusable widgets list for tab traversal
    # Will be populated as widgets are created and explicitly re-ordered for `bind_tab_traversal`
    focusable_widgets = []    

    # NEW: Serial Number (Auto-generated for display)
    ttk.Label(tab, text="SERIAL NUMBER", style='Large.TLabel').grid(row=0, column=0, sticky='e', padx=10, pady=5)
    serial_no_label = ttk.Label(tab, text="", style='BoldLarge.TLabel')    
    serial_no_label.grid(row=0, column=1, sticky='w', pady=5)
    
    def update_serial_label():
        serial_no_label.config(text=str(get_next_serial_number('orders')))
    update_serial_label() # Call once to set initial serial number

    def create_label_entry(row, label_text):
        ttk.Label(tab, text=label_text, style='Large.TLabel').grid(row=row, column=0, sticky='e', padx=10, pady=5)
        entry = ttk.Entry(tab, width=40, font=FONT_LARGE)
        entry.grid(row=row, column=1, sticky='ew', pady=5)
        entry.bind("<KeyRelease>", capitalize_entry_on_keyrelease) # Bind for auto-capitalization
        return entry

    # Define fields and add to focusable_widgets in logical order
    fields['Name'] = create_label_entry(1, "Name of the Customer")
    focusable_widgets.append(fields['Name'])

    fields['Phone'] = create_label_entry(2, "Phone Number")
    focusable_widgets.append(fields['Phone'])
    
    # Order Form No. - Now a regular entry, no auto-generate button
    ttk.Label(tab, text="Order Form No.", style='Large.TLabel').grid(row=3, column=0, sticky='e', padx=10, pady=5)
    fields['FormNo'] = ttk.Entry(tab, width=40, font=FONT_LARGE)
    fields['FormNo'].grid(row=3, column=1, sticky='ew', pady=5)
    fields['FormNo'].bind("<KeyRelease>", capitalize_entry_on_keyrelease) # Bind for auto-capitalization
    focusable_widgets.append(fields['FormNo'])

    fields['OrderDate'] = DateEntry(tab, date_pattern='dd/mm/yyyy', font=FONT_LARGE)
    ttk.Label(tab, text="Order Date", style='Large.TLabel').grid(row=4, column=0, sticky='e', padx=10)
    fields['OrderDate'].grid(row=4, column=1, sticky='ew', pady=5)
    focusable_widgets.append(fields['OrderDate'])
    
    fields['Item'] = create_label_entry(5, "Item Ordered")
    focusable_widgets.append(fields['Item'])

    # Image Upload
    img_label = ttk.Label(tab, background=BG_COLOR)
    img_label.grid(row=6, column=1, sticky='w', pady=5)
    fields['ImagePath'] = '' # Store image path

    def upload_image():
        path = filedialog.askopenfilename(filetypes=[["Image files", "*.png;*.jpg;*.jpeg"]])
        if path:
            fields['ImagePath'] = path # Update the path in the fields dictionary
            img = Image.open(path)
            img.thumbnail((100, 100))
            img_tk = ImageTk.PhotoImage(img)
            img_label.image = img_tk  # Keep a reference to prevent garbage collection
            img_label.configure(image=img_tk)
            messagebox.showinfo("Image Uploaded", "Image selected successfully!")
        else:
            messagebox.showwarning("No Image Selected", "No image was selected.")

    upload_image_button = ttk.Button(tab, text="Upload Reference Image", command=upload_image)
    upload_image_button.grid(row=6, column=0, pady=5)
    focusable_widgets.append(upload_image_button) # Add button to focus order
    
    fields['CustDate'] = DateEntry(tab, date_pattern='dd/mm/yyyy', font=FONT_LARGE)
    ttk.Label(tab, text="Customer Delivery Date", style='Large.TLabel').grid(row=7, column=0, sticky='e')
    fields['CustDate'].grid(row=7, column=1, sticky='ew', pady=5)
    focusable_widgets.append(fields['CustDate'])
    
    fields['WorkDate'] = DateEntry(tab, date_pattern='dd/mm/yyyy', font=FONT_LARGE)
    ttk.Label(tab, text="Worker Delivery Date", style='Large.TLabel').grid(row=8, column=0, sticky='e')
    fields['WorkDate'].grid(row=8, column=1, sticky='ew', pady=5)
    focusable_widgets.append(fields['WorkDate'])

    ttk.Label(tab, text="Issued To", style='Large.TLabel').grid(row=9, column=0, sticky='e')
    worker_box = ttk.Combobox(tab, width=37, state="readonly", font=FONT_LARGE) # Make combobox readonly
    worker_box.grid(row=9, column=1, sticky='ew', pady=5)
    fields['Worker'] = worker_box
    focusable_widgets.append(fields['Worker'])

    def refresh_workers():
        conn = connect_db()
        cur = conn.cursor()
        cur.execute("SELECT name FROM workers")
        names = [w[0] for w in cur.fetchall()]
        worker_box['values'] = names
        conn.close()

    refresh_workers() # Initial call when tab is loaded

    def clear_orders_fields():
        """Clears all input fields in the Orders Inward tab and updates serial number."""
        for key, field in fields.items():
            if key != 'ImagePath': # ImagePath is handled separately
                if isinstance(field, ttk.Entry):
                    field.delete(0, tk.END)
                elif isinstance(field, DateEntry):
                    field.set_date(datetime.now()) # Reset date to current
                elif isinstance(field, ttk.Combobox):
                    field.set('') # Clear selected value
        img_label.configure(image='') # Clear image display
        fields['ImagePath'] = '' # Clear stored image path
        update_serial_label() # Update serial number for the new entry
        fields['Name'].focus_set() # Focus back to the first field

    def save_order():
        data = {
            'serial_no': int(serial_no_label.cget("text")), # Get serial number for saving
            'name': fields['Name'].get().strip(),
            'phone': fields['Phone'].get().strip(),
            'form': fields['FormNo'].get().strip(),
            'order_date': fields['OrderDate'].get(),
            'item': fields['Item'].get().strip(),
            'image': fields.get('ImagePath', ''), # Get safely, defaults to empty string
            'cust_date': fields['CustDate'].get(),
            'work_date': fields['WorkDate'].get(),
            'worker': fields['Worker'].get().strip(),
            'status': "Order Issued"
        }
        
        # Basic validation
        if not all([data['name'], data['phone'], data['form'], data['item'], data['worker']]):
            messagebox.showwarning("Missing Information", "Please fill in all required fields:\nCustomer Name, Phone Number, Order Form No., Item Ordered, and Issued To.")
            return
        
        try:
            conn = connect_db()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO orders (serial_no, customer_name, phone_number, order_form_no, order_date,
                    item_ordered, image_path, customer_delivery_date, worker_delivery_date,
                    issued_to, order_status, financial_year)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (data['serial_no'], data['name'], data['phone'], data['form'], data['order_date'],
                  data['item'], data['image'], data['cust_date'], data['work_date'],
                  data['worker'], data['status'], fy))
            conn.commit()
            conn.close()
            messagebox.showinfo("Saved", "Order saved successfully.")
            
            clear_orders_fields() # Use the new clear function
            
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed: orders.order_form_no" in str(e):
                messagebox.showerror("Duplicate Entry", f"Order Form No. '{data['form']}' must be unique. Please enter a different one.")
            else:
                messagebox.showerror("Database Error", f"A database error occurred: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {e}")

    save_button = ttk.Button(tab, text="Save Order", command=save_order)
    save_button.grid(row=10, column=1, sticky='w', pady=10)
    focusable_widgets.append(save_button) # Add save button to focus order

    reset_button = ttk.Button(tab, text="RESET ENTRY", command=clear_orders_fields) # Reset button
    reset_button.grid(row=10, column=0, sticky='e', pady=10, padx=10) # Positioned to the left of save
    focusable_widgets.append(reset_button)

    # Apply tab traversal
    bind_tab_traversal(tab, focusable_widgets)

    return refresh_workers # Return the refresh function so other tabs can call it

# --- Tab 2: Worker Master ---
def implement_worker_tab(tab, refresh_orders_workers_callback): # Accept the callback
    tab.columnconfigure(1, weight=1) # Allow column 1 to expand
    for i in range(10): # Adjusted to make space for serial number and buttons
        tab.rowconfigure(i, weight=0)
    
    entries = {}
    focusable_widgets = []

    # NEW: Serial Number (Auto-generated for display)
    ttk.Label(tab, text="SERIAL NUMBER", style='Large.TLabel').grid(row=0, column=0, sticky='e', padx=10, pady=5)
    serial_no_label = ttk.Label(tab, text="", style='BoldLarge.TLabel')    
    serial_no_label.grid(row=0, column=1, sticky='w', pady=5)

    def update_serial_label():
        serial_no_label.config(text=str(get_next_serial_number('workers')))
    update_serial_label() # Call once to set initial serial number

    def create_entry(row, label):
        ttk.Label(tab, text=label, style='Large.TLabel').grid(row=row, column=0, sticky='e', padx=10, pady=5)
        entry = ttk.Entry(tab, width=40, font=FONT_LARGE)
        entry.grid(row=row, column=1, sticky='ew', pady=5)
        entry.bind("<KeyRelease>", capitalize_entry_on_keyrelease) # Bind for auto-capitalization
        return entry

    entries['name'] = create_entry(1, "Name")
    focusable_widgets.append(entries['name'])

    entries['alias'] = create_entry(2, "Alias")
    focusable_widgets.append(entries['alias'])

    entries['company'] = create_entry(3, "Company Name")
    focusable_widgets.append(entries['company'])

    ttk.Label(tab, text="Address", style='Large.TLabel').grid(row=4, column=0, sticky='ne', padx=10, pady=5) # 'ne' for top alignment
    address_text = tk.Text(tab, height=4, width=30, bg=ENTRY_BG, fg=INPUT_TEXT_COLOR, insertbackground=INPUT_TEXT_COLOR, font=FONT_LARGE)
    address_text.grid(row=4, column=1, sticky='ew', pady=5)
    address_text.bind("<KeyRelease>", capitalize_text_on_keyrelease) # Bind for auto-capitalization
    entries['address_text'] = address_text # Storing the Text widget itself for separate handling
    focusable_widgets.append(address_text)

    entries['type'] = create_entry(5, "Type of Work")
    focusable_widgets.append(entries['type'])

    entries['contact'] = create_entry(6, "Contact")
    focusable_widgets.append(entries['contact'])

    def clear_worker_fields(): # Clear function for Worker tab
        for entry_widget in entries.values():
            if isinstance(entry_widget, ttk.Entry):
                entry_widget.delete(0, tk.END)
        entries['address_text'].delete("1.0", tk.END)
        update_serial_label() # Update serial number
        entries['name'].focus_set()

    def save_worker():
        name = entries['name'].get().strip()
        serial_no = int(serial_no_label.cget("text")) # Get serial number for saving
        if not name:
            messagebox.showwarning("Missing Information", "Worker Name is required.")
            entries['name'].focus_set()
            return

        try:
            conn = connect_db()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO workers (serial_no, name, alias, company_name, address, work_type, contact)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (serial_no, name, entries['alias'].get().strip(), entries['company'].get().strip(),
                  entries['address_text'].get("1.0", "end").strip(), entries['type'].get().strip(), entries['contact'].get().strip()))
            conn.commit()
            conn.close()
            messagebox.showinfo("SAVED", "Worker profile saved successfully.")
            
            clear_worker_fields() # Use the clear function
            if refresh_orders_workers_callback: # Call the callback to refresh orders tab's workers
                refresh_orders_workers_callback()

        except sqlite3.IntegrityError:
            messagebox.showerror("DUPLICATE ENTRY", f"A worker named '{name}' already exists.")
            entries['name'].focus_set()
        except Exception as e:
            messagebox.showerror("ERROR", f"An error occurred: {e}")

    save_button = ttk.Button(tab, text="SAVE WORKER", command=save_worker)
    save_button.grid(row=7, column=1, sticky='w', pady=10)
    focusable_widgets.append(save_button)

    reset_button = ttk.Button(tab, text="RESET ENTRY", command=clear_worker_fields) # Reset button
    reset_button.grid(row=7, column=0, sticky='e', pady=10, padx=10) # Positioned to the left of save
    focusable_widgets.append(reset_button)
    
    bind_tab_traversal(tab, focusable_widgets)

# --- Tab 3: Status Update ---
def implement_status_update_tab(tab, fy):
    tab.columnconfigure(1, weight=1)
    for i in range(5): # Adjusted row count for new reset button
        tab.rowconfigure(i, weight=0)

    focusable_widgets = []

    ttk.Label(tab, text="Select Financial Year", style='Large.TLabel').grid(row=0, column=0, padx=10, pady=10, sticky="e")
    
    all_fys = get_financial_years()
    year_combo = ttk.Combobox(tab, values=all_fys, state="readonly", width=30, font=FONT_LARGE)
    year_combo.set(fy) 
    year_combo.grid(row=0, column=1, sticky="ew", pady=10)
    focusable_widgets.append(year_combo)

    ttk.Label(tab, text="Order Form No.", style='Large.TLabel').grid(row=1, column=0, padx=10, pady=10, sticky="e")
    form_entry = ttk.Entry(tab, width=32, font=FONT_LARGE)
    form_entry.grid(row=1, column=1, sticky="ew", pady=10)
    form_entry.bind("<KeyRelease>", capitalize_entry_on_keyrelease) # Bind for auto-capitalization
    focusable_widgets.append(form_entry)

    ttk.Label(tab, text="Order Status", style='Large.TLabel').grid(row=2, column=0, padx=10, pady=10, sticky="e")
    status_combo = ttk.Combobox(tab, values=["Order Issued", "In Process", "Ready", "Delivered", "Cancelled"], state="readonly", width=30, font=FONT_LARGE)
    status_combo.grid(row=2, column=1, sticky="ew", pady=10)
    focusable_widgets.append(status_combo)

    def clear_status_update_fields(): # Clear function for Status Update tab
        form_entry.delete(0, tk.END)
        status_combo.set('')
        year_combo.set(fy) # Reset FY to current default
        form_entry.focus_set()

    def fetch_status():
        order_form_no = form_entry.get().strip()
        selected_fy = year_combo.get()
        if not order_form_no:
            messagebox.showwarning("Input Required", "Please enter an Order Form No.")
            form_entry.focus_set()
            return

        conn = connect_db()
        if conn is None: # Handle database connection error
            return
        cur = conn.cursor()
        cur.execute("SELECT order_status FROM orders WHERE order_form_no=? AND financial_year=?", (order_form_no, selected_fy))
        row = cur.fetchone()
        conn.close()
        if row:
            status_combo.set(row[0])
            messagebox.showinfo("STATUS FETCHED", f"Current status for {order_form_no}: {row[0]}")
        else:
            messagebox.showerror("NOT FOUND", f"Order '{order_form_no}' not found for financial year {selected_fy}.")
            status_combo.set('')

    def update_status():
        order_form_no = form_entry.get().strip()
        new_status = status_combo.get()
        selected_fy = year_combo.get()

        if not order_form_no or not new_status:
            messagebox.showwarning("Input Required", "Please enter Order Form No. and select a new status.")
            return

        conn = connect_db()
        if conn is None: # Handle database connection error
            return
        try:
            cur = conn.cursor()
            cur.execute("UPDATE orders SET order_status=? WHERE order_form_no=? AND financial_year=?",
                        (new_status, order_form_no, selected_fy))
            conn.commit()
            if cur.rowcount > 0: # Check if any row was actually updated
                messagebox.showinfo("UPDATED", "Order status updated successfully.")
                clear_status_update_fields() # Use clear function
            else:
                messagebox.showwarning("NOT FOUND", f"No order found with form number '{order_form_no}' for financial year {selected_fy} to update.")
            conn.close()
        except Exception as e:
            messagebox.showerror("ERROR", f"An error occurred during update: {e}")
            if conn:
                conn.close()

    fetch_button = ttk.Button(tab, text="FETCH STATUS", command=fetch_status)
    fetch_button.grid(row=3, column=0, padx=10, pady=10)
    focusable_widgets.append(fetch_button)

    update_button = ttk.Button(tab, text="UPDATE STATUS", command=update_status)
    update_button.grid(row=3, column=1, padx=10, pady=10, sticky="w")
    focusable_widgets.append(update_button)

    reset_button = ttk.Button(tab, text="RESET ENTRY", command=clear_status_update_fields) # Reset button
    reset_button.grid(row=4, column=0, columnspan=2, pady=10, sticky='ew', padx=10) # Centered below other buttons
    focusable_widgets.append(reset_button)

    bind_tab_traversal(tab, focusable_widgets)

# --- Tab 4: Status Check ---
def implement_status_check_tab(tab):
    tab.columnconfigure(1, weight=1)
    for i in range(5): # Adjusted row count for new reset button
        tab.rowconfigure(i, weight=0)

    focusable_widgets = []

    ttk.Label(tab, text="Enter Order Form No. / Phone Number", style='Large.TLabel').grid(row=0, column=0, padx=10, pady=10, sticky="e")
    search_entry = ttk.Entry(tab, width=40, font=FONT_LARGE)
    search_entry.grid(row=0, column=1, sticky="ew", pady=10)
    search_entry.bind("<KeyRelease>", capitalize_entry_on_keyrelease) # Bind for auto-capitalization
    focusable_widgets.append(search_entry)

    result_label = ttk.Label(tab, text="", style='BoldLarge.TLabel')
    result_label.grid(row=2, column=0, columnspan=2, pady=10)

    extra_info = ttk.Label(tab, text="", font=FONT_NORMAL)
    extra_info.grid(row=3, column=0, columnspan=2)

    def clear_status_check_fields(): # Clear function for Status Check tab
        search_entry.delete(0, tk.END)
        result_label.configure(text="", foreground=FG_COLOR)
        extra_info.configure(text="")
        search_entry.focus_set()

    def check_status():
        key = search_entry.get().strip()
        if not key:
            result_label.configure(text="Please enter a search query.", foreground="red") # Changed to red for clearer error
            extra_info.configure(text="")
            return

        conn = connect_db()
        if conn is None: # Handle database connection error
            return
        cur = conn.cursor()
        cur.execute("""
            SELECT order_status, worker_delivery_date, customer_delivery_date, customer_name, item_ordered, order_form_no
            FROM orders WHERE order_form_no=? OR phone_number=?
        """, (key, key))
        row = cur.fetchone()
        conn.close()
        
        if row:
            status, w_date, c_date, cust_name, item_name, order_form_no = row
            
            if status.lower() == "ready":
                result_label.configure(text="READY FOR PICKUP", foreground="green")
                extra_info.configure(text=f"Order: {order_form_no}\nCustomer: {cust_name}\nItem: {item_name}\nCustomer Delivery Date: {c_date}")
            elif status.lower() == "delivered":
                result_label.configure(text="DELIVERED", foreground="blue")
                extra_info.configure(text=f"Order: {order_form_no}\nCustomer: {cust_name}\nItem: {item_name}\nOrder has been delivered.")
            elif status.lower() == "cancelled":
                result_label.configure(text="CANCELLED", foreground="grey")
                extra_info.configure(text=f"Order: {order_form_no}\nCustomer: {cust_name}\nItem: {item_name}\nThis order has been cancelled.")
            else: # In Process or Order Issued
                result_label.configure(text="IN PROCESS", foreground="orange") # Changed to orange, red is often for errors
                extra_info.configure(text=f"Order: {order_form_no}\nCustomer: {cust_name}\nItem: {item_name}\nWorker Date: {w_date}\nCustomer Date: {c_date}")
        else:
            result_label.configure(text="ORDER NOT FOUND", foreground="red") # Changed to red for clearer error
            extra_info.configure(text="Please verify the Order Form No. or Phone Number.")
        search_entry.focus_set()

    check_button = ttk.Button(tab, text="CHECK STATUS", command=check_status)
    check_button.grid(row=1, column=1, sticky="w", pady=5)
    focusable_widgets.append(check_button)

    reset_button = ttk.Button(tab, text="RESET ENTRY", command=clear_status_check_fields) # Reset button
    reset_button.grid(row=1, column=0, sticky='e', pady=5, padx=10) # Positioned to the left of check
    focusable_widgets.append(reset_button)
    
    bind_tab_traversal(tab, focusable_widgets)

# --- Tab 5: Order Management (New) ---
def implement_order_management_tab(tab, fy):
    tab.columnconfigure(1, weight=1)
    for i in range(15): # Adjusted for buttons and potential image/spacing
        tab.rowconfigure(i, weight=0)

    order_fields = {} # Dictionary to hold entry widgets for loaded order
    focusable_widgets = [] # Main focusable widgets for this tab

    # Search section
    ttk.Label(tab, text="Enter Order Form No.", style='Large.TLabel').grid(row=0, column=0, sticky='e', padx=10, pady=5)
    search_entry = ttk.Entry(tab, width=40, font=FONT_LARGE)
    search_entry.grid(row=0, column=1, sticky='ew', pady=5)
    search_entry.bind("<KeyRelease>", capitalize_entry_on_keyrelease) # Bind for auto-capitalization
    focusable_widgets.append(search_entry) # Always focusable

    def set_editable_state(state):
        """Sets the state of all data entry widgets in the order_fields dictionary."""
        # Fields that should be editable in 'normal' state
        editable_fields = ['Name', 'Phone', 'OrderDate', 'Item', 'CustDate', 'WorkDate', 'Worker', 'Status']
        
        for field_key in editable_fields:
            if field_key in order_fields:
                widget = order_fields[field_key]
                widget.config(state=state)
        
        # Financial Year is display-only in this section, always readonly
        if 'FY' in order_fields:
            order_fields['FY'].config(state='readonly')

        # Manage visibility of change_image_button based on state
        if state == 'normal':
            change_image_button.grid()
        else:
            change_image_button.grid_remove()

        # Update focusable_widgets list based on current mode
        update_focusable_widgets(state)

    def update_focusable_widgets(current_state):
        """Helper to update the focusable_widgets list based on edit mode."""
        focusable_widgets.clear()
        focusable_widgets.append(search_entry)
        focusable_widgets.append(load_button)
        focusable_widgets.append(edit_button) # This button is always clickable

        if current_state == 'normal': # In edit mode
            # Add all editable fields
            focusable_widgets.extend([
                order_fields['Name'], order_fields['Phone'], order_fields['OrderDate'],
                order_fields['Item'], change_image_button, order_fields['CustDate'],
                order_fields['WorkDate'], order_fields['Worker'], order_fields['Status'],
                update_order_button, delete_button
            ])
        
        focusable_widgets.append(reset_manage_button) # This button is always clickable
        bind_tab_traversal(tab, focusable_widgets)


    def clear_order_management_fields(): # Clear function for Order Management tab
        search_entry.delete(0, tk.END)
        order_fields['OrderFormDisplay'].config(text="") # Clear the displayed order form number

        for field_name in ['Name', 'Phone', 'OrderDate', 'Item', 'CustDate', 'WorkDate', 'Worker', 'Status', 'FY']:
            if field_name in order_fields:
                widget = order_fields[field_name]
                if isinstance(widget, ttk.Entry):
                    widget.config(state='normal') # Ensure editable before clearing
                    widget.delete(0, tk.END)
                elif isinstance(widget, DateEntry):
                    widget.config(state='normal') # Ensure editable before clearing
                    widget.set_date(datetime.now()) # Reset to current date
                elif isinstance(widget, ttk.Combobox):
                    widget.config(state='normal') # Ensure editable before clearing
                    widget.set('')
        
        if 'ImageDisplay' in order_fields:
            order_fields['ImageDisplay'].configure(image='', text="No Image Loaded") # Clear image and set text
            order_fields['ImageDisplay'].image = None # Clear image reference

        order_fields['LoadedID'] = None # Clear loaded ID
        order_fields['LoadedImagePath'] = '' # Clear stored image path
        
        set_editable_state('readonly') # Set all fields back to readonly
        edit_button.config(text="EDIT ORDER", style='TButton') # Revert edit button
        update_order_button.grid_remove() # Hide update button
        delete_button.grid_remove() # Hide delete button
        change_image_button.grid_remove() # Hide change image button
        search_entry.focus_set()


    def load_order():
        order_form_no = search_entry.get().strip()
        if not order_form_no:
            messagebox.showwarning("Input Required", "Please enter an **Order Form No.** to load.")
            search_entry.focus_set()
            return
        
        # Always clear fields before attempting to load new data
        # This prevents stale data from previous loads/edits
        clear_order_management_fields() 

        conn = connect_db()
        if conn is None: # Handle database connection error
            return
        cur = conn.cursor()
        cur.execute("""
            SELECT customer_name, phone_number, order_date, item_ordered, image_path,
                   customer_delivery_date, worker_delivery_date, issued_to, order_status, financial_year, id
            FROM orders WHERE order_form_no=?
        """, (order_form_no,))
        order_data = cur.fetchone()
        conn.close()

        if order_data:
            # Temporarily enable fields to populate, then set to readonly
            set_editable_state('normal') # Enable editing temporarily to fill values
            
            # Populate fields
            order_fields['LoadedID'] = order_data[10] # Store the database ID for update/delete
            order_fields['OrderFormDisplay'].config(text=order_form_no) # Display the loaded order form number
            order_fields['Name'].insert(0, order_data[0])
            order_fields['Phone'].insert(0, order_data[1])
            
            # Date fields parsing with robust error handling
            date_fields = [
                ('OrderDate', order_data[2], "Order Date"),
                ('CustDate', order_data[5], "Customer Delivery Date"),
                ('WorkDate', order_data[6], "Worker Delivery Date")
            ]

            for field_key, date_str, field_name_display in date_fields:
                try:
                    # Clear existing value before setting new one for DateEntry
                    order_fields[field_key].set_date(datetime.strptime(date_str, '%d/%m/%Y'))
                except (ValueError, TypeError): # Handle cases where date_str might be None or invalid
                    messagebox.showwarning("Date Format Error", 
                                           f"The **{field_name_display}** `'{date_str}'` for order **{order_form_no}** has an invalid format. "
                                           "It has been reset to the current date. Please correct it if necessary during edit.")
                    order_fields[field_key].set_date(datetime.now()) # Fallback to current date
            
            order_fields['Item'].insert(0, order_data[3])
            
            # Image path
            current_image_path = order_data[4]
            order_fields['LoadedImagePath'] = current_image_path # Store loaded path
            if current_image_path and os.path.exists(current_image_path):
                try:
                    img = Image.open(current_image_path)
                    img.thumbnail((100, 100))
                    img_tk = ImageTk.PhotoImage(img)
                    order_fields['ImageDisplay'].image = img_tk
                    order_fields['ImageDisplay'].configure(image=img_tk, text="") # Clear text if image loads
                except Exception as e:
                    messagebox.showwarning("Image Load Error", f"Error loading image `'{current_image_path}'`: {e}. Image not displayed.")
                    order_fields['ImageDisplay'].configure(image='', text="Image Error") # Show text on error
            else:
                order_fields['ImageDisplay'].configure(image='', text="No Image/Invalid Path") # Indicate no image

            order_fields['Worker'].set(order_data[7])
            order_fields['Status'].set(order_data[8])
            
            # Financial Year is read-only, needs special handling for insertion
            order_fields['FY'].config(state='normal') # Temporarily normal to insert
            order_fields['FY'].delete(0, tk.END) # Clear existing content before inserting
            order_fields['FY'].insert(0, order_data[9]) # Financial Year of the loaded order
            order_fields['FY'].config(state='readonly') # Set back to readonly

            messagebox.showinfo("ORDER LOADED", f"Order **{order_form_no}** loaded successfully. You can now edit or delete it.")
            set_editable_state('readonly') # Set fields back to readonly after populating
            edit_button.config(text="EDIT ORDER", style='TButton') # Reset edit button state
            update_order_button.grid_remove()
            delete_button.grid_remove()
            change_image_button.grid_remove() # Ensure it's hidden initially after load
        else:
            messagebox.showerror("NOT FOUND", f"Order `'{order_form_no}'` not found. Please check the **Order Form No.**")
            clear_order_management_fields() # Clear fields if not found

    load_button = ttk.Button(tab, text="LOAD ORDER", command=load_order)
    load_button.grid(row=1, column=1, sticky='w', pady=5)
    focusable_widgets.append(load_button)

    # --- Order Details Display ---
    # Row for Order Form No. (display only, not editable directly in this section)
    ttk.Label(tab, text="Order Form No.", style='Large.TLabel').grid(row=2, column=0, sticky='e', padx=10, pady=5)
    order_form_display = ttk.Label(tab, text="", font=FONT_LARGE) # This label will display the loaded order form number
    order_form_display.grid(row=2, column=1, sticky='w', pady=5)
    # Store reference to update it when an order is loaded
    order_fields['OrderFormDisplay'] = order_form_display 

    # --- Input Fields for Order Management ---
    # These labels and widgets are created once. Their state will be managed by set_editable_state.
    current_row = 3
    for label_text, field_key, widget_type in [
        ("Customer Name", 'Name', 'entry'),
        ("Phone Number", 'Phone', 'entry'),
        ("Order Date", 'OrderDate', 'date'),
        ("Item Ordered", 'Item', 'entry'),
        ("Customer Delivery Date", 'CustDate', 'date'),
        ("Worker Delivery Date", 'WorkDate', 'date'),
        ("Issued To (Worker)", 'Worker', 'combobox'), 
        ("Order Status", 'Status', 'combobox'),
        ("Financial Year", "FY", 'entry') # Display FY but not editable directly
    ]:
        ttk.Label(tab, text=label_text, style='Large.TLabel').grid(row=current_row, column=0, sticky='e', padx=10, pady=5)
        if widget_type == 'entry':
            entry = ttk.Entry(tab, width=40, font=FONT_LARGE, state='readonly')
            entry.grid(row=current_row, column=1, sticky='ew', pady=5)
            entry.bind("<KeyRelease>", capitalize_entry_on_keyrelease) # Bind for auto-capitalization
            order_fields[field_key] = entry
        elif widget_type == 'date':
            date_entry = DateEntry(tab, width=37, background='darkblue', foreground='white', borderwidth=2,
                                   date_pattern='dd/mm/yyyy', font=FONT_LARGE, state='readonly')
            date_entry.grid(row=current_row, column=1, sticky='ew', pady=5)
            order_fields[field_key] = date_entry
        elif widget_type == 'combobox':
            if field_key == 'Worker':
                conn = connect_db()
                worker_names = []
                if conn:
                    cur = conn.cursor()
                    cur.execute("SELECT name FROM workers")
                    worker_names = [w[0] for w in cur.fetchall()]
                    conn.close()
                combo = ttk.Combobox(tab, values=worker_names, state="readonly", width=38, font=FONT_LARGE)
            elif field_key == 'Status':
                combo = ttk.Combobox(tab, values=["Order Issued", "In Process", "Ready", "Delivered", "Cancelled"], state="readonly", width=38, font=FONT_LARGE)
            combo.grid(row=current_row, column=1, sticky="ew", pady=5)
            order_fields[field_key] = combo
        current_row += 1

    # Image Display
    ttk.Label(tab, text="Order Image", style='Large.TLabel').grid(row=current_row, column=0, sticky='ne', padx=10, pady=5)
    image_display_label = ttk.Label(tab, text="No Image Loaded", font=FONT_NORMAL, compound="image")
    image_display_label.grid(row=current_row, column=1, sticky='nw', pady=5)
    order_fields['ImageDisplay'] = image_display_label
    current_row += 1

    def change_image():
        current_image_path = order_fields.get('LoadedImagePath', '')
        # Set initial directory to the directory of the currently loaded image, if it exists
        initial_dir = os.path.dirname(current_image_path) if current_image_path and os.path.exists(current_image_path) else os.getcwd()

        file_path = filedialog.askopenfilename(initialdir=initial_dir,
                                               filetypes=[("Image Files", "*.png *.jpg *.jpeg *.gif *.bmp")])
        if file_path:
            try:
                img = Image.open(file_path)
                img.thumbnail((100, 100))
                img_tk = ImageTk.PhotoImage(img)
                order_fields['ImageDisplay'].image = img_tk # Keep a reference!
                order_fields['ImageDisplay'].configure(image=img_tk, text="") # Clear text if image loads
                order_fields['LoadedImagePath'] = file_path # Update the stored path for saving
            except Exception as e:
                messagebox.showerror("Image Error", f"Could not load image: {e}")
                order_fields['ImageDisplay'].configure(image='', text="Image Load Failed") # Show text on error
        else:
            messagebox.showwarning("NO IMAGE SELECTED", "No new image was selected.")

    change_image_button = ttk.Button(tab, text="CHANGE IMAGE", command=change_image)
    change_image_button.grid(row=current_row, column=0, pady=5, sticky='e', padx=10) # Positioned under image label
    change_image_button.grid_remove() # Initially hidden

    # --- Action Buttons ---
    current_row += 1 # Move to after image section and its button

    def toggle_edit_mode():
        if order_fields.get('LoadedID') is None:
            messagebox.showwarning("NO ORDER LOADED", "Please load an order first to enable edit mode.")
            return

        if edit_button.cget('text') == "EDIT ORDER":
            set_editable_state('normal')
            edit_button.config(text="CANCEL EDIT", style='Accent.TButton') 
            update_order_button.grid(row=current_row, column=0, padx=10, pady=10, sticky='e')
            delete_button.grid(row=current_row, column=1, padx=10, pady=10, sticky='w')
            # change_image_button visibility is handled by set_editable_state
            order_fields['Name'].focus_set() # Focus on the first editable field
        else: # CANCEL EDIT
            set_editable_state('readonly')
            edit_button.config(text="EDIT ORDER", style='TButton') 
            update_order_button.grid_remove() # Hide update button
            delete_button.grid_remove() # Hide delete button
            # change_image_button visibility is handled by set_editable_state
            load_order() # Reload original data to discard changes (important for 'cancel edit')
            search_entry.focus_set() # Return focus to search

    def update_order():
        order_id = order_fields.get('LoadedID')
        if order_id is None:
            messagebox.showwarning("NO ORDER LOADED", "Please load an order first before attempting to update.")
            return

        confirm = messagebox.askyesno("CONFIRM UPDATE", "Are you sure you want to update this order?")
        if not confirm:
            return

        # Gather updated data
        try:
            customer_name = order_fields['Name'].get().strip()
            phone_number = order_fields['Phone'].get().strip()
            order_date = order_fields['OrderDate'].get_date().strftime('%d/%m/%Y')
            item_ordered = order_fields['Item'].get().strip()
            customer_delivery_date = order_fields['CustDate'].get_date().strftime('%d/%m/%Y')
            worker_delivery_date = order_fields['WorkDate'].get_date().strftime('%d/%m/%Y')
            issued_to = order_fields['Worker'].get().strip()
            order_status = order_fields['Status'].get().strip()
            # financial_year_loaded is for WHERE clause, not updated by user here
            financial_year_loaded = order_fields['FY'].get().strip() 
            image_path = order_fields.get('LoadedImagePath', '') # Get the (potentially updated) image path

            # Basic validation
            if not all([customer_name, phone_number, order_date, item_ordered, customer_delivery_date, 
                        worker_delivery_date, issued_to, order_status, financial_year_loaded]):
                messagebox.showwarning("Missing Information", "All fields must be filled to update the order.")
                return

            conn = connect_db()
            if conn is None:
                return
            cur = conn.cursor()
            cur.execute("""
                UPDATE orders SET
                    customer_name=?, phone_number=?, order_date=?, item_ordered=?, image_path=?,
                    customer_delivery_date=?, worker_delivery_date=?, issued_to=?, order_status=?
                WHERE id=? AND financial_year=?
            """, (customer_name, phone_number, order_date, item_ordered, image_path,
                  customer_delivery_date, worker_delivery_date, issued_to, order_status,
                  order_id, financial_year_loaded))
            conn.commit()

            if cur.rowcount > 0:
                messagebox.showinfo("UPDATE SUCCESS", "Order updated successfully!")
                # After successful update, revert to readonly mode and clear fields
                clear_order_management_fields() 
            else:
                messagebox.showwarning("UPDATE FAILED", "No order found with the given ID and financial year, or no changes were made.")
            conn.close()
        except Exception as e:
            messagebox.showerror("ERROR", f"An error occurred during update: {e}")
            if conn:
                conn.close()

    def delete_order():
        order_id = order_fields.get('LoadedID')
        order_form_num = search_entry.get().strip() # Get the order form number from search entry
        if order_id is None:
            messagebox.showwarning("NO ORDER LOADED", "Please load an order first before attempting to delete.")
            return

        if messagebox.askyesno("CONFIRM DELETE", f"Are you sure you want to delete order `'{order_form_num}'` permanently? This action cannot be undone."):
            conn = connect_db()
            if conn is None:
                return
            try:
                cur = conn.cursor()
                cur.execute("DELETE FROM orders WHERE id=?", (order_id,))
                conn.commit()
                if cur.rowcount > 0:
                    messagebox.showinfo("DELETE SUCCESS", f"Order `'{order_form_num}'` deleted successfully.")
                    clear_order_management_fields() # Clear all fields and hide buttons
                else:
                    messagebox.showwarning("DELETE FAILED", "No order found with the given ID to delete.")
                conn.close()
            except Exception as e:
                messagebox.showerror("ERROR", f"An error occurred during deletion: {e}")
                if conn:
                    conn.close()

    edit_button = ttk.Button(tab, text="EDIT ORDER", command=toggle_edit_mode)
    edit_button.grid(row=current_row, column=0, padx=10, pady=10, sticky='e')
    # No longer adding to focusable_widgets here, handled by update_focusable_widgets()

    update_order_button = ttk.Button(tab, text="SAVE CHANGES", command=update_order, style='Accent.TButton')
    update_order_button.grid(row=current_row, column=0, padx=10, pady=10, sticky='e') # Positioned same as edit, but hidden
    update_order_button.grid_remove() # Hidden by default
    # Not adding to focusable_widgets here, handled by update_focusable_widgets()

    delete_button = ttk.Button(tab, text="DELETE ORDER", command=delete_order, style='Danger.TButton')
    delete_button.grid(row=current_row, column=1, padx=10, pady=10, sticky='w') # Positioned same as edit, but hidden
    delete_button.grid_remove() # Hidden by default
    # Not adding to focusable_widgets here, handled by update_focusable_widgets()

    reset_manage_button = ttk.Button(tab, text="RESET ALL", command=clear_order_management_fields)
    reset_manage_button.grid(row=current_row + 1, column=0, columnspan=2, pady=10, sticky='ew', padx=10)
    # No longer adding to focusable_widgets here, handled by update_focusable_widgets()
    
    # Initialize focusable widgets after all buttons are created
    update_focusable_widgets('readonly')


# --- Tab 6: Settings (Original Tab 5) ---
def implement_settings_tab(tab):
    tab.columnconfigure(1, weight=1)
    for i in range(15): # Adjusted row count for reset button
        tab.rowconfigure(i, weight=0)

    focusable_widgets = [] # For settings tab fields

    # Password Management
    ttk.Label(tab, text="CHANGE ADMIN PASSWORD", style='BoldLarge.TLabel').grid(row=0, column=0, columnspan=2, pady=10, sticky='w', padx=10)
    
    ttk.Label(tab, text="New Password:", style='Large.TLabel').grid(row=1, column=0, sticky='e', padx=10)
    new_password_entry = ttk.Entry(tab, show='*', width=30, font=FONT_LARGE)
    new_password_entry.grid(row=1, column=1, sticky='ew', pady=5)
    focusable_widgets.append(new_password_entry)

    ttk.Label(tab, text="Confirm Password:", style='Large.TLabel').grid(row=2, column=0, sticky='e', padx=10)
    confirm_password_entry = ttk.Entry(tab, show='*', width=30, font=FONT_LARGE)
    confirm_password_entry.grid(row=2, column=1, sticky='ew', pady=5)
    focusable_widgets.append(confirm_password_entry)

    def clear_settings_fields(): # Dedicated clear function for settings tab
        new_password_entry.delete(0, tk.END)
        confirm_password_entry.delete(0, tk.END)
        new_fy_entry.delete(0, tk.END) # Clear FY entry as well
        new_password_entry.focus_set()


    def change_password():
        new_pass = new_password_entry.get()
        confirm_pass = confirm_password_entry.get()

        if not new_pass or not confirm_pass:
            messagebox.showwarning("INPUT REQUIRED", "Please enter and confirm the new password.")
            return
        if new_pass != confirm_pass:
            messagebox.showerror("MISMATCHED PASSWORDS", "New password and confirmation do not match.")
            return
        
        save_setting('admin_password', new_pass)
        messagebox.showinfo("PASSWORD CHANGED", "Admin password updated successfully. Use this for next login.")
        clear_settings_fields()

    change_password_button = ttk.Button(tab, text="CHANGE PASSWORD", command=change_password)
    change_password_button.grid(row=3, column=1, sticky='w', pady=10)
    focusable_widgets.append(change_password_button)

    # Splash Screen Logo Management
    ttk.Label(tab, text="SPLASH SCREEN LOGO", style='BoldLarge.TLabel').grid(row=4, column=0, columnspan=2, pady=10, sticky='w', padx=10)
    
    current_logo_path_label = ttk.Label(tab, text=f"CURRENT: {os.path.basename(load_setting('splash_logo_path', SPLASH_LOGO_DEFAULT))}", font=FONT_NORMAL)
    current_logo_path_label.grid(row=5, column=0, columnspan=2, sticky='w', padx=10, pady=5)

    def set_splash_logo():
        path = filedialog.askopenfilename(filetypes=[("Image files", "*.png;*.jpg;*.jpeg")])
        if path:
            save_setting('splash_logo_path', path)
            messagebox.showinfo("LOGO SET", "Splash screen logo updated. Restart app to see changes.")
            current_logo_path_label.configure(text=f"CURRENT: {os.path.basename(path)}")
        else:
            messagebox.showwarning("CANCELLED", "No logo file selected.")

    set_logo_button = ttk.Button(tab, text="SET SPLASH LOGO", command=set_splash_logo)
    set_logo_button.grid(row=6, column=1, sticky='w', pady=10)
    focusable_widgets.append(set_logo_button)
    
    # Financial Year Management
    ttk.Label(tab, text="MANAGE FINANCIAL YEARS", style='BoldLarge.TLabel').grid(row=7, column=0, columnspan=2, pady=10, sticky='w', padx=10)

    ttk.Label(tab, text="ADD NEW FY (YYYY-YY):", style='Large.TLabel').grid(row=8, column=0, sticky='e', padx=10)
    new_fy_entry = ttk.Entry(tab, width=20, font=FONT_LARGE)
    new_fy_entry.grid(row=8, column=1, sticky='ew', pady=5)
    # No capitalization for financial year entry (specific format expected)
    focusable_widgets.append(new_fy_entry)

    def add_new_fy():
        new_fy = new_fy_entry.get().strip()
        if not new_fy:
            messagebox.showwarning("INPUT REQUIRED", "Please enter a financial year (e.g., 2024-25).")
            return
        
        # Validate format YYYY-YY
        if not (len(new_fy) == 7 and new_fy[4] == '-' and new_fy[:4].isdigit() and new_fy[5:].isdigit()):
            messagebox.showwarning("INVALID FORMAT", "Financial year format should be **YYYY-YY** (e.g., 2024-25).")
            return
        
        # Optional: Add more robust validation for year logic (e.g., 2024-25, not 2024-26)
        try:
            start_year = int(new_fy[:4])
            end_year_short = int(new_fy[5:])
            if not (end_year_short == (start_year + 1) % 100):
                 messagebox.showwarning("INVALID YEAR LOGIC", "Financial year end part should be the last two digits of (start_year + 1). E.g., 2024-25.")
                 return
        except ValueError:
            messagebox.showwarning("INVALID YEAR", "Years in financial year must be valid numbers.")
            return

        if add_financial_year(new_fy): # This calls the dummy/real function
            messagebox.showinfo("FY ADDED", f"Financial year `'{new_fy}'` added successfully. It will appear in login/status update dropdowns.")
            new_fy_entry.delete(0, tk.END)
        else:
            messagebox.showwarning("ALREADY EXISTS", f"Financial year `'{new_fy}'` already exists.")

    add_fy_button = ttk.Button(tab, text="ADD FINANCIAL YEAR", command=add_new_fy)
    add_fy_button.grid(row=9, column=1, sticky='w', pady=10)
    focusable_widgets.append(add_fy_button)

    # Standard export/backup/restore buttons (from previous version)
    ttk.Label(tab, text="DATABASE OPERATIONS", style='BoldLarge.TLabel').grid(row=10, column=0, columnspan=2, pady=10, sticky='w', padx=10)

    def export_to_excel():
        try:
            conn = connect_db()
            if conn is None: # Handle database connection error
                return
            df = pd.read_sql_query("SELECT * FROM orders", conn)
            conn.close()
            
            if df.empty:
                messagebox.showwarning("NO DATA", "No orders found to export.")
                return

            export_path = filedialog.asksaveasfilename(defaultextension=".xlsx", 
                                                        filetypes=[("Excel Files", "*.xlsx")],
                                                        title="Save Orders to Excel")
            if export_path:
                df.to_excel(export_path, index=False)
                messagebox.showinfo("EXPORTED", f"Data exported to:\n`{export_path}`")
            else:
                messagebox.showwarning("CANCELLED", "Excel export cancelled.")
        except Exception as e:
            messagebox.showerror("ERROR", f"An error occurred during Excel export: {e}")

    def backup_database():
        try:
            if not os.path.exists(BACKUP_FOLDER):
                os.makedirs(BACKUP_FOLDER)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = os.path.join(BACKUP_FOLDER, f"orders_backup_{timestamp}.db")
            
            # Ensure the database connection is closed before copying
            # You might need to add logic to close all open connections if your app keeps them open
            
            shutil.copyfile(DB_PATH, backup_file)
            messagebox.showinfo("BACKUP COMPLETE", f"Database backup saved to:\n`{backup_file}`")
        except Exception as e:
            messagebox.showerror("BACKUP ERROR", f"An error occurred during backup: {e}")

    def restore_database():
        if not messagebox.askyesno("CONFIRM RESTORE", 
                                   "Restoring the database will overwrite your current data. Are you sure you want to proceed?"):
            return
        
        path = filedialog.askopenfilename(filetypes=[("Database Files", "*.db")],
                                           title="Select Database Backup File")
        if path:
            try:
                # Ensure the application's main connection to DB_PATH is closed
                # before attempting to overwrite it. This might require a global conn object
                # or a mechanism to close connections from other parts of the app.
                
                shutil.copyfile(path, DB_PATH)
                messagebox.showinfo("RESTORED", "Database restored successfully. Please restart the application to see the changes.")
            except Exception as e:
                messagebox.showerror("RESTORE ERROR", f"An error occurred during restore: {e}")
        else:
            messagebox.showwarning("CANCELLED", "Database restore cancelled.")

    export_button = ttk.Button(tab, text="EXPORT ORDERS TO EXCEL", command=export_to_excel)
    export_button.grid(row=11, column=0, columnspan=2, pady=5, sticky='ew', padx=10)
    focusable_widgets.append(export_button)

    backup_button = ttk.Button(tab, text="BACKUP DATABASE", command=backup_database)
    backup_button.grid(row=12, column=0, columnspan=2, pady=5, sticky='ew', padx=10)
    focusable_widgets.append(backup_button)

    restore_button = ttk.Button(tab, text="RESTORE DATABASE", command=restore_database)
    restore_button.grid(row=13, column=0, columnspan=2, pady=5, sticky='ew', padx=10)
    focusable_widgets.append(restore_button)

    reset_settings_button = ttk.Button(tab, text="RESET ENTRY", command=clear_settings_fields)
    reset_settings_button.grid(row=14, column=0, columnspan=2, pady=10, sticky='ew', padx=10)
    focusable_widgets.append(reset_settings_button)

    bind_tab_traversal(tab, focusable_widgets)


# --- Main Application Logic ---
class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.withdraw() # Hide the main window initially
        apply_dark_theme(self)
        init_db() # Initialize the database at startup
        
        self.bind("<<SplashScreenClosed>>", self.show_login) # Bind custom event
        self.splash = SplashScreen(self, duration_ms=2000)
        self.current_financial_year = "" # Store the selected FY after login

    def show_login(self, event=None):
        LoginScreen(self, self.start_main_app)

    def start_main_app(self, financial_year):
        self.current_financial_year = financial_year
        main_app_window(self, self.current_financial_year)


if __name__ == "__main__":
    app = MainApp()
    app.mainloop()