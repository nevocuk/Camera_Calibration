"""Iki kamerayi yazilimla parlaklik olarak esitle ve ayarlari kaydet.

Kullanim (camera_test.py KAPALI olmali):
    .\\calistir.ps1 parlaklik_esitle

Donanimsal isik gecirgenligi farki (lens/diyafram/film) fiziksel olarak
duzeltilemiyorsa, SAG kameraya pozlama + gain telafisi uygulanarak
esitlenebilir. Bu arac telafileri OLCEREK bulur ve
data/camera_settings.json dosyasina yazar.

Sira:
  1) SOL kamerayi hedef parlakliga getiren ORTAK pozlamayi bul
  2) SAG'i SOL'a yaklastiran POZLAMA TELAFISI (kaba, 2x adimlar)
  3) Kalani kapatan GAIN TELAFISI (ince)
  4) Dogrula ve kaydet
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
HEDEF = 125.0
W, H = 1280, 960


def olc(cap, n=5):
    gs = []
    for _ in range(n):
        cap.grab()
    for _ in range(n):
        cap.grab()
        ok, f = cap.retrieve()
        if ok:
            gs.append(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY))
    if not gs:
        return None
    g = np.mean(gs, axis=0)
    return dict(ort=float(g.mean()), std=float(g.std()),
                p50=float(np.percentile(g, 50)))


def main():
    s = json.load(open(SETTINGS, encoding="utf-8"))
    li, ri = s["left_idx"], s["right_idx"]
    print("=" * 66)
    print("PARLAKLIK ESITLEME")
    print("=" * 66)
    print(f"SOL = idx {li}   SAG = idx {ri}")
    print("Sahneyi SABIT tut, kameralarin onune gecme.\n")

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
        c.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
        c.set(cv2.CAP_PROP_AUTO_WB, 0)
        c.set(cv2.CAP_PROP_GAIN, 0)
        c.set(cv2.CAP_PROP_BRIGHTNESS, 0)
        caps[ad] = c
    time.sleep(1.5)
    for _ in range(12):
        for c in caps.values():
            c.grab()

    # --- 1) Ortak pozlama: SOL hedefe yakin olsun ---
    print("1) ORTAK POZLAMA araniyor (SOL kamera hedef ~%.0f)" % HEDEF)
    en_iyi, en_fark = None, 1e9
    for p in range(-9, -1):
        for c in caps.values():
            c.set(cv2.CAP_PROP_EXPOSURE, p)
        time.sleep(0.45)
        m = olc(caps["SOL"], 3)
        if m is None:
            continue
        print(f"   poz={p:3d} -> SOL {m['ort']:6.1f}")
        if 35 < m["ort"] < 235 and abs(m["ort"] - HEDEF) < en_fark:
            en_fark, en_iyi = abs(m["ort"] - HEDEF), p
    if en_iyi is None:
        print("\nHATA: uygun pozlama yok. Isik cok az veya cok fazla.")
        for c in caps.values():
            c.release()
        sys.exit(1)
    poz = en_iyi
    for c in caps.values():
        c.set(cv2.CAP_PROP_EXPOSURE, poz)
    time.sleep(0.6)
    L = olc(caps["SOL"])
    R0 = olc(caps["SAG"])
    print(f"   -> POZLAMA = {poz}   SOL={L['ort']:.1f}  SAG={R0['ort']:.1f}"
          f"  (oran {L['ort']/max(R0['ort'],1):.2f}x)\n")

    # --- 2) Pozlama telafisi (kaba) ---
    print("2) POZLAMA TELAFISI (SAG icin, 1 kademe = 2x)")
    en_pt, en_pt_fark = 0, abs(R0["ort"] - L["ort"])
    for pt in range(-3, 4):
        hedef_poz = max(-13, min(0, poz + pt))
        caps["SAG"].set(cv2.CAP_PROP_EXPOSURE, hedef_poz)
        time.sleep(0.45)
        m = olc(caps["SAG"], 3)
        if m is None:
            continue
        f = abs(m["ort"] - L["ort"])
        isaret = " <<<" if f < en_pt_fark else ""
        print(f"   telafi={pt:+d} (poz={hedef_poz:3d}) -> SAG {m['ort']:6.1f}"
              f"  fark {f:6.1f}{isaret}")
        if f < en_pt_fark:
            en_pt_fark, en_pt = f, pt
    caps["SAG"].set(cv2.CAP_PROP_EXPOSURE, max(-13, min(0, poz + en_pt)))
    time.sleep(0.5)
    print(f"   -> POZLAMA TELAFI = {en_pt:+d}\n")

    # --- 3) Gain telafisi (ince) ---
    print("3) GAIN TELAFISI (ince ayar)")
    en_g, en_g_fark = 0, 1e9
    for g in range(0, 61, 5):
        caps["SAG"].set(cv2.CAP_PROP_GAIN, g)
        time.sleep(0.4)
        m = olc(caps["SAG"], 3)
        if m is None:
            continue
        f = abs(m["ort"] - L["ort"])
        isaret = " <<<" if f < en_g_fark else ""
        print(f"   gain=+{g:2d} -> SAG {m['ort']:6.1f}  fark {f:6.1f}{isaret}")
        if f < en_g_fark:
            en_g_fark, en_g = f, g
    caps["SAG"].set(cv2.CAP_PROP_GAIN, en_g)
    time.sleep(0.5)
    print(f"   -> GAIN TELAFI = +{en_g}\n")

    # --- 4) Dogrula ---
    L2 = olc(caps["SOL"])
    R2 = olc(caps["SAG"])
    print("=" * 66)
    print("SONUC")
    print("=" * 66)
    print(f"{'':8} {'ONCE':>10} {'SONRA':>10}")
    print(f"{'SOL':8} {L['ort']:10.1f} {L2['ort']:10.1f}")
    print(f"{'SAG':8} {R0['ort']:10.1f} {R2['ort']:10.1f}")
    onceki = max(L['ort'], R0['ort']) / max(min(L['ort'], R0['ort']), 1)
    simdiki = max(L2['ort'], R2['ort']) / max(min(L2['ort'], R2['ort']), 1)
    print(f"\nParlaklik orani: {onceki:.2f}x  ->  {simdiki:.2f}x")
    print(f"Kontrast (std) : SOL {L2['std']:.1f}   SAG {R2['std']:.1f}")

    for c in caps.values():
        c.release()

    if simdiki > 1.35:
        print("\nUYARI: %35'in altina inemedi. Kalan farki ton eslemesi")
        print("       ('Histogram') kapatacak, ama fiziksel neden arastirilmali.")

    print(f"\nAyarlar kaydedilsin mi? data/camera_settings.json")
    print(f"   pozlama={poz}  exp_offset_r={en_pt:+d}  gain_offset_r={en_g}")
    cev = input("   [E/h] > ").strip().lower()
    if cev in ("", "e", "evet", "y", "yes"):
        s["exposure"] = poz
        s["exp_offset_r"] = en_pt
        s["gain_offset_r"] = float(en_g)
        s["gain"] = 0
        with open(SETTINGS, "w", encoding="utf-8") as f:
            json.dump(s, f, indent=2, ensure_ascii=False)
        print("   Kaydedildi.")
    else:
        print("   Kaydedilmedi.")


if __name__ == "__main__":
    main()
