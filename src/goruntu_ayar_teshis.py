"""KESKINLIK / KONTRAST derinlik kalitesini nasil etkiliyor?

Amac: "keskinlik 3 mu 5 mi" gibi sorulari tahminle degil OLCUMLE
cevaplamak. Her ayar degerinde gercek bir stereo cift alinir ve SGBM'in
WLS ONCESI (yani gercek) eslesme orani ile doku seviyesi olculur.

Neden WLS ONCESI: WLS bosluklari TAHMINLE doldurur, bu yuzden filtre
sonrasi "%99 dolu" degeri her ayarda iyi gorunur ve hicbir sey ayirt
etmez. Gercegi ham eslesme orani soyler.

Keskinlik hipotezi: yapay kenar keskinlestirme kenarlarda halo uretir,
bu halolar iki kamerada ayni olmadigi icin SGBM sahte eslesme yapar.
Ayni mekanizma CLAHE icin olculmustu (sicrama 0.361 -> 0.419).

UYGULAMAYI KAPAT - kameralari o tutuyor.
Kullanim:  .\calistir.ps1 goruntu_ayar_teshis
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
CALIB = os.path.join(PROJECT_DIR, "calibration", "calib_result.npz")


def kur():
    cfg = {}
    if os.path.exists(SETTINGS):
        with open(SETTINGS, encoding="utf-8") as f:
            cfg = json.load(f)
    c = np.load(CALIB)
    size = tuple(int(v) for v in c["image_size"])
    m1 = cv2.initUndistortRectifyMap(c["K1"], c["D1"], c["R1"], c["P1"],
                                     size, cv2.CV_32FC1)
    m2 = cv2.initUndistortRectifyMap(c["K2"], c["D2"], c["R2"], c["P2"],
                                     size, cv2.CV_32FC1)
    return cfg, size, m1, m2


def ac(idx, size, cfg):
    cap = cv2.VideoCapture(idx, cv2.CAP_MSMF)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, size[0])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, size[1])
    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
    cap.set(cv2.CAP_PROP_AUTO_WB, 0)
    cap.set(cv2.CAP_PROP_WB_TEMPERATURE, cfg.get("wb", 4500))
    cap.set(cv2.CAP_PROP_EXPOSURE, cfg.get("exposure", -4))
    cap.set(cv2.CAP_PROP_GAIN, cfg.get("gain", 0))
    cap.set(cv2.CAP_PROP_BRIGHTNESS, cfg.get("brightness", 0))
    cap.set(cv2.CAP_PROP_SATURATION, cfg.get("saturation", 64))
    cap.set(cv2.CAP_PROP_GAMMA, cfg.get("gamma", 100))
    cap.set(cv2.CAP_PROP_HUE, 0)
    cap.set(cv2.CAP_PROP_BACKLIGHT, 0)
    return cap


def cift(cl, cr, m1, m2, n=4):
    """n kare ortala (gurultuyu azalt), rektifiye gri cift dondur."""
    al = ar = None
    alindi = 0
    for _ in range(n * 4):
        cl.grab(); cr.grab()
        ok1, a = cl.retrieve()
        ok2, b = cr.retrieve()
        if not (ok1 and ok2):
            continue
        g1 = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY).astype(np.float32)
        g2 = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY).astype(np.float32)
        al = g1 if al is None else al + g1
        ar = g2 if ar is None else ar + g2
        alindi += 1
        if alindi >= n:
            break
        time.sleep(0.03)
    if alindi == 0:
        return None, None
    gl = cv2.remap(np.round(al/alindi).astype(np.uint8), m1[0], m1[1],
                   cv2.INTER_LINEAR)
    gr = cv2.remap(np.round(ar/alindi).astype(np.uint8), m2[0], m2[1],
                   cv2.INTER_LINEAR)
    return gl, gr


ND = 256


def olc(gl, gr):
    """WLS ONCESI gercek eslesme orani + doku + harita puruzsuzlugu."""
    st = cv2.StereoSGBM_create(
        minDisparity=0, numDisparities=ND, blockSize=7,
        P1=8*3*49, P2=32*3*49, disp12MaxDiff=1, uniquenessRatio=15,
        speckleWindowSize=200, speckleRange=2, preFilterCap=63,
        mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY)
    d = st.compute(gl, gr).astype(np.float32) / 16.0
    kul = d[:, ND:]
    ham = float((kul > 0).mean() * 100)
    # doku: yerel standart sapma ortalamasi
    doku = float(cv2.Laplacian(gl, cv2.CV_32F).std())
    # sicrama: komsu pikseller arasi disparity farki (dusuk = duzgun)
    g = kul.copy()
    g[g <= 0] = np.nan
    dx = np.abs(np.diff(g, axis=1))
    sic = float(np.nanmean(dx)) if np.isfinite(dx).any() else float("nan")
    return ham, doku, sic


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--left", type=int, default=None)
    p.add_argument("--right", type=int, default=None)
    p.add_argument("--ozellik", choices=["keskinlik", "kontrast"],
                   default="keskinlik")
    p.add_argument("--tekrar", type=int, default=0,
                   help="Ayari DEGISTIRMEDEN N olcum al - olcumun kendi "
                        "salinimini gorup farklarin anlamli olup "
                        "olmadigina karar vermek icin")
    a = p.parse_args()

    cfg, size, m1, m2 = kur()
    li = a.left if a.left is not None else cfg.get("left_idx", 2)
    ri = a.right if a.right is not None else cfg.get("right_idx", 1)

    if a.ozellik == "keskinlik":
        prop, degerler, ref = cv2.CAP_PROP_SHARPNESS, [0, 2, 3, 5, 7, 10], 3
        sabit = [(cv2.CAP_PROP_CONTRAST, cfg.get("contrast", 32))]
    else:
        prop, degerler, ref = cv2.CAP_PROP_CONTRAST, [16, 24, 32, 40, 48], 32
        sabit = [(cv2.CAP_PROP_SHARPNESS, cfg.get("sharpness", 3))]

    print(f"SOL=idx{li} SAG=idx{ri}  {size[0]}x{size[1]}  "
          f"poz={cfg.get('exposure')}  gamma={cfg.get('gamma')}")
    print(f"Taranan: {a.ozellik.upper()}   (referans {ref})")
    print("Sahneyi SABIT ve DOKULU tut - olcumler ancak ayni sahnede "
          "karsilastirilabilir.\n")

    cl, cr = ac(li, size, cfg), ac(ri, size, cfg)
    if not (cl.isOpened() and cr.isOpened()):
        print("HATA: kamera acilamadi - uygulama acik olabilir.")
        return 1
    for c in (cl, cr):
        for pr, v in sabit:
            c.set(pr, v)

    if a.tekrar:
        # AYNI ayarda tekrarli olcum: farklarin gurultuden buyuk olup
        # olmadigini ancak bu belirler. Salinim, ayarlar arasi farktan
        # buyukse o farklar anlamsizdir.
        ref_v = ref
        for c in (cl, cr):
            c.set(prop, ref_v)
        time.sleep(0.5)
        print(f"  {a.ozellik}={ref_v} SABIT, {a.tekrar} tekrar olcum:")
        print()
        print(f"  {'#':>3} {'ham eslesme':>13} {'doku':>8} {'sicrama':>9}")
        print("-" * 40)
        kk = []
        for i in range(a.tekrar):
            gl, gr = cift(cl, cr, m1, m2)
            if gl is None:
                continue
            ham, doku, sic = olc(gl, gr)
            kk.append((ham, doku, sic))
            print(f"  {i+1:3d} {ham:12.1f}% {doku:8.1f} {sic:9.3f}")
        cl.release(); cr.release()
        if len(kk) >= 3:
            K = np.array(kk)
            print()
            print("=" * 56)
            print("OLCUMUN KENDI SALINIMI (ayar hic degismedi)")
            print("=" * 56)
            print(f"  ham eslesme : ort %{K[:,0].mean():.1f}  "
                  f"salinim +-{K[:,0].std():.2f}  "
                  f"aralik %{K[:,0].min():.1f}-%{K[:,0].max():.1f}")
            print(f"  sicrama     : ort {K[:,2].mean():.3f}  "
                  f"salinim +-{K[:,2].std():.3f}")
            print()
            yayilim = K[:, 0].max() - K[:, 0].min()
            print(f"  -> Ayni ayarda ham oran %{yayilim:.1f} yayiliyor.")
            print(f"     Ayarlar arasi farklar bundan KUCUKSE anlamsizdir;")
            print(f"     o ayarin derinlige olcülebilir etkisi yok demektir.")
        return 0

    print(f"  {'deger':>6} {'ham eslesme':>13} {'doku':>8} {'sicrama':>9}  not")
    print("-" * 60)
    kayit = []
    for v in degerler:
        for c in (cl, cr):
            c.set(prop, v)
        time.sleep(0.5)
        gl, gr = cift(cl, cr, m1, m2)
        if gl is None:
            print(f"  {v:6d}   kare alinamadi")
            continue
        ham, doku, sic = olc(gl, gr)
        kayit.append((v, ham, doku, sic))
        print(f"  {v:6d} {ham:12.1f}% {doku:8.1f} {sic:9.3f}"
              f"  {'<- referans' if v == ref else ''}")

    cl.release(); cr.release()

    if len(kayit) >= 3:
        A = np.array(kayit)
        print()
        print("=" * 60)
        print("SONUC")
        print("=" * 60)
        en_ham = A[np.argmax(A[:, 1])]
        en_duz = A[np.nanargmin(A[:, 3])]
        print(f"  En yuksek ham eslesme : {a.ozellik}={en_ham[0]:.0f}"
              f"  (%{en_ham[1]:.1f})")
        print(f"  En duzgun harita      : {a.ozellik}={en_duz[0]:.0f}"
              f"  (sicrama {en_duz[3]:.3f})")
        print()
        print("  Ikisi ayni degerde bulusuyorsa secim nettir. Ayrilirlarsa")
        print("  DUZGUNLUGU tercih et: yuksek ham oran, halo kaynakli sahte")
        print("  eslesmelerden de gelebilir (CLAHE'de olculen etkinin aynisi).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
