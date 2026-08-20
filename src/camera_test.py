"""
Stereo Kamera - Tam Pipeline Araci v4

Tek pencerede tum islemler:
  Tab 1: Ayarlar - cozunurluk, pozlama, gain, WB + canli degerler
  Tab 2: Hesaplama - deltaZ hesaplayici, calisma zarfi
  Tab 3: Kalibrasyon - desen tespiti, kare toplama, kalibre et
  Tab 4: Derinlik - canli disparity/derinlik haritasi
  Tab 5: Olcum - nesne olcumu + kutu onerisi
  Tab 6: Durum - pipeline durumu, olcum defteri
  Tab 7: Rehber - adim adim ne yapilacak
"""
import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import threading
import glob
import subprocess
import sys
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
    ("3840x2160 ~1fps (canli icin uygun degil)", 3840, 2160, "MJPG"),
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


class Ipucu:
    """Fareyle uzerine gelince aciklama gosteren balon.

    Neden gerekli: arayuzdeki kisaltmalar (tol, gri tol, sinir, esik)
    ne oldugunu kendiliginden anlatmiyor ve yanlis anlasilinca olcum
    bozuluyor. Ornek: "esik" bir boyut filtresi sanildi, oysa duzlem
    otelemesi - cismin altini da kesiyor.

    Tk'nin yerlesik tooltip'i yok; Toplevel + overrideredirect ile
    kuruluyor. Gecikme, farenin ustunden gecerken balon patlamasin diye.
    """

    def __init__(self, widget, metin, gecikme=450, genislik=460):
        self.widget = widget
        self.metin = metin
        self.gecikme = gecikme
        self.genislik = genislik
        self._is = None
        self._pencere = None
        widget.bind("<Enter>", self._gir, add="+")
        widget.bind("<Leave>", self._cik, add="+")
        widget.bind("<ButtonPress>", self._cik, add="+")

    def _gir(self, _=None):
        self._iptal()
        self._is = self.widget.after(self.gecikme, self._goster)

    def _cik(self, _=None):
        self._iptal()
        self._gizle()

    def _iptal(self):
        if self._is is not None:
            try:
                self.widget.after_cancel(self._is)
            except Exception:
                pass
            self._is = None

    def _goster(self):
        if self._pencere is not None:
            return
        try:
            x = self.widget.winfo_rootx() + 18
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        except Exception:
            return
        self._pencere = tk.Toplevel(self.widget)
        self._pencere.wm_overrideredirect(True)
        try:
            self._pencere.wm_attributes("-topmost", True)
        except Exception:
            pass
        cerceve = tk.Frame(self._pencere, bg=BORDER, bd=0)
        cerceve.pack()
        tk.Label(cerceve, text=self.metin, bg="#2b2b40", fg=FG,
                 font=("Segoe UI", 9), justify="left", wraplength=self.genislik,
                 padx=10, pady=7).pack(padx=1, pady=1)
        # ekrandan tasmasin
        self._pencere.update_idletasks()
        gen = self._pencere.winfo_width()
        ekran = self._pencere.winfo_screenwidth()
        if x + gen > ekran - 10:
            x = max(10, ekran - gen - 10)
        self._pencere.wm_geometry(f"+{int(x)}+{int(y)}")

    def _gizle(self):
        if self._pencere is not None:
            try:
                self._pencere.destroy()
            except Exception:
                pass
            self._pencere = None


def ipucu(widget, metin):
    """Kisayol: bir bilesene aciklama balonu bagla."""
    Ipucu(widget, metin)
    return widget


def soru(parent, metin, bg=None):
    """Yanina konulan kucuk '?' isareti - uzerine gelince aciklama."""
    lbl = tk.Label(parent, text="?", bg=bg or CARD, fg=ACCENT,
                   font=("Segoe UI", 9, "bold"), cursor="question_arrow")
    Ipucu(lbl, metin)
    return lbl


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
        detector = cv2.aruco.CharucoDetector(board)
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
        self.entry.insert(0, self._fmt(var.get()))
        self.entry.bind("<Return>", self._on_entry)
        self.entry.bind("<FocusOut>", self._on_entry)

        # Degisken disaridan set() edilirse (ayar yukleme, sifirlama,
        # kalibrasyondan otomatik doldurma) kutu metni de takip etsin
        var.trace_add("write", self._sync_entry)

    def _fmt(self, val):
        return str(int(float(val))) if self.res >= 1 else f"{float(val):.2f}"

    def _sync_entry(self, *_):
        try:
            new = self._fmt(self.var.get())
        except (ValueError, tk.TclError):
            return
        if self.entry.get() != new:
            self.entry.delete(0, tk.END)
            self.entry.insert(0, new)

    def _on_scale(self, val):
        self.entry.delete(0, tk.END)
        self.entry.insert(0, self._fmt(val))
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
        self.root.title("Stereo Kamera - Kalibrasyon Hazirlama")
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

        # Derinlik/olcum state
        self.depth_mode = False
        self._quality_frozen = False
        self.calib_data = None
        self.ground_data = None
        self.map1x = self.map1y = self.map2x = self.map2y = None
        self.stereo = None
        self.bg_frame_l = None
        self.measure_result = None
        self._click_point = None
        self._display_scale = 1.0
        self._display_fl_w = 0
        self._display_fl_h = 0
        self._display_off_x = 0.0
        self._display_off_y = 0.0
        self._zoom = 1.0          # goruntu yakinlastirma
        self._zoom_c = None       # yakinlastirma merkezi (birlesik koord)
        self._zoom_crop = (0, 0)  # kirpma sol-ust kosesi
        self._pre_ground_dsp = None
        # _depth_olcum yalnizca _depth_worker calisinca olusuyordu;
        # derinlik hic acilmadan "Zemin tespit et" denince
        # AttributeError veriyor ve tespit tamamen basarisiz oluyordu.
        # Burada tanimlanarak kok neden kapatildi.
        self._depth_olcum = None
        self._son_olcum = None
        self._bekleyen = {}
        self._current_dsp = None
        # Derinlik ayri thread'de hesaplanir (ana thread donmesin)
        self._depth_lock = threading.Lock()
        self._depth_result = None
        self._depth_thread = None
        self._raw_disp = None
        self._last_raw_mask = None
        self._last_quality = ""
        self._num_disp = 256          # disparity arama araligi (yakin sinir)
        self._min_disp = 0            # arama penceresinin BASLANGICI
        self._sgbm_cache = {}

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
        self.cam_label.bind("<Button-1>", self._on_cam_click)
        self.cam_label.bind("<MouseWheel>", self._on_cam_wheel)
        self.cam_label.bind("<Double-Button-1>", self._on_cam_double)

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

    def _kaydirilabilir(self, tab):
        """Sekmeyi kaydirilabilir yap; icerik cercevesini dondur.

        Tekerlek baglantisi <Enter>/<Leave> ile bind_all uzerinden
        yapilir. Yalnizca canvas ve ic cerceveye baglamak YETMIYOR:
        fare bir butonun/etiketin uzerindeyken olay o widget'a gidiyor
        ve kaydirma calismiyor ("bazi yerlerde scroll yok" sikayeti).
        bind_all, imlec sekmenin herhangi bir yerindeyken calisir.
        """
        canvas = tk.Canvas(tab, bg=CARD, highlightthickness=0)
        cubuk = tk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        sf = tk.Frame(canvas, bg=CARD)
        sf.bind("<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=sf, anchor="nw", tags="sf")
        canvas.configure(yscrollcommand=cubuk.set)
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig("sf", width=e.width))
        cubuk.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        def tekerlek(e):
            # Icerik sigiyorsa kaydirma - yoksa sayfa titrer
            ilk, son = canvas.yview()
            if ilk <= 0.0 and son >= 1.0:
                return
            canvas.yview_scroll(-1 * (e.delta // 120), "units")

        def gir(_=None):
            canvas.bind_all("<MouseWheel>", tekerlek)

        def cik(_=None):
            canvas.unbind_all("<MouseWheel>")

        for w in (canvas, sf):
            w.bind("<Enter>", gir)
            w.bind("<Leave>", cik)
        return sf

    def _section(self, parent, title, katlanabilir=False, acik=True):
        """Bolum basligi + icerik cercevesi.

        katlanabilir=True ise baslik tiklanabilir olur ve icerik
        gizlenebilir. Nadiren degistirilen ayarlar gorunumu doldurmaz.

        DIKKAT: icerik cercevesinin MASTER'i sarmalayicidir. Once
        parent'a bagli bir cerceve yapip `pack(in_=sarmal)` demek
        calismiyor - Tk widget'i sarmalayicinin ARKASINA cizer; yer
        kaplar ama gorunmez. (winfo_ismapped() yine True doner, yani
        "haritalanmis" testi bu hatayi yakalamaz.)
        """
        f = tk.Frame(parent, bg=CARD)
        f.pack(fill=tk.X, padx=8, pady=(10, 0))

        if not katlanabilir:
            tk.Label(f, text=title, bg=CARD, fg=ACCENT,
                     font=("Segoe UI", 11, "bold")).pack(anchor="w")
            tk.Frame(f, bg=BORDER, height=1).pack(fill=tk.X, pady=(4, 0))
            content = tk.Frame(parent, bg=CARD)
            content.pack(fill=tk.X, padx=8, pady=(4, 0))
            return content

        durum = {"acik": acik}
        lbl = tk.Label(f, text="", bg=CARD, fg=ACCENT, cursor="hand2",
                       font=("Segoe UI", 11, "bold"))
        lbl.pack(anchor="w")
        tk.Frame(f, bg=BORDER, height=1).pack(fill=tk.X, pady=(4, 0))

        # Sarmalayici hep pakette -> bolumun sekmedeki YERI sabit kalir.
        sarmal = tk.Frame(parent, bg=CARD)
        sarmal.pack(fill=tk.X)
        content = tk.Frame(sarmal, bg=CARD)      # MASTER = sarmal

        def ciz():
            lbl.config(text=("\u25be  " if durum["acik"] else "\u25b8  ") + title)
            if durum["acik"]:
                content.pack(fill=tk.X, padx=8, pady=(4, 0))
                sarmal.pack_propagate(True)  # boyut cocuktan gelsin
            else:
                content.pack_forget()
                # Tk cercevesi cocuklari kaldirilinca ISTENEN
                # boyutunu KORUR (olculdu: reqheight 105'te
                # kaliyor). Bosaltmak yetmiyor, yukseklik
                # acikca sifirlanmali - yoksa kapali bolum
                # kocaman bir bosluk birakiyor.
                sarmal.configure(height=1)

        def degistir(_=None):
            durum["acik"] = not durum["acik"]
            ciz()

        lbl.bind("<Button-1>", degistir)
        ciz()
        return content

    @staticmethod
    def _key_guard(action):
        """Kisayol tusu - Entry/Text icine yaziliyorsa tetiklenmez."""
        def handler(event):
            if isinstance(event.widget, (tk.Entry, ttk.Entry, tk.Text)):
                return
            action()
        return handler

    def _info_row(self, parent, label, value="", color=FG):
        row = tk.Frame(parent, bg=CARD)
        row.pack(fill=tk.X, pady=2)
        tk.Label(row, text=label, bg=CARD, fg=MUTED,
                 font=("Segoe UI", 10), anchor="w").pack(side=tk.LEFT)
        lbl = tk.Label(row, text=value, bg=CARD, fg=color,
                        font=("Consolas", 11, "bold"), anchor="e")
        lbl.pack(side=tk.RIGHT)
        return lbl

    # â”€â”€ Tab: Ayarlar â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _build_tab_settings(self):
        tab = tk.Frame(self.notebook, bg=CARD)
        self.notebook.add(tab, text="  Ayarlar  ")

        sf = self._kaydirilabilir(tab)

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
        tk.Label(c, text=("SAG kameraya uygulanir:  sag = sol + telafi\n"
                          "0 = iki kamera ayni ayarda (varsayilan)"),
                 bg=CARD, fg=MUTED, font=("Segoe UI", 9),
                 justify="left").pack(anchor="w")
        self.exp_offset_r = tk.IntVar(value=0)
        self.gain_offset_r = tk.DoubleVar(value=0)
        self.bright_offset_r = tk.IntVar(value=0)
        SpinSlider(c, "Pozlama telafi", self.exp_offset_r, -5, 5,
                    self._on_exposure, resolution=1).pack(fill=tk.X, pady=2)
        SpinSlider(c, "Gain telafi", self.gain_offset_r, -30, 30,
                    self._on_gain, resolution=1).pack(fill=tk.X, pady=2)
        SpinSlider(c, "Parlaklik telafi", self.bright_offset_r, -30, 30,
                    self._on_bright_offset, resolution=1).pack(fill=tk.X, pady=2)
        ofs_btn = tk.Frame(c, bg=CARD)
        ofs_btn.pack(fill=tk.X, pady=(4, 0))
        tk.Button(ofs_btn, text="Telafileri sifirla (0)",
                  command=self._reset_offsets,
                  bg=BORDER, fg=FG, font=("Segoe UI", 9),
                  relief="flat", padx=10, pady=3,
                  cursor="hand2").pack(side=tk.LEFT)
        tk.Button(ofs_btn, text="Otomatik esitle",
                  command=self._auto_match_cameras,
                  bg="#4a6fa5", fg="white", font=("Segoe UI", 9, "bold"),
                  relief="flat", padx=10, pady=3,
                  cursor="hand2").pack(side=tk.LEFT, padx=(6, 0))
        self.lbl_match = tk.Label(c, text="", bg=CARD, fg=MUTED,
                                  font=("Segoe UI", 8), justify="left",
                                  anchor="w")
        self.lbl_match.pack(fill=tk.X, pady=(2, 0))

        # Goruntu
        c = self._section(sf, "Goruntu")
        self.brightness_var = tk.IntVar(value=0)
        self.contrast_var = tk.IntVar(value=32)
        self.saturation_var = tk.IntVar(value=64)
        self.sharpness_var = tk.IntVar(value=3)
        # Gamma: UVC'de x100 olcek, 100 = notr (fabrika varsayilani).
        #
        # ONEMLI (2026-08-18 olculdu): Onceki notlarda "SOL kamera 200'un
        # altini reddediyor, bu yuzden 300 kullanilmali" yaziyordu. BU
        # TESHIS YANLISTI. Gamma iki kameraya da yazildiginda:
        #     gamma 300 -> parlaklik 1.18x, kontrast 1.20x  (188/159)
        #     gamma 100 -> parlaklik 1.04x, kontrast 1.02x  (127/133)
        # Yani 100 daha dengeli VE hedef parlaklik bandinin (90-150)
        # ortasinda. Gecmiste 100'de olculen buyuk fark, degerin kotu
        # olmasindan degil, gamma'nin yalnizca BIR kameraya yazilmasindan
        # kaynaklaniyordu (_apply_all eskiden gamma yazmiyordu).
        #
        # Kural: degerin kendisi degil, IKI KAMERADA AYNI olmasi onemli.
        self.gamma_var = tk.IntVar(value=100)
        SpinSlider(c, "Parlaklik", self.brightness_var, -64, 64,
                    self._on_img_prop).pack(fill=tk.X, pady=2)
        SpinSlider(c, "Kontrast", self.contrast_var, 0, 100,
                    self._on_img_prop).pack(fill=tk.X, pady=2)
        SpinSlider(c, "Doygunluk", self.saturation_var, 0, 128,
                    self._on_img_prop).pack(fill=tk.X, pady=2)
        SpinSlider(c, "Keskinlik", self.sharpness_var, 0, 10,
                    self._on_img_prop).pack(fill=tk.X, pady=2)
        SpinSlider(c, "Gamma (100=notr)", self.gamma_var, 72, 500,
                    self._on_img_prop).pack(fill=tk.X, pady=2)
        tk.Label(c, text="Onemli olan degerin kendisi degil, iki kamerada AYNI "
                         "olmasi. Olculdu: 100 -> 1.04x, 300 -> 1.18x. "
                         "Onerilen: 100. Degistirdikten sonra "
                         "'Ayarlari kameraya yeniden yaz'.",
                 bg=CARD, fg=MUTED, font=("Segoe UI", 8),
                 justify="left", anchor="w", wraplength=380).pack(fill=tk.X)

        # Kamera saglik kontrolu
        c = self._section(sf, "Kamera saglik kontrolu")
        tk.Label(c, text=(
            "MSMF'de cap.get() YALAN SOYLER - ne yazarsan yaz sabit deger\n"
            "doner. Bu yuzden ayarlarin dogru islendigi ancak GORUNTU\n"
            "olculerek anlasilir. Iki kamera ozdes (olculdu 1.02x), buyuk\n"
            "fark = bir ayar iki kameraya farkli islenmis demektir."
        ), bg=CARD, fg=MUTED, font=("Segoe UI", 8),
                 justify="left").pack(anchor="w", pady=(0, 4))
        hrow = tk.Frame(c, bg=CARD)
        hrow.pack(fill=tk.X, pady=2)
        tk.Button(hrow, text="Ayarlari kameraya yeniden yaz",
                  command=self._rewrite_all_settings,
                  bg="#2d6a4f", fg="white", font=("Segoe UI", 9, "bold"),
                  relief="flat", padx=10, pady=4,
                  cursor="hand2").pack(side=tk.LEFT)
        tk.Button(hrow, text="Kontrol et",
                  command=lambda: self._check_camera_balance(sessiz=False),
                  bg=BORDER, fg=FG, font=("Segoe UI", 9),
                  relief="flat", padx=10, pady=4,
                  cursor="hand2").pack(side=tk.LEFT, padx=(6, 0))
        self.lbl_health = tk.Label(c, text="(henuz kontrol edilmedi)",
                                   bg=CARD, fg=MUTED, font=("Segoe UI", 8),
                                   justify="left", anchor="w", wraplength=380)
        self.lbl_health.pack(fill=tk.X, pady=(3, 0))

        # Canli degerler
        c = self._section(sf, "Canli degerler")
        self.lbl_fps = self._info_row(c, "FPS")
        self.lbl_net_l = self._info_row(c, "Netlik SOL")
        self.lbl_net_r = self._info_row(c, "Netlik SAG")
        self.lbl_net_ratio = self._info_row(c, "SOL/SAG orani")
        self.lbl_net_peak_l = self._info_row(c, "Tepe SOL")
        self.lbl_net_peak_r = self._info_row(c, "Tepe SAG")
        self.lbl_bright_l = self._info_row(c, "Parlaklik SOL")
        self.lbl_bright_r = self._info_row(c, "Parlaklik SAG")
        self.lbl_bright_diff = self._info_row(c, "Fark %")
        self.lbl_res_active = self._info_row(c, "Cozunurluk")
        self.lbl_format = self._info_row(c, "Format")

    # â”€â”€ Tab: Gereksinimler â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _build_tab_requirements(self):
        tab = tk.Frame(self.notebook, bg=CARD)
        self.notebook.add(tab, text="  Hesaplama  ")

        sf = self._kaydirilabilir(tab)

        c = self._section(sf, "Calisma mesafesi")
        # Z min varsayilani 300'du ama sistem numDisparities=256 ile
        # 399 mm'den yakini OLCEMEZ. Ulasilamaz bir deger icin hesap
        # yapmak yaniltici; 400'e cekildi ve asagida donanim siniri
        # ayrica gosteriliyor.
        self.z_min_var = tk.IntVar(value=400)
        self.z_max_var = tk.IntVar(value=900)
        SpinSlider(c, "Z min (mm)", self.z_min_var, 100, 1000,
                    self._calc_dz).pack(fill=tk.X, pady=2)
        SpinSlider(c, "Z max (mm)", self.z_max_var, 200, 2000,
                    self._calc_dz).pack(fill=tk.X, pady=2)
        self.lbl_zlimit = tk.Label(c, text="", bg=CARD, fg=MUTED,
                                   font=("Segoe UI", 8), justify="left",
                                   anchor="w", wraplength=380)
        self.lbl_zlimit.pack(fill=tk.X, pady=(2, 0))

        c = self._section(sf, "Hedef hassasiyet")
        self.target_var = tk.DoubleVar(value=3.0)
        SpinSlider(c, "Hedef (mm)", self.target_var, 0.5, 20,
                    self._calc_dz, resolution=0.5).pack(fill=tk.X, pady=2)

        c = self._section(sf, "Sistem parametreleri")
        self.baseline_var = tk.IntVar(value=72)
        # P1[0,0] (rektifiye odak) - K1[0,0]=1292 DEGIL. Kalibrasyon
        # yuklenince _load_calib_data() bu degeri gercek P1'den gunceller.
        self.fpx_var = tk.IntVar(value=1420)
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
            "f_px: kalibrasyondan (P1 matrisi).\n"
            "Kalibrasyon yuklenince otomatik dolar.\n\n"
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

        # DONANIM SINIRI: numDisparities kadar disparity aranabilir, daha
        # yakin cisim arama araligina sigmaz. Olculdu (f=1418.18, B=71.79):
        #   nd=128 -> 802mm   nd=256 -> 399mm   nd=384 -> 266mm
        nd = getattr(self, "_num_disp", 256)
        z_don = f * b / (nd - 1)          # mm (f px, b mm)
        if hasattr(self, "lbl_zlimit"):
            if z_min < z_don:
                self.lbl_zlimit.config(
                    text=(f"DONANIM SINIRI: numDisparities={nd} ile en yakin "
                          f"{z_don:.0f} mm olculebilir.\n"
                          f"Z min={z_min} mm ULASILAMAZ - Derinlik tabindan "
                          f"arama araligini buyut veya Z min'i yukselt."),
                    fg=RED)
            else:
                self.lbl_zlimit.config(
                    text=(f"Donanim siniri: numDisparities={nd} -> en yakin "
                          f"{z_don:.0f} mm. Z min={z_min} mm uygun."),
                    fg=MUTED)

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

    # â”€â”€ Tab: Kalibrasyon â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _build_tab_calibration(self):
        tab = tk.Frame(self.notebook, bg=CARD)
        self.notebook.add(tab, text="  Kalibrasyon  ")
        tab = self._kaydirilabilir(tab)

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

        self.root.bind("<s>", self._key_guard(self._save_frame))
        self.root.bind("<S>", self._key_guard(self._save_frame))
        self.root.bind("<c>", self._key_guard(self._toggle_calib))
        self.root.bind("<C>", self._key_guard(self._toggle_calib))
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

        # Board degisti -> pitch yeniden olculmeli, alani acik birak
        self.sq_locked = False
        self.sq_entry.config(state="normal")
        self.sq_entry.delete(0, tk.END)
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
            self.sq_status.config(text="GIRILMEDI - kumpasla olc", fg=RED)
        else:
            try:
                v = float(val)
                design = self.charuco_cfg["square_length_mm"]
                if abs(v - design) <= design * 0.15:
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
        """Aktif kareleri yedekle ve frames/ klasorunu bosalt.

        Yedege kareler + calib_result.npz + charuco_config.json +
        camera_settings.json birlikte konur. Desen tanimi (ozellikle
        OLCULEN kare boyutu) olmadan eski kareler yeniden islenemez -
        yalnizca fotograf yedeklemek geri donusu imkansiz kilar.
        """
        current = len([f for f in os.listdir(FRAMES_DIR) if f.startswith("L_")])
        if current == 0:
            self.lbl_set_info.config(
                text="Aktif sette kare yok, yedeklenecek bir sey yok")
            return
        calib_dir = os.path.dirname(FRAMES_DIR)
        # Isim CATISMASIZ uretilmeli: len(existing)+1 kullanmak, aradan
        # bir set silinmisse var olan bir klasoru hedef gosterir ve
        # copytree FileExistsError ile coker.
        damga = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        taban = f"frames_set_{damga}_{self.current_w}x{self.current_h}"
        set_name, k = taban, 2
        while os.path.exists(os.path.join(calib_dir, set_name)):
            set_name = f"{taban}_{k}"
            k += 1
        if not messagebox.askyesno(
                "Yeni Set",
                f"Mevcut {current} kare '{set_name}' olarak yedeklenecek.\n"
                f"Kareler + kalibrasyon + desen tanimi + kamera ayarlari.\n"
                f"Aktif frames/ klasoru bosaltilacak.\n\nDevam?"):
            return
        import shutil
        dest = os.path.join(calib_dir, set_name)
        shutil.copytree(FRAMES_DIR, dest)
        for kaynak, ad in ((CALIB_PATH, "calib_result.npz"),
                           (CONFIG_PATH, "charuco_config.json"),
                           (SETTINGS_PATH, "camera_settings.json")):
            if os.path.exists(kaynak):
                shutil.copy2(kaynak, os.path.join(dest, ad))
        with open(os.path.join(dest, "SET_BILGI.txt"), "w",
                  encoding="utf-8") as f:
            f.write(f"Yedek tarihi : {damga}\n"
                    f"Kare sayisi  : {current} cift\n"
                    f"Cozunurluk   : {self.current_w}x{self.current_h}\n"
                    f"Icerik       : kareler, calib_result.npz,\n"
                    f"               charuco_config.json, "
                    f"camera_settings.json\n"
                    f"Geri yukleme : Kalibrasyon tabi > 'Eski Seti Yukle'\n")
        for f in os.listdir(FRAMES_DIR):
            os.remove(os.path.join(FRAMES_DIR, f))
        self.save_count = 0
        self.lbl_saved.config(text="0 cift")
        self._update_set_info()
        self.lbl_set_info.config(
            text=f"{set_name} olarak yedeklendi "
                 f"(kareler + kalibrasyon + desen + ayarlar)", fg=GREEN)

    def _load_calib_set(self):
        """Yedeklenmis seti geri yukle - kareler VE kalibrasyon/desen."""
        calib_dir = os.path.dirname(FRAMES_DIR)
        sets = sorted([d for d in os.listdir(calib_dir)
                       if d.startswith("frames_set_") and
                       os.path.isdir(os.path.join(calib_dir, d))])
        if not sets:
            self.lbl_set_info.config(text="Yedeklenmis set yok")
            return
        import shutil
        from tkinter import simpledialog
        choice = simpledialog.askstring(
            "Set Yukle",
            f"Mevcut setler: {', '.join(sets)}\n\n"
            f"Yuklemek istedigin set adini yaz:\n(ornek: {sets[-1]})")
        if not choice or choice not in sets:
            return
        current = len([f for f in os.listdir(FRAMES_DIR) if f.startswith("L_")])
        if current > 0:
            if not messagebox.askyesno(
                    "Uyari",
                    f"Aktif sette {current} kare var.\nUstune yazilacak. "
                    f"Devam?"):
                return
        src = os.path.join(calib_dir, choice)
        # Aktif kalibrasyon/desen de degisecek - once ONLARI yedekle,
        # yoksa geri donus yolu kalmaz.
        onc = os.path.join(calib_dir, "_oncekiler")
        os.makedirs(onc, exist_ok=True)
        for yol, ad in ((CALIB_PATH, "calib_result.npz"),
                        (CONFIG_PATH, "charuco_config.json")):
            if os.path.exists(yol):
                shutil.copy2(yol, os.path.join(onc, ad))

        for f in os.listdir(FRAMES_DIR):
            os.remove(os.path.join(FRAMES_DIR, f))
        geri = []
        for f in os.listdir(src):
            kaynak = os.path.join(src, f)
            if not os.path.isfile(kaynak):
                continue
            if f == "calib_result.npz":
                shutil.copy2(kaynak, CALIB_PATH); geri.append("kalibrasyon")
            elif f == "charuco_config.json":
                shutil.copy2(kaynak, CONFIG_PATH); geri.append("desen")
            elif f == "SET_BILGI.txt" or f == "camera_settings.json":
                continue                      # bilgi/ayar dosyasi, kopyalanmaz
            else:
                shutil.copy2(kaynak, FRAMES_DIR)
        self.save_count = len([f for f in os.listdir(FRAMES_DIR)
                               if f.startswith("L_")])
        self.lbl_saved.config(text=f"{self.save_count} cift")
        self._load_calib_data()               # bellege yeniden yukle
        self._update_set_info()
        ek = (" + " + ", ".join(geri)) if geri else ""
        self.lbl_set_info.config(
            text=f"{choice} yuklendi ({self.save_count} cift{ek}). "
                 f"Onceki kalibrasyon/desen 'calibration/_oncekiler' "
                 f"klasorunde.", fg=GREEN)

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
                    [sys.executable, os.path.join(SCRIPT_DIR, "calibration.py"),
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
            # Yeni kalibrasyonu HEMEN bellege al. Aksi halde uygulama
            # eski kalibrasyonla olcmeye devam eder (sessiz hata).
            self.calib_data = None
            self._depth_result = None
            self._sgbm_cache = {}
            if self._ensure_calib_current():
                self.lbl_depth_calib.config(text="HAZIR (yeni)", fg=GREEN)
            try:
                d = np.load(CALIB_PATH)
                rms = float(d["rms"])
                bl = float(d.get("baseline_mm", 0))
                # calibration.py ile ayni olcekli limit: 0.4 px @ 960 genislik
                width = int(d["image_size"][0]) if "image_size" in d else 960
                rms_limit = 0.4 * (width / 960.0)
                color = GREEN if rms < rms_limit else YELLOW
                self.lbl_calib_status.config(
                    text=f"RMS={rms:.4f}px (limit {rms_limit:.2f})  Baseline={bl:.1f}mm",
                    fg=color)
            except Exception:
                self.lbl_calib_status.config(text="Tamamlandi", fg=GREEN)
        else:
            lines = output.strip().split('\n')
            last = lines[-1] if lines else "Bilinmeyen hata"
            self.lbl_calib_status.config(text=f"HATA: {last[:60]}", fg=RED)
        print(output)

    # â”€â”€ Tab: Derinlik â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _build_tab_depth(self):
        tab = tk.Frame(self.notebook, bg=CARD)
        self.notebook.add(tab, text="  Derinlik  ")
        tab = self._kaydirilabilir(tab)

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

        self.qframes_var = tk.IntVar(value=10)
        tk.Button(btn_row, text="Kaliteli Tek Kare [F]", command=self._capture_quality_frame,
                  bg="#6a2d4f", fg="white", font=("Segoe UI", 10, "bold"),
                  relief="flat", padx=14, pady=6, cursor="hand2").pack(side=tk.LEFT)
        tk.Label(btn_row, text="kare:", bg=CARD, fg=MUTED,
                 font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=(8, 2))
        tk.Spinbox(btn_row, from_=1, to=60, increment=5, width=4,
                   textvariable=self.qframes_var, bg=BG, fg=FG,
                   buttonbackground=BORDER, relief="flat",
                   font=("Segoe UI", 9)).pack(side=tk.LEFT)

        btn_row2 = tk.Frame(c, bg=CARD)
        btn_row2.pack(fill=tk.X, pady=4)
        self.clean_disp_var = tk.BooleanVar(value=True)
        self.btn_clean_disp = tk.Checkbutton(
            btn_row2, text="Post-processing (temizleme)",
            variable=self.clean_disp_var, bg=CARD, fg=FG,
            selectcolor=BORDER, activebackground=CARD, activeforeground=FG,
            font=("Segoe UI", 9))
        self.btn_clean_disp.pack(side=tk.LEFT)
        ipucu(self.btn_clean_disp,
              "Disparity haritasini temizle - uc adim sirayla:\n"
              "  1. Median 5x5: tuz-biber gurultusu\n"
              "  2. Morfolojik kapama 7x7: kucuk delikleri doldur\n"
              "  3. 500 pikselden kucuk izole bolgeleri sil\n\n"
              "Sira onemli: once nokta gurultusu gider, sonra delikler "
              "kapanir, en son izole yamalar atilir. Ters sirada kucuk "
              "gurultu yamalari birlesip 'buyuk bolge' gibi gorunurdu.")

        # CLAHE varsayilan KAPALI: 6 gercek cift uzerinde olculdu, acikken
        # derinlik haritasi parcalaniyor (sicrama 0.361 -> 0.419, >2px %1.5 -> %2.1).
        # Duz yuzeylerde gurultuyu yukselterek sahte doku/sahte eslesme uretiyor.
        self.clahe_var = tk.BooleanVar(value=False)
        cb_clahe = tk.Checkbutton(
            btn_row2, text="CLAHE (kontrast art. - harita parcalanir)",
            variable=self.clahe_var, bg=CARD, fg=FG,
            selectcolor=BORDER, activebackground=CARD, activeforeground=FG,
            font=("Segoe UI", 9))
        cb_clahe.pack(side=tk.LEFT, padx=(12, 0))
        ipucu(cb_clahe,
              "Yerel kontrast artirma. VARSAYILAN KAPALI - acmak haritayi "
              "genelde BOZAR.\n\n"
              "Neden: duz ve dokusuz yuzeylerde (duvar, masa) CLAHE'nin "
              "yukselttigi sey sensor GURULTUSUDUR. SGBM bunu gercek doku "
              "sanip sahte eslesme uretir.\n\n"
              "Olculdu (6 gercek stereo cift, ayni veri):\n"
              "  kapali    -> sicrama 0.361 | >2px %1.5\n"
              "  CLAHE 1.0 -> 0.399 | %1.9\n"
              "  CLAHE 2.0 -> 0.419 | %2.1\n\n"
              "Merkez mesafe degeri etkilenmiyor; bozulan haritanin "
              "butunlugu, yani kontur/hacim tabanli olcum.")

        # Iki kameranin ton egrileri donanimsal olarak farkli (olculdu:
        # SOL p5=92/std=38.6, SAG p5=47/std=63.3). Dogrusal mean/std transferi
        # bu dogrusal-olmayan farki duzeltemez; histogram (CDF) eslemesi duzeltir.
        # Olcum: ton farki 27.8 -> 1.0, harita sicramasi 0.367 -> 0.249.
        btn_row3 = tk.Frame(c, bg=CARD)
        btn_row3.pack(fill=tk.X, pady=2)
        IP_TON = ("Iki kameranin parlaklik/ton farkini esitle.\n\n"
                  "Gerekli, cunku iki kameranin ton egrisi DONANIMSAL "
                  "olarak farkli (olculdu: SOL p5=92/std=38.6, "
                  "SAG p5=47/std=63.3). SGBM ayni noktayi iki goruntude "
                  "ayni parlaklikta gormezse eslestiremez.\n\n"
                  "Olculdu (gercek cift):\n"
                  "  Yok       -> ton farki 46.80 | sicrama 0.964\n"
                  "  Dogrusal  -> 4.60 | 0.799   (mean/std transferi)\n"
                  "  Histogram -> 0.20 | 0.795   (CDF eslemesi)\n\n"
                  "Dogrusal yontem ortalamayi esitler ama DAGILIM farkini "
                  "birakir; fark dogrusal olmadigi icin histogram gerekli.")
        lbl_ton = tk.Label(btn_row3, text="Kamera ton eslemesi:", bg=CARD,
                           fg=FG, font=("Segoe UI", 9))
        lbl_ton.pack(side=tk.LEFT)
        ipucu(lbl_ton, IP_TON)
        soru(btn_row3, IP_TON).pack(side=tk.LEFT, padx=(3, 0))
        self.tone_var = tk.StringVar(value="histogram")
        for deger, etiket in (("histogram", "Histogram (onerilen)"),
                              ("dogrusal", "Dogrusal"),
                              ("yok", "Yok")):
            tk.Radiobutton(btn_row3, text=etiket, variable=self.tone_var,
                           value=deger, bg=CARD, fg=FG, selectcolor=BORDER,
                           activebackground=CARD, activeforeground=FG,
                           font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=3)

        c = viz_c = self._section(tab, "Gorsellestirme ve gelismis",
                                  katlanabilir=True, acik=False)

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

        # Renk olcegi. Varsayilan "otomatik" her karenin kendi maksimumuna gore
        # olcekler - birkac bozuk piksel maksimumu yukseltince tum sahne koyuya
        # ezilir ve renkler kareler arasi karsilastirilamaz. "Sabit" secenegi
        # Hesaplama tabindaki Z_min/Z_max araligini kullanir.
        # Canli onizleme cozunurlugu. Olculdu (2048x1536):
        #   1.00 -> 1035 ms   0.75 -> 364 ms   0.50 -> 121 ms   0.35 -> 49 ms
        # Mesafe sonucu ayni cikiyor; kaybedilen alt-piksel hassasiyeti.
        # Rektifikasyon HER ZAMAN tam cozunurlukte yapilir, kalibrasyon bozulmaz.
        # Disparity arama araligi = yakin mesafe sinirini belirler.
        # Olculdu (f=1418.18 px, B=71.79 mm, 2048x1536):
        #   nd=128 -> 802mm,  6.2% olu kenar,  529 ms
        #   nd=256 -> 399mm, 12.5% olu kenar, 1002 ms   (varsayilan)
        #   nd=384 -> 266mm, 18.8% olu kenar, 1760 ms
        # Hassasiyeti BOZMAZ (deltaZ = Z^2*dd/(f*B) degismiyor),
        # sadece yavaslatir ve sol kenarda olu bant buyur.
        nd_row = tk.Frame(c, bg=CARD)
        nd_row.pack(fill=tk.X, pady=4)
        tk.Label(nd_row, text="Arama araligi:", bg=CARD, fg=FG,
                 font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self.numdisp_var = tk.StringVar(value="256")
        for d, e in (("128", "128 (>80cm)"), ("256", "256 (>40cm)"),
                     ("384", "384 (>27cm)")):
            tk.Radiobutton(nd_row, text=e, variable=self.numdisp_var, value=d,
                           command=self._on_numdisp_change,
                           bg=CARD, fg=FG, selectcolor=BORDER,
                           activebackground=CARD, activeforeground=FG,
                           font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=3)
        # SGBM [minDisparity, minDisparity+numDisparities) araligini tarar.
        # minDisparity'yi buyutmek pencereyi YAKINA kaydirir ve maliyeti
        # ARTIRMAZ (maliyet numDisparities ile orantili). Bedeli uzak
        # ucu kaybetmek ve olu bandin genislemesi.
        #   md=0   nd=256 -> 399 mm .. sonsuz, olu %12.5, 1.0x
        #   md=128 nd=256 -> 266 mm .. 795 mm, olu %18.8, 1.0x
        #   md=192 nd=256 -> 228 mm .. 530 mm, olu %21.9, 1.0x
        #   md=0   nd=384 -> 266 mm .. sonsuz, olu %18.8, 1.5x
        md_row = tk.Frame(c, bg=CARD)
        md_row.pack(fill=tk.X, pady=4)
        tk.Label(md_row, text="Arama basi (yakina kaydir):", bg=CARD, fg=FG,
                 font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self.mindisp_var = tk.StringVar(value="0")
        for d, e in (("0", "0 (uzak dahil)"), ("128", "128"), ("192", "192")):
            tk.Radiobutton(md_row, text=e, variable=self.mindisp_var, value=d,
                           command=self._on_numdisp_change,
                           bg=CARD, fg=FG, selectcolor=BORDER,
                           activebackground=CARD, activeforeground=FG,
                           font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=3)
        self.lbl_numdisp = tk.Label(c, text="", bg=CARD, fg=MUTED,
                                    font=("Segoe UI", 8), justify="left",
                                    anchor="w", wraplength=380)
        self.lbl_numdisp.pack(fill=tk.X)

        dsc_row = tk.Frame(c, bg=CARD)
        dsc_row.pack(fill=tk.X, pady=4)
        tk.Label(dsc_row, text="Canli hiz:", bg=CARD, fg=FG,
                 font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self.dscale_var = tk.StringVar(value="0.5")
        for d, e in (("1.0", "Tam (yavas)"), ("0.5", "Yari (onerilen)"),
                     ("0.35", "Hizli")):
            tk.Radiobutton(dsc_row, text=e, variable=self.dscale_var, value=d,
                           bg=CARD, fg=FG, selectcolor=BORDER,
                           activebackground=CARD, activeforeground=FG,
                           font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=3)
        tk.Label(c, text=(
            "Yari/hizli olcek yalnizca ONIZLEME icindir - nisan almak ve\n"
            "sahneyi gormek icin. Olculdu: kucultme tek bir cekimde 566 mm\n"
            "yerine 904 mm verdi (%60 sapma), cunku eslesmeyi saglayan ince\n"
            "yapi kayboluyor. Bu yuzden onizlemedeyken [V] dogrulama\n"
            "REDDEDILIR; olcum her zaman TAM cozunurluklu [F] ile alinir."),
                 bg=CARD, fg=MUTED, font=("Segoe UI", 8),
                 justify="left").pack(anchor="w")

        scale_row = tk.Frame(c, bg=CARD)
        scale_row.pack(fill=tk.X, pady=4)
        tk.Label(scale_row, text="Renk olcegi:", bg=CARD, fg=FG,
                 font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self.cscale_var = tk.StringVar(value="sabit")
        for d, e in (("sabit", "Sabit (Z_min..Z_max) - karsilastirilabilir"),
                     ("otomatik", "Otomatik (kare bazli)")):
            tk.Radiobutton(scale_row, text=e, variable=self.cscale_var, value=d,
                           bg=CARD, fg=FG, selectcolor=BORDER,
                           activebackground=CARD, activeforeground=FG,
                           font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=3)

        # Zemin cikarma GORSELLESTIRME degil, olcum hazirligidir -
        # katlanabilir bolumun icinde kalmamali, her zaman gorunsun.
        c = self._section(tab, "Zemin duzlemi (olcum icin)")
        # Duzlem: n·X + d = 0  ->  bir noktanin yuksekligi h = n·X + d
        zem_row = tk.Frame(c, bg=CARD)
        zem_row.pack(fill=tk.X, pady=4)
        self.ground_var = tk.BooleanVar(value=False)
        cb_zem = tk.Checkbutton(zem_row, text="Zemin/masa cikar (OLCUM icin)",
                                variable=self.ground_var, bg=CARD, fg=FG,
                                selectcolor=BORDER, activebackground=CARD,
                                activeforeground=FG, font=("Segoe UI", 9))
        cb_zem.pack(side=tk.LEFT)
        ipucu(cb_zem,
              "Kayitli zemin duzlemine YAKIN pikselleri haritadan sil.\n\n"
              "Yalnizca DESTEK YUZEYINI siler, arka plani DEGIL. Genis bir "
              "sahnede duvar, raf ve oda gercekten masanin uzerindedir ve "
              "dogru sekilde korunur.\n\n"
              "Olculdu: sahnenin %11.7 kadari duzlem uzerinde, %73.1 "
              "kadari duzlemin uzerinde kaliyor.\n\n"
              "Bir GORUNTULEME modu degil, OLCUM aracidir - acikken "
              "haritanin buyuk kismi silinir. Olcum yapacaginda ac.")
        IP_ESIK = ("Kesme duzleminin OTELEMESI (mm) - boyut filtresi "
                   "DEGIL. NEGATIF olabilir.\n\n"
                   "Kesme duzlemi, tespit edilen duzlemden bu kadar "
                   "otelenir ve altinda kalan her sey silinir.\n\n"
                   "POZITIF: duzlem yukari cikar. Cisim masada durdugu "
                   "icin CISMIN ALT BU KADARI DA GIDER - hata degil, "
                   "tanimin kendisi. Kaybi 'zemin haritasi' secenegi "
                   "olcup geri ekler (taban geri kazanimi).\n\n"
                   "NEGATIF: duzlem asagi iner. Iki gercek sebep var:\n"
                   "  1) Tahtanin KALINLIGI - tespit edilen duzlem masa "
                   "degil tahtanin UST yuzeyidir. Tahtayi kaldirip cismi "
                   "koydugunda cismin tabani duzlemin ALTINDA kalir.\n"
                   "  2) solvePnP pozunun sapmasi (olculdu: 30-53 mm).\n\n"
                   "Ayar yontemi: masayi bos birak, zemin cikarmayi ac, "
                   "esigi masa TAM kaybolana kadar ayarla. Cismi sonra "
                   "koy.\n\n"
                   "Buyuk pozitif deger secmek zorunda kaliyorsan duzlem "
                   "kaymistir - 'Zemin tespit et' uyari veriyor mu bak.")
        lbl_es = tk.Label(zem_row, text="esik (mm):", bg=CARD, fg=MUTED,
                          font=("Segoe UI", 8))
        lbl_es.pack(side=tk.LEFT, padx=(10, 2))
        ipucu(lbl_es, IP_ESIK)
        self.ground_th_var = tk.IntVar(value=12)
        # Duzlemi solvePnP yerine tahtanin stereo derinliginden uydur.
        # VARSAYILAN KAPALI - mevcut davranis degismesin. Acik/kapali
        # farki her tespitte durum satirinda yan yana gosterilir.
        self.ground_derinlik_var = tk.BooleanVar(value=False)
        sp_es = tk.Spinbox(zem_row, from_=-60, to=100, width=4,
                           textvariable=self.ground_th_var, bg=INPUT_BG,
                           fg=YELLOW, font=("Consolas", 9), relief="flat",
                           buttonbackground=BORDER)
        sp_es.pack(side=tk.LEFT)
        ipucu(sp_es, IP_ESIK)
        soru(zem_row, IP_ESIK).pack(side=tk.LEFT, padx=(2, 0))
        # Bu satir da tek basina tasiyordu (678 / 671 px olculdu);
        # kutucuklar ve buton ikinci satira aliniyor.
        zem_row2 = tk.Frame(c, bg=CARD)
        zem_row2.pack(fill=tk.X, pady=(0, 2))
        zem_row = zem_row2
        self.ground_clean_var = tk.BooleanVar(value=True)
        cb_mt = tk.Checkbutton(zem_row, text="maske temizle",
                               variable=self.ground_clean_var,
                               bg=CARD, fg=FG, selectcolor=BG,
                               activebackground=CARD, activeforeground=FG,
                               font=("Segoe UI", 8))
        cb_mt.pack(side=tk.LEFT, padx=(8, 0))
        ipucu(cb_mt,
              "Zemin cikarildiktan sonra kalan maskeyi toparla: kapama "
              "(cisimdeki ince catlaklar), acma (masadan kalan benekler), "
              "delik doldurma.\n\n"
              "Gerekli, cunku cismin dokusuz yuzeylerinde gercek eslesme "
              "yoktur; WLS oralari cevreden TAHMIN ederek doldurur ve "
              "tahmin duzleme yakin duserse piksel yanlislikla zemin "
              "sayilip silinir - cisim delik delik cikar.")
        cb_gd = tk.Checkbutton(zem_row, text="derinlikten uydur",
                               variable=self.ground_derinlik_var,
                               bg=CARD, fg=FG, selectcolor=BG,
                               activebackground=CARD, activeforeground=FG,
                               font=("Segoe UI", 8))
        cb_gd.pack(side=tk.LEFT, padx=(8, 0))
        ipucu(cb_gd,
              "Duzlemi solvePnP yerine TAHTANIN STEREO DERINLIGINDEN "
              "uydur.\n\n"
              "SORUN: duz bir desende solvePnP'nin iki matematiksel "
              "cozumu vardir ve secim zayif kalabiliyor. Olculdu: secim "
              "gerekcesi 'derinlik uyumu %12 vs %6' iken duzlem gercek "
              "masaya gore 7.8 derece EGIK ve 30-53 mm havada cikti. "
              "Egim esikle telafi edilemez.\n\n"
              "BU YONTEMDE:\n"
              "  iki-kokluluk yok, tek cozum\n"
              "  kare olcusune bagimli degil\n"
              "  zaten derinlikle ayni cercevede\n"
              "  96 kose yerine on binlerce noktaya uyuyor\n\n"
              "SARTI: tahtanin uzerinde saglam disparity olmali. "
              "ChArUco siyah-beyaz kareli oldugu icin SGBM'nin en iyi "
              "calistigi durumdur.\n\n"
              "Kapali olsa bile her tespitte iki yontem yan yana "
              "olculup durum satirinda gosterilir - once oraya bakip "
              "hangisinin sahneye daha iyi oturdugunu gor.")
        btn_zt = tk.Button(zem_row, text="Zemin tespit et",
                           command=self._detect_ground_plane,
                           bg="#1a5276", fg="white",
                           font=("Segoe UI", 9, "bold"),
                           relief="flat", padx=10, pady=2, cursor="hand2")
        btn_zt.pack(side=tk.LEFT, padx=(10, 0))
        ipucu(btn_zt,
              "ChArUco tahtasindan masa duzlemini olc ve kaydet.\n\n"
              "Tahtayi cismin duracagi yuzeye DUZ yatir. Kutu/kitap "
              "uzerinde ya da elde tutarken olcersen duzlem yanlis yere "
              "oturur - kose sayisi ve izdusum hatasi yine mukemmel "
              "gorunur, hata gizli kalir.\n\n"
              "Olculdu (2026-08-20): 96 kose, izdusum 0.34 px, buna ragmen "
              "duzlem masadan 53 mm yukarida cikti ve zemin cikarma "
              "sahnenin %69 kadarini sildi.\n\n"
              "Tespit bitince sonuc sahnenin kendi duzlemiyle "
              "karsilastirilir; 15 mm'den fazla oteleme varsa KIRMIZI "
              "uyari cikar.")
        self.lbl_ground = tk.Label(c, text="", bg=CARD, fg=MUTED,
                                   font=("Segoe UI", 8), justify="left",
                                   anchor="w", wraplength=380)
        self.lbl_ground.pack(fill=tk.X)

        # Konturlar ve ham/WLS karsilastirma GORSELLESTIRMEDIR - zemin
        # bolumune dusmustu, katlanan bolume geri aliniyor.
        viz_row = tk.Frame(viz_c, bg=CARD)
        viz_row.pack(fill=tk.X, pady=4)
        self.contour_var = tk.BooleanVar(value=False)
        cb_kont = tk.Checkbutton(viz_row, text="Derinlik konturlari",
                                 variable=self.contour_var, bg=CARD, fg=FG,
                                 selectcolor=BORDER, activebackground=CARD,
                                 activeforeground=FG, font=("Segoe UI", 9))
        cb_kont.pack(side=tk.LEFT, padx=(0, 12))
        ipucu(cb_kont,
              "Esit derinlik cizgilerini haritanin uzerine ciz (harita "
              "seviyesi 30..230 arasi 8 kademe).\n\n"
              "Yalnizca gorsel: yuzeyin egimini ve derinlik sicramalarini "
              "gozle gormeyi kolaylastirir. Olcume girmez.")
        self.compare_var = tk.BooleanVar(value=False)
        cb_hw = tk.Checkbutton(viz_row, text="Ham / WLS karsilastir",
                               variable=self.compare_var, bg=CARD, fg=FG,
                               selectcolor=BORDER, activebackground=CARD,
                               activeforeground=FG, font=("Segoe UI", 9))
        cb_hw.pack(side=tk.LEFT)
        ipucu(cb_hw,
              "Sag panelin SOL yarisi ham SGBM, SAG yarisi WLS filtreli "
              "sonuc olsun.\n\n"
              "Neden onemli: WLS bosluklari INTERPOLASYONLA doldurur. "
              "Bu yuzden 'dolgulu %' bir kalite olcusu DEGILDIR - %100 "
              "yazarken haritanin buyuk kismi tahmin olabilir. Gercek "
              "olcut ham eslesme oranidir.\n\n"
              "Ham tarafta genis siyah alanlar goruyorsan orada gercek "
              "eslesme yok demektir; oradan alinan olcume guvenme.")

        c = self._section(tab, "Mesafe dogrulama [V]")
        vrow = tk.Frame(c, bg=CARD)
        vrow.pack(fill=tk.X, pady=4)
        tk.Label(vrow, text="Gercek mesafe:", bg=CARD, fg=FG,
                 font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self.verify_entry = tk.Entry(vrow, width=8, font=("Segoe UI", 10),
                                      bg=BORDER, fg=FG, insertbackground=FG)
        self.verify_entry.pack(side=tk.LEFT, padx=6)
        tk.Button(vrow, text="Dogrula [V]", command=self._verify_distance,
                  bg="#4a6fa5", fg="white", font=("Segoe UI", 9, "bold"),
                  relief="flat", padx=10, pady=4, cursor="hand2").pack(side=tk.LEFT, padx=4)
        self.lbl_verify_result = tk.Label(c, text="", bg=CARD, fg=MUTED,
                                           font=("Consolas", 9), justify="left")
        self.lbl_verify_result.pack(fill=tk.X, pady=2)

        c = self._section(tab, "Bilgi")
        self.lbl_depth_status = self._info_row(c, "Durum")
        self.lbl_depth_center = self._info_row(c, "Merkez mesafe")
        self.lbl_depth_calib = self._info_row(c, "Kalibrasyon")

        has_calib = os.path.exists(CALIB_PATH)
        self.lbl_depth_calib.config(
            text="HAZIR" if has_calib else "YOK - once kalibre et",
            fg=GREEN if has_calib else RED)

        c = self._section(tab, "Renk skalasi")
        self.lbl_cmap_desc = tk.Label(c, text="", bg=CARD, fg=MUTED,
                                       font=("Segoe UI", 9), justify="left")
        self.lbl_cmap_desc.pack(fill=tk.X, pady=4)
        self.colormap_var.trace_add("write", lambda *_: self._update_cmap_desc())
        self.compare_var.trace_add("write", lambda *_: self._update_cmap_desc())
        self._update_cmap_desc()

        # Entry'ye yazarken tetiklenmemeli (orn. dogrulama alanina "60cm" yazmak)
        for key, action in (("d", self._save_depth), ("D", self._save_depth),
                            ("f", self._capture_quality_frame),
                            ("F", self._capture_quality_frame),
                            ("v", self._verify_distance),
                            ("V", self._verify_distance),
                            ("r", self._reset_click_point),
                            ("R", self._reset_click_point)):
            self.root.bind(f"<{key}>", self._key_guard(action))

    # â”€â”€ Tab: Olcum â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _build_tab_measure(self):
        tab = tk.Frame(self.notebook, bg=CARD)
        self.notebook.add(tab, text="  Olcum  ")
        tab = self._kaydirilabilir(tab)

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
        self.pca_sinir_var = tk.IntVar(value=250)
        self.pca_tol_var = tk.IntVar(value=30)
        # VARSAYILAN KAPALI. Olculdu: bolge derinlik TOLERANSIYLA
        # buyudugu icin zaten ince bir derinlik dilimidir - yani tanimi
        # geregi neredeyse DUZLEMDIR. RANSAC bu yuzden her seferinde
        # %69-100 "duzlem" buluyor ve cismin kendisini siliyor; termosun
        # tam merkezine tiklandiginda bile "destek yuzeyinde" diyor.
        # Fikir yalnizca bolge derinlikce kalin oldugunda anlamli.
        self.pca_gri_var = tk.IntVar(value=35)
        # KENAR ve BASAMAK engelleri: 'gri tol' bir SEVIYE esigidir ve
        # cisme bagimlidir. Bu ikisi cismin SINIRINI duvar yapar, icini
        # serbest birakir. Ikisi de VARSAYILAN KAPALI - mevcut davranis
        # degismesin diye.
        self.pca_kenar_var = tk.IntVar(value=0)
        self.pca_basamak_var = tk.DoubleVar(value=0.0)
        # YUKSEKLIK KRITERI: derinlik toleransi yerine "duzlemden en az
        # su kadar yukarida" olcutu. Ayakta duran cisme TEPEDEN
        # bakildiginda sart - uzun eksen bakis dogrultusuna dondugu icin
        # derinlik toleransi cismin ancak bir dilimini kapsar.
        # Olculdu (q_20260820_110729, ayakta sise, tikla 1049,581):
        #   derinlik toleransi tol 15/30/60 -> 65 / 83 / 158 mm
        #   yukseklik kriteri  h 15/25, yanal 45/70 -> 248 / 247 / 248 / 247
        # VARSAYILAN KAPALI (0).
        self.pca_yukseklik_var = tk.IntVar(value=0)
        # WATERSHED: iyi kenarlari kapali cevrit gerektirmeden kullanir.
        # Zemin duzlemi GEREKMEZ - yukseklik kriterinin tek dezavantaji
        # buydu. Olculdu (ayakta sise, gercek 250x72): 248.9 x 75.9 mm,
        # kapsam %99 / saflik %93, dort farkli ayarda ayni.
        # VARSAYILAN KAPALI (0).
        self.pca_watershed_var = tk.IntVar(value=0)
        self.pca_duzlem_var = tk.BooleanVar(value=False)
        # Kutu gorselini ZEMIN CIKARILMIS haritadan uret. Olculdu
        # (q_20260819_170641, termos 250x72x36, tikla 1373,1045):
        #   ham harita     tol 20 -> 263x68 | tol 60 -> 263x70
        #                  parlaklik kisiti kapaliyken 362x324 (masaya kacti)
        #   zemin haritasi tol 20 -> 254x68 | tol 60 -> 254x70
        #                  parlaklik kisiti kapaliyken bile 254x69
        # Zemin cikarma bolgenin masaya sizmasini FIZIKSEL olarak
        # engelledigi icin sonuc tol/parlaklik ayarina duyarsiz kaliyor.
        # Esigin kestigi taban bandi duzleme kadar uzatilarak geri eklenir.
        self.pca_zemin_var = tk.BooleanVar(value=False)
        tk.Button(btn_row, text="Tiklayarak olc (duzlemsiz)",
                  command=self._measure_click_pca,
                  bg="#6a4d1a", fg="white", font=("Segoe UI", 10, "bold"),
                  relief="flat", padx=12, pady=6,
                  cursor="hand2").pack(side=tk.LEFT, padx=(6, 0))
        # Butonlar tek satira sigmiyordu (sagdaki ikisi ekran disinda
        # kaliyordu). Ikinci satira tasiniyor.
        # ARAYUZ NOTU: bu bolumde 11 kontrol var ve tek satira
        # sigmiyordu - sagdaki kutular ve iki buton ekran disinda
        # kaliyordu. Dort mantiksal gruba bolundu; her grubun basinda
        # ne ise yaradigini soyleyen kucuk bir baslik var.
        def _grup(baslik_metni, ust=None):
            hedef = ust if ust is not None else c
            tk.Label(hedef, text=baslik_metni, bg=CARD, fg=ACCENT,
                     font=("Segoe UI", 8, "bold"), anchor="w"
                     ).pack(fill=tk.X, pady=(6, 0))
            f = tk.Frame(hedef, bg=CARD)
            f.pack(fill=tk.X, pady=(0, 2))
            return f

        # OLCULEN EN IYI KURULUM (2026-08-20, termos 250 x 72 mm):
        # kamera cisme YANDAN bakarken (masa duzlemi ~80 derece),
        # mesafe 550-650 mm, cisim DIK:
        #    170641  tol 15/30/60 -> 252.3 / 252.2 / 252.2  (yayilim 0.1)
        #    172145  tol 15/30/60 -> 256.8 / 256.8 / 256.8  (yayilim 0.0)
        #    172354  tol 15/30/60 -> 254.5 / 255.2 / 255.2  (yayilim 0.7)
        # Tepeden bakis ya da uzak mesafe ayni kodla bozuluyor:
        #    093039 (561 mm, tepeden) -> 270.9 / 290.5 / 310.1 (39 mm)
        #    141234 (718 mm, tepeden) -> 177.8 / 204.7 / 264.6 (87 mm)
        # Asil kazanc dogruluk degil, toleransa DUYARSIZLIK.
        rehber = tk.Label(
            c, bg=CARD, fg=GREEN, font=("Segoe UI", 8), justify="left",
            anchor="w", wraplength=620,
            text=("OLCULEN EN IYI KURULUM: kamera cisme YANDAN baksin, "
                  "mesafe 550-650 mm, cisim DIK dursun. Bu kurulumda "
                  "sonuc tolerans ayarindan bagimsiz cikiyor (yayilim "
                  "0.1 mm); tepeden bakista ya da 700 mm'de ayni kod "
                  "39-87 mm oynuyor."))
        rehber.pack(fill=tk.X, pady=(2, 0))
        ipucu(rehber,
              "Olculen sonuclar (termos, gercek 250 x 72 mm):\n\n"
              "YANDAN, 610-625 mm, cisim dik:\n"
              "   252.3 / 252.2 / 252.2 mm   (tol 15/30/60)\n"
              "   256.8 / 256.8 / 256.8 mm\n"
              "   254.5 / 255.2 / 255.2 mm\n\n"
              "TEPEDEN, 561 mm: 270.9 / 290.5 / 310.1 mm\n"
              "TEPEDEN, 718 mm: 177.8 / 204.7 / 264.6 mm\n\n"
              "Ayni kod, ayni ayarlar - fark yalnizca GEOMETRI.")

        sat_bolge = _grup("Bolge secimi - derinlik toleransi")
        btn_row2 = sat_bolge          # ilk grup bu cercevede
        IP_TOL = ("DERINLIK toleransi (mm) - disparity degil.\n\n"
                  "Tikladigin noktadan baslayan bolge, derinligi tohumdan "
                  "en fazla bu kadar farkli olan pikselleri alir. Mesafeye "
                  "gore otomatik disparity'ye cevrilir (dd = f*B*dZ/Z^2), "
                  "boylece 500 mm'de de 1500 mm'de de ayni fiziksel "
                  "kalinligi kapsar.\n\n"
                  "KUCUK: bolge cismin bir dilimini alir, olcu kucuk cikar.\n"
                  "BUYUK: bolge masaya tasar, olcu buyuk cikar.\n\n"
                  "Olculdu - yatik termos (gercek 250 mm):\n"
                  "  tol 15 -> 284 mm | tol 30 -> 308 mm\n"
                  "'zemin haritasi' isaretliyken bu duyarlilik kaybolur.")
        lbl_tol = tk.Label(btn_row2, text="tol mm:", bg=CARD, fg=MUTED,
                           font=("Segoe UI", 8))
        lbl_tol.pack(side=tk.LEFT, padx=(0, 2))
        ipucu(lbl_tol, IP_TOL)
        sp_tol = tk.Spinbox(btn_row2, from_=5, to=200, increment=5, width=4,
                            textvariable=self.pca_tol_var, bg=BG, fg=FG,
                            buttonbackground=BORDER, relief="flat",
                            font=("Segoe UI", 9))
        sp_tol.pack(side=tk.LEFT)
        ipucu(sp_tol, IP_TOL)
        soru(btn_row2, IP_TOL).pack(side=tk.LEFT, padx=(2, 0))
        IP_GRI = ("PARLAKLIK toleransi (0-255). 0 = kapali.\n\n"
                  "Derinlik tek basina cismi masadan ayiramaz - cismin "
                  "masaya degdigi yerde derinlik sicramasi yoktur. Ama "
                  "cisim ile yuzeyin RENGI genelde farklidir. Tikladigin "
                  "pikselin gri degerinden bu kadardan fazla sapan "
                  "pikseller bolgeden atilir.\n\n"
                  "Olculdu - koyu termos / beyaz masa:\n"
                  "  kapali -> 340 x 272 mm (bolge masaya kacti)\n"
                  "  45 -> 262 x 78 | 25 -> 258 x 70 | gercek 250 x 72\n\n"
                  "DIKKAT: cismin farkli yerleri farkli parlakliktaysa "
                  "(kapak, etiket, parlama) cismin bir kismini da atar. "
                  "O durumda gevset ve kenar engeline guven.")
        lbl_gri = tk.Label(btn_row2, text="gri tol:", bg=CARD, fg=MUTED,
                           font=("Segoe UI", 8))
        lbl_gri.pack(side=tk.LEFT, padx=(6, 2))
        ipucu(lbl_gri, IP_GRI)
        sp_gri = tk.Spinbox(btn_row2, from_=0, to=120, increment=5, width=4,
                            textvariable=self.pca_gri_var, bg=BG, fg=FG,
                            buttonbackground=BORDER, relief="flat",
                            font=("Segoe UI", 9))
        sp_gri.pack(side=tk.LEFT)
        ipucu(sp_gri, IP_GRI)
        soru(btn_row2, IP_GRI).pack(side=tk.LEFT, padx=(2, 0))
        IP_SINIR = ("Tiklanan noktadan 3B kus ucusu uzaklik siniri (mm).\n\n"
                    "Bolge ne kadar buyurse buyusun, tohuma bu mesafeden "
                    "uzaktaki noktalar alinmaz. Bolgenin sahnenin yarisina "
                    "yayilmasini yapisal olarak engeller.\n\n"
                    "Olculdu: sinirsizken uzun eksen 635 mm cikti, "
                    "200 mm sinirla 314 mm.\n\n"
                    "Olcecegin cismin en uzun kenarindan biraz buyuk sec; "
                    "cok kucuk secersen cismin ucunu keser.")
        lbl_sn = tk.Label(btn_row2, text="sinir:", bg=CARD, fg=MUTED,
                          font=("Segoe UI", 8))
        lbl_sn.pack(side=tk.LEFT, padx=(6, 2))
        ipucu(lbl_sn, IP_SINIR)
        sp_sn = tk.Spinbox(btn_row2, from_=80, to=800, increment=25, width=5,
                           textvariable=self.pca_sinir_var, bg=BG, fg=FG,
                           buttonbackground=BORDER, relief="flat",
                           font=("Segoe UI", 9))
        sp_sn.pack(side=tk.LEFT)
        ipucu(sp_sn, IP_SINIR)
        soru(btn_row2, IP_SINIR).pack(side=tk.LEFT, padx=(2, 0))
        # DENEYSEL: bu dort kontrol yalnizca KOTU geometride (tepeden
        # bakis, uzak mesafe) ise yariyor ve hicbiri iyi kurulumda
        # sonucu degistirmiyor - olculdu, 170641'de kenar/basamak acik
        # ve kapali sonuc ayni. Varsayilan olarak KAPALI bir bolume
        # alindi ki gunluk kullanimda gorunmesinler.
        deneysel = self._section(
            tab, "Deneysel yontemler (kotu geometri icin)",
            katlanabilir=True, acik=False)
        tk.Label(deneysel, bg=CARD, fg=MUTED, font=("Segoe UI", 8),
                 justify="left", anchor="w", wraplength=600,
                 text=("Bunlarin hicbiri iyi kurulumda sonucu "
                       "degistirmiyor (olculdu). Once geometriyi "
                       "duzelt; ancak duzeltemiyorsan buraya bak.")
                 ).pack(fill=tk.X)
        btn_row2 = _grup("Engeller - bolgenin cismin sinirini asmasini "
                         "onler", ust=deneysel)
        IP_KENAR = ("PARLAKLIK BASAMAGI engeli (|grad I|). 0 = kapali.\n\n"
                    "'gri tol' bir SEVIYE esigidir: tohumdan cok farkli "
                    "parlaklikta olan HER pikseli atar, yani cismin kendi "
                    "kapagi/etiketi farkli renkteyse onu da atar.\n\n"
                    "Kenar engeli bunun yerine yalnizca SINIRI duvar yapar: "
                    "parlaklik degisiminin buyuk oldugu pikseller "
                    "sifirlanir, bolge nesne sinirini asamaz ama cismin "
                    "ici serbest kalir.\n\n"
                    "Olculen iyi deger: 30. Daha buyuk (60-100) zayif "
                    "kenarlari kacirir, daha kucuk cismin icini boler.")
        lbl_kn = tk.Label(btn_row2, text="kenar:", bg=CARD, fg=MUTED,
                          font=("Segoe UI", 8))
        lbl_kn.pack(side=tk.LEFT, padx=(6, 2))
        ipucu(lbl_kn, IP_KENAR)
        sp_kn = tk.Spinbox(btn_row2, from_=0, to=200, increment=10, width=4,
                           textvariable=self.pca_kenar_var, bg=BG, fg=FG,
                           buttonbackground=BORDER, relief="flat",
                           font=("Segoe UI", 9))
        sp_kn.pack(side=tk.LEFT)
        ipucu(sp_kn, IP_KENAR)
        IP_BAS = ("DERINLIK BASAMAGI engeli (mm / piksel). 0 = kapali.\n\n"
                  "Tam senin istedigin sey: bolge tohumdan yayilirken "
                  "ADIM ADIM degisime bakar, degisim buyuk oldugunda "
                  "durur. Parlaklikla degil DERINLIKLE calistigi icin "
                  "cismin rengine ve buyuklugune BAGLI DEGILDIR.\n\n"
                  "Olculen |grad Z| dagilimi:\n"
                  "  duz yuzey     ~0.2 - 2 mm/px\n"
                  "  cisim siniri  10+ mm/px\n"
                  "  (masa sacilimi 1.15 mm, 26 derece egimde 0.18 mm/px)\n"
                  "Iyi deger: 3\n\n"
                  "Olculen kazanc - ORTA eksenin tol 15/30/60 yayilimi:\n"
                  "  gri35+kenar60        : 15 / 24 / 31 / 65 mm\n"
                  "  gri35+kenar30+basamak3: 3 /  0 / 12 / 31 mm\n\n"
                  "SINIR: cisim yuzeye DEGDIGI yerde basamak yoktur "
                  "(yatik silindir masaya tegettir). Tek basina yetmez, "
                  "gri veya kenar ile BIRLIKTE kullan.")
        lbl_bs = tk.Label(btn_row2, text="bas.:", bg=CARD, fg=MUTED,
                          font=("Segoe UI", 8))
        lbl_bs.pack(side=tk.LEFT, padx=(6, 2))
        ipucu(lbl_bs, IP_BAS)
        sp_bs = tk.Spinbox(btn_row2, from_=0, to=50, increment=1, width=4,
                           textvariable=self.pca_basamak_var, bg=BG, fg=FG,
                           buttonbackground=BORDER, relief="flat",
                           font=("Segoe UI", 9))
        sp_bs.pack(side=tk.LEFT)
        ipucu(sp_bs, IP_BAS)
        soru(btn_row2, IP_BAS).pack(side=tk.LEFT, padx=(2, 0))
        btn_row2 = _grup("Alternatif kriter - biri secilirse "
                         "YUKARIDAKILER KULLANILMAZ", ust=deneysel)
        IP_YUK = ("YUKSEKLIK KRITERI (mm). 0 = kapali.\n\n"
                  "Bolgeyi derinlik toleransiyla degil, 'zemin "
                  "duzleminden en az bu kadar yukarida' olcutuyle secer. "
                  "Tolerans hic kullanilmaz, dolayisiyla sonuc ona "
                  "duyarsizdir.\n\n"
                  "NE ZAMAN: cisim AYAKTA duruyor ve kamera TEPEDEN "
                  "bakiyorsa sart. O durumda cismin uzun ekseni bakis "
                  "dogrultusuna doner; tabandan tepeye derinlik surekli "
                  "degisir ve tolerans cismin ancak bir dilimini kapsar.\n\n"
                  "Olculdu (ayakta sise, tepeden, gercek ~250 mm):\n"
                  "  derinlik toleransi 15/30/60 -> 65 / 83 / 158 mm\n"
                  "  yukseklik kriteri            -> 248 / 247 / 248 / 247\n\n"
                  "Bu modda 'sinir mm' YANAL yaricap olur (duzlem "
                  "uzerinde), onerilen 45-70. Yukseklik serbest kalir.\n\n"
                  "SARTI: gecerli bir zemin duzlemi ve cismin duzlemin "
                  "uzerinde durmasi. Onerilen deger: 15-25")
        lbl_yk = tk.Label(btn_row2, text="yuks.:", bg=CARD, fg=MUTED,
                          font=("Segoe UI", 8))
        lbl_yk.pack(side=tk.LEFT, padx=(6, 2))
        ipucu(lbl_yk, IP_YUK)
        sp_yk = tk.Spinbox(btn_row2, from_=0, to=200, increment=5, width=4,
                           textvariable=self.pca_yukseklik_var, bg=BG, fg=FG,
                           buttonbackground=BORDER, relief="flat",
                           font=("Segoe UI", 9))
        sp_yk.pack(side=tk.LEFT)
        ipucu(sp_yk, IP_YUK)
        soru(btn_row2, IP_YUK).pack(side=tk.LEFT, padx=(2, 0))
        IP_WS = ("WATERSHED segmentasyonu. Deger = arka plan halkasinin "
                 "yaricapi (piksel). 0 = kapali. Onerilen 400-550.\n\n"
                 "Kenar engelleri cismin sinirini zaten cok iyi buluyor "
                 "(olculdu: siluette |grad I| 108.3, cismin icinde 5.7 - "
                 "19 kat ayrim). Ama o duvarlari floodFill'e vermek "
                 "yetmiyor: tutmasi icin duvarin HER YERDE kapali olmasi "
                 "gerekiyor ve en iyi durumda siluetin %86'si duvar "
                 "oluyor - kalan bosluktan bolge kaciyor.\n\n"
                 "Watershed'de bu sart yok; her piksel en kolay ulastigi "
                 "isaretciye atanir, tek delik her seyi bozmaz.\n\n"
                 "Olculdu (ayakta sise, tepeden, gercek 250 x 72 mm):\n"
                 "  derinlik toleransi 15/30/60 -> 65 / 83 / 158 mm\n"
                 "  watershed (4 farkli ayar)   -> 248.9 / 249.0 /\n"
                 "                                 248.9 / 249.0 mm\n"
                 "  kapsam %99, saflik %93\n\n"
                 "YUKSEKLIK kriterinden farki: zemin duzlemi GEREKMEZ.\n"
                 "Bu modda tol/gri/kenar/basamak kullanilmaz; yalnizca "
                 "'sinir mm' 3B uzaklik siniri olarak calisir.")
        lbl_ws = tk.Label(btn_row2, text="w.shed:", bg=CARD, fg=MUTED,
                          font=("Segoe UI", 8))
        lbl_ws.pack(side=tk.LEFT, padx=(6, 2))
        ipucu(lbl_ws, IP_WS)
        sp_ws = tk.Spinbox(btn_row2, from_=0, to=900, increment=50, width=4,
                           textvariable=self.pca_watershed_var, bg=BG, fg=FG,
                           buttonbackground=BORDER, relief="flat",
                           font=("Segoe UI", 9))
        sp_ws.pack(side=tk.LEFT)
        ipucu(sp_ws, IP_WS)
        soru(btn_row2, IP_WS).pack(side=tk.LEFT, padx=(2, 0))
        btn_row2 = _grup("Secenekler ve cikti")
        tk.Button(btn_row2, text="Onerilen ayarlar",
                  command=self._onerilen_olcum_ayarlari,
                  bg="#2d5a3d", fg="white", font=("Segoe UI", 9),
                  relief="flat", padx=8, pady=2,
                  cursor="hand2").pack(side=tk.LEFT, padx=(0, 8))
        cb_dz = tk.Checkbutton(btn_row2, text="masayi at",
                               variable=self.pca_duzlem_var,
                               bg=CARD, fg=FG, selectcolor=BG,
                               activebackground=CARD, activeforeground=FG,
                               font=("Segoe UI", 8))
        cb_dz.pack(side=tk.LEFT, padx=(8, 0))
        ipucu(cb_dz,
              "Bolgenin ICINDEKI baskin duzlemi RANSAC ile bulup at.\n\n"
              "VARSAYILAN KAPALI ve genelde acilmamali: bolge zaten ince "
              "bir derinlik dilimi, yani KENDISI duzlemsel. RANSAC "
              "ayirmak istedigimiz iki seyi de duzlem bulur.\n\n"
              "Olculdu: bolgenin %69-100 kadari duzlem sayilip cisim "
              "silindi. Yalnizca cisim belirgin sekilde duzlemsel "
              "olmayan bir sahnede dene.")
        cb_zh = tk.Checkbutton(btn_row2, text="zemin haritasi",
                               variable=self.pca_zemin_var,
                               bg=CARD, fg=FG, selectcolor=BG,
                               activebackground=CARD, activeforeground=FG,
                               font=("Segoe UI", 8))
        cb_zh.pack(side=tk.LEFT, padx=(4, 0))
        ipucu(cb_zh,
              "Kutu gorseli ZEMIN CIKARILMIS haritayi kullansin ve esigin "
              "kestigi tabani duzleme kadar geri eklesin.\n\n"
              "Kazanci dogruluk degil DUYARSIZLIK: bolge masaya sizemedigi "
              "icin sonuc tolerans ve parlaklik ayarindan bagimsiz cikar.\n\n"
              "Olculdu (termos 250 x 72 mm):\n"
              "  ham harita     tol 20 -> 263 | tol 60 -> 263\n"
              "                 kisitlar kapali -> 362 x 324\n"
              "  zemin haritasi tol 20 -> 254 | tol 60 -> 254\n"
              "                 kisitlar kapali -> 254 x 69\n\n"
              "SART: kareyi alirken 'Zemin/masa cikar' isaretli olmali.")
        tk.Button(btn_row2, text="Kutu gorseli",
                  command=self._save_box_visual,
                  bg="#4a2d6a", fg="white", font=("Segoe UI", 10, "bold"),
                  relief="flat", padx=12, pady=6,
                  cursor="hand2").pack(side=tk.LEFT, padx=(6, 0))
        tk.Button(btn_row2, text="Duzlemle olc",
                  command=self._measure_object_plane,
                  bg="#1a5276", fg="white", font=("Segoe UI", 10, "bold"),
                  relief="flat", padx=12, pady=6,
                  cursor="hand2").pack(side=tk.LEFT, padx=(6, 0))

        c = self._section(tab, "Sonuc")
        # Isimler FIZIKSEL yonu soylesin. "En/Boy" tek basina belirsiz;
        # hangi eksen oldugu anlasilmiyordu.
        self.lbl_meas_en = self._info_row(c, "Taban KISA kenar (mm)")
        self.lbl_meas_boy = self._info_row(c, "Taban UZUN kenar (mm)")
        self.lbl_meas_yuk = self._info_row(c, "YUKSEKLIK - yuzeye dik (mm)")
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
            "1. Masayi bos birak â†’ B ile arka plan kaydet\n"
            "2. Nesneyi masaya koy\n"
            "3. M ile olc\n"
            "Kutu onerisi otomatik gosterilir."
        ), bg=CARD, fg=MUTED, font=("Segoe UI", 9),
                 justify="left").pack(fill=tk.X, pady=4)

        for key, action in (("b", self._capture_bg), ("B", self._capture_bg),
                            ("m", self._do_measure), ("M", self._do_measure)):
            self.root.bind(f"<{key}>", self._key_guard(action))

    # â”€â”€ Tab: Durum â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _build_tab_status(self):
        tab = tk.Frame(self.notebook, bg=CARD)
        self.notebook.add(tab, text="  Durum  ")

        sf = self._kaydirilabilir(tab)

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

    # â”€â”€ Tab: Rehber â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _build_tab_guide(self):
        tab = tk.Frame(self.notebook, bg=CARD)
        self.notebook.add(tab, text="  Rehber  ")

        sf = self._kaydirilabilir(tab)

        steps = [
            ("ADIM 1: Cozunurluk sec", ACCENT,
             "Ayarlar tabinda cozunurluk sec.\n"
             "Onerilen: 1280x720 YUY2 (6 FPS)\n"
             "Kalibrasyon ve olcum AYNI cozunurlukle\n"
             "yapilmali - sonra degistirme.\n"
             "640x480 az detay, 2048x1536 onerilen.\n"
             "Kaliteli Tek Kare [F] ile sabit cekim."),

            ("ADIM 2: Aydinlatma sabitle", YELLOW,
             "Masa lambasi kullan, perdeyi kapat.\n"
             "Gun isigi degisir - kalibrasyon bozulur.\n"
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
             "mesafeyi olc â†’ yaklasik baseline.\n\n"
             "Bu degeri Hesaplama tabindaki\n"
             "'Baseline' alanina gir.\n\n"
             "Gercek baseline kalibrasyondan gelecek\n"
             "(||T|| vektoru). Kumpas olcumuyle\n"
             "karsilastir - %5'ten fazla fark varsa\n"
             "kalibrasyonda sorun var demek."),

            ("ADIM 7: Kalibrasyon karesi topla", GREEN,
             "1. Kalibrasyon tabinda modu AC\n"
             "2. Deseni farkli pozisyon/acilarda tut\n"
             "3. Yesil cerceve gorununce S ile kaydet\n"
             "4. 25-40 gecerli cift topla\n"
             "5. 3x3 grid kapsama + egim + mesafe\n\n"
             "Her iki kamerada da desen gorunmeli.\n"
             "Hareket bulanikliginden kacin -\n"
             "dur, bekle, kaydet."),

            ("ADIM 8: Kalibre et", GREEN,
             "Kareler toplandiktan sonra\n"
             "calibration.py scriptini calistir.\n"
             "(Henuz yazilmadi - bu adimda\n"
             "Claude Code'a sor.)\n\n"
             "Hedef: RMS < 0.4 px\n"
             "Cikti: calibration/calib_result.npz"),

            ("KAMERALAR DENGESIZ GORUNUYORSA", RED,
             "Belirti: iki goruntunun parlakligi/rengi\n"
             "belirgin farkli, derinlik haritasi bozuk.\n\n"
             "NEDEN: Kameralar ayarlari HAFIZASINDA\n"
             "saklÄ±yor. Bir ozellik yazilmazsa eski\n"
             "degeri kalir ve iki kamerada farkli olur.\n"
             "MSMF geri okumasi bozuk oldugu icin bu\n"
             "fark cap.get() ile GORULEMEZ - sadece\n"
             "goruntu olculerek anlasilir.\n\n"
             "COZUM (tek adim):\n"
             "Ayarlar tabi > 'Ayarlari kameraya\n"
             "yeniden yaz' butonu. Tum ozellikleri\n"
             "iki kameraya da yazar ve olcerek\n"
             "dogrular.\n\n"
             "Uygulama 30 sn'de bir kendiliginden\n"
             "kontrol eder; dengesizlik olursa durum\n"
             "cubugunda kirmizi uyari cikar.\n\n"
             "Olculen normal deger: parlaklik 1.02x,\n"
             "kontrast 1.09x. Iki kamera ozdestir -\n"
             "buyuk fark her zaman AYAR sorunudur,\n"
             "donanim degil."),

            ("KISAYOLLAR", ACCENT,
             "[F] Kaliteli Tek Kare yakala / birak\n"
             "[V] Mesafe dogrulama\n"
             "[D] Derinlik ekran goruntusu kaydet\n"
             "[R] Olcum noktasini merkeze sifirla\n\n"
             "TIKLAMA ILE OLCUM:\n"
             "Derinlik modunda veya kaliteli karede\n"
             "sol goruntuye TIKLA â†’ o noktanin\n"
             "mesafesini olcer. Cismin UZERINDE\n"
             "tiklaman lazim, arka plana tiklanirsa\n"
             "duvar/zemin mesafesini olcer."),
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

    # â”€â”€ Kamera â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _open_cameras(self):
        self.status_bar.config(text="Kameralar baglaniyor (MSMF)...", fg=YELLOW)
        self.root.update()
        threading.Thread(target=self._open_cameras_bg, daemon=True).start()

    def _open_cameras_bg(self):
        cap_l = cv2.VideoCapture(self.left_idx, cv2.CAP_MSMF)
        cap_r = cv2.VideoCapture(self.right_idx, cv2.CAP_MSMF)
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
            text="Kameralar bagli - {} MSMF".format(sel), fg=ACCENT))
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
        # MSMF'de akis baslamadan yazilan property'ler sessizce yok sayilabilir.
        # Ilk kareler aktiktan sonra ayarlari TEKRAR uygula - aksi halde hangi
        # kamera once hazir olursa ayari o alir, digeri almaz ve iki kamera
        # farkli parlaklikta kalir.
        self.root.after(1200, self._apply_all)
        self.root.after(2500, self._apply_all)
        self.root.after(3200, self._periodic_health_check)
        self._update_display()

    def _periodic_health_check(self):
        """30 sn'de bir sessiz saglik kontrolu - bozulma kendiliginden yakalansin.

        Ayarlar kamerada kalici saklandigi ve MSMF ile okunamadigi icin
        (bkz. _check_camera_balance) tek guvenilir izleme yolu goruntuyu
        surekli olcmektir.
        """
        if not self.running:
            return
        try:
            self._check_camera_balance(sessiz=True)
        except Exception:
            pass
        self.root.after(30000, self._periodic_health_check)

    def _check_camera_balance(self, sessiz=True):
        """Kamera saglik kontrolu - GORUNTUYU olcer, cap.get() KULLANMAZ.

        MSMF'de cap.get() yalan soyler (ne yazarsan yaz sabit deger doner),
        bu yuzden ayarlarin dogru uygulandigi ancak gercek kareyi olcerek
        anlasilabilir. Iki kamera ozdes oldugu icin (olculdu: 1.02x)
        buyuk fark = bir ayar iki kameraya farkli islenmis demektir.
        """
        with self.lock:
            fl, fr = self.frame_l, self.frame_r
        if fl is None or fr is None:
            if not sessiz:
                self.lbl_health.config(text="Kare alinamadi", fg=YELLOW)
            return None
        gl = cv2.cvtColor(fl, cv2.COLOR_BGR2GRAY)
        gr = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
        bl, br = float(gl.mean()), float(gr.mean())
        sl, sr = float(gl.std()), float(gr.std())
        p_oran = max(bl, br) / max(min(bl, br), 1)
        k_oran = max(sl, sr) / max(min(sl, sr), 1)

        if p_oran < 1.15 and k_oran < 1.25:
            msg = (f"SAGLIKLI - parlaklik {p_oran:.2f}x  kontrast {k_oran:.2f}x"
                   f"  (SOL {bl:.0f}/{sl:.0f}  SAG {br:.0f}/{sr:.0f})")
            renk = GREEN
        elif p_oran < 1.35 and k_oran < 1.5:
            msg = (f"SINIRDA - parlaklik {p_oran:.2f}x  kontrast {k_oran:.2f}x"
                   f"  ('Ayarlari kameraya yeniden yaz' dene)")
            renk = YELLOW
        else:
            msg = (f"DENGESIZ - parlaklik {p_oran:.2f}x  kontrast {k_oran:.2f}x"
                   f"  (SOL {bl:.0f} / SAG {br:.0f})  ->  yeniden yaz!")
            renk = RED
        if hasattr(self, "lbl_health"):
            self.lbl_health.config(text=msg, fg=renk)
        if renk is RED and sessiz:
            self.status_bar.config(
                text=f"  UYARI: kameralar dengesiz (parlaklik {p_oran:.2f}x) "
                     f"- Ayarlar tabindan 'Ayarlari kameraya yeniden yaz'",
                fg=RED)
        return p_oran, k_oran

    def _rewrite_all_settings(self):
        """Tum ayarlari iki kameraya da yeniden yaz, sonra olcerek dogrula.

        Bu, 'ayar bozuldu' sikayetinin tek adimli cozumu. Ozellikle
        GAMMA/HUE/BACKLIGHT kamerada kalici saklandigi ve MSMF ile
        okunamadigi icin duzenli olarak yeniden yazilmalari gerekir.
        """
        self.lbl_health.config(text="Yaziliyor...", fg=YELLOW)
        self.root.update()
        self._apply_all()
        # MSMF ilk yazimi yutabiliyor -> akis ilerledikten sonra tekrar
        self.root.after(900, self._apply_all)
        self.root.after(1800, self._apply_all)
        self.root.after(2600, lambda: self._check_camera_balance(sessiz=False))

    def _apply_all(self):
        """Tum ayarlari uygula. SAG kamera telafileri de DAHIL -
        eskiden burada iki kameraya ayni deger yaziliyordu ve
        telafiler acilista sessizce yok sayiliyordu."""
        # TUM ozellikler yazilmali. Eskiden GAMMA/HUE/BACKLIGHT yazilmiyordu;
        # bu ozellikler kamerada KALICI saklandigi ve MSMF geri okumasi bozuk
        # oldugu icin iki kamerada farkli kalip gorunmez bir dengesizlik
        # yaratiyordu (olculdu: gamma 200 vs 100 -> 2.7x parlaklik farki).
        # Hepsi esitlendiginde kameralar 1.02x ile ozdes cikti.
        for cap in [self.cap_l, self.cap_r]:
            if not cap or not cap.isOpened():
                continue
            cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
            cap.set(cv2.CAP_PROP_AUTO_WB, 0)
            cap.set(cv2.CAP_PROP_WB_TEMPERATURE, self.wb_var.get())
            cap.set(cv2.CAP_PROP_CONTRAST, self.contrast_var.get())
            cap.set(cv2.CAP_PROP_SATURATION, self.saturation_var.get())
            cap.set(cv2.CAP_PROP_SHARPNESS, self.sharpness_var.get())
            cap.set(cv2.CAP_PROP_GAMMA, self.gamma_var.get())
            cap.set(cv2.CAP_PROP_HUE, 0)
            cap.set(cv2.CAP_PROP_BACKLIGHT, 0)
        # Telafili ayarlar (sag = sol + telafi)
        # Geciktirmeli sarmalayicilar DEGIL, dogrudan yazicilar:
        # _rewrite_all_settings bu fonksiyonu uc kez ard arda cagirir ve
        # her cagrinin gercekten yazmasi gerekir.
        self._yaz_exposure()
        self._yaz_gain()
        self._on_bright_offset()

    def _set_prop(self, prop, val):
        for cap in [self.cap_l, self.cap_r]:
            if cap and cap.isOpened():
                cap.set(prop, val)

    def _gecikmeli(self, anahtar, fn, ms=250):
        """Ayni islemi tekrar tekrar cagirmak yerine SONUNCUSUNU uygula.

        Neden gerekli: SpinSlider her hareket olayinda komutu cagiriyor.
        Pozlamayi -2'den -6'ya suruklemek onlarca ardisik cap.set()
        uretiyor ve MSMF bu hizli yazimlarin bir kismini yutuyor. Yazim
        bir kameraya ulasip digerine ulasmayinca kameralar KALICI olarak
        ayrisiyor - geri okuma bozuk oldugu icin de gorunmuyor.
        (Gozlendi: pozlamayla oynadikca parlaklik orani 1.04x -> 3.14x.)
        Kullanici slider'i birakinca tek bir yazim yapilir.
        """
        eski = self._bekleyen.get(anahtar)
        if eski is not None:
            try:
                self.root.after_cancel(eski)
            except Exception:
                pass
        self._bekleyen[anahtar] = self.root.after(ms, fn)

    def _on_exposure(self):
        self._gecikmeli("poz", self._yaz_exposure)

    def _yaz_exposure(self):
        exp = self.exposure_var.get()
        for cap in [self.cap_l, self.cap_r]:
            if cap and cap.isOpened():
                cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
        if self.cap_l and self.cap_l.isOpened():
            self.cap_l.set(cv2.CAP_PROP_EXPOSURE, exp)
        if self.cap_r and self.cap_r.isOpened():
            self.cap_r.set(cv2.CAP_PROP_EXPOSURE,
                           max(-13, min(0, exp + self.exp_offset_r.get())))
        # MSMF ilk yazimi yutabiliyor - akis ilerledikten sonra tekrarla
        self.root.after(220, self._yaz_exposure_tekrar)

    def _yaz_exposure_tekrar(self):
        exp = self.exposure_var.get()
        if self.cap_l and self.cap_l.isOpened():
            self.cap_l.set(cv2.CAP_PROP_EXPOSURE, exp)
        if self.cap_r and self.cap_r.isOpened():
            self.cap_r.set(cv2.CAP_PROP_EXPOSURE,
                           max(-13, min(0, exp + self.exp_offset_r.get())))

    def _on_gain(self):
        self._gecikmeli("gain", self._yaz_gain)

    def _yaz_gain(self):
        g = self.gain_var.get()
        if self.cap_l and self.cap_l.isOpened():
            self.cap_l.set(cv2.CAP_PROP_GAIN, g)
        if self.cap_r and self.cap_r.isOpened():
            self.cap_r.set(cv2.CAP_PROP_GAIN,
                           max(0, min(100, g + self.gain_offset_r.get())))

    def _on_wb(self):
        self._set_prop(cv2.CAP_PROP_AUTO_WB, 0)
        self._set_prop(cv2.CAP_PROP_WB_TEMPERATURE, self.wb_var.get())

    def _auto_match_cameras(self):
        """SAG kamerayi SOL'a esitleyen gain telafisini olcerek bul.

        Iki kameranin parlaklik farki sahne/isiga gore degisir ama bir oturum
        icinde kararlidir (olculdu: fark +46.1, 30 sn'de salinim 0.3).
        Bu yuzden sabit deger gomulmez, ihtiyac oldukca burada olculur.
        """
        if not (self.cap_l and self.cap_l.isOpened()
                and self.cap_r and self.cap_r.isOpened()):
            self.lbl_match.config(text="Iki kamera da acik olmali!", fg=RED)
            return
        self.lbl_match.config(text="Olculuyor, sahneyi sabit tut...", fg=YELLOW)
        self.root.update()

        def parlaklik():
            vals = []
            for _ in range(6):
                with self.lock:
                    a, b = self.frame_l, self.frame_r
                if a is not None and b is not None:
                    vals.append((float(cv2.cvtColor(a, cv2.COLOR_BGR2GRAY).mean()),
                                 float(cv2.cvtColor(b, cv2.COLOR_BGR2GRAY).mean())))
                time.sleep(0.08)
            if not vals:
                return None, None
            arr = np.array(vals)
            return float(arr[:, 0].mean()), float(arr[:, 1].mean())

        def calis():
            try:
                eski = self.gain_offset_r.get()
                l0, r0 = parlaklik()
                if l0 is None:
                    self.root.after(0, lambda: self.lbl_match.config(
                        text="Kare alinamadi", fg=RED))
                    return
                en_iyi, en_iyi_fark, sonuc = eski, abs(r0 - l0), []
                for g in range(0, 61, 5):
                    self.root.after(0, lambda v=g: self.gain_offset_r.set(v))
                    time.sleep(0.45)
                    l, r = parlaklik()
                    if l is None:
                        continue
                    sonuc.append((g, r - l))
                    if abs(r - l) < en_iyi_fark:
                        en_iyi, en_iyi_fark = g, abs(r - l)
                self.root.after(0, lambda: self.gain_offset_r.set(en_iyi))
                time.sleep(0.4)
                l, r = parlaklik()
                msg = (f"Gain telafi = +{en_iyi}  |  SOL {l:.0f} / SAG {r:.0f} "
                       f"(fark {r-l:+.0f})")
                renk = GREEN if abs(r - l) < 8 else YELLOW
                if abs(r - l) >= 8:
                    msg += "  - fark buyuk, ton eslemesi 'Histogram' kalsin"
                self.root.after(0, lambda: self.lbl_match.config(text=msg, fg=renk))
            except Exception as ex:
                self.root.after(0, lambda: self.lbl_match.config(
                    text=f"Hata: {ex}", fg=RED))

        threading.Thread(target=calis, daemon=True).start()

    def _reset_offsets(self):
        """Uc SAG kamera telafisini de 0'a al ve kameralara uygula."""
        self.exp_offset_r.set(0)
        self.gain_offset_r.set(0)
        self.bright_offset_r.set(0)
        self._on_exposure()
        self._on_gain()
        self._on_bright_offset()
        self.status_bar.config(text="  SAG kamera telafileri sifirlandi", fg=GREEN)

    def _on_bright_offset(self):
        val = self.brightness_var.get()
        if self.cap_l and self.cap_l.isOpened():
            self.cap_l.set(cv2.CAP_PROP_BRIGHTNESS, val)
        if self.cap_r and self.cap_r.isOpened():
            self.cap_r.set(cv2.CAP_PROP_BRIGHTNESS,
                           max(-64, min(64, val + self.bright_offset_r.get())))

    def _on_img_prop(self):
        # Pozlama/gain ile ayni gerekce: slider suruklenirken onlarca
        # yazim uretilir, MSMF bir kismini yutar ve kameralar ayrisir.
        self._gecikmeli("img", self._yaz_img_prop)

    def _yaz_img_prop(self):
        # Parlakligi _on_bright_offset uzerinden uygula - dogrudan
        # _set_prop kullanilirsa SAG kameranin parlaklik telafisi silinir
        self._on_bright_offset()
        self._set_prop(cv2.CAP_PROP_CONTRAST, self.contrast_var.get())
        self._set_prop(cv2.CAP_PROP_SATURATION, self.saturation_var.get())
        self._set_prop(cv2.CAP_PROP_SHARPNESS, self.sharpness_var.get())
        self._set_prop(cv2.CAP_PROP_GAMMA, self.gamma_var.get())

    def _on_resolution_change(self, event=None):
        sel = self.res_var.get()
        for name, w, h, fmt in RESOLUTIONS:
            if name == sel:
                if w >= 3840:
                    self.status_bar.config(
                        text="4K canli kullanima uygun degil (~1fps). Kaliteli Tek Kare [F] butonunu kullanin.",
                        fg=YELLOW)
                    prev = f"{self.current_w}x{self.current_h}"
                    for rn, rw, rh, rf in RESOLUTIONS:
                        if rw == self.current_w and rh == self.current_h:
                            self.res_var.set(rn)
                            break
                    return
                self.running = False
                time.sleep(0.15)
                for cap in [self.cap_l, self.cap_r]:
                    if not cap or not cap.isOpened():
                        continue
                    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fmt))
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
                self.current_w = w
                self.current_h = h
                self._apply_all()
                self.running = True
                self.thread = threading.Thread(target=self._capture_loop, daemon=True)
                self.thread.start()
                break

    # â”€â”€ Capture â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

            gray_l = cv2.cvtColor(fl, cv2.COLOR_BGR2GRAY)
            gray_r = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)

            if not hasattr(self, '_metric_skip'):
                self._metric_skip = 0
            self._metric_skip += 1
            if self._metric_skip % 5 == 0:
                # Netlik: merkez %60 ROI uzerinden - odak_test.py ile AYNI olcum.
                # Tum kare uzerinden olcmek duz zemin/duvari da sayar ve
                # skoru sahneye gore 1.5-2x dusurur, iki arac karsilastirilamaz.
                mh, mw = gray_l.shape
                y1, y2 = int(mh * 0.2), int(mh * 0.8)
                x1, x2 = int(mw * 0.2), int(mw * 0.8)
                sl = cv2.Laplacian(gray_l[y1:y2, x1:x2], cv2.CV_64F).var()
                sr = cv2.Laplacian(gray_r[y1:y2, x1:x2], cv2.CV_64F).var()
                bl = float(gray_l.mean())
                br = float(gray_r.mean())
            else:
                sl = getattr(self, 'score_l', 0)
                sr = getattr(self, 'score_r', 0)
                bl = getattr(self, 'bright_l', 0)
                br = getattr(self, 'bright_r', 0)

            if self.calib_mode:
                dl = fl.copy()
                dr = fr.copy()
            else:
                dl = fl
                dr = fr
            cl = cr = 0

            if self.calib_mode:
                if not hasattr(self, '_detect_skip'):
                    self._detect_skip = 0
                    self._last_detect_l = (None, None)
                    self._last_detect_r = (None, None)
                self._detect_skip += 1
                run_detect = (self._detect_skip % 3 == 0)
                is_grid = isinstance(self.detector, cv2.aruco.ArucoDetector)

                if run_detect:
                    try:
                        if is_grid:
                            corners_l, ids_l, _ = self.detector.detectMarkers(gray_l)
                            self._last_detect_l = (corners_l, ids_l)
                        else:
                            ch_corners_l, ch_ids_l, _, _ = self.detector.detectBoard(gray_l)
                            self._last_detect_l = (ch_corners_l, ch_ids_l)
                    except Exception as e:
                        if not hasattr(self, '_dbg_err'):
                            self._dbg_err = True
                            print(f"[DEBUG] SOL HATA: {e}")
                    try:
                        if is_grid:
                            corners_r, ids_r, _ = self.detector.detectMarkers(gray_r)
                            self._last_detect_r = (corners_r, ids_r)
                        else:
                            ch_corners_r, ch_ids_r, _, _ = self.detector.detectBoard(gray_r)
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

    # â”€â”€ Display â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _on_cam_wheel(self, event):
        """Fare tekerlegi: imlecin bulundugu noktaya yakinlas/uzaklas."""
        s = self._display_scale
        if s <= 0:
            return
        ox = getattr(self, "_display_off_x", 0.0)
        oy = getattr(self, "_display_off_y", 0.0)
        kx, ky = getattr(self, "_zoom_crop", (0, 0))
        # Imlecin BIRLESIK goruntudeki karsiligi - yakinlastirma bu
        # noktanin etrafinda olsun ki kullanici baktigi yeri kaybetmesin.
        mx = kx + (event.x - ox) / s
        my = ky + (event.y - oy) / s
        yon = 1 if getattr(event, "delta", 0) > 0 else -1
        eski = float(getattr(self, "_zoom", 1.0))
        yeni = float(np.clip(eski * (1.25 if yon > 0 else 1 / 1.25), 1.0, 8.0))
        self._zoom = yeni
        self._zoom_c = (mx, my) if yeni > 1.001 else None
        self.status_bar.config(
            text=f"  Yakinlastirma {yeni:.1f}x"
                 f"{'  (tekerlek: degistir, cift tik: sifirla)' if yeni > 1 else ''}")

    def _on_cam_double(self, event):
        """Cift tiklama: yakinlastirmayi sifirla."""
        self._zoom = 1.0
        self._zoom_c = None
        self.status_bar.config(text="  Yakinlastirma sifirlandi")

    def _on_cam_click(self, event):
        """Sol goruntuye tiklaninca o noktayi olcum noktasi yap."""
        if not self.depth_mode and not getattr(self, '_quality_frozen', False):
            return
        s = self._display_scale
        fl_w = self._display_fl_w
        fl_h = getattr(self, "_display_fl_h", 0)
        if s <= 0 or fl_w <= 0 or fl_h <= 0:
            return
        # Ekran -> birlesik goruntu koordinati.
        # Once ORTALAMA kaydirmasi cikarilir, sonra olcege bolunur.
        ox = getattr(self, "_display_off_x", 0.0)
        oy = getattr(self, "_display_off_y", 0.0)
        kx, ky = getattr(self, "_zoom_crop", (0, 0))
        gx = kx + (event.x - ox) / s
        gy = ky + (event.y - oy) / s
        if gx < kx or gy < ky:
            return                      # siyah banda tiklandi
        if gx >= fl_w:          # sag panele tiklandi
            return
        # Birlesik goruntu -> DISPARITY koordinati.
        # Dogrudan bolmek YETMEZ: gosterilen sol panel ile disparity
        # haritasi ayni boyutta olmayabilir (yukseklik esitleme,
        # kaliteli kare overlay'inin yeniden boyutlanmasi). Bu yuzden
        # KESIR uzerinden cevriliyor - ara boyut ne olursa olsun dogru.
        ref = self._current_dsp if self._current_dsp is not None else None
        if ref is None and self.calib_data is not None:
            w0, h0 = tuple(int(v) for v in self.calib_data["image_size"])
        elif ref is not None:
            h0, w0 = ref.shape[:2]
        else:
            h0, w0 = int(fl_h), int(fl_w)
        img_x = int(gx / fl_w * w0)
        img_y = int(gy / fl_h * h0)
        img_x = max(0, min(img_x, w0 - 1))
        img_y = max(0, min(img_y, h0 - 1))
        self._click_point = (img_y, img_x)
        if getattr(self, '_quality_frozen', False) and self._current_dsp is not None:
            dsp = self._current_dsp
            h, w = dsp.shape
            cy, cx = self._click_point
            cy = max(25, min(cy, h - 25))
            cx = max(25, min(cx, w - 25))
            roi_half = 15
            y1, y2 = cy - roi_half, cy + roi_half
            x1, x2 = cx - roi_half, cx + roi_half
            roi = dsp[y1:y2, x1:x2]
            valid = roi[roi > 0]
            if len(valid) > 10 and self.calib_data is not None:
                pts = cv2.reprojectImageTo3D(dsp, self.calib_data["Q"])
                roi_z = np.abs(pts[y1:y2, x1:x2, 2][roi > 0]) * 1000
                cz = float(np.median(roi_z))
                overlay = self._quality_rect_l.copy() if hasattr(self, '_quality_rect_l') else self._quality_overlay.copy()
                d_norm = self._normalize_disp(dsp)
                cmap_id = self.colormap_map.get(self.colormap_var.get(), cv2.COLORMAP_JET)
                dc = cv2.applyColorMap(d_norm, cmap_id)
                dc[dsp <= 0] = [0, 0, 0]
                mask = dsp > 0
                overlay[mask] = cv2.addWeighted(overlay, 0.4, dc, 0.6, 0)[mask]
                cv2.line(overlay, (cx - 20, cy), (cx + 20, cy), (0, 255, 0), 2)
                cv2.line(overlay, (cx, cy - 20), (cx, cy + 20), (0, 255, 0), 2)
                if 0 < cz < 5000:
                    cv2.putText(overlay, f"{cz:.0f} mm", (cx + 25, cy - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    self.lbl_depth_center.config(text=f"{cz:.0f} mm (tiklanilan nokta)")
                self._quality_overlay = overlay.copy()

    def _reset_click_point(self):
        self._click_point = None
        self.lbl_depth_center.config(text="Merkez (sifirlandÄ±)")

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
            # Kaliteli kare sonucu dondurulmussa onu goster
            if getattr(self, '_quality_frozen', False) and hasattr(self, '_quality_overlay'):
                qo = self._quality_overlay
                qd = self._quality_depth
                h_q, w_q = qo.shape[:2]
                h_fl, w_fl = fl.shape[:2]
                if (h_q, w_q) != (h_fl, w_fl):
                    qo = cv2.resize(qo, (w_fl, h_fl))
                    qd = cv2.resize(qd, (w_fl, h_fl))
                fl = qo
                fr = qd
            # Derinlik modu aktifse sol goruntuye overlay ekle
            elif self.depth_mode and self.map1x is not None and self.stereo is not None:
                try:
                    # Derinlik AYRI THREAD'de hesaplanir; burada sadece hazir
                    # sonuc okunur. Eskiden hesap bu satirda senkron yapiliyordu
                    # ve arayuzu her karede ~920 ms donduruyordu (olculdu).
                    with self._depth_lock:
                        hazir = self._depth_result
                    if hazir is not None:
                        rl, dsp, gl = hazir
                        dn = self._normalize_disp(dsp)
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
                        if self.compare_var.get() and self._raw_disp is not None:
                            dsp_raw = self._raw_disp
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
                        self._current_dsp = dsp.copy()
                        # Olcum noktasi: tiklanmissa orasi, yoksa merkez
                        if self._click_point is not None:
                            cy, cx = self._click_point
                            cy = max(25, min(cy, rl.shape[0] - 25))
                            cx = max(25, min(cx, rl.shape[1] - 25))
                        else:
                            cy, cx = rl.shape[0]//2, rl.shape[1]//2
                        cross_size = 20
                        cv2.line(fl, (cx - cross_size, cy), (cx + cross_size, cy), (0, 255, 0), 2)
                        cv2.line(fl, (cx, cy - cross_size), (cx, cy + cross_size), (0, 255, 0), 2)
                        cv2.line(fr, (cx - cross_size, cy), (cx + cross_size, cy), (0, 255, 0), 2)
                        cv2.line(fr, (cx, cy - cross_size), (cx, cy + cross_size), (0, 255, 0), 2)
                        # Etiketler
                        label_txt = "Sol kamera + derinlik (tikla=olc)"
                        cv2.putText(fl, label_txt, (10, 25),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
                        cv2.putText(fr, "Disparity map", (10, 25),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
                        dsp_olc = getattr(self, "_depth_olcum", None)
                        if dsp_olc is None or dsp_olc.shape != dsp.shape:
                            dsp_olc = dsp
                        cz, etiket, renk = self._measure_point(
                            dsp_olc, gl, cy, cx)
                        # Nokta zemin olarak silindiyse mesafe yine dogru,
                        # olculen sey masa yuzeyidir - bunu belirt.
                        if (dsp_olc is not dsp and cz is not None
                                and dsp[cy, cx] <= 0):
                            etiket += " (ZEMIN)"
                        # Dusuk cozunurluklu onizleme OLCUM DEGILDIR.
                        # Olculdu: 0.5 olcekte tek bir cekimde 566 -> 904 mm
                        # (%59.8 sapma). Kucultme ince yapiyi yok edip
                        # eslesmeyi kaydiriyor. Bu yuzden onizleme degeri
                        # olcum defterine YAZILAMAZ; V tusu reddeder.
                        try:
                            _onizleme = float(self.dscale_var.get()) < 0.999
                        except Exception:
                            _onizleme = True
                        if _onizleme:
                            etiket = "ONIZLEME (olcum icin F)"
                            renk = YELLOW
                        # Guvenilmez veya onizleme -> deftere yazilmaz
                        self._last_center_mm = (cz if (renk is GREEN
                                                       and not _onizleme)
                                                else None)
                        self._last_quality = etiket
                        if cz is not None and 0 < cz < 5000:
                            bgr = {GREEN: (0, 255, 0), YELLOW: (0, 200, 255),
                                   RED: (0, 80, 255)}.get(renk, (0, 255, 0))
                            cv2.putText(fl, f"{cz:.0f}mm", (cx + 25, cy - 10),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, bgr, 2)
                            if renk is not GREEN:
                                cv2.putText(fl, etiket, (cx + 25, cy + 18),
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, bgr, 2)
                            cv2.putText(fr, f"{cz:.0f}mm", (cx + 25, cy - 10),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, bgr, 2)
                            self.root.after(0, lambda z=cz, e=etiket, r=renk:
                                            self.lbl_depth_center.config(
                                                text=f"{z:.0f} mm - {e}", fg=r))
                        else:
                            self.root.after(0, lambda e=etiket, r=renk:
                                            self.lbl_depth_center.config(
                                                text=e, fg=r))
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
            self._display_fl_w = fl.shape[1]
            self._display_fl_h = fl.shape[0]
            combined = np.hstack([fl, fr])

            # YAKINLASTIRMA: birlesik goruntuden bir pencere kirpilir.
            # Nisan almak icin gerekli - 2048 piksel genisligindeki harita
            # ekrana ~1050 px sigdiginda 1 ekran pikseli ~2 harita pikseli
            # demek; tiklama hassasiyeti o oranda dusuyor.
            z = max(1.0, float(getattr(self, "_zoom", 1.0)))
            if z > 1.001:
                ch0, cw0 = combined.shape[:2]
                w2, h2 = int(cw0 / z), int(ch0 / z)
                zc = self._zoom_c or (cw0 // 2, ch0 // 2)
                x0 = int(np.clip(zc[0] - w2 // 2, 0, max(0, cw0 - w2)))
                y0 = int(np.clip(zc[1] - h2 // 2, 0, max(0, ch0 - h2)))
                combined = combined[y0:y0 + h2, x0:x0 + w2]
                self._zoom_crop = (x0, y0)
            else:
                self._zoom_crop = (0, 0)

            mw = max(self.cam_label.winfo_width(), 100)
            mh = max(self.cam_label.winfo_height(), 100)
            ch, cw = combined.shape[:2]
            scale = min(mw/cw, mh/ch, 1.0)
            self._display_scale = scale
            if scale < 1.0:
                combined = cv2.resize(combined, (int(cw*scale), int(ch*scale)))
            # tk.Label goruntuyu ORTALAR (varsayilan anchor=CENTER).
            # Etiket goruntuden buyukse ust/altta ve yanlarda siyah bant
            # olusur; tiklama koordinati etiketin sol-ust kosesinden
            # olculdugu icin bu kaydirma cikarilmazsa nisan noktasi
            # kayar (gozlendi: ust bolgeye tiklaninca alta dusuyordu).
            self._display_off_x = max(0, (mw - combined.shape[1]) / 2.0)
            self._display_off_y = max(0, (mh - combined.shape[0]) / 2.0)

            rgb = cv2.cvtColor(combined, cv2.COLOR_BGR2RGB)
            img = ImageTk.PhotoImage(image=Image.fromarray(rgb))
            self.cam_label.imgtk = img
            self.cam_label.config(image=img)

        # Status bar
        fourcc_int = int(self.cap_l.get(cv2.CAP_PROP_FOURCC)) if self.cap_l else 0
        # FOURCC'ten gelen karakterler her zaman yazdirilabilir DEGIL. Kamera
        # bozuk/eksik kod dondurunce icine NUL karakteri giriyor ve Tk etiketi
        # metni ORADA KESIYOR - durum cubugunda cozunurlukten sonrasi
        # (FPS, parlaklik, netlik, poz) tamamen kayboluyordu.
        fmt = "?"
        if fourcc_int:
            ham = [chr((fourcc_int >> 8 * j) & 0xFF) for j in range(4)]
            temiz = "".join(ch for ch in ham if 32 <= ord(ch) < 127).strip()
            fmt = temiz if temiz else f"0x{fourcc_int:08X}"
        # MSMF'de CAP_PROP_EXPOSURE geri okumasi BOZUK - yazilan deger ne olursa
        # olsun sabit (-6) donuyor, oysa pozlama gercekte uygulaniyor. Bu yuzden
        # kameradan okumak yerine bizim yazdigimiz degeri gosteriyoruz.
        exp = self.exposure_var.get()
        gain = self.gain_var.get()
        st = (f"  {self.current_w}x{self.current_h} {fmt}   "
              f"FPS: {fps:.1f}   "
              f"Parlaklik: L={bl:.0f} R={br:.0f}   "
              f"Netlik: L={sl:.0f} R={sr:.0f}   "
              f"Poz: {exp:.0f}  Gain: {gain:.0f}   "
              f"Kayit: {self.save_count}")
        if self.calib_mode:
            st += f"   Kose: L={cl}/{self.max_corners} R={cr}/{self.max_corners}"
        # Doyma uyarisi: olculdu -> poz=-2'de iki kamera da ~245'e cikiyor
        # (std 9). Doymus pikselde doku kalmaz, SGBM eslesme uretemez.
        # Kullanilabilir bant -5 ... -3.
        renk = FG
        if max(bl, br) > 235:
            st += "   DOYMUS - pozlamayi dusur (-4)"
            renk = RED
        elif max(bl, br) > 210:
            st += "   parlak - doymaya yakin"
            renk = YELLOW
        elif min(bl, br) < 40:
            st += "   cok karanlik - pozlamayi artir"
            renk = YELLOW
        st = "".join(ch if ch.isprintable() else " " for ch in st)
        self.status_bar.config(text=st, fg=renk)

        # Ayarlar tab canli
        self.lbl_fps.config(text=f"{fps:.1f}",
                             fg=GREEN if fps > 3 else YELLOW if fps > 1 else RED)
        self.lbl_net_l.config(text=f"{sl:.0f}",
                               fg=GREEN if sl > 100 else YELLOW if sl > 30 else RED)
        self.lbl_net_r.config(text=f"{sr:.0f}",
                               fg=GREEN if sr > 100 else YELLOW if sr > 30 else RED)
        self.lbl_net_peak_l.config(text=f"{pl:.0f}", fg=MUTED)
        self.lbl_net_peak_r.config(text=f"{pr:.0f}", fg=MUTED)
        # Iki kamera arasi netlik dengesi. Kalibrasyon karelerinde olculen
        # normal aralik: 0.81 - 2.23 (ortalama 1.26)
        if sr > 0:
            ratio = sl / sr
            self.lbl_net_ratio.config(
                text=f"{ratio:.2f}",
                fg=GREEN if 0.7 <= ratio <= 1.5 else YELLOW if 0.5 <= ratio <= 2.3 else RED)

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

    # â”€â”€ Actions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

    # â”€â”€ Swap kamera â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _swap_cameras(self):
        self.running = False
        time.sleep(0.2)
        for cap in [self.cap_l, self.cap_r]:
            if cap:
                cap.release()
        self.left_idx, self.right_idx = self.right_idx, self.left_idx
        self.lbl_cam_idx.config(text=f"SOL=idx {self.left_idx}  SAG=idx {self.right_idx}")
        self._open_cameras()

    # â”€â”€ Ayar kaydet/yukle â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
            "gamma": self.gamma_var.get(),
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
        self.exp_offset_r.set(s.get("exp_offset_r", 0))
        self.gain_offset_r.set(s.get("gain_offset_r", 0))
        self.bright_offset_r.set(s.get("bright_offset_r", 0))
        self.brightness_var.set(s.get("brightness", 0))
        self.contrast_var.set(s.get("contrast", 32))
        self.saturation_var.set(s.get("saturation", 64))
        self.sharpness_var.set(s.get("sharpness", 3))
        self.gamma_var.set(int(s.get("gamma", 100)))
        res = s.get("resolution", RESOLUTIONS[6][0])
        self.res_var.set(res)
        self._pending_settings = None

    # â”€â”€ Derinlik â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _load_ground_data(self):
        """Zemin duzlemini yukle; dosya degistiyse yeniden oku.

        Kalibrasyonla ayni mantik: zemin tespiti yeniden yapildiginda
        uygulama eski duzlemi kullanmaya devam etmemeli.
        """
        if not os.path.exists(GROUND_PATH):
            self.ground_data = None
            return False
        t = os.path.getmtime(GROUND_PATH)
        if (self.ground_data is None
                or t != getattr(self, "_ground_mtime", None)):
            self._ground_mtime = t
            # np.load NPZ dosyasini ACIK TUTAR. Windows'ta acik tutulan
            # dosyanin uzerine np.savez yazamaz -> ikinci kez zemin
            # tespiti yapmak PermissionError verirdi. Icerigi bellege
            # kopyalayip dosyayi kapatiyoruz.
            with np.load(GROUND_PATH) as z:
                self.ground_data = {k: z[k] for k in z.files}
        return True

    def _ensure_calib_current(self):
        """Kalibrasyon dosyasi degistiyse BELLEGE yeniden yukle.

        Eskiden yalnizca 'calib_data is None' kontrolu vardi; bir kez
        yuklendikten sonra bir daha okunmuyordu. Uygulama acikken yeniden
        kalibre edilirse bellekteki ESKI kalibrasyon kullanilmaya devam
        ediyordu - mesafeler sessizce yanlis cikardi.
        """
        if not os.path.exists(CALIB_PATH):
            return self.calib_data is not None
        t = os.path.getmtime(CALIB_PATH)
        if self.calib_data is None or t != getattr(self, "_calib_mtime", None):
            return self._load_calib_data()
        return True

    def _load_calib_data(self):
        if not os.path.exists(CALIB_PATH):
            return False
        self._calib_mtime = os.path.getmtime(CALIB_PATH)
        # Zemin dosyasiyla ayni gerekce: npz'yi acik birakma, yoksa
        # uygulama acikken yeniden kalibrasyon dosyayi yazamaz.
        with np.load(CALIB_PATH) as z:
            self.calib_data = {k: z[k] for k in z.files}
        K1, D1 = self.calib_data["K1"], self.calib_data["D1"]
        K2, D2 = self.calib_data["K2"], self.calib_data["D2"]
        R1, R2 = self.calib_data["R1"], self.calib_data["R2"]
        P1, P2 = self.calib_data["P1"], self.calib_data["P2"]
        image_size = tuple(self.calib_data["image_size"])
        self.map1x, self.map1y = cv2.initUndistortRectifyMap(
            K1, D1, R1, P1, image_size, cv2.CV_32FC1)
        self.map2x, self.map2y = cv2.initUndistortRectifyMap(
            K2, D2, R2, P2, image_size, cv2.CV_32FC1)
        self.stereo = cv2.StereoSGBM_create(
            minDisparity=0, numDisparities=256, blockSize=7,
            P1=8*3*49, P2=32*3*49, disp12MaxDiff=1,
            # uniquenessRatio 15 = eski (72cc70a) deger. 10'a dusurulmustu;
            # daha gevsek = dokusuz bolgelerde belirsiz eslesmeleri kabul eder.
            uniquenessRatio=15, speckleWindowSize=200, speckleRange=2,
            preFilterCap=63, mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY)
        self.stereo_r = cv2.ximgproc.createRightMatcher(self.stereo)
        self.wls_filter = cv2.ximgproc.createDisparityWLSFilter(self.stereo)
        self.wls_filter.setLambda(8000)
        self.wls_filter.setSigmaColor(1.5)
        self.hires_stereo = None
        self._dsp_history = []
        self._load_ground_data()
        try:
            f_px = int(round(P1[0, 0]))
            T = self.calib_data["T"]
            baseline_mm = int(round(np.linalg.norm(T) * 1000))
            self.fpx_var.set(f_px)
            self.baseline_var.set(baseline_mm)
            self._calc_dz()
        except Exception:
            pass
        return True

    @staticmethod
    def _tone_match(gray_l, gray_r, yontem):
        """SAG goruntuyu SOL'un ton dagilimina oturt.

        histogram: CDF eslemesi - dogrusal olmayan ton egrisi farkini da duzeltir
        dogrusal : mean/std transferi - sadece olcek+kaydirma
        """
        if yontem == "histogram":
            hl = np.bincount(gray_l.ravel(), minlength=256).astype(np.float64)
            hr = np.bincount(gray_r.ravel(), minlength=256).astype(np.float64)
            if hl.sum() == 0 or hr.sum() == 0:
                return gray_r
            cdf_l = np.cumsum(hl) / hl.sum()
            cdf_r = np.cumsum(hr) / hr.sum()
            lut = np.interp(cdf_r, cdf_l, np.arange(256)).astype(np.uint8)
            return lut[gray_r]
        if yontem == "dogrusal":
            mu_l, sig_l = gray_l.mean(), max(gray_l.std(), 1)
            mu_r, sig_r = gray_r.mean(), max(gray_r.std(), 1)
            return np.clip((gray_r.astype(np.float32) - mu_r) * (sig_l / sig_r)
                           + mu_l, 0, 255).astype(np.uint8)
        return gray_r

    def _normalize_disp(self, dsp):
        """Disparity -> 0-255 gri. Sabit modda olcek Z_min/Z_max'ten gelir,
        boylece ayni renk her karede ayni mesafeyi gosterir."""
        mod = self.cscale_var.get() if hasattr(self, "cscale_var") else "otomatik"
        if mod == "sabit" and self.calib_data is not None:
            try:
                f_px = float(self.calib_data["P1"][0, 0])
                b_m = float(np.linalg.norm(self.calib_data["T"]))
                z_min = max(self.z_min_var.get(), 1) / 1000.0
                z_max = max(self.z_max_var.get(), z_min * 1000 + 1) / 1000.0
                d_hi = f_px * b_m / z_min      # yakin -> buyuk disparity
                d_lo = f_px * b_m / z_max      # uzak  -> kucuk disparity
                if d_hi > d_lo:
                    n = (dsp - d_lo) / (d_hi - d_lo) * 255.0
                    return np.clip(n, 0, 255).astype(np.uint8)
            except Exception:
                pass
        dm = dsp.max() if dsp.max() > 0 else 1
        return (dsp / dm * 255).astype(np.uint8)

    def _on_numdisp_change(self):
        """Arama araligi degisti - SGBM onbellegini bosalt, sinirlari guncelle."""
        try:
            nd = int(self.numdisp_var.get())
        except (ValueError, AttributeError):
            return
        try:
            md = int(self.mindisp_var.get())
        except (ValueError, AttributeError):
            md = 0
        self._num_disp = nd
        self._min_disp = md
        self._sgbm_cache = {}          # yeni araligla yeniden kurulacak
        self._depth_result = None
        if self.calib_data is not None:
            f = float(self.calib_data["P1"][0, 0])
            b = float(np.linalg.norm(self.calib_data["T"])) * 1000
            z_yakin = f * b / (md + nd - 1)
            z_uzak = (f * b / md) if md > 0 else None
            olu = (md + nd) / max(self.current_w, 1) * 100
            aralik = (f"{z_yakin:.0f} - {z_uzak:.0f} mm" if z_uzak
                      else f"{z_yakin:.0f} mm ve otesi")
            metin = (f"Olculebilir aralik: {aralik}  |  "
                     f"sol kenarda olu bant %{olu:.1f}  |  "
                     f"hiz ~{nd/256:.1f}x yavas")
            renk = MUTED
            if md > 0:
                # OLCULDU (2026-08-18): uzak arka planli sahnede md>0
                # zararli. Pencerenin otesindeki pikseller gecersiz
                # OLMUYOR, pencere icine SIKISTIRILIYOR ve yakin gibi
                # cikiyor. Gercek ciftlerde sahnenin %51-79'u 530 mm
                # otesindeyken md=192 sonrasi bu oran %0-1'e dustu;
                # merkez okumasi 442 -> 261 mm kaydi. Ustelik ham
                # eslesme %100 gosteriyor - gosterge yaniltici oluyor.
                metin += (
                    " !! md>0 yalnizca cercevede UZAK hicbir sey"
                    " yokken kullanilabilir. Arka planda oda/duvar"
                    " varsa onlar yakin gibi hesaplanir ve harita"
                    " bozulur. Suphedeysen 0 sec.")
                renk = YELLOW
            self.lbl_numdisp.config(text=metin, fg=renk)
        self._calc_dz()

    def _sgbm_for_scale(self, olcek):
        """Olcege uygun SGBM+WLS uretir ve onbellekler.

        numDisparities de olcekle kucultulmeli: yari cozunurlukte gercek
        disparity de yariya iner, 256'lik arama gereksiz ve yavas olur.
        (Olculdu: olcek 0.5 + numDisp 128 -> 121 ms, tam cozunurluk 1035 ms;
        mesafe sonucu birebir ayni.)
        """
        anahtar = round(olcek, 2)
        onbellek = getattr(self, "_sgbm_cache", None)
        if onbellek is None:
            onbellek = self._sgbm_cache = {}
        if anahtar in onbellek:
            return onbellek[anahtar]
        taban = getattr(self, "_num_disp", 256)
        nd = max(16, int(round(taban * olcek / 16)) * 16)
        # minDisparity de olcekle kucultulmeli: yari cozunurlukte
        # gercek disparity de yariya iner.
        md_taban = getattr(self, "_min_disp", 0)
        md = int(round(md_taban * olcek / 16)) * 16
        bs = 7 if olcek > 0.6 else 5
        st = cv2.StereoSGBM_create(
            minDisparity=md, numDisparities=nd, blockSize=bs,
            P1=8*3*bs*bs, P2=32*3*bs*bs, disp12MaxDiff=1,
            uniquenessRatio=15, speckleWindowSize=200, speckleRange=2,
            preFilterCap=63, mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY)
        rm = cv2.ximgproc.createRightMatcher(st)
        wl = cv2.ximgproc.createDisparityWLSFilter(st)
        wl.setLambda(8000)
        wl.setSigmaColor(1.5)
        onbellek[anahtar] = (st, rm, wl)
        return onbellek[anahtar]

    def _compute_disparity(self, gray_l, gray_r, olcek=1.0):
        """WLS filtreli disparity hesapla ve post-processing uygula.

        Dondurulen disparity GIRDI olceginde olur; tam cozunurluk karsiligina
        cevirmek cagiranin sorumlulugundadir (bkz. _depth_worker)."""
        # CLAHE opsiyonel - varsayilan kapali (duz yuzeylerde gurultuyu
        # yukseltip sahte eslesme uretiyor, olculdu).
        if getattr(self, "clahe_var", None) is not None and self.clahe_var.get():
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            gray_l = clahe.apply(gray_l)
            gray_r = clahe.apply(gray_r)
        yontem = self.tone_var.get() if hasattr(self, "tone_var") else "histogram"
        gray_r = self._tone_match(gray_l, gray_r, yontem)
        gray_l = cv2.GaussianBlur(gray_l, (3, 3), 0)
        gray_r = cv2.GaussianBlur(gray_r, (3, 3), 0)
        stereo, right_m, wls = self._sgbm_for_scale(olcek)
        dsp_l = stereo.compute(gray_l, gray_r)
        dsp_r = right_m.compute(gray_r, gray_l)
        # GERCEK eslesen pikseller - WLS doldurmadan ONCE. Guvenilirlik
        # degerlendirmesi bunu kullanir; WLS sonrasi maske her yeri dolu
        # gosterdigi icin kalite olcusu olarak KULLANILAMAZ.
        self._last_raw_mask = (dsp_l > 0)
        dsp = wls.filter(dsp_l, gray_l, disparity_map_right=dsp_r)
        dsp = dsp.astype(np.float32) / 16.0
        dsp[dsp <= 0] = 0
        if hasattr(self, 'clean_disp_var') and self.clean_disp_var.get():
            dsp = self._clean_disparity(dsp)
        if hasattr(self, '_dsp_history'):
            self._dsp_history.append(dsp.copy())
            if len(self._dsp_history) > 5:
                self._dsp_history.pop(0)
            if len(self._dsp_history) >= 2:
                stack = np.stack(self._dsp_history, axis=0)
                dsp = np.median(stack, axis=0).astype(np.float32)
        return dsp

    def _depth_worker(self):
        """Derinligi AYRI THREAD'de hesapla - arayuz hic donmesin.

        Olculdu: tam cozunurlukte bir derinlik karesi 920 ms suruyor
        (SGBM sol 346 + SGBM sag 396 + WLS 100 + digerleri). Bu is eskiden
        _update_display icinde, yani ana thread'de yapiliyordu; arayuz her
        karede ~920 ms doniyordu. FPS sayaci yakalama thread'ini olctugu
        icin sorun gostergede gorunmuyordu.

        COZUNURLUK MANTIGI (kalibrasyonu bozmaz):
          remap TAM cozunurlukte yapilir - kalibrasyon (K,D,R,P) yalnizca
          orada kullanilir. Rektifiye cift kucultulunce epipolar hizalama
          korunur (satirlar esit olceklenir). SGBM kucuk goruntude calisir,
          sonra disparity haritasi tam cozunurluge buyutulup degerleri
          1/olcek ile CARPILIR. Boylece asagi akista (mesafe, guvenilirlik,
          renklendirme) hicbir sey degismez.
          Bedeli: alt-piksel hassasiyeti olcek kadar duser -> yalnizca
          CANLI ONIZLEME icin. Olcumler tam cozunurluklu 'Kaliteli Kare'den.
        """
        while self.running:
            try:
                if (not self.depth_mode or self._quality_frozen
                        or self.map1x is None or self.stereo is None):
                    time.sleep(0.08)
                    continue
                with self.lock:
                    raw_l, raw_r = self.frame_l, self.frame_r
                if raw_l is None or raw_r is None:
                    time.sleep(0.05)
                    continue

                # 1) Rektifikasyon - TAM cozunurlukte (kalibrasyon burada)
                rl = cv2.remap(raw_l, self.map1x, self.map1y, cv2.INTER_LINEAR)
                rr = cv2.remap(raw_r, self.map2x, self.map2y, cv2.INTER_LINEAR)
                gl = cv2.cvtColor(rl, cv2.COLOR_BGR2GRAY)
                gr = cv2.cvtColor(rr, cv2.COLOR_BGR2GRAY)

                try:
                    olcek = float(self.dscale_var.get())
                except Exception:
                    olcek = 0.5
                olcek = min(max(olcek, 0.25), 1.0)

                if olcek < 0.999:
                    h0, w0 = gl.shape
                    gl_s = cv2.resize(gl, None, fx=olcek, fy=olcek,
                                      interpolation=cv2.INTER_AREA)
                    gr_s = cv2.resize(gr, None, fx=olcek, fy=olcek,
                                      interpolation=cv2.INTER_AREA)
                    dsp_s = self._compute_disparity(gl_s, gr_s, olcek)
                    # 2) Tam cozunurluge geri: hem BOYUT hem DEGER olceklenir
                    dsp = cv2.resize(dsp_s, (w0, h0),
                                     interpolation=cv2.INTER_NEAREST) / olcek
                    if self._last_raw_mask is not None:
                        self._last_raw_mask = cv2.resize(
                            self._last_raw_mask.astype(np.uint8), (w0, h0),
                            interpolation=cv2.INTER_NEAREST).astype(bool)
                else:
                    dsp = self._compute_disparity(gl, gr, 1.0)

                if self.compare_var.get():
                    ham = self.stereo.compute(gl, gr).astype(np.float32) / 16.0
                    ham[ham <= 0] = 0
                    self._raw_disp = ham
                else:
                    self._raw_disp = None

                # Cikarma oncesi harita OLCUM icin saklanir; silinen
                # pikseller eslesme hatasi degil, kasten atilmis zemindir.
                dsp_olcum = dsp
                if self.ground_var.get():
                    if self._load_ground_data():
                        dsp_olcum = dsp.copy()
                        dsp = self._remove_ground(dsp)
                    else:
                        self.root.after(0, lambda: self.lbl_ground.config(
                            text="Zemin duzlemi YOK - Derinlik tabi > "
                                 "'Zemin tespit et'e bas", fg=RED))

                with self._depth_lock:
                    self._depth_result = (rl, dsp, gl)
                    self._depth_olcum = dsp_olcum
                self._pre_ground_dsp = dsp_olcum
            except Exception:
                time.sleep(0.15)

    def _remove_ground(self, dsp):
        """Zemin/masa duzlemine yakin pikselleri maskele.

        ground_plane.npz icinde duzlem normali n ve d katsayisi var:
            n·X + d = 0
        Bir 3B nokta X icin duzleme dik uzaklik  h = n·X + d  (metre).
        Masa yuzeyi h≈0'dir; uzerindeki cisimler h>0. Esigin altindaki
        ve duzlemin ALTINDAKI (h<0, gurultu/yansima) pikseller atilir.

        Not: n ve d, ZEMIN TESPITI yapilan andaki kamera pozuna goredir.
        Kamera veya masa hareket ederse zemin tespiti tekrarlanmalidir.
        """
        g = self.ground_data
        if g is None or self.calib_data is None:
            return dsp
        try:
            n = np.asarray(g["normal"], dtype=np.float64).ravel()
            d = float(g["d"])
            # Duzlem HAM kamera cercevesinde kaydedildiyse (eski
            # ground_plane.py ciktisi) REKTIFIYE cerceveye dondur.
            # reprojectImageTo3D noktalari rektifiye cercevededir; ikisi
            # R1 kadar farkli (bu kalibrasyonda 1.57 derece) ve bu, masa
            # uzerinde 200 mm yanda ~5 mm yukseklik hatasi demek.
            cerceve = str(g["frame"]) if "frame" in g else "raw"
            if cerceve != "rectified":
                R1 = np.asarray(self.calib_data["R1"], dtype=np.float64)
                n = R1 @ n          # d degismez: donme mesafeyi korur
            n = n / max(float(np.linalg.norm(n)), 1e-9)
            pts = cv2.reprojectImageTo3D(dsp, self.calib_data["Q"])
            h = pts @ n + d              # metre
            # NEGATIF deger serbest: kesme duzlemini duzlemin ALTINA
            # indirir. Gerekli, cunku (a) tahtanin kendi kalinligi var -
            # tespit edilen duzlem masa degil TAHTANIN UST YUZEYIDIR,
            # (b) solvePnP pozu birkac on mm sapabiliyor. Ikisi de
            # cismin tabanini duzlemin ALTINDA birakir ve pozitif esik
            # cismin altini keser.
            esik = float(self.ground_th_var.get()) / 1000.0
            cisim = (dsp > 0) & (h >= esik)
            if self.ground_clean_var.get():
                cisim = self._clean_object_mask(cisim)
            out = dsp.copy()
            out[~cisim] = 0
            kalan = float((out > 0).sum()) / max(out.size, 1) * 100
            self.root.after(0, lambda k=kalan: self.lbl_ground.config(
                text=f"Zemin cikarildi — kalan piksel %{k:.1f}",
                fg=GREEN if k > 1 else YELLOW))
            return out
        except Exception as ex:
            self.root.after(0, lambda e=ex: self.lbl_ground.config(
                text=f"Zemin cikarilamadi: {e}", fg=RED))
            return dsp

    def _detect_ground_plane(self):
        """Zemin/masa duzlemini UYGULAMA ICINDE tespit et ve kaydet.

        Neden ayri script degil: ground_plane.py'yi Durum tabindan
        baslatmak calismiyordu - uygulama kameralari zaten aciktir,
        ikinci surec ayni cihazi acamaz.

        Neden REKTIFIYE goruntu: duzlem, derinlik noktalariyla AYNI
        koordinat cercevesinde olmak zorunda. reprojectImageTo3D ciktisi
        rektifiye sol kamera cercevesindedir; ham goruntude solvePnP ise
        HAM cerceveyi verir. Ikisi R1 kadar (bu kalibrasyonda 1.57 derece)
        farkli - masa uzerinde 200 mm yanda ~5 mm yukseklik hatasi demek.
        Rektifiye goruntude intrinsik P1[:3,:3], distorsiyon ise sifirdir
        (remap zaten gidermistir).
        """
        if not self._ensure_calib_current():
            self.lbl_ground.config(text="Once kalibrasyon gerekli.", fg=RED)
            return
        if self.board is None or self.detector is None:
            self.lbl_ground.config(text="Desen tanimi yuklenemedi.", fg=RED)
            return

        # Sensor gurultusunu azaltmak icin birkac kare ortala.
        yiginlar = []
        for _ in range(8):
            fl = self.frame_l
            if fl is not None:
                yiginlar.append(cv2.cvtColor(fl, cv2.COLOR_BGR2GRAY))
            time.sleep(0.04)
        if not yiginlar:
            self.lbl_ground.config(text="Kamera karesi yok.", fg=RED)
            return
        gray = np.mean(np.stack(yiginlar), axis=0).astype(np.uint8)

        # Rektifiye et - duzlem derinlikle ayni cercevede cikacak.
        gray = cv2.remap(gray, self.map1x, self.map1y, cv2.INTER_LINEAR)
        K = np.asarray(self.calib_data["P1"], dtype=np.float64)[:3, :3]
        D = np.zeros(5, dtype=np.float64)

        try:
            if isinstance(self.detector, cv2.aruco.ArucoDetector):
                corners, ids, _ = self.detector.detectMarkers(gray)
                if ids is None or len(ids) < 6:
                    n = 0 if ids is None else len(ids)
                    self.lbl_ground.config(
                        text=f"Desen bulunamadi ({n} isaret). Tahtayi "
                             "masaya duz koy, isigi artir.", fg=RED)
                    return
                obj_pts, img_pts = self.board.matchImagePoints(corners, ids)
                n_kose = len(ids)
            else:
                cc, ci, _, _ = self.detector.detectBoard(gray)
                if cc is None or len(cc) < 12:
                    n = 0 if cc is None else len(cc)
                    self.lbl_ground.config(
                        text=f"Desen bulunamadi ({n} kose, en az 12 gerek). "
                             "Tahtayi masaya duz koy, isigi artir.", fg=RED)
                    return
                obj_pts, img_pts = self.board.matchImagePoints(cc, ci)
                n_kose = len(cc)

            # DUZ HEDEFTE IKI-KOKLULUK (planar pose ambiguity):
            # Duzlemsel bir desende solvePnP'nin, duzleme gore birbirinin
            # aynasi olan IKI cozumu vardir ve ikisi de dusuk yeniden
            # izdusum hatasi verir. Yanlis kok secilirse duzlem tamamen
            # yanlis yonelir (gozlendi: ayni masada 43.5 derece yerine
            # 85.2 derece, izdusum 0.68 px ile "temiz" gorunerek).
            # Bu yuzden IPPE ile HER IKI cozum alinir ve aralarinda
            # secim GERCEK DERINLIK VERISIYLE yapilir: dogru duzlem,
            # olculen 3B noktalarin buyuk kismini h~0'da birakandir.
            try:
                ok, rvecs, tvecs, hatalar = cv2.solvePnPGeneric(
                    obj_pts, img_pts, K, D, flags=cv2.SOLVEPNP_IPPE)
            except cv2.error:
                ok, rvecs, tvecs, hatalar = False, None, None, None
            if not ok or rvecs is None or len(rvecs) == 0:
                ok2, rv, tv = cv2.solvePnP(obj_pts, img_pts, K, D,
                                           flags=cv2.SOLVEPNP_ITERATIVE)
                if not ok2:
                    self.lbl_ground.config(text="Poz cozulemedi.", fg=RED)
                    return
                rvecs, tvecs = [rv], [tv]
                hatalar = [np.array([[0.0]])]

            adaylar = []
            for k in range(len(rvecs)):
                Rk, _ = cv2.Rodrigues(rvecs[k])
                nk = Rk[:, 2].astype(np.float64)
                if nk[2] > 0:
                    nk = -nk
                dk = float(-np.dot(nk, np.asarray(tvecs[k]).ravel()))
                rp, _ = cv2.projectPoints(obj_pts, rvecs[k], tvecs[k], K, D)
                rmsk = float(np.sqrt(np.mean(np.sum(
                    (rp.reshape(-1, 2) - img_pts.reshape(-1, 2)) ** 2, 1))))
                adaylar.append((nk, dk, rmsk))

            secim, gerekce = 0, "tek cozum"
            if len(adaylar) > 1:
                dsp_ref = getattr(self, "_pre_ground_dsp", None)
                if dsp_ref is None:
                    dsp_ref = getattr(self, "_current_dsp", None)
                puan = []
                if dsp_ref is not None and self.calib_data is not None:
                    P3 = cv2.reprojectImageTo3D(dsp_ref, self.calib_data["Q"])
                    iyi = (dsp_ref > 0) & np.isfinite(P3).all(axis=2)
                    orn = P3[iyi]
                    if len(orn) > 20000:
                        orn = orn[::max(1, len(orn) // 20000)]
                    for nk, dk, _ in adaylar:
                        hk = np.abs(orn @ nk + dk) * 1000.0
                        puan.append(float((hk < 20).mean()))     # h~0 orani
                    secim = int(np.argmax(puan))
                    gerekce = (f"derinlik uyumu %{puan[secim]*100:.0f}"
                               f" vs %{puan[1-secim]*100:.0f}")
                else:
                    secim = int(np.argmin([a[2] for a in adaylar]))
                    gerekce = "izdusum hatasi (derinlik verisi yok)"

            normal, d, rms = adaylar[secim]
            pnp_normal, pnp_d = normal.copy(), float(d)

            # --- IKINCI YONTEM: tahtanin stereo derinliginden uydur ---
            # Her zaman hesaplanir (kutucuk kapali olsa da) ki kullanici
            # iki yontemi yan yana gorsun. Kullanilmasi kutucuga bagli.
            der_normal = der_d = None
            der_not = "derinlik verisi yok"
            dsp_ref2 = getattr(self, "_pre_ground_dsp", None)
            if dsp_ref2 is None:
                with self._depth_lock:
                    dsp_ref2 = getattr(self, "_depth_olcum", None)
            if dsp_ref2 is not None and dsp_ref2.shape[:2] == gray.shape[:2]:
                dn, dd2, ic_oran, der_not = self._tahtadan_derinlik_duzlemi(
                    img_pts, dsp_ref2, self.calib_data["Q"])
                if dn is not None:
                    der_normal, der_d = dn, dd2

            kaynak = "solvePnP"
            if self.ground_derinlik_var.get():
                if der_normal is None:
                    self.lbl_ground.config(
                        text=f"Derinlikten uydurulamadi ({der_not}). "
                             "Kutucugu kapat ya da tahtanin uzerinde "
                             "derinlik olustugundan emin ol.", fg=RED)
                    return
                normal, d = der_normal, der_d
                kaynak = "derinlik"
                rms = 0.0          # bu yontemde izdusum hatasi tanimsiz

            # Iki yontem arasindaki fark - rapor icin degerli
            karsilastirma = ""
            if der_normal is not None:
                fark_aci = float(np.degrees(np.arccos(np.clip(
                    abs(float(pnp_normal @ der_normal)), -1.0, 1.0))))
                fark_mm = abs(abs(pnp_d) - abs(der_d)) * 1000.0
                karsilastirma = (f" | solvePnP vs derinlik: {fark_mm:.0f} mm, "
                                 f"{fark_aci:.1f} derece ({der_not})")

            aci = float(np.degrees(np.arccos(min(abs(normal[2]), 1.0))))
            mesafe = abs(d) * 1000.0
            # ACI BIR HATA OLCUTU DEGIL. Kamera masaya egik baktiginda
            # duzlem normali ile optik eksen arasindaki aci dogal olarak
            # 40-50 derece cikar; tahta yine de masaya tam duz yatiyordur.
            # Gecerliligin gercek olcutu, cozulen pozun kose noktalarini
            # ne kadar iyi acikladigidir: yeniden izdusum hatasi.
            if kaynak == "solvePnP" and rms > 2.0:
                self.lbl_ground.config(
                    text=f"Duzlem uyumsuz (izdusum hatasi {rms:.2f} px). "
                         "Tahta bukuk/kalkik olabilir, isigi artir.", fg=RED)
                return

            # --- SAHNEYE KARSI DOGRULAMA ---
            # Tahta masadan yuksekte durursa tespit metrikleri temiz
            # cikar ama duzlem yanlis yerdedir. Sahnenin kendi baskin
            # duzlemiyle karsilastirip kullaniciya SAYIYLA soyluyoruz.
            sapma_metni, sapma_renk = "", None
            # ONCE DERINLIGIN KENDISI SAGLAM MI? Kontrol, sahnenin
            # duzlemini derinlikten cikariyor; derinlik bozuksa uyari
            # da yanlis olur. Olculdu 2026-08-20: ChArUco tekrarli bir
            # desen ve blok esleme bazen yanlis kareye kilitleniyor -
            # q_20260820_105934'te DUZ tahtanin mesafesi 410..656 mm
            # arasina yayildi, tahta uzerindeki disparity salinimi
            # 37.4 px cikti (saglikli cekimde 8.9 px). O cekimde
            # solvePnP ile derinlik 35 mm ayristi; 23 arsiv cekiminde
            # ise medyan fark yalnizca 3.4 mm.
            tahta_salinim = float("nan")
            try:
                iyy = np.asarray(img_pts, np.float32).reshape(-1, 2)
                kabb = cv2.convexHull(iyy).reshape(-1, 2)
                merr = kabb.mean(axis=0)
                mk_ = np.zeros(gray.shape[:2], np.uint8)
                cv2.fillConvexPoly(
                    mk_, (merr + (kabb - merr) * 0.85).astype(np.int32), 1)
                dsp_t = getattr(self, "_pre_ground_dsp", None)
                if dsp_t is None:
                    with self._depth_lock:
                        dsp_t = getattr(self, "_depth_olcum", None)
                if dsp_t is not None and dsp_t.shape[:2] == gray.shape[:2]:
                    dv = dsp_t[(mk_ > 0) & (dsp_t > 0)]
                    if dv.size > 500:
                        tahta_salinim = float(np.std(dv))
            except Exception:
                pass
            if np.isfinite(tahta_salinim) and tahta_salinim > 20.0:
                sapma_metni = (
                    f"  !! TAHTADA DERINLIK BOZUK: disparity salinimi "
                    f"{tahta_salinim:.0f} px (saglikli deger <10). Duz bir "
                    f"tahtada bu imkansiz - blok esleme tekrarli desende "
                    f"yanlis kareye kilitlenmis. Tahtayi biraz UZAKLASTIR "
                    f"ya da yanina dokulu bir sey koy; sahne karsilastirmasi "
                    f"bu karede guvenilmez.")
                sapma_renk = YELLOW
            try:
                if sapma_metni:
                    raise StopIteration          # karsilastirmayi atla
                dsp_k = getattr(self, "_pre_ground_dsp", None)
                if dsp_k is None:
                    with self._depth_lock:
                        dsp_k = getattr(self, "_depth_olcum", None)
                if dsp_k is not None and dsp_k.shape[:2] == gray.shape[:2]:
                    pts_k = cv2.reprojectImageTo3D(
                        dsp_k.astype(np.float32), self.calib_data["Q"]) * 1000.0
                    gec_k = (dsp_k > 0) & np.isfinite(pts_k).all(axis=2)
                    sn, sd, oran = self._sahne_duzlemi(pts_k, gec_k)
                    if sn is not None and oran > 0.10:
                        if float(sn @ normal) < 0:
                            sn, sd = -sn, -sd
                        d_aci = float(np.degrees(np.arccos(
                            np.clip(abs(float(normal @ sn)), -1.0, 1.0))))
                        d_ote = abs(abs(d * 1000.0) - abs(sd))
                        # Esik secimi olculdu (2026-08-20, 5 cekim x 6
                        # RANSAC kosusu): OTELEME kararli (48-56 mm,
                        # kosular arasi salinim +-1.5 mm), ACI ise 2.4-11
                        # derece arasi oynuyor cunku RANSAC bazen masa
                        # yerine laptop/kutu yuzeyini seciyor. Bu yuzden
                        # asil olcut oteleme; aci sinirini genis tuttuk.
                        if d_ote > 15.0 or d_aci > 10.0:
                            sapma_metni = (
                                f"  !! SAHNEYLE UYUSMUYOR: duzlem sahnenin "
                                f"baskin yuzeyinden {d_ote:.0f} mm otede, "
                                f"aci farki {d_aci:.1f} derece. Tahta masaya "
                                f"DUZ yatirilmali (kutu/kitap uzerinde ya da "
                                f"elde olmamali). Zemin cikarma bu haliyle "
                                f"cismin altini da siler.")
                            sapma_renk = RED
                        else:
                            sapma_metni = (f"  (sahneyle uyumlu: {d_ote:.0f} mm, "
                                           f"{d_aci:.1f} derece)")
            except StopIteration:
                pass
            except Exception:
                pass

            np.savez(GROUND_PATH,
                     normal=normal, d=d,
                     K=K, D=D,
                     frame="rectified",          # KRITIK: cerceve etiketi
                     n_corners=n_kose, rms_px=rms, aci_derece=aci,
                     yontem=kaynak,
                     tarih=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
            self.ground_data = None              # yeniden okunmaya zorla
            self._load_ground_data()
            # Kutucugu OTOMATIK ACMIYORUZ. Zemin cikarma bir OLCUM
            # aracidir, goruntuleme modu degil: acikken sahnenin buyuk
            # kismi (masadan alcak her sey ve duzlemin altindaki tum
            # bolgeler) silinir ve haritaya bakmak isteyen kullanici
            # "bozulmus" gorur. Olcum yapilacagi zaman elle acilir.
            uyari = "  (cok siyirtma acisi, hassasiyet dusuk)" if aci > 70 else ""
            self.lbl_ground.config(
                text=f"Zemin kaydedildi [{kaynak}]: {n_kose} kose, "
                     + (f"izdusum {rms:.2f} px, " if kaynak == "solvePnP"
                        else "")
                     + f"bakis acisi {aci:.1f} derece, "
                     + f"duzlem {mesafe:.0f} mm, {gerekce}.{karsilastirma} "
                     + f"Olcum icin kutucugu isaretle.{uyari}{sapma_metni}",
                fg=sapma_renk or (YELLOW if aci > 70 else GREEN))
        except Exception as ex:
            self.lbl_ground.config(text=f"Zemin tespiti hatasi: {ex}", fg=RED)

    @staticmethod
    def _tahtadan_derinlik_duzlemi(img_pts, dsp, Q, ic_pay=0.12,
                                   tur=400, esik=3.0):
        """Duzlemi solvePnP yerine TAHTANIN STEREO DERINLIGINDEN uydur.

        NEDEN: solvePnP duz bir hedefte iki cozum uretir (planar pose
        ambiguity) ve secim zayif kalabiliyor. Olculdu 2026-08-20:
        secim gerekcesi "derinlik uyumu %12 vs %6" - kazanan da zayif;
        sonucta duzlem gercek masaya gore 7.8 derece EGIK ve 30-53 mm
        havada cikti. Egim esikle telafi edilemez (olculdu: gercek masa
        pikselleri uzerinde ortalama -44.2 mm ama salinim 20.4 mm).

        BU YONTEMDE:
          - iki-kokluluk YOK, tek bir en kucuk kareler cozumu var
          - kare olcusune (olculen_kare_boyutu_mm) BAGIMLI DEGIL
          - zaten derinlikle ayni cercevede, R1 donusumu gerekmiyor
          - 96 kose yerine on binlerce noktaya uyduruyor

        SARTI: tahtanin uzerinde saglam disparity olmali. ChArUco
        siyah-beyaz kareli oldugu icin SGBM icin en iyi durum - orada
        eslesme guclu.

        ic_pay: tahtanin kenarindan iceri kirpma orani. Kenarda
        disparity kenar etkisiyle bozulur, iceriyi kullaniyoruz.
        """
        iy = np.asarray(img_pts, dtype=np.float32).reshape(-1, 2)
        if len(iy) < 8:
            return None, None, 0.0, "kose azligi"
        kabuk = cv2.convexHull(iy).reshape(-1, 2)
        merkez = kabuk.mean(axis=0)
        kabuk_ic = (merkez + (kabuk - merkez) * (1.0 - ic_pay))
        maske = np.zeros(dsp.shape[:2], np.uint8)
        cv2.fillConvexPoly(maske, kabuk_ic.astype(np.int32), 1)
        gec = (maske > 0) & (dsp > 0)
        if gec.sum() < 2000:
            return None, None, 0.0, f"tahtada disparity yok ({int(gec.sum())} px)"
        P3 = cv2.reprojectImageTo3D(dsp.astype(np.float32), Q)
        gec &= np.isfinite(P3).all(axis=2)
        Q3 = P3[gec] * 1000.0                      # mm
        if len(Q3) < 2000:
            return None, None, 0.0, "gecerli nokta az"
        rng = np.random.default_rng(0)
        S = Q3 if len(Q3) <= 40000 else Q3[
            rng.choice(len(Q3), 40000, replace=False)]
        en, en_n, en_d = 0, None, None
        for _ in range(tur):
            a, b, cc = S[rng.choice(len(S), 3, replace=False)]
            nn = np.cross(b - a, cc - a)
            L = float(np.linalg.norm(nn))
            if L < 1e-9:
                continue
            nn = nn / L
            dd = float(-nn @ a)
            say = int((np.abs(S @ nn + dd) < esik).sum())
            if say > en:
                en, en_n, en_d = say, nn, dd
        if en_n is None:
            return None, None, 0.0, "RANSAC cozum bulamadi"
        # Ic noktalarla en kucuk kareler ince ayar (RANSAC 3 noktaya
        # dayanir, sonucu tum ic noktalara oturtmak gurultuyu azaltir).
        ic = np.abs(S @ en_n + en_d) < esik
        if ic.sum() > 100:
            X = S[ic]
            mu = X.mean(axis=0)
            _, _, V = np.linalg.svd(X - mu, full_matrices=False)
            en_n = V[2] / np.linalg.norm(V[2])
            en_d = float(-en_n @ mu)
        if en_n[2] > 0:                            # kamera onunde: nz < 0
            en_n, en_d = -en_n, -en_d
        kalinti = float(np.median(np.abs(S[ic] @ en_n + en_d))) if ic.sum() > 100 \
            else float("nan")
        return (en_n.astype(np.float64), en_d / 1000.0,   # d METRE (uyumluluk)
                float(ic.sum()) / len(S),
                f"{int(gec.sum())} px, ic %{ic.mean()*100:.0f}, "
                f"kalinti {kalinti:.2f} mm")

    @staticmethod
    def _sahne_duzlemi(pts, gec, tur=600, esik=6.0, ornek=60000):
        """Sahnenin BASKIN duzlemini RANSAC ile bul (mm, kamera cercevesi).

        Amaci ChArUco duzlemini DOGRULAMAK. ChArUco tahtasi masadan
        yuksekte durursa (kutu/kitap uzerinde, ya da elde tutulurken)
        tespit metrikleri (kose sayisi, izdusum hatasi) mukemmel gorunur
        ama duzlem yanlis yerdedir. Olculdu 2026-08-20: 96 kose,
        izdusum 0.34 px, buna ragmen duzlem masadan 53 mm yukarida;
        zemin cikarma sahnenin %69'unu ve cismin altini sildi.
        """
        Q = pts[gec]
        if len(Q) < 5000:
            return None, None, 0.0
        rng = np.random.default_rng(0)
        S = Q[rng.choice(len(Q), min(ornek, len(Q)), replace=False)]
        en, en_n, en_d = 0, None, None
        for _ in range(tur):
            a, b, cc = S[rng.choice(len(S), 3, replace=False)]
            nn = np.cross(b - a, cc - a)
            L = float(np.linalg.norm(nn))
            if L < 1e-9:
                continue
            nn = nn / L
            dd = float(-nn @ a)
            say = int((np.abs(S @ nn + dd) < esik).sum())
            if say > en:
                en, en_n, en_d = say, nn, dd
        if en_n is None:
            return None, None, 0.0
        return en_n, en_d, en / len(S)

    @staticmethod
    def _clean_object_mask(mask, min_alan=1500, kapama=9):
        """Zemin cikarildiktan sonra kalan cisim maskesini toparla.

        Neden: cismin dokusuz yuzeylerinde gercek eslesme yoktur, WLS
        oralari cevreden TAHMIN ederek doldurur. Tahmin degeri duzleme
        yakin duserse piksel yanlislikla 'zemin' sayilip silinir - cisim
        delik deliksiz cikar. Uc adim:
          1) CLOSE : cisim icindeki ince catlaklari kapatir
          2) OPEN  : masadan kalan tek tuk benekleri atar
          3) delik doldurma: goruntu kenarina degmeyen kucuk bosluklar
             cismin ici demektir, doldurulur
        """
        m = mask.astype(np.uint8)
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (kapama, kapama)))
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (5, 5)))
        n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
        for i in range(1, n):
            if st[i, cv2.CC_STAT_AREA] < min_alan:
                m[lab == i] = 0
        inv = (m == 0).astype(np.uint8)
        n2, lab2, st2, _ = cv2.connectedComponentsWithStats(inv, 4)
        h, w = m.shape
        kenar = (set(lab2[0, :]) | set(lab2[-1, :])
                 | set(lab2[:, 0]) | set(lab2[:, -1]))
        for i in range(1, n2):
            if i not in kenar and st2[i, cv2.CC_STAT_AREA] < 0.02 * h * w:
                m[lab2 == i] = 1
        return m.astype(bool)

    def _measure_point(self, dsp, gray, cy, cx, roi_half=15):
        """Bir noktada mesafe olc VE guvenilirligini degerlendir.

        Neden gerekli: WLS filtresi bosluklari TAHMINLE doldurur, bu yuzden
        'gecerli piksel sayisi' kontrolu her zaman gecer - dokusuz bir yuzeyde
        bile. Bu, gurultu disparity'sinden (3.5 px) uretilmis 2062 mm gibi
        sahte olcumlere yol acti. Asagidaki uc olcut bunu yakalar.

        Doner: (mesafe_mm | None, etiket, renk)
        """
        h, w = dsp.shape
        cy = int(np.clip(cy, roi_half, h - roi_half - 1))
        cx = int(np.clip(cx, roi_half, w - roi_half - 1))
        y1, y2 = cy - roi_half, cy + roi_half
        x1, x2 = cx - roi_half, cx + roi_half

        roi = dsp[y1:y2, x1:x2]
        valid = roi[roi > 0]
        if len(valid) < 10:
            return None, "ESLESME YOK", RED

        med = float(np.median(valid))
        if med <= 0:
            return None, "ESLESME YOK", RED

        # Mesafe: Z = f*B/d (reprojectImageTo3D ile ayni sonucu verir,
        # ama tum goruntuyu isletmedigi icin cok daha ucuz)
        try:
            f_px = float(self.calib_data["P1"][0, 0])
            b_m = float(np.linalg.norm(self.calib_data["T"]))
        except Exception:
            return None, "KALIBRASYON YOK", RED
        z_mm = f_px * b_m / med * 1000.0

        # --- Olcut 1: DOKU ---
        # SGBM blok eslestirir; doku yoksa eslestirecek desen de yoktur.
        # Olculdu: avuc ici yerel std 1.14 -> eslesme fiziksel olarak imkansiz.
        doku = float(gray[y1:y2, x1:x2].std())

        # --- Olcut 2: DISPARITY TUTARLILIGI ---
        # ROI bir derinlik sinirini kesiyorsa degerler iki kumeye ayrilir;
        # medyan hangi yuzeye dustugune gore zipllar (476mm vs 937mm olayi).
        q1, q3 = np.percentile(valid, [25, 75])
        yayilim = (q3 - q1) / med

        # --- Olcut 3: HAM ESLESME ORANI (WLS oncesi) ---
        ham_oran = None
        rm = getattr(self, "_last_raw_mask", None)
        if rm is not None and rm.shape == dsp.shape:
            ham_oran = float(rm[y1:y2, x1:x2].mean())

        # --- Olcut 4: OLCULEBILIR ARALIK ---
        # Arama araligi kadar disparity gorulebilir; daha yakin cisim
        # araliga sigmaz ve disparity tavana yapisir (sahte ~Z_min okumasi).
        nd = getattr(self, "_num_disp", 256)
        md = getattr(self, "_min_disp", 0)
        z_min = f_px * b_m / (md + nd - 1) * 1000.0
        # minDisparity>0 iken UZAK ucu da kaybederiz - o sinir da kontrol
        # edilmeli, yoksa arka plan sessizce yanlis okunur.
        z_max = (f_px * b_m / md * 1000.0) if md > 0 else None

        if z_mm < z_min * 1.02:
            return z_mm, f"ARALIK DISI (<{z_min:.0f}mm)", RED
        if z_max is not None and z_mm > z_max * 0.98:
            return z_mm, f"ARALIK DISI (>{z_max:.0f}mm)", RED
        if doku < 4.0:
            return z_mm, f"DOKUSUZ (doku {doku:.1f}) - GUVENILMEZ", RED
        if ham_oran is not None and ham_oran < 0.25:
            return z_mm, f"ESLESME ZAYIF (%{ham_oran*100:.0f} ham)", RED
        if yayilim > 0.20:
            return z_mm, f"DERINLIK SINIRI (yayilim %{yayilim*100:.0f})", YELLOW
        if doku < 8.0 or (ham_oran is not None and ham_oran < 0.5):
            return z_mm, "SINIRDA", YELLOW
        return z_mm, "GUVENILIR", GREEN

    def _clean_disparity(self, dsp):
        """Disparity haritasini temizle: median + morfoloji + kucuk bolge."""
        mask = dsp > 0
        # 1. Median filtre - tuz-biber gurultusunu temizle
        dsp_med = cv2.medianBlur(dsp, 5)
        dsp = np.where(mask, dsp_med, 0)
        # 2. Morfolojik kapama - kucuk delikleri doldur
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
        self._quality_frozen = False
        if not self.depth_mode:
            if not self._ensure_calib_current():
                self.lbl_depth_status.config(text="Kalibrasyon yok!", fg=RED)
                return
            self.depth_mode = True
            self._dsp_history = []
            self._depth_result = None
            if self._depth_thread is None or not self._depth_thread.is_alive():
                self._depth_thread = threading.Thread(
                    target=self._depth_worker, daemon=True)
                self._depth_thread.start()
            self.btn_depth.config(text="Derinlik ACIK", bg="#2d6a4f")
            self.lbl_depth_status.config(text="Aktif", fg=GREEN)
            self.lbl_depth_calib.config(text="HAZIR", fg=GREEN)
        else:
            self.depth_mode = False
            self.btn_depth.config(text="Derinlik KAPALI", bg=BORDER)
            self.lbl_depth_status.config(text="Kapali", fg=MUTED)

    def _save_depth(self):
        if not self.depth_mode and not getattr(self, '_quality_frozen', False):
            self.lbl_depth_status.config(text="Once derinligi ac veya F ile cekim yap!", fg=YELLOW)
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
        d_norm = self._normalize_disp(disp)
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

    def _capture_quality_frame(self):
        """Kaliteli tek kare: 10 farkli kare yakala, ortala, ozenli SGBM isle, ekranda goster ve kaydet."""
        if self._quality_frozen:
            self._quality_frozen = False
            self.lbl_depth_status.config(
                text="Canli moda donuldu" if self.depth_mode else "Kapali", fg=MUTED)
            return
        if not self._ensure_calib_current():
            self.lbl_depth_status.config(text="Kalibrasyon yok!", fg=RED)
            return
        if self.map1x is None:
            self.lbl_depth_status.config(text="Kalibrasyon yuklenemedi!", fg=RED)
            return

        self.lbl_depth_status.config(text="Kaliteli cekim: cismi sabit tut...", fg=YELLOW)
        self.root.update()

        def do_quality():
            try:
                # Kac kare ortalanacak. 10 varsayilan; artirmak sensor
                # gurultusunu sqrt(N) ile azaltir (10->3.16x, 40->6.32x)
                # ama sure uzadikca sahnenin kipirdama riski artar ve
                # ortalama bulaniklasir. Kars, deneyle secilsin diye
                # arayuzden ayarlanabilir.
                try:
                    N_FRAMES = max(1, min(60, int(self.qframes_var.get())))
                except Exception:
                    N_FRAMES = 10
                acc_l = None
                acc_r = None
                collected = 0
                last_hash = None
                attempts = 0
                max_attempts = N_FRAMES * 8
                while collected < N_FRAMES and attempts < max_attempts:
                    attempts += 1
                    with self.lock:
                        raw_l = self.frame_l
                        raw_r = self.frame_r
                    if raw_l is None or raw_r is None:
                        time.sleep(0.05)
                        continue
                    cur_hash = hash(raw_l.data.tobytes()[:1024])
                    if cur_hash == last_hash:
                        time.sleep(0.05)
                        continue
                    last_hash = cur_hash
                    rl = cv2.remap(raw_l, self.map1x, self.map1y, cv2.INTER_LINEAR)
                    rr = cv2.remap(raw_r, self.map2x, self.map2y, cv2.INTER_LINEAR)
                    gl = cv2.cvtColor(rl, cv2.COLOR_BGR2GRAY).astype(np.float32)
                    gr = cv2.cvtColor(rr, cv2.COLOR_BGR2GRAY).astype(np.float32)
                    if acc_l is None:
                        acc_l = gl
                        acc_r = gr
                        rect_l_color = rl.copy()
                    else:
                        acc_l += gl
                        acc_r += gr
                    collected += 1
                    self.root.after(0, lambda c=collected: self.lbl_depth_status.config(
                        text=f"Kaliteli cekim: {c}/{N_FRAMES} kare...", fg=YELLOW))
                    time.sleep(0.05)

                if collected < 3:
                    self.root.after(0, lambda: self.lbl_depth_status.config(
                        text="Yeterli kare toplanamadi!", fg=RED))
                    return

                self.root.after(0, lambda: self.lbl_depth_status.config(
                    text="Isleniyor...", fg=YELLOW))

                gray_l = np.round(acc_l / collected).astype(np.uint8)
                gray_r = np.round(acc_r / collected).astype(np.uint8)

                if self.clahe_var.get():
                    clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
                    gray_l = clahe.apply(gray_l)
                    gray_r = clahe.apply(gray_r)
                gray_r = self._tone_match(gray_l, gray_r, self.tone_var.get())
                gray_l = cv2.GaussianBlur(gray_l, (5, 5), 0)
                gray_r = cv2.GaussianBlur(gray_r, (5, 5), 0)

                nd_q = getattr(self, "_num_disp", 256)
                md_q = getattr(self, "_min_disp", 0)
                stereo_q = cv2.StereoSGBM_create(
                    minDisparity=md_q, numDisparities=nd_q, blockSize=9,
                    P1=8*3*81, P2=32*3*81, disp12MaxDiff=1,
                    uniquenessRatio=15, speckleWindowSize=250, speckleRange=2,
                    preFilterCap=63, mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY)
                stereo_q_r = cv2.ximgproc.createRightMatcher(stereo_q)
                wls_q = cv2.ximgproc.createDisparityWLSFilter(stereo_q)
                wls_q.setLambda(12000)
                wls_q.setSigmaColor(1.2)

                dsp_l = stereo_q.compute(gray_l, gray_r)
                dsp_r = stereo_q_r.compute(gray_r, gray_l)
                self._q_raw_mask = (dsp_l > 0)     # WLS oncesi gercek eslesme
                dsp = wls_q.filter(dsp_l, gray_l, disparity_map_right=dsp_r)
                dsp = dsp.astype(np.float32) / 16.0
                dsp[dsp <= 0] = 0
                dsp = self._clean_disparity(dsp)

                # Zemin cikarma yalnizca GORUNTULEME icin uygulanir.
                # Olcum ve kapsama istatistigi cikarma ONCESI haritadan
                # alinir: aksi halde "dolgulu %20" gibi degerler eslesme
                # basarisizligi sanilir, oysa o pikseller kasten silinmis
                # zemindir. Merkez nokta masa uzerindeyse de "ESLESME YOK"
                # denip gercek mesafe kaybedilirdi.
                dsp_olcum = dsp
                if self.ground_var.get():
                    if self._load_ground_data():
                        dsp_olcum = dsp.copy()      # cikarma oncesi sakla
                        dsp = self._remove_ground(dsp)
                    else:
                        self.root.after(0, lambda: self.lbl_ground.config(
                            text="Zemin duzlemi YOK - once 'Zemin tespit et'",
                            fg=RED))

                # Olcum icin zemin cikarilmamis harita saklanir
                self._pre_ground_dsp = dsp_olcum

                h, w = dsp.shape
                cy, cx = h // 2, w // 2
                onceki_mask = getattr(self, "_last_raw_mask", None)
                self._last_raw_mask = self._q_raw_mask
                cz, q_etiket, q_renk = self._measure_point(
                    dsp_olcum, gray_l, cy, cx, roi_half=25)
                self._last_raw_mask = onceki_mask
                # Nokta zemin olarak silindiyse bunu belirt - mesafe yine
                # dogru, sadece olculen sey masa yuzeyi.
                if dsp_olcum is not dsp and cz is not None and dsp[cy, cx] <= 0:
                    q_etiket += " (ZEMIN)"
                center_dist = (f"  Merkez: {cz:.0f} mm [{q_etiket}]"
                               if cz is not None else f"  [{q_etiket}]")
                # md>0 iken pencerenin UZAK ucuna (d ~ md) yigilma,
                # sahnenin araligin disina tastiginin isaretidir.
                if md_q > 0:
                    kul_d = dsp_olcum[:, md_q + nd_q:]
                    gec_d = kul_d > 0
                    if gec_d.sum() > 1000:
                        uc = float((kul_d[gec_d] < md_q + 6).mean())
                        if uc > 0.10:
                            center_dist += (f"  !! SAHNE ARALIK DISINA "
                                            f"TASIYOR (%{uc*100:.0f} uzak "
                                            f"ucta) - 'Arama basi'ni 0 yap")

                # Iki ayri kapsama: WLS SONRASI (doldurulmus) ve HAM (gercek
                # eslesme). "%99.9" gibi degerler WLS dolgusundan gelir ve
                # kalite gostergesi DEGILDIR - ham oran gercegi soyler.
                # Olu bant minDisparity+numDisparities kadardir - yalnizca
                # nd almak, minDisp>0 iken gecersiz sol seridi istatistige
                # katar ve orani oldugundan dusuk gosterir.
                olu_q = md_q + nd_q
                usable_area = dsp_olcum[:, olu_q:]
                valid_pct = (usable_area > 0).sum() / usable_area.size * 100
                rm = getattr(self, "_q_raw_mask", None)
                ham_pct = (float(rm[:, olu_q:].mean()) * 100
                           if rm is not None else float("nan"))
                d_norm = self._normalize_disp(dsp)
                cmap_id = self.colormap_map.get(
                    self.colormap_var.get(), cv2.COLORMAP_JET)
                depth_color = cv2.applyColorMap(d_norm, cmap_id)
                depth_color[dsp <= 0] = [0, 0, 0]
                overlay = rect_l_color.copy()
                mask = dsp > 0
                overlay[mask] = cv2.addWeighted(rect_l_color, 0.4, depth_color, 0.6, 0)[mask]

                cv2.line(overlay, (cx - 20, cy), (cx + 20, cy), (0, 255, 0), 2)
                cv2.line(overlay, (cx, cy - 20), (cx, cy + 20), (0, 255, 0), 2)
                if center_dist:
                    cv2.putText(overlay, center_dist.strip(), (cx + 25, cy - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

                disp_gray = cv2.cvtColor(d_norm, cv2.COLOR_GRAY2BGR)
                disp_gray[dsp <= 0] = [0, 0, 0]
                # HAM/WLS karsilastirmasi kaliteli karede de calissin.
                # Eskiden yalnizca canli modda vardi; oysa "bu plato
                # gercek olcum mu, WLS duzlemesi mi" sorusu tam da
                # olcum alinan karede sorulur.
                if self.compare_var.get():
                    ham_d = dsp_l.astype(np.float32) / 16.0
                    ham_d[ham_d <= 0] = 0
                    ortak = max(dsp.max(), ham_d.max(), 1)
                    hn = (ham_d / ortak * 255).astype(np.uint8)
                    wn = (dsp / ortak * 255).astype(np.uint8)
                    hc = cv2.applyColorMap(hn, cmap_id)
                    wc = cv2.applyColorMap(wn, cmap_id)
                    hc[ham_d <= 0] = [0, 0, 0]
                    wc[dsp <= 0] = [0, 0, 0]
                    hh, ww = wc.shape[:2]
                    orta = ww // 2
                    disp_gray = wc.copy()
                    disp_gray[:, :orta] = hc[:, :orta]
                    cv2.line(disp_gray, (orta, 0), (orta, hh), (255,255,255), 2)
                    cv2.putText(disp_gray, "Ham SGBM (filtresiz)", (20, 45),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255,255,255), 2)
                    cv2.putText(disp_gray, "WLS + temizleme", (orta + 20, 45),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255,255,255), 2)
                self._quality_overlay = overlay.copy()
                self._quality_depth = disp_gray.copy()
                self._quality_dsp = dsp.copy()
                self._quality_gray_l = gray_l.copy()   # guvenilirlik icin
                self._current_dsp = dsp.copy()
                self._quality_rect_l = rect_l_color.copy()
                self._click_point = None
                self._quality_frozen = True

                out_dir = os.path.join(PROJECT_DIR, "output", "depth_captures")
                os.makedirs(out_dir, exist_ok=True)
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                cv2.imwrite(os.path.join(out_dir, f"q_{ts}_sol.png"), rect_l_color)
                cv2.imwrite(os.path.join(out_dir, f"q_{ts}_derinlik.png"), depth_color)
                cv2.imwrite(os.path.join(out_dir, f"q_{ts}_overlay.png"), overlay)
                cv2.imwrite(os.path.join(out_dir, f"q_{ts}_disparity.png"), d_norm)
                cv2.imwrite(os.path.join(out_dir, f"q_{ts}_gray_l.png"), gray_l)
                cv2.imwrite(os.path.join(out_dir, f"q_{ts}_gray_r.png"), gray_r)
                # ZEMIN CIKARILMAMIS harita da kaydedilir. Yalnizca
                # cikarilmis hali saklanirsa sonradan "esik neyi yedi"
                # sorusu cevaplanamaz: silinmis veride tekrar esik
                # taramasi yapmak dairesel olur.
                np.savez_compressed(
                    os.path.join(out_dir, f"q_{ts}_data.npz"),
                    disparity=dsp,             # gosterilen (zemin cikarilmis)
                    disparity_ham=dsp_olcum,   # cikarma ONCESI
                    zemin_cikarildi=bool(self.ground_var.get()),
                    zemin_esik_mm=float(self.ground_th_var.get()),
                    raw_mask=self._q_raw_mask,   # WLS oncesi gercek eslesme
                    gray_l=gray_l, gray_r=gray_r)

                msg = (f"Kaydedildi: {ts} | {collected} kare | "
                       f"Eslesme: ham %{ham_pct:.0f} / dolgulu %{valid_pct:.0f}"
                       f" |{center_dist}")
                mrenk = q_renk if q_renk is not GREEN else GREEN
                self.root.after(0, lambda m=msg, r=mrenk:
                                self.lbl_depth_status.config(text=m, fg=r))
            except Exception as ex:
                self.root.after(0, lambda: self.lbl_depth_status.config(
                    text=f"Kaliteli cekim hata: {ex}", fg=RED))

        self._quality_frozen = False
        threading.Thread(target=do_quality, daemon=True).start()

    def _verify_distance(self):
        """Merkez mesafeyi gercek degerle karsilastir ve olcum defterine yaz."""
        try:
            val = self.verify_entry.get().strip().lower()
            if val.endswith("cm"):
                real_mm = float(val.replace("cm", "")) * 10
            elif val.endswith("mm"):
                real_mm = float(val.replace("mm", ""))
            else:
                real_mm = float(val)
                if real_mm < 100:
                    real_mm *= 10
        except (ValueError, AttributeError):
            self.lbl_verify_result.config(
                text="Mesafeyi gir: 600 veya 60cm (mm varsayilan)", fg=YELLOW)
            return
        if real_mm <= 0:
            self.lbl_verify_result.config(text="Gecersiz deger!", fg=RED)
            return

        measured, etiket, renk = None, "", GREEN
        if getattr(self, '_quality_frozen', False) and hasattr(self, '_quality_dsp'):
            dsp = self._quality_dsp
            h, w = dsp.shape
            if self._click_point is not None:
                cy, cx = self._click_point
            else:
                cy, cx = h // 2, w // 2
            gq = getattr(self, "_quality_gray_l", None)
            if gq is None:
                gq = cv2.cvtColor(self._quality_rect_l, cv2.COLOR_BGR2GRAY)
            measured, etiket, renk = self._measure_point(dsp, gq, cy, cx,
                                                         roi_half=25)
        else:
            measured = getattr(self, "_last_center_mm", None)
            etiket = getattr(self, "_last_quality", "GUVENILIR")

        if measured is None or measured <= 0:
            self.lbl_verify_result.config(
                text=f"Olcum alinamadi: {etiket or 'once F ile cekim yap'}",
                fg=YELLOW)
            return

        # Guvenilmez olcum RAPOR VERISINE girmemeli - defter bozulur
        if renk is RED:
            self.lbl_verify_result.config(
                text=f"REDDEDILDI: {etiket}\nOlcum noktasini dokulu bir yuzeye "
                     f"tasi (tikla) veya cismi yaklastir/uzaklastir.", fg=RED)
            return

        error_mm = measured - real_mm
        error_pct = abs(error_mm) / real_mm * 100
        quality = "BASARILI" if error_pct < 3 else ("KABUL EDILEBILIR" if error_pct < 5 else "KOTU")
        color = GREEN if error_pct < 3 else (YELLOW if error_pct < 5 else RED)

        result = (f"Gercek: {real_mm:.0f} mm | Olculen: {measured:.0f} mm | "
                  f"Hata: {error_mm:+.1f} mm ({error_pct:.1f}%) - {quality}")
        self.lbl_verify_result.config(text=result, fg=color)

        # Olcum defteri semasi: tarih,saat,asama,parametre,ayar,deger,birim,not
        # (mevcut dosyanin basligi budur - sema disi satir yazilirsa defter bozulur)
        header_needed = not os.path.exists(DIARY_PATH)
        now = datetime.datetime.now()
        date = now.strftime("%Y-%m-%d")
        time_ = now.strftime("%H:%M")
        exp = self.exposure_var.get()
        gain = self.gain_var.get()
        wb = self.wb_var.get()
        ayar = f"poz={exp} gain={gain} wb={wb}"
        with open(DIARY_PATH, "a", encoding="utf-8") as f:
            if header_needed:
                f.write("tarih,saat,asama,parametre,ayar,deger,birim,not\n")
            f.write(f"{date},{time_},dogrulama,olculen_mesafe,{ayar},"
                    f"{measured:.1f},mm,gercek={real_mm:.0f}mm\n")
            f.write(f"{date},{time_},dogrulama,hata,{ayar},"
                    f"{error_mm:.1f},mm,gercek={real_mm:.0f}mm\n")
            f.write(f"{date},{time_},dogrulama,hata_yuzde,{ayar},"
                    f"{error_pct:.1f},%,{quality}\n")

    # â”€â”€ Olcum â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _capture_bg(self):
        with self.lock:
            fl = self.frame_l
        if fl is not None:
            self.bg_frame_l = fl.copy()
            self.lbl_meas_bg.config(text="Kaydedildi", fg=GREEN)
            self.lbl_meas_status.config(text="Arka plan hazir, nesneyi koy ve M bas", fg=YELLOW)

    @staticmethod
    def _taban_geri_kazan(govde, h, gec, esik_mm, yaricap=15):
        """Cismin duzleme temas eden bandini geri kazan.

        Zemin cikarma "duzlemden esik kadar yuksek" pikselleri tutar;
        cismin masaya DEGEN alt bandi (h < esik) bu tanimla zeminle
        birlikte silinir. Gorsel olarak cismin alti kesik gorunur.

        Neden YEREL (govdeye komsu) yontem: govdenin duzlem izdusumunu
        (ayak izi) kullanmak cazip ama guvensiz - egik bakista govdenin
        izdusumu gercek tabandan tasar ve yanindaki masa da iceri girer.
        Komsuluk siniri boyle bir kacagi yapisal olarak imkansiz kilar.

        NOT: bu adim yalnizca GORUNUM icindir. Yukseklik duzlemden en
        yuksek noktaya olculur, taban gorunmese de degismez; en/boy da
        govdenin izdusumunden gelir. Olcum bu adim olmadan da dogrudur.
        """
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                      (yaricap * 2 + 1, yaricap * 2 + 1))
        komsu = cv2.dilate(govde.astype(np.uint8), k).astype(bool)
        return govde | (komsu & gec & (h >= -5.0) & (h < esik_mm))

    @staticmethod
    def _yuvarlak_mi(xy, uzun_kenar):
        """Ayak izi bir cember yayi mi? (yuvarlak, cap) dondurur.

        NEDEN GEREKLI: stereo cismin yalnizca ON yuzunu gorur. Silindirin
        duzleme izdusumu tam daire degil, YARIM DAIRE YAYIdir. minAreaRect
        o yaya uygulaninca uzun kenar ~2r (dogru cap) ama kisa kenar ~r
        cikar - yani cap YARIYA duser. Cember uydurup gercek capi geri
        kazaniyoruz.

        Iki sart:
          1) kalinti/yaricap kucuk  -> noktalar gercekten cembere oturuyor
          2) yaricap makul (< 0.60 * uzun kenar) -> duz bir yuzey de
             cembere oturur ama DEV yaricapla; bu sart onu eler.

        Esik 0.06: sentetik kalibrasyonla secildi (gurultu 2 mm'de
        yaylar 0.038-0.042, kutunun iki yuzu 0.092). 5 mm gurultude
        ayrim kayboluyor, ama 700 mm'de derinlik gurultusu ~1.7 mm.
        """
        x = xy[:, 0].astype(np.float64)
        y = xy[:, 1].astype(np.float64)
        A = np.stack([x, y, np.ones_like(x)], 1)
        try:
            sol, *_ = np.linalg.lstsq(A, x * x + y * y, rcond=None)
        except np.linalg.LinAlgError:
            return False, None
        cx, cy = sol[0] / 2.0, sol[1] / 2.0
        r2 = sol[2] + cx * cx + cy * cy
        if r2 <= 0:
            return False, None
        r = float(np.sqrt(r2))
        kal = float(np.median(np.abs(np.hypot(x - cx, y - cy) - r)))
        if r >= 0.60 * uzun_kenar:          # duz yuzey, dev yaricap
            return False, None
        return (kal / r) < 0.06, 2.0 * r

    def _onerilen_olcum_ayarlari(self):
        """Olcum ayarlarini OLCULEN en iyi degerlere dondur.

        Bu degerler tahmin degil: 2026-08-20'de termos (250 x 72 mm)
        uzerinde uc cekimde dogrulandi. Yandan bakis, 610-625 mm:
        tol 15/30/60 arasinda sonuc 252.2-256.8 mm ve yayilim 0.1 mm.
        Deneysel kontroller (kenar/basamak/yukseklik/watershed) o
        kurulumda sonucu degistirmediginden sifirlanir.
        """
        self.pca_tol_var.set(30)
        self.pca_gri_var.set(35)
        self.pca_sinir_var.set(300)
        self.pca_kenar_var.set(0)
        self.pca_basamak_var.set(0.0)
        self.pca_yukseklik_var.set(0)
        self.pca_watershed_var.set(0)
        self.pca_duzlem_var.set(False)
        self.pca_zemin_var.set(False)
        self.lbl_meas_status.config(
            text="Onerilen ayarlar yuklendi (tol 30, gri 35, sinir 300, "
                 "deneyseller kapali). Kamera cisme YANDAN baksin, "
                 "550-650 mm.", fg=GREEN)

    def _save_box_visual(self):
        """Olculen 3B kutuyu goruntu uzerine cizip kaydet.

        Sayilara bakip dogrulugu anlamak zor; kutu cismin uzerine
        cizilince hata aninda gorunur (kutu cismi sariyorsa olcum
        dogru, cevreye tasiyorsa bolge kacmis). Rapora da bu gorsel
        girer - "olculdu" demek yerine "olculen su" gostermek.
        """
        try:
            import subprocess
            if self._click_point is None:
                self.lbl_meas_status.config(
                    text="Once cismin uzerine tikla", fg=YELLOW)
                return
            kayit = sorted(glob.glob(os.path.join(
                PROJECT_DIR, "output", "depth_captures", "q_*_data.npz")))
            if not kayit:
                self.lbl_meas_status.config(
                    text="Once [F] ile kaliteli kare al", fg=YELLOW)
                return
            sy, sx = self._click_point
            self.lbl_meas_status.config(text="Gorsel uretiliyor...", fg=YELLOW)
            self.root.update()
            r = subprocess.run(
                [sys.executable, os.path.join(SCRIPT_DIR, "kutu_gorsel.py"),
                 "--dosya", os.path.basename(kayit[-1]),
                 "--nokta", f"{int(sx)},{int(sy)}",
                 "--sinir", str(self.pca_sinir_var.get()),
                 "--tol", str(self.pca_tol_var.get()),
                 "--gri", str(self.pca_gri_var.get()),
                 "--kenar", str(self.pca_kenar_var.get()),
                 "--basamak", str(self.pca_basamak_var.get()),
                 "--yukseklik", str(self.pca_yukseklik_var.get()),
                 "--watershed", str(self.pca_watershed_var.get())]
                + (["--zemin"] if self.pca_zemin_var.get() else []),
                capture_output=True, text=True, timeout=90)
            cikti = (r.stdout or "") + (r.stderr or "")
            ad = ""
            for satir in cikti.splitlines():
                if "Gorsel:" in satir:
                    ad = satir.split("Gorsel:")[1].strip()
            if ad:
                yol = os.path.join(PROJECT_DIR, "output",
                                   "depth_captures", ad)
                self.lbl_meas_status.config(
                    text=f"Gorsel kaydedildi: {ad}", fg=GREEN)
                try:
                    os.startfile(yol)
                except Exception:
                    pass
            else:
                self.lbl_meas_status.config(
                    text=f"Gorsel uretilemedi: {cikti.strip()[:120]}", fg=RED)
        except Exception as ex:
            self.lbl_meas_status.config(text=f"Hata: {ex}", fg=RED)

    @staticmethod
    def _baskin_duzlemi_at(m, pts, sy, sx, esik=8.0, tur=300):
        """Bolgedeki baskin DUZLEMI (destek yuzeyi) bul ve at.

        NEDEN: cisim bir masanin uzerindeyse derinlik surekliligi
        tabandan masaya kaciyor ve bolge masayi da aliyor (olculdu:
        340x260 mm cikti, gercek 250x72). Masa bir DUZLEM, cisim degil -
        bu ayrimi kullanabiliriz.

        Onceden tespit edilmis zemin duzlemine ihtiyac YOK; duzlem
        bolgenin kendi icinden RANSAC ile bulunur. Kamera yuzeye cok
        siyirtma acisiyla baksa bile calisir.

        Olculdu (esik taramasi): 5 mm -> duzlem tam atilmiyor (242x199),
        8 mm -> 197x64 (dengeli), 12 mm -> cismin bir kismi da gidiyor,
        20 mm -> bolge cokuyor. Varsayilan 8 mm.
        """
        P3 = pts[m]
        if len(P3) < 1000:
            return m, 0.0
        rng = np.random.default_rng(0)
        en_iyi, en_n, en_d = 0, None, None
        for _ in range(tur):
            i = rng.choice(len(P3), 3, replace=False)
            a, b, cc = P3[i]
            nn = np.cross(b - a, cc - a)
            L = float(np.linalg.norm(nn))
            if L < 1e-9:
                continue
            nn = nn / L
            dd = float(-nn @ a)
            say = int((np.abs(P3 @ nn + dd) < esik).sum())
            if say > en_iyi:
                en_iyi, en_n, en_d = say, nn, dd
        if en_n is None:
            return m, 0.0
        oran = en_iyi / len(P3)
        if oran < 0.25:
            return m, oran          # baskin duzlem yok, dokunma
        h = np.full(m.shape, 1e9)
        h[m] = np.abs(pts[m] @ en_n + en_d)
        m2 = m & (h >= esik)
        n, lab, st, _ = cv2.connectedComponentsWithStats(
            m2.astype(np.uint8), 8)
        if lab[sy, sx] > 0:
            m2 = (lab == lab[sy, sx])
            return (m2 if m2.sum() > 300 else m), oran
        # TOHUM DUZLEMIN UZERINDEYDI - yani kullanici cismin degil
        # DESTEK YUZEYININ uzerine tiklamis. "En buyuk bolgeye" dusmek
        # sessizce baska bir seyi olcmek olur (gozlendi: dizustu
        # bilgisayarin kenari olculdu). Bunu bildir.
        return None, oran

    def _measure_click_pca(self):
        """Zemin duzlemi OLMADAN olc: tiklanan noktadan derinlik
        surekliligiyle bolge buyut, PCA ile yonlendirilmis kutu cikar.

        NE ZAMAN: duzlem yontemi kullanilamadiginda - duzlem yoksa,
        eskimisse veya kamera yuzeye cok siyirtma acisiyla bakiyorsa
        (olculdu: 79.8 derecede duzlem yontemi 1053 mm "cap" verdi,
        bu yontem ayni sahnede 288x126x53 mm verdi; gercek ~250x72x72).

        SINIRI: cisim arka planindan DERINLIKCE ayrilmalidir. Bir
        yuzeyin uzerinde duran ve o yuzeyle ayni derinlikte olan cisim
        ayrilamaz - o durumda duzlem yontemi gerekir.
        """
        if not self._ensure_calib_current():
            self.lbl_meas_status.config(text="Kalibrasyon yok", fg=RED)
            return
        dsp = getattr(self, "_pre_ground_dsp", None)
        if dsp is None:
            dsp = getattr(self, "_current_dsp", None)
        if dsp is None:
            self.lbl_meas_status.config(
                text="Once [F] ile kaliteli kare al", fg=YELLOW)
            return
        H, W = dsp.shape
        if self._click_point is not None:
            sy, sx = int(self._click_point[0]), int(self._click_point[1])
            nasil = "tiklanan nokta"
        else:
            sy, sx = H // 2, W // 2
            nasil = "goruntu merkezi"
        sy = max(0, min(sy, H - 1)); sx = max(0, min(sx, W - 1))
        if dsp[sy, sx] <= 0:
            self.lbl_meas_status.config(
                text="Tiklanan noktada disparity yok - baska yere tikla",
                fg=RED)
            return
        try:
            # Tolerans DERINLIK (mm) cinsinden; disparity'ye mesafeye
            # gore cevrilir. Sabit disparity toleransi uzakta cok genis
            # bir derinlik bandi kabul eder (olculdu: 6 px, 730 mm'de
            # 63 mm ama 1750 mm'de 365 mm) ve bolge kacar.
            pts0 = cv2.reprojectImageTo3D(dsp, self.calib_data["Q"]) * 1000.0
            Z0 = float(pts0[sy, sx, 2])
            f_px0 = float(self.calib_data["P1"][0, 0])
            B_mm0 = float(np.linalg.norm(self.calib_data["T"])) * 1000.0
            # Olculdu (termos, 849 mm): tol 20-30 mm -> 244x70-71 mm
            # (gercek 250x72, hata <%3). 60 mm -> 244x103, 100 mm ->
            # 244x144, yani bolge masaya kaciyor. 30 mm guvenli orta yol.
            tol_mm = float(self.pca_tol_var.get())
            tol = (f_px0 * B_mm0 * tol_mm / (Z0 * Z0)
                   if np.isfinite(Z0) and Z0 > 0 else 6.0)
            tol = float(max(0.5, min(tol, 40.0)))
            # PARLAKLIK OLCUTU: derinlik tek basina cismi destek
            # yuzeyinden ayirmiyor - tabanda derinlik sicramasi yok ve
            # o pikseller WLS uydurmasi DEGIL, gercek olcum (olculdu:
            # kacan bolgede ham eslesme %100). Ama cisim ile yuzeyin
            # RENGI genelde farkli. Olculdu (koyu termos / beyaz masa):
            #   gri tolerans yok -> 340x272 mm  (masaya kacmis)
            #   45 -> 262x78 | 35 -> 262x76 | 25 -> 258x70
            #   gercek 250x72x36  => hata %3
            # Cisim ile yuzey ayni renkteyse ise yaramaz; 0 = kapali.
            calis_dsp = dsp
            gri_tol = float(self.pca_gri_var.get())
            gri_kaynak = getattr(self, "_quality_gray_l", None)
            if gri_tol > 0 and gri_kaynak is not None                     and gri_kaynak.shape == dsp.shape:
                fark = np.abs(gri_kaynak.astype(np.float32)
                              - float(gri_kaynak[sy, sx]))
                calis_dsp = dsp.copy()
                calis_dsp[fark > gri_tol] = 0
                if calis_dsp[sy, sx] <= 0:
                    calis_dsp = dsp          # tohum elendi, filtreyi atla
            # KENAR ENGELI - parlaklik basamagi. Seviye esiginin aksine
            # cismin icini bolmez, yalnizca sinirini duvar yapar.
            kenar_esik = float(self.pca_kenar_var.get())
            if kenar_esik > 0 and gri_kaynak is not None \
                    and gri_kaynak.shape == dsp.shape:
                bl = cv2.GaussianBlur(gri_kaynak, (5, 5), 0).astype(np.float32)
                mag = np.hypot(cv2.Sobel(bl, cv2.CV_32F, 1, 0, ksize=3),
                               cv2.Sobel(bl, cv2.CV_32F, 0, 1, ksize=3))
                yeni = calis_dsp.copy()
                yeni[mag > kenar_esik] = 0
                if yeni[sy, sx] > 0:
                    calis_dsp = yeni
            # BASAMAK ENGELI - derinligin komsuya gore degisimi (mm/px).
            # Cisme bagli degil; olculdu: duz yuzey ~0.2-2, sinir 10+.
            basamak = float(self.pca_basamak_var.get())
            if basamak > 0:
                Zh = np.nan_to_num(pts0[:, :, 2], nan=0.0).astype(np.float32)
                Zh = cv2.GaussianBlur(Zh, (3, 3), 0)
                gmag = np.hypot(
                    cv2.Sobel(Zh, cv2.CV_32F, 1, 0, ksize=3) / 8.0,
                    cv2.Sobel(Zh, cv2.CV_32F, 0, 1, ksize=3) / 8.0)
                gmag[calis_dsp <= 0] = np.float32(1e6)
                yeni = calis_dsp.copy()
                yeni[gmag > basamak] = 0
                if yeni[sy, sx] > 0:
                    calis_dsp = yeni
            m0 = np.zeros((H + 2, W + 2), np.uint8)
            im = calis_dsp.astype(np.float32).copy()
            cv2.floodFill(im, m0, (sx, sy), 0, loDiff=tol, upDiff=tol,
                          flags=(8 | cv2.FLOODFILL_MASK_ONLY
                                 | cv2.FLOODFILL_FIXED_RANGE | (255 << 8)))
            m = m0[1:-1, 1:-1].astype(bool) & (calis_dsp > 0)
            if m.mean() > 0.25:
                self.lbl_meas_status.config(
                    text=(f"Bolge kareye tasti (%{m.mean()*100:.0f}) - "
                          f"cisim arka planla ayni derinlikte olabilir. "
                          f"Duzlem yontemi gerekir."), fg=RED)
                return
            pts = pts0
            m &= np.isfinite(pts).all(axis=2)
            # TOHUMDAN 3B UZAKLIK SINIRI. Derinlik surekliligi tek
            # basina bolgeyi cisme hapsetmiyor - komsu yuzeyler ayni
            # derinlikte oldugunda bolge yayiliyor. Olculdu: sinirsiz
            # uzun eksen 635 mm, 200 mm sinirla 314 mm.
            # Sinir, olculebilecek en buyuk cismi de belirler.
            sinir = float(self.pca_sinir_var.get())
            tohum3 = pts[sy, sx]
            if np.isfinite(tohum3).all():
                m &= (np.linalg.norm(pts - tohum3, axis=2) < sinir)
            n, lab, st, _ = cv2.connectedComponentsWithStats(
                m.astype(np.uint8), 8)
            if lab[sy, sx] > 0:
                m = (lab == lab[sy, sx])       # tohumun BOLGESI
            elif n > 1:
                i = int(np.argmax(st[1:, cv2.CC_STAT_AREA])) + 1
                m = (lab == i)
            # Destek yuzeyini (masa) bolgeden at
            duz_not = ""
            if self.pca_duzlem_var.get():
                m_yeni, d_oran = self._baskin_duzlemi_at(m, pts, sy, sx)
                if m_yeni is None:
                    self.lbl_meas_status.config(
                        text=(f"TIKLANAN NOKTA DESTEK YUZEYINDE "
                              f"(bolgenin %{d_oran*100:.0f}'i duzlem). "
                              f"Masaya degil CISMIN uzerine tikla - "
                              f"tekerlekle yakinlasip nisan al."), fg=RED)
                    for L in (self.lbl_meas_en, self.lbl_meas_boy,
                              self.lbl_meas_yuk):
                        L.config(text="-", fg=RED)
                    return
                m = m_yeni
                if d_oran >= 0.25:
                    duz_not = f" | duzlem atildi (%{d_oran*100:.0f})"
            ok = m
            P = pts[ok]
            if len(P) < 800:
                self.lbl_meas_status.config(
                    text=f"Yeterli 3B nokta yok ({len(P)})", fg=RED)
                return
            Q = P - P.mean(axis=0)
            _, _, Vt = np.linalg.svd(Q, full_matrices=False)
            pr = Q @ Vt.T
            b = sorted([float(np.percentile(pr[:, k], 99)
                              - np.percentile(pr[:, k], 1)) for k in range(3)],
                       reverse=True)
            self.lbl_meas_yuk.config(text=f"{b[0]:.1f}", fg=GREEN)
            self.lbl_meas_boy.config(text=f"{b[1]:.1f}", fg=GREEN)
            self.lbl_meas_en.config(text=f"{b[2]:.1f}", fg=GREEN)
            self.lbl_meas_status.config(
                text=(f"DUZLEMSIZ (PCA) | {nasil} | {int(ok.sum()):,} px | "
                      f"Z={np.median(P[:, 2]):.0f} mm{duz_not} | tol {tol:.1f} px"
                      f"{f', gri {gri_tol:.0f}' if gri_tol > 0 else ''} | "
                      f"kisa kenar CISMIN GORUNEN yuzunun kalinligidir, "
                      f"arka yuz olculemez"), fg=GREEN)
            self._son_olcum = (b[0], b[1], b[2])
        except Exception as ex:
            self.lbl_meas_status.config(text=f"Hata: {ex}", fg=RED)

    def _measure_object_plane(self):
        """Zemin duzlemi + tiklanan nokta ile cismin EN/BOY/YUKSEKLIK'ini olc.

        Neden duzlem koordinatlari: goruntudeki piksel boyutu mesafeye ve
        bakis acisina gore degisir. Noktalar duzleme izdusurulunce olcu
        gercek fiziksel boyut olur; cisim egik dursa bile minAreaRect
        donmus dikdortgeni bulur.

        Neden calisma hacmi: duzlem SONSUZDUR - arkadaki duvar/raf da
        "duzlemin uzerinde"dir. Olculdu: sinirsizken boy 3219 mm cikti.
        Bu yuzden hem yukseklik hem KAMERA MESAFESI penceresi uygulanir.
        """
        if not self._ensure_calib_current():
            self.lbl_meas_status.config(text="Kalibrasyon yok", fg=RED)
            return
        if not self._load_ground_data():
            self.lbl_meas_status.config(
                text="Zemin duzlemi yok - Derinlik tabi > 'Zemin tespit et'",
                fg=RED)
            return
        dsp = getattr(self, "_pre_ground_dsp", None)
        if dsp is None:
            dsp = self._current_dsp
        if dsp is None:
            self.lbl_meas_status.config(
                text="Once [F] ile kaliteli kare al", fg=YELLOW)
            return
        try:
            g = self.ground_data
            n = np.asarray(g["normal"], np.float64).ravel()
            if (str(g["frame"]) if "frame" in g else "raw") != "rectified":
                n = np.asarray(self.calib_data["R1"], np.float64) @ n
            n = n / np.linalg.norm(n)
            d = float(g["d"])

            pts = cv2.reprojectImageTo3D(dsp, self.calib_data["Q"])
            gec = (dsp > 0) & np.isfinite(pts).all(axis=2)
            h = np.full(dsp.shape, -1e9)
            h[gec] = (pts[gec] @ n + d) * 1000.0
            Zmm = pts[:, :, 2] * 1000.0

            # BAKIS ACISI KAPISI
            # Duzlem normali ile optik eksen arasindaki aci buyudukce
            # yuzey KENARDAN gorulur. Olculdu (Z=700, blok 7 px):
            #   20 derece -> blok boyunca 0.26 px kayma  (cok iyi)
            #   43 derece -> 0.68 px                     (sinirda)
            #   60 derece -> 1.24 px                     (bozulur)
            #   80 derece -> 3.99 px                     (eslesme imkansiz)
            # Ayrica yukseklik yonunun optik eksene izdusumu cos(aci):
            # 80 derecede 0.177, yani olcmek istedigimiz boyut en zayif
            # gozlenen yonde kaliyor. Bu kosulda uretilen her sayi
            # yaniltici olur - sayi uretmek yerine durmak dogru.
            # Kapi DEGIL uyari: kullanici kamerayi her zaman
            # yeniden konumlandiramaz. Olcum yapilir ama guvenilirlik
            # acikca yazilir - karari kullanici verir.
            aci_p = float(np.degrees(np.arccos(min(abs(n[2]), 1.0))))
            if aci_p > 60.0:
                aci_not = (f"  !! BAKIS ACISI {aci_p:.0f} derece - yuzeye "
                           f"neredeyse kenardan bakiliyor, yukseklik "
                           f"guvenilmez (izdusum {abs(n[2]):.2f})")
                aci_renk = RED
            elif aci_p > 45.0:
                aci_not = f"  ! bakis acisi {aci_p:.0f} derece - sinirda"
                aci_renk = YELLOW
            else:
                aci_not, aci_renk = "", None

            # DUZLEM HALA GECERLI MI?
            # Duzlem, tespit edildigi andaki KAMERA POZUNA goredir.
            # Kamera veya yuzey oynadiysa dosya durur ama artik hicbir
            # gercek yuzeye karsilik gelmez. O zaman "duzlemin ustunde"
            # testi tum sahneyi secer ve olcum sacmalar (gozlendi:
            # boy 3806 mm). Dosyanin VARLIGI gecerlilik demek degil.
            # Olcut: gercekten duzlem uzerinde (|h| < 15 mm) duran
            # piksel orani. Duzlem sahnedeki bir yuzeyi tarif ediyorsa
            # bu oran kayda deger olmali.
            duzlem_ustu = float((gec & (np.abs(h) < 15.0)).sum()
                                / max(gec.sum(), 1))
            if duzlem_ustu < 0.03:
                self.lbl_meas_status.config(
                    text=(f"ZEMIN DUZLEMI ESKIMIS - sahnenin yalnizca "
                          f"%{duzlem_ustu*100:.1f}'i duzlem uzerinde. "
                          f"Kamera/yuzey oynamis. Derinlik tabi > "
                          f"'Zemin tespit et' ile YENIDEN tespit et."),
                    fg=RED)
                self.lbl_meas_en.config(text="-", fg=RED)
                self.lbl_meas_boy.config(text="-", fg=RED)
                self.lbl_meas_yuk.config(text="-", fg=RED)
                return
            duzlem = gec & (np.abs(h) < 15)
            z_masa = float(np.median(Zmm[duzlem])) if duzlem.sum() > 5000 \
                else float(np.median(Zmm[gec]))
            esik = float(self.ground_th_var.get())   # negatif olabilir
            m = ((h >= esik) & (h <= 400) & gec
                 & (Zmm < z_masa + 150)).astype(np.uint8)
            m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, (9, 9)))
            m = cv2.morphologyEx(m, cv2.MORPH_OPEN, cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, (5, 5)))
            m = (m.astype(bool) & gec).astype(np.uint8)

            nlab, lab, st, cen = cv2.connectedComponentsWithStats(m, 8)
            if nlab < 2:
                self.lbl_meas_status.config(text="Cisim bulunamadi", fg=RED)
                return
            H, W = dsp.shape
            if self._click_point is not None:
                hedef = np.array([self._click_point[1], self._click_point[0]],
                                 float)
                nasil = "tiklanan nokta"
            else:
                hedef = np.array([W / 2.0, H / 2.0])
                nasil = "goruntu merkezi"
            # SECIM: once TIKLANAN PIKSELIN ICINDE oldugu bolge.
            # Eskiden "merkezi tiklamaya en yakin bolge" seciliyordu; bu
            # yanlis - kucuk bir cisme tiklarken yanindaki buyuk cismin
            # merkezi daha yakin olabilir ve o olculur. Tiklanan pikselin
            # etiketine bakmak niyeti dogrudan verir.
            tik_y, tik_x = int(hedef[1]), int(hedef[0])
            tik_y = max(0, min(tik_y, H - 1))
            tik_x = max(0, min(tik_x, W - 1))
            secilen = int(lab[tik_y, tik_x])
            if secilen > 0 and st[secilen, cv2.CC_STAT_AREA] >= 800:
                nasil += " (tam uzerinde)"
            else:
                # Tiklanan piksel hicbir bolgede degil (zemin, bosluk veya
                # esik alti). En yakin merkezli bolgeye dus.
                aday = [(np.linalg.norm(cen[k] - hedef), k)
                        for k in range(1, nlab)
                        if st[k, cv2.CC_STAT_AREA] >= 3000]
                if not aday:
                    self.lbl_meas_status.config(
                        text="Tiklanan noktada cisim yok ve yakinda "
                             "yeterli buyuklukte bolge bulunamadi", fg=RED)
                    return
                aday.sort()
                secilen = aday[0][1]
                nasil += " (uzerinde degil, en yakin bolge)"
            aday = [k for k in range(1, nlab)
                    if st[k, cv2.CC_STAT_AREA] >= 3000]
            govde = (lab == secilen)
            # Cismin masaya degen alt bandini geri kazan (yalnizca
            # gorunum; olcum bu adim olmadan da dogru - bkz. metod notu)
            cisim = self._taban_geri_kazan(govde, h, gec, esik)
            kazanc = int(cisim.sum() - govde.sum())

            yardim = np.array([1.0, 0, 0]) if abs(n[0]) < 0.9 \
                else np.array([0, 1.0, 0])
            u = np.cross(n, yardim); u /= np.linalg.norm(u)
            v = np.cross(n, u);      v /= np.linalg.norm(v)
            P = pts[cisim] * 1000.0
            xy = np.stack([P @ u, P @ v], 1).astype(np.float32)
            (_, _), (w1, w2), _ = cv2.minAreaRect(xy)
            en, boy = sorted((w1, w2))
            # Yuvarlak cisimde kisa kenar yariya duser (yalnizca on yuz
            # gorunur -> ayak izi yarim daire yayi). Cember uydurup
            # gercek capi geri kazan.
            # Bakis acisi kotuyse duzeltme UYGULANMAZ. Cember uydurma
            # matematigi dogru ama girdi bolge bozuksa sonucu "duzeltilmis"
            # diye sunmak yaniltir (gozlendi: cap 1053 mm). Cop veriyi
            # susleme - oldugu gibi goster.
            yv, cap = (False, None)
            if aci_p <= 60.0:
                yv, cap = self._yuvarlak_mi(xy, boy)
            yuv_not = ""
            if yv and cap is not None:
                yuv_not = (f"  [YUVARLAK: cap {cap:.0f} mm - kisa kenar "
                           f"{en:.0f} yerine cap kullanildi]")
                en = boy = float(cap)
            yuk = float(np.percentile(h[cisim], 98))

            # ARALIK KONTROLU: cismin tepesi Z_min'den yakinsa o
            # pikseller HIC uretilmez (disparity arama penceresi disi),
            # nokta bulutunda bulunmazlar ve YUKSEKLIK sessizce eksik
            # cikar. Hata verilmedigi icin fark edilmesi zor - uyar.
            nd = getattr(self, "_num_disp", 256)
            f_px = float(self.calib_data["P1"][0, 0])
            b_mm = float(np.linalg.norm(self.calib_data["T"])) * 1000.0
            z_min = f_px * b_mm / (nd - 1)
            z_tepe = float(np.percentile(P[:, 2], 2))   # cismin en yakin ucu
            uyari, renk = "", GREEN
            if z_tepe < z_min * 1.05:
                uyari = (f"  !! TEPESI KESIK OLABILIR: {z_tepe:.0f} mm, "
                         f"sinir {z_min:.0f} mm (arama araligini buyut "
                         f"veya kamerayi yukselt)")
                renk = RED
            elif z_tepe < z_min * 1.20:
                uyari = f"  ! sinira yakin ({z_tepe:.0f} / {z_min:.0f} mm)"
                renk = YELLOW

            if aci_renk is not None and renk == GREEN:
                renk = aci_renk
            uyari = aci_not + yuv_not + uyari
            self.lbl_meas_en.config(text=f"{en:.1f}", fg=renk)
            self.lbl_meas_boy.config(text=f"{boy:.1f}", fg=renk)
            self.lbl_meas_yuk.config(text=f"{yuk:.1f}", fg=renk)
            self.lbl_meas_status.config(
                text=f"{nasil} | {len(aday)} aday | "
                     f"{int(cisim.sum()):,} px (+{kazanc:,} taban) | desi "
                     f"{en*boy*yuk/3e6:.2f}{uyari}", fg=renk)
            self._son_olcum = (en, boy, yuk)
        except Exception as ex:
            self.lbl_meas_status.config(text=f"Hata: {ex}", fg=RED)

    def _do_measure(self):
        if not self._ensure_calib_current():
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
            g = self.ground_data
            ground_n = np.asarray(g["normal"], np.float64).ravel()
            # Duzlem ham cercevede kaydedildiyse rektifiye cerceveye cevir
            # (bkz. _remove_ground - R1 farki 1.567 derece)
            if (str(g["frame"]) if "frame" in g else "raw") != "rectified":
                ground_n = np.asarray(self.calib_data["R1"],
                                      np.float64) @ ground_n
            ground_d = float(g["d"])

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

            # BIRIM: Q metre biriminde (kalibrasyon sq/1000 kullaniyor),
            # dolayisiyla proj_* degerleri METREDIR. Etiketler ve kutu
            # onerisi mm bekliyor - *1000 EKSIKTI. Belirtisi: 0.3 x 0.3
            # x 0.2 "mm" gorunumu ve her cisme "Mini koli" onerisi.
            en = float(max(proj_u) - min(proj_u)) * 1000.0
            boy = float(max(proj_v) - min(proj_v)) * 1000.0
            yuk = float(max(proj_n) - min(proj_n)) * 1000.0
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

    # â”€â”€ Durum tab islemleri â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
        cmd = [sys.executable, script]
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
        """Zemin tespitini UYGULAMA ICINDE yap.

        Eskiden ground_plane.py'yi ayri surec olarak baslatiyordu; uygulama
        kameralari zaten acik tuttugu icin o surec kamerayi acamiyor ve
        sessizce basarisiz oluyordu. Artik ayni is Derinlik tabindaki
        mantikla, mevcut kare uzerinden yapiliyor.
        """
        self._append_process_output(
            ">>> Zemin tespiti (uygulama ici, rektifiye cerceve)...")
        self._detect_ground_plane()
        self._append_process_output(self.lbl_ground.cget("text"))
        self._refresh_status()

    def _run_focus_test(self):
        script = os.path.join(SCRIPT_DIR, "odak_test.py")
        self._append_process_output(">>> Odak testi baslatiliyor (ayri pencere)...")
        subprocess.Popen([sys.executable, script,
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
