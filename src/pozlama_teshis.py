"""POZLAMA TESHISI - iki kamera pozlamaya ayni tepkiyi veriyor mu?

Neden gerekli: gamma esitlendikten sonra bile ~1.18x parlaklik farki kaldi.
Iki olasi neden var ve bunlari AYIRT etmek gerekiyor:

  A) Otomatik pozlama gercekte KAPANMAMIS olabilir.
     Kod CAP_PROP_AUTO_EXPOSURE'a 0.25 yaziyor; bu DSHOW/V4L2
     konvansiyonu, MSMF'de ayni anlama gelmeyebilir. Otomatik acik
     kalirsa her kamera KENDI gordugu sahneye gore pozlama secer -
     iki kamera farkli acidan baktigi icin farkli deger secerler.
     Imza: sabit bir carpan yok, fark sahneye gore oynar; ayrica
     ayni ayarda arka arkaya olcumler kayar.

  B) Otomatik kapali ama sensor/ISP tepkisi farkli.
     Imza: fark her pozlama kademesinde TUTARLI bir carpan olarak
     kalir ve olcumler tekrarlanabilir.

Uygulama kameralari acik tutar - CALISTIRMADAN ONCE UYGULAMAYI KAPAT.

Kullanim:  .\calistir.ps1 pozlama_teshis
"""
import argparse
import json
import os
import sys
import time

import numpy as np
import cv2

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
SETTINGS = os.path.join(PROJECT_DIR, "data", "camera_settings.json")


def ac(idx, w, h):
    cap = cv2.VideoCapture(idx, cv2.CAP_MSMF)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
    return cap


def ortak_ayarlar(cap, cfg):
    """camera_test.py _apply_all ile AYNI degerleri yaz (pozlama haric)."""
    cap.set(cv2.CAP_PROP_AUTO_WB, 0)
    cap.set(cv2.CAP_PROP_WB_TEMPERATURE, cfg.get("wb", 4500))
    cap.set(cv2.CAP_PROP_BRIGHTNESS, cfg.get("brightness", 0))
    cap.set(cv2.CAP_PROP_CONTRAST, cfg.get("contrast", 32))
    cap.set(cv2.CAP_PROP_SATURATION, cfg.get("saturation", 64))
    cap.set(cv2.CAP_PROP_SHARPNESS, cfg.get("sharpness", 3))
    cap.set(cv2.CAP_PROP_GAMMA, max(200, cfg.get("gamma", 300)))
    cap.set(cv2.CAP_PROP_HUE, 0)
    cap.set(cv2.CAP_PROP_BACKLIGHT, 0)
    cap.set(cv2.CAP_PROP_GAIN, cfg.get("gain", 0))


def parlaklik(cap, atla=6, orta=3):
    """Birkac kare at (ayarin oturmasi icin), sonra ortalama al."""
    for _ in range(atla):
        cap.read()
    d = []
    for _ in range(orta):
        ok, f = cap.read()
        if ok and f is not None:
            d.append(float(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).mean()))
        time.sleep(0.03)
    return float(np.mean(d)) if d else float("nan")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--left", type=int, default=None)
    p.add_argument("--right", type=int, default=None)
    a = p.parse_args()

    cfg = {}
    if os.path.exists(SETTINGS):
        with open(SETTINGS, encoding="utf-8") as f:
            cfg = json.load(f)
    li = a.left if a.left is not None else cfg.get("left_idx", 2)
    ri = a.right if a.right is not None else cfg.get("right_idx", 1)
    res = str(cfg.get("resolution", "2048x1536")).split()[0]
    w, h = (int(v) for v in res.split("x"))

    print(f"SOL=idx{li}  SAG=idx{ri}  {w}x{h}")
    print("UYGULAMA ACIKSA KAMERALAR ACILAMAZ - kapali oldugundan emin ol.\n")

    cl, cr = ac(li, w, h), ac(ri, w, h)
    if not (cl.isOpened() and cr.isOpened()):
        print("HATA: kamera acilamadi. Uygulama hala acik olabilir.")
        return 1
    ortak_ayarlar(cl, cfg)
    ortak_ayarlar(cr, cfg)

    # ---- TEST 1: otomatik pozlama hangi degerle kapaniyor? -------------
    print("=" * 70)
    print("TEST 1  Otomatik pozlama gercekten kapaniyor mu?")
    print("=" * 70)
    print("Yontem: ayni pozlamayi yaz, sahne sabitken arka arkaya olc.")
    print("Otomatik ACIKSA kamera kendi kendine ayar yapar -> degerler kayar.\n")
    print(f"  {'AUTO_EXPOSURE':>14} {'SOL kayma':>11} {'SAG kayma':>11}   yorum")
    print("-" * 70)
    en_iyi, en_iyi_kayma = None, 1e9
    for ae in (0.25, 0.0, 1.0, 3.0):
        for c in (cl, cr):
            c.set(cv2.CAP_PROP_AUTO_EXPOSURE, ae)
            c.set(cv2.CAP_PROP_EXPOSURE, -4)
        time.sleep(0.4)
        sol = [parlaklik(cl, atla=3, orta=2) for _ in range(3)]
        sag = [parlaklik(cr, atla=3, orta=2) for _ in range(3)]
        ks, kr = float(np.std(sol)), float(np.std(sag))
        yorum = "kapali gorunuyor" if max(ks, kr) < 2.0 else "OTOMATIK ACIK?"
        print(f"  {ae:14.2f} {ks:11.2f} {kr:11.2f}   {yorum}")
        if max(ks, kr) < en_iyi_kayma:
            en_iyi, en_iyi_kayma = ae, max(ks, kr)
    print(f"\n  -> en kararli AUTO_EXPOSURE degeri: {en_iyi}")

    # ---- TEST 2: pozlama tepki egrisi ---------------------------------
    print()
    print("=" * 70)
    print("TEST 2  Iki kamera pozlamaya AYNI tepkiyi mi veriyor?")
    print("=" * 70)
    for c in (cl, cr):
        c.set(cv2.CAP_PROP_AUTO_EXPOSURE, en_iyi)
    print(f"  {'poz':>5} {'SOL':>8} {'SAG':>8} {'oran':>8}   durum")
    print("-" * 70)
    oranlar = []
    for e in (-2, -3, -4, -5, -6):
        for c in (cl, cr):
            c.set(cv2.CAP_PROP_EXPOSURE, e)
        time.sleep(0.35)
        bl, br = parlaklik(cl), parlaklik(cr)
        oran = bl / max(br, 1e-6)
        durum = []
        if max(bl, br) > 235:
            durum.append("DOYMUS")
        elif min(bl, br) < 40:
            durum.append("cok karanlik")
        else:
            durum.append("kullanilabilir")
            oranlar.append(oran)
        print(f"  {e:5d} {bl:8.1f} {br:8.1f} {oran:8.2f}x  {' '.join(durum)}")

    print()
    print("=" * 70)
    print("SONUC")
    print("=" * 70)
    if len(oranlar) >= 2:
        o = np.array(oranlar)
        print(f"  Kullanilabilir bantta oran: ort {o.mean():.2f}x, "
              f"salinim {o.std():.3f}")
        if o.std() < 0.05:
            print("  -> Oran her kademede TUTARLI: otomatik pozlama sorunu")
            print("     DEGIL. Sabit bir sensor/ISP farki var; SAG kamera")
            print(f"     gain telafisi ile kapatilabilir (Ayarlar >")
            print("     'Otomatik esitle').")
        else:
            print("  -> Oran kademeden kademeye DEGISIYOR: pozlama tutarsiz")
            print("     uygulaniyor, otomatik pozlama hala devrede olabilir.")
        if en_iyi_kayma >= 2.0:
            print("  UYARI: hicbir AUTO_EXPOSURE degeri kaymayi durduramadi -")
            print("         MSMF yerine DSHOW ile kapatmak gerekebilir.")
    else:
        print("  Yeterli kullanilabilir olcum yok - isigi degistirip tekrarla.")

    cl.release()
    cr.release()
    return 0


if __name__ == "__main__":
    sys.exit(main())
