"""Stereo Olcum Kiti - iki USB kamerayla 3B boyut olcumu.

Herhangi bir kamera cifti ile calisir. Dort adimlik rehberli akis:

  1. KAMERALAR  - bagli kameralari bul, cozunurluk sec
  2. KALIBRASYON - desen tanit, kare topla, kalibre et
  3. DERINLIK   - canli derinlik haritasi, parametre ayari
  4. OLCUM      - cisme tikla, boyutlarini al

Calistirma:
    python stereo_kit.py
"""
from __future__ import annotations

import os
import sys
import json
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# OpenCV'nin backend uyarilarini bastir - kamera taramasi sirasinda
# ekrani dolduruyor ve kullanici icin anlamsiz.
os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")
os.environ.setdefault("OPENCV_VIDEOIO_PRIORITY_MSMF", "1")

import numpy as np                                          # noqa: E402
import cv2                                                  # noqa: E402
from PIL import Image, ImageTk                              # noqa: E402

KOK = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, KOK)
from cekirdek import kamera, kalibrasyon, derinlik, olcum    # noqa: E402
from cekirdek.ipucu import ipucu, soru                       # noqa: E402

try:
    cv2.setLogLevel(0)
except Exception:
    pass

VERI = os.path.join(KOK, "veri")
KALIB_YOL = os.path.join(VERI, "kalibrasyon.npz")
AYAR_YOL = os.path.join(VERI, "ayarlar.json")
KARE_KLASOR = os.path.join(VERI, "kareler")
CIKTI = os.path.join(KOK, "cikti")

BG = "#1e1e2e"
KART = "#262637"
KENAR = "#3a3a5c"
YAZI = "#d4d4e8"
VURGU = "#7aa2f7"
YESIL = "#9ece6a"
SARI = "#e0af68"
KIRMIZI = "#f7768e"
SOLUK = "#8a8fa8"


class StereoKit:
    def __init__(self, kok):
        self.kok = kok
        kok.title("Stereo Olcum Kiti")
        kok.geometry("1500x900")
        kok.configure(bg=BG)
        os.makedirs(VERI, exist_ok=True)
        os.makedirs(KARE_KLASOR, exist_ok=True)
        os.makedirs(CIKTI, exist_ok=True)

        self.kameralar = []
        self.sol_cap = self.sag_cap = None
        self.sol_kare = self.sag_kare = None
        self.calisiyor = False
        self.kalib = None
        self.haritalar = None
        self.motor = derinlik.DerinlikMotoru()
        self.derinlik_acik = False
        self.son_dsp = None
        self.son_ham = None
        self.son_gri_sol = None
        self.tiklama = None
        self.toplanan = []
        self._onizleme = None

        self.tahta = kalibrasyon.TahtaTanimi()
        self._ayarlari_yukle()
        self._arayuz()
        self._kalib_yukle_sessiz()
        self.kok.protocol("WM_DELETE_WINDOW", self._kapat)
        self.kok.after(40, self._ekrani_guncelle)

    # ------------------------------------------------------------ arayuz
    def _arayuz(self):
        ust = tk.Frame(self.kok, bg=BG)
        ust.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        sol = tk.Frame(ust, bg="#101018")
        sol.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.gorsel = tk.Label(sol, bg="#101018")
        self.gorsel.pack(fill=tk.BOTH, expand=True)
        self.gorsel.bind("<Button-1>", self._goruntuye_tikla)

        sag = tk.Frame(ust, bg=BG, width=560)
        sag.pack(side=tk.RIGHT, fill=tk.Y)
        sag.pack_propagate(False)

        self.sekmeler = ttk.Notebook(sag)
        self.sekmeler.pack(fill=tk.BOTH, expand=True)
        for ad, kur in (("1 · Kameralar", self._sekme_kamera),
                        ("2 · Kalibrasyon", self._sekme_kalibrasyon),
                        ("3 · Derinlik", self._sekme_derinlik),
                        ("4 · Olcum", self._sekme_olcum),
                        ("Yardim", self._sekme_yardim)):
            cerceve = tk.Frame(self.sekmeler, bg=KART)
            self.sekmeler.add(cerceve, text=ad)
            kur(self._kaydirilabilir(cerceve))

        self.durum = tk.Label(self.kok, text="Hazir", bg="#16161f",
                              fg=SOLUK, anchor="w", font=("Consolas", 9))
        self.durum.pack(fill=tk.X, side=tk.BOTTOM)

    def _kaydirilabilir(self, ust):
        """Icerik tasarsa dikey kaydirma cubugu cikar."""
        tuval = tk.Canvas(ust, bg=KART, highlightthickness=0)
        cubuk = ttk.Scrollbar(ust, orient="vertical", command=tuval.yview)
        ic = tk.Frame(tuval, bg=KART)
        ic.bind("<Configure>",
                lambda e: tuval.configure(scrollregion=tuval.bbox("all")))
        pencere = tuval.create_window((0, 0), window=ic, anchor="nw")
        tuval.bind("<Configure>",
                   lambda e: tuval.itemconfig(pencere, width=e.width))
        tuval.configure(yscrollcommand=cubuk.set)
        tuval.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        cubuk.pack(side=tk.RIGHT, fill=tk.Y)

        def teker(e):
            tuval.yview_scroll(int(-1 * (e.delta / 120)), "units")
        ic.bind("<Enter>", lambda e: tuval.bind_all("<MouseWheel>", teker))
        ic.bind("<Leave>", lambda e: tuval.unbind_all("<MouseWheel>"))
        return ic

    def _baslik(self, ust, metin, aciklama=None):
        tk.Label(ust, text=metin, bg=KART, fg=VURGU,
                 font=("Segoe UI", 11, "bold"), anchor="w"
                 ).pack(fill=tk.X, pady=(12, 2), padx=10)
        if aciklama:
            tk.Label(ust, text=aciklama, bg=KART, fg=SOLUK,
                     font=("Segoe UI", 8), justify="left", anchor="w",
                     wraplength=500).pack(fill=tk.X, padx=10, pady=(0, 4))
        tk.Frame(ust, bg=KENAR, height=1).pack(fill=tk.X, padx=10)

    def _buton(self, ust, metin, komut, aciklama, renk="#2d4a6a"):
        b = tk.Button(ust, text=metin, command=komut, bg=renk, fg="white",
                      font=("Segoe UI", 9, "bold"), relief="flat",
                      padx=10, pady=5, cursor="hand2")
        ipucu(b, aciklama)
        return b

    def _satir(self, ust):
        f = tk.Frame(ust, bg=KART)
        f.pack(fill=tk.X, padx=10, pady=3)
        return f

    def _sayi(self, ust, etiket, degisken, alt, ust_s, adim, aciklama,
              genislik=6):
        f = self._satir(ust)
        l = tk.Label(f, text=etiket, bg=KART, fg=YAZI,
                     font=("Segoe UI", 9))
        l.pack(side=tk.LEFT)
        s = tk.Spinbox(f, from_=alt, to=ust_s, increment=adim,
                       width=genislik, textvariable=degisken, bg=BG,
                       fg=YAZI, buttonbackground=KENAR, relief="flat",
                       font=("Consolas", 9))
        s.pack(side=tk.LEFT, padx=(6, 0))
        ipucu(l, aciklama)
        ipucu(s, aciklama)
        soru(f, aciklama, bg=KART).pack(side=tk.LEFT, padx=(4, 0))
        return s

    def _bilgi(self, ust, etiket, deger="—", renk=None):
        f = self._satir(ust)
        tk.Label(f, text=etiket, bg=KART, fg=SOLUK,
                 font=("Segoe UI", 9)).pack(side=tk.LEFT)
        l = tk.Label(f, text=deger, bg=KART, fg=renk or YAZI,
                     font=("Consolas", 9, "bold"))
        l.pack(side=tk.RIGHT)
        return l

    # ------------------------------------------------- 1. KAMERALAR
    def _sekme_kamera(self, u):
        self._baslik(
            u, "Bagli kameralari bul",
            "Tarama her kamerayi acip GERCEKTEN kare alabildigini "
            "dogrular. Acilan ama goruntu vermeyen sanal cihazlar "
            "elenir. Iki kameranin da takili oldugundan emin ol.")
        f = self._satir(u)
        self._buton(f, "Kameralari tara", self._kameralari_tara,
                    "Bagli tum kameralari bulur. Birkac saniye surer; "
                    "her cihaz acilip kapatilir.", "#2d5a3d"
                    ).pack(side=tk.LEFT)
        self._buton(f, "Cozunurlukleri tara", self._cozunurluk_tara,
                    "Secili iki kameranin GERCEKTEN destekledigi "
                    "cozunurlukleri bulur.\n\nNeden gerekli: bir "
                    "kameraya desteklemedigi bir cozunurluk verilince "
                    "surucu cogu zaman hata vermez, sessizce baska bir "
                    "boyuta duser. Bu tarama kare alip gercek boyutuna "
                    "bakar.\n\n30-60 saniye surebilir."
                    ).pack(side=tk.LEFT, padx=6)

        self.kamera_liste = tk.Listbox(
            u, height=6, bg=BG, fg=YAZI, selectbackground=VURGU,
            font=("Consolas", 9), relief="flat", highlightthickness=1,
            highlightbackground=KENAR)
        self.kamera_liste.pack(fill=tk.X, padx=10, pady=6)
        ipucu(self.kamera_liste,
              "Bulunan kameralar. Sol ve sag kamerayi asagidan sec.")

        self.sol_idx = tk.StringVar()
        self.sag_idx = tk.StringVar()
        for etiket, degisken, acik in (
                ("SOL kamera:", self.sol_idx,
                 "Stereo ciftin sol gozü. Hangisinin sol oldugunu "
                 "bilmiyorsan sec, canli goruntude kontrol et ve "
                 "gerekirse degistir - yanlis secim derinligi ters "
                 "cevirir ve olcum calismaz."),
                ("SAG kamera:", self.sag_idx,
                 "Stereo ciftin sag gozü. Iki kamera YATAY olarak "
                 "yan yana ve ayni yone bakiyor olmali.")):
            f = self._satir(u)
            l = tk.Label(f, text=etiket, bg=KART, fg=YAZI,
                         font=("Segoe UI", 9))
            l.pack(side=tk.LEFT)
            c = ttk.Combobox(f, textvariable=degisken, width=28,
                             state="readonly")
            c.pack(side=tk.LEFT, padx=(6, 0))
            ipucu(l, acik)
            ipucu(c, acik)
            soru(f, acik, bg=KART).pack(side=tk.LEFT, padx=(4, 0))
            if degisken is self.sol_idx:
                self.sol_kutu = c
            else:
                self.sag_kutu = c

        self.coz_var = tk.StringVar()
        f = self._satir(u)
        l = tk.Label(f, text="Cozunurluk:", bg=KART, fg=YAZI,
                     font=("Segoe UI", 9))
        l.pack(side=tk.LEFT)
        self.coz_kutu = ttk.Combobox(f, textvariable=self.coz_var,
                                     width=28, state="readonly")
        self.coz_kutu.pack(side=tk.LEFT, padx=(6, 0))
        COZ_ACIK = ("Iki kameranin ORTAK destekledigi cozunurlukler.\n\n"
                    "Yuksek cozunurluk daha ince ayrinti demek ama "
                    "islem yavaslar ve USB bant genisligi sinirlayabilir. "
                    "1280x720 ya da 1280x960 cogu durumda iyi bir "
                    "baslangic.\n\nONEMLI: kalibrasyon hangi "
                    "cozunurlukte yapildiysa olcum de o cozunurlukte "
                    "yapilmali. Cozunurluk degisirse yeniden kalibre et.")
        ipucu(l, COZ_ACIK)
        ipucu(self.coz_kutu, COZ_ACIK)
        soru(f, COZ_ACIK, bg=KART).pack(side=tk.LEFT, padx=(4, 0))

        f = self._satir(u)
        self._buton(f, "Kameralari ac", self._kameralari_ac,
                    "Secili iki kamerayi acar ve canli goruntuyu "
                    "baslatir. Sol tarafta iki goruntu yan yana "
                    "gorunur.", "#2d5a3d").pack(side=tk.LEFT)
        self._buton(f, "Kapat", self._kameralari_kapat,
                    "Kameralari birakir. Baska bir program kamerayi "
                    "kullanacaksa once burayi kullan."
                    ).pack(side=tk.LEFT, padx=6)
        self._buton(f, "Sol/Sag degistir", self._taraf_degistir,
                    "Iki kamerayi yer degistirir. Derinlik haritasi "
                    "tamamen bos ya da anlamsiz cikiyorsa ilk "
                    "deneyecegin sey budur.").pack(side=tk.LEFT)

        self._baslik(u, "Durum")
        self.lbl_kam_durum = self._bilgi(u, "Kameralar", "kapali", SARI)
        self.lbl_kam_coz = self._bilgi(u, "Cozunurluk")
        self.lbl_kam_fps = self._bilgi(u, "Kare hizi")
        self.lbl_kam_netlik = self._bilgi(u, "Netlik (sol / sag)")
        self.lbl_kam_parlak = self._bilgi(u, "Parlaklik (sol / sag)")
        tk.Label(u, bg=KART, fg=SOLUK, font=("Segoe UI", 8),
                 justify="left", anchor="w", wraplength=500,
                 text=("Netlik: Laplacian varyansi. Mutlak bir hedefi "
                       "yok; iki kameranin BIRBIRINE yakin olmasi ve "
                       "lense dokununca degismemesi onemli.\n"
                       "Parlaklik: 90-150 bandi iyi. 240 ustu doymus "
                       "demektir - doku kaybolur ve stereo esleme "
                       "calisamaz.")
                 ).pack(fill=tk.X, padx=10, pady=(2, 10))

    # ---------------------------------------------- 2. KALIBRASYON
    def _sekme_kalibrasyon(self, u):
        self._baslik(
            u, "Kalibrasyon deseni",
            "Kendi bastigin deseni tanit. Olculeri KUMPASLA ya da "
            "cetvelle ölç - yazicidan cikan desen neredeyse hicbir "
            "zaman tasarim olcusunde degildir.")

        self.t_tur = tk.StringVar(value=self.tahta.tur)
        f = self._satir(u)
        TUR_ACIK = ("ChArUco: satranc deseninin uzerine ArUco isaretleri "
                    "gomulu. Desenin bir kismi gorunse bile calisir ve "
                    "kose konumlari alt-piksel hassasiyetle bulunur. "
                    "Onerilen.\n\nSatranc: klasik satranc tahtasi. "
                    "Desenin TAMAMI gorunmek zorunda; kismen kapalıysa "
                    "kare bulunamaz.")
        l = tk.Label(f, text="Desen turu:", bg=KART, fg=YAZI,
                     font=("Segoe UI", 9))
        l.pack(side=tk.LEFT)
        for d, ad in (("charuco", "ChArUco"), ("satranc", "Satranc")):
            r = tk.Radiobutton(f, text=ad, variable=self.t_tur, value=d,
                               bg=KART, fg=YAZI, selectcolor=BG,
                               activebackground=KART, activeforeground=YAZI,
                               font=("Segoe UI", 9))
            r.pack(side=tk.LEFT, padx=4)
            ipucu(r, TUR_ACIK)
        ipucu(l, TUR_ACIK)
        soru(f, TUR_ACIK, bg=KART).pack(side=tk.LEFT, padx=(4, 0))

        self.t_kx = tk.IntVar(value=self.tahta.kare_x)
        self.t_ky = tk.IntVar(value=self.tahta.kare_y)
        self.t_kmm = tk.DoubleVar(value=self.tahta.kare_mm)
        self.t_mmm = tk.DoubleVar(value=self.tahta.marker_mm)
        self.t_sozluk = tk.StringVar(value=self.tahta.sozluk)
        self.t_eski = tk.BooleanVar(value=self.tahta.eski_desen)

        self._sayi(u, "Yatay kare sayisi:", self.t_kx, 3, 30, 1,
                   "Desendeki KARE sayisi (kose sayisi degil). "
                   "Satranc tahtasinda soldan saga kac kare varsa o.")
        self._sayi(u, "Dikey kare sayisi:", self.t_ky, 3, 30, 1,
                   "Desendeki dikey KARE sayisi.\n\nIpucu: yatay ve "
                   "dikey sayilarin FARKLI olmasi iyidir - desenin "
                   "yonu belirsiz kalmaz.")
        self._sayi(u, "Kare kenari (mm):", self.t_kmm, 1, 200, 0.1,
                   "Bir karenin OLCULEN kenar uzunlugu.\n\n"
                   "EN KRITIK DEGER BU. Yanlissa TUM olcumler ayni "
                   "oranda kayar ve hata sistemin icinden fark "
                   "edilemez.\n\nDogru olcme yontemi: bes karenin "
                   "toplam uzunlugunu olcup 5'e bol. Tek kare olcmek "
                   "cok hassas degil.")
        self._sayi(u, "Isaret kenari (mm):", self.t_mmm, 1, 200, 0.1,
                   "ChArUco'da karenin icindeki siyah isaretin olculen "
                   "kenari. Kare kenarindan kucuktur (genelde %70-80'i). "
                   "Satranc deseninde kullanilmaz.")
        f = self._satir(u)
        SOZ_ACIK = ("ChArUco isaretlerinin hangi sozlukten uretildigi. "
                    "Deseni ureten aracta hangisini sectiysen o. "
                    "En yaygin: DICT_4X4_50, DICT_4X4_100, "
                    "DICT_5X5_100, DICT_6X6_250.\n\nYanlis sozluk = "
                    "hicbir isaret bulunamaz.")
        l = tk.Label(f, text="ArUco sozlugu:", bg=KART, fg=YAZI,
                     font=("Segoe UI", 9))
        l.pack(side=tk.LEFT)
        c = ttk.Combobox(f, textvariable=self.t_sozluk, width=18,
                         state="readonly",
                         values=["DICT_4X4_50", "DICT_4X4_100",
                                 "DICT_4X4_250", "DICT_5X5_100",
                                 "DICT_5X5_250", "DICT_6X6_100",
                                 "DICT_6X6_250", "DICT_7X7_100"])
        c.pack(side=tk.LEFT, padx=(6, 0))
        ipucu(l, SOZ_ACIK)
        ipucu(c, SOZ_ACIK)
        soru(f, SOZ_ACIK, bg=KART).pack(side=tk.LEFT, padx=(4, 0))

        f = self._satir(u)
        cb = tk.Checkbutton(f, text="Eski desen duzeni (calib.io vb.)",
                            variable=self.t_eski, bg=KART, fg=YAZI,
                            selectcolor=BG, activebackground=KART,
                            activeforeground=YAZI, font=("Segoe UI", 9))
        cb.pack(side=tk.LEFT)
        ipucu(cb, "OpenCV 4.6'dan sonra ChArUco isaretlerinin "
                  "yerlesimi degisti. calib.io gibi araclarla ya da "
                  "eski OpenCV ile uretilmis desenlerde bu kutu "
                  "ISARETLI olmali.\n\nDesen goruluyor ama kalibrasyon "
                  "sacma sonuc veriyorsa once bunu degistirmeyi dene.")

        self._baslik(
            u, "Kare toplama",
            "Tahtayi farkli acilardan ve goruntunun farkli "
            "bolgelerinden gosterip kare topla. Kenarlar ve koseler "
            "onemli - lens bozulmasi orada belirgindir.")
        f = self._satir(u)
        self._buton(f, "Kare yakala", self._kare_yakala,
                    "O anki goruntu ciftini kalibrasyon setine ekler. "
                    "Desen iki kamerada da GORUNUYORSA kaydedilir.\n\n"
                    "Hedef: 15-25 kare. Tahtayi her karede biraz "
                    "farkli tut - egik, yakin, uzak, kenarlarda.",
                    "#2d5a3d").pack(side=tk.LEFT)
        self._buton(f, "Sonuncuyu sil", self._kare_sil,
                    "Son eklenen kareyi listeden cikarir.").pack(
            side=tk.LEFT, padx=6)
        self._buton(f, "Hepsini temizle", self._kare_temizle,
                    "Toplanan tum kareleri siler. Desen tanimini "
                    "degistirdiysen mutlaka temizle - eski kareler "
                    "yeni tanimla uyusmaz.", "#6a2d2d").pack(side=tk.LEFT)

        self.lbl_kare_sayi = self._bilgi(u, "Toplanan kare", "0")
        self.lbl_kare_son = self._bilgi(u, "Son kare")

        f = self._satir(u)
        self._buton(f, "KALIBRE ET", self._kalibre_et,
                    "Toplanan karelerle stereo kalibrasyon yapar.\n\n"
                    "Uc adim: her kamera ayri kalibre edilir, sonra "
                    "aralarindaki konum bulunur, sonra rektifikasyon "
                    "haritalari cikarilir.\n\nBirkac saniye ile birkac "
                    "dakika arasi surebilir.", "#6a4d1a").pack(side=tk.LEFT)
        self._buton(f, "Dosyadan yukle", self._kalib_dosyadan,
                    "Daha once kaydedilmis bir kalibrasyon dosyasi ac."
                    ).pack(side=tk.LEFT, padx=6)

        self._baslik(u, "Kalibrasyon sonucu")
        self.lbl_k_durum = self._bilgi(u, "Durum", "yok", SARI)
        self.lbl_k_rms = self._bilgi(u, "RMS")
        self.lbl_k_epi = self._bilgi(u, "Epipolar hata")
        self.lbl_k_baz = self._bilgi(u, "Baz uzunlugu")
        self.lbl_k_f = self._bilgi(u, "Odak uzunlugu")
        self.lbl_k_hassas = self._bilgi(u, "Derinlik adimi @500mm")
        tk.Label(u, bg=KART, fg=SOLUK, font=("Segoe UI", 8),
                 justify="left", anchor="w", wraplength=500,
                 text=("RMS: modelin kendi verisine uyumu. Tek basina "
                       "yaniltici - veriden zor kareleri atarak "
                       "dusurulebilir ama bu kalibrasyonu "
                       "iyilestirmez.\n"
                       "EPIPOLAR HATA: asil olcut. Rektifikasyondan "
                       "sonra ayni noktanin iki goruntude ayni satirda "
                       "cikip cikmadigi. 1 pikselin altinda olmali.")
                 ).pack(fill=tk.X, padx=10, pady=(2, 10))

    # ------------------------------------------------- 3. DERINLIK
    def _sekme_derinlik(self, u):
        self._baslik(
            u, "Derinlik haritasi",
            "Iki goruntu arasindaki kaymadan (disparity) mesafe "
            "hesaplanir. Kalibrasyon yuklu olmali.")
        f = self._satir(u)
        self.btn_derinlik = self._buton(
            f, "Derinligi AC", self._derinlik_ac_kapat,
            "Canli derinlik haritasini baslatir/durdurur. Islem "
            "yogundur; yavaslik olursa cozunurlugu dusur.", "#2d5a3d")
        self.btn_derinlik.pack(side=tk.LEFT)
        self._buton(f, "Goruntuyu kaydet", self._goruntu_kaydet,
                    "O anki goruntu, derinlik haritasi ve ham veriyi "
                    "'cikti' klasorune kaydeder.").pack(side=tk.LEFT, padx=6)

        self._baslik(
            u, "Arama araligi",
            "Algoritmanin kac piksellik kayma arayacagi. Olculebilen "
            "EN YAKIN mesafeyi belirler.")
        self.d_arama = tk.IntVar(value=128)
        self._sayi(u, "Arama araligi:", self.d_arama, 16, 512, 16,
                   "Kac piksellik kayma araninacak (16'nin kati).\n\n"
                   "En yakin olculebilir mesafe = f x baz / arama.\n\n"
                   "BUYUTMEK: daha yakin cisimler olculebilir, ama "
                   "islem yavaslar ve goruntunun SOL kenarinda bu "
                   "kadar piksellik bir bant yapisal olarak gecersiz "
                   "olur (eslesecek karsilik yok).\n\n"
                   "Asagidaki 'en yakin mesafe' satirina bakarak sec.")
        self.lbl_d_yakin = self._bilgi(u, "En yakin olculebilir")
        self.lbl_d_olu = self._bilgi(u, "Sol kenarda olu bant")

        self._baslik(u, "Esleme parametreleri")
        self.d_blok = tk.IntVar(value=7)
        self.d_benzersiz = tk.IntVar(value=15)
        self._sayi(u, "Blok boyutu:", self.d_blok, 3, 21, 2,
                   "Esleme penceresinin boyutu (tek sayi).\n\n"
                   "KUCUK: ince ayrinti yakalanir ama harita "
                   "gurultulu olur.\nBUYUK: harita yumusar ama ince "
                   "yapilar kaybolur.\n\n5-9 arasi cogu durumda iyi.")
        self._sayi(u, "Benzersizlik:", self.d_benzersiz, 0, 50, 1,
                   "En iyi eslesme, ikinci en iyiden bu oran kadar "
                   "iyi degilse eslesme REDDEDILIR.\n\n"
                   "YUKSEK: yalnizca kesin eslesmeler kabul edilir; "
                   "harita daha boslukli ama guvenilir.\n"
                   "DUSUK: dokusuz bolgelerde belirsiz eslesmeler de "
                   "kabul edilir; harita dolu gorunur ama yanlis "
                   "olabilir.")

        self._baslik(u, "On-isleme ve filtre")
        self.d_ton = tk.StringVar(value="histogram")
        f = self._satir(u)
        TON_ACIK = ("Iki kameranin parlaklik/ton farkini giderir.\n\n"
                    "Neden gerekli: esleme 'ayni nokta iki goruntude "
                    "ayni parlaklikta gorunur' varsayimina dayanir. "
                    "Iki kamera ayni sahneyi farkli tonda gorebilir.\n\n"
                    "Histogram: dagilimin tamamini esler. Onerilen.\n"
                    "Dogrusal: yalnizca ortalama ve sacilimi esitler.\n"
                    "Yok: kameralar zaten ayni ton veriyorsa.")
        l = tk.Label(f, text="Ton eslemesi:", bg=KART, fg=YAZI,
                     font=("Segoe UI", 9))
        l.pack(side=tk.LEFT)
        for d, ad in (("histogram", "Histogram"), ("dogrusal", "Dogrusal"),
                      ("yok", "Yok")):
            r = tk.Radiobutton(f, text=ad, variable=self.d_ton, value=d,
                               bg=KART, fg=YAZI, selectcolor=BG,
                               activebackground=KART, activeforeground=YAZI,
                               font=("Segoe UI", 8))
            r.pack(side=tk.LEFT, padx=2)
            ipucu(r, TON_ACIK)
        ipucu(l, TON_ACIK)
        soru(f, TON_ACIK, bg=KART).pack(side=tk.LEFT, padx=(4, 0))

        self.d_temizle = tk.BooleanVar(value=True)
        f = self._satir(u)
        cb = tk.Checkbutton(f, text="Haritayi temizle",
                            variable=self.d_temizle, bg=KART, fg=YAZI,
                            selectcolor=BG, activebackground=KART,
                            activeforeground=YAZI, font=("Segoe UI", 9))
        cb.pack(side=tk.LEFT)
        ipucu(cb, "Median filtre + kucuk delikleri kapatma + izole "
                  "kucuk yamalari silme.\n\nGurultuyu azaltir. Cok "
                  "kucuk cisimler olcuyorsan kapatmayi dene - silinen "
                  "yamalar cismin kendisi olabilir.")

        f = self._satir(u)
        self._buton(f, "Parametreleri uygula", self._derinlik_uygula,
                    "Degisiklikleri derinlik motoruna aktarir.",
                    "#2d5a3d").pack(side=tk.LEFT)
        self._buton(f, "Varsayilanlara don", self._derinlik_varsayilan,
                    "Genel amacli baslangic degerlerini yukler."
                    ).pack(side=tk.LEFT, padx=6)

        self._baslik(u, "Harita durumu")
        self.lbl_d_dolu = self._bilgi(u, "Harita doluluk")
        self.lbl_d_ham = self._bilgi(u, "GERCEK eslesme")
        self.lbl_d_merkez = self._bilgi(u, "Merkez mesafe")
        tk.Label(u, bg=KART, fg=SOLUK, font=("Segoe UI", 8),
                 justify="left", anchor="w", wraplength=500,
                 text=("'Harita doluluk' filtre SONRASI orandir ve "
                       "kalite olcusu DEGILDIR - filtre bosluklari "
                       "komsulardan TAHMIN ederek doldurur.\n"
                       "'GERCEK eslesme' filtre ONCESI gercekten "
                       "eslesen piksellerin orani. Guvenilirlik icin "
                       "bu satira bak; dusukse haritanin buyuk kismi "
                       "tahmindir.")
                 ).pack(fill=tk.X, padx=10, pady=(2, 10))

    # --------------------------------------------------- 4. OLCUM
    def _sekme_olcum(self, u):
        self._baslik(
            u, "Nesne olcumu",
            "Sol goruntude olcmek istedigin cisme TIKLA. Sistem o "
            "noktanin ait oldugu cismi ayirip 3B boyutlarini hesaplar.")

        f = self._satir(u)
        self._buton(f, "Kurulum kontrolu", self._kurulum_kontrol,
                    "Kamera yerlesimi olcum icin uygun mu, olcer.\n\n"
                    "Iki sey bakilir: kameranin yuzeye bakis acisi ve "
                    "olcum mesafesi.\n\nNeden onemli: cismin kameraya "
                    "DOGRU uzanan ekseni olculemez. Uzun bir cisim "
                    "kameraya dogru bakiyorsa sistem onun ancak bir "
                    "dilimini gorur.", "#1a5276").pack(side=tk.LEFT)

        self._baslik(u, "Segmentasyon yontemi")
        self.o_yontem = tk.StringVar(value="tolerans")
        YON_ACIK = (
            "Tiklanan pikselin hangi cisme ait oldugunu bulma "
            "yontemi.\n\n"
            "TOLERANS: tiklanan noktayla ayni derinlikteki komsulari "
            "alir. Cisim goruntu duzlemine paralel uzaniyorsa iyi "
            "calisir.\n\n"
            "WATERSHED: parlaklik gradyanlarindaki sirtlari kullanir. "
            "Cisim kameraya dogru uzaniyorsa (orn. ayakta duran uzun "
            "bir cisme tepeden bakiyorsan) tolerans yontemi cismin "
            "ancak bir dilimini yakalar; watershed tamamini alabilir.\n\n"
            "Ikisini de dene ve GORSELE bak.")
        f = self._satir(u)
        l = tk.Label(f, text="Yontem:", bg=KART, fg=YAZI,
                     font=("Segoe UI", 9))
        l.pack(side=tk.LEFT)
        for d, ad in (("tolerans", "Tolerans"), ("watershed", "Watershed")):
            r = tk.Radiobutton(f, text=ad, variable=self.o_yontem, value=d,
                               bg=KART, fg=YAZI, selectcolor=BG,
                               activebackground=KART, activeforeground=YAZI,
                               font=("Segoe UI", 9))
            r.pack(side=tk.LEFT, padx=4)
            ipucu(r, YON_ACIK)
        ipucu(l, YON_ACIK)
        soru(f, YON_ACIK, bg=KART).pack(side=tk.LEFT, padx=(4, 0))

        self.o_tol = tk.IntVar(value=30)
        self.o_gri = tk.IntVar(value=35)
        self.o_sinir = tk.IntVar(value=300)
        self.o_dis = tk.IntVar(value=450)

        self._sayi(u, "Derinlik toleransi (mm):", self.o_tol, 5, 200, 5,
                   "Bolge, derinligi tiklanan noktadan en fazla bu "
                   "kadar farkli olan pikselleri alir.\n\n"
                   "Bu bir DERINLIK toleransi (mm), disparity degil - "
                   "mesafeye gore otomatik cevrilir, boylece yakinda "
                   "da uzakta da ayni fiziksel kalinligi kapsar.\n\n"
                   "KUCUK: cismin yalnizca bir dilimi alinir.\n"
                   "BUYUK: bolge zemine tasar.\n\n"
                   "Yalnizca Tolerans yonteminde kullanilir.")
        self._sayi(u, "Parlaklik toleransi:", self.o_gri, 0, 200, 5,
                   "Tiklanan pikselin gri degerinden bu kadardan fazla "
                   "sapan pikseller bolgeden atilir. 0 = kapali.\n\n"
                   "Cisim ile zemin farkli renkteyse cok ise yarar. "
                   "Ayni renkteyse etkisiz.\n\nDIKKAT: cismin kendi "
                   "uzerinde parlak/koyu bolgeler varsa (etiket, "
                   "kapak, yansima) onlari da atabilir. Cismin bir "
                   "kismi eksik cikiyorsa once bunu gevset.")
        self._sayi(u, "Yaricap siniri (mm):", self.o_sinir, 50, 1000, 25,
                   "Tiklanan noktadan bu mesafeden uzaktaki noktalar "
                   "alinmaz. Bolgenin sahnenin yarisina yayilmasini "
                   "engeller.\n\nBu bir YARICAP: olcecegin cismin en "
                   "uzun kenarindan BUYUK olmali. Cismin ucuna "
                   "tiklarsan diger uc bu sinirin disinda kalabilir.")
        self._sayi(u, "Watershed dis yaricap:", self.o_dis, 100, 1200, 50,
                   "Arka plan isaretcisinin baslama yaricapi (piksel).\n\n"
                   "Cismin goruntudeki yaricapindan BUYUK olmali; "
                   "kucuk secilirse arka plan isaretcisi cismin "
                   "uzerine duser ve cisim parcalanir.\n\n"
                   "Yalnizca Watershed yonteminde kullanilir.")

        f = self._satir(u)
        self._buton(f, "OLC", self._olc,
                    "Son tikladigin noktadaki cismi olcer.\n\n"
                    "Once sol goruntude cisme tiklaman gerekir.",
                    "#2d5a3d").pack(side=tk.LEFT)
        self._buton(f, "Dogrulama gorseli", self._dogrulama_gorseli,
                    "Olculen kutuyu goruntu uzerine cizip kaydeder.\n\n"
                    "BU EN ONEMLI ADIM: sayilara bakip dogrulugu "
                    "anlamak guvenilir degil - yanlis bir bolge de "
                    "tesadufen makul sayilar uretebilir. Kutu cismi "
                    "sariyorsa olcum dogru, cevreye tasiyorsa bolge "
                    "kacmis demektir.", "#4a2d6a").pack(side=tk.LEFT, padx=6)

        self._baslik(u, "Sonuc")
        self.lbl_o_uzun = self._bilgi(u, "UZUN kenar")
        self.lbl_o_orta = self._bilgi(u, "ORTA kenar")
        self.lbl_o_kisa = self._bilgi(u, "KISA kenar")
        self.lbl_o_mesafe = self._bilgi(u, "Mesafe")
        self.lbl_o_piksel = self._bilgi(u, "Bolge buyuklugu")
        self.lbl_o_durum = tk.Label(
            u, text="", bg=KART, fg=SOLUK, font=("Segoe UI", 9),
            justify="left", anchor="w", wraplength=500)
        self.lbl_o_durum.pack(fill=tk.X, padx=10, pady=(6, 10))

        tk.Label(u, bg=KART, fg=SOLUK, font=("Segoe UI", 8),
                 justify="left", anchor="w", wraplength=500,
                 text=("Kenarlar buyukten kucuge siralanir; hangisinin "
                       "en/boy/yukseklik oldugu cismin duruşuna bagli "
                       "oldugu icin isim verilmez.\n\n"
                       "TEK BAKIS ACISININ SINIRI: sistem cismin "
                       "yalnizca gorunen yuzunu olcer. Silindirik bir "
                       "cismin arka yarisi gorunmedigi icin en kisa "
                       "kenar oldugundan kucuk cikar.")
                 ).pack(fill=tk.X, padx=10, pady=(0, 10))

    # -------------------------------------------------- YARDIM
    def _sekme_yardim(self, u):
        self._baslik(u, "Nasil kullanilir")
        adimlar = [
            ("1. Kameralar",
             "Iki kamerayi USB'ye tak. 'Kameralari tara' de. Listeden "
             "sol ve sag kamerayi sec. 'Cozunurluklari tara' ile "
             "ortak destekledikleri boyutlari bul, birini sec ve "
             "'Kameralari ac' de.\n\n"
             "Iki kamera YATAY olarak yan yana, ayni yone bakmali ve "
             "birbirine gore SABIT olmali. Kalibrasyondan sonra "
             "aralarindaki mesafe degisirse kalibrasyon gecersiz olur."),
            ("2. Kalibrasyon",
             "Bir ChArUco ya da satranc deseni bas, duz bir yuzeye "
             "yapistir. Olculerini KUMPASLA ol ve sekmede gir.\n\n"
             "Tahtayi iki kameranin da gordugu sekilde tut ve 'Kare "
             "yakala' de. Her karede tahtayi biraz farkli tut: egik, "
             "yakin, uzak, goruntunun kenarlarinda. 15-25 kare topla, "
             "sonra 'KALIBRE ET'.\n\n"
             "Epipolar hata 1 pikselin altindaysa kalibrasyon iyi."),
            ("3. Derinlik",
             "'Derinligi AC' de. Renkli harita cismin mesafesini "
             "gosterir.\n\n"
             "Harita bos ya da anlamsizsa sirasiyla: sol/sag kamerayi "
             "degistir, isigi artir, arama araligini buyut, cismin "
             "uzerine dokulu bir sey koy (duz beyaz yuzeyler "
             "eslesemez)."),
            ("4. Olcum",
             "Sol goruntude cisme tikla, sonra 'OLC'.\n\n"
             "Sonuc supheliyse 'Dogrulama gorseli' uret ve kutunun "
             "cismi sarip sarmadigina BAK. Sayilara guvenme - "
             "gorsele guven."),
        ]
        for baslik, metin in adimlar:
            tk.Label(u, text=baslik, bg=KART, fg=VURGU,
                     font=("Segoe UI", 10, "bold"), anchor="w"
                     ).pack(fill=tk.X, padx=10, pady=(10, 2))
            tk.Label(u, text=metin, bg=KART, fg=YAZI,
                     font=("Segoe UI", 9), justify="left", anchor="w",
                     wraplength=500).pack(fill=tk.X, padx=10)

        self._baslik(u, "Sik karsilasilan sorunlar")
        sorunlar = [
            ("Derinlik haritasi tamamen bos",
             "Sol ve sag kamera ters olabilir - 'Sol/Sag degistir' "
             "dene. Kalibrasyon yanlissa da bos cikar."),
            ("Harita benekli / parcali",
             "Isik yetersiz ya da yuzey dokusuz. Isigi artir; duz "
             "yuzeylere gecici olarak desenli bir kagit koy."),
            ("Cismin yalnizca bir kismi olculuyor",
             "Cisim kameraya DOGRU uzaniyor olabilir. Cismi cevir ya "
             "da kamerayi yandan bakacak sekilde yerlestir. "
             "'Kurulum kontrolu' bunu soyler.\n"
             "Alternatif: Watershed yontemini dene."),
            ("Olcum cevreye tasiyor",
             "Derinlik toleransini kucult, parlaklik toleransini "
             "dusur ya da yaricap sinirini kucult."),
            ("Kalibrasyon sacma sonuc veriyor",
             "Kare olcusunu kontrol et - en sik hata budur. "
             "ChArUco'da 'Eski desen duzeni' kutusunu degistirmeyi "
             "dene. Toplanan kareleri temizleyip yeniden topla."),
            ("Olcumler sistematik olarak buyuk/kucuk",
             "Kare olcusu yanlis girilmis olabilir. Bes karenin "
             "toplamini olcup 5'e bol ve yeniden kalibre et."),
        ]
        for baslik, metin in sorunlar:
            tk.Label(u, text="• " + baslik, bg=KART, fg=SARI,
                     font=("Segoe UI", 9, "bold"), anchor="w",
                     wraplength=500, justify="left"
                     ).pack(fill=tk.X, padx=10, pady=(8, 1))
            tk.Label(u, text=metin, bg=KART, fg=YAZI,
                     font=("Segoe UI", 9), justify="left", anchor="w",
                     wraplength=490).pack(fill=tk.X, padx=20)

        self._baslik(u, "Sistemin sinirlari")
        tk.Label(
            u, bg=KART, fg=YAZI, font=("Segoe UI", 9), justify="left",
            anchor="w", wraplength=500,
            text=("• Tek bakis acisi: cismin yalnizca gorunen yuzu "
                  "olculur. Arka taraf tahmin edilmez.\n\n"
                  "• Derinlik hassasiyeti mesafenin KARESIYLE "
                  "kotulesir. Iki kat uzaga koymak hatayi dort kat "
                  "artirir.\n\n"
                  "• Dokusuz yuzeyler (duz beyaz duvar, parlak metal, "
                  "cam) eslesemez; o bolgelerde derinlik uretilemez.\n\n"
                  "• Yansimalar hayalet derinlik uretir. Golge zararsiz "
                  "ama parlama zararlidir - isigi yandan ver.\n\n"
                  "• Kameraya DOGRU uzanan eksen olculemez.")
        ).pack(fill=tk.X, padx=10, pady=(2, 20))

    # ==================================================== islevler
    def _durum_yaz(self, metin, renk=SOLUK):
        self.durum.config(text=metin, fg=renk)
        self.kok.update_idletasks()

    def _kameralari_tara(self):
        self._durum_yaz("Kameralar taraniyor...", SARI)
        self.kameralar = kamera.kameralari_bul()
        self.kamera_liste.delete(0, tk.END)
        secenekler = []
        for k in self.kameralar:
            s = (f"[{k['indeks']}] {k['backend_ad']}  "
                 f"{k['genislik']}x{k['yukseklik']}")
            self.kamera_liste.insert(tk.END, s)
            secenekler.append(s)
        self.sol_kutu["values"] = secenekler
        self.sag_kutu["values"] = secenekler
        if len(secenekler) >= 2:
            self.sol_idx.set(secenekler[0])
            self.sag_idx.set(secenekler[1])
            self._durum_yaz(f"{len(self.kameralar)} kamera bulundu", YESIL)
        elif secenekler:
            self.sol_idx.set(secenekler[0])
            self._durum_yaz(
                "Yalnizca 1 kamera bulundu - stereo icin 2 gerekli", SARI)
        else:
            self._durum_yaz("Kamera bulunamadi", KIRMIZI)

    def _secili(self, degisken):
        m = degisken.get()
        if not m:
            return None
        try:
            i = int(m.split("]")[0].strip("["))
        except Exception:
            return None
        return next((k for k in self.kameralar if k["indeks"] == i), None)

    def _cozunurluk_tara(self):
        a, b = self._secili(self.sol_idx), self._secili(self.sag_idx)
        if not a or not b:
            messagebox.showwarning("Eksik", "Once iki kamerayi sec.")
            return
        self._kameralari_kapat()

        def ilerle(i, n, metin):
            self._durum_yaz(f"Taraniyor {i}/{n}: {metin}", SARI)

        self._durum_yaz("Sol kamera taraniyor...", SARI)
        ra = kamera.cozunurluk_tara(a["indeks"], a["backend_id"],
                                    ilerleme=ilerle)
        self._durum_yaz("Sag kamera taraniyor...", SARI)
        rb = kamera.cozunurluk_tara(b["indeks"], b["backend_id"],
                                    ilerleme=ilerle)
        ortak = kamera.ortak_cozunurlukler(ra, rb)
        if not ortak:
            self._durum_yaz("Ortak cozunurluk bulunamadi", KIRMIZI)
            return
        degerler = [f"{r['genislik']}x{r['yukseklik']}  {r['fourcc']}"
                    for r in ortak]
        self.coz_kutu["values"] = degerler
        self._ortak_coz = ortak
        # varsayilan: 1280 civari, yoksa ortanca
        varsayilan = next((d for d in degerler if d.startswith("1280x")),
                          degerler[len(degerler) // 2])
        self.coz_var.set(varsayilan)
        self._durum_yaz(f"{len(ortak)} ortak cozunurluk bulundu", YESIL)

    def _secili_coz(self):
        m = self.coz_var.get()
        if not m:
            return None
        try:
            wh = m.split()[0]
            w, h = [int(v) for v in wh.split("x")]
            fcc = m.split()[1] if len(m.split()) > 1 else "MJPG"
            return w, h, fcc
        except Exception:
            return None

    def _kameralari_ac(self):
        a, b = self._secili(self.sol_idx), self._secili(self.sag_idx)
        if not a or not b:
            messagebox.showwarning("Eksik", "Once iki kamerayi sec.")
            return
        if a["indeks"] == b["indeks"]:
            messagebox.showwarning("Hata", "Ayni kamera iki kez secilemez.")
            return
        coz = self._secili_coz()
        if not coz:
            messagebox.showwarning(
                "Eksik", "Once cozunurluk sec ('Cozunurlukleri tara').")
            return
        self._kameralari_kapat()
        w, h, fcc = coz
        self._durum_yaz("Kameralar aciliyor...", SARI)
        self.sol_cap, gw1, gh1 = kamera.kamera_ac(
            a["indeks"], a["backend_id"], w, h, fcc)
        self.sag_cap, gw2, gh2 = kamera.kamera_ac(
            b["indeks"], b["backend_id"], w, h, fcc)
        if self.sol_cap is None or self.sag_cap is None:
            self._durum_yaz("Kameralar acilamadi", KIRMIZI)
            self._kameralari_kapat()
            return
        if (gw1, gh1) != (gw2, gh2):
            self._durum_yaz(
                f"UYARI: kameralar farkli boyut verdi "
                f"{gw1}x{gh1} vs {gw2}x{gh2}", KIRMIZI)
        self.calisiyor = True
        self.lbl_kam_durum.config(text="acik", fg=YESIL)
        self.lbl_kam_coz.config(text=f"{gw1}x{gh1}")
        threading.Thread(target=self._yakalama, daemon=True).start()
        self._ayarlari_kaydet()
        self._durum_yaz("Kameralar acik", YESIL)

    def _kameralari_kapat(self):
        self.calisiyor = False
        self.derinlik_acik = False
        time.sleep(0.15)
        for c in (self.sol_cap, self.sag_cap):
            if c is not None:
                try:
                    c.release()
                except Exception:
                    pass
        self.sol_cap = self.sag_cap = None
        self.sol_kare = self.sag_kare = None
        if hasattr(self, "lbl_kam_durum"):
            self.lbl_kam_durum.config(text="kapali", fg=SARI)

    def _taraf_degistir(self):
        a, b = self.sol_idx.get(), self.sag_idx.get()
        self.sol_idx.set(b)
        self.sag_idx.set(a)
        if self.calisiyor:
            self._kameralari_ac()

    def _yakalama(self):
        fps_t, fps_n = time.time(), 0
        while self.calisiyor and self.sol_cap and self.sag_cap:
            try:
                self.sol_cap.grab()
                self.sag_cap.grab()
                r1, k1 = self.sol_cap.retrieve()
                r2, k2 = self.sag_cap.retrieve()
                if r1 and r2 and k1 is not None and k2 is not None:
                    self.sol_kare, self.sag_kare = k1, k2
                    fps_n += 1
                    if time.time() - fps_t >= 1.0:
                        self._fps = fps_n / (time.time() - fps_t)
                        fps_t, fps_n = time.time(), 0
                if self.derinlik_acik and self.haritalar is not None:
                    self._derinlik_hesapla()
            except Exception:
                time.sleep(0.05)
            time.sleep(0.005)

    def _derinlik_hesapla(self):
        try:
            m1x, m1y, m2x, m2y = self.haritalar
            rl = cv2.remap(self.sol_kare, m1x, m1y, cv2.INTER_LINEAR)
            rr = cv2.remap(self.sag_kare, m2x, m2y, cv2.INTER_LINEAR)
            gl = cv2.cvtColor(rl, cv2.COLOR_BGR2GRAY)
            gr = cv2.cvtColor(rr, cv2.COLOR_BGR2GRAY)
            dsp, ham = self.motor.hesapla(gl, gr)
            self.son_dsp, self.son_ham, self.son_gri_sol = dsp, ham, gl
            self.son_rekt_sol = rl
        except Exception:
            pass

    # ------------------------------------------------ ekran
    def _ekrani_guncelle(self):
        try:
            if self.sol_kare is not None and self.sag_kare is not None:
                sol, sag = self.sol_kare, self.sag_kare
                if self.derinlik_acik and self.son_dsp is not None:
                    self._derinlik_bilgi()
                    kalib = self.kalib
                    f = float(kalib["P1"][0, 0]) if kalib is not None else None
                    B = (float(np.linalg.norm(kalib["T"])) * 1000.0
                         if kalib is not None else None)
                    renk = derinlik.renklendir(self.son_dsp, 200, 1500, f, B)
                    taban = getattr(self, "son_rekt_sol", sol)
                    maske = self.son_dsp > 0
                    gosterim = taban.copy()
                    gosterim[maske] = cv2.addWeighted(
                        taban, 0.4, renk, 0.6, 0)[maske]
                    if self.tiklama:
                        x, y = self.tiklama
                        cv2.drawMarker(gosterim, (x, y), (0, 0, 255),
                                       cv2.MARKER_CROSS, 40, 2)
                    birlesik = np.hstack([gosterim, renk])
                else:
                    self._kamera_bilgi()
                    birlesik = np.hstack([sol, sag])
                self._goster(birlesik)
        except Exception:
            pass
        self.kok.after(50, self._ekrani_guncelle)

    def _goster(self, bgr):
        h, w = bgr.shape[:2]
        gw = max(self.gorsel.winfo_width(), 100)
        gh = max(self.gorsel.winfo_height(), 100)
        olcek = min(gw / w, gh / h)
        yeni = cv2.resize(bgr, (max(1, int(w * olcek)),
                                max(1, int(h * olcek))))
        self._son_olcek = olcek
        self._son_boyut = (w, h)
        img = ImageTk.PhotoImage(
            Image.fromarray(cv2.cvtColor(yeni, cv2.COLOR_BGR2RGB)))
        self.gorsel.configure(image=img)
        self.gorsel.image = img
        self._onizleme = yeni

    def _kamera_bilgi(self):
        try:
            gl = cv2.cvtColor(self.sol_kare, cv2.COLOR_BGR2GRAY)
            gr = cv2.cvtColor(self.sag_kare, cv2.COLOR_BGR2GRAY)
            n1, n2 = kamera.netlik_skoru(gl), kamera.netlik_skoru(gr)
            p1, _ = kamera.kare_parlakligi(gl)
            p2, _ = kamera.kare_parlakligi(gr)
            self.lbl_kam_netlik.config(text=f"{n1:.0f} / {n2:.0f}")
            renk = YESIL if 90 <= p1 <= 150 and 90 <= p2 <= 150 else SARI
            if p1 > 235 or p2 > 235:
                renk = KIRMIZI
            self.lbl_kam_parlak.config(text=f"{p1:.0f} / {p2:.0f}", fg=renk)
            if hasattr(self, "_fps"):
                self.lbl_kam_fps.config(text=f"{self._fps:.1f} fps")
        except Exception:
            pass

    def _derinlik_bilgi(self):
        try:
            d = self.son_dsp
            olu = self.motor.ayarlar.arama_basi + \
                self.motor.ayarlar.arama_araligi
            gecerli = d[:, olu:] > 0
            self.lbl_d_dolu.config(text=f"%{gecerli.mean()*100:.1f}")
            if self.son_ham is not None:
                ham = self.son_ham[:, olu:]
                oran = float(ham.mean()) * 100
                self.lbl_d_ham.config(
                    text=f"%{oran:.1f}",
                    fg=YESIL if oran > 60 else (SARI if oran > 30
                                                else KIRMIZI))
            if self.kalib is not None:
                pts = derinlik.noktalar_3b(d, self.kalib["Q"])
                h, w = d.shape
                Z = pts[h // 2, w // 2, 2]
                self.lbl_d_merkez.config(
                    text=f"{Z:.0f} mm" if 0 < Z < 1e5 else "—")
        except Exception:
            pass

    def _goruntuye_tikla(self, olay):
        if self._onizleme is None or self.son_dsp is None:
            return
        oh, ow = self._onizleme.shape[:2]
        gw, gh = self.gorsel.winfo_width(), self.gorsel.winfo_height()
        # Label goruntuyu ORTALAR - ofseti hesaba katmazsak tiklama kayar
        ox, oy = (gw - ow) // 2, (gh - oh) // 2
        x, y = olay.x - ox, olay.y - oy
        if not (0 <= x < ow and 0 <= y < oh):
            return
        yarim = ow // 2
        if x >= yarim:                       # sag panel = derinlik gorseli
            x -= yarim
        olcek = getattr(self, "_son_olcek", 1.0)
        W, H = self._son_boyut
        tam_x = int(x / olcek)
        tam_y = int(y / olcek)
        # birlesik goruntu iki panel yan yana; tek panelin genisligi W/2
        tam_x = int(tam_x % (W // 2)) if W else tam_x
        d = self.son_dsp
        tam_x = max(0, min(tam_x, d.shape[1] - 1))
        tam_y = max(0, min(tam_y, d.shape[0] - 1))
        self.tiklama = (tam_x, tam_y)
        self._durum_yaz(f"Tiklanan nokta: ({tam_x}, {tam_y})", VURGU)

    # --------------------------------------------- kalibrasyon
    def _tahtayi_oku(self):
        return kalibrasyon.TahtaTanimi(
            tur=self.t_tur.get(), kare_x=self.t_kx.get(),
            kare_y=self.t_ky.get(), kare_mm=self.t_kmm.get(),
            marker_mm=self.t_mmm.get(), sozluk=self.t_sozluk.get(),
            eski_desen=self.t_eski.get())

    def _kare_yakala(self):
        if self.sol_kare is None or self.sag_kare is None:
            self._durum_yaz("Once kameralari ac", SARI)
            return
        tahta = self._tahtayi_oku()
        board, det = tahta.olustur()
        gl = cv2.cvtColor(self.sol_kare, cv2.COLOR_BGR2GRAY)
        gr = cv2.cvtColor(self.sag_kare, cv2.COLOR_BGR2GRAY)
        _, _, _, nl = kalibrasyon.kose_bul(gl, tahta, board, det)
        _, _, _, nr = kalibrasyon.kose_bul(gr, tahta, board, det)
        if nl < 6 or nr < 6:
            self._durum_yaz(
                f"Desen yeterince gorunmuyor (sol {nl}, sag {nr} kose). "
                "Tahtayi iki kameranin da tam gordugunden emin ol.",
                KIRMIZI)
            return
        self.toplanan.append((gl.copy(), gr.copy()))
        i = len(self.toplanan)
        cv2.imwrite(os.path.join(KARE_KLASOR, f"S_{i:03d}.png"), gl)
        cv2.imwrite(os.path.join(KARE_KLASOR, f"G_{i:03d}.png"), gr)
        self.lbl_kare_sayi.config(text=str(i))
        self.lbl_kare_son.config(text=f"sol {nl} / sag {nr} kose")
        self._durum_yaz(f"{i}. kare eklendi (sol {nl}, sag {nr} kose)",
                        YESIL)

    def _kare_sil(self):
        if self.toplanan:
            self.toplanan.pop()
            self.lbl_kare_sayi.config(text=str(len(self.toplanan)))
            self._durum_yaz("Son kare silindi", SARI)

    def _kare_temizle(self):
        self.toplanan = []
        self.lbl_kare_sayi.config(text="0")
        self._durum_yaz("Kareler temizlendi", SARI)

    def _kalibre_et(self):
        if len(self.toplanan) < 5:
            messagebox.showwarning(
                "Yetersiz kare",
                f"{len(self.toplanan)} kare var. En az 5 gerekli, "
                "15-25 onerilir.")
            return
        tahta = self._tahtayi_oku()
        h, w = self.toplanan[0][0].shape[:2]
        self._durum_yaz("Kalibre ediliyor...", SARI)

        def ilerle(i, n, metin):
            self._durum_yaz(f"Kalibrasyon: {metin}"
                            + (f" ({i}/{n})" if n else ""), SARI)

        sonuc, hata = kalibrasyon.stereo_kalibre(
            self.toplanan, (w, h), tahta, ilerleme=ilerle)
        if sonuc is None:
            self.lbl_k_durum.config(text="basarisiz", fg=KIRMIZI)
            self._durum_yaz(hata, KIRMIZI)
            messagebox.showerror("Kalibrasyon basarisiz", hata)
            return
        self._durum_yaz("Epipolar hata olculuyor...", SARI)
        epi, n = kalibrasyon.epipolar_hata(sonuc, self.toplanan, tahta)
        sonuc["epipolar_px"] = np.array(epi)
        kalibrasyon.kaydet(sonuc, KALIB_YOL)
        self.tahta = tahta
        self._ayarlari_kaydet()
        self._kalib_uygula(sonuc, epi)
        self._durum_yaz(f"Kalibrasyon tamam - epipolar hata {epi:.3f} px",
                        YESIL)

    def _kalib_dosyadan(self):
        yol = filedialog.askopenfilename(
            title="Kalibrasyon dosyasi", initialdir=VERI,
            filetypes=[("NumPy arsivi", "*.npz")])
        if not yol:
            return
        s = kalibrasyon.yukle(yol)
        if s is None or "Q" not in s:
            messagebox.showerror("Hata", "Gecerli bir kalibrasyon degil.")
            return
        self._kalib_uygula(s, float(s.get("epipolar_px", float("nan"))))
        self._durum_yaz("Kalibrasyon yuklendi", YESIL)

    def _kalib_yukle_sessiz(self):
        s = kalibrasyon.yukle(KALIB_YOL)
        if s is not None and "Q" in s:
            self._kalib_uygula(s, float(s.get("epipolar_px", float("nan"))))

    def _kalib_uygula(self, sonuc, epi=float("nan")):
        self.kalib = sonuc
        self.haritalar = kalibrasyon.rektifikasyon_haritalari(sonuc)
        o = kalibrasyon.ozet(sonuc)
        self.lbl_k_durum.config(text="hazir", fg=YESIL)
        self.lbl_k_rms.config(
            text=f"{o['rms']:.3f} px  (sol {o['rms_sol']:.3f} / "
                 f"sag {o['rms_sag']:.3f})")
        if np.isfinite(epi):
            self.lbl_k_epi.config(
                text=f"{epi:.3f} px",
                fg=YESIL if epi < 1.0 else (SARI if epi < 2.0 else KIRMIZI))
        self.lbl_k_baz.config(text=f"{o['baz_mm']:.2f} mm")
        self.lbl_k_f.config(text=f"{o['f_rektifiye_px']:.1f} px")
        self.lbl_k_hassas.config(text=f"{o['derinlik_adimi'][500]:.2f} mm")
        self._derinlik_bilgi_guncelle()

    # ------------------------------------------------- derinlik
    def _derinlik_ayar_oku(self):
        return derinlik.DerinlikAyarlari(
            arama_araligi=self.d_arama.get(), blok=self.d_blok.get(),
            benzersizlik=self.d_benzersiz.get(),
            ton_esleme=self.d_ton.get(), temizle=self.d_temizle.get())

    def _derinlik_uygula(self):
        self.motor.ayarla(self._derinlik_ayar_oku())
        self._derinlik_bilgi_guncelle()
        self._durum_yaz("Derinlik parametreleri guncellendi", YESIL)

    def _derinlik_varsayilan(self):
        self.d_arama.set(128)
        self.d_blok.set(7)
        self.d_benzersiz.set(15)
        self.d_ton.set("histogram")
        self.d_temizle.set(True)
        self._derinlik_uygula()

    def _derinlik_bilgi_guncelle(self):
        a = self._derinlik_ayar_oku()
        if self.kalib is not None:
            f = float(self.kalib["P1"][0, 0])
            B = float(np.linalg.norm(self.kalib["T"])) * 1000.0
            W = int(self.kalib["image_size"][0])
            self.lbl_d_yakin.config(
                text=f"{a.en_yakin_mesafe(f, B):.0f} mm")
            self.lbl_d_olu.config(text=f"%{a.olu_kenar_yuzde(W):.1f}")

    def _derinlik_ac_kapat(self):
        if self.kalib is None:
            messagebox.showwarning(
                "Kalibrasyon yok",
                "Derinlik icin once kalibrasyon gerekli (adim 2).")
            return
        if not self.calisiyor:
            messagebox.showwarning("Kamera kapali", "Once kameralari ac.")
            return
        self.derinlik_acik = not self.derinlik_acik
        self.btn_derinlik.config(
            text="Derinligi KAPAT" if self.derinlik_acik else "Derinligi AC",
            bg="#6a2d2d" if self.derinlik_acik else "#2d5a3d")

    def _goruntu_kaydet(self):
        if self.son_dsp is None:
            self._durum_yaz("Once derinligi ac", SARI)
            return
        ad = time.strftime("cekim_%Y%m%d_%H%M%S")
        yol = os.path.join(CIKTI, ad)
        cv2.imwrite(yol + "_sol.png", getattr(self, "son_rekt_sol",
                                              self.sol_kare))
        np.savez_compressed(
            yol + "_veri.npz", disparity=self.son_dsp,
            ham_maske=self.son_ham, gri_sol=self.son_gri_sol)
        self._durum_yaz(f"Kaydedildi: {ad}", YESIL)

    # ---------------------------------------------------- olcum
    def _kurulum_kontrol(self):
        if self.son_dsp is None or self.kalib is None:
            self._durum_yaz("Once derinligi ac", SARI)
            return
        pts = derinlik.noktalar_3b(self.son_dsp, self.kalib["Q"])
        s = olcum.kurulum_kontrolu(self.son_dsp, pts, tikla=self.tiklama)
        if s["uyarilar"]:
            self.lbl_o_durum.config(text="  ".join(s["uyarilar"]),
                                    fg=SARI)
        else:
            self.lbl_o_durum.config(
                text=(f"Kurulum uygun gorunuyor. Yuzey acisi "
                      f"{s['aci']:.0f} derece, mesafe "
                      f"{s['mesafe']:.0f} mm."), fg=YESIL)

    def _olc(self):
        if self.son_dsp is None or self.kalib is None:
            self._durum_yaz("Once derinligi ac", SARI)
            return
        if self.tiklama is None:
            self.lbl_o_durum.config(
                text="Once sol goruntude olcmek istedigin cisme tikla.",
                fg=SARI)
            return
        x, y = self.tiklama
        pts = derinlik.noktalar_3b(self.son_dsp, self.kalib["Q"])
        f = float(self.kalib["P1"][0, 0])
        B = float(np.linalg.norm(self.kalib["T"])) * 1000.0
        sonuc, hata = olcum.olc(
            self.son_dsp, pts, self.son_gri_sol, x, y,
            yontem=self.o_yontem.get(), f_px=f, baz_mm=B,
            tolerans_mm=float(self.o_tol.get()),
            parlaklik_tol=float(self.o_gri.get()),
            sinir_mm=float(self.o_sinir.get()),
            dis_yaricap=int(self.o_dis.get()))
        if sonuc is None:
            self.lbl_o_durum.config(text=hata, fg=KIRMIZI)
            return
        self._son_olcum = sonuc
        self.lbl_o_uzun.config(text=f"{sonuc['uzun']:.1f} mm")
        self.lbl_o_orta.config(text=f"{sonuc['orta']:.1f} mm")
        self.lbl_o_kisa.config(text=f"{sonuc['kisa']:.1f} mm")
        self.lbl_o_mesafe.config(text=f"{sonuc['mesafe']:.0f} mm")
        self.lbl_o_piksel.config(text=f"{sonuc['piksel']:,} px")
        self.lbl_o_durum.config(
            text=("Olculdu. Sonucu KABUL ETMEDEN ONCE 'Dogrulama "
                  "gorseli' uret ve kutunun cismi sarip sarmadigina bak."),
            fg=VURGU)

    def _dogrulama_gorseli(self):
        s = getattr(self, "_son_olcum", None)
        if s is None or self.kalib is None:
            self._durum_yaz("Once bir olcum yap", SARI)
            return
        x, y = self.tiklama
        vis = olcum.kutu_ciz(self.son_gri_sol, s, self.kalib["P1"], x, y)
        ad = time.strftime("olcum_%Y%m%d_%H%M%S") + ".png"
        yol = os.path.join(CIKTI, ad)
        cv2.imwrite(yol, vis)
        self._durum_yaz(f"Dogrulama gorseli: {ad}", YESIL)
        try:
            os.startfile(yol)
        except Exception:
            pass

    # ---------------------------------------------------- ayarlar
    def _ayarlari_kaydet(self):
        try:
            d = {"tahta": self._tahtayi_oku().sozluge(),
                 "cozunurluk": self.coz_var.get(),
                 "sol": self.sol_idx.get(), "sag": self.sag_idx.get()}
            with open(AYAR_YOL, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _ayarlari_yukle(self):
        try:
            if os.path.exists(AYAR_YOL):
                with open(AYAR_YOL, encoding="utf-8") as f:
                    d = json.load(f)
                if "tahta" in d:
                    self.tahta = kalibrasyon.TahtaTanimi.sozlukten(d["tahta"])
        except Exception:
            pass

    def _kapat(self):
        self._ayarlari_kaydet()
        self._kameralari_kapat()
        self.kok.destroy()


def main():
    kok = tk.Tk()
    stil = ttk.Style()
    try:
        stil.theme_use("clam")
    except Exception:
        pass
    stil.configure("TNotebook", background=BG, borderwidth=0)
    stil.configure("TNotebook.Tab", background=KART, foreground=YAZI,
                   padding=(12, 6), font=("Segoe UI", 9))
    stil.map("TNotebook.Tab", background=[("selected", VURGU)],
             foreground=[("selected", "#101018")])
    StereoKit(kok)
    kok.mainloop()


if __name__ == "__main__":
    main()
