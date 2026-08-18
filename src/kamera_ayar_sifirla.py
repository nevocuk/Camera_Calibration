"""Iki kameranin saklanmis ayarlarini AYNI degerlere getir.

Kullanim (camera_test.py KAPALI olmali):
    .\\calistir.ps1 kamera_ayar_sifirla              # ayarlari esitle
    .\\calistir.ps1 kamera_ayar_sifirla -- --dialog  # surucu penceresini ac

NEDEN GEREKLI:
  Olculdu — bu kameralar ayarlari HAFIZASINDA saklıyor ve ikisinin
  saklanmis degerleri farkliydi:
      EXPOSURE  -6 / -3   (3 kademe = 8x parlaklik farki)
      GAMMA    200 / 100  (ton egrisi farki)
      SHARPNESS 50 / 5    (50, kameranin bildirdigi 0-10 araliginin disinda)
  Bu fark stereo eslemeyi bozar.

BACKEND NOTU:
  Yazma/okuma DSHOW ile yapilir — MSMF'de geri okuma bozuk (ne yazarsan
  yaz sabit deger doner). Ayarlar kamerada saklandigi icin DSHOW ile bir
  kez yazmak yeterli; camera_test.py MSMF ile acsa da bu degerleri devralir.
"""
import argparse
import json
import os
import sys
import time
import cv2

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
SETTINGS = os.path.join(PROJECT_DIR, "data", "camera_settings.json")

# Iki kameraya da yazilacak ORTAK degerler.
# Amac "fabrika degeri" degil, IKISININ AYNI olmasi.
ORTAK = [
    ("BRIGHTNESS",  cv2.CAP_PROP_BRIGHTNESS,   0),
    ("CONTRAST",    cv2.CAP_PROP_CONTRAST,    32),
    ("SATURATION",  cv2.CAP_PROP_SATURATION,  64),
    ("SHARPNESS",   cv2.CAP_PROP_SHARPNESS,    3),
    # GAMMA=100 (2026-08-18 duzeltildi). Onceki 300 secimi yanlis
    # teshise dayaniyordu: "100'de fark 2.76x" olcumu, gamma'nin
    # yalnizca BIR kameraya ulastigi donemde alinmisti (uygulamanin
    # _apply_all'i o zaman gamma yazmiyordu). Ikisine de yazilinca:
    #     300 -> 1.18x (188/159)   |   100 -> 1.04x (127/133)
    # 100 ayrica hedef parlaklik bandinin (90-150) ortasinda.
    # Onemli olan deger degil, IKI KAMERADA AYNI olmasi.
    ("GAMMA",       cv2.CAP_PROP_GAMMA,      100),
    ("HUE",         cv2.CAP_PROP_HUE,          0),
    ("BACKLIGHT",   cv2.CAP_PROP_BACKLIGHT,    0),
    ("GAIN",        cv2.CAP_PROP_GAIN,         0),
]
KONTROL = ORTAK + [("EXPOSURE", cv2.CAP_PROP_EXPOSURE, None)]


def ac(idx):
    c = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
    if not c.isOpened():
        return None
    time.sleep(0.8)
    for _ in range(5):
        c.grab()
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dialog", action="store_true",
                    help="Surucunun kendi ayar penceresini ac (Default butonu icin)")
    ap.add_argument("--exposure", type=int, default=None,
                    help="Iki kameraya da yazilacak pozlama (orn. -5)")
    args = ap.parse_args()

    s = json.load(open(SETTINGS, encoding="utf-8"))
    li, ri = s["left_idx"], s["right_idx"]
    poz = args.exposure if args.exposure is not None else s.get("exposure", -5)

    print("=" * 70)
    print("KAMERA AYAR ESITLEME")
    print("=" * 70)
    print(f"SOL = idx {li}   SAG = idx {ri}   yazilacak pozlama = {poz}\n")

    if args.dialog:
        print("Surucu ayar pencereleri aciliyor.")
        print("Her pencerede 'Default' / 'Varsayilan' butonuna basip OK de.\n")
        for ad, idx in (("SOL", li), ("SAG", ri)):
            c = ac(idx)
            if c is None:
                print(f"  {ad} acilamadi")
                continue
            print(f"  {ad} (idx {idx}) penceresi aciliyor — kapatinca devam eder...")
            c.set(cv2.CAP_PROP_SETTINGS, 1)
            time.sleep(0.5)
            c.release()
            time.sleep(0.8)
        print("\nPencereler kapandi. Simdi --dialog olmadan tekrar calistir.")
        return

    for ad, idx in (("SOL", li), ("SAG", ri)):
        c = ac(idx)
        if c is None:
            print(f"HATA: {ad} (idx {idx}) acilamadi. camera_test.py acik mi?")
            sys.exit(1)
        print(f"--- {ad} (idx {idx}) ---")
        c.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
        c.set(cv2.CAP_PROP_AUTO_WB, 0)
        for pad, prop, val in ORTAK:
            onceki = c.get(prop)
            c.set(prop, val)
            time.sleep(0.15)
            sonra = c.get(prop)
            ok = "OK" if abs(sonra - val) < 1e-6 else "KABUL EDILMEDI"
            degisti = "" if abs(onceki - sonra) < 1e-6 else f"  ({onceki:.0f} -> {sonra:.0f})"
            print(f"  {pad:<12} = {val:6.0f}   {ok}{degisti}")
        c.set(cv2.CAP_PROP_EXPOSURE, poz)
        time.sleep(0.2)
        e = c.get(cv2.CAP_PROP_EXPOSURE)
        print(f"  {'EXPOSURE':<12} = {poz:6.0f}   "
              f"{'OK' if abs(e-poz) < 1e-6 else 'KABUL EDILMEDI'}  (okunan {e:.0f})")
        c.release()
        time.sleep(0.8)
        print()

    # --- Dogrulama: ikisi de ayni mi + goruntu parlakligi ---
    print("=" * 70)
    print("DOGRULAMA")
    print("=" * 70)
    sonuc = {}
    for ad, idx in (("SOL", li), ("SAG", ri)):
        c = ac(idx)
        if c is None:
            continue
        d = {p[0]: c.get(p[1]) for p in KONTROL}
        import numpy as np
        gs = []
        for _ in range(6):
            c.grab()
            ok, f = c.retrieve()
            if ok:
                gs.append(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY))
        d["_parlaklik"] = float(np.mean(gs).mean()) if gs else float("nan")
        sonuc[ad] = d
        c.release()
        time.sleep(0.6)

    if len(sonuc) == 2:
        print(f"{'OZELLIK':<14} {'SOL':>10} {'SAG':>10} {'ayni mi':>9}")
        print("-" * 48)
        farkli = []
        for pad, _, _ in KONTROL:
            a, b = sonuc["SOL"][pad], sonuc["SAG"][pad]
            ayni = abs(a - b) < 1e-6
            if not ayni:
                farkli.append(pad)
            print(f"{pad:<14} {a:10.0f} {b:10.0f} {'EVET' if ayni else 'HAYIR':>9}")
        pa, pb = sonuc["SOL"]["_parlaklik"], sonuc["SAG"]["_parlaklik"]
        oran = max(pa, pb) / max(min(pa, pb), 1)
        print(f"\n{'GORUNTU parlaklik':<14} {pa:10.1f} {pb:10.1f}   oran {oran:.2f}x")
        print()
        if farkli:
            print(f"  Hala farkli: {', '.join(farkli)}")
            print("  -> Bu ozellikler surucu tarafindan kilitli olabilir.")
            print("     '--dialog' ile surucu penceresinden 'Default' dene.")
        else:
            print("  Tum ayarlar ESIT.")
        if oran < 1.25:
            print(f"  Goruntu parlakligi da dengeli ({oran:.2f}x). SORUN COZULDU.")
            print("  Kalan kucuk farki ton eslemesi ('Histogram') kapatir.")
        else:
            print(f"  Ayarlar esit ama goruntu hala {oran:.2f}x farkli.")
            print("  SIRAYLA kontrol et:")
            print("   1) Yukarida 'KABUL EDILMEDI' yazan ozellik var mi?")
            print("      Varsa once o cozulmeli — ayarlar gercekte esit degil.")
            print("   2) '--dialog' ile surucu penceresinden 'Default' dene.")
            print("   3) Ikisi de temizse O ZAMAN donanim (lens/film/kir)")
            print("      fiziksel kontrolu anlamli olur.")


if __name__ == "__main__":
    main()
