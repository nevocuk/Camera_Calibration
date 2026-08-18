"""Kalibrasyona hazir miyiz? Tum on kosullari kontrol eder.

Kullanim (camera_test.py KAPALI olmali):
    .\\calistir.ps1 kalibrasyon_hazirlik

Kontrol edilenler:
  1. Kamera ayarlari dosyasi tam mi
  2. Iki kamera dengeli mi (GORUNTU olculerek — cap.get() guvenilmez)
  3. Pozlama uygun mu (cok karanlik/yanik degil)
  4. ChArUco konfigurasyonu gecerli mi
  5. Desen SU AN tespit edilebiliyor mu (ikisinde de)
  6. Cozunurluk konfigurasyonla uyusuyor mu
  7. Eski kalibrasyon kareleri temizlenmis mi (ODAK DEGISTIYSE ZORUNLU)
"""
import json
import os
import sys
import time
import numpy as np
import cv2

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
SETTINGS = os.path.join(PROJECT_DIR, "data", "camera_settings.json")
CONFIG = os.path.join(PROJECT_DIR, "data", "charuco_config.json")
FRAMES = os.path.join(PROJECT_DIR, "calibration", "frames")
CALIB = os.path.join(PROJECT_DIR, "calibration", "calib_result.npz")

GECER, UYARI, KAL = [], [], []


def ok(m):
    GECER.append(m)
    print(f"  [OK]     {m}")


def uy(m):
    UYARI.append(m)
    print(f"  [UYARI]  {m}")


def hata(m):
    KAL.append(m)
    print(f"  [KALDI]  {m}")


def main():
    print("=" * 72)
    print("KALIBRASYON HAZIRLIK KONTROLU")
    print("=" * 72)

    # --- 1. Ayar dosyasi ---
    print("\n1) Kamera ayarlari")
    if not os.path.exists(SETTINGS):
        hata("camera_settings.json yok")
        return
    s = json.load(open(SETTINGS, encoding="utf-8"))
    gerekli = ["exposure", "gain", "brightness", "contrast", "saturation",
               "sharpness", "gamma", "left_idx", "right_idx"]
    eksik = [k for k in gerekli if k not in s]
    if eksik:
        hata(f"ayar dosyasinda eksik alan: {', '.join(eksik)}")
    else:
        ok(f"tum ayarlar mevcut (SOL=idx{s['left_idx']} SAG=idx{s['right_idx']})")
    for k in ("exp_offset_r", "gain_offset_r", "bright_offset_r"):
        if abs(s.get(k, 0)) > 0.01:
            uy(f"{k}={s[k]} — telafi sifirdan farkli, kameralar esitse gereksiz")

    # --- 4. ChArUco konfig ---
    print("\n2) ChArUco konfigurasyonu")
    cfg = json.load(open(CONFIG, encoding="utf-8"))
    sq = cfg.get("olculen_kare_boyutu_mm")
    if not sq:
        hata("olculen_kare_boyutu_mm bos — deseni kumpasla olcup gir!")
    else:
        tas = cfg["square_length_mm"]
        ok(f"olculen kare = {sq} mm (tasarim {tas} mm)")
        if abs(sq - tas) / tas > 0.3:
            uy(f"olculen deger tasarimdan %{abs(sq-tas)/tas*100:.0f} farkli — dogru mu?")
    calib_res = cfg.get("calib_resolution")
    ok(f"hedef cozunurluk {calib_res[0]}x{calib_res[1]}, "
       f"sozluk {cfg['aruco_dict']}, {cfg['squares_x']}x{cfg['squares_y']}")

    # --- 7. Eski kareler ---
    print("\n3) Kalibrasyon kareleri")
    kareler = sorted([f for f in os.listdir(FRAMES) if f.startswith("L_")]) \
        if os.path.isdir(FRAMES) else []
    calib_t = os.path.getmtime(CALIB) if os.path.exists(CALIB) else 0
    kare_t = max((os.path.getmtime(os.path.join(FRAMES, f)) for f in kareler),
                 default=0)

    def zaman(t):
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(t))

    if not kareler:
        ok("frames/ bos — yeni set toplamaya hazir")
    elif calib_t > kare_t:
        # Kalibrasyon karelerden SONRA uretilmis -> bu kareler onu uretti.
        # Bayat degiller; yeniden kalibrasyon icin bir engel yok.
        ok(f"{len(kareler)} kare mevcut ve kalibrasyon bunlardan uretilmis "
           f"(kalibrasyon {zaman(calib_t)} > son kare {zaman(kare_t)})")
        uy("Yeni kare EKLEYECEKSEN mevcut sete ekleyip tekrar kalibre et; "
           "SIFIRDAN baslayacaksan 'Yeni Set Baslat' ile arsivle")
    else:
        hata(f"{len(kareler)} kare var ve kalibrasyondan YENI "
             f"(son kare {zaman(kare_t)} > kalibrasyon {zaman(calib_t)}) — "
             f"kalibrasyon guncel degil, yeniden calistir")

    if os.path.exists(CALIB):
        try:
            cd = np.load(CALIB)
            rms = float(cd["rms"])
            limit = 0.4 * (int(cd["image_size"][0]) / 960.0)
            if rms <= limit:
                ok(f"mevcut kalibrasyon RMS {rms:.4f} (limit {limit:.3f}) — gecerli")
            else:
                uy(f"mevcut kalibrasyon RMS {rms:.4f} > limit {limit:.3f}")
        except Exception:
            pass

    # --- 2,3,5,6. Canli kamera kontrolleri ---
    print("\n4) Canli kamera kontrolu")
    li, ri = s["left_idx"], s["right_idx"]
    W, H = calib_res
    caps = {}
    for ad, idx in (("SOL", li), ("SAG", ri)):
        c = cv2.VideoCapture(idx, cv2.CAP_MSMF)
        if not c.isOpened():
            hata(f"{ad} kamera (idx {idx}) acilamadi — camera_test.py acik mi?")
            for x in caps.values():
                x.release()
            ozet()
            return
        c.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        c.set(cv2.CAP_PROP_FRAME_WIDTH, W)
        c.set(cv2.CAP_PROP_FRAME_HEIGHT, H)
        for p, v in ((cv2.CAP_PROP_AUTO_EXPOSURE, 0.25),
                     (cv2.CAP_PROP_AUTO_WB, 0),
                     (cv2.CAP_PROP_BRIGHTNESS, s["brightness"]),
                     (cv2.CAP_PROP_CONTRAST, s["contrast"]),
                     (cv2.CAP_PROP_SATURATION, s["saturation"]),
                     (cv2.CAP_PROP_SHARPNESS, s["sharpness"]),
                     (cv2.CAP_PROP_GAMMA, s["gamma"]),
                     (cv2.CAP_PROP_HUE, 0),
                     (cv2.CAP_PROP_BACKLIGHT, 0),
                     (cv2.CAP_PROP_GAIN, s["gain"]),
                     (cv2.CAP_PROP_EXPOSURE, s["exposure"])):
            c.set(p, v)
        caps[ad] = c
    time.sleep(1.5)
    for _ in range(10):
        for c in caps.values():
            c.grab()
    for ad, c in caps.items():          # MSMF: akis sonrasi tekrar yaz
        c.set(cv2.CAP_PROP_EXPOSURE, s["exposure"])
        c.set(cv2.CAP_PROP_GAMMA, s["gamma"])
    time.sleep(0.8)

    kare = {}
    for ad, c in caps.items():
        gs = []
        for _ in range(6):
            c.grab()
            r, f = c.retrieve()
            if r:
                gs.append(f)
        kare[ad] = gs[-1] if gs else None

    # cozunurluk
    for ad, c in caps.items():
        rw = int(c.get(cv2.CAP_PROP_FRAME_WIDTH))
        rh = int(c.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if (rw, rh) != (W, H):
            hata(f"{ad} cozunurluk {rw}x{rh}, beklenen {W}x{H}")
        else:
            ok(f"{ad} cozunurluk {rw}x{rh}")

    # parlaklik / denge
    gl = cv2.cvtColor(kare["SOL"], cv2.COLOR_BGR2GRAY)
    gr = cv2.cvtColor(kare["SAG"], cv2.COLOR_BGR2GRAY)
    bl, br = float(gl.mean()), float(gr.mean())
    sl, sr = float(gl.std()), float(gr.std())
    p_or = max(bl, br) / max(min(bl, br), 1)
    k_or = max(sl, sr) / max(min(sl, sr), 1)
    if p_or < 1.15 and k_or < 1.25:
        ok(f"kameralar dengeli — parlaklik {p_or:.2f}x, kontrast {k_or:.2f}x")
    elif p_or < 1.35:
        uy(f"sinirda denge — parlaklik {p_or:.2f}x, kontrast {k_or:.2f}x")
    else:
        hata(f"kameralar DENGESIZ — parlaklik {p_or:.2f}x "
             f"(SOL {bl:.0f} / SAG {br:.0f})")

    for ad, g in (("SOL", gl), ("SAG", gr)):
        m = float(g.mean())
        if m < 70:
            hata(f"{ad} COK KARANLIK ({m:.0f}/255) — pozlamayi ac")
        elif m > 200:
            hata(f"{ad} COK PARLAK ({m:.0f}/255) — pozlamayi kis")
        else:
            ok(f"{ad} parlaklik {m:.0f}/255 uygun")
        yanik = (g > 250).sum() / g.size * 100
        if yanik > 5:
            uy(f"{ad} %{yanik:.1f} yanik beyaz — detay kaybi")

    # desen tespiti
    print("\n5) ChArUco desen tespiti (SU ANKI goruntude)")
    ad_dict = getattr(cv2.aruco, cfg["aruco_dict"])
    adict = cv2.aruco.getPredefinedDictionary(ad_dict)
    mk = cfg["marker_length_mm"] * sq / cfg["square_length_mm"] if sq else 0
    board = cv2.aruco.CharucoBoard((cfg["squares_x"], cfg["squares_y"]),
                                   sq / 1000.0, mk / 1000.0, adict)
    if not cfg["aruco_dict"].startswith("DICT_APRILTAG"):
        board.setLegacyPattern(True)
    par = cv2.aruco.DetectorParameters()
    par.adaptiveThreshWinSizeMax = 73
    par.adaptiveThreshWinSizeStep = 2
    det = cv2.aruco.CharucoDetector(board, cv2.aruco.CharucoParameters(), par)
    maks = (cfg["squares_x"] - 1) * (cfg["squares_y"] - 1)
    bulunan = {}
    for ad, g in (("SOL", gl), ("SAG", gr)):
        try:
            cc, ci, _, _ = det.detectBoard(g)
            n = 0 if cc is None else len(cc)
        except Exception as e:
            n = 0
        bulunan[ad] = n
        if n >= maks * 0.5:
            ok(f"{ad}: {n}/{maks} kose bulundu")
        elif n > 0:
            uy(f"{ad}: sadece {n}/{maks} kose — deseni daha iyi konumlandir")
        else:
            uy(f"{ad}: desen gorunmuyor (kalibrasyon sirasinda tutacaksin, "
               f"su an normal)")
    if bulunan["SOL"] > 0 and bulunan["SAG"] > 0:
        ortak = min(bulunan.values())
        ok(f"her iki kamerada da desen goruluyor (min {ortak} kose)")

    for c in caps.values():
        c.release()
    ozet()


def ozet():
    print()
    print("=" * 72)
    print("SONUC")
    print("=" * 72)
    print(f"  Gecen: {len(GECER)}   Uyari: {len(UYARI)}   Engel: {len(KAL)}")
    if KAL:
        print("\n  KALIBRASYONDAN ONCE COZULMESI GEREKENLER:")
        for m in KAL:
            print(f"    - {m}")
        print("\n  >>> HENUZ HAZIR DEGIL")
    else:
        if UYARI:
            print("\n  Uyarilar (engel degil):")
            for m in UYARI:
                print(f"    - {m}")
        print("\n  >>> KALIBRASYONA HAZIR")
        print("      Kalibrasyon tabi > modu AC > 25-40 cift topla > Kalibre Et")


if __name__ == "__main__":
    main()
