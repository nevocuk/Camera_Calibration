"""
Stereo Kamera — Tam Pipeline Araci v4

Tek pencerede tum islemler:
  Tab 1: Ayarlar — cozunurluk, pozlama, gain, WB + canli degerler
  Tab 2: Hesaplama — deltaZ hesaplayici, calisma zarfi
  Tab 3: Kalibrasyon — desen tespiti, kare toplama, kalibre et
  Tab 4: Derinlik — canli disparity/derinlik haritasi
  Tab 5: Olcum — nesne olcumu + kutu onerisi
  Tab 6: Durum — pipeline durumu, olcum defteri
  Tab 7: Rehber — adim adim ne yapilacak
"""
import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import threading
import subprocess
import time
import os
import json
import math
import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
FRAMES_DIR = os.path.join(PROJECT_DIR, "calibration", "frames")
CONFIG_PATH = os.path.join(PROJECT_DIR, "data", "charuco_config.json")
CALIB_PATH = os.path.join(PROJECT_DIR, "calibration", "calib_result.npz")
GROUND_PATH = os.path.join(PROJECT_DIR, "calibration", "ground_plane.npz")
DIARY_PATH = os.path.join(PROJECT_DIR, "data", "olcum_defteri.csv")
SETTINGS_PATH = os.path.join(PROJECT_DIR, "data", "camera_settings.json")
os.makedirs(FRAMES_DIR, exist_ok=True)

RESOLUTIONS = [
    ("640x480 ~30fps", 640, 480, "MJPG"),
    ("800x600 ~30fps", 800, 600, "MJPG"),
    ("1024x768 ~30fps", 1024, 768, "MJPG"),
    ("1280x720 ~30fps", 1280, 720, "MJPG"),
    ("1280x960 ~30fps", 1280, 960, "MJPG"),
    ("1920x1080 ~30fps", 1920, 1080, "MJPG"),
    ("2048x1536 ~30fps", 2048, 1536, "MJPG"),
    ("3840x2160 ~1fps (sadece 4K foto)", 3840, 2160, "MJPG"),
]

# Renkler
BG = "#1e1e2e"
CARD = "#262637"
BORDER = "#3a3a5c"
FG = "#d4d4e8"
ACCENT = "#7aa2f7"
GREEN = "#9ece6a"
YELLOW = "#e0af68"
RED = "#f7768e"
MUTED = "#636882"
INPUT_BG = "#1a1a2a"


def load_charuco():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
    else:
        cfg = {"squares_x": 7, "squares_y": 5, "square_length_mm": 30,
               "marker_length_mm": 22, "aruco_dict": "DICT_5X5_50"}
    aruco_dict = cv2.aruco.getPredefinedDictionary(
        getattr(cv2.aruco, cfg["aruco_dict"]))
    sq = cfg.get("olculen_kare_boyutu_mm") or cfg["square_length_mm"]
    mk = cfg["marker_length_mm"] * sq / cfg["square_length_mm"]
    board_type = cfg.get("board_type", "charuco")

    if board_type == "grid":
        cols, rows = cfg["squares_x"], cfg["squares_y"]
        ids_arr = np.array([(cols - 1 - c) * rows + r
                            for r in range(rows) for c in range(cols)],
                           dtype=np.int32)
        sep = (sq - mk) / 1000.0
        board = cv2.aruco.GridBoard(
            (cols, rows), mk / 1000.0, sep, aruco_dict, ids_arr)
        params = cv2.aruco.DetectorParameters()
        if cfg["aruco_dict"].startswith("DICT_APRILTAG"):
            params.adaptiveThreshWinSizeMax = 73
            params.adaptiveThreshWinSizeStep = 2
        detector = cv2.aruco.ArucoDetector(aruco_dict, params)
        max_corners = cols * rows
    else:
        board = cv2.aruco.CharucoBoard(
            (cfg["squares_x"], cfg["squares_y"]),
            sq / 1000.0, mk / 1000.0, aruco_dict)
        use_legacy = not cfg["aruco_dict"].startswith("DICT_APRILTAG")
        if use_legacy:
            board.setLegacyPattern(True)
        params = cv2.aruco.DetectorParameters()
        params.adaptiveThreshWinSizeMax = 73
        params.adaptiveThreshWinSizeStep = 2
        charuco_params = cv2.aruco.CharucoParameters()
        detector = cv2.aruco.CharucoDetector(board, charuco_params,
                                              params)
        max_corners = (cfg["squares_x"] - 1) * (cfg["squares_y"] - 1)

    return board, detector, max_corners, cfg


class SpinSlider(tk.Frame):
    """Slider + sayi girisi birlikte."""
    def __init__(self, parent, label, var, from_, to_, command,
                 resolution=1, width_label=16, **kw):
        super().__init__(parent, bg=CARD)
        self.var = var
        self.cmd = command
        self.res = resolution

        tk.Label(self, text=label, bg=CARD, fg=FG,
                 font=("Segoe UI", 10), width=width_label,
                 anchor="w").pack(side=tk.LEFT, padx=(0, 4))

        self.scale = tk.Scale(self, from_=from_, to=to_, orient=tk.HORIZONTAL,
                               variable=var, resolution=resolution, showvalue=False,
                               bg=CARD, fg=ACCENT, troughcolor="#3a3a5c",
                               activebackground="#9dc0ff",
                               highlightthickness=0, sliderrelief="raised",
                               sliderlength=24, width=18, length=140,
                               command=self._on_scale)
        self.scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

        self.entry = tk.Entry(self, width=6, bg=INPUT_BG, fg=YELLOW,
                               font=("Consolas", 11, "bold"),
                               insertbackground=YELLOW, borderwidth=1,
                               relief="flat", justify="center")
        self.entry.pack(side=tk.LEFT, padx=(4, 0))
        self.entry.insert(0, str(var.get()))
        self.entry.bind("<Return>", self._on_entry)
        self.entry.bind("<FocusOut>", self._on_entry)

    def _on_scale(self, val):
        self.entry.delete(0, tk.END)
        if self.res >= 1:
            self.entry.insert(0, str(int(float(val))))
        else:
            self.entry.insert(0, f"{float(val):.2f}")
        self.cmd()

    def _on_entry(self, event=None):
        try:
            v = float(self.entry.get())
            self.var.set(v)
            self.cmd()
        except ValueError:
            pass


class CameraApp:
    def __init__(self, root, left_idx, right_idx):
        self.root = root
        self.root.title("Stereo Kamera — Kalibrasyon Hazirlama")
        self.root.configure(bg=BG)
        self.root.geometry("1500x850")
        self.root.minsize(1100, 650)

        self.left_idx = left_idx
        self.right_idx = right_idx
        self.cap_l = None
        self.cap_r = None
        self.running = False
        self.lock = threading.Lock()

        self.fps = 0.0
        self.score_l = 0.0
        self.score_r = 0.0
        self.frame_l = None
        self.frame_r = None
        self.display_frame_l = None
        self.display_frame_r = None
        self.save_count = len([f for f in os.listdir(FRAMES_DIR) if f.startswith("L_")])

        self.board, self.detector, self.max_corners, self.charuco_cfg = load_charuco()
        self.calib_mode = False
        self.corners_l = 0
        self.corners_r = 0
        self.current_w = 640
        self.current_h = 480
        self.bright_l = 0.0
        self.bright_r = 0.0
        self.peak_l = 0.0
        self.peak_r = 0.0

        # GPU destegi
        try:
            self._use_gpu = cv2.cuda.getCudaEnabledDeviceCount() > 0
        except Exception:
            self._use_gpu = False

        # Derinlik/olcum state
        self.depth_mode = False
        self.calib_data = None
        self.ground_data = None
        self.map1x = self.map1y = self.map2x = self.map2y = None
        self.stereo = None
        self.bg_frame_l = None
        self.measure_result = None

        self._load_settings()
        self._build_ui()
        self._open_cameras()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        main = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, bg=BG,
                              sashwidth=5, sashrelief=tk.FLAT)
        main.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # Sol: kamera
        cam_container = tk.Frame(main, bg="#000")
        main.add(cam_container, stretch="always")
        self.cam_label = tk.Label(cam_container, bg="#000")
        self.cam_label.pack(fill=tk.BOTH, expand=True)

        # Status bar
        self.status_bar = tk.Label(cam_container, text="", bg=CARD, fg=FG,
                                    font=("Consolas", 10), anchor="w", padx=8, pady=6)
        self.status_bar.pack(fill=tk.X)

        # Sag: panel
        panel = tk.Frame(main, bg=BG, width=420)
        main.add(panel, stretch="never")

        style = ttk.Style()
        style.theme_use("default")
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=CARD, foreground=FG,
                         padding=[14, 8], font=("Segoe UI", 10))
        style.map("TNotebook.Tab",
                   background=[("selected", BORDER)],
                   foreground=[("selected", ACCENT)])
        style.configure("TCombobox", fieldbackground=INPUT_BG, background=CARD,
                         foreground=FG, selectbackground=BORDER,
                         selectforeground=FG, arrowcolor=FG)
        style.map("TCombobox",
                   fieldbackground=[("readonly", INPUT_BG), ("focus", INPUT_BG)],
                   foreground=[("readonly", FG), ("focus", FG)],
                   selectbackground=[("readonly", BORDER)],
                   selectforeground=[("readonly", FG)])
        self.root.option_add("*TCombobox*Listbox.background", INPUT_BG)
        self.root.option_add("*TCombobox*Listbox.foreground", FG)
        self.root.option_add("*TCombobox*Listbox.selectBackground", BORDER)
        self.root.option_add("*TCombobox*Listbox.selectForeground", ACCENT)

        self.notebook = ttk.Notebook(panel)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self._build_tab_settings()
        self._build_tab_requirements()
        self._build_tab_calibration()
        self._build_tab_depth()
        self._build_tab_measure()
        self._build_tab_status()
        self._build_tab_guide()

    def _section(self, parent, title):
        f = tk.Frame(parent, bg=CARD)
        f.pack(fill=tk.X, padx=8, pady=(10, 0))
        tk.Label(f, text=title, bg=CARD, fg=ACCENT,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w")
        tk.Frame(f, bg=BORDER, height=1).pack(fill=tk.X, pady=(4, 0))
        content = tk.Frame(parent, bg=CARD)
        content.pack(fill=tk.X, padx=8, pady=(4, 0))
        return content

    def _info_row(self, parent, label, value="", color=FG):
        row = tk.Frame(parent, bg=CARD)
        row.pack(fill=tk.X, pady=2)
        tk.Label(row, text=label, bg=CARD, fg=MUTED,
                 font=("Segoe UI", 10), anchor="w").pack(side=tk.LEFT)
        lbl = tk.Label(row, text=value, bg=CARD, fg=color,
                        font=("Consolas", 11, "bold"), anchor="e")
        lbl.pack(side=tk.RIGHT)
        return lbl

    # ── Tab: Ayarlar ──────────────────────────────────
    def _build_tab_settings(self):
        tab = tk.Frame(self.notebook, bg=CARD)
        self.notebook.add(tab, text="  Ayarlar  ")

        canvas = tk.Canvas(tab, bg=CARD, highlightthickness=0)
        scrollbar = tk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        sf = tk.Frame(canvas, bg=CARD)
        sf.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=sf, anchor="nw", tags="sf")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig("sf", width=e.width))
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sf.bind("<MouseWheel>", lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))
        canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))

        # Cozunurluk
        c = self._section(sf, "Cozunurluk / Format")
        self.res_var = tk.StringVar(value=RESOLUTIONS[6][0])
        combo_f = tk.Frame(c, bg=CARD)
        combo_f.pack(fill=tk.X, pady=4)
        self.res_combo = ttk.Combobox(combo_f, textvariable=self.res_var,
                                       values=[r[0] for r in RESOLUTIONS],
                                       state="readonly", width=30,
                                       font=("Segoe UI", 10))
        self.res_combo.pack(side=tk.LEFT)
        self.res_combo.bind("<<ComboboxSelected>>", self._on_resolution_change)

        self.lbl_cam_idx = self._info_row(c, "Kamera",
            f"SOL=idx {self.left_idx}  SAG=idx {self.right_idx}")

        btn_row = tk.Frame(c, bg=CARD)
        btn_row.pack(fill=tk.X, pady=4)
        tk.Button(btn_row, text="SOL/SAG Degistir", command=self._swap_cameras,
                  bg=BORDER, fg=FG, font=("Segoe UI", 9, "bold"),
                  relief="flat", padx=10, pady=4, cursor="hand2").pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(btn_row, text="Ayarlari Kaydet", command=self._save_settings,
                  bg="#2d6a4f", fg="white", font=("Segoe UI", 9, "bold"),
                  relief="flat", padx=10, pady=4, cursor="hand2").pack(side=tk.LEFT)

        tk.Label(c, text=(
            "Dogrulama: Sol elinizi kaldir.\n"
            "Ekranda SOL tarafta gorunmeli.\n"
            "Tersse 'SOL/SAG Degistir' tikla + Kaydet."
        ), bg=CARD, fg=MUTED, font=("Segoe UI", 9),
                 justify="left").pack(fill=tk.X, pady=(4, 0))

        # Kamera ayarlari
        c = self._section(sf, "Kamera ayarlari (ortak)")
        self.exposure_var = tk.IntVar(value=-4)
        self.gain_var = tk.IntVar(value=0)
        self.wb_var = tk.IntVar(value=4500)
        SpinSlider(c, "Pozlama", self.exposure_var, -13, 0,
                    self._on_exposure).pack(fill=tk.X, pady=2)
        SpinSlider(c, "Gain", self.gain_var, 0, 100,
                    self._on_gain).pack(fill=tk.X, pady=2)
        SpinSlider(c, "Beyaz dengesi", self.wb_var, 2000, 7000,
                    self._on_wb).pack(fill=tk.X, pady=2)

        # SAG kamera telafi
        c = self._section(sf, "SAG kamera telafisi")
        tk.Label(c, text="Sol kameranin degerine eklenir",
                 bg=CARD, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w")
        self.exp_offset_r = tk.IntVar(value=1)
        self.gain_offset_r = tk.DoubleVar(value=0)
        self.bright_offset_r = tk.IntVar(value=0)
        SpinSlider(c, "Pozlama telafi", self.exp_offset_r, -5, 5,
                    self._on_exposure, resolution=1).pack(fill=tk.X, pady=2)
        SpinSlider(c, "Gain telafi", self.gain_offset_r, -30, 30,
                    self._on_gain, resolution=1).pack(fill=tk.X, pady=2)
        SpinSlider(c, "Parlaklik telafi", self.bright_offset_r, -30, 30,
                    self._on_bright_offset, resolution=1).pack(fill=tk.X, pady=2)

        # Goruntu
        c = self._section(sf, "Goruntu")
        self.brightness_var = tk.IntVar(value=0)
        self.contrast_var = tk.IntVar(value=32)
        self.saturation_var = tk.IntVar(value=64)
        self.sharpness_var = tk.IntVar(value=3)
        SpinSlider(c, "Parlaklik", self.brightness_var, -64, 64,
                    self._on_img_prop).pack(fill=tk.X, pady=2)
        SpinSlider(c, "Kontrast", self.contrast_var, 0, 100,
                    self._on_img_prop).pack(fill=tk.X, pady=2)
        SpinSlider(c, "Doygunluk", self.saturation_var, 0, 128,
                    self._on_img_prop).pack(fill=tk.X, pady=2)
        SpinSlider(c, "Keskinlik", self.sharpness_var, 0, 10,
                    self._on_img_prop).pack(fill=tk.X, pady=2)

        # Canli degerler
        c = self._section(sf, "Canli degerler")
        self.lbl_fps = self._info_row(c, "FPS")
        self.lbl_net_l = self._info_row(c, "Netlik SOL")
        self.lbl_net_r = self._info_row(c, "Netlik SAG")
        self.lbl_net_peak_l = self._info_row(c, "Tepe SOL")
        self.lbl_net_peak_r = self._info_row(c, "Tepe SAG")
        self.lbl_bright_l = self._info_row(c, "Parlaklik SOL")
        self.lbl_bright_r = self._info_row(c, "Parlaklik SAG")
        self.lbl_bright_diff = self._info_row(c, "Fark %")
        self.lbl_res_active = self._info_row(c, "Cozunurluk")
        self.lbl_format = self._info_row(c, "Format")

    # ── Tab: Gereksinimler ────────────────────────────
    def _build_tab_requirements(self):
        tab = tk.Frame(self.notebook, bg=CARD)
        self.notebook.add(tab, text="  Hesaplama  ")

        canvas = tk.Canvas(tab, bg=CARD, highlightthickness=0)
        scrollbar = tk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        sf = tk.Frame(canvas, bg=CARD)
        sf.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=sf, anchor="nw", tags="sf")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig("sf", width=e.width))
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sf.bind("<MouseWheel>", lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))
        canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))

        c = self._section(sf, "Calisma mesafesi")
        self.z_min_var = tk.IntVar(value=300)
        self.z_max_var = tk.IntVar(value=900)
        SpinSlider(c, "Z min (mm)", self.z_min_var, 100, 1000,
                    self._calc_dz).pack(fill=tk.X, pady=2)
        SpinSlider(c, "Z max (mm)", self.z_max_var, 200, 2000,
                    self._calc_dz).pack(fill=tk.X, pady=2)

        c = self._section(sf, "Hedef hassasiyet")
        self.target_var = tk.DoubleVar(value=3.0)
        SpinSlider(c, "Hedef (mm)", self.target_var, 0.5, 20,
                    self._calc_dz, resolution=0.5).pack(fill=tk.X, pady=2)

        c = self._section(sf, "Sistem parametreleri")
        self.baseline_var = tk.IntVar(value=72)
        self.fpx_var = tk.IntVar(value=800)
        self.dd_var = tk.DoubleVar(value=0.35)
        SpinSlider(c, "Baseline (mm)", self.baseline_var, 10, 300,
                    self._calc_dz).pack(fill=tk.X, pady=2)
        SpinSlider(c, "f piksel", self.fpx_var, 100, 5000,
                    self._calc_dz).pack(fill=tk.X, pady=2)
        SpinSlider(c, "delta_d (px)", self.dd_var, 0.1, 1.0,
                    self._calc_dz, resolution=0.05).pack(fill=tk.X, pady=2)

        c = self._section(sf, "Sonuclar")
        self.lbl_dz_min = self._info_row(c, "deltaZ @ Z_min")
        self.lbl_dz_max = self._info_row(c, "deltaZ @ Z_max")
        self.lbl_z_limit = self._info_row(c, "Maks mesafe (hedef icinde)")
        self.lbl_verdict = self._info_row(c, "Durum")

        c = self._section(sf, "Bilgi")
        tk.Label(c, text=(
            "deltaZ = Z^2 * delta_d / (f_px * B)\n\n"
            "Baseline: kumpasla olc, kalibrasyondan\n"
            "sonra ||T|| ile dogrula.\n\n"
            "f_px: kalibrasyondan gelecek (K matrisi).\n"
            "Simdi tahmini deger gir, sonra guncelle.\n\n"
            "delta_d: eslesme belirsizligi.\n"
            "Tekrarlanabilirlik testinden gelecek (5.3)."
        ), bg=CARD, fg=MUTED, font=("Segoe UI", 9),
                 justify="left", anchor="nw").pack(fill=tk.X, pady=4)

        self._calc_dz()

    def _calc_dz(self, *_):
        z_min = self.z_min_var.get()
        z_max = self.z_max_var.get()
        f = self.fpx_var.get()
        b = self.baseline_var.get()
        dd = self.dd_var.get()
        target = self.target_var.get()
        if f <= 0 or b <= 0 or dd <= 0:
            return

        dz_min = (z_min**2 * dd) / (f * b)
        dz_max = (z_max**2 * dd) / (f * b)
        z_limit = math.sqrt(target * f * b / dd)

        self.lbl_dz_min.config(text=f"{dz_min:.2f} mm",
                                fg=GREEN if dz_min <= target else RED)
        self.lbl_dz_max.config(text=f"{dz_max:.2f} mm",
                                fg=GREEN if dz_max <= target else RED)
        self.lbl_z_limit.config(text=f"{z_limit:.0f} mm ({z_limit/10:.0f} cm)")
        if dz_max <= target:
            self.lbl_verdict.config(text="Tum aralik uygun", fg=GREEN)
        elif dz_min <= target:
            self.lbl_verdict.config(text=f"{z_limit:.0f} mm'ye kadar OK", fg=YELLOW)
        else:
            self.lbl_verdict.config(text="Yetersiz!", fg=RED)

    # ── Tab: Kalibrasyon ──────────────────────────────
    def _build_tab_calibration(self):
        tab = tk.Frame(self.notebook, bg=CARD)
        self.notebook.add(tab, text="  Kalibrasyon  ")

        cfg = self.charuco_cfg
        btype = cfg.get("board_type", "charuco")

        c = self._section(tab, "Board ayarlari")
        self._board_cfg_locked = True

        board_fields = tk.Frame(c, bg=CARD)
        board_fields.pack(fill=tk.X, pady=2)

        fields = [
            ("Tip", "board_type", ["grid", "charuco"], 10),
            ("Sutun", "squares_x", None, 5),
            ("Satir", "squares_y", None, 5),
            ("Pitch mm", "square_length_mm", None, 6),
            ("Marker mm", "marker_length_mm", None, 6),
            ("Sozluk", "aruco_dict", [
                "DICT_APRILTAG_36h11", "DICT_4X4_50", "DICT_4X4_100",
                "DICT_5X5_50", "DICT_5X5_100", "DICT_6X6_50"
            ], 22),
        ]
        self._board_entries = {}
        for i, (label, key, options, width) in enumerate(fields):
            row = tk.Frame(board_fields, bg=CARD)
            row.pack(fill=tk.X, pady=1)
            tk.Label(row, text=f"{label}:", bg=CARD, fg=MUTED,
                     font=("Segoe UI", 9), width=10, anchor="w").pack(side=tk.LEFT)
            if options:
                var = tk.StringVar(value=str(cfg.get(key, options[0])))
                w = ttk.Combobox(row, textvariable=var, values=options,
                                 width=width, state="disabled")
                w.pack(side=tk.LEFT, padx=4)
                self._board_entries[key] = (w, var)
            else:
                e = tk.Entry(row, width=width, bg=INPUT_BG, fg=FG,
                             font=("Consolas", 10), insertbackground=FG,
                             borderwidth=1, relief="flat", justify="center",
                             state="disabled")
                e.pack(side=tk.LEFT, padx=4)
                e.config(state="normal")
                e.insert(0, str(cfg.get(key, "")))
                e.config(state="disabled")
                self._board_entries[key] = (e, None)

        btype_label = "AprilTag Grid" if btype == "grid" else "ChArUco"
        total = cfg["squares_x"] * cfg["squares_y"] if btype == "grid" else \
                (cfg["squares_x"] - 1) * (cfg["squares_y"] - 1)
        unit = "marker" if btype == "grid" else "kose"
        self._board_info = tk.Label(c, text=f"{btype_label} | {total} {unit}",
                                     bg=CARD, fg=ACCENT, font=("Segoe UI", 9, "bold"))
        self._board_info.pack(fill=tk.X, pady=2)

        btn_row_board = tk.Frame(c, bg=CARD)
        btn_row_board.pack(fill=tk.X, pady=4)
        self.btn_board_edit = tk.Button(
            btn_row_board, text="Ayarlari Degistir",
            command=self._unlock_board_cfg,
            bg=BORDER, fg=FG, font=("Segoe UI", 9),
            relief="flat", padx=10, pady=2, cursor="hand2")
        self.btn_board_edit.pack(side=tk.LEFT, padx=4)
        self.btn_board_apply = tk.Button(
            btn_row_board, text="Uygula & Kilitle",
            command=self._apply_board_cfg,
            bg="#2d6a4f", fg="white", font=("Segoe UI", 9, "bold"),
            relief="flat", padx=10, pady=2, cursor="hand2",
            state="disabled")
        self.btn_board_apply.pack(side=tk.LEFT, padx=4)
        self.btn_board_cancel = tk.Button(
            btn_row_board, text="Iptal",
            command=self._cancel_board_cfg,
            bg="#9d0208", fg="white", font=("Segoe UI", 9),
            relief="flat", padx=8, pady=2, cursor="hand2",
            state="disabled")
        self.btn_board_cancel.pack(side=tk.LEFT, padx=2)

        c = self._section(tab, "Olculen pitch boyutu")
        sq = cfg.get("olculen_kare_boyutu_mm")

        row_sq = tk.Frame(c, bg=CARD)
        row_sq.pack(fill=tk.X, pady=2)
        tk.Label(row_sq, text="Kumpasla olculen (mm):", bg=CARD, fg=FG,
                 font=("Segoe UI", 10), anchor="w").pack(side=tk.LEFT)
        self.sq_entry = tk.Entry(row_sq, width=8, bg=INPUT_BG, fg=YELLOW,
                                  font=("Consolas", 12, "bold"),
                                  insertbackground=YELLOW, borderwidth=1,
                                  relief="flat", justify="center")
        self.sq_entry.pack(side=tk.LEFT, padx=8)
        if sq:
            self.sq_entry.insert(0, str(sq))
        self.sq_locked = True if sq else False
        self.sq_status = tk.Label(row_sq, text="", bg=CARD,
                                   font=("Segoe UI", 10, "bold"))
        self.sq_status.pack(side=tk.LEFT, padx=4)

        self.btn_sq_save = tk.Button(row_sq, text="Kaydet & Kilitle",
                            command=self._save_sq,
                            bg="#2d6a4f", fg="white", font=("Segoe UI", 9, "bold"),
                            relief="flat", padx=10, pady=2, cursor="hand2")
        self.btn_sq_save.pack(side=tk.LEFT, padx=4)

        self.btn_sq_unlock = tk.Button(row_sq, text="Kilidi Ac",
                            command=self._unlock_sq,
                            bg="#9d0208", fg="white", font=("Segoe UI", 9),
                            relief="flat", padx=8, pady=2, cursor="hand2")
        self.btn_sq_unlock.pack(side=tk.LEFT, padx=2)

        self._update_sq_status()
        if self.sq_locked:
            self.sq_entry.config(state="disabled")
            self.btn_sq_save.config(state="disabled")

        c = self._section(tab, "Kontrol")
        btn_frame = tk.Frame(c, bg=CARD)
        btn_frame.pack(fill=tk.X, pady=6)

        self.btn_calib = tk.Button(btn_frame, text="Kalibrasyon KAPALI",
                                    command=self._toggle_calib,
                                    bg=BORDER, fg=FG, font=("Segoe UI", 10, "bold"),
                                    relief="flat", padx=14, pady=6, cursor="hand2")
        self.btn_calib.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_save = tk.Button(btn_frame, text="Kaydet [S]",
                                   command=self._save_frame,
                                   bg="#2d6a4f", fg="white",
                                   font=("Segoe UI", 10, "bold"),
                                   relief="flat", padx=14, pady=6, cursor="hand2")
        self.btn_save.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_del = tk.Button(btn_frame, text="Son sil",
                                  command=self._delete_last,
                                  bg="#9d0208", fg="white",
                                  font=("Segoe UI", 10),
                                  relief="flat", padx=10, pady=6, cursor="hand2")
        self.btn_del.pack(side=tk.LEFT)

        btn_frame2 = tk.Frame(c, bg=CARD)
        btn_frame2.pack(fill=tk.X, pady=4)
        self.auto_capture = False
        self._last_auto_corners = None
        self._auto_cooldown = 0
        self.btn_auto = tk.Button(btn_frame2, text="Otomatik Cekim: KAPALI",
                                   command=self._toggle_auto_capture,
                                   bg=BORDER, fg=FG, font=("Segoe UI", 10, "bold"),
                                   relief="flat", padx=14, pady=6, cursor="hand2")
        self.btn_auto.pack(side=tk.LEFT)
        tk.Label(btn_frame2, text="  (board hareket edince otomatik ceker)",
                 bg=CARD, fg=MUTED, font=("Segoe UI", 9)).pack(side=tk.LEFT)

        c = self._section(tab, "Durum")
        self.lbl_saved = self._info_row(c, "Kaydedilen", f"{self.save_count} cift")
        self.lbl_corners_l = self._info_row(c, "Kose SOL", "--")
        self.lbl_corners_r = self._info_row(c, "Kose SAG", "--")

        c = self._section(tab, "Set Yonetimi")
        set_row = tk.Frame(c, bg=CARD)
        set_row.pack(fill=tk.X, pady=4)
        self.btn_new_set = tk.Button(
            set_row, text="Yeni Set Baslat",
            command=self._new_calib_set,
            bg=BORDER, fg=FG, font=("Segoe UI", 9, "bold"),
            relief="flat", padx=10, pady=4, cursor="hand2")
        self.btn_new_set.pack(side=tk.LEFT, padx=(0, 6))
        self.btn_load_set = tk.Button(
            set_row, text="Eski Seti Yukle",
            command=self._load_calib_set,
            bg=BORDER, fg=FG, font=("Segoe UI", 9, "bold"),
            relief="flat", padx=10, pady=4, cursor="hand2")
        self.btn_load_set.pack(side=tk.LEFT)
        self.lbl_set_info = tk.Label(c, text="", bg=CARD, fg=MUTED,
                                     font=("Segoe UI", 9))
        self.lbl_set_info.pack(fill=tk.X, pady=2)
        self._update_set_info()

        c = self._section(tab, "Kalibre Et")
        btn_frame3 = tk.Frame(c, bg=CARD)
        btn_frame3.pack(fill=tk.X, pady=4)
        self.btn_run_calib = tk.Button(
            btn_frame3, text="Kalibrasyonu Baslat",
            command=self._run_calibration,
            bg="#7aa2f7", fg="white", font=("Segoe UI", 10, "bold"),
            relief="flat", padx=14, pady=6, cursor="hand2")
        self.btn_run_calib.pack(side=tk.LEFT, padx=(0, 6))
        self.lbl_calib_status = tk.Label(btn_frame3, text="",
                                          bg=CARD, fg=MUTED, font=("Segoe UI", 9))
        self.lbl_calib_status.pack(side=tk.LEFT)

        c = self._section(tab, "Cekim rehberi")
        tk.Label(c, text=(
            "Hedef: 25-40 gecerli cift\n\n"
            "3x3 grid kapsama:\n"
            " [sol-ust] [orta-ust] [sag-ust]\n"
            " [sol-ort] [merkez ] [sag-ort]\n"
            " [sol-alt] [orta-alt] [sag-alt]\n\n"
            "Her bolgede 2-3 kare.\n"
            "Egim: +/-30-45 derece pitch/yaw\n"
            "Mesafe: yakin + orta + uzak\n"
            "Birkac karede tahtayi dondur\n\n"
            "Yesil cerceve = yeterli kose\n"
            "Iki kamerada da gorunmeli"
        ), bg=CARD, fg=MUTED, font=("Segoe UI", 9),
                 justify="left").pack(fill=tk.X, pady=4)

        def _key_if_not_entry(action):
            def handler(e):
                if not isinstance(e.widget, tk.Entry):
                    action()
            return handler
        self.root.bind("<s>", _key_if_not_entry(self._save_frame))
        self.root.bind("<S>", _key_if_not_entry(self._save_frame))
        self.root.bind("<c>", _key_if_not_entry(self._toggle_calib))
        self.root.bind("<C>", _key_if_not_entry(self._toggle_calib))
        self.root.bind("<Escape>", lambda e: self._on_close())

    def _unlock_board_cfg(self):
        if not messagebox.askyesno(
                "Board Ayarlari",
                "Board ayarlarini degistirmek mevcut kalibrasyonu gecersiz kilar.\n"
                "Devam etmek istiyor musun?"):
            return
        self._board_cfg_locked = False
        for key, (widget, var) in self._board_entries.items():
            if var is not None:
                widget.config(state="readonly")
            else:
                widget.config(state="normal")
        self.btn_board_edit.config(state="disabled")
        self.btn_board_apply.config(state="normal")
        self.btn_board_cancel.config(state="normal")

    def _apply_board_cfg(self):
        try:
            new_cfg = {}
            w_type, v_type = self._board_entries["board_type"]
            new_cfg["board_type"] = v_type.get()
            new_cfg["squares_x"] = int(self._board_entries["squares_x"][0].get())
            new_cfg["squares_y"] = int(self._board_entries["squares_y"][0].get())
            new_cfg["square_length_mm"] = float(self._board_entries["square_length_mm"][0].get())
            new_cfg["marker_length_mm"] = float(self._board_entries["marker_length_mm"][0].get())
            w_dict, v_dict = self._board_entries["aruco_dict"]
            new_cfg["aruco_dict"] = v_dict.get()
        except (ValueError, KeyError):
            messagebox.showerror("Hata", "Gecersiz deger! Sayilari kontrol et.")
            return

        config_path = os.path.join(PROJECT_DIR, "data", "charuco_config.json")
        with open(config_path, encoding="utf-8") as f:
            cfg = json.load(f)
        cfg.update(new_cfg)
        cfg["olculen_kare_boyutu_mm"] = None
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)

        self.charuco_cfg = cfg
        self.board, self.detector, self.max_corners, self.charuco_cfg = load_charuco()
        self._lock_board_cfg()

        btype = cfg.get("board_type", "charuco")
        btype_label = "AprilTag Grid" if btype == "grid" else "ChArUco"
        total = cfg["squares_x"] * cfg["squares_y"] if btype == "grid" else \
                (cfg["squares_x"] - 1) * (cfg["squares_y"] - 1)
        unit = "marker" if btype == "grid" else "kose"
        self._board_info.config(text=f"{btype_label} | {total} {unit}")

        self.sq_entry.config(state="normal")
        self.sq_entry.delete(0, tk.END)
        self.sq_entry.config(state="disabled") if self.sq_locked else None
        self.sq_locked = False
        self.btn_sq_save.config(state="normal")
        self._update_sq_status()

    def _cancel_board_cfg(self):
        cfg = self.charuco_cfg
        for key, (widget, var) in self._board_entries.items():
            if var is not None:
                var.set(str(cfg.get(key, "")))
            else:
                widget.config(state="normal")
                widget.delete(0, tk.END)
                widget.insert(0, str(cfg.get(key, "")))
        self._lock_board_cfg()

    def _lock_board_cfg(self):
        self._board_cfg_locked = True
        for key, (widget, var) in self._board_entries.items():
            widget.config(state="disabled")
        self.btn_board_edit.config(state="normal")
        self.btn_board_apply.config(state="disabled")
        self.btn_board_cancel.config(state="disabled")

    def _update_sq_status(self):
        val = self.sq_entry.get().strip()
        if not val:
            self.sq_status.config(text="GIRILMEDI — kumpasla olc", fg=RED)
        else:
            try:
                v = float(val)
                design = self.charuco_cfg["square_length_mm"]
                if abs(v - design) <= design * 0.5:
                    status = f"{v} mm OK" + (" KILITLI" if self.sq_locked else "")
                    self.sq_status.config(text=status, fg=GREEN)
                else:
                    self.sq_status.config(text=f"Tasarimdan cok farkli ({design}mm)!", fg=YELLOW)
            except ValueError:
                self.sq_status.config(text="Gecersiz!", fg=RED)

    def _save_sq(self):
        val = self.sq_entry.get().strip()
        try:
            v = float(val)
        except ValueError:
            self.sq_status.config(text="Gecersiz sayi!", fg=RED)
            return
        config_path = os.path.join(PROJECT_DIR, "data", "charuco_config.json")
        with open(config_path, encoding="utf-8") as f:
            cfg = json.load(f)
        cfg["olculen_kare_boyutu_mm"] = v
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        self.charuco_cfg["olculen_kare_boyutu_mm"] = v
        self.sq_locked = True
        self.sq_entry.config(state="disabled")
        self.btn_sq_save.config(state="disabled")
        self._update_sq_status()

    def _unlock_sq(self):
        self.sq_locked = False
        self.sq_entry.config(state="normal")
        self.btn_sq_save.config(state="normal")
        self._update_sq_status()

    def _update_set_info(self):
        calib_dir = os.path.dirname(FRAMES_DIR)
        sets = sorted([d for d in os.listdir(calib_dir)
                       if d.startswith("frames_set_") and
                       os.path.isdir(os.path.join(calib_dir, d))])
        current = len([f for f in os.listdir(FRAMES_DIR) if f.startswith("L_")])
        parts = [f"Aktif: {current} cift"]
        for s in sets:
            sd = os.path.join(calib_dir, s)
            n = len([f for f in os.listdir(sd) if f.startswith("L_")])
            parts.append(f"{s}: {n} cift")
        self.lbl_set_info.config(text=" | ".join(parts))

    def _new_calib_set(self):
        current = len([f for f in os.listdir(FRAMES_DIR) if f.startswith("L_")])
        if current == 0:
            self.lbl_set_info.config(text="Aktif sette kare yok, yedeklenecek bir sey yok")
            return
        calib_dir = os.path.dirname(FRAMES_DIR)
        existing = [d for d in os.listdir(calib_dir) if d.startswith("frames_set_")]
        next_num = len(existing) + 1
        set_name = f"frames_set_{next_num}"
        if not messagebox.askyesno("Yeni Set",
                f"Mevcut {current} kare '{set_name}' olarak yedeklenecek.\n"
                f"Aktif frames/ klasoru bosaltilacak.\n\nDevam?"):
            return
        import shutil
        dest = os.path.join(calib_dir, set_name)
        shutil.copytree(FRAMES_DIR, dest)
        if os.path.exists(CALIB_PATH):
            shutil.copy2(CALIB_PATH, os.path.join(dest, "calib_result.npz"))
        for f in os.listdir(FRAMES_DIR):
            os.remove(os.path.join(FRAMES_DIR, f))
        self.save_count = 0
        self.lbl_saved.config(text="0 cift")
        self._update_set_info()
        self.lbl_set_info.config(
            text=f"{set_name} olarak yedeklendi (kareler + kalibrasyon)", fg=GREEN)

    def _load_calib_set(self):
        calib_dir = os.path.dirname(FRAMES_DIR)
        sets = sorted([d for d in os.listdir(calib_dir)
                       if d.startswith("frames_set_") and
                       os.path.isdir(os.path.join(calib_dir, d))])
        if not sets:
            self.lbl_set_info.config(text="Yedeklenmis set yok")
            return
        import shutil
        from tkinter import simpledialog
        choice = simpledialog.askstring("Set Yukle",
            f"Mevcut setler: {', '.join(sets)}\n\n"
            f"Yuklemek istedigin set adini yaz:\n"
            f"(ornek: {sets[-1]})")
        if not choice or choice not in sets:
            return
        current = len([f for f in os.listdir(FRAMES_DIR) if f.startswith("L_")])
        if current > 0:
            if not messagebox.askyesno("Uyari",
                    f"Aktif sette {current} kare var.\n"
                    f"Ustune yazilacak. Devam?"):
                return
        for f in os.listdir(FRAMES_DIR):
            os.remove(os.path.join(FRAMES_DIR, f))
        src = os.path.join(calib_dir, choice)
        for f in os.listdir(src):
            shutil.copy2(os.path.join(src, f), FRAMES_DIR)
        self.save_count = len([f for f in os.listdir(FRAMES_DIR) if f.startswith("L_")])
        self.lbl_saved.config(text=f"{self.save_count} cift")
        self._update_set_info()
        self.lbl_set_info.config(
            text=f"{choice} yuklendi ({self.save_count} cift)", fg=GREEN)

    def _run_calibration(self):
        frame_count = len([f for f in os.listdir(FRAMES_DIR) if f.startswith("L_")])
        if frame_count < 5:
            self.lbl_calib_status.config(text=f"Yetersiz: {frame_count} cift (min 5)", fg=RED)
            return
        if not self.charuco_cfg.get("olculen_kare_boyutu_mm"):
            self.lbl_calib_status.config(text="Once pitch olcusu girilmeli!", fg=RED)
            return

        self.btn_run_calib.config(state="disabled")
        self.lbl_calib_status.config(text="Hesaplaniyor...", fg=YELLOW)
        self.root.update()

        def run():
            try:
                result = subprocess.run(
                    ["python", os.path.join(SCRIPT_DIR, "calibration.py"),
                     "--frames", FRAMES_DIR,
                     "--out", CALIB_PATH],
                    capture_output=True, text=True, cwd=PROJECT_DIR)
                output = result.stdout + result.stderr
                success = result.returncode == 0 and os.path.exists(CALIB_PATH)
                self.root.after(0, lambda: self._calib_done(success, output))
            except Exception as e:
                self.root.after(0, lambda: self._calib_done(False, str(e)))

        threading.Thread(target=run, daemon=True).start()

    def _calib_done(self, success, output):
        self.btn_run_calib.config(state="normal")
        if success:
            try:
                d = np.load(CALIB_PATH)
                rms = float(d["rms"])
                bl = float(d.get("baseline_mm", 0))
                color = GREEN if rms < 0.4 else YELLOW
                self.lbl_calib_status.config(
                    text=f"RMS={rms:.4f}px  Baseline={bl:.1f}mm", fg=color)
            except Exception:
                self.lbl_calib_status.config(text="Tamamlandi", fg=GREEN)
        else:
            lines = output.strip().split('\n')
            last = lines[-1] if lines else "Bilinmeyen hata"
            self.lbl_calib_status.config(text=f"HATA: {last[:60]}", fg=RED)
        print(output)

    # ── Tab: Derinlik ────────────────────────────────
    def _build_tab_depth(self):
        tab = tk.Frame(self.notebook, bg=CARD)
        self.notebook.add(tab, text="  Derinlik  ")

        c = self._section(tab, "Canli derinlik haritasi")

        btn_row = tk.Frame(c, bg=CARD)
        btn_row.pack(fill=tk.X, pady=6)
        self.btn_depth = tk.Button(btn_row, text="Derinlik KAPALI",
                                    command=self._toggle_depth,
                                    bg=BORDER, fg=FG, font=("Segoe UI", 10, "bold"),
                                    relief="flat", padx=14, pady=6, cursor="hand2")
        self.btn_depth.pack(side=tk.LEFT, padx=(0, 6))

        tk.Button(btn_row, text="Ekran goruntusu [D]", command=self._save_depth,
                  bg="#2d6a4f", fg="white", font=("Segoe UI", 10, "bold"),
                  relief="flat", padx=14, pady=6, cursor="hand2").pack(side=tk.LEFT, padx=(0, 6))

        tk.Button(btn_row, text="4K Foto Modu", command=self._capture_4k_depth,
                  bg="#6a2d4f", fg="white", font=("Segoe UI", 10, "bold"),
                  relief="flat", padx=14, pady=6, cursor="hand2").pack(side=tk.LEFT)

        btn_row2 = tk.Frame(c, bg=CARD)
        btn_row2.pack(fill=tk.X, pady=4)
        self.clean_disp_var = tk.BooleanVar(value=True)
        self.btn_clean_disp = tk.Checkbutton(
            btn_row2, text="Post-processing (temizleme)",
            variable=self.clean_disp_var, bg=CARD, fg=FG,
            selectcolor=BORDER, activebackground=CARD, activeforeground=FG,
            font=("Segoe UI", 9))
        self.btn_clean_disp.pack(side=tk.LEFT)

        c = self._section(tab, "Gorsellestirme")

        cmap_row = tk.Frame(c, bg=CARD)
        cmap_row.pack(fill=tk.X, pady=4)
        tk.Label(cmap_row, text="Renk haritasi:", bg=CARD, fg=FG,
                 font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self.colormap_var = tk.StringVar(value="JET")
        self.colormap_names = ["JET", "TURBO", "MAGMA", "INFERNO", "BONE", "HOT"]
        self.colormap_map = {
            "JET": cv2.COLORMAP_JET,
            "TURBO": cv2.COLORMAP_TURBO,
            "MAGMA": cv2.COLORMAP_MAGMA,
            "INFERNO": cv2.COLORMAP_INFERNO,
            "BONE": cv2.COLORMAP_BONE,
            "HOT": cv2.COLORMAP_HOT,
        }
        for name in self.colormap_names:
            tk.Radiobutton(cmap_row, text=name, variable=self.colormap_var,
                           value=name, bg=CARD, fg=FG, selectcolor=BORDER,
                           activebackground=CARD, activeforeground=FG,
                           font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=2)

        viz_row = tk.Frame(c, bg=CARD)
        viz_row.pack(fill=tk.X, pady=4)
        self.contour_var = tk.BooleanVar(value=False)
        tk.Checkbutton(viz_row, text="Derinlik konturlari",
                       variable=self.contour_var, bg=CARD, fg=FG,
                       selectcolor=BORDER, activebackground=CARD,
                       activeforeground=FG, font=("Segoe UI", 9)
                       ).pack(side=tk.LEFT, padx=(0, 12))
        self.compare_var = tk.BooleanVar(value=False)
        tk.Checkbutton(viz_row, text="Ham / WLS karsilastir",
                       variable=self.compare_var, bg=CARD, fg=FG,
                       selectcolor=BORDER, activebackground=CARD,
                       activeforeground=FG, font=("Segoe UI", 9)
                       ).pack(side=tk.LEFT)

        c = self._section(tab, "Bilgi")
        self.lbl_depth_status = self._info_row(c, "Durum")
        self.lbl_depth_center = self._info_row(c, "Merkez mesafe")
        self.lbl_depth_calib = self._info_row(c, "Kalibrasyon")

        has_calib = os.path.exists(CALIB_PATH)
        self.lbl_depth_calib.config(
            text="HAZIR" if has_calib else "YOK — once kalibre et",
            fg=GREEN if has_calib else RED)

        c = self._section(tab, "Renk skalasi")
        self.lbl_cmap_desc = tk.Label(c, text="", bg=CARD, fg=MUTED,
                                       font=("Segoe UI", 9), justify="left")
        self.lbl_cmap_desc.pack(fill=tk.X, pady=4)
        self.colormap_var.trace_add("write", lambda *_: self._update_cmap_desc())
        self.compare_var.trace_add("write", lambda *_: self._update_cmap_desc())
        self._update_cmap_desc()

        self.root.bind("<d>", lambda e: self._save_depth())
        self.root.bind("<D>", lambda e: self._save_depth())

    # ── Tab: Olcum ───────────────────────────────────
    def _build_tab_measure(self):
        tab = tk.Frame(self.notebook, bg=CARD)
        self.notebook.add(tab, text="  Olcum  ")

        c = self._section(tab, "Nesne olcumu")

        btn_row = tk.Frame(c, bg=CARD)
        btn_row.pack(fill=tk.X, pady=6)
        tk.Button(btn_row, text="Arka plan kaydet [B]",
                  command=self._capture_bg,
                  bg=BORDER, fg=FG, font=("Segoe UI", 10, "bold"),
                  relief="flat", padx=12, pady=6, cursor="hand2").pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(btn_row, text="Olc [M]",
                  command=self._do_measure,
                  bg="#2d6a4f", fg="white", font=("Segoe UI", 10, "bold"),
                  relief="flat", padx=12, pady=6, cursor="hand2").pack(side=tk.LEFT)

        c = self._section(tab, "Sonuc")
        self.lbl_meas_en = self._info_row(c, "En (mm)")
        self.lbl_meas_boy = self._info_row(c, "Boy (mm)")
        self.lbl_meas_yuk = self._info_row(c, "Yukseklik (mm)")
        self.lbl_meas_status = self._info_row(c, "Durum")

        c = self._section(tab, "Kutu onerisi")
        self.lbl_box_name = self._info_row(c, "Onerilen kutu")
        self.lbl_box_size = self._info_row(c, "Kutu boyutu")
        self.lbl_box_desi = self._info_row(c, "Desi")

        c = self._section(tab, "Gereksinimler")
        has_calib = os.path.exists(CALIB_PATH)
        has_ground = os.path.exists(GROUND_PATH)
        self.lbl_meas_calib = self._info_row(c, "Kalibrasyon",
            "HAZIR" if has_calib else "YOK", GREEN if has_calib else RED)
        self.lbl_meas_ground = self._info_row(c, "Zemin duzlemi",
            "HAZIR" if has_ground else "YOK", GREEN if has_ground else RED)
        self.lbl_meas_bg = self._info_row(c, "Arka plan", "Kaydedilmedi", RED)

        tk.Label(c, text=(
            "Adimlar:\n"
            "1. Masayi bos birak → B ile arka plan kaydet\n"
            "2. Nesneyi masaya koy\n"
            "3. M ile olc\n"
            "Kutu onerisi otomatik gosterilir."
        ), bg=CARD, fg=MUTED, font=("Segoe UI", 9),
                 justify="left").pack(fill=tk.X, pady=4)

        self.root.bind("<b>", lambda e: self._capture_bg())
        self.root.bind("<B>", lambda e: self._capture_bg())
        self.root.bind("<m>", lambda e: self._do_measure())
        self.root.bind("<M>", lambda e: self._do_measure())

    # ── Tab: Durum ───────────────────────────────────
    def _build_tab_status(self):
        tab = tk.Frame(self.notebook, bg=CARD)
        self.notebook.add(tab, text="  Durum  ")

        canvas = tk.Canvas(tab, bg=CARD, highlightthickness=0)
        scrollbar = tk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        sf = tk.Frame(canvas, bg=CARD)
        sf.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=sf, anchor="nw", tags="sf")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig("sf", width=e.width))
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sf.bind("<MouseWheel>", lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))
        canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))

        # Pipeline durumu
        c = self._section(sf, "Pipeline durumu")
        self.status_checks = {}
        checks = [
            ("charuco", "ChArUco olculdu mu"),
            ("frames", "Kalibrasyon kareleri"),
            ("calib", "Kalibrasyon (calib_result.npz)"),
            ("ground", "Zemin duzlemi (ground_plane.npz)"),
        ]
        for key, label in checks:
            self.status_checks[key] = self._info_row(c, label, "---")

        btn_row = tk.Frame(c, bg=CARD)
        btn_row.pack(fill=tk.X, pady=6)
        tk.Button(btn_row, text="Durumu yenile",
                  command=self._refresh_status,
                  bg=BORDER, fg=FG, font=("Segoe UI", 9, "bold"),
                  relief="flat", padx=10, pady=4, cursor="hand2").pack(side=tk.LEFT)

        # Islemler
        c = self._section(sf, "Islemler")
        btn_row2 = tk.Frame(c, bg=CARD)
        btn_row2.pack(fill=tk.X, pady=6)
        tk.Button(btn_row2, text="Kalibre et",
                  command=self._run_calibration,
                  bg="#2d6a4f", fg="white", font=("Segoe UI", 10, "bold"),
                  relief="flat", padx=14, pady=6, cursor="hand2").pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(btn_row2, text="Zemin tespiti",
                  command=self._run_ground_plane,
                  bg="#1a5276", fg="white", font=("Segoe UI", 10, "bold"),
                  relief="flat", padx=14, pady=6, cursor="hand2").pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(btn_row2, text="Odak testi",
                  command=self._run_focus_test,
                  bg=BORDER, fg=FG, font=("Segoe UI", 10, "bold"),
                  relief="flat", padx=14, pady=6, cursor="hand2").pack(side=tk.LEFT)

        self.lbl_process_out = tk.Text(c, height=10, bg=INPUT_BG, fg=FG,
                                        font=("Consolas", 9), relief="flat",
                                        state="disabled", wrap="word")
        self.lbl_process_out.pack(fill=tk.X, pady=6)

        # Olcum defteri
        c = self._section(sf, "Olcum defteri (son 10)")
        self.diary_text = tk.Text(c, height=8, bg=INPUT_BG, fg=FG,
                                   font=("Consolas", 9), relief="flat",
                                   state="disabled", wrap="none")
        self.diary_text.pack(fill=tk.X, pady=4)
        tk.Button(c, text="Defteri yenile", command=self._refresh_diary,
                  bg=BORDER, fg=FG, font=("Segoe UI", 9),
                  relief="flat", padx=8, pady=2, cursor="hand2").pack(anchor="w")

        self._refresh_status()
        self._refresh_diary()

    # ── Tab: Rehber ───────────────────────────────────
    def _build_tab_guide(self):
        tab = tk.Frame(self.notebook, bg=CARD)
        self.notebook.add(tab, text="  Rehber  ")

        canvas = tk.Canvas(tab, bg=CARD, highlightthickness=0)
        scrollbar = tk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        sf = tk.Frame(canvas, bg=CARD)
        sf.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=sf, anchor="nw", tags="sf")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig("sf", width=e.width))
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sf.bind("<MouseWheel>", lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))
        canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))

        steps = [
            ("ADIM 1: Cozunurluk sec", ACCENT,
             "Ayarlar tabinda cozunurluk sec.\n"
             "Onerilen: 1280x720 YUY2 (6 FPS)\n"
             "Kalibrasyon ve olcum AYNI cozunurlukle\n"
             "yapilmali — sonra degistirme.\n"
             "4K (0.7 FPS) cok yavas, 640x480 az detay."),

            ("ADIM 2: Aydinlatma sabitle", YELLOW,
             "Masa lambasi kullan, perdeyi kapat.\n"
             "Gun isigi degisir — kalibrasyon bozulur.\n"
             "Floresan/LED: pozlamayi 10ms katlarina\n"
             "ayarla (50 Hz bantlanma onlemi)."),

            ("ADIM 3: Pozlama / Gain / WB ayarla", YELLOW,
             "Ayarlar tabindaki slider'larla:\n"
             "- Pozlama: goruntu ne karalik ne yanik\n"
             "- Gain: dusuk tut (gurultu artirir)\n"
             "- WB: iki kamerada da ayni renk tonu\n\n"
             "Degerler iki kamerada ayni uygulanir.\n"
             "Bu degerleri olcum defterine yaz!"),

            ("ADIM 4: Odak ayarla (FIZIKSEL)", RED,
             "Bu adim FIZIKSEL lens cevirme gerektirir.\n\n"
             "1. Calisma mesafesine (30-90 cm) bir\n"
             "   hedef (gazete, yazi) koy\n"
             "2. M12 lensi yavasca cevir\n"
             "3. Netlik SAG/SOL degerini izle\n"
             "   (Ayarlar tabinda veya status bar'da)\n"
             "4. Maksimum degere getir\n"
             "5. Iki kamerada da benzer skor hedefle\n"
             "6. LENS KILIT VIDASINI SIK veya oje sur\n\n"
             "BUNDAN SONRA LENSE DOKUNMA!\n"
             "Kalibrasyondan sonra lens oynamasi\n"
             "tum olcumleri gecersiz kilar."),

            ("ADIM 5: Deseni bas ve olc", YELLOW,
             "patterns/charuco_board.png dosyasini\n"
             "yazicidan %100 olcekle bas.\n\n"
             "Basili desendeki bir karenin kenarini\n"
             "KUMPASLA OLC (beklenen: 30 mm).\n"
             "5 kareyi olc, ortalama al.\n\n"
             "Olculen degeri data/charuco_config.json\n"
             "icindeki 'olculen_kare_boyutu_mm'\n"
             "alanina yaz.\n\n"
             "Deseni SERT DUZLEME yapistir\n"
             "(cam, foreks, kalin mukavva).\n"
             "Kivrik kagit = yanlis kalibrasyon."),

            ("ADIM 6: Baseline olc", GREEN,
             "Kumpasla iki lens merkezi arasindaki\n"
             "mesafeyi olc → yaklasik baseline.\n\n"
             "Bu degeri Hesaplama tabindaki\n"
             "'Baseline' alanina gir.\n\n"
             "Gercek baseline kalibrasyondan gelecek\n"
             "(||T|| vektoru). Kumpas olcumuyle\n"
             "karsilastir — %5'ten fazla fark varsa\n"
             "kalibrasyonda sorun var demek."),

            ("ADIM 7: Kalibrasyon karesi topla", GREEN,
             "1. Kalibrasyon tabinda modu AC\n"
             "2. Deseni farkli pozisyon/acilarda tut\n"
             "3. Yesil cerceve gorununce S ile kaydet\n"
             "4. 25-40 gecerli cift topla\n"
             "5. 3x3 grid kapsama + egim + mesafe\n\n"
             "Her iki kamerada da desen gorunmeli.\n"
             "Hareket bulanikliginden kacin —\n"
             "dur, bekle, kaydet."),

            ("ADIM 8: Kalibre et", GREEN,
             "Kareler toplandiktan sonra\n"
             "calibration.py scriptini calistir.\n"
             "(Henuz yazilmadi — bu adimda\n"
             "Claude Code'a sor.)\n\n"
             "Hedef: RMS < 0.4 px\n"
             "Cikti: calibration/calib_result.npz"),
        ]

        for title, color, text in steps:
            frame = tk.Frame(sf, bg=CARD, highlightbackground=color,
                              highlightthickness=1, padx=12, pady=8)
            frame.pack(fill=tk.X, padx=8, pady=4)
            tk.Label(frame, text=title, bg=CARD, fg=color,
                     font=("Segoe UI", 11, "bold"), anchor="w").pack(fill=tk.X)
            tk.Label(frame, text=text, bg=CARD, fg=FG,
                     font=("Segoe UI", 9), justify="left",
                     anchor="nw").pack(fill=tk.X, pady=(4, 0))

    # ── Kamera ────────────────────────────────────────
    def _open_cameras(self):
        self.status_bar.config(text="Kameralar baglaniyor (MSMF)...", fg=YELLOW)
        self.root.update()
        threading.Thread(target=self._open_cameras_bg, daemon=True).start()

    def _open_cameras_bg(self):
        results = [None, None]
        def _open(idx, slot):
            results[slot] = cv2.VideoCapture(idx, cv2.CAP_MSMF)
        t_l = threading.Thread(target=_open, args=(self.left_idx, 0))
        t_r = threading.Thread(target=_open, args=(self.right_idx, 1))
        t_l.start(); t_r.start()
        t_l.join(); t_r.join()
        cap_l, cap_r = results
        self.cap_l = cap_l
        self.cap_r = cap_r

        cam_ok_l = cap_l is not None and cap_l.isOpened()
        cam_ok_r = cap_r is not None and cap_r.isOpened()

        if not cam_ok_l and not cam_ok_r:
            self.root.after(0, lambda: self.status_bar.config(
                text="HATA: Hicbir kamera bulunamadi!", fg=RED))
            return
        if not cam_ok_l:
            self.root.after(0, lambda: self.status_bar.config(
                text="UYARI: Sol kamera (idx {}) acilamadi!".format(self.left_idx), fg=YELLOW))
        if not cam_ok_r:
            self.root.after(0, lambda: self.status_bar.config(
                text="UYARI: Sag kamera (idx {}) acilamadi!".format(self.right_idx), fg=YELLOW))

        sel = self.res_var.get()
        w, h, fmt = 2048, 1536, "MJPG"
        for name, rw, rh, rfmt in RESOLUTIONS:
            if name == sel:
                w, h, fmt = rw, rh, rfmt
                break
        for cap in [cap_l, cap_r]:
            if cap and cap.isOpened():
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fmt))
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        self.current_w = w
        self.current_h = h
        self.root.after(0, self._apply_loaded_settings)
        self.root.after(0, self._apply_all)
        self.running = True
        self.root.after(0, lambda: self.status_bar.config(
            text="Kameralar bagli — {} MSMF".format(sel), fg=ACCENT))
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
        self._update_display()

    def _apply_all(self):
        for cap in [self.cap_l, self.cap_r]:
            if not cap or not cap.isOpened():
                continue
            cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
            cap.set(cv2.CAP_PROP_EXPOSURE, self.exposure_var.get())
            cap.set(cv2.CAP_PROP_AUTO_WB, 0)
            cap.set(cv2.CAP_PROP_WB_TEMPERATURE, self.wb_var.get())
            cap.set(cv2.CAP_PROP_GAIN, self.gain_var.get())
            cap.set(cv2.CAP_PROP_BRIGHTNESS, self.brightness_var.get())
            cap.set(cv2.CAP_PROP_CONTRAST, self.contrast_var.get())
            cap.set(cv2.CAP_PROP_SATURATION, self.saturation_var.get())
            cap.set(cv2.CAP_PROP_SHARPNESS, self.sharpness_var.get())

    def _set_prop(self, prop, val):
        for cap in [self.cap_l, self.cap_r]:
            if cap and cap.isOpened():
                cap.set(prop, val)

    def _on_exposure(self):
        exp = self.exposure_var.get()
        for cap in [self.cap_l, self.cap_r]:
            if cap and cap.isOpened():
                cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
        if self.cap_l and self.cap_l.isOpened():
            self.cap_l.set(cv2.CAP_PROP_EXPOSURE, exp)
        if self.cap_r and self.cap_r.isOpened():
            self.cap_r.set(cv2.CAP_PROP_EXPOSURE,
                           max(-13, min(0, exp + self.exp_offset_r.get())))

    def _on_gain(self):
        g = self.gain_var.get()
        if self.cap_l and self.cap_l.isOpened():
            self.cap_l.set(cv2.CAP_PROP_GAIN, g)
        if self.cap_r and self.cap_r.isOpened():
            self.cap_r.set(cv2.CAP_PROP_GAIN,
                           max(0, min(100, g + self.gain_offset_r.get())))

    def _on_wb(self):
        self._set_prop(cv2.CAP_PROP_AUTO_WB, 0)
        self._set_prop(cv2.CAP_PROP_WB_TEMPERATURE, self.wb_var.get())

    def _on_bright_offset(self):
        val = self.brightness_var.get()
        if self.cap_l and self.cap_l.isOpened():
            self.cap_l.set(cv2.CAP_PROP_BRIGHTNESS, val)
        if self.cap_r and self.cap_r.isOpened():
            self.cap_r.set(cv2.CAP_PROP_BRIGHTNESS,
                           max(-64, min(64, val + self.bright_offset_r.get())))

    def _on_img_prop(self):
        self._set_prop(cv2.CAP_PROP_BRIGHTNESS, self.brightness_var.get())
        self._set_prop(cv2.CAP_PROP_CONTRAST, self.contrast_var.get())
        self._set_prop(cv2.CAP_PROP_SATURATION, self.saturation_var.get())
        self._set_prop(cv2.CAP_PROP_SHARPNESS, self.sharpness_var.get())

    def _on_resolution_change(self, event=None):
        sel = self.res_var.get()
        for name, w, h, fmt in RESOLUTIONS:
            if name == sel:
                if w >= 3840:
                    self.status_bar.config(
                        text="4K canli kullanima uygun degil (~1fps). 4K Foto Modu butonunu kullanin.",
                        fg=YELLOW)
                    prev = f"{self.current_w}x{self.current_h}"
                    for rn, rw, rh, rf in RESOLUTIONS:
                        if rw == self.current_w and rh == self.current_h:
                            self.res_var.set(rn)
                            break
                    return
                self.running = False
                if self.thread is not None:
                    self.thread.join(timeout=2.0)
                for cap in [self.cap_l, self.cap_r]:
                    if cap and cap.isOpened():
                        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fmt))
                        cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
                        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
                self.current_w = w
                self.current_h = h
                self._apply_all()
                self.running = True
                self.thread = threading.Thread(target=self._capture_loop, daemon=True)
                self.thread.start()
                self._update_display()
                break

    # ── Capture ───────────────────────────────────────
    def _try_reconnect(self, side):
        sel = self.res_var.get()
        w, h, fmt = self.current_w, self.current_h, "YUY2"
        for name, rw, rh, rfmt in RESOLUTIONS:
            if name == sel:
                w, h, fmt = rw, rh, rfmt
                break
        if side == "left":
            if self.cap_l is not None:
                self.cap_l.release()
            self.cap_l = cv2.VideoCapture(self.left_idx, cv2.CAP_MSMF)
            cap = self.cap_l
        else:
            if self.cap_r is not None:
                self.cap_r.release()
            self.cap_r = cv2.VideoCapture(self.right_idx, cv2.CAP_MSMF)
            cap = self.cap_r
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fmt))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
            self._apply_all()
            return True
        return False

    def _capture_loop(self):
        prev_time = time.time()
        frame_count = 0
        reconnect_timer = time.time()
        while self.running:
            try:
                l_ok = self.cap_l is not None and self.cap_l.isOpened()
                r_ok = self.cap_r is not None and self.cap_r.isOpened()

                # Her 3 saniyede kopuk kamerayi yeniden bagla
                if (not l_ok or not r_ok) and time.time() - reconnect_timer > 3.0:
                    reconnect_timer = time.time()
                    if not l_ok:
                        if self._try_reconnect("left"):
                            l_ok = True
                    if not r_ok:
                        if self._try_reconnect("right"):
                            r_ok = True

                if not l_ok and not r_ok:
                    time.sleep(0.5)
                    continue

                fl = fr = None
                if l_ok:
                    self.cap_l.grab()
                if r_ok:
                    self.cap_r.grab()
                if l_ok:
                    ret_l, fl = self.cap_l.retrieve()
                    if not ret_l:
                        fl = None
                if r_ok:
                    ret_r, fr = self.cap_r.retrieve()
                    if not ret_r:
                        fr = None

                if fl is None and fr is None:
                    time.sleep(0.1)
                    continue
                if fl is None:
                    fl = np.zeros((self.current_h, self.current_w, 3), dtype=np.uint8)
                    cv2.putText(fl, "SOL KAMERA YOK", (30, self.current_h // 2),
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                if fr is None:
                    fr = np.zeros((self.current_h, self.current_w, 3), dtype=np.uint8)
                    cv2.putText(fr, "SAG KAMERA YOK", (30, self.current_h // 2),
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            except Exception:
                time.sleep(0.2)
                continue

            if not hasattr(self, '_metric_skip'):
                self._metric_skip = 0
            self._metric_skip += 1
            skip_n = 10 if self.current_w >= 2048 else 3
            if self._metric_skip % skip_n == 0:
                small_l = cv2.cvtColor(cv2.resize(fl, (640, 480)), cv2.COLOR_BGR2GRAY)
                small_r = cv2.cvtColor(cv2.resize(fr, (640, 480)), cv2.COLOR_BGR2GRAY)
                sl = cv2.Laplacian(small_l, cv2.CV_64F).var()
                sr = cv2.Laplacian(small_r, cv2.CV_64F).var()
                bl = float(small_l.mean())
                br = float(small_r.mean())
            else:
                sl = getattr(self, 'score_l', 0)
                sr = getattr(self, 'score_r', 0)
                bl = getattr(self, 'bright_l', 0)
                br = getattr(self, 'bright_r', 0)

            cl = cr = 0

            if self.calib_mode:
                dl = fl.copy()
                dr = fr.copy()
            else:
                dl = fl
                dr = fr

            if self.calib_mode:
                if not hasattr(self, '_detect_skip'):
                    self._detect_skip = 0
                    self._last_detect_l = (None, None)
                    self._last_detect_r = (None, None)
                self._detect_skip += 1
                run_detect = (self._detect_skip % 5 == 0)
                is_grid = isinstance(self.detector, cv2.aruco.ArucoDetector)

                if run_detect:
                    if self.current_w > 1280:
                        det_scale = 960.0 / fl.shape[0]
                        det_w = int(fl.shape[1] * det_scale)
                        det_l = cv2.cvtColor(cv2.resize(fl, (det_w, 960)), cv2.COLOR_BGR2GRAY)
                        det_r = cv2.cvtColor(cv2.resize(fr, (det_w, 960)), cv2.COLOR_BGR2GRAY)
                        inv_scale = 1.0 / det_scale
                    else:
                        det_l = cv2.cvtColor(fl, cv2.COLOR_BGR2GRAY)
                        det_r = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
                        inv_scale = 1.0
                    try:
                        if is_grid:
                            corners_l, ids_l, _ = self.detector.detectMarkers(det_l)
                            if corners_l and inv_scale != 1.0:
                                corners_l = tuple(c * inv_scale for c in corners_l)
                            self._last_detect_l = (corners_l, ids_l)
                        else:
                            ch_corners_l, ch_ids_l, _, _ = self.detector.detectBoard(det_l)
                            if ch_corners_l is not None and inv_scale != 1.0:
                                ch_corners_l = ch_corners_l * inv_scale
                            self._last_detect_l = (ch_corners_l, ch_ids_l)
                    except Exception as e:
                        if not hasattr(self, '_dbg_err'):
                            self._dbg_err = True
                            print(f"[DEBUG] SOL HATA: {e}")
                    try:
                        if is_grid:
                            corners_r, ids_r, _ = self.detector.detectMarkers(det_r)
                            if corners_r and inv_scale != 1.0:
                                corners_r = tuple(c * inv_scale for c in corners_r)
                            self._last_detect_r = (corners_r, ids_r)
                        else:
                            ch_corners_r, ch_ids_r, _, _ = self.detector.detectBoard(det_r)
                            if ch_corners_r is not None and inv_scale != 1.0:
                                ch_corners_r = ch_corners_r * inv_scale
                            self._last_detect_r = (ch_corners_r, ch_ids_r)
                    except Exception as e:
                        if not hasattr(self, '_dbg_err_r'):
                            self._dbg_err_r = True
                            print(f"[DEBUG] SAG HATA: {e}")

                det_l, det_id_l = self._last_detect_l
                det_r, det_id_r = self._last_detect_r
                if is_grid:
                    if det_id_l is not None and len(det_id_l) > 0:
                        cl = len(det_id_l)
                        cv2.aruco.drawDetectedMarkers(dl, det_l, det_id_l)
                    if det_id_r is not None and len(det_id_r) > 0:
                        cr = len(det_id_r)
                        cv2.aruco.drawDetectedMarkers(dr, det_r, det_id_r)
                else:
                    if det_l is not None and len(det_l) > 0:
                        cl = len(det_l)
                        r = max(3, self.current_w // 200)
                        for pt in det_l:
                            cv2.circle(dl, tuple(pt.ravel().astype(int)), r, (0, 255, 0), -1)
                    if det_r is not None and len(det_r) > 0:
                        cr = len(det_r)
                        r = max(3, self.current_w // 200)
                        for pt in det_r:
                            cv2.circle(dr, tuple(pt.ravel().astype(int)), r, (0, 255, 0), -1)

                if cl >= self.max_corners * 0.15:
                    cv2.rectangle(dl, (0,0), (dl.shape[1]-1, dl.shape[0]-1), (0,255,0), 3)
                if cr >= self.max_corners * 0.15:
                    cv2.rectangle(dr, (0,0), (dr.shape[1]-1, dr.shape[0]-1), (0,255,0), 3)
                self._check_auto_capture(cl, cr)

            with self.lock:
                self.frame_l = fl
                self.frame_r = fr
                self.display_frame_l = dl
                self.display_frame_r = dr
                self.score_l = sl
                self.score_r = sr
                self.bright_l = bl
                self.bright_r = br
                if sl > self.peak_l:
                    self.peak_l = sl
                if sr > self.peak_r:
                    self.peak_r = sr
                self.corners_l = cl
                self.corners_r = cr

            frame_count += 1
            now = time.time()
            if now - prev_time >= 0.5:
                self.fps = frame_count / (now - prev_time)
                frame_count = 0
                prev_time = now

    # ── Display ───────────────────────────────────────
    def _update_display(self):
        if not self.running:
            return

        with self.lock:
            fl = self.display_frame_l
            fr = self.display_frame_r
            fps = self.fps
            sl = self.score_l
            sr = self.score_r
            bl = self.bright_l
            br = self.bright_r
            pl = self.peak_l
            pr = self.peak_r
            cl = self.corners_l
            cr = self.corners_r

        if fl is not None and fr is not None:
            h1, w1 = fl.shape[:2]
            h2, w2 = fr.shape[:2]
            if h1 != h2:
                th = min(h1, h2)
                fl = cv2.resize(fl, (int(w1*th/h1), th))
                fr = cv2.resize(fr, (int(w2*th/h2), th))
            # Derinlik modu aktifse sol goruntuye overlay ekle
            if self.depth_mode and self.map1x is not None and self.stereo is not None:
                try:
                    with self.lock:
                        raw_l = self.frame_l
                        raw_r = self.frame_r
                    if raw_l is not None and raw_r is not None:
                        if self._use_gpu:
                            gpu_src_l = cv2.cuda_GpuMat(); gpu_src_l.upload(raw_l)
                            gpu_src_r = cv2.cuda_GpuMat(); gpu_src_r.upload(raw_r)
                            gpu_rl = cv2.cuda.remap(gpu_src_l, self.gpu_map1x, self.gpu_map1y, cv2.INTER_LINEAR)
                            gpu_rr = cv2.cuda.remap(gpu_src_r, self.gpu_map2x, self.gpu_map2y, cv2.INTER_LINEAR)
                            rl = gpu_rl.download()
                            gpu_gl = cv2.cuda.cvtColor(gpu_rl, cv2.COLOR_BGR2GRAY)
                            gpu_gr = cv2.cuda.cvtColor(gpu_rr, cv2.COLOR_BGR2GRAY)
                            gl = gpu_gl.download()
                            gr = gpu_gr.download()
                        else:
                            rl = cv2.remap(raw_l, self.map1x, self.map1y, cv2.INTER_LINEAR)
                            rr = cv2.remap(raw_r, self.map2x, self.map2y, cv2.INTER_LINEAR)
                            gl = cv2.cvtColor(rl, cv2.COLOR_BGR2GRAY)
                            gr = cv2.cvtColor(rr, cv2.COLOR_BGR2GRAY)
                        dsp = self._compute_disparity(gl, gr)
                        dm = dsp.max() if dsp.max() > 0 else 1
                        dn = (dsp / dm * 255).astype(np.uint8)
                        cmap_id = self.colormap_map.get(
                            self.colormap_var.get(), cv2.COLORMAP_JET)
                        dc = cv2.applyColorMap(dn, cmap_id)
                        dc[dsp <= 0] = [0, 0, 0]
                        if self.contour_var.get():
                            levels = np.linspace(30, 230, 8).astype(np.uint8)
                            for lv in levels:
                                edges = cv2.inRange(dn, int(lv) - 3, int(lv) + 3)
                                edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE,
                                    np.ones((3, 3), np.uint8))
                                dc[edges > 0] = [255, 255, 255]
                        msk = dsp > 0
                        fl = rl.copy()
                        fl[msk] = cv2.addWeighted(rl, 0.4, dc, 0.6, 0)[msk]
                        if self.compare_var.get():
                            if self._use_gpu:
                                g_l = cv2.cuda_GpuMat()
                                g_r = cv2.cuda_GpuMat()
                                g_l.upload(gl)
                                g_r.upload(gr)
                                dsp_raw = self.stereo.compute(g_l, g_r).download().astype(np.float32) / 16.0
                            else:
                                dsp_raw = self.stereo.compute(gl, gr).astype(np.float32) / 16.0
                            dsp_raw[dsp_raw <= 0] = 0
                            common_max = max(dsp.max(), dsp_raw.max(), 1)
                            dn_r = (dsp_raw / common_max * 255).astype(np.uint8)
                            dn_c = (dsp / common_max * 255).astype(np.uint8)
                            dc_raw = cv2.applyColorMap(dn_r, cmap_id)
                            dc_wls = cv2.applyColorMap(dn_c, cmap_id)
                            dc_raw[dsp_raw <= 0] = [0, 0, 0]
                            dc_wls[dsp <= 0] = [0, 0, 0]
                            h, w = dc_wls.shape[:2]
                            mid = w // 2
                            fr = dc_wls.copy()
                            fr[:, :mid] = dc_raw[:, :mid]
                            cv2.line(fr, (mid, 0), (mid, h), (255, 255, 255), 2)
                            cv2.putText(fr, "Ham SGBM", (10, 25),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)
                            cv2.putText(fr, "WLS+Post", (mid + 10, 25),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)
                        else:
                            disp_gray = cv2.cvtColor(dn, cv2.COLOR_GRAY2BGR)
                            disp_gray[dsp <= 0] = [0, 0, 0]
                            fr = disp_gray
                        # Merkez mesafe
                        cy, cx = rl.shape[0]//2, rl.shape[1]//2
                        # Nisan isareti (crosshair) — her iki goruntuye
                        cross_size = 20
                        cv2.line(fl, (cx - cross_size, cy), (cx + cross_size, cy), (0, 255, 0), 2)
                        cv2.line(fl, (cx, cy - cross_size), (cx, cy + cross_size), (0, 255, 0), 2)
                        cv2.line(fr, (cx - cross_size, cy), (cx + cross_size, cy), (0, 255, 0), 2)
                        cv2.line(fr, (cx, cy - cross_size), (cx, cy + cross_size), (0, 255, 0), 2)
                        # Etiketler
                        cv2.putText(fl, "Sol kamera + derinlik", (10, 25),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
                        cv2.putText(fr, "Disparity map", (10, 25),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
                        cd = dsp[cy, cx]
                        if cd > 0:
                            pts = cv2.reprojectImageTo3D(dsp, self.calib_data["Q"])
                            cz = abs(pts[cy, cx, 2]) * 1000
                            if 0 < cz < 5000:
                                cv2.putText(fl, f"{cz:.0f}mm", (cx + 25, cy - 10),
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                                cv2.putText(fr, f"{cz:.0f}mm", (cx + 25, cy - 10),
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                                self.root.after(0, lambda z=cz: self.lbl_depth_center.config(
                                    text=f"{z:.0f} mm", fg=GREEN))
                except Exception:
                    pass

            # Kamera etiketleri
            h_fl, w_fl = fl.shape[:2]
            h_fr, w_fr = fr.shape[:2]
            if not self.depth_mode:
                cv2.putText(fl, f"SOL (idx {self.left_idx})", (10, h_fl - 15),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
                cv2.putText(fr, f"SAG (idx {self.right_idx})", (10, h_fr - 15),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
            combined = np.hstack([fl, fr])

            mw = max(self.cam_label.winfo_width(), 100)
            mh = max(self.cam_label.winfo_height(), 100)
            ch, cw = combined.shape[:2]
            scale = min(mw/cw, mh/ch, 1.0)
            if scale < 1.0:
                combined = cv2.resize(combined, (int(cw*scale), int(ch*scale)))

            rgb = cv2.cvtColor(combined, cv2.COLOR_BGR2RGB)
            img = ImageTk.PhotoImage(image=Image.fromarray(rgb))
            self.cam_label.imgtk = img
            self.cam_label.config(image=img)

        # Status bar
        fourcc_int = int(self.cap_l.get(cv2.CAP_PROP_FOURCC)) if self.cap_l else 0
        fmt = "".join([chr((fourcc_int >> 8*j) & 0xFF) for j in range(4)]) if fourcc_int else "?"
        exp = self.cap_l.get(cv2.CAP_PROP_EXPOSURE) if self.cap_l else 0
        gpu_tag = "GPU" if self._use_gpu else "CPU"
        st = (f"  {self.current_w}x{self.current_h} {fmt} [{gpu_tag}]   "
              f"FPS: {fps:.1f}   "
              f"Netlik: L={sl:.0f} R={sr:.0f}   "
              f"Poz: {exp:.0f}   "
              f"Kayit: {self.save_count}")
        if self.calib_mode:
            st += f"   Kose: L={cl}/{self.max_corners} R={cr}/{self.max_corners}"
        self.status_bar.config(text=st)

        # Ayarlar tab canli
        self.lbl_fps.config(text=f"{fps:.1f}",
                             fg=GREEN if fps > 3 else YELLOW if fps > 1 else RED)
        self.lbl_net_l.config(text=f"{sl:.0f}",
                               fg=GREEN if sl > 100 else YELLOW if sl > 30 else RED)
        self.lbl_net_r.config(text=f"{sr:.0f}",
                               fg=GREEN if sr > 100 else YELLOW if sr > 30 else RED)
        self.lbl_net_peak_l.config(text=f"{pl:.0f}", fg=MUTED)
        self.lbl_net_peak_r.config(text=f"{pr:.0f}", fg=MUTED)

        bright_ok = lambda b: GREEN if 90 <= b <= 130 else YELLOW if 50 <= b <= 180 else RED
        self.lbl_bright_l.config(text=f"{bl:.0f}/255", fg=bright_ok(bl))
        self.lbl_bright_r.config(text=f"{br:.0f}/255", fg=bright_ok(br))
        if max(bl, br) > 0:
            diff_pct = abs(bl - br) / max(bl, br) * 100
            self.lbl_bright_diff.config(
                text=f"{diff_pct:.0f}%",
                fg=GREEN if diff_pct < 15 else YELLOW if diff_pct < 30 else RED)

        self.lbl_res_active.config(text=f"{self.current_w}x{self.current_h}")
        self.lbl_format.config(text=fmt)

        # Kalibrasyon tab
        if self.calib_mode:
            gl = cl >= self.max_corners * 0.15
            gr = cr >= self.max_corners * 0.15
            self.lbl_corners_l.config(text=f"{cl}/{self.max_corners}",
                                       fg=GREEN if gl else RED)
            self.lbl_corners_r.config(text=f"{cr}/{self.max_corners}",
                                       fg=GREEN if gr else RED)

        self.root.after(33, self._update_display)

    # ── Actions ───────────────────────────────────────
    def _toggle_auto_capture(self):
        self.auto_capture = not self.auto_capture
        if self.auto_capture:
            if not self.calib_mode:
                self.calib_mode = True
                self.btn_calib.config(text="Kalibrasyon ACIK", bg="#2d6a4f")
            self.btn_auto.config(text="Otomatik Cekim: ACIK", bg="#2d6a4f")
            self._last_auto_corners = None
            self._auto_cooldown = 0
        else:
            self.btn_auto.config(text="Otomatik Cekim: KAPALI", bg=BORDER)

    def _check_auto_capture(self, corners_l, corners_r):
        if not self.auto_capture:
            return
        if self._auto_cooldown > 0:
            self._auto_cooldown -= 1
            return
        min_corners = self.max_corners * 0.15
        if corners_l < min_corners or corners_r < min_corners:
            return
        self._auto_cooldown = 15
        self.root.after(0, self._save_frame)
        self.root.after(0, lambda: self.status_bar.config(
            text=f"  Otomatik cekim #{self.save_count + 1}!", fg=GREEN))

    def _toggle_calib(self):
        self.calib_mode = not self.calib_mode
        if self.calib_mode:
            self.btn_calib.config(text="Kalibrasyon ACIK", bg="#2d6a4f")
        else:
            self.btn_calib.config(text="Kalibrasyon KAPALI", bg=BORDER)
            self.lbl_corners_l.config(text="--", fg=FG)
            self.lbl_corners_r.config(text="--", fg=FG)
            if self.auto_capture:
                self._toggle_auto_capture()

    def _save_frame(self):
        with self.lock:
            fl = self.frame_l
            fr = self.frame_r
        if fl is None or fr is None:
            return
        self.save_count += 1
        cv2.imwrite(os.path.join(FRAMES_DIR, f"L_{self.save_count:03d}.png"), fl)
        cv2.imwrite(os.path.join(FRAMES_DIR, f"R_{self.save_count:03d}.png"), fr)
        self.lbl_saved.config(text=f"{self.save_count} cift")
        print(f"#{self.save_count} Netlik: L={self.score_l:.0f} R={self.score_r:.0f}")

    def _delete_last(self):
        if self.save_count < 1:
            return
        for prefix in ["L_", "R_"]:
            p = os.path.join(FRAMES_DIR, f"{prefix}{self.save_count:03d}.png")
            if os.path.exists(p):
                os.remove(p)
        self.save_count -= 1
        self.lbl_saved.config(text=f"{self.save_count} cift")

    # ── Swap kamera ────────────────────────────────────
    def _swap_cameras(self):
        self.running = False
        time.sleep(0.2)
        for cap in [self.cap_l, self.cap_r]:
            if cap:
                cap.release()
        self.left_idx, self.right_idx = self.right_idx, self.left_idx
        self.lbl_cam_idx.config(text=f"SOL=idx {self.left_idx}  SAG=idx {self.right_idx}")
        self._open_cameras()

    # ── Ayar kaydet/yukle ────────────────────────────
    def _save_settings(self):
        settings = {
            "exposure": self.exposure_var.get(),
            "gain": self.gain_var.get(),
            "wb": self.wb_var.get(),
            "exp_offset_r": self.exp_offset_r.get(),
            "gain_offset_r": self.gain_offset_r.get(),
            "bright_offset_r": self.bright_offset_r.get(),
            "brightness": self.brightness_var.get(),
            "contrast": self.contrast_var.get(),
            "saturation": self.saturation_var.get(),
            "sharpness": self.sharpness_var.get(),
            "resolution": self.res_var.get(),
            "left_idx": self.left_idx,
            "right_idx": self.right_idx,
        }
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
        self.status_bar.config(text="  Ayarlar kaydedildi!", fg=GREEN)

    def _load_settings(self):
        if not os.path.exists(SETTINGS_PATH):
            return
        try:
            with open(SETTINGS_PATH, encoding="utf-8") as f:
                s = json.load(f)
            self.left_idx = s.get("left_idx", self.left_idx)
            self.right_idx = s.get("right_idx", self.right_idx)
            self._pending_settings = s
        except Exception:
            self._pending_settings = None

    def _apply_loaded_settings(self):
        s = getattr(self, "_pending_settings", None)
        if not s:
            return
        self.exposure_var.set(s.get("exposure", -4))
        self.gain_var.set(s.get("gain", 0))
        self.wb_var.set(s.get("wb", 4500))
        self.exp_offset_r.set(s.get("exp_offset_r", 1))
        self.gain_offset_r.set(s.get("gain_offset_r", 0))
        self.bright_offset_r.set(s.get("bright_offset_r", 0))
        self.brightness_var.set(s.get("brightness", 0))
        self.contrast_var.set(s.get("contrast", 32))
        self.saturation_var.set(s.get("saturation", 64))
        self.sharpness_var.set(s.get("sharpness", 3))
        res = s.get("resolution", RESOLUTIONS[6][0])
        self.res_var.set(res)
        self._pending_settings = None

    # ── Derinlik ─────────────────────────────────────
    def _load_calib_data(self):
        if not os.path.exists(CALIB_PATH):
            return False
        self.calib_data = np.load(CALIB_PATH)
        K1, D1 = self.calib_data["K1"], self.calib_data["D1"]
        K2, D2 = self.calib_data["K2"], self.calib_data["D2"]
        R1, R2 = self.calib_data["R1"], self.calib_data["R2"]
        P1, P2 = self.calib_data["P1"], self.calib_data["P2"]
        image_size = tuple(self.calib_data["image_size"])
        self.map1x, self.map1y = cv2.initUndistortRectifyMap(
            K1, D1, R1, P1, image_size, cv2.CV_32FC1)
        self.map2x, self.map2y = cv2.initUndistortRectifyMap(
            K2, D2, R2, P2, image_size, cv2.CV_32FC1)
        if self._use_gpu:
            self.gpu_map1x = cv2.cuda_GpuMat(); self.gpu_map1x.upload(self.map1x)
            self.gpu_map1y = cv2.cuda_GpuMat(); self.gpu_map1y.upload(self.map1y)
            self.gpu_map2x = cv2.cuda_GpuMat(); self.gpu_map2x.upload(self.map2x)
            self.gpu_map2y = cv2.cuda_GpuMat(); self.gpu_map2y.upload(self.map2y)
            self.stereo = cv2.cuda.createStereoSGM(
                minDisparity=0, numDisparities=256, P1=10, P2=120,
                uniquenessRatio=15, mode=0)
            self.stereo_r = None
            self.wls_filter = None
        else:
            self.stereo = cv2.StereoSGBM_create(
                minDisparity=0, numDisparities=256, blockSize=5,
                P1=8*3*49, P2=32*3*49, disp12MaxDiff=1,
                uniquenessRatio=15, speckleWindowSize=200, speckleRange=2,
                preFilterCap=63, mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY)
            self.stereo_r = cv2.ximgproc.createRightMatcher(self.stereo)
            self.wls_filter = cv2.ximgproc.createDisparityWLSFilter(self.stereo)
            self.wls_filter.setLambda(8000)
            self.wls_filter.setSigmaColor(1.5)
        self.hires_stereo = None
        if os.path.exists(GROUND_PATH):
            self.ground_data = np.load(GROUND_PATH)
        return True

    def _compute_disparity(self, gray_l, gray_r):
        """Disparity hesapla — GPU StereoSGM + post-process, veya CPU SGBM + WLS."""
        if self._use_gpu:
            gpu_l = cv2.cuda_GpuMat()
            gpu_r = cv2.cuda_GpuMat()
            gpu_l.upload(gray_l)
            gpu_r.upload(gray_r)
            dsp = self.stereo.compute(gpu_l, gpu_r).download().astype(np.float32) / 16.0
            dsp[dsp <= 0] = 0
            dsp = cv2.medianBlur(dsp, 5)
        else:
            dsp_l = self.stereo.compute(gray_l, gray_r)
            dsp_r = self.stereo_r.compute(gray_r, gray_l)
            dsp = self.wls_filter.filter(dsp_l, gray_l, disparity_map_right=dsp_r)
            dsp = dsp.astype(np.float32) / 16.0
            dsp[dsp <= 0] = 0
        if hasattr(self, 'clean_disp_var') and self.clean_disp_var.get():
            dsp = self._clean_disparity(dsp)
        return dsp

    def _clean_disparity(self, dsp):
        """Disparity haritasini temizle: median + morfoloji + kucuk bolge."""
        mask = dsp > 0
        # 1. Median filtre — tuz-biber gurultusunu temizle
        dsp_med = cv2.medianBlur(dsp, 5)
        dsp = np.where(mask, dsp_med, 0)
        # 2. Morfolojik kapama — kucuk delikleri doldur
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        mask_closed = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_CLOSE, kernel)
        # 3. Kucuk bolgeleri sil (< 500 piksel)
        n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
            mask_closed, connectivity=8)
        for i in range(1, n_labels):
            if stats[i, cv2.CC_STAT_AREA] < 500:
                dsp[labels == i] = 0
        dsp[mask_closed == 0] = 0
        return dsp

    def _update_cmap_desc(self):
        descs = {
            "JET": (
                "KIRMIZI/SARI = yakin cisim\n"
                "YESIL/CYAN = orta mesafe\n"
                "MAVI/MOR = uzak cisim\n"
                "SIYAH = hesaplanamadi (dokusuz)"),
            "TURBO": (
                "KIRMIZI = yakin cisim\n"
                "SARI/YESIL = orta mesafe\n"
                "MAVI/MOR = uzak cisim\n"
                "SIYAH = hesaplanamadi (dokusuz)"),
            "MAGMA": (
                "SARI/BEYAZ = yakin cisim\n"
                "PEMBE/MOR = orta mesafe\n"
                "KOYU MOR/SIYAH = uzak cisim\n"
                "SIYAH = hesaplanamadi (dokusuz)"),
            "INFERNO": (
                "SARI/BEYAZ = yakin cisim\n"
                "TURUNCU/KIRMIZI = orta mesafe\n"
                "MOR/SIYAH = uzak cisim\n"
                "SIYAH = hesaplanamadi (dokusuz)"),
            "BONE": (
                "BEYAZ = yakin cisim\n"
                "ACIK MAVI = orta mesafe\n"
                "KOYU MAVI/SIYAH = uzak cisim\n"
                "SIYAH = hesaplanamadi (dokusuz)"),
            "HOT": (
                "BEYAZ/SARI = yakin cisim\n"
                "KIRMIZI/TURUNCU = orta mesafe\n"
                "KOYU KIRMIZI/SIYAH = uzak cisim\n"
                "SIYAH = hesaplanamadi (dokusuz)"),
        }
        name = self.colormap_var.get()
        txt = descs.get(name, descs["JET"])
        if self.compare_var.get():
            txt += ("\n\n--- Sag panel: Karsilastirma modu ---\n"
                    "Sol yari: Ham SGBM (filtresiz, gurultulu)\n"
                    "Sag yari: WLS + Post-processing (temiz)\n"
                    "Ayni renk skalasi, ayni normalizasyon")
        else:
            txt += ("\n\n--- Sag panel: Disparity haritasi ---\n"
                    "BEYAZ = yuksek disparity (yakin)\n"
                    "KOYU GRI = dusuk disparity (uzak)\n"
                    "SIYAH = hesaplanamadi")
        txt += "\n\nD tusu ile ekran goruntusu kaydeder."
        self.lbl_cmap_desc.config(text=txt)

    def _toggle_depth(self):
        if not self.depth_mode:
            if self.calib_data is None:
                if not self._load_calib_data():
                    self.lbl_depth_status.config(text="Kalibrasyon yok!", fg=RED)
                    return
            self.depth_mode = True
            self.btn_depth.config(text="Derinlik ACIK", bg="#2d6a4f")
            self.lbl_depth_status.config(text="Aktif", fg=GREEN)
            self.lbl_depth_calib.config(text="HAZIR", fg=GREEN)
        else:
            self.depth_mode = False
            self.btn_depth.config(text="Derinlik KAPALI", bg=BORDER)
            self.lbl_depth_status.config(text="Kapali", fg=MUTED)

    def _save_depth(self):
        if not self.depth_mode:
            return
        with self.lock:
            fl = self.frame_l
            fr = self.frame_r
        if fl is None or fr is None:
            return
        rect_l = cv2.remap(fl, self.map1x, self.map1y, cv2.INTER_LINEAR)
        rect_r = cv2.remap(fr, self.map2x, self.map2y, cv2.INTER_LINEAR)
        gray_l = cv2.cvtColor(rect_l, cv2.COLOR_BGR2GRAY)
        gray_r = cv2.cvtColor(rect_r, cv2.COLOR_BGR2GRAY)
        disp = self._compute_disparity(gray_l, gray_r)
        d_max = disp.max() if disp.max() > 0 else 1
        d_norm = (disp / d_max * 255).astype(np.uint8)
        cmap_id = self.colormap_map.get(
            self.colormap_var.get(), cv2.COLORMAP_JET)
        depth_color = cv2.applyColorMap(d_norm, cmap_id)
        depth_color[disp <= 0] = [0, 0, 0]
        overlay = rect_l.copy()
        mask = disp > 0
        overlay[mask] = cv2.addWeighted(rect_l, 0.4, depth_color, 0.6, 0)[mask]

        out_dir = os.path.join(PROJECT_DIR, "output", "depth_captures")
        os.makedirs(out_dir, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        cv2.imwrite(os.path.join(out_dir, f"depth_{ts}_sol.png"), rect_l)
        cv2.imwrite(os.path.join(out_dir, f"depth_{ts}_sag.png"), rect_r)
        cv2.imwrite(os.path.join(out_dir, f"depth_{ts}_derinlik.png"), depth_color)
        cv2.imwrite(os.path.join(out_dir, f"depth_{ts}_overlay.png"), overlay)
        self.lbl_depth_status.config(text=f"Kaydedildi: {ts}", fg=GREEN)

    def _capture_4k_depth(self):
        """4K foto modu: kameralari gecici olarak 3840x2160'a cikart, tek kare cek, derinlik hesapla."""
        if self.calib_data is None:
            if not self._load_calib_data():
                self.lbl_depth_status.config(text="Kalibrasyon yok!", fg=RED)
                return

        self.lbl_depth_status.config(text="4K cekim yapiliyor...", fg=YELLOW)
        self.root.update()

        def do_4k():
            try:
                cap_l = cv2.VideoCapture(self.left_idx, cv2.CAP_MSMF)
                cap_r = cv2.VideoCapture(self.right_idx, cv2.CAP_MSMF)
                fourcc = cv2.VideoWriter_fourcc('M', 'J', 'P', 'G')
                for cap in [cap_l, cap_r]:
                    cap.set(cv2.CAP_PROP_FOURCC, fourcc)
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 3840)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 2160)

                for _ in range(3):
                    cap_l.read()
                    cap_r.read()

                ret_l, frame_l = cap_l.read()
                ret_r, frame_r = cap_r.read()
                cap_l.release()
                cap_r.release()

                if not ret_l or not ret_r:
                    self.root.after(0, lambda: self.lbl_depth_status.config(
                        text="4K cekim basarisiz!", fg=RED))
                    return

                h4k, w4k = frame_l.shape[:2]

                K1 = self.calib_data["K1"].copy()
                D1 = self.calib_data["D1"].copy()
                K2 = self.calib_data["K2"].copy()
                D2 = self.calib_data["D2"].copy()
                R1, R2 = self.calib_data["R1"], self.calib_data["R2"]
                P1, P2 = self.calib_data["P1"].copy(), self.calib_data["P2"].copy()
                calib_size = tuple(self.calib_data["image_size"])

                sx = w4k / calib_size[0]
                sy = h4k / calib_size[1]
                K1[0, :] *= sx; K1[1, :] *= sy
                K2[0, :] *= sx; K2[1, :] *= sy
                P1[0, :] *= sx; P1[1, :] *= sy
                P2[0, :] *= sx; P2[1, :] *= sy

                map1x, map1y = cv2.initUndistortRectifyMap(
                    K1, D1, R1, P1, (w4k, h4k), cv2.CV_32FC1)
                map2x, map2y = cv2.initUndistortRectifyMap(
                    K2, D2, R2, P2, (w4k, h4k), cv2.CV_32FC1)

                rect_l = cv2.remap(frame_l, map1x, map1y, cv2.INTER_LINEAR)
                rect_r = cv2.remap(frame_r, map2x, map2y, cv2.INTER_LINEAR)
                gray_l = cv2.cvtColor(rect_l, cv2.COLOR_BGR2GRAY)
                gray_r = cv2.cvtColor(rect_r, cv2.COLOR_BGR2GRAY)

                num_disp = 512
                stereo_4k = cv2.StereoSGBM_create(
                    minDisparity=0, numDisparities=num_disp, blockSize=5,
                    P1=8*3*49, P2=32*3*49, disp12MaxDiff=1,
                    uniquenessRatio=15, speckleWindowSize=200, speckleRange=2,
                    preFilterCap=63, mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY)
                stereo_4k_r = cv2.ximgproc.createRightMatcher(stereo_4k)
                wls_4k = cv2.ximgproc.createDisparityWLSFilter(stereo_4k)
                wls_4k.setLambda(8000)
                wls_4k.setSigmaColor(1.5)

                dsp_l = stereo_4k.compute(gray_l, gray_r)
                dsp_r = stereo_4k_r.compute(gray_r, gray_l)
                dsp = wls_4k.filter(dsp_l, gray_l, disparity_map_right=dsp_r)
                dsp = dsp.astype(np.float32) / 16.0
                dsp[dsp <= 0] = 0
                dsp = self._clean_disparity(dsp)

                Q4k = self.calib_data["Q"].copy()
                Q4k[0, 3] *= sx
                Q4k[1, 3] *= sy
                Q4k[2, 3] = P1[0, 0]

                d_max = dsp.max() if dsp.max() > 0 else 1
                d_norm = (dsp / d_max * 255).astype(np.uint8)
                cmap_id = self.colormap_map.get(
                    self.colormap_var.get(), cv2.COLORMAP_JET)
                depth_color = cv2.applyColorMap(d_norm, cmap_id)
                depth_color[dsp <= 0] = [0, 0, 0]
                overlay = rect_l.copy()
                mask = dsp > 0
                overlay[mask] = cv2.addWeighted(rect_l, 0.4, depth_color, 0.6, 0)[mask]

                out_dir = os.path.join(PROJECT_DIR, "output", "depth_captures")
                os.makedirs(out_dir, exist_ok=True)
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                cv2.imwrite(os.path.join(out_dir, f"4k_{ts}_sol.png"), rect_l)
                cv2.imwrite(os.path.join(out_dir, f"4k_{ts}_sag.png"), rect_r)
                cv2.imwrite(os.path.join(out_dir, f"4k_{ts}_derinlik.png"), depth_color)
                cv2.imwrite(os.path.join(out_dir, f"4k_{ts}_overlay.png"), overlay)
                cv2.imwrite(os.path.join(out_dir, f"4k_{ts}_disparity.png"), d_norm)

                self.root.after(0, lambda: self.lbl_depth_status.config(
                    text=f"4K kaydedildi: {ts} ({w4k}x{h4k})", fg=GREEN))
            except Exception as ex:
                self.root.after(0, lambda: self.lbl_depth_status.config(
                    text=f"4K hata: {ex}", fg=RED))

        import threading
        threading.Thread(target=do_4k, daemon=True).start()

    # ── Olcum ────────────────────────────────────────
    def _capture_bg(self):
        with self.lock:
            fl = self.frame_l
        if fl is not None:
            self.bg_frame_l = fl.copy()
            self.lbl_meas_bg.config(text="Kaydedildi", fg=GREEN)
            self.lbl_meas_status.config(text="Arka plan hazir, nesneyi koy ve M bas", fg=YELLOW)

    def _do_measure(self):
        if self.calib_data is None:
            if not self._load_calib_data():
                self.lbl_meas_status.config(text="Kalibrasyon yok!", fg=RED)
                return
        if self.ground_data is None:
            if os.path.exists(GROUND_PATH):
                self.ground_data = np.load(GROUND_PATH)
            else:
                self.lbl_meas_status.config(text="Zemin duzlemi yok!", fg=RED)
                return
        if self.bg_frame_l is None:
            self.lbl_meas_status.config(text="Once B ile arka plan kaydet!", fg=RED)
            return

        with self.lock:
            fl = self.frame_l
            fr = self.frame_r
        if fl is None or fr is None:
            return

        try:
            rect_l = cv2.remap(fl, self.map1x, self.map1y, cv2.INTER_LINEAR)
            rect_r = cv2.remap(fr, self.map2x, self.map2y, cv2.INTER_LINEAR)
            rect_bg = cv2.remap(self.bg_frame_l, self.map1x, self.map1y, cv2.INTER_LINEAR)

            gray_l = cv2.cvtColor(rect_l, cv2.COLOR_BGR2GRAY)
            gray_r = cv2.cvtColor(rect_r, cv2.COLOR_BGR2GRAY)
            disp = self._compute_disparity(gray_l, gray_r)

            diff = cv2.absdiff(rect_l, rect_bg)
            gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
            _, mask = cv2.threshold(gray_diff, 30, 255, cv2.THRESH_BINARY)
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                self.lbl_meas_status.config(text="Nesne bulunamadi!", fg=RED)
                return
            contour = max(contours, key=cv2.contourArea)
            if cv2.contourArea(contour) < 500:
                self.lbl_meas_status.config(text="Kontur cok kucuk!", fg=RED)
                return

            Q = self.calib_data["Q"]
            ground_n = self.ground_data["normal"].ravel()
            ground_d = float(self.ground_data["d"])

            pts_2d = contour.reshape(-1, 2)
            pts_3d = []
            for px, py in pts_2d:
                d = disp[int(py), int(px)]
                if d > 0:
                    vec = np.array([px, py, d, 1.0])
                    p = Q @ vec
                    p = p[:3] / p[3]
                    pts_3d.append(p)
            if len(pts_3d) < 10:
                self.lbl_meas_status.config(text="Yetersiz 3B nokta!", fg=RED)
                return
            pts_3d = np.array(pts_3d)

            # Zemin koordinat sistemine
            n = ground_n / np.linalg.norm(ground_n)
            arbitrary = np.array([1, 0, 0]) if abs(n[0]) < 0.9 else np.array([0, 1, 0])
            u = np.cross(n, arbitrary)
            u = u / np.linalg.norm(u)
            v = np.cross(n, u)

            proj_u = pts_3d @ u
            proj_v = pts_3d @ v
            proj_n = pts_3d @ n

            en = float(max(proj_u) - min(proj_u))
            boy = float(max(proj_v) - min(proj_v))
            yuk = float(max(proj_n) - min(proj_n))
            if en < boy:
                en, boy = boy, en

            self.lbl_meas_en.config(text=f"{en:.1f}", fg=GREEN)
            self.lbl_meas_boy.config(text=f"{boy:.1f}", fg=GREEN)
            self.lbl_meas_yuk.config(text=f"{yuk:.1f}", fg=GREEN)
            self.lbl_meas_status.config(
                text=f"Olculdu: {en:.0f} x {boy:.0f} x {yuk:.0f} mm", fg=GREEN)

            # Kutu onerisi
            try:
                import sys
                if SCRIPT_DIR not in sys.path:
                    sys.path.insert(0, SCRIPT_DIR)
                from box_output import load_boxes, suggest_boxes
                boxes = load_boxes()
                candidates = suggest_boxes(en, boy, yuk, boxes)
                if candidates:
                    best = candidates[0][1]
                    self.lbl_box_name.config(text=best["isim"], fg=ACCENT)
                    self.lbl_box_size.config(
                        text=f"{best['en_mm']}x{best['boy_mm']}x{best['yukseklik_mm']} mm", fg=FG)
                    self.lbl_box_desi.config(text=f"{best['desi']:.1f}", fg=FG)
                else:
                    self.lbl_box_name.config(text="Standart kutu yok!", fg=YELLOW)
            except Exception:
                pass

            # Deftere yaz
            now = datetime.datetime.now()
            os.makedirs(os.path.dirname(DIARY_PATH), exist_ok=True)
            exists = os.path.exists(DIARY_PATH)
            with open(DIARY_PATH, "a", encoding="utf-8") as f:
                if not exists:
                    f.write("tarih,saat,asama,parametre,ayar,deger,birim,not\n")
                f.write(f"{now.strftime('%Y-%m-%d')},{now.strftime('%H:%M')},"
                        f"olcum,en_boy_yuk,,{en:.1f}x{boy:.1f}x{yuk:.1f},mm,\n")

        except Exception as e:
            self.lbl_meas_status.config(text=f"Hata: {str(e)[:50]}", fg=RED)

    # ── Durum tab islemleri ──────────────────────────
    def _refresh_status(self):
        sq = None
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, encoding="utf-8") as f:
                cfg = json.load(f)
            sq = cfg.get("olculen_kare_boyutu_mm")
        self.status_checks["charuco"].config(
            text=f"{sq} mm" if sq else "GIRILMEDI",
            fg=GREEN if sq else RED)

        frame_count = len([f for f in os.listdir(FRAMES_DIR) if f.startswith("L_")])
        self.status_checks["frames"].config(
            text=f"{frame_count} cift" if frame_count > 0 else "YOK",
            fg=GREEN if frame_count >= 20 else YELLOW if frame_count > 0 else RED)

        has_calib = os.path.exists(CALIB_PATH)
        if has_calib:
            try:
                d = np.load(CALIB_PATH)
                rms = float(d["rms"])
                self.status_checks["calib"].config(
                    text=f"HAZIR (RMS={rms:.3f})",
                    fg=GREEN if rms < 0.4 else YELLOW)
            except Exception:
                self.status_checks["calib"].config(text="HAZIR", fg=GREEN)
        else:
            self.status_checks["calib"].config(text="YOK", fg=RED)

        has_ground = os.path.exists(GROUND_PATH)
        self.status_checks["ground"].config(
            text="HAZIR" if has_ground else "YOK",
            fg=GREEN if has_ground else RED)

        # Olcum tabindaki gostergeleri de guncelle
        if hasattr(self, "lbl_meas_calib"):
            self.lbl_meas_calib.config(
                text="HAZIR" if has_calib else "YOK", fg=GREEN if has_calib else RED)
            self.lbl_meas_ground.config(
                text="HAZIR" if has_ground else "YOK", fg=GREEN if has_ground else RED)
        if hasattr(self, "lbl_depth_calib"):
            self.lbl_depth_calib.config(
                text="HAZIR" if has_calib else "YOK", fg=GREEN if has_calib else RED)

    def _refresh_diary(self):
        self.diary_text.config(state="normal")
        self.diary_text.delete("1.0", tk.END)
        if os.path.exists(DIARY_PATH):
            with open(DIARY_PATH, encoding="utf-8") as f:
                lines = f.readlines()
            if len(lines) > 1:
                self.diary_text.insert("1.0", lines[0])
                for line in lines[-10:]:
                    self.diary_text.insert(tk.END, line)
            else:
                self.diary_text.insert("1.0", "Henuz kayit yok.")
        else:
            self.diary_text.insert("1.0", "Defter dosyasi yok.")
        self.diary_text.config(state="disabled")

    def _append_process_output(self, text):
        self.lbl_process_out.config(state="normal")
        self.lbl_process_out.insert(tk.END, text + "\n")
        self.lbl_process_out.see(tk.END)
        self.lbl_process_out.config(state="disabled")

    def _run_script(self, script_name, args=None):
        script = os.path.join(SCRIPT_DIR, script_name)
        cmd = ["python", script]
        if args:
            cmd.extend(args)
        self._append_process_output(f">>> {' '.join(cmd)}")

        def run():
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                output = result.stdout + result.stderr
                self.root.after(0, lambda: self._append_process_output(output.strip()))
                self.root.after(0, self._refresh_status)
            except subprocess.TimeoutExpired:
                self.root.after(0, lambda: self._append_process_output("ZAMAN ASIMI!"))
            except Exception as e:
                self.root.after(0, lambda: self._append_process_output(f"HATA: {e}"))

        threading.Thread(target=run, daemon=True).start()

    def _run_ground_plane(self):
        script = os.path.join(SCRIPT_DIR, "ground_plane.py")
        self._append_process_output(">>> Zemin tespiti baslatiliyor (ayri pencere)...")
        subprocess.Popen(["python", script,
                          "--left", str(self.left_idx),
                          "--right", str(self.right_idx)])

    def _run_focus_test(self):
        script = os.path.join(SCRIPT_DIR, "odak_test.py")
        self._append_process_output(">>> Odak testi baslatiliyor (ayri pencere)...")
        subprocess.Popen(["python", script,
                          "--left", str(self.left_idx),
                          "--right", str(self.right_idx)])

    def _on_close(self):
        self._save_settings()
        self.running = False
        time.sleep(0.2)
        for cap in [self.cap_l, self.cap_r]:
            if cap:
                cap.release()
        self.root.destroy()


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--left", type=int, default=1)
    p.add_argument("--right", type=int, default=2)
    args = p.parse_args()
    root = tk.Tk()
    CameraApp(root, args.left, args.right)
    root.mainloop()


if __name__ == "__main__":
    main()
