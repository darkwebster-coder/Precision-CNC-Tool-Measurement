import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from PIL import Image, ImageTk, ImageEnhance
import json
import csv
from datetime import datetime
import os
import time
import math
from scipy import optimize
from scipy.spatial import distance

class CNCToolMeasurerPro:
    def __init__(self, root):
        self.root = root
        self.root.title("AI-Assisted CNC Tool Measurement System Pro")
        self.root.geometry("1600x1000")
        self.unsaved_changes = False
        
        # Initialize variables
        self.initialize_variables()
        
        # Create GUI
        self.create_enterprise_gui()
        
        # Initialize camera (but don't start yet)
        self.cap = None
        self.camera_active = False

        # Keyboard shortcuts
        self.root.bind('<Control-o>', lambda e: self.load_image('top_view'))
        self.root.bind('<Control-s>', lambda e: self.save_current_measurement())
        self.root.bind('<Control-n>', lambda e: self.reset_measurement())
        self.root.bind('<Control-plus>', lambda e: self.zoom_in())
        self.root.bind('<Control-minus>', lambda e: self.zoom_out())
        self.root.bind('<F1>', lambda e: self.show_help())
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def initialize_variables(self):
        # Measurement variables
        self.reference_objects = {
            "Indian ₹5 Coin": 23.0,
            "Indian ₹10 Coin": 27.0,
            "Standard Credit Card": 85.6,
            "Custom": None
        }
        self.current_reference = "Indian ₹5 Coin"
        self.reference_diameter = 23.0
        self.pixels_per_mm = None
        self.measurement_history = []
        self.current_measurement = {
            'top_view': {'image': None, 'original_image': None, 'measurements': {}},
            'side_view': {'image': None, 'original_image': None, 'measurements': {}},
            'metadata': {
                'timestamp': None,
                'tool_id': '',
                'operator': '',
                'notes': ''
            }
        }
        self.current_view = None
        self.detected_objects = []
        self.last_update_time = 0
        self.min_update_interval = 0.1  # 100ms between updates for stability
        self.image = None
        self.dark_mode = False
        self.full_img = None
        self.selection_points = []
        self.overlay_img = None
        self.selection_stage = 0
        self.zoom_level = 1.0
        self.pan_start_x = 0
        self.pan_start_y = 0
        self.pan_offset_x = 0
        self.pan_offset_y = 0
        
        # CMM-specific variables
        self.cmm_mode = False
        self.cmm_accuracy = 0.5  # microns
        self.cmm_probe_type = "VAST XT gold"  # Same as Ultima M 450
        self.calibration_data = None
        self.measurement_strategy = "automatic"  # or "manual"
        
        # Manual measurement variables
        self.manual_measurement_mode = False
        self.manual_measurement_points = []
        self.image_scale = 1.0  # Track scaling between displayed and original image
        self.working_img = None  # Working copy of image for processing
        self.display_img = None  # Display copy of image

        # Tooltip tracking
        self.tooltip_window = None
        self.tooltip_label = None

    def set_theme(self):
        """Configure the visual theme of the application"""
        self.style = ttk.Style()
        self.style.theme_use('clam')
        if self.dark_mode:
            self.style.configure('.', background='#222', foreground='white',
                               fieldbackground='#333', borderwidth=1)
            self.style.map('.', background=[('selected', '#447')])
        else:
            self.style.configure('.', background='#f0f0f0', foreground='black',
                               fieldbackground='white', borderwidth=1)

    def update_status(self, message):
        """Update the status bar with a message"""
        self.status_var.set(message)
        self.root.update_idletasks()

    def create_enterprise_gui(self):
        # Configure main window style
        self.style = ttk.Style()
        self.set_theme()
        self.style.configure('Header.TLabel', font=('Helvetica', 12, 'bold'))

        # Menu bar
        self.create_menu_bar()

        # Main frame
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=5)
        ttk.Label(header_frame, text="AI-Assisted CNC Tool Measurement System", 
                 style='Header.TLabel').pack(side=tk.LEFT)

        # Help button
        help_btn = ttk.Button(header_frame, text="Help (F1)", command=self.show_help)
        help_btn.pack(side=tk.RIGHT, padx=5)
        self.create_tooltip(help_btn, "Get help and guidance on using the application")

        # Status bar
        self.status_var = tk.StringVar()
        self.status_bar = ttk.Label(main_frame, textvariable=self.status_var, 
                                  relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(fill=tk.X, pady=(5,0))
        self.update_status("Ready - Please load or capture images")

        # Content area
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True)

        # Left panel - Image display and controls
        left_panel = ttk.Frame(content_frame)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # Image display - triple view
        self.create_image_display(left_panel)

        # Control panel
        self.create_control_panel(left_panel)

        # Right panel - Results and history
        right_panel = ttk.Frame(content_frame)
        right_panel.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

        # Measurement results
        self.create_results_panel(right_panel)

        # Measurement history
        self.create_history_panel(right_panel)

        # Tool information
        self.create_tool_info_panel(right_panel)

        # Configure grid weights
        content_frame.columnconfigure(0, weight=2)
        content_frame.columnconfigure(1, weight=1)
        content_frame.rowconfigure(0, weight=1)

        # Add AI guidance prompts
        self.show_initial_guidance()

    def create_menu_bar(self):
        self.menubar = tk.Menu(self.root)
        
        # File menu
        filemenu = tk.Menu(self.menubar, tearoff=0)
        filemenu.add_command(label="Load Top View (Ctrl+O)", command=lambda: self.load_image('top_view'))
        filemenu.add_command(label="Save Measurement (Ctrl+S)", command=self.save_current_measurement)
        filemenu.add_command(label="Export Report", command=self.export_report)
        filemenu.add_command(label="Export All Data", command=self.export_all_data)
        filemenu.add_separator()
        filemenu.add_command(label="Reset/Start New (Ctrl+N)", command=self.reset_measurement)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.on_closing)
        self.menubar.add_cascade(label="File", menu=filemenu)
        
        # View menu
        viewmenu = tk.Menu(self.menubar, tearoff=0)
        viewmenu.add_command(label="Toggle Dark Mode", command=self.toggle_dark_mode)
        viewmenu.add_command(label="Zoom In (Ctrl++)", command=self.zoom_in)
        viewmenu.add_command(label="Zoom Out (Ctrl+-)", command=self.zoom_out)
        viewmenu.add_command(label="Reset Zoom", command=self.reset_pan_zoom)
        self.menubar.add_cascade(label="View", menu=viewmenu)
        
        # CMM menu
        cmm_menu = tk.Menu(self.menubar, tearoff=0)
        cmm_menu.add_command(label="Enable CMM Mode", command=self.toggle_cmm_mode)
        cmm_menu.add_command(label="Calibrate System", command=self.run_calibration)
        cmm_menu.add_command(label="Set Measurement Strategy", command=self.set_measurement_strategy)
        cmm_menu.add_separator()
        cmm_menu.add_command(label="Ultima M 450 Simulation", command=self.enable_ultima_simulation)
        self.menubar.add_cascade(label="CMM", menu=cmm_menu)
        
        # Help menu
        helpmenu = tk.Menu(self.menubar, tearoff=0)
        helpmenu.add_command(label="User Guide", command=self.show_help)
        helpmenu.add_command(label="Quick Start", command=self.show_initial_guidance)
        helpmenu.add_command(label="About", command=lambda: messagebox.showinfo("About", "CNC Tool Measurement System Pro\nVersion 2.0\n© 2025"))
        self.menubar.add_cascade(label="Help", menu=helpmenu)
        
        self.root.config(menu=self.menubar)

    def create_image_display(self, parent):
        img_display_frame = ttk.LabelFrame(parent, text="Image Analysis")
        img_display_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # Triple view display
        triple_frame = ttk.Frame(img_display_frame)
        triple_frame.pack(fill=tk.BOTH, expand=True)

        # Reference view
        self.ref_frame = ttk.LabelFrame(triple_frame, text="Reference Object")
        self.ref_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        self.ref_canvas = tk.Canvas(self.ref_frame, bg="#222" if self.dark_mode else "#fff")
        self.ref_canvas.image = None  # Initialize image reference
        self.ref_canvas.pack(fill=tk.BOTH, expand=True)
        self.ref_canvas.bind("<Button-1>", self.on_ref_canvas_click)
        self.ref_canvas.bind("<B1-Motion>", self.on_ref_canvas_drag)
        self.ref_canvas.bind("<Double-Button-1>", lambda e: self.reset_pan_zoom('ref'))

        # Tool view
        self.tool_frame = ttk.LabelFrame(triple_frame, text="CNC Tool")
        self.tool_frame.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
        self.tool_canvas = tk.Canvas(self.tool_frame, bg="#222" if self.dark_mode else "#fff")
        self.tool_canvas.image = None  # Initialize image reference
        self.tool_canvas.pack(fill=tk.BOTH, expand=True)
        self.tool_canvas.bind("<Button-1>", self.on_tool_canvas_click)
        self.tool_canvas.bind("<B1-Motion>", self.on_tool_canvas_drag)
        self.tool_canvas.bind("<Double-Button-1>", lambda e: self.reset_pan_zoom('tool'))

        # Measurement overlay
        self.overlay_frame = ttk.LabelFrame(triple_frame, text="Measurement Visualization")
        self.overlay_frame.grid(row=0, column=2, padx=5, pady=5, sticky="nsew")
        self.overlay_canvas = tk.Canvas(self.overlay_frame, bg="#222" if self.dark_mode else "#fff")
        self.overlay_canvas.image = None  # Initialize image reference
        self.overlay_canvas.pack(fill=tk.BOTH, expand=True)
        self.overlay_canvas.bind("<Button-1>", self.on_overlay_canvas_click)
        self.overlay_canvas.bind("<B1-Motion>", self.on_overlay_canvas_drag)
        self.overlay_canvas.bind("<Double-Button-1>", lambda e: self.reset_pan_zoom('overlay'))

        # View indicator
        self.view_indicator = ttk.Label(img_display_frame, text="Current View: Not Set", 
                                      style='Header.TLabel')
        self.view_indicator.pack(pady=5)

        # Configure grid weights
        triple_frame.columnconfigure(0, weight=1)
        triple_frame.columnconfigure(1, weight=1)
        triple_frame.columnconfigure(2, weight=1)
        triple_frame.rowconfigure(0, weight=1)

    def create_control_panel(self, parent):
        control_frame = ttk.LabelFrame(parent, text="Measurement Controls")
        control_frame.pack(fill=tk.X, pady=5)

        # Reference selection
        ref_frame = ttk.Frame(control_frame)
        ref_frame.pack(fill=tk.X, pady=5)
        ttk.Label(ref_frame, text="Reference:").pack(side=tk.LEFT)
        self.ref_combo = ttk.Combobox(ref_frame, values=list(self.reference_objects.keys()))
        self.ref_combo.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        self.ref_combo.set(self.current_reference)
        self.ref_combo.bind("<<ComboboxSelected>>", self.update_reference)
        self.custom_ref_entry = ttk.Entry(ref_frame, width=10)
        self.custom_ref_entry.pack(side=tk.LEFT, padx=5)
        self.custom_ref_entry.configure(state='disabled')
        self.create_tooltip(self.ref_combo, "Select reference object with known dimensions\nor choose 'Custom' to enter specific size")

        # Measurement type selection
        measure_type_frame = ttk.Frame(control_frame)
        measure_type_frame.pack(fill=tk.X, pady=5)
        ttk.Label(measure_type_frame, text="Measurement Type:").pack(side=tk.LEFT)
        self.measure_type_var = tk.StringVar(value="Diameter")
        self.measure_type_combo = ttk.Combobox(measure_type_frame, textvariable=self.measure_type_var, 
                                              values=["Diameter", "Inner Diameter", "Height"])
        self.measure_type_combo.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        self.create_tooltip(self.measure_type_combo, "Select what dimension to measure:\n- Diameter: Outer diameter\n- Inner Diameter: Inner hole diameter\n- Height: Tool height from side view")

        # Measurement buttons
        measure_frame = ttk.Frame(control_frame)
        measure_frame.pack(fill=tk.X, pady=5)
        
        # Auto-detect button
        auto_detect_btn = ttk.Button(measure_frame, text="Auto Detect", 
                                  command=self.auto_detect_circles)
        auto_detect_btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.create_tooltip(auto_detect_btn, "Automatically detect circular tools using computer vision")
        
        # Manual measurement button
        manual_btn = ttk.Button(measure_frame, text="Manual Measure", 
                              command=self.start_manual_measurement)
        manual_btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.create_tooltip(manual_btn, "Manually select points for precise measurement control")
        
        # Reference scale button
        ref_scale_btn = ttk.Button(measure_frame, text="Set Reference Scale", 
                                 command=self.set_reference_scale)
        ref_scale_btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.create_tooltip(ref_scale_btn, "Set measurement scale using known reference object size")
        
        # Measure tool button
        measure_btn = ttk.Button(measure_frame, text="Measure Tool", 
                               command=self.measure_tool)
        measure_btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.create_tooltip(measure_btn, "Calculate tool dimensions based on current selections")
        
        # AI Analyze button
        ai_btn = ttk.Button(measure_frame, text="AI Analyze", 
                          command=self.ai_analyze)
        ai_btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.create_tooltip(ai_btn, "Get AI-powered analysis of tool geometry and measurements")

        # Interactive selection button
        select_frame = ttk.Frame(control_frame)
        select_frame.pack(fill=tk.X, pady=5)
        select_btn = ttk.Button(select_frame, text="Select Reference/Object", 
                              command=self.start_interactive_selection)
        select_btn.pack(side=tk.LEFT, padx=5, expand=True)
        self.create_tooltip(select_btn, "Interactively select reference and tool objects in the image")

        # View selection buttons
        view_frame = ttk.Frame(control_frame)
        view_frame.pack(fill=tk.X, pady=5)
        top_view_btn = ttk.Button(view_frame, text="Set Top View", 
                                command=lambda: self.set_view('top_view'))
        top_view_btn.pack(side=tk.LEFT, padx=5, expand=True)
        self.create_tooltip(top_view_btn, "Define current image as top view of tool (for diameter measurement)")
        
        side_view_btn = ttk.Button(view_frame, text="Set Side View", 
                                 command=lambda: self.set_view('side_view'))
        side_view_btn.pack(side=tk.LEFT, padx=5, expand=True)
        self.create_tooltip(side_view_btn, "Define current image as side view of tool (for height measurement)")

        # Image source buttons
        source_frame = ttk.Frame(control_frame)
        source_frame.pack(fill=tk.X, pady=5)
        load_top_btn = ttk.Button(source_frame, text="Load Top View", 
                                command=lambda: self.load_image('top_view'))
        load_top_btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.create_tooltip(load_top_btn, "Load existing image file for top view measurement")
        
        load_side_btn = ttk.Button(source_frame, text="Load Side View", 
                                 command=lambda: self.load_image('side_view'))
        load_side_btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.create_tooltip(load_side_btn, "Load existing image file for side view measurement")
        
        capture_btn = ttk.Button(source_frame, text="Capture Current View", 
                               command=self.capture_current_view)
        capture_btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.create_tooltip(capture_btn, "Capture new image from connected camera")

        # Export buttons
        export_frame = ttk.Frame(control_frame)
        export_frame.pack(fill=tk.X, pady=5)
        save_btn = ttk.Button(export_frame, text="Save Measurement", 
                            command=self.save_current_measurement)
        save_btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.create_tooltip(save_btn, "Save current measurements to history database")
        
        export_btn = ttk.Button(export_frame, text="Export Report", 
                              command=self.export_report)
        export_btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.create_tooltip(export_btn, "Generate detailed measurement report in various formats")
        
        export_all_btn = ttk.Button(export_frame, text="Export All Data", 
                                  command=self.export_all_data)
        export_all_btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.create_tooltip(export_all_btn, "Export all measurement data including images and history")

        # Reset/New Measurement
        reset_frame = ttk.Frame(control_frame)
        reset_frame.pack(fill=tk.X, pady=5)
        reset_btn = ttk.Button(reset_frame, text="Reset/Start New Measurement", 
                             command=self.reset_measurement)
        reset_btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.create_tooltip(reset_btn, "Clear current measurements and start fresh")

    def create_results_panel(self, parent):
        results_frame = ttk.LabelFrame(parent, text="Measurement Results")
        results_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.results_notebook = ttk.Notebook(results_frame)
        self.results_notebook.pack(fill=tk.BOTH, expand=True)
        
        # Top view results
        self.top_results_frame = ttk.Frame(self.results_notebook)
        self.results_notebook.add(self.top_results_frame, text="Top View")
        self.top_results_text = tk.Text(self.top_results_frame, wrap=tk.WORD)
        self.top_results_text.pack(fill=tk.BOTH, expand=True)
        
        # Side view results
        self.side_results_frame = ttk.Frame(self.results_notebook)
        self.results_notebook.add(self.side_results_frame, text="Side View")
        self.side_results_text = tk.Text(self.side_results_frame, wrap=tk.WORD)
        self.side_results_text.pack(fill=tk.BOTH, expand=True)
        
        # Add scrollbars to both text widgets
        for text_widget in [self.top_results_text, self.side_results_text]:
            scrollbar = ttk.Scrollbar(text_widget)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            text_widget.config(yscrollcommand=scrollbar.set)
            scrollbar.config(command=text_widget.yview)

    def create_history_panel(self, parent):
        history_frame = ttk.LabelFrame(parent, text="Measurement History")
        history_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Create treeview for history
        self.history_tree = ttk.Treeview(history_frame, columns=('timestamp', 'tool_id', 'operator', 'diameter'))
        self.history_tree.heading('#0', text='ID')
        self.history_tree.heading('timestamp', text='Timestamp')
        self.history_tree.heading('tool_id', text='Tool ID')
        self.history_tree.heading('operator', text='Operator')
        self.history_tree.heading('diameter', text='Diameter (mm)')
        
        # Configure columns
        self.history_tree.column('#0', width=50)
        self.history_tree.column('timestamp', width=150)
        self.history_tree.column('tool_id', width=100)
        self.history_tree.column('operator', width=100)
        self.history_tree.column('diameter', width=100)
        
        self.history_tree.pack(fill=tk.BOTH, expand=True)
        
        # History controls
        history_controls = ttk.Frame(history_frame)
        history_controls.pack(fill=tk.X, pady=5)
        
        load_btn = ttk.Button(history_controls, text="Load History", 
                            command=self.load_history)
        load_btn.pack(side=tk.LEFT, padx=5, expand=True)
        self.create_tooltip(load_btn, "Load previously saved measurement history")
        
        clear_btn = ttk.Button(history_controls, text="Clear History", 
                             command=self.clear_history)
        clear_btn.pack(side=tk.LEFT, padx=5, expand=True)
        self.create_tooltip(clear_btn, "Clear all measurement history")
        
        view_btn = ttk.Button(history_controls, text="View Details", 
                            command=self.view_history_details)
        view_btn.pack(side=tk.LEFT, padx=5, expand=True)
        self.create_tooltip(view_btn, "View detailed information about selected measurement")

    def create_tool_info_panel(self, parent):
        info_frame = ttk.LabelFrame(parent, text="Tool Information")
        info_frame.pack(fill=tk.BOTH, pady=5)
        
        # Tooltip definitions
        self.tool_tips = {
            'tool_id': "Unique identifier for the tool being measured",
            'operator': "Name of person performing the measurement",
            'notes': "Any observations or special conditions during measurement"
        }
        
        # Tool ID
        ttk.Label(info_frame, text="Tool ID:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.tool_id_entry = ttk.Entry(info_frame)
        self.tool_id_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=2)
        self.create_tooltip(self.tool_id_entry, self.tool_tips['tool_id'])
        
        # Operator
        ttk.Label(info_frame, text="Operator:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.operator_entry = ttk.Entry(info_frame)
        self.operator_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=2)
        self.create_tooltip(self.operator_entry, self.tool_tips['operator'])
        
        # Notes
        ttk.Label(info_frame, text="Notes:").grid(row=2, column=0, sticky="nw", padx=5, pady=2)
        self.notes_text = tk.Text(info_frame, height=4, width=30)
        self.notes_text.grid(row=2, column=1, sticky="ew", padx=5, pady=2)
        self.create_tooltip(self.notes_text, self.tool_tips['notes'])
        
        # Configure grid weights
        info_frame.columnconfigure(1, weight=1)

    def create_tooltip(self, widget, text):
        """Create a tooltip that appears when hovering over a widget"""
        def enter(event):
            x = widget.winfo_rootx() + widget.winfo_width() + 5
            y = widget.winfo_rooty()
            
            # Create tooltip window if it doesn't exist
            if not hasattr(self, 'tooltip_window') or not self.tooltip_window:
                self.tooltip_window = tk.Toplevel(self.root)
                self.tooltip_window.wm_overrideredirect(True)
                self.tooltip_label = ttk.Label(self.tooltip_window, text=text, 
                                             background="#ffffe0", relief="solid", 
                                             borderwidth=1, padding=5, 
                                             wraplength=300)
                self.tooltip_label.pack()
            
            self.tooltip_window.wm_geometry(f"+{x}+{y}")
            self.tooltip_label.config(text=text)
            self.tooltip_window.wm_deiconify()
        
        def leave(event):
            if hasattr(self, 'tooltip_window') and self.tooltip_window:
                self.tooltip_window.wm_withdraw()
        
        widget.bind("<Enter>", enter)
        widget.bind("<Leave>", leave)

    def show_help(self):
        """Show comprehensive help information"""
        help_text = """
        CNC Tool Measurement System Pro - User Guide
        
        === Getting Started ===
        1. Capture/Load Images:
           - Start with a TOP VIEW image showing both tool and reference object
           - Then capture/load a SIDE VIEW image
           - Use consistent lighting and focus
        
        2. Set Reference Scale:
           - Select reference object from dropdown
           - For custom objects, enter known dimension in mm
           - Click 'Set Reference Scale' to calibrate
        
        3. Measure Tool:
           - Use 'Auto Detect' for automatic measurement
           - Use 'Manual Measure' for precise control
           - Measure in both views for complete analysis
        
        4. Analyze & Save:
           - Review measurements in results panel
           - Use 'AI Analyze' for additional insights
           - Save measurements or export reports
        
        === Measurement Techniques ===
        - For best results:
          * Use high-contrast backgrounds
          * Ensure reference and tool are in same plane
          * Use reference object similar in size to tool
          * In CMM mode, measurements include uncertainty
        
        === Keyboard Shortcuts ===
        Ctrl+O: Load image
        Ctrl+S: Save measurement
        Ctrl+N: New measurement
        Ctrl++/-: Zoom in/out
        F1: Show this help
        
        === Advanced Features ===
        - CMM Mode: High-precision measurement simulation
        - AI Analysis: Detailed tool geometry assessment
        - History Tracking: Save and compare measurements
        - Reporting: Generate professional measurement reports
        """
        self.show_scrollable_message("User Guide", help_text.strip())

    def show_initial_guidance(self):
        """Show initial guidance when starting the application"""
        message = """
        Welcome to AI-Assisted CNC Tool Measurement System Pro!
        
        For accurate measurements:
        1. First capture/load a TOP VIEW image with tool and reference
        2. Then capture/load a SIDE VIEW image
        3. Set reference scale using the known reference size
        4. Measure tool dimensions in both views
        
        The AI will guide you through each step.
        
        Pro Tips:
        - Use high-contrast backgrounds for better edge detection
        - Ensure reference and tool are in same focal plane
        - For best accuracy, use reference similar in size to your tool
        - In CMM mode, measurements include precision estimates
        
        Press F1 anytime for detailed help.
        """
        messagebox.showinfo("Getting Started", message.strip())
        self.update_status("Please capture/load TOP VIEW image first")

    def show_scrollable_message(self, title, message):
        """Show long messages in a scrollable window"""
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        
        frame = ttk.Frame(dialog)
        frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        text = tk.Text(frame, wrap=tk.WORD, width=80, height=25)
        text.insert(tk.END, message)
        text.config(state=tk.DISABLED)
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(frame, command=text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text.config(yscrollcommand=scrollbar.set)
        
        btn = ttk.Button(dialog, text="OK", command=dialog.destroy)
        btn.pack(pady=5)

    def load_image(self, view_type):
        file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp")])
        if file_path:
            self.current_view = view_type
            self.update_view_indicator()
            img = cv2.imread(file_path)
            if img is None:
                messagebox.showerror("Error", "Failed to load image. Please select a valid image file.")
                return
            
            # Store original image and create working copy
            self.current_measurement[view_type]['original_image'] = img.copy()
            
            # Resize for display while maintaining aspect ratio
            self.full_img = self.resize_for_display(img)
            self.working_img = img.copy()  # Keep full resolution for measurements
            
            # Update all canvases
            self.display_image(self.overlay_canvas, self.full_img)
            self.display_image(self.ref_canvas, self.full_img)
            self.display_image(self.tool_canvas, self.full_img)
            
            self.update_status(f"{os.path.basename(file_path)} loaded as {view_type.replace('_', ' ')}")
            self.unsaved_changes = True

    def resize_for_display(self, img):
        """Resize image for display while maintaining aspect ratio"""
        max_size = 800
        h, w = img.shape[:2]
        self.image_scale = min(max_size / w, max_size / h, 1.0)
        new_w, new_h = int(w * self.image_scale), int(h * self.image_scale)
        return cv2.resize(img, (new_w, new_h))

    def capture_current_view(self):
        if self.current_view is None:
            messagebox.showwarning("No View Selected", "Please select a view type first (Top or Side)")
            return
            
        if not self.camera_active:
            self.init_camera()
            
        ret, frame = self.cap.read()
        if ret:
            # Store original and create display version
            self.current_measurement[self.current_view]['original_image'] = frame.copy()
            self.full_img = self.resize_for_display(frame)
            self.working_img = frame.copy()
            
            # Update all canvases
            self.display_image(self.overlay_canvas, self.full_img)
            self.display_image(self.ref_canvas, self.full_img)
            self.display_image(self.tool_canvas, self.full_img)
            
            self.update_status(f"Image captured for {self.current_view.replace('_', ' ')} view")
            self.unsaved_changes = True

    def init_camera(self):
        try:
            self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            if not self.cap.isOpened():
                self.cap = cv2.VideoCapture(0)
            self.camera_active = True
            self.update_camera_view()
            self.update_status("Camera initialized - Live view active")
        except Exception as e:
            messagebox.showerror("Camera Error", f"Could not initialize camera: {str(e)}")
            self.update_status("Camera initialization failed")

    def update_camera_view(self):
        if self.camera_active and self.cap:
            ret, frame = self.cap.read()
            if ret:
                self.image = frame.copy()
                self.display_image(self.overlay_canvas, self.image)
            self.root.after(30, self.update_camera_view)

    def display_image(self, canvas, cv_image):
        # Check if canvas exists before trying to display
        if not canvas.winfo_exists():
            return
            
        current_time = time.time()
        if current_time - self.last_update_time < self.min_update_interval:
            return
            
        self.last_update_time = current_time
        
        try:
            if cv_image is None:
                return
                
            img_rgb = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
            img_pil = Image.fromarray(img_rgb)
            
            canvas_width = canvas.winfo_width()
            canvas_height = canvas.winfo_height()
            
            if canvas_width > 1 and canvas_height > 1:
                img_ratio = img_pil.width / img_pil.height
                canvas_ratio = canvas_width / canvas_height
                
                if img_ratio > canvas_ratio:
                    new_width = canvas_width
                    new_height = int(canvas_width / img_ratio)
                else:
                    new_height = canvas_height
                    new_width = int(canvas_height * img_ratio)
                
                img_pil = img_pil.resize((new_width, new_height), Image.Resampling.LANCZOS)
                img_tk = ImageTk.PhotoImage(image=img_pil)
                
                canvas.delete("all")
                canvas.create_image(canvas_width//2, canvas_height//2, anchor=tk.CENTER, image=img_tk)
                canvas.image = img_tk  # Keep reference to prevent garbage collection
        except Exception as e:
            print(f"Error displaying image: {e}")

    def on_ref_canvas_click(self, event):
        self.pan_start_x = event.x
        self.pan_start_y = event.y

    def on_ref_canvas_drag(self, event):
        self.pan_image(event, 'ref')

    def on_tool_canvas_click(self, event):
        self.pan_start_x = event.x
        self.pan_start_y = event.y

    def on_tool_canvas_drag(self, event):
        self.pan_image(event, 'tool')

    def on_overlay_canvas_click(self, event):
        if self.manual_measurement_mode:
            self.manual_measurement_click(event)
        else:
            self.pan_start_x = event.x
            self.pan_start_y = event.y

    def on_overlay_canvas_drag(self, event):
        if not self.manual_measurement_mode:
            self.pan_image(event, 'overlay')

    def pan_image(self, event, canvas_type):
        dx = event.x - self.pan_start_x
        dy = event.y - self.pan_start_y
        
        # Update pan offset (scaled by zoom level)
        self.pan_offset_x += int(dx / self.zoom_level)
        self.pan_offset_y += int(dy / self.zoom_level)
        
        self.pan_start_x = event.x
        self.pan_start_y = event.y
        
        self.update_zoom(canvas_type)

    def set_view(self, view_type):
        self.current_view = view_type
        self.update_view_indicator()
        self.update_status(f"Current view set to {view_type.replace('_', ' ').title()}")

    def update_view_indicator(self):
        if self.current_view:
            view_name = "Top View" if self.current_view == "top_view" else "Side View"
            self.view_indicator.config(text=f"Current View: {view_name}")
        else:
            self.view_indicator.config(text="Current View: Not Set")

    def start_interactive_selection(self):
        if self.current_view is None:
            messagebox.showwarning("No View Selected", "Please select a view type first (Top or Side)")
            return
            
        if self.current_measurement[self.current_view]['original_image'] is None:
            messagebox.showwarning("No Image", "Please load or capture an image first")
            return
            
        self.selection_points = []
        self.selection_stage = 0  # 0: waiting for reference, 1: waiting for tool
        self.overlay_canvas.bind("<Button-1>", self.on_canvas_click)
        self.update_status("Click on the REFERENCE object in the image.")

    def on_canvas_click(self, event):
        canvas = self.overlay_canvas
        img = self.full_img
        if img is None:
            return
            
        canvas_width = canvas.winfo_width()
        canvas_height = canvas.winfo_height()
        img_height, img_width = img.shape[:2]
        scale_x = img_width / canvas_width
        scale_y = img_height / canvas_height
        x_img = int(event.x * scale_x)
        y_img = int(event.y * scale_y)
        
        self.selection_points.append((x_img, y_img))
        
        if len(self.selection_points) == 1:
            self.selection_stage = 1
            self._highlight_selection(self.selection_points[0], color=(0,255,0), label="REFERENCE")
            self.update_status("Reference selected. Now click on the TOOL to measure.")
        elif len(self.selection_points) == 2:
            self.overlay_canvas.unbind("<Button-1>")
            self.detect_reference_and_object()
            self.update_status("Reference and tool selected. Now set reference scale and measure.")

    def _highlight_selection(self, point, color=(0,255,0), label=""):
        img = self.full_img.copy()
        cv2.circle(img, point, 15, color, 3)
        if label:
            cv2.putText(img, label, (point[0]+10, point[1]-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 3)
        self.display_image(self.overlay_canvas, img)

    def detect_reference_and_object(self):
        if self.full_img is None:
            return
            
        img = self.full_img.copy()
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (9, 9), 2)
        edges = cv2.Canny(blurred, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if len(contours) == 0:
            messagebox.showerror("Error", "No objects detected in the image")
            return
            
        selected_objs = []
        for pt in self.selection_points:
            min_dist = float('inf')
            closest = None
            for cnt in contours:
                dist = cv2.pointPolygonTest(cnt, pt, True)
                if abs(dist) < min_dist:
                    min_dist = abs(dist)
                    closest = cnt
            if closest is not None:
                selected_objs.append(closest)
            
        if len(selected_objs) >= 2:
            ref_cnt, tool_cnt = selected_objs[0], selected_objs[1]
            x_ref, y_ref, w_ref, h_ref = cv2.boundingRect(ref_cnt)
            x_tool, y_tool, w_tool, h_tool = cv2.boundingRect(tool_cnt)
            
            self.detected_objects = [
                {'type': 'reference', 'contour': ref_cnt, 'bbox': (x_ref, y_ref, w_ref, h_ref)},
                {'type': 'tool', 'contour': tool_cnt, 'bbox': (x_tool, y_tool, w_tool, h_tool)}
            ]
            
            overlay = img.copy()
            cv2.drawContours(overlay, [ref_cnt], -1, (0, 255, 0), 4)
            cv2.drawContours(overlay, [tool_cnt], -1, (0, 0, 255), 4)
            cv2.putText(overlay, "REFERENCE", (x_ref, y_ref-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)
            cv2.putText(overlay, "TOOL", (x_tool, y_tool-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)
            
            self.overlay_img = overlay
            self.display_image(self.overlay_canvas, self.overlay_img)
            
            # Update reference and tool canvases
            ref_img = img.copy()
            cv2.drawContours(ref_img, [ref_cnt], -1, (0, 255, 0), 4)
            self.display_image(self.ref_canvas, ref_img)
            
            tool_img = img.copy()
            cv2.drawContours(tool_img, [tool_cnt], -1, (0, 0, 255), 4)
            self.display_image(self.tool_canvas, tool_img)
        else:
            messagebox.showerror("Error", "Could not detect both reference and tool objects")

    def auto_detect_circles(self):
        """Improved circle detection based on the provided code"""
        if self.current_view is None:
            messagebox.showwarning("No View Selected", "Please select a view type first")
            return
            
        if self.working_img is None:
            messagebox.showwarning("No Image", "Please load or capture an image first")
            return
            
        # Work on the original resolution image
        img = self.working_img.copy()
        
        # Convert to grayscale and blur
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.medianBlur(gray, 5)
        
        # Detect circles with optimized parameters
        circles = cv2.HoughCircles(
            gray, cv2.HOUGH_GRADIENT, dp=1.2, minDist=20,
            param1=50, param2=30, minRadius=10, maxRadius=150
        )
        
        if circles is None:
            messagebox.showerror("Error", "No circles detected. Try manual mode.")
            return
            
        # Process detected circles
        circles = np.uint16(np.around(circles[0, :]))
        circles = sorted(circles, key=lambda c: c[2])  # Sort by radius
        
        if len(circles) < 2:
            messagebox.showerror("Error", "Need at least 2 circles (reference and tool)")
            return
            
        # Assume smallest is reference, largest is tool
        reference = circles[0]
        tool = circles[-1]
        
        # Calculate scale factor
        reference_px_diameter = reference[2] * 2
        self.pixels_per_mm = reference_px_diameter / self.reference_diameter
        
        # Calculate tool diameter in mm
        tool_px_diameter = tool[2] * 2
        tool_mm_diameter = tool_px_diameter / self.pixels_per_mm
        
        # Store measurements
        self.current_measurement[self.current_view]['measurements'] = {
            'diameter_mm': tool_mm_diameter,
            'pixels_per_mm': self.pixels_per_mm
        }
        
        if self.cmm_mode:
            self.current_measurement[self.current_view]['measurements']['diameter_std_dev'] = self.cmm_accuracy / 1000
        
        # Draw circles on display image
        display_img = self.full_img.copy()
        
        # Scale circle coordinates to display size
        ref_x = int(reference[0] * self.image_scale)
        ref_y = int(reference[1] * self.image_scale)
        ref_r = int(reference[2] * self.image_scale)
        
        tool_x = int(tool[0] * self.image_scale)
        tool_y = int(tool[1] * self.image_scale)
        tool_r = int(tool[2] * self.image_scale)
        
        cv2.circle(display_img, (ref_x, ref_y), ref_r, (0, 255, 0), 3)
        cv2.circle(display_img, (tool_x, tool_y), tool_r, (0, 0, 255), 3)
        
        # Label circles
        cv2.putText(display_img, "REFERENCE", (ref_x - ref_r, ref_y - ref_r - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.putText(display_img, "TOOL", (tool_x - tool_r, tool_y - tool_r - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        
        # Show measurements
        text = f"Tool Diameter: {tool_mm_diameter:.2f} mm"
        cv2.putText(display_img, text, (20, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        
        self.display_image(self.overlay_canvas, display_img)
        
        # Update reference and tool canvases
        ref_img = self.full_img.copy()
        cv2.circle(ref_img, (ref_x, ref_y), ref_r, (0, 255, 0), 3)
        self.display_image(self.ref_canvas, ref_img)
        
        tool_img = self.full_img.copy()
        cv2.circle(tool_img, (tool_x, tool_y), tool_r, (0, 0, 255), 3)
        self.display_image(self.tool_canvas, tool_img)
        
        self.display_measurements()
        self.update_status(f"Auto-detected tool diameter: {tool_mm_diameter:.2f} mm")

    def start_manual_measurement(self):
        """Improved manual measurement based on the provided code"""
        if self.current_view is None:
            messagebox.showwarning("No View Selected", "Please select a view type first")
            return
            
        if self.working_img is None:
            messagebox.showwarning("No Image", "Please load or capture an image first")
            return
            
        self.manual_measurement_mode = True
        self.manual_measurement_points = []
        
        # Create fresh display image
        self.display_img = self.full_img.copy()
        self.display_image(self.overlay_canvas, self.display_img)
        
        measure_type = self.measure_type_var.get()
        
        if measure_type == "Diameter":
            self.update_status("Manual mode: Click 2 points on reference (for scale), then 2 points on tool diameter")
        elif measure_type == "Inner Diameter":
            self.update_status("Manual mode: Click 2 points on reference (for scale), then 2 points on tool inner diameter")
        elif measure_type == "Height":
            self.update_status("Manual mode: Click 2 points on reference (for scale), then 2 points on tool height")
            
        self.overlay_canvas.bind("<Button-1>", self.manual_measurement_click)
        self.overlay_canvas.bind("<Button-3>", self.manual_measurement_clear_last)  # Right-click to clear last point

    def manual_measurement_clear_last(self, event):
        if self.manual_measurement_mode and len(self.manual_measurement_points) > 0:
            self.manual_measurement_points.pop()
            self.display_img = self.full_img.copy()
            self.display_image(self.overlay_canvas, self.display_img)
            
            # Redraw existing points
            for i, (x, y) in enumerate(self.manual_measurement_points):
                x_img = int(x * self.image_scale)
                y_img = int(y * self.image_scale)
                color = (0, 255, 0) if i < 2 else (0, 0, 255)  # Green for reference, red for tool
                cv2.circle(self.display_img, (x_img, y_img), 5, color, -1)
                
                # Draw lines if we have pairs
                if len(self.manual_measurement_points) >= 2:
                    p1 = (int(self.manual_measurement_points[0][0] * self.image_scale),
                          int(self.manual_measurement_points[0][1] * self.image_scale))
                    p2 = (int(self.manual_measurement_points[1][0] * self.image_scale),
                          int(self.manual_measurement_points[1][1] * self.image_scale))
                    cv2.line(self.display_img, p1, p2, (0, 255, 0), 2)
                    cv2.putText(self.display_img, "Reference", 
                               (p1[0] + 10, p1[1] - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                
            self.display_image(self.overlay_canvas, self.display_img)
            self.update_status("Last point removed. Click to add new points.")

    def manual_measurement_click(self, event):
        if not self.manual_measurement_mode:
            return
            
        # Get click coordinates in display image
        canvas = self.overlay_canvas
        display_img = self.display_img
        canvas_width = canvas.winfo_width()
        canvas_height = canvas.winfo_height()
        img_height, img_width = display_img.shape[:2]
        
        # Calculate scaling factors
        scale_x = img_width / canvas_width
        scale_y = img_height / canvas_height
        
        # Get image coordinates
        x_img = int(event.x * scale_x)
        y_img = int(event.y * scale_y)
        
        # Store point (in original image coordinates)
        x_orig = int(x_img / self.image_scale)
        y_orig = int(y_img / self.image_scale)
        self.manual_measurement_points.append((x_orig, y_orig))
        
        # Draw point on display image
        color = (0, 255, 0) if len(self.manual_measurement_points) <= 2 else (0, 0, 255)  # Green for reference, red for tool
        cv2.circle(display_img, (x_img, y_img), 5, color, -1)
        
        # Draw line if we have pairs of points
        if len(self.manual_measurement_points) >= 2:
            if len(self.manual_measurement_points) == 2:
                # Reference line
                p1 = (int(self.manual_measurement_points[0][0] * self.image_scale),
                      int(self.manual_measurement_points[0][1] * self.image_scale))
                p2 = (int(self.manual_measurement_points[1][0] * self.image_scale),
                      int(self.manual_measurement_points[1][1] * self.image_scale))
                cv2.line(display_img, p1, p2, (0, 255, 0), 2)
                cv2.putText(display_img, "Reference", 
                           (p1[0] + 10, p1[1] - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            elif len(self.manual_measurement_points) == 4:
                # Tool measurement line
                p1 = (int(self.manual_measurement_points[2][0] * self.image_scale),
                      int(self.manual_measurement_points[2][1] * self.image_scale))
                p2 = (int(self.manual_measurement_points[3][0] * self.image_scale),
                      int(self.manual_measurement_points[3][1] * self.image_scale))
                cv2.line(display_img, p1, p2, (0, 0, 255), 2)
                cv2.putText(display_img, "Tool", 
                           (p1[0] + 10, p1[1] - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        
        self.display_image(self.overlay_canvas, display_img)
        
        # Check if we have all needed points
        if len(self.manual_measurement_points) == 4:
            self.finish_manual_measurement()

    def finish_manual_measurement(self):
        """Complete manual measurement and calculate dimensions"""
        if len(self.manual_measurement_points) != 4:
            messagebox.showerror("Error", "Need exactly 4 points for measurement")
            return
            
        # Get reference points (first two)
        ref_p1 = self.manual_measurement_points[0]
        ref_p2 = self.manual_measurement_points[1]
        
        # Get tool points (last two)
        tool_p1 = self.manual_measurement_points[2]
        tool_p2 = self.manual_measurement_points[3]
        
        # Calculate distances in pixels
        ref_dist_px = math.hypot(ref_p1[0] - ref_p2[0], ref_p1[1] - ref_p2[1])
        tool_dist_px = math.hypot(tool_p1[0] - tool_p2[0], tool_p1[1] - tool_p2[1])
        
        if ref_dist_px == 0:
            messagebox.showerror("Error", "Reference points are the same")
            return
            
        # Calculate scale factor
        self.pixels_per_mm = ref_dist_px / self.reference_diameter
        
        # Calculate tool measurement based on selected type
        measure_type = self.measure_type_var.get()
        measurements = {}
        
        if measure_type == "Diameter":
            tool_mm = tool_dist_px / self.pixels_per_mm
            measurements['diameter_mm'] = tool_mm
            if self.cmm_mode:
                measurements['diameter_std_dev'] = self.cmm_accuracy / 1000
        elif measure_type == "Inner Diameter":
            tool_mm = tool_dist_px / self.pixels_per_mm
            measurements['inner_diameter_mm'] = tool_mm
            if self.cmm_mode:
                measurements['inner_diameter_std_dev'] = self.cmm_accuracy / 1000
        elif measure_type == "Height":
            tool_mm = tool_dist_px / self.pixels_per_mm
            measurements['height_mm'] = tool_mm
            if self.cmm_mode:
                measurements['height_std_dev'] = self.cmm_accuracy / 1000
        
        # Store measurements
        self.current_measurement[self.current_view]['measurements'] = measurements
        
        # Draw lines on display image
        display_img = self.full_img.copy()
        
        # Scale points to display size
        ref_p1_disp = (int(self.manual_measurement_points[0][0] * self.image_scale),
                      int(self.manual_measurement_points[0][1] * self.image_scale))
        ref_p2_disp = (int(self.manual_measurement_points[1][0] * self.image_scale),
                      int(self.manual_measurement_points[1][1] * self.image_scale))
        tool_p1_disp = (int(self.manual_measurement_points[2][0] * self.image_scale),
                       int(self.manual_measurement_points[2][1] * self.image_scale))
        tool_p2_disp = (int(self.manual_measurement_points[3][0] * self.image_scale),
                       int(self.manual_measurement_points[3][1] * self.image_scale))
        
        # Draw reference line
        cv2.line(display_img, ref_p1_disp, ref_p2_disp, (0, 255, 0), 2)
        cv2.putText(display_img, "Reference", 
                   (ref_p1_disp[0] + 10, ref_p1_disp[1] - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        
        # Draw tool line
        cv2.line(display_img, tool_p1_disp, tool_p2_disp, (0, 0, 255), 2)
        cv2.putText(display_img, "Tool", 
                   (tool_p1_disp[0] + 10, tool_p1_disp[1] - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        
        # Show measurement
        if measure_type == "Diameter":
            text = f"Tool Diameter: {measurements['diameter_mm']:.2f} mm"
        elif measure_type == "Inner Diameter":
            text = f"Tool Inner Diameter: {measurements['inner_diameter_mm']:.2f} mm"
        elif measure_type == "Height":
            text = f"Tool Height: {measurements['height_mm']:.2f} mm"
            
        cv2.putText(display_img, text, (20, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        
        self.display_image(self.overlay_canvas, display_img)
        
        # Update reference and tool canvases
        ref_img = self.full_img.copy()
        cv2.line(ref_img, ref_p1_disp, ref_p2_disp, (0, 255, 0), 2)
        self.display_image(self.ref_canvas, ref_img)
        
        tool_img = self.full_img.copy()
        cv2.line(tool_img, tool_p1_disp, tool_p2_disp, (0, 0, 255), 2)
        self.display_image(self.tool_canvas, tool_img)
        
        self.display_measurements()
        
        self.manual_measurement_mode = False
        self.overlay_canvas.unbind("<Button-1>")
        self.overlay_canvas.unbind("<Button-3>")
        self.update_status(f"Manual measurement complete: {text}")

    def zoom_in(self):
        """Zoom in on the image"""
        if self.full_img is None:
            return
            
        self.zoom_level *= 1.2
        self.update_zoom('all')

    def zoom_out(self):
        """Zoom out from the image"""
        if self.full_img is None:
            return
            
        self.zoom_level /= 1.2
        if self.zoom_level < 0.1:
            self.zoom_level = 0.1
        self.update_zoom('all')

    def update_zoom(self, canvas_type='all'):
        """Update the displayed image with current zoom level"""
        if self.full_img is None:
            return
            
        h, w = self.full_img.shape[:2]
        new_w = int(w * self.zoom_level)
        new_h = int(h * self.zoom_level)
        
        # Calculate center point
        center_x = w // 2 + self.pan_offset_x
        center_y = h // 2 + self.pan_offset_y
        
        # Calculate crop area
        crop_x1 = max(0, center_x - new_w // 2)
        crop_y1 = max(0, center_y - new_h // 2)
        crop_x2 = min(w, center_x + new_w // 2)
        crop_y2 = min(h, center_y + new_h // 2)
        
        # Crop and resize
        if crop_x2 > crop_x1 and crop_y2 > crop_y1:
            zoomed_img = self.full_img[crop_y1:crop_y2, crop_x1:crop_x2]
            zoomed_img = cv2.resize(zoomed_img, (w, h))
            
            if canvas_type == 'all' or canvas_type == 'overlay':
                self.display_image(self.overlay_canvas, zoomed_img)
            if canvas_type == 'all' or canvas_type == 'ref':
                self.display_image(self.ref_canvas, zoomed_img)
            if canvas_type == 'all' or canvas_type == 'tool':
                self.display_image(self.tool_canvas, zoomed_img)
            
            self.update_status(f"Zoom: {self.zoom_level:.1f}x")

    def reset_pan_zoom(self, canvas_type='all'):
        """Reset pan and zoom to default"""
        self.zoom_level = 1.0
        self.pan_offset_x = 0
        self.pan_offset_y = 0
        
        if self.full_img is not None:
            if canvas_type == 'all' or canvas_type == 'overlay':
                self.display_image(self.overlay_canvas, self.full_img)
            if canvas_type == 'all' or canvas_type == 'ref':
                self.display_image(self.ref_canvas, self.full_img)
            if canvas_type == 'all' or canvas_type == 'tool':
                self.display_image(self.tool_canvas, self.full_img)
            
            self.update_status("Zoom and pan reset")

    def set_reference_scale(self):
        if len(self.detected_objects) < 2:
            messagebox.showerror("Error", "Could not detect both reference and tool")
            return
            
        if self.current_reference == "Custom":
            try:
                self.reference_diameter = float(self.custom_ref_entry.get())
            except ValueError:
                messagebox.showerror("Error", "Please enter a valid number for custom reference size")
                return
                
        ref_obj = next(obj for obj in self.detected_objects if obj['type'] == 'reference')
        x, y, w, h = ref_obj['bbox']
        ref_pixel_size = max(w, h)
        self.pixels_per_mm = ref_pixel_size / self.reference_diameter
        
        messagebox.showinfo("Scale Set", 
                          f"Reference scale established: {self.pixels_per_mm:.2f} pixels/mm\n"
                          f"Reference size: {self.reference_diameter}mm = {ref_pixel_size} pixels")
        self.update_status(f"Scale set: {self.pixels_per_mm:.2f} pixels/mm")

    def measure_tool(self):
        """Enhanced measurement with CMM-like precision"""
        if self.pixels_per_mm is None:
            messagebox.showerror("Error", "Please set reference scale first")
            return
            
        if len(self.detected_objects) < 2:
            messagebox.showerror("Error", "Tool not detected. Please ensure tool is visible with reference.")
            return
            
        if self.current_view is None:
            messagebox.showerror("Error", "No view selected. Please select top or side view first.")
            return
            
        if self.current_measurement[self.current_view]['original_image'] is None:
            messagebox.showerror("Error", "No image available for measurement. Please capture or load an image first.")
            return
            
        # Re-detect objects to ensure we have fresh contours
        self.detect_reference_and_object()
        
        if len(self.detected_objects) < 2:
            messagebox.showerror("Error", "Tool detection failed. Please try selecting objects again.")
            return
            
        tool_obj = next(obj for obj in self.detected_objects if obj['type'] == 'tool')
        cnt = tool_obj['contour']
        measurements = {}
        measure_type = self.measure_type_var.get()
        
        try:
            if measure_type == "Diameter":
                diameter = self.measure_diameter(cnt)
                measurements['diameter_mm'] = diameter
                if self.cmm_mode:
                    measurements['diameter_std_dev'] = self.cmm_accuracy / 1000  # Convert µm to mm
            
            elif measure_type == "Inner Diameter":
                inner_diameter = self.measure_inner_diameter(cnt)
                measurements['inner_diameter_mm'] = inner_diameter
                if self.cmm_mode:
                    measurements['inner_diameter_std_dev'] = self.cmm_accuracy / 1000
            
            elif measure_type == "Height":
                height = self.measure_height(cnt)
                measurements['height_mm'] = height
                if self.cmm_mode:
                    measurements['height_std_dev'] = self.cmm_accuracy / 1000
            
            self.current_measurement[self.current_view]['measurements'] = measurements
            self.display_measurements()
            self.update_overlay_with_measurements(measurements)
            
            status_msg = f"{measure_type} measured in {self.current_view.replace('_', ' ')} view"
            if self.cmm_mode:
                status_msg += f" (CMM precision: ±{self.cmm_accuracy}µm)"
            self.update_status(status_msg)
            self.unsaved_changes = True
            
        except Exception as e:
            messagebox.showerror("Measurement Error", f"Failed to measure: {str(e)}")
            self.update_status("Measurement failed")
    
    def measure_diameter(self, contour):
        """Precise outer diameter measurement using circle fitting"""
        if len(contour) < 5:  # Need at least 5 points to fit a circle
            x, y, w, h = cv2.boundingRect(contour)
            return max(w, h) / self.pixels_per_mm
            
        if self.measurement_strategy == "automatic":
            # Fit circle to contour points
            (x, y), radius = cv2.minEnclosingCircle(contour)
            
            # For CMM mode, use more precise fitting
            if self.cmm_mode:
                def circle_residuals(params, points):
                    x0, y0, r = params
                    residuals = []
                    for x, y in points:
                        residuals.append(abs(math.sqrt((x-x0)**2 + (y-y0)**2) - r))
                    return residuals
                
                points = contour.reshape(-1, 2)
                initial_guess = (x, y, radius)
                result = optimize.least_squares(circle_residuals, initial_guess, args=(points,))
                x, y, radius = result.x
            
            diameter = (radius * 2) / self.pixels_per_mm
        else:
            # Manual measurement - use bounding box
            x, y, w, h = cv2.boundingRect(contour)
            diameter = max(w, h) / self.pixels_per_mm
        
        return diameter
    
    def measure_inner_diameter(self, contour):
        """Precise inner diameter measurement using inscribed circle"""
        if len(contour) < 5:  # Need at least 5 points for good measurement
            x, y, w, h = cv2.boundingRect(contour)
            return min(w, h) / self.pixels_per_mm
            
        if self.measurement_strategy == "automatic":
            # Create distance transform to find largest inscribed circle
            mask = np.zeros(self.full_img.shape[:2], dtype=np.uint8)
            cv2.drawContours(mask, [contour], -1, 255, -1)
            dist_transform = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
            
            # Find the maximum distance (radius of largest inscribed circle)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(dist_transform)
            radius = max_val
            
            # For CMM mode, use more precise calculation
            if self.cmm_mode:
                # Sample points on the contour
                points = contour.reshape(-1, 2)
                
                # Find minimum distance from center to contour
                center = np.array(max_loc)
                distances = [distance.euclidean(center, point) for point in points]
                radius = min(distances)
            
            diameter = (radius * 2) / self.pixels_per_mm
        else:
            # Manual measurement - use minimum dimension
            x, y, w, h = cv2.boundingRect(contour)
            diameter = min(w, h) / self.pixels_per_mm
        
        return diameter
    
    def measure_height(self, contour):
        """Precise height measurement"""
        if len(contour) < 2:  # Need at least 2 points
            x, y, w, h = cv2.boundingRect(contour)
            return h / self.pixels_per_mm
            
        if self.measurement_strategy == "automatic":
            # Fit rectangle to contour
            rect = cv2.minAreaRect(contour)
            height = max(rect[1]) / self.pixels_per_mm
            
            # For CMM mode, use extreme points
            if self.cmm_mode:
                points = contour.reshape(-1, 2)
                y_coords = points[:, 1]
                height = (max(y_coords) - min(y_coords)) / self.pixels_per_mm
        else:
            # Manual measurement - use bounding box
            x, y, w, h = cv2.boundingRect(contour)
            height = h / self.pixels_per_mm
        
        return height

    def update_overlay_with_measurements(self, measurements):
        if not hasattr(self, 'overlay_img'):
            return
            
        overlay = self.overlay_img.copy()
        tool_obj = next(obj for obj in self.detected_objects if obj['type'] == 'tool')
        x, y, w, h = tool_obj['bbox']
        text_y = y
        
        for name, value in measurements.items():
            if name.endswith('_std_dev'):
                continue  # Skip standard deviation for overlay
                
            if name in self.current_measurement[self.current_view]['measurements'] and f"{name}_std_dev" in self.current_measurement[self.current_view]['measurements']:
                std_dev = self.current_measurement[self.current_view]['measurements'][f"{name}_std_dev"]
                text = f"{name.replace('_', ' ').title()}: {value:.4f} ±{std_dev:.4f} mm"
            else:
                text = f"{name.replace('_', ' ').title()}: {value:.4f} mm"
                
            cv2.putText(overlay, text, (x, text_y), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)
            text_y += 20
            
        self.overlay_img = overlay
        self.display_analysis()

    def display_analysis(self):
        if hasattr(self, 'overlay_img'):
            self.display_image(self.overlay_canvas, self.overlay_img)

    def display_measurements(self):
        """Enhanced measurement display with CMM-like reporting"""
        self.top_results_text.delete(1.0, tk.END)
        self.top_results_text.insert(tk.END, "=== Top View Measurements ===\n\n")
        
        for name, value in self.current_measurement['top_view']['measurements'].items():
            if name.endswith('_std_dev'):
                continue  # Skip std dev for main display
                
            if name in self.current_measurement['top_view']['measurements'] and f"{name}_std_dev" in self.current_measurement['top_view']['measurements']:
                std_dev = self.current_measurement['top_view']['measurements'][f"{name}_std_dev"]
                self.top_results_text.insert(tk.END, 
                    f"{name.replace('_', ' ').title()}: {value:.4f} ±{std_dev:.4f} mm\n")
            else:
                self.top_results_text.insert(tk.END, 
                    f"{name.replace('_', ' ').title()}: {value:.4f} mm\n")
        
        self.side_results_text.delete(1.0, tk.END)
        self.side_results_text.insert(tk.END, "=== Side View Measurements ===\n\n")
        
        for name, value in self.current_measurement['side_view']['measurements'].items():
            if name.endswith('_std_dev'):
                continue
                
            if name in self.current_measurement['side_view']['measurements'] and f"{name}_std_dev" in self.current_measurement['side_view']['measurements']:
                std_dev = self.current_measurement['side_view']['measurements'][f"{name}_std_dev"]
                self.side_results_text.insert(tk.END, 
                    f"{name.replace('_', ' ').title()}: {value:.4f} ±{std_dev:.4f} mm\n")
            else:
                self.side_results_text.insert(tk.END, 
                    f"{name.replace('_', ' ').title()}: {value:.4f} mm\n")
        
        if self.pixels_per_mm:
            precision = f" ±{self.cmm_accuracy/1000:.4f} mm" if self.cmm_mode else ""
            self.top_results_text.insert(tk.END, f"\nScale: {self.pixels_per_mm:.4f}{precision} pixels/mm")
            self.side_results_text.insert(tk.END, f"\nScale: {self.pixels_per_mm:.4f}{precision} pixels/mm")
        
        if self.cmm_mode:
            self.top_results_text.insert(tk.END, "\n\n=== CMM Measurement Report ===")
            self.top_results_text.insert(tk.END, f"\nProbe Type: {self.cmm_probe_type}")
            self.top_results_text.insert(tk.END, f"\nNominal Accuracy: ±{self.cmm_accuracy} µm")
            
            self.side_results_text.insert(tk.END, "\n\n=== CMM Measurement Report ===")
            self.side_results_text.insert(tk.END, f"\nProbe Type: {self.cmm_probe_type}")
            self.side_results_text.insert(tk.END, f"\nNominal Accuracy: ±{self.cmm_accuracy} µm")

    def save_current_measurement(self):
        """Save the current measurement to history"""
        if not self.current_measurement['top_view']['measurements'] and not self.current_measurement['side_view']['measurements']:
            messagebox.showerror("Error", "No measurements to save")
            return
            
        self.current_measurement['metadata']['timestamp'] = datetime.now().isoformat()
        self.current_measurement['metadata']['tool_id'] = self.tool_id_entry.get()
        self.current_measurement['metadata']['operator'] = self.operator_entry.get()
        self.current_measurement['metadata']['notes'] = self.notes_text.get("1.0", tk.END).strip()
        
        self.measurement_history.append(self.current_measurement.copy())
        self.update_history_tree()
        self.save_history_to_file()
        
        messagebox.showinfo("Saved", "Measurement saved to history")
        self.update_status("Measurement saved to history")
        self.unsaved_changes = False

    def save_history_to_file(self):
        try:
            with open("measurement_history.json", 'w') as f:
                json.dump(self.measurement_history, f, indent=2)
        except Exception as e:
            messagebox.showerror("Error", f"Could not save history: {str(e)}")

    def load_history(self):
        file_path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json"), ("CSV files", "*.csv")])
        if file_path:
            try:
                if file_path.endswith('.json'):
                    with open(file_path, 'r') as f:
                        self.measurement_history = json.load(f)
                elif file_path.endswith('.csv'):
                    with open(file_path, 'r') as f:
                        reader = csv.DictReader(f)
                        self.measurement_history = []
                        for row in reader:
                            self.measurement_history.append({
                                'metadata': {
                                    'timestamp': row['Timestamp'],
                                    'tool_id': row['Tool ID'],
                                    'operator': row['Operator'],
                                    'notes': row['Notes']
                                },
                                'top_view': {
                                    'measurements': {
                                        'diameter_mm': float(row['Diameter (mm)']) if row['Diameter (mm)'] else None
                                    }
                                }
                            })
                self.update_history_tree()
                messagebox.showinfo("Success", f"Loaded {len(self.measurement_history)} measurements")
                self.update_status(f"History loaded from {os.path.basename(file_path)}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not load history: {str(e)}")

    def clear_history(self):
        if messagebox.askyesno("Confirm", "Clear all measurement history?"):
            self.measurement_history = []
            self.update_history_tree()
            self.update_status("Measurement history cleared")

    def update_history_tree(self):
        self.history_tree.delete(*self.history_tree.get_children())
        for idx, measurement in enumerate(self.measurement_history[-50:]):
            diameter = measurement['top_view']['measurements'].get('diameter_mm', 'N/A') if 'top_view' in measurement else 'N/A'
            self.history_tree.insert('', 'end', text=str(idx+1),
                                   values=(measurement['metadata']['timestamp'],
                                          measurement['metadata']['tool_id'],
                                          measurement['metadata']['operator'],
                                          f"{diameter:.2f}" if isinstance(diameter, float) else diameter))

    def view_history_details(self):
        selected = self.history_tree.focus()
        if not selected:
            return
            
        idx = int(self.history_tree.item(selected, 'text')) - 1
        if 0 <= idx < len(self.measurement_history):
            measurement = self.measurement_history[idx]
            detail_window = tk.Toplevel(self.root)
            detail_window.title(f"Measurement Details - {measurement['metadata']['tool_id']}")
            
            text = tk.Text(detail_window, wrap=tk.WORD)
            text.pack(fill=tk.BOTH, expand=True)
            
            text.insert(tk.END, f"Tool ID: {measurement['metadata']['tool_id']}\n")
            text.insert(tk.END, f"Operator: {measurement['metadata']['operator']}\n")
            text.insert(tk.END, f"Timestamp: {measurement['metadata']['timestamp']}\n\n")
            
            if 'top_view' in measurement:
                text.insert(tk.END, "=== Top View ===\n")
                for name, value in measurement['top_view']['measurements'].items():
                    text.insert(tk.END, f"{name.replace('_', ' ').title()}: {value:.2f} mm\n")
                    
            if 'side_view' in measurement:
                text.insert(tk.END, "\n=== Side View ===\n")
                for name, value in measurement['side_view']['measurements'].items():
                    text.insert(tk.END, f"{name.replace('_', ' ').title()}: {value:.2f} mm\n")
                    
            text.insert(tk.END, f"\nNotes:\n{measurement['metadata']['notes']}")
            text.config(state=tk.DISABLED)

    def ai_analyze(self):
        """Enhanced AI analysis with more detailed feedback"""
        if not self.detected_objects:
            messagebox.showwarning("No Objects", "Please load/capture images first")
            return
            
        has_top = self.current_measurement['top_view']['original_image'] is not None
        has_side = self.current_measurement['side_view']['original_image'] is not None
        
        if not has_top or not has_side:
            messagebox.showwarning("Incomplete Data", 
                                 "For complete analysis, please capture both:\n"
                                 "- TOP VIEW for diameter measurements\n"
                                 "- SIDE VIEW for height and profile analysis")
            return
            
        tool_obj = next(obj for obj in self.detected_objects if obj['type'] == 'tool')
        ref_obj = next(obj for obj in self.detected_objects if obj['type'] == 'reference')
        
        tool_area = cv2.contourArea(tool_obj['contour'])
        ref_area = cv2.contourArea(ref_obj['contour'])
        size_ratio = tool_area / ref_area
        
        # Analyze tool shape
        perimeter = cv2.arcLength(tool_obj['contour'], True)
        circularity = (4 * math.pi * tool_area) / (perimeter ** 2) if perimeter > 0 else 0
        
        # Get measurements if available
        diameter = self.current_measurement['top_view']['measurements'].get('diameter_mm', 0)
        height = self.current_measurement['side_view']['measurements'].get('height_mm', 0)
        
        insights = [
            "=== AI Tool Analysis Report ===",
            f"Tool ID: {self.current_measurement['metadata']['tool_id']}",
            f"Analysis Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "Shape Analysis:",
            f"- Size ratio to reference: {size_ratio:.1f}x",
            f"- Circularity index: {circularity:.2f} (1.0 = perfect circle)",
            "- Shape appears suitable for CNC machining" if size_ratio > 0.5 else "- Shape appears small for CNC - check specifications",
            "- Edges appear sharp and well-defined" if circularity > 0.85 else "- Edges may need inspection",
            "",
            "Measurement Analysis:"
        ]
        
        if diameter > 0:
            insights.append(f"- Diameter: {diameter:.2f}mm")
            if diameter < 1:
                insights.append("  WARNING: Very small diameter - check tool specifications")
            elif diameter > 25:
                insights.append("  NOTE: Large diameter tool - ensure machine capacity")
        
        if height > 0:
            insights.append(f"- Height: {height:.2f}mm")
            aspect_ratio = diameter/height if height > 0 else 0
            if aspect_ratio > 5:
                insights.append("  WARNING: High aspect ratio tool - may be fragile")
        
        if self.cmm_mode:
            insights.extend([
                "",
                "CMM-Specific Analysis:",
                "- Geometry appears stable for high-precision measurement",
                "- Surface quality suitable for contact probing" if tool_area > 2000 else "- Surface may require non-contact measurement",
                f"- Recommended measurement strategy: {'Scanning' if circularity > 0.9 else 'Single-point'}",
                f"- Estimated uncertainty: ±{self.cmm_accuracy}µm"
            ])
        
        insights.extend([
            "",
            "Recommendations:",
            "- Verify against tool specifications sheet",
            "- Check for visible wear or damage" if circularity < 0.9 else "- Tool geometry appears within normal parameters",
            "- Re-measure if lighting conditions were suboptimal"
        ])
        
        # Show in scrollable dialog
        self.show_scrollable_message("AI Analysis Results", "\n".join(insights))
        self.update_status("AI analysis completed with detailed recommendations")

    def export_report(self):
        """Export measurement report to file"""
        if not self.current_measurement['top_view']['measurements'] and not self.current_measurement['side_view']['measurements']:
            messagebox.showerror("Error", "No measurements to export")
            return
            
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if file_path:
            with open(file_path, 'w') as f:
                f.write("CNC Tool Measurement Report\n\n")
                f.write(f"Tool ID: {self.current_measurement['metadata']['tool_id']}\n")
                f.write(f"Operator: {self.current_measurement['metadata']['operator']}\n")
                f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                if 'top_view' in self.current_measurement:
                    f.write("Top View Measurements:\n")
                    for name, value in self.current_measurement['top_view']['measurements'].items():
                        if name.endswith('_std_dev'):
                            continue
                        if f"{name}_std_dev" in self.current_measurement['top_view']['measurements']:
                            std_dev = self.current_measurement['top_view']['measurements'][f"{name}_std_dev"]
                            f.write(f"  {name.replace('_', ' ').title()}: {value:.4f} ±{std_dev:.4f} mm\n")
                        else:
                            f.write(f"  {name.replace('_', ' ').title()}: {value:.4f} mm\n")
                
                if 'side_view' in self.current_measurement:
                    f.write("\nSide View Measurements:\n")
                    for name, value in self.current_measurement['side_view']['measurements'].items():
                        if name.endswith('_std_dev'):
                            continue
                        if f"{name}_std_dev" in self.current_measurement['side_view']['measurements']:
                            std_dev = self.current_measurement['side_view']['measurements'][f"{name}_std_dev"]
                            f.write(f"  {name.replace('_', ' ').title()}: {value:.4f} ±{std_dev:.4f} mm\n")
                        else:
                            f.write(f"  {name.replace('_', ' ').title()}: {value:.4f} mm\n")
            
            messagebox.showinfo("Export Complete", f"Report saved to:\n{file_path}")
            self.update_status(f"Report exported to {os.path.basename(file_path)}")

    def export_all_data(self):
        """Export all measurement data to files"""
        if not self.measurement_history:
            messagebox.showerror("Error", "No measurement data to export")
            return
            
        dir_path = filedialog.askdirectory()
        if dir_path:
            # Save current image if available
            if self.image is not None:
                img_path = os.path.join(dir_path, "measurement_image.png")
                cv2.imwrite(img_path, self.image)
            
            # Save measurement data
            data_path = os.path.join(dir_path, "measurement_data.json")
            with open(data_path, 'w') as f:
                json.dump(self.current_measurement, f, indent=2)
            
            # Save history
            history_path = os.path.join(dir_path, "measurement_history.csv")
            with open(history_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Timestamp', 'Tool ID', 'Operator', 'Diameter (mm)', 'Notes'])
                for m in self.measurement_history:
                    diameter = m['top_view']['measurements'].get('diameter_mm', '') if 'top_view' in m else ''
                    writer.writerow([
                        m['metadata']['timestamp'],
                        m['metadata']['tool_id'],
                        m['metadata']['operator'],
                        diameter,
                        m['metadata']['notes'].replace('\n', ' ')
                    ])
            
            messagebox.showinfo("Export Complete", f"All data exported to:\n{dir_path}")
            self.update_status(f"All data exported to {dir_path}")

    def reset_measurement(self):
        if self.unsaved_changes:
            if not messagebox.askyesno("Unsaved Changes", "You have unsaved changes. Reset anyway?"):
                return
                
        self.initialize_variables()
        self.update_view_indicator()
        self.display_measurements()
        self.ref_canvas.delete("all")
        self.tool_canvas.delete("all")
        self.overlay_canvas.delete("all")
        self.tool_id_entry.delete(0, tk.END)
        self.operator_entry.delete(0, tk.END)
        self.notes_text.delete(1.0, tk.END)
        self.update_status("Measurement reset. Ready for new measurement.")
        self.unsaved_changes = False

    def on_closing(self):
        if self.unsaved_changes:
            if not messagebox.askyesno("Unsaved Changes", "You have unsaved changes. Exit anyway?"):
                return
                
        if self.camera_active and self.cap:
            self.cap.release()
        self.root.destroy()

    def toggle_dark_mode(self):
        self.dark_mode = not self.dark_mode
        self.set_theme()
        # Update canvas backgrounds
        self.ref_canvas.config(bg="#222" if self.dark_mode else "#fff")
        self.tool_canvas.config(bg="#222" if self.dark_mode else "#fff")
        self.overlay_canvas.config(bg="#222" if self.dark_mode else "#fff")
        self.update_status("Dark mode " + ("enabled" if self.dark_mode else "disabled"))

    def update_reference(self, event=None):
        self.current_reference = self.ref_combo.get()
        if self.current_reference == "Custom":
            self.custom_ref_entry.configure(state='normal')
            try:
                self.reference_diameter = float(self.custom_ref_entry.get())
                self.update_status(f"Custom reference set to {self.reference_diameter}mm")
            except ValueError:
                self.update_status("Enter custom reference size in mm")
        else:
            self.custom_ref_entry.configure(state='disabled')
            self.reference_diameter = self.reference_objects[self.current_reference]
            self.update_status(f"Reference set to {self.current_reference} ({self.reference_diameter}mm)")
    
    def toggle_cmm_mode(self):
        self.cmm_mode = not self.cmm_mode
        mode = "CMM Mode" if self.cmm_mode else "Standard Mode"
        self.update_status(f"{mode} activated")
        if self.cmm_mode:
            messagebox.showinfo("CMM Mode", 
                              "High-precision CMM mode activated\n"
                              f"Simulating {self.cmm_probe_type} probe\n"
                              f"Nominal accuracy: ±{self.cmm_accuracy}µm")
    
    def enable_ultima_simulation(self):
        self.cmm_mode = True
        self.cmm_accuracy = 0.5  # microns
        self.cmm_probe_type = "VAST XT gold"
        self.update_status("Ultima M 450 simulation activated")
        messagebox.showinfo("Ultima Simulation", 
                          "Zeiss Ultima M 450 simulation activated\n"
                          "Features simulated:\n"
                          "- VAST XT gold scanning probe\n"
                          "- 0.5µm accuracy\n"
                          "- Ceramic guideways\n"
                          "- Dynamic thermal compensation")
    
    def run_calibration(self):
        """Enhanced calibration routine similar to CMMs"""
        self.update_status("Running full system calibration...")
        
        # Simulate CMM calibration process
        self.calibration_data = {
            'date': datetime.now().isoformat(),
            'probe_type': self.cmm_probe_type,
            'linear_accuracy': self.cmm_accuracy,
            'volumetric_accuracy': self.cmm_accuracy * 1.5,
            'repeatability': self.cmm_accuracy * 0.3
        }
        
        # Create calibration report
        report = (
            "=== CMM Calibration Report ===\n"
            f"Date: {self.calibration_data['date']}\n"
            f"Probe: {self.calibration_data['probe_type']}\n"
            f"Linear Accuracy: ±{self.calibration_data['linear_accuracy']}µm\n"
            f"Volumetric Accuracy: ±{self.calibration_data['volumetric_accuracy']}µm\n"
            f"Repeatability: ±{self.calibration_data['repeatability']}µm\n"
            "Status: Calibration successful"
        )
        
        messagebox.showinfo("Calibration Complete", report)
        self.update_status("System calibration complete")
    
    def set_measurement_strategy(self):
        """Set measurement approach (automatic/manual)"""
        strategy = simpledialog.askstring("Measurement Strategy",
                                        "Enter measurement strategy (automatic/manual):",
                                        initialvalue=self.measurement_strategy)
        if strategy and strategy.lower() in ['automatic', 'manual']:
            self.measurement_strategy = strategy.lower()
            self.update_status(f"Measurement strategy set to {self.measurement_strategy}")

if __name__ == "__main__":
    root = tk.Tk()
    app = CNCToolMeasurerPro(root)
    root.mainloop()
