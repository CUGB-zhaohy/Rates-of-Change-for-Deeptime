"""
Graphical user interface for the RoC workflow.

This GUI is a wrapper around main.py. It does not change the calculation
logic directly. Instead, it builds a temporary runtime configuration file
from user-selected GUI parameters and then calls main.py as a subprocess.

Main GUI functions:
- select input Excel file
- define sheet, Age column, and Value column
- optional Z-score normalization
- select output directory
- set time-bin parameters and generate time-bin widths by range
- select RoC methods: IBR, TS, IQR
- select interpolation mode: none, linear, or weighted
- select advanced analyses: LRI, nTV/Gini, breakpoint, KDE, phase
- run dry-run checks and full workflow
- view runtime logs
- preview generated tables, text logs, and PNG figures

Run:
    python gui.py
"""

from __future__ import annotations

import os
import sys
import yaml
import queue
import threading
import subprocess
from pathlib import Path
import sys

if sys.platform == "win32":
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog, messagebox, scrolledtext

try:
    from PIL import Image, ImageTk
except Exception:
    Image = None
    ImageTk = None


class RoCGUI(tk.Tk):
    """
    Desktop GUI for running the RoC workflow.
    """

    def __init__(self):
        super().__init__()

        self.geometry("1400x900")
        self.minsize(1200, 760)

        # Increase global UI scaling.
        # You can try 1.2, 1.3, or 1.4 depending on your screen.
        self.tk.call("tk", "scaling", 1.25)

        # Global fonts.
        self.default_font = ("Segoe UI", 15)
        self.small_font = ("Segoe UI", 14)
        self.title_font = ("Segoe UI", 24, "bold")
        self.mono_font = ("Consolas", 14)

        self.configure_fonts()
        self.tk.call("tk", "scaling", 1.25)

        if getattr(sys, "frozen", False):
            self.project_root = Path(sys.executable).resolve().parent
        else:
            self.project_root = Path(__file__).resolve().parent

        self.title("RoC Workflow GUI")
        # Set GUI window icon.
        icon_path = self.project_root / "logo.ico"

        if icon_path.exists():
            try:
                self.iconbitmap(str(icon_path))
            except Exception:
                pass

        # ------------------------------------------------------------------
        # General paths
        # ------------------------------------------------------------------
        self.config_path = tk.StringVar(
            value=str(self.project_root / "config_test.yaml")
        )
        self.input_excel_path = tk.StringVar(
            value=str(self.project_root / "data" / "O.xlsx")
        )
        self.output_dir = tk.StringVar(
            value=str(self.project_root / "outputs")
        )

        # ------------------------------------------------------------------
        # Input settings
        # ------------------------------------------------------------------
        self.sheet_name = tk.StringVar(value="0")
        self.age_column = tk.StringVar(value="Age")
        self.value_column = tk.StringVar(value="Value")
        self.sort_by_age = tk.BooleanVar(value=True)
        self.use_zscore = tk.BooleanVar(value=True)

        # ------------------------------------------------------------------
        # Time-bin settings
        # ------------------------------------------------------------------
        self.start_age_kyr = tk.StringVar(value="67000")
        self.end_age_kyr = tk.StringVar(value="0")
        self.resolution_kyr = tk.StringVar(value="100")
        self.widths_text = tk.StringVar(value="100, 500, 1000")

        self.width_from = tk.StringVar(value="50")
        self.width_to = tk.StringVar(value="1000")
        self.width_step = tk.StringVar(value="50")

        # ------------------------------------------------------------------
        # Method settings
        # ------------------------------------------------------------------
        self.run_ibr = tk.BooleanVar(value=True)
        self.run_ts = tk.BooleanVar(value=True)
        self.run_iqr = tk.BooleanVar(value=True)

        # ------------------------------------------------------------------
        # Interpolation settings
        # ------------------------------------------------------------------
        self.interpolation_method = tk.StringVar(value="weighted")
        self.count_weight_alpha = tk.StringVar(value="1.0")
        self.distance_weight_beta = tk.StringVar(value="1.0")
        self.edge_mode = tk.StringVar(value="nearest")
        self.interpolation_method.trace_add(
            "write",
            lambda *_: self.update_interpolation_parameter_state(),
        )
        # ------------------------------------------------------------------
        # Advanced analysis settings
        # ------------------------------------------------------------------
        self.run_lri = tk.BooleanVar(value=True)
        self.run_metrics = tk.BooleanVar(value=True)
        self.run_breakpoint_analysis = tk.BooleanVar(value=True)
        self.run_plotting = tk.BooleanVar(value=True)

        self.breakpoint_data_type = tk.StringVar(
            value="time_scale_corrected_relative"
        )
        self.segments = tk.StringVar(value="5, 6")
        self.pwlf_half_window_kyr = tk.StringVar(value="1000")
        self.pwlf_min_points = tk.StringVar(value="5")
        self.pwlf_alpha = tk.StringVar(value="0.05")

        self.kde_grid_step_kyr = tk.StringVar(value="100")
        self.kde_bandwidth_kyr = tk.StringVar(value="1000")
        self.kde_top_n_peaks = tk.StringVar(value="10")

        # ------------------------------------------------------------------
        # Runtime state
        # ------------------------------------------------------------------
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.current_process: subprocess.Popen | None = None
        self.result_tree_path_map: dict[str, Path] = {}
        self.preview_image_ref = None

        # Progress state for Run & Log tab.
        self.progress_value = tk.DoubleVar(value=0.0)
        self.progress_text = tk.StringVar(value="Progress: idle")
        self.runtime_estimate_text = tk.StringVar(
            value="Estimated run time: not started yet."
        )

        # Folders/files hidden from the Results Preview tree.
        # These outputs are not part of the current main GUI workflow.
        self.hidden_result_names = {
            "11_sampling_sensitivity",
        }

        self._build_widgets()
        self.update_interpolation_parameter_state()
        self._poll_log_queue()
        self._auto_refresh_results()

    # ======================================================================
    # GUI layout
    # ======================================================================
    def create_scrollable_tab(self, parent: ttk.Frame) -> ttk.Frame:
        """
        Create a vertically scrollable frame inside a notebook tab.

        The scrollable content is placed in a top container, so that a
        fixed navigation footer can be added at the bottom of the tab.
        """
        scroll_container = ttk.Frame(parent)
        scroll_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(scroll_container, highlightthickness=0)
        y_scrollbar = ttk.Scrollbar(
            scroll_container,
            orient=tk.VERTICAL,
            command=canvas.yview,
        )

        scrollable_frame = ttk.Frame(canvas, padding=10)

        window_id = canvas.create_window(
            (0, 0),
            window=scrollable_frame,
            anchor="nw",
        )

        canvas.configure(yscrollcommand=y_scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def update_scroll_region(event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def update_frame_width(event):
            canvas.itemconfigure(window_id, width=event.width)

        def on_mousewheel(event):
            if event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")
            else:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def bind_mousewheel(event):
            canvas.bind_all("<MouseWheel>", on_mousewheel)
            canvas.bind_all("<Button-4>", on_mousewheel)
            canvas.bind_all("<Button-5>", on_mousewheel)

        def unbind_mousewheel(event):
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        scrollable_frame.bind("<Configure>", update_scroll_region)
        canvas.bind("<Configure>", update_frame_width)

        canvas.bind("<Enter>", bind_mousewheel)
        canvas.bind("<Leave>", unbind_mousewheel)

        return scrollable_frame

    def select_notebook_tab(self, tab_index: int):
        """
        Select a notebook tab by index.
        """
        if not hasattr(self, "notebook"):
            return

        tabs = self.notebook.tabs()

        if 0 <= int(tab_index) < len(tabs):
            self.notebook.select(int(tab_index))

    def add_navigation_footer(
            self,
            parent: ttk.Frame,
            previous_index: int | None = None,
            next_index: int | None = None,
    ):
        """
        Add previous/next navigation buttons at the bottom-right of a tab.

        Parameters
        ----------
        parent:
            The outer tab frame, such as self.input_tab_outer.

        previous_index:
            Notebook tab index for the Previous button. If None, no Previous
            button is added.

        next_index:
            Notebook tab index for the Next button. If None, no Next button
            is added.
        """
        footer = ttk.Frame(parent, padding=(10, 8, 10, 10))
        footer.pack(side=tk.BOTTOM, fill=tk.X)

        if next_index is not None:
            ttk.Button(
                footer,
                text="Next step ▶",
                style="Nav.TButton",
                command=lambda: self.select_notebook_tab(next_index),
            ).pack(side=tk.RIGHT)

        if previous_index is not None:
            ttk.Button(
                footer,
                text="◀ Previous step",
                style="Nav.TButton",
                command=lambda: self.select_notebook_tab(previous_index),
            ).pack(side=tk.RIGHT, padx=(0, 10))


    def configure_fonts(self):
        """
        Configure global fonts for Tk and ttk widgets.
        """
        default_font = tkfont.nametofont("TkDefaultFont")
        default_font.configure(family="Segoe UI", size=15)

        text_font = tkfont.nametofont("TkTextFont")
        text_font.configure(family="Segoe UI", size=15)

        fixed_font = tkfont.nametofont("TkFixedFont")
        fixed_font.configure(family="Consolas", size=14)

        menu_font = tkfont.nametofont("TkMenuFont")
        menu_font.configure(family="Segoe UI", size=15)

        heading_font = tkfont.nametofont("TkHeadingFont")
        heading_font.configure(family="Segoe UI", size=15, weight="bold")

        style = ttk.Style(self)

        style.configure("TLabel", font=self.default_font)
        style.configure("TButton", font=self.default_font)
        style.configure("TCheckbutton", font=self.default_font)
        style.configure("TRadiobutton", font=self.default_font)
        style.configure("TEntry", font=self.default_font)
        style.configure("TCombobox", font=self.default_font)
        style.configure("TLabelframe.Label", font=("Segoe UI", 15, "bold"))
        style.configure(
            "TNotebook.Tab",
            font=("Segoe UI", 17, "bold"),
            padding=(18, 8),
        )
        style.configure(
            "Nav.TButton",
            font=("Segoe UI", 15, "bold"),
            padding=(16, 8),
        )
        style.configure(
            "Horizontal.TProgressbar",
            thickness=22,
        )
        style.configure("Treeview", font=("Segoe UI", 15), rowheight=34)
        style.configure("Treeview.Heading", font=("Segoe UI", 15, "bold"))

    def _build_widgets(self):
        """
        Build the main GUI layout.
        """
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        title_label = ttk.Label(
            main_frame,
            text="Rates-of-Change RoC Workflow",
            font=self.title_font,
        )
        title_label.pack(anchor="w", pady=(0, 8))

        subtitle = ttk.Label(
            main_frame,
            text=(
                "Configure input data, RoC settings, advanced analysis, "
                "then run the workflow and preview outputs."
            ),
        )
        subtitle.pack(anchor="w", pady=(0, 10))

        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.input_tab_outer = ttk.Frame(self.notebook)
        self.roc_tab_outer = ttk.Frame(self.notebook)
        self.analysis_tab_outer = ttk.Frame(self.notebook)

        self.run_tab = ttk.Frame(self.notebook, padding=10)
        self.results_tab = ttk.Frame(self.notebook, padding=10)

        self.notebook.add(self.input_tab_outer, text="1. Input Data")
        self.notebook.add(self.roc_tab_outer, text="2. RoC Settings")
        self.notebook.add(self.analysis_tab_outer, text="3. Advanced Analysis")
        self.notebook.add(self.run_tab, text="4. Run & Log")
        self.notebook.add(self.results_tab, text="5. Results Preview")

        self.input_tab = self.create_scrollable_tab(self.input_tab_outer)
        self.roc_tab = self.create_scrollable_tab(self.roc_tab_outer)
        self.analysis_tab = self.create_scrollable_tab(self.analysis_tab_outer)

        self._build_input_tab()
        self._build_roc_tab()
        self._build_analysis_tab()
        self._build_run_tab()
        self._build_results_tab()

        # Bottom navigation buttons for the first three workflow tabs.
        self.add_navigation_footer(
            parent=self.input_tab_outer,
            previous_index=None,
            next_index=1,
        )

        self.add_navigation_footer(
            parent=self.roc_tab_outer,
            previous_index=0,
            next_index=2,
        )

        self.add_navigation_footer(
            parent=self.analysis_tab_outer,
            previous_index=1,
            next_index=3,
        )

    def _build_input_tab(self):
        """
        Build input data tab.
        """
        frame = self.input_tab

        config_frame = ttk.LabelFrame(frame, text="Base configuration", padding=10)
        config_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(config_frame, text="Base config file:").grid(row=0, column=0, sticky="w")
        ttk.Entry(config_frame, textvariable=self.config_path).grid(
            row=0, column=1, sticky="ew", padx=8
        )
        ttk.Button(
            config_frame,
            text="Browse",
            command=self.browse_config,
        ).grid(row=0, column=2, sticky="e")
        config_frame.columnconfigure(1, weight=1)

        input_frame = ttk.LabelFrame(frame, text="Input Excel data", padding=10)
        input_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(input_frame, text="Excel file:").grid(row=0, column=0, sticky="w")
        ttk.Entry(input_frame, textvariable=self.input_excel_path).grid(
            row=0, column=1, sticky="ew", padx=8
        )
        ttk.Button(
            input_frame,
            text="Browse",
            command=self.browse_input_excel,
        ).grid(row=0, column=2, sticky="e")

        ttk.Label(input_frame, text="Sheet:").grid(
            row=1, column=0, sticky="w", pady=(8, 0)
        )
        ttk.Entry(input_frame, textvariable=self.sheet_name, width=20).grid(
            row=1, column=1, sticky="w", padx=8, pady=(8, 0)
        )

        ttk.Label(input_frame, text="Age column:").grid(
            row=2, column=0, sticky="w", pady=(8, 0)
        )
        ttk.Entry(input_frame, textvariable=self.age_column, width=20).grid(
            row=2, column=1, sticky="w", padx=8, pady=(8, 0)
        )

        ttk.Label(input_frame, text="Value column:").grid(
            row=3, column=0, sticky="w", pady=(8, 0)
        )
        ttk.Entry(input_frame, textvariable=self.value_column, width=20).grid(
            row=3, column=1, sticky="w", padx=8, pady=(8, 0)
        )

        ttk.Checkbutton(
            input_frame,
            text="Sort data by Age before analysis",
            variable=self.sort_by_age,
        ).grid(row=4, column=1, sticky="w", padx=8, pady=(10, 0))

        ttk.Checkbutton(
            input_frame,
            text="Use Z-score normalized values for RoC analysis",
            variable=self.use_zscore,
        ).grid(row=5, column=1, sticky="w", padx=8, pady=(6, 0))

        input_frame.columnconfigure(1, weight=1)

        output_frame = ttk.LabelFrame(frame, text="Output folder", padding=10)
        output_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(output_frame, text="Output folder:").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Entry(output_frame, textvariable=self.output_dir).grid(
            row=0, column=1, sticky="ew", padx=8
        )
        ttk.Button(
            output_frame,
            text="Browse",
            command=self.browse_output_folder,
        ).grid(row=0, column=2, sticky="e")
        ttk.Button(
            output_frame,
            text="Open outputs",
            command=self.open_outputs,
        ).grid(row=0, column=3, sticky="e", padx=(8, 0))

        output_frame.columnconfigure(1, weight=1)

        note_frame = ttk.LabelFrame(frame, text="Notes", padding=10)
        note_frame.pack(fill=tk.X)

        note_text = (
            "1. The base config file provides default and advanced settings. "
            "Values shown in the GUI will override the corresponding settings "
            "in the base config during runtime.\n\n"
            "2. Default sheet = 0 means the first sheet in the Excel file.\n\n"
            "3. If Z-score is enabled, the workflow will add a Z_score column and "
            "use it for RoC calculation."
        )

        note_label = ttk.Label(
            note_frame,
            text=note_text,
            justify="left",
        )
        note_label.pack(anchor="w", fill=tk.X)

        def update_note_wraplength(event):
            note_label.configure(wraplength=max(event.width - 30, 600))

        note_frame.bind("<Configure>", update_note_wraplength)

    def _build_roc_tab(self):
        """
        Build RoC settings tab.
        """
        frame = self.roc_tab

        age_frame = ttk.LabelFrame(frame, text="Age range and resolution", padding=10)
        age_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(age_frame, text="Start age (kyr):").grid(row=0, column=0, sticky="w")
        ttk.Entry(age_frame, textvariable=self.start_age_kyr, width=15).grid(
            row=0, column=1, sticky="w", padx=8
        )

        ttk.Label(age_frame, text="End age (kyr):").grid(row=0, column=2, sticky="w")
        ttk.Entry(age_frame, textvariable=self.end_age_kyr, width=15).grid(
            row=0, column=3, sticky="w", padx=8
        )

        ttk.Label(age_frame, text="Step (kyr):").grid(
            row=0, column=4, sticky="w"
        )
        ttk.Entry(age_frame, textvariable=self.resolution_kyr, width=15).grid(
            row=0, column=5, sticky="w", padx=8
        )

        width_frame = ttk.LabelFrame(frame, text="Analytical time-bin widths", padding=10)
        width_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(width_frame, text="Time-bin widths (kyr):").grid(
            row=0, column=0, sticky="nw"
        )

        widths_entry = ttk.Entry(width_frame, textvariable=self.widths_text)
        widths_entry.grid(row=0, column=1, columnspan=6, sticky="ew", padx=8)

        generate_frame = ttk.Frame(width_frame)
        generate_frame.grid(
            row=1,
            column=1,
            columnspan=7,
            sticky="w",
            padx=8,
            pady=(10, 0),
        )

        ttk.Label(width_frame, text="Generate widths:").grid(
            row=1, column=0, sticky="w", pady=(10, 0)
        )

        ttk.Label(generate_frame, text="From").pack(side=tk.LEFT)
        ttk.Entry(
            generate_frame,
            textvariable=self.width_from,
            width=8,
        ).pack(side=tk.LEFT, padx=(4, 12))

        ttk.Label(generate_frame, text="To").pack(side=tk.LEFT)
        ttk.Entry(
            generate_frame,
            textvariable=self.width_to,
            width=8,
        ).pack(side=tk.LEFT, padx=(4, 12))

        ttk.Label(generate_frame, text="Step").pack(side=tk.LEFT)
        ttk.Entry(
            generate_frame,
            textvariable=self.width_step,
            width=8,
        ).pack(side=tk.LEFT, padx=(4, 12))

        ttk.Button(
            generate_frame,
            text="Generate",
            command=self.generate_widths,
        ).pack(side=tk.LEFT)

        width_frame.columnconfigure(1, weight=1)

        method_frame = ttk.LabelFrame(frame, text="RoC methods", padding=10)
        method_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Checkbutton(method_frame, text="IBR", variable=self.run_ibr).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Checkbutton(method_frame, text="TS", variable=self.run_ts).grid(
            row=0, column=1, sticky="w", padx=20
        )
        ttk.Checkbutton(method_frame, text="IQR", variable=self.run_iqr).grid(
            row=0, column=2, sticky="w"
        )

        interp_frame = ttk.LabelFrame(frame, text="Interpolation", padding=10)
        interp_frame.pack(fill=tk.X)

        ttk.Radiobutton(
            interp_frame,
            text="No interpolation",
            variable=self.interpolation_method,
            value="none",
        ).grid(row=0, column=0, sticky="w")

        ttk.Radiobutton(
            interp_frame,
            text="Linear interpolation",
            variable=self.interpolation_method,
            value="linear",
        ).grid(row=0, column=1, sticky="w", padx=20)

        ttk.Radiobutton(
            interp_frame,
            text="Distance-count weighted interpolation",
            variable=self.interpolation_method,
            value="weighted",
        ).grid(row=0, column=2, sticky="w")

        self.count_weight_label = ttk.Label(interp_frame, text="Count weight alpha:")
        self.count_weight_label.grid(row=1, column=0, sticky="w", pady=(10, 0))

        self.count_weight_entry = ttk.Entry(
            interp_frame,
            textvariable=self.count_weight_alpha,
            width=12,
        )
        self.count_weight_entry.grid(row=1, column=1, sticky="w", pady=(10, 0))

        self.distance_weight_label = ttk.Label(interp_frame, text="Distance weight beta:")
        self.distance_weight_label.grid(row=2, column=0, sticky="w", pady=(8, 0))

        self.distance_weight_entry = ttk.Entry(
            interp_frame,
            textvariable=self.distance_weight_beta,
            width=12,
        )
        self.distance_weight_entry.grid(row=2, column=1, sticky="w", pady=(8, 0))

        self.edge_mode_label = ttk.Label(interp_frame, text="Edge mode:")
        self.edge_mode_label.grid(row=3, column=0, sticky="w", pady=(8, 0))

        self.edge_mode_combobox = ttk.Combobox(
            interp_frame,
            textvariable=self.edge_mode,
            values=["nearest", "nan", "zero"],
            width=10,
            state="readonly",
        )
        self.edge_mode_combobox.grid(row=3, column=1, sticky="w", pady=(8, 0))
        note_frame = ttk.LabelFrame(frame, text="Notes", padding=10)
        note_frame.pack(fill=tk.X, pady=(10, 0))

        note_text = (
            "1. Start age should be greater than End age. For example, use "
            "Start age = 67000 kyr and End age = 0 kyr for a 0–67 Ma record.\n\n"
            "2. Start age, End age, and Step jointly define the age nodes used for "
            "RoC calculation. Step is the spacing between adjacent age nodes. "
            "For example, Step = 100 kyr generates age nodes every 100 kyr.\n\n"
            "3. Time-bin widths define the analytical timescales. The Generate widths "
            "tool can quickly create a sequence of widths, such as 50–1000 kyr "
            "with a 50 kyr step.\n\n"
            "4. Edge mode controls how missing values at the beginning or end of "
            "the interpolated series are handled:\n"
            "   - nearest: fill edge missing values using the nearest valid value.\n"
            "   - nan: keep edge missing values as NaN.\n"
            "   - zero: fill edge missing values with 0."
        )

        note_label = ttk.Label(
            note_frame,
            text=note_text,
            justify="left",
        )
        note_label.pack(anchor="w", fill=tk.X)

        def update_note_wraplength(event):
            note_label.configure(wraplength=max(event.width - 30, 600))

        note_frame.bind("<Configure>", update_note_wraplength)

    def _build_analysis_tab(self):
        """
        Build advanced analysis tab.
        """
        frame = self.analysis_tab

        analysis_frame = ttk.LabelFrame(frame, text="Post-RoC analysis", padding=10)
        analysis_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Checkbutton(
            analysis_frame,
            text="LRI time-scale effect analysis and correction",
            variable=self.run_lri,
        ).grid(row=0, column=0, sticky="w")

        ttk.Checkbutton(
            analysis_frame,
            text="nTV / Gini method evaluation",
            variable=self.run_metrics,
        ).grid(row=1, column=0, sticky="w", pady=(6, 0))

        ttk.Checkbutton(
            analysis_frame,
            text="Breakpoint analysis: PWLF + KDE consensus + phase statistics",
            variable=self.run_breakpoint_analysis,
        ).grid(row=2, column=0, sticky="w", pady=(6, 0))

        ttk.Checkbutton(
            analysis_frame,
            text="Generate SVG and PNG summary figures",
            variable=self.run_plotting,
        ).grid(row=5, column=0, sticky="w", pady=(6, 0))

        bp_frame = ttk.LabelFrame(frame, text="Breakpoint settings", padding=10)
        bp_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(bp_frame, text="Breakpoint input:").grid(row=0, column=0, sticky="w")

        ttk.Radiobutton(
            bp_frame,
            text="Raw RoC results",
            variable=self.breakpoint_data_type,
            value="raw",
        ).grid(row=0, column=1, sticky="w", padx=8)

        ttk.Radiobutton(
            bp_frame,
            text="Time-scale-corrected relative RoC results",
            variable=self.breakpoint_data_type,
            value="time_scale_corrected_relative",
        ).grid(row=0, column=2, sticky="w", padx=8)

        ttk.Label(bp_frame, text="Segments:").grid(
            row=1, column=0, sticky="w", pady=(10, 0)
        )
        ttk.Entry(bp_frame, textvariable=self.segments, width=25).grid(
            row=1, column=1, sticky="w", padx=8, pady=(10, 0)
        )

        ttk.Label(bp_frame, text="PWLF half-window (kyr):").grid(
            row=2, column=0, sticky="w", pady=(8, 0)
        )
        ttk.Entry(bp_frame, textvariable=self.pwlf_half_window_kyr, width=12).grid(
            row=2, column=1, sticky="w", padx=8, pady=(8, 0)
        )

        ttk.Label(bp_frame, text="PWLF min points:").grid(
            row=3, column=0, sticky="w", pady=(8, 0)
        )
        ttk.Entry(bp_frame, textvariable=self.pwlf_min_points, width=12).grid(
            row=3, column=1, sticky="w", padx=8, pady=(8, 0)
        )

        ttk.Label(bp_frame, text="PWLF alpha:").grid(
            row=4, column=0, sticky="w", pady=(8, 0)
        )
        ttk.Entry(bp_frame, textvariable=self.pwlf_alpha, width=12).grid(
            row=4, column=1, sticky="w", padx=8, pady=(8, 0)
        )

        kde_frame = ttk.LabelFrame(frame, text="KDE and phase settings", padding=10)
        kde_frame.pack(fill=tk.X)

        ttk.Label(kde_frame, text="KDE grid step (kyr):").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Entry(kde_frame, textvariable=self.kde_grid_step_kyr, width=12).grid(
            row=0, column=1, sticky="w", padx=8
        )

        ttk.Label(kde_frame, text="KDE bandwidth (kyr):").grid(
            row=1, column=0, sticky="w", pady=(8, 0)
        )
        ttk.Entry(kde_frame, textvariable=self.kde_bandwidth_kyr, width=12).grid(
            row=1, column=1, sticky="w", padx=8, pady=(8, 0)
        )

        ttk.Label(kde_frame, text="Consensus breakpoints:").grid(
            row=2, column=0, sticky="w", pady=(8, 0)
        )
        ttk.Entry(kde_frame, textvariable=self.kde_top_n_peaks, width=12).grid(
            row=2, column=1, sticky="w", padx=8, pady=(8, 0)
        )
        note_frame = ttk.LabelFrame(frame, text="Notes", padding=10)
        note_frame.pack(fill=tk.X, pady=(10, 0))

        note_text = (
            "1. PWLF segments defines the number of linear segments used to fit "
            "the cumulative RoC curve. A larger number of segments allows more "
            "breakpoints to be detected, but may also identify more local or "
            "minor changes.\n\n"
            "2. PWLF half-window controls the age window used for local statistical "
            "testing around each breakpoint. A larger half-window gives a broader "
            "comparison around the breakpoint, whereas a smaller half-window focuses "
            "on more local changes.\n\n"
            "3. PWLF min points defines the minimum number of data points required "
            "on each side of a breakpoint for local testing. A larger value makes "
            "the test more conservative.\n\n"
            "4. KDE grid step controls the age spacing of the KDE density grid. "
            "A smaller grid step gives a finer age resolution but requires more "
            "calculation time.\n\n"
            "5. KDE bandwidth controls the smoothing window for consensus breakpoint "
            "detection. A larger bandwidth merges nearby breakpoints into broader "
            "consensus peaks, whereas a smaller bandwidth preserves more local peaks.\n\n"
            "6. Consensus breakpoints defines the maximum number of KDE peaks retained "
            "as final consensus breakpoints. These breakpoints are then used to divide "
            "the record into phases."
        )

        note_label = ttk.Label(
            note_frame,
            text=note_text,
            justify="left",
        )
        note_label.pack(anchor="w", fill=tk.X)

        def update_note_wraplength(event):
            note_label.configure(wraplength=max(event.width - 30, 600))

        note_frame.bind("<Configure>", update_note_wraplength)

    def _build_run_tab(self):
        """
        Build run and log tab.
        """
        frame = self.run_tab

        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))

        self.dry_run_button = ttk.Button(
            button_frame,
            text="Check settings / Dry run",
            command=self.run_dry_run,
        )
        self.dry_run_button.pack(side=tk.LEFT, padx=(0, 8))

        self.run_button = ttk.Button(
            button_frame,
            text="Run workflow",
            command=self.run_workflow,
        )
        self.run_button.pack(side=tk.LEFT, padx=(0, 8))

        self.stop_button = ttk.Button(
            button_frame,
            text="Stop",
            command=self.stop_process,
            state=tk.DISABLED,
        )
        self.stop_button.pack(side=tk.LEFT, padx=(0, 8))

        self.clear_button = ttk.Button(
            button_frame,
            text="Clear log",
            command=self.clear_log,
        )
        self.clear_button.pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(
            button_frame,
            text="Open output folder",
            command=self.open_outputs,
        ).pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(
            button_frame,
            text="Refresh results",
            command=self.refresh_result_tree,
        ).pack(side=tk.LEFT)

        progress_frame = ttk.LabelFrame(frame, text="Workflow progress", padding=10)
        progress_frame.pack(fill=tk.X, pady=(0, 10))

        estimate_label = ttk.Label(
            progress_frame,
            textvariable=self.runtime_estimate_text,
            justify="left",
        )
        estimate_label.pack(anchor="w", pady=(0, 6))

        progress_label = ttk.Label(
            progress_frame,
            textvariable=self.progress_text,
            justify="left",
        )
        progress_label.pack(anchor="w", pady=(0, 6))

        self.progress_bar = ttk.Progressbar(
            progress_frame,
            variable=self.progress_value,
            maximum=100,
            mode="determinate",
            style="Horizontal.TProgressbar",
        )
        self.progress_bar.pack(fill=tk.X)

        log_frame = ttk.LabelFrame(frame, text="Run log", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            font=self.mono_font,
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

        self.write_log("RoC Workflow GUI started.")
        self.write_log(f"Project root: {self.project_root}")
        self.write_log("Configure the workflow, then use Dry run or Run workflow.")

    def _build_results_tab(self):
        """
        Build results preview tab.
        """
        frame = self.results_tab

        toolbar = ttk.Frame(frame)
        toolbar.pack(fill=tk.X, pady=(0, 8))

        ttk.Button(
            toolbar,
            text="Refresh",
            command=self.refresh_result_tree,
        ).pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(
            toolbar,
            text="Open selected file",
            command=self.open_selected_result,
        ).pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(
            toolbar,
            text="Open output folder",
            command=self.open_outputs,
        ).pack(side=tk.LEFT)

        paned = ttk.PanedWindow(frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        left_frame = ttk.LabelFrame(paned, text="Output files", padding=6)
        right_frame = ttk.LabelFrame(paned, text="Preview", padding=6)

        paned.add(left_frame, weight=1)
        paned.add(right_frame, weight=3)

        self.result_tree = ttk.Treeview(left_frame, show="tree")
        tree_scroll = ttk.Scrollbar(
            left_frame,
            orient=tk.VERTICAL,
            command=self.result_tree.yview,
        )
        self.result_tree.configure(yscrollcommand=tree_scroll.set)

        self.result_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.result_tree.bind("<<TreeviewSelect>>", self.preview_selected_result)

        self.preview_frame = ttk.Frame(right_frame)
        self.preview_frame.pack(fill=tk.BOTH, expand=True)

        self.show_text_preview(
            "Results preview will appear here.\n\n"
            "After running the workflow, click Refresh or select a file from "
            "the output tree.\n\n"
            "Supported previews:\n"
            "- Excel/CSV: first 100 rows\n"
            "- TXT/log: text content\n"
            "- PNG/JPG: image preview\n"
            "- SVG: open externally"
        )

    # ======================================================================
    # Browse functions
    # ======================================================================
    def browse_config(self):
        """
        Select a YAML configuration file.
        """
        selected_file = filedialog.askopenfilename(
            title="Select config file",
            initialdir=str(self.project_root),
            filetypes=[
                ("YAML files", "*.yaml *.yml"),
                ("All files", "*.*"),
            ],
        )

        if selected_file:
            self.config_path.set(selected_file)

    def browse_input_excel(self):
        """
        Select an input Excel file.
        """
        selected_file = filedialog.askopenfilename(
            title="Select input Excel file",
            initialdir=str(self.project_root / "data"),
            filetypes=[
                ("Excel files", "*.xlsx *.xls"),
                ("All files", "*.*"),
            ],
        )

        if selected_file:
            self.input_excel_path.set(selected_file)

    def browse_output_folder(self):
        """
        Select an output folder.
        """
        selected_dir = filedialog.askdirectory(
            title="Select output folder",
            initialdir=str(self.project_root),
        )

        if selected_dir:
            self.output_dir.set(selected_dir)
            self.refresh_result_tree()

    # ======================================================================
    # Parsing helpers
    # ======================================================================
    def _parse_sheet_value(self):
        """
        Convert sheet value from GUI to int if possible.
        """
        sheet_text = self.sheet_name.get().strip()

        if sheet_text == "":
            return 0

        try:
            return int(sheet_text)
        except ValueError:
            return sheet_text

    def parse_float(self, value_text: str, name: str) -> float:
        """
        Parse a float value from text.
        """
        try:
            return float(str(value_text).strip())
        except ValueError as exc:
            raise ValueError(f"{name} must be a numeric value.") from exc

    def parse_int(self, value_text: str, name: str) -> int:
        """
        Parse an integer value from text.
        """
        try:
            value = float(str(value_text).strip())
        except ValueError as exc:
            raise ValueError(f"{name} must be an integer value.") from exc

        if not value.is_integer():
            raise ValueError(f"{name} must be an integer value.")

        return int(value)

    def parse_number_list(self, text: str, name: str) -> list[float]:
        """
        Parse comma/semicolon/space separated numeric values.
        """
        text = str(text).replace(";", ",").replace("，", ",")
        parts = []

        for chunk in text.split(","):
            chunk = chunk.strip()

            if chunk:
                parts.append(chunk)

        values = []

        for part in parts:
            try:
                values.append(float(part))
            except ValueError as exc:
                raise ValueError(f"{name} contains invalid value: {part}") from exc

        if not values:
            raise ValueError(f"{name} cannot be empty.")

        return values

    def parse_int_list(self, text: str, name: str) -> list[int]:
        """
        Parse comma-separated integer values.
        """
        values = self.parse_number_list(text, name)
        output = []

        for value in values:
            if not float(value).is_integer():
                raise ValueError(f"{name} must contain integers only.")
            output.append(int(value))

        if not output:
            raise ValueError(f"{name} cannot be empty.")

        return output

    def generate_widths(self):
        """
        Generate time-bin widths from From/To/Step fields.
        """
        try:
            start = self.parse_float(self.width_from.get(), "Width from")
            end = self.parse_float(self.width_to.get(), "Width to")
            step = self.parse_float(self.width_step.get(), "Width step")

            if step <= 0:
                raise ValueError("Width step must be greater than 0.")

            if end < start:
                raise ValueError("Width to must be greater than or equal to Width from.")

            values = []
            current = start

            while current <= end + 1e-9:
                values.append(current)
                current += step

            if not values:
                raise ValueError("No time-bin widths were generated.")

            formatted = []

            for value in values:
                if float(value).is_integer():
                    formatted.append(str(int(value)))
                else:
                    formatted.append(str(value))

            self.widths_text.set(", ".join(formatted))
            self.write_log(
                "Generated time-bin widths: " + ", ".join(formatted)
            )

        except Exception as exc:
            messagebox.showerror(
                "Invalid time-bin width range",
                str(exc),
            )

    def update_interpolation_parameter_state(self):
        """
        Enable or disable interpolation parameter widgets according to the
        selected interpolation method.

        No interpolation:
            all interpolation parameters are disabled.

        Linear interpolation:
            edge_mode is still useful for boundary missing values, but
            count_weight_alpha and distance_weight_beta are disabled.

        Weighted interpolation:
            all interpolation parameters are enabled.
        """
        if not hasattr(self, "count_weight_entry"):
            return

        method = self.interpolation_method.get()

        if method == "none":
            weighted_state = tk.DISABLED
            edge_state = tk.DISABLED
        elif method == "linear":
            weighted_state = tk.DISABLED
            edge_state = "readonly"
        else:
            weighted_state = tk.NORMAL
            edge_state = "readonly"

        self.count_weight_entry.configure(state=weighted_state)
        self.distance_weight_entry.configure(state=weighted_state)
        self.edge_mode_combobox.configure(state=edge_state)


    # ======================================================================
    # Runtime config
    # ======================================================================
    def build_runtime_config(self) -> Path:
        """
        Build a temporary config file for GUI-based execution.
        """
        base_config_path = Path(self.config_path.get())
        input_file = Path(self.input_excel_path.get())
        output_dir = Path(self.output_dir.get())

        if not base_config_path.exists():
            raise FileNotFoundError(f"Config file does not exist: {base_config_path}")

        if not input_file.exists():
            raise FileNotFoundError(f"Input Excel file does not exist: {input_file}")

        age_col = self.age_column.get().strip()
        value_col = self.value_column.get().strip()

        if age_col == "":
            raise ValueError("Age column name cannot be empty.")

        if value_col == "":
            raise ValueError("Value column name cannot be empty.")

        start_age = self.parse_float(self.start_age_kyr.get(), "Start age")
        end_age = self.parse_float(self.end_age_kyr.get(), "End age")
        resolution = self.parse_float(self.resolution_kyr.get(), "Step")

        if start_age <= end_age:
            raise ValueError(
                "Start age must be greater than End age. "
                "For example, use Start age = 67000 kyr and End age = 0 kyr."
            )

        if resolution <= 0:
            raise ValueError("Step must be greater than 0.")

        widths = self.parse_number_list(
            self.widths_text.get(),
            "Time-bin widths",
        )

        widths = sorted(set(float(width) for width in widths))

        if any(width <= 0 for width in widths):
            raise ValueError("All time-bin widths must be greater than 0.")

        if not (
            self.run_ibr.get()
            or self.run_ts.get()
            or self.run_iqr.get()
        ):
            raise ValueError("At least one RoC method must be selected.")

        if (
                self.breakpoint_data_type.get() == "time_scale_corrected_relative"
                and self.run_breakpoint_analysis.get()
                and not self.run_lri.get()
        ):
            raise ValueError(
                "Breakpoint input is set to time-scale-corrected relative RoC, "
                "but LRI correction is not enabled."
            )

        with open(base_config_path, "r", encoding="utf-8") as file:
            config = yaml.safe_load(file)

        if config is None:
            config = {}

        # ------------------------------------------------------------------
        # Hidden advanced method settings
        # ------------------------------------------------------------------
        # These settings are controlled by config_test.yaml / config_full.yaml.
        # They are not shown in the GUI, but must be preserved in config_gui.yaml.
        base_methods_config = config.get("methods", {})

        base_iqr_quartile_method = str(
            base_methods_config.get("iqr_quartile_method", "exc")
        ).strip().lower()

        if base_iqr_quartile_method in {
            "exc",
            "exclusive",
            "quartile.exc",
            "percentile.exc",
        }:
            base_iqr_quartile_method = "exc"
        elif base_iqr_quartile_method in {
            "inc",
            "inclusive",
            "quartile.inc",
            "percentile.inc",
        }:
            base_iqr_quartile_method = "inc"
        else:
            raise ValueError(
                "methods.iqr_quartile_method must be 'exc' or 'inc'. "
                f"Got: {base_iqr_quartile_method}"
            )

        try:
            base_iqr_min_count = int(base_methods_config.get("iqr_min_count", 5))
        except Exception as exc:
            raise ValueError(
                "methods.iqr_min_count must be an integer greater than or equal to 1."
            ) from exc

        if base_iqr_min_count < 1:
            raise ValueError(
                "methods.iqr_min_count must be an integer greater than or equal to 1."
            )

        age_min = min(start_age, end_age)
        age_max = max(start_age, end_age)

        # ------------------------------------------------------------------
        # Input and output
        # ------------------------------------------------------------------
        config.setdefault("input", {})
        config["input"]["file"] = str(input_file)
        config["input"]["sheet"] = self._parse_sheet_value()
        config["input"]["age_column"] = age_col
        config["input"]["value_column"] = value_col

        config.setdefault("output", {})
        config["output"]["directory"] = str(output_dir)

        # ------------------------------------------------------------------
        # Preprocess
        # ------------------------------------------------------------------
        config.setdefault("preprocess", {})
        config["preprocess"]["sort_by_age"] = bool(self.sort_by_age.get())
        config["preprocess"]["use_zscore"] = bool(self.use_zscore.get())
        config["preprocess"]["zscore_column"] = "Z_score"
        config["preprocess"]["save_preprocessed"] = True

        # ------------------------------------------------------------------
        # Time-bin settings
        # ------------------------------------------------------------------
        config.setdefault("timebin", {})
        config["timebin"]["start_age_kyr"] = start_age
        config["timebin"]["end_age_kyr"] = end_age
        config["timebin"]["resolution_kyr"] = resolution
        config["timebin"]["widths_kyr"] = widths

        # ------------------------------------------------------------------
        # Methods
        # ------------------------------------------------------------------
        config.setdefault("methods", {})
        config["methods"]["run_ibr"] = bool(self.run_ibr.get())
        config["methods"]["run_ts"] = bool(self.run_ts.get())
        config["methods"]["run_iqr"] = bool(self.run_iqr.get())
        config["methods"]["theilsen_alpha"] = 0.90

        # Hidden IQR settings preserved from the selected base config.
        # They are intentionally not exposed in the GUI.
        config["methods"]["iqr_quartile_method"] = base_iqr_quartile_method
        config["methods"]["iqr_min_count"] = base_iqr_min_count

        # ------------------------------------------------------------------
        # Interpolation
        # ------------------------------------------------------------------
        config.setdefault("interpolation", {})
        config["interpolation"]["method"] = self.interpolation_method.get()
        config["interpolation"]["count_weight_alpha"] = self.parse_float(
            self.count_weight_alpha.get(),
            "Count weight alpha",
        )
        config["interpolation"]["distance_weight_beta"] = self.parse_float(
            self.distance_weight_beta.get(),
            "Distance weight beta",
        )
        config["interpolation"]["edge_mode"] = self.edge_mode.get()

        # ------------------------------------------------------------------
        # Analysis switches
        # ------------------------------------------------------------------
        config.setdefault("analysis", {})
        config["analysis"]["run_lri"] = bool(self.run_lri.get())
        config["analysis"]["run_metrics"] = bool(self.run_metrics.get())

        run_breakpoint_analysis = bool(self.run_breakpoint_analysis.get())
        config["analysis"]["run_pwlf"] = run_breakpoint_analysis
        config["analysis"]["run_kde"] = run_breakpoint_analysis
        config["analysis"]["run_phase"] = run_breakpoint_analysis

        config["analysis"]["run_plotting"] = bool(self.run_plotting.get())

        # ------------------------------------------------------------------
        # Breakpoint, KDE, phase
        # ------------------------------------------------------------------
        config.setdefault("breakpoint", {})
        config["breakpoint"]["data_type"] = self.breakpoint_data_type.get()
        config["breakpoint"]["age_min_kyr"] = age_min
        config["breakpoint"]["age_max_kyr"] = age_max
        config["breakpoint"]["segments"] = self.parse_int_list(
            self.segments.get(),
            "Segments",
        )
        config["breakpoint"]["half_window_kyr"] = self.parse_float(
            self.pwlf_half_window_kyr.get(),
            "PWLF half-window",
        )
        config["breakpoint"]["min_points"] = self.parse_int(
            self.pwlf_min_points.get(),
            "PWLF min points",
        )
        config["breakpoint"]["alpha"] = self.parse_float(
            self.pwlf_alpha.get(),
            "PWLF alpha",
        )

        config.setdefault("kde", {})
        config["kde"]["age_min_kyr"] = age_min
        config["kde"]["age_max_kyr"] = age_max
        config["kde"]["grid_step_kyr"] = self.parse_float(
            self.kde_grid_step_kyr.get(),
            "KDE grid step",
        )
        config["kde"]["bandwidth_kyr"] = self.parse_float(
            self.kde_bandwidth_kyr.get(),
            "KDE bandwidth",
        )
        config["kde"]["top_n_peaks"] = self.parse_int(
            self.kde_top_n_peaks.get(),
            "Consensus breakpoints",
        )

        config.setdefault("phase", {})
        config["phase"]["age_min_kyr"] = age_min
        config["phase"]["age_max_kyr"] = age_max
        config["phase"]["breakpoint_col"] = "Consensus_breakpoint_kyr"
        config["phase"]["sort_breakpoints"] = True

        # ------------------------------------------------------------------
        # Plotting
        # ------------------------------------------------------------------
        config.setdefault("plotting", {})
        config["plotting"]["enabled"] = bool(self.run_plotting.get())
        config["plotting"]["figure_formats"] = ["svg", "png"]
        config["plotting"]["dpi"] = int(config["plotting"].get("dpi", 600))
        config["plotting"]["age_min_kyr"] = age_min
        config["plotting"]["age_max_kyr"] = age_max

        runtime_dir = self.project_root / ".gui_runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)

        runtime_config_path = runtime_dir / "config_gui.yaml"

        with open(runtime_config_path, "w", encoding="utf-8") as file:
            yaml.safe_dump(
                config,
                file,
                sort_keys=False,
                allow_unicode=True,
            )

        return runtime_config_path

    # ======================================================================
    # Run functions
    # ======================================================================
    def run_dry_run(self):
        """
        Run dry-run mode.
        """
        self._run_command(dry_run=True)

    def run_workflow(self):
        """
        Run full workflow after confirming output folder.
        """
        output_path = Path(self.output_dir.get())

        confirm = messagebox.askyesno(
            "Confirm output folder",
            "The workflow results will be saved to:\n\n"
            f"{output_path}\n\n"
            "Do you want to continue?"
        )

        if not confirm:
            self.write_log("Workflow run was cancelled by the user.")
            return

        self._run_command(dry_run=False)

    def build_main_command(self, runtime_config_path: Path, dry_run: bool) -> list[str]:
        """
        Build command for running the workflow.

        In source-code mode, the GUI calls:
            python main.py --config config_gui.yaml

        In frozen exe mode, the GUI calls:
            RoC_Workflow_Main.exe --config config_gui.yaml
        """
        if getattr(sys, "frozen", False):
            main_exe = self.project_root / "_internal" / "RoC_Workflow_Main.exe"

            if not main_exe.exists():
                raise FileNotFoundError(
                    f"Workflow backend executable was not found:\n{main_exe}"
                )

            command = [
                str(main_exe),
                "--config",
                str(runtime_config_path),
            ]
        else:
            command = [
                sys.executable,
                str(self.project_root / "main.py"),
                "--config",
                str(runtime_config_path),
            ]

        if dry_run:
            command.append("--dry-run")

        return command

    def reset_progress(self):
        """
        Reset workflow progress bar before a new run.
        """
        self.progress_value.set(0.0)
        self.progress_text.set("Progress: 0% - waiting to start")

    def update_progress(self, percent: float, message: str):
        """
        Update workflow progress bar and progress text.
        """
        percent = max(0.0, min(100.0, float(percent)))
        self.progress_value.set(percent)
        self.progress_text.set(f"Progress: {percent:.0f}% - {message}")

    def handle_progress_message(self, message: str):
        """
        Parse progress messages emitted by main.py / pipeline.py.

        Expected format:
            __ROC_PROGRESS__|percent|message
        """
        try:
            _, percent_text, progress_message = message.split("|", 2)
            self.update_progress(float(percent_text), progress_message)
        except Exception:
            # If a malformed progress message is received, keep it in the log.
            self.write_log(message)

    def estimate_runtime_message(self, runtime_config_path: Path) -> str:
        """
        Estimate approximate runtime based on number of time scales, enabled
        methods, and enabled analysis steps.

        This is only a rough reminder for users. Actual runtime depends on
        computer performance, input data size, number of time scales, PWLF/KDE
        settings, and plotting.
        """
        try:
            with open(runtime_config_path, "r", encoding="utf-8") as file:
                config = yaml.safe_load(file) or {}

            widths = config.get("timebin", {}).get("widths_kyr", [])
            methods = config.get("methods", {})
            analysis = config.get("analysis", {})

            n_scales = len(widths)

            n_methods = 0
            n_methods += int(bool(methods.get("run_ibr", True)))
            n_methods += int(bool(methods.get("run_ts", True)))
            n_methods += int(bool(methods.get("run_iqr", True)))

            score = max(1, n_scales) * max(1, n_methods)

            if analysis.get("run_lri", True):
                score += 6
            if analysis.get("run_metrics", True):
                score += 4
            if analysis.get("run_pwlf", True):
                score += 10
            if analysis.get("run_kde", True):
                score += 4
            if analysis.get("run_phase", True):
                score += 4
            if analysis.get("run_plotting", True):
                score += 8

            if score <= 15:
                estimate = "usually less than 1–3 minutes"
            elif score <= 50:
                estimate = "usually about 3–10 minutes"
            elif score <= 90:
                estimate = "usually about 10–20 minutes"
            else:
                estimate = "may take more than 20 minutes"

            return (
                f"{estimate}. Actual runtime depends on computer performance, "
                f"input data size, number of time scales, PWLF/KDE settings, "
                f"and whether figures are generated."
            )

        except Exception:
            return (
                "runtime may range from a few minutes to more than 20 minutes, "
                "depending on data size, selected methods, and computer performance."
            )

    def _run_command(self, dry_run: bool):
        """
        Run main.py in a background thread.
        """
        try:
            runtime_config_path = self.build_runtime_config()
        except Exception as exc:
            messagebox.showerror(
                "Invalid GUI settings",
                f"Failed to build runtime config.\n\n"
                f"Error type: {type(exc).__name__}\n"
                f"Error message: {exc}",
            )
            return

        try:
            command = self.build_main_command(
                runtime_config_path=runtime_config_path,
                dry_run=dry_run,
            )
        except Exception as exc:
            messagebox.showerror(
                "Failed to build workflow command",
                f"Error type: {type(exc).__name__}\n"
                f"Error message: {exc}",
            )
            return

        self.notebook.select(self.run_tab)

        self.reset_progress()

        estimate_message = self.estimate_runtime_message(runtime_config_path)

        if dry_run:
            self.runtime_estimate_text.set(
                "Estimated run time: dry run usually finishes within a few seconds."
            )
        else:
            self.runtime_estimate_text.set(
                f"Estimated run time: {estimate_message}"
            )

        self.write_log("")
        self.write_log("=" * 80)
        self.write_log("Dry run started." if dry_run else "Workflow run started.")
        self.write_log("Estimated run time:")
        self.write_log(
            "  Dry run usually finishes within a few seconds."
            if dry_run
            else f"  {estimate_message}"
        )
        self.write_log("Runtime config:")
        self.write_log(f"  {runtime_config_path}")
        self.write_log("Input Excel:")
        self.write_log(f"  {self.input_excel_path.get()}")
        self.write_log("Output folder:")
        self.write_log(f"  {self.output_dir.get()}")

        try:
            with open(runtime_config_path, "r", encoding="utf-8") as file:
                runtime_config = yaml.safe_load(file) or {}

            runtime_methods = runtime_config.get("methods", {})
            self.write_log("Hidden IQR settings:")
            self.write_log(
                f"  IQR quartile method: "
                f"{runtime_methods.get('iqr_quartile_method', 'exc')}"
            )
            self.write_log(
                f"  IQR min count      : "
                f"{runtime_methods.get('iqr_min_count', 5)}"
            )
        except Exception:
            pass

        self.write_log("Command:")
        self.write_log(" ".join(command))
        self.write_log("=" * 80)

        self._set_running_state(True)

        worker = threading.Thread(
            target=self._process_worker,
            args=(command,),
            daemon=True,
        )
        worker.start()

    def _process_worker(self, command: list[str]):
        """
        Background worker for running the subprocess.
        """
        try:
            popen_kwargs = {}

            if os.name == "nt":
                popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

            self.current_process = subprocess.Popen(
                command,
                cwd=str(self.project_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding="utf-8",
                errors="replace",
                **popen_kwargs,
            )

            assert self.current_process.stdout is not None

            for line in self.current_process.stdout:
                self.log_queue.put(line.rstrip("\n"))

            return_code = self.current_process.wait()

            self.log_queue.put("=" * 80)

            if return_code == 0:
                self.log_queue.put("__ROC_PROGRESS__|100|Workflow completed successfully.")
                self.log_queue.put("Process completed successfully.")
            else:
                self.log_queue.put("__ROC_PROGRESS__|0|Workflow failed or was stopped.")
                self.log_queue.put(f"Process failed with return code: {return_code}")

            self.log_queue.put("=" * 80)

        except Exception as exc:
            self.log_queue.put("=" * 80)
            self.log_queue.put("GUI failed to run the workflow.")
            self.log_queue.put(f"Error type   : {type(exc).__name__}")
            self.log_queue.put(f"Error message: {exc}")
            self.log_queue.put("=" * 80)

        finally:
            self.current_process = None
            self.log_queue.put("__PROCESS_FINISHED__")

    def _poll_log_queue(self):
        """
        Periodically read log messages from the queue.
        """
        try:
            while True:
                message = self.log_queue.get_nowait()

                if message == "__PROCESS_FINISHED__":
                    self._set_running_state(False)
                    self.refresh_result_tree()
                elif message.startswith("__ROC_PROGRESS__|"):
                    self.handle_progress_message(message)
                else:
                    self.write_log(message)

        except queue.Empty:
            pass

        self.after(100, self._poll_log_queue)

    def _set_running_state(self, is_running: bool):
        """
        Enable or disable buttons depending on process state.
        """
        state_when_idle = tk.NORMAL if not is_running else tk.DISABLED
        state_when_running = tk.NORMAL if is_running else tk.DISABLED

        self.dry_run_button.config(state=state_when_idle)
        self.run_button.config(state=state_when_idle)
        self.stop_button.config(state=state_when_running)

    def stop_process(self):
        """
        Stop the currently running process.
        """
        if self.current_process is not None:
            self.write_log("Stopping current process...")
            self.current_process.terminate()

    # ======================================================================
    # Output opening and preview
    # ======================================================================
    def open_path(self, path: Path):
        """
        Open a file or folder using the operating system.
        """
        path = Path(path)

        if not path.exists():
            messagebox.showwarning(
                "Path not found",
                f"The path does not exist:\n{path}",
            )
            return

        try:
            if os.name == "nt":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            messagebox.showerror(
                "Failed to open path",
                f"Could not open:\n{path}\n\n{exc}",
            )

    def open_outputs(self):
        """
        Open output folder in file explorer.
        """
        output_path = Path(self.output_dir.get())

        if not output_path.exists():
            messagebox.showwarning(
                "Output folder not found",
                f"Output folder does not exist yet:\n{output_path}\n\n"
                "Run the workflow first to generate outputs.",
            )
            return

        self.open_path(output_path)

    def open_selected_result(self):
        """
        Open selected output file externally.
        """
        selected = self.result_tree.selection()

        if not selected:
            messagebox.showinfo("No file selected", "Please select a result file first.")
            return

        item_id = selected[0]
        path = self.result_tree_path_map.get(item_id)

        if path is None:
            return

        self.open_path(path)

    def refresh_result_tree(self):
        """
        Refresh output file tree while preserving expanded folders and selection.
        """
        if not hasattr(self, "result_tree"):
            return

        output_path = Path(self.output_dir.get())

        expanded_paths = self.get_expanded_result_paths()
        selected_path = self.get_selected_result_path()

        self.result_tree.delete(*self.result_tree.get_children())
        self.result_tree_path_map.clear()

        if not output_path.exists():
            root_id = self.result_tree.insert(
                "",
                "end",
                text=f"Output folder not found: {output_path}",
                open=True,
            )
            self.result_tree_path_map[root_id] = output_path
            return

        root_id = self._insert_result_node(
            parent="",
            path=output_path,
            expanded_paths=expanded_paths,
        )

        try:
            self.result_tree.item(root_id, open=True)
        except Exception:
            pass

        self.restore_selected_result_path(selected_path)

    def _insert_result_node(
            self,
            parent: str,
            path: Path,
            expanded_paths: set[str] | None = None,
    ) -> str:
        """
        Insert one file or directory into the result tree.

        Expanded folders are restored after automatic refresh.
        """
        if expanded_paths is None:
            expanded_paths = set()

        item_id = f"item_{len(self.result_tree_path_map)}"
        self.result_tree_path_map[item_id] = path

        text = path.name if path.name else str(path)

        try:
            path_key = str(path.resolve())
        except Exception:
            path_key = str(path)

        should_open = path.is_dir() and path_key in expanded_paths

        self.result_tree.insert(
            parent,
            "end",
            iid=item_id,
            text=text,
            open=should_open,
        )

        if path.is_dir():
            try:
                children = sorted(
                    path.iterdir(),
                    key=lambda p: (not p.is_dir(), p.name.lower()),
                )
            except PermissionError:
                children = []

            for child in children:
                if child.name in self.hidden_result_names:
                    continue

                self._insert_result_node(
                    parent=item_id,
                    path=child,
                    expanded_paths=expanded_paths,
                )

        return item_id

    def get_expanded_result_paths(self) -> set[str]:
        """
        Get paths of folders currently expanded in the result tree.
        """
        expanded_paths = set()

        if not hasattr(self, "result_tree"):
            return expanded_paths

        def visit(item_id: str):
            path = self.result_tree_path_map.get(item_id)

            if path is not None and path.is_dir():
                try:
                    if self.result_tree.item(item_id, "open"):
                        expanded_paths.add(str(path.resolve()))
                except Exception:
                    pass

            for child_id in self.result_tree.get_children(item_id):
                visit(child_id)

        for root_id in self.result_tree.get_children(""):
            visit(root_id)

        return expanded_paths

    def get_selected_result_path(self) -> Path | None:
        """
        Get the currently selected result path.
        """
        if not hasattr(self, "result_tree"):
            return None

        selected = self.result_tree.selection()

        if not selected:
            return None

        return self.result_tree_path_map.get(selected[0])

    def restore_selected_result_path(self, selected_path: Path | None):
        """
        Restore selected item after refreshing the result tree.
        """
        if selected_path is None:
            return

        try:
            selected_key = str(selected_path.resolve())
        except Exception:
            selected_key = str(selected_path)

        for item_id, path in self.result_tree_path_map.items():
            try:
                path_key = str(path.resolve())
            except Exception:
                path_key = str(path)

            if path_key == selected_key:
                self.result_tree.selection_set(item_id)
                self.result_tree.see(item_id)
                return

    def _auto_refresh_results(self):
        """
        Periodically refresh output file tree.
        """
        if hasattr(self, "result_tree"):
            try:
                self.refresh_result_tree()
            except Exception:
                pass

        self.after(3000, self._auto_refresh_results)

    def clear_preview(self):
        """
        Clear preview frame.
        """
        for widget in self.preview_frame.winfo_children():
            widget.destroy()

        self.preview_image_ref = None

    def show_text_preview(self, text: str):
        """
        Show text in preview panel with both vertical and horizontal scrollbars.
        """
        self.clear_preview()

        container = ttk.Frame(self.preview_frame)
        container.pack(fill=tk.BOTH, expand=True)

        text_widget = tk.Text(
            container,
            wrap=tk.NONE,
            font=self.mono_font,
        )

        y_scrollbar = ttk.Scrollbar(
            container,
            orient=tk.VERTICAL,
            command=text_widget.yview,
        )

        x_scrollbar = ttk.Scrollbar(
            container,
            orient=tk.HORIZONTAL,
            command=text_widget.xview,
        )

        text_widget.configure(
            yscrollcommand=y_scrollbar.set,
            xscrollcommand=x_scrollbar.set,
        )

        text_widget.grid(row=0, column=0, sticky="nsew")
        y_scrollbar.grid(row=0, column=1, sticky="ns")
        x_scrollbar.grid(row=1, column=0, sticky="ew")

        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)

        text_widget.insert(tk.END, text)
        text_widget.configure(state=tk.DISABLED)

    def show_image_preview(self, path: Path):
        """
        Show image in preview panel.
        """
        self.clear_preview()

        if Image is None or ImageTk is None:
            self.show_text_preview(
                "Image preview requires Pillow.\n\n"
                f"File:\n{path}\n\n"
                "You can open it externally with 'Open selected file'."
            )
            return

        try:
            image = Image.open(path)
            max_width = 850
            max_height = 620

            width, height = image.size
            scale = min(max_width / width, max_height / height, 1.0)

            new_size = (
                max(1, int(width * scale)),
                max(1, int(height * scale)),
            )

            image = image.resize(new_size)
            photo = ImageTk.PhotoImage(image)

            label = ttk.Label(self.preview_frame, image=photo)
            label.pack(anchor="center", expand=True)

            self.preview_image_ref = photo

        except Exception as exc:
            self.show_text_preview(
                f"Failed to preview image:\n{path}\n\n{exc}"
            )

    def preview_selected_result(self, event=None):
        """
        Preview selected output file.
        """
        selected = self.result_tree.selection()

        if not selected:
            return

        item_id = selected[0]
        path = self.result_tree_path_map.get(item_id)

        if path is None:
            return

        if path.is_dir():
            try:
                children = list(path.iterdir())
                message = [f"Directory: {path}", "", "Contents:"]
                message.extend(f"- {child.name}" for child in children[:300])

                if len(children) > 300:
                    message.append(f"... {len(children) - 300} more items")

                self.show_text_preview("\n".join(message))
            except Exception as exc:
                self.show_text_preview(f"Could not read directory:\n{path}\n\n{exc}")
            return

        suffix = path.suffix.lower()

        if suffix in [".png", ".jpg", ".jpeg"]:
            self.show_image_preview(path)
            return

        if suffix in [".svg"]:
            self.show_text_preview(
                "SVG preview is not embedded in this GUI.\n\n"
                f"File:\n{path}\n\n"
                "Use 'Open selected file' to view or edit it externally."
            )
            return

        if suffix in [".txt", ".log", ".yaml", ".yml", ".md", ".py"]:
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
                self.show_text_preview(text[:200000])
            except Exception as exc:
                self.show_text_preview(f"Could not read file:\n{path}\n\n{exc}")
            return

        if suffix in [".xlsx", ".xls", ".csv"]:
            try:
                import pandas as pd

                if suffix == ".csv":
                    table = pd.read_csv(path, nrows=100)
                else:
                    table = pd.read_excel(path, nrows=100)

                preview_text = (
                    f"File: {path}\n"
                    f"Preview: first {len(table)} rows\n\n"
                    f"{table.to_string(index=False)}"
                )
                self.show_text_preview(preview_text)

            except Exception as exc:
                self.show_text_preview(
                    f"Could not preview table:\n{path}\n\n{exc}"
                )
            return

        self.show_text_preview(
            f"No embedded preview is available for this file type.\n\n{path}\n\n"
            "Use 'Open selected file' to open it externally."
        )

    # ======================================================================
    # Log
    # ======================================================================
    def clear_log(self):
        """
        Clear log text.
        """
        self.log_text.delete("1.0", tk.END)

    def write_log(self, message: str):
        """
        Write one line to the log window.
        """
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)


def main():
    app = RoCGUI()
    app.mainloop()


if __name__ == "__main__":
    main()