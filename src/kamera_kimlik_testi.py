"""1) Hangi kamera fiziksel olarak SOL, hangisi SAG?  2) Default ayarda ne kadar farklilar?

Kullanim (camera_test.py KAPALI olmali):
    .\\calistir.ps1 kamera_kimlik_testi

TEST 1 — SOL/SAG dogrulamasi:
    Kalibrasyon belli bir SOL/SAG atamasi ile yapildi. Atama tersse
    disparity negatif olur ve SGBM hicbir sey eslestiremez.
    Iki olasiligi da hesaplayip hangisinin gecerli oldugunu buluyoruz.

TEST 2 — Default (fabrika) ayarda karsilastirma:
    Hicbir property yazmadan acip olcuyoruz. Ayni model kameralar burada
    yakin olmali; buyuk fark varsa donanimsal (lens/odak/kir/sensor).
"""
import json
import os
import sys
import time
import numpy as np
import cv2

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
CALIB = os.path.join(PROJECT_DIR, "calibration", "calib_result.npz")
SETTINGS = os.path.join(PROJECT_DIR, "data", "camera_settings.json")
OUT = os.path.join(PROJECT_DIR, "output", "kimlik_testi")
os.makedirs(OUT, exist_ok=True)


def kare_al(cap, n=8):
    gs = []
    for _ in range(n):
        cap.grab()
    for _ in range(n):
        cap.grab()
        ok, f = cap.retrieve()
        if ok:
            gs.append(f.astype(np.float32))
    return np.mean(gs, axis=0).astype(np.uint8) if gs else None


def main():
    s = json.load(open(SETTINGS, encoding="utf-8"))
    idx_a, idx_b = s["left_idx"], s["right_idx"]
    calib = np.load(CALIB)
    sz = tuple(calib["image_size"])
    f_px = float(calib["P1"][0, 0])
    B_m = float(np.linalg.norm(calib["T"]))
    T = calib["T"].ravel()

    print("=" * 72)
    print("KAMERA KIMLIK TESTI")
    print("=" * 72)
    print(f"Ayar dosyasi diyor ki: SOL=idx {idx_a}   SAG=idx {idx_b}")
    print(f"Kalibrasyon T vektoru : [{T[0]:+.5f}, {T[1]:+.5f}, {T[2]:+.5f}] m")
    print(f"  Tx isareti {'NEGATIF' if T[0] < 0 else 'POZITIF'} -> OpenCV konvansiyonunda "
          f"{'kamera2 SAGDA (standart)' if T[0] < 0 else 'kamera2 SOLDA (ters!)'}")
    print()

    # --- Kareleri al (DEFAULT ayar, hicbir property yazmadan) ---
    print("TEST 2: DEFAULT (fabrika) ayarda karsilastirma")
    print("-" * 72)
    frames = {}
    for ad, idx in (("idx" + str(idx_a), idx_a), ("idx" + str(idx_b), idx_b)):
        c = cv2.VideoCapture(idx, cv2.CAP_MSMF)
        if not c.isOpened():
            print(f"  {ad} acilamadi!")
            return
        c.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        c.set(cv2.CAP_PROP_FRAME_WIDTH, sz[0])
        c.set(cv2.CAP_PROP_FRAME_HEIGHT, sz[1])
        time.sleep(1.5)
        frames[ad] = kare_al(c)
        c.release()
        time.sleep(0.5)

    adlar = list(frames.keys())
    print(f"{'olcum':<14} {adlar[0]:>10} {adlar[1]:>10} {'fark':>10}")
    for ad, fn in (("parlaklik", lambda g: g.mean()),
                   ("std", lambda g: g.std()),
                   ("p5", lambda g: np.percentile(g, 5)),
                   ("p50", lambda g: np.percentile(g, 50)),
                   ("p95", lambda g: np.percentile(g, 95)),
                   ("netlik", lambda g: cv2.Laplacian(
                       cv2.cvtColor(g, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())):
        a = float(fn(frames[adlar[0]]))
        b = float(fn(frames[adlar[1]]))
        print(f"{ad:<14} {a:10.1f} {b:10.1f} {b-a:+10.1f}")
    pa = frames[adlar[0]].mean()
    pb = frames[adlar[1]].mean()
    oran = max(pa, pb) / max(min(pa, pb), 1)
    print(f"\n  Parlaklik orani: {oran:.2f}x  "
          f"{'-> NORMAL DEGIL, donanim kontrolu gerek' if oran > 1.5 else '-> kabul edilebilir'}")
    for ad in adlar:
        cv2.imwrite(os.path.join(OUT, f"default_{ad}.png"), frames[ad])

    # --- TEST 1: SOL/SAG dogrulamasi ---
    print()
    print("TEST 1: SOL/SAG atamasi dogru mu?")
    print("-" * 72)
    m1x, m1y = cv2.initUndistortRectifyMap(calib["K1"], calib["D1"], calib["R1"],
                                           calib["P1"], sz, cv2.CV_32FC1)
    m2x, m2y = cv2.initUndistortRectifyMap(calib["K2"], calib["D2"], calib["R2"],
                                           calib["P2"], sz, cv2.CV_32FC1)
    st = cv2.StereoSGBM_create(
        minDisparity=0, numDisparities=256, blockSize=7,
        P1=8*3*49, P2=32*3*49, disp12MaxDiff=1, uniquenessRatio=15,
        speckleWindowSize=200, speckleRange=2, preFilterCap=63,
        mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY)

    A, B = frames[adlar[0]], frames[adlar[1]]
    sonuc = {}
    for etiket, (sol, sag) in (
            (f"SOL={adlar[0]}, SAG={adlar[1]}  (ayar dosyasindaki)", (A, B)),
            (f"SOL={adlar[1]}, SAG={adlar[0]}  (TERS)", (B, A))):
        rl = cv2.remap(sol, m1x, m1y, cv2.INTER_LINEAR)
        rr = cv2.remap(sag, m2x, m2y, cv2.INTER_LINEAR)
        gl = cv2.cvtColor(rl, cv2.COLOR_BGR2GRAY)
        gr = cv2.cvtColor(rr, cv2.COLOR_BGR2GRAY)
        # ton farkini notrle (kimlik testi parlakliktan etkilenmesin)
        hl = np.bincount(gl.ravel(), minlength=256).astype(float)
        hr = np.bincount(gr.ravel(), minlength=256).astype(float)
        lut = np.interp(np.cumsum(hr)/hr.sum(), np.cumsum(hl)/hl.sum(),
                        np.arange(256)).astype(np.uint8)
        gr = lut[gr]
        d = st.compute(gl, gr).astype(np.float32) / 16.0
        d[d <= 0] = 0
        core = d[:, 300:]
        kaps = (core > 0).sum() / core.size * 100
        med = float(np.median(core[core > 0])) if (core > 0).any() else 0
        sonuc[etiket] = (kaps, med)
        print(f"  {etiket}")
        print(f"     gecerli disparity orani: %{kaps:5.1f}   medyan disparity: {med:6.1f} px"
              f"   -> {f_px*B_m/med*1000:.0f} mm" if med > 0 else "")

    en_iyi = max(sonuc, key=lambda k: sonuc[k][0])
    print()
    if "TERS" in en_iyi:
        print("  >>> SONUC: ATAMA TERS! Ayarlar tabinda 'SOL/SAG Degistir' + Kaydet.")
    else:
        print("  >>> SONUC: Atama DOGRU (ayar dosyasindaki gibi).")
    fark = abs(sonuc[list(sonuc)[0]][0] - sonuc[list(sonuc)[1]][0])
    if fark < 10:
        print("      NOT: iki secenek birbirine yakin — sahne dokusuz olabilir,")
        print("      dokulu bir sahnede tekrarla.")
    print(f"\n  Goruntuler: {OUT}")


if __name__ == "__main__":
    main()
