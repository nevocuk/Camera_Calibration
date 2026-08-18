"""Renk farki ve odak farkinin nedenini olc.

Kullanim (camera_test.py KAPALI olmali):
    .\\calistir.ps1 renk_odak_teshis

TEST 1 — RENK: kanal bazinda (B,G,R) ortalama. Fark varsa beyaz dengesi
         kilitlenmemis demektir. AUTO_WB=0 gercekten isliyor mu test edilir.

TEST 2 — ODAK HARITASI: kareyi 3x3 boluge bolup her bolgenin netligini
         olcer. Odak farkinin nedenini ayirt eder:
           - Tum bolgeler birlikte dusuk  -> lens odagi kaymis (cevirerek duzelir)
           - Bir kenar dusuk, karsi kenar yuksek -> SENSOR EGIK (cevirerek DUZELMEZ)
           - Merkez yuksek, kenarlar dusuk -> normal alan egrilligi
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
OUT = os.path.join(PROJECT_DIR, "output", "renk_odak")
os.makedirs(OUT, exist_ok=True)
W, H = 1280, 960


def kare(c, n=8):
    fs = []
    for _ in range(n):
        c.grab()
    for _ in range(n):
        c.grab()
        ok, f = c.retrieve()
        if ok:
            fs.append(f.astype(np.float32))
    return np.mean(fs, axis=0).astype(np.uint8) if fs else None


def netlik(g):
    m = float(g.mean())
    if m < 5:
        return 0.0
    return float(cv2.Laplacian(g, cv2.CV_64F).var() / (m * m) * 1000)


def main():
    s = json.load(open(SETTINGS, encoding="utf-8"))
    li, ri = s["left_idx"], s["right_idx"]

    caps = {}
    for ad, idx in (("SOL", li), ("SAG", ri)):
        c = cv2.VideoCapture(idx, cv2.CAP_MSMF)
        if not c.isOpened():
            print(f"HATA: {ad} (idx {idx}) acilamadi. camera_test.py acik mi?")
            for x in caps.values():
                x.release()
            sys.exit(1)
        c.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        c.set(cv2.CAP_PROP_FRAME_WIDTH, W)
        c.set(cv2.CAP_PROP_FRAME_HEIGHT, H)
        for p, v in ((cv2.CAP_PROP_AUTO_EXPOSURE, 0.25),
                     (cv2.CAP_PROP_AUTO_WB, 0),
                     (cv2.CAP_PROP_WB_TEMPERATURE, s.get("wb", 4500)),
                     (cv2.CAP_PROP_BRIGHTNESS, s.get("brightness", 0)),
                     (cv2.CAP_PROP_CONTRAST, s.get("contrast", 32)),
                     (cv2.CAP_PROP_SATURATION, s.get("saturation", 64)),
                     (cv2.CAP_PROP_SHARPNESS, s.get("sharpness", 3)),
                     (cv2.CAP_PROP_GAMMA, s.get("gamma", 100)),
                     (cv2.CAP_PROP_HUE, 0),
                     (cv2.CAP_PROP_BACKLIGHT, 0),
                     (cv2.CAP_PROP_GAIN, s.get("gain", 0)),
                     (cv2.CAP_PROP_EXPOSURE, s.get("exposure", -5))):
            c.set(p, v)
        caps[ad] = c
    time.sleep(1.5)
    for _ in range(10):
        for c in caps.values():
            c.grab()
    # akis basladiktan sonra tekrar
    for ad, c in caps.items():
        c.set(cv2.CAP_PROP_AUTO_WB, 0)
        c.set(cv2.CAP_PROP_WB_TEMPERATURE, s.get("wb", 4500))
        c.set(cv2.CAP_PROP_EXPOSURE, s.get("exposure", -5))
    time.sleep(1.0)

    fr = {ad: kare(c) for ad, c in caps.items()}
    if any(v is None for v in fr.values()):
        print("Kare alinamadi")
        return

    print("=" * 70)
    print("TEST 1 — RENK DENGESI (kanal ortalamalari)")
    print("=" * 70)
    print(f"{'':6} {'MAVI':>8} {'YESIL':>8} {'KIRMIZI':>9} "
          f"{'K/M':>7} {'Y/M':>7}   yorum")
    print("-" * 70)
    orn = {}
    for ad in ("SOL", "SAG"):
        b, g, r = [float(fr[ad][:, :, i].mean()) for i in range(3)]
        km, ym = r / max(b, 1), g / max(b, 1)
        orn[ad] = (b, g, r, km, ym)
        if km > 1.12:
            yorum = "sicak (kirmiziya kacik)"
        elif km < 0.9:
            yorum = "soguk (maviye kacik)"
        elif ym > 1.15:
            yorum = "yesile kacik"
        else:
            yorum = "notr"
        print(f"{ad:6} {b:8.1f} {g:8.1f} {r:9.1f} {km:7.2f} {ym:7.2f}   {yorum}")

    dk = abs(orn['SOL'][3] - orn['SAG'][3])
    dy = abs(orn['SOL'][4] - orn['SAG'][4])
    print(f"\n  Iki kamera arasi fark: K/M {dk:.3f}   Y/M {dy:.3f}")
    if dk < 0.06 and dy < 0.06:
        print("  -> Renk dengesi UYUMLU.")
    else:
        print("  -> RENK FARKI VAR. Beyaz dengesi kilitlenmemis olabilir.")
        print("     NOT: stereo derinlik gri tonlamada hesaplanir, renk farki")
        print("     DERINLIGI ETKILEMEZ. Sadece overlay gorunumunu etkiler.")

    # WB kilitli mi? Degeri degistirip goruntu degisiyor mu bak
    print()
    print("  AUTO_WB=0 gercekten kilitliyor mu? (WB degerini degistirip bak)")
    for ad, c in caps.items():
        oranlar = []
        for wb in (2800, 4500, 6500):
            c.set(cv2.CAP_PROP_AUTO_WB, 0)
            c.set(cv2.CAP_PROP_WB_TEMPERATURE, wb)
            time.sleep(0.5)
            f = kare(c, 4)
            b, g, r = [float(f[:, :, i].mean()) for i in range(3)]
            oranlar.append(r / max(b, 1))
        deg = max(oranlar) - min(oranlar)
        print(f"    {ad}: WB 2800/4500/6500 -> K/M "
              f"{oranlar[0]:.2f}/{oranlar[1]:.2f}/{oranlar[2]:.2f}  "
              f"{'WB CALISIYOR' if deg > 0.08 else 'WB ETKISIZ (kilitli/desteklenmiyor)'}")
        c.set(cv2.CAP_PROP_WB_TEMPERATURE, s.get("wb", 4500))
    time.sleep(0.6)

    print()
    print("=" * 70)
    print("TEST 2 — ODAK HARITASI (3x3 bolge netligi)")
    print("=" * 70)
    print("Hedef DUZ ve kareyi dolduruyor olmali, yoksa sonuc yaniltir!\n")
    fr = {ad: kare(c) for ad, c in caps.items()}
    harita = {}
    for ad in ("SOL", "SAG"):
        g = cv2.cvtColor(fr[ad], cv2.COLOR_BGR2GRAY)
        h, w = g.shape
        m = np.zeros((3, 3))
        for i in range(3):
            for j in range(3):
                blok = g[i*h//3:(i+1)*h//3, j*w//3:(j+1)*w//3]
                m[i, j] = netlik(blok)
        harita[ad] = m
        print(f"  {ad}:")
        for i in range(3):
            print("    " + "  ".join(f"{m[i, j]:7.1f}" for j in range(3)))
        merkez = m[1, 1]
        ust, alt = m[0].mean(), m[2].mean()
        sol, sag = m[:, 0].mean(), m[:, 2].mean()
        print(f"    merkez={merkez:.1f}  ust={ust:.1f} alt={alt:.1f}  "
              f"sol={sol:.1f} sag={sag:.1f}")
        eg_dikey = abs(ust - alt) / max(ust, alt, 1) * 100
        eg_yatay = abs(sol - sag) / max(sol, sag, 1) * 100
        print(f"    dikey dengesizlik %{eg_dikey:.0f}   "
              f"yatay dengesizlik %{eg_yatay:.0f}")
        if eg_dikey > 40 or eg_yatay > 40:
            print("    >>> SENSOR/LENS EGIK olabilir — lensi cevirmek DUZELTMEZ")
        print()

    a, b = harita["SOL"][1, 1], harita["SAG"][1, 1]
    print(f"  Merkez netlik: SOL {a:.1f}   SAG {b:.1f}   "
          f"oran {max(a,b)/max(min(a,b),1):.2f}x")

    for ad in ("SOL", "SAG"):
        cv2.imwrite(os.path.join(OUT, f"{ad}.png"), fr[ad])
    print(f"\n  Goruntuler: {OUT}")

    for c in caps.values():
        c.release()


if __name__ == "__main__":
    main()
