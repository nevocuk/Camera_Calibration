"""Raporun iki sekli - VERIDEN uretilir, elle cizilmez.

Neden yeniden yazildi: bu iki sekil daha once tek seferlik scriptlerle
uretilip PNG olarak birakilmisti ve icerikleri raporla CELISIYORDU.

  akis semasi  : "31 stereo cift, AprilTag grid board" yaziyordu;
                 rapor 44 cift ve ChArUco diyor. Ayrica akis kontur
                 tabanliydi, oysa olcum bolge buyutme + PCA ile
                 yapiliyor. Basligina da "Sekil 1" gomuluydu.
  kose hatasi  : grid board donemine ait marker kose hatasi (65-71 px)
                 grafigiydi; 6.5'teki 0,407 px epipolar hatayla hicbir
                 ilgisi yok. Basliginda "Sekil 4" yaziyordu.

Yeni surumler:
  - akis semasi metni Cizelge 2 ile ayni kaynaktan gelir
  - epipolar histogram kalibrasyon karelerinden olculur
  - hicbirinde "Sekil N" basligi yok; numarayi Word altyazisi verir

Kullanim:
    python src/rapor_sekilleri.py
"""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrow, FancyBboxPatch
import numpy as np

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CIKTI = os.path.join(KOK, "output", "reports")

# Cizelge 2 ile ayni adimlar, ayni sirada. Biri degisirse digeri de
# degismeli - bu yuzden tek yerde duruyor.
ADIMLAR = [
    ("Kamera ayarlarını kilitle\n(pozlama, gain, WB, çözünürlük)", "hazirlik"),
    ("Eş zamanlı kare yakalama\n(MSMF, MJPG, 2048×1536)", "hazirlik"),
    ("ChArUco köşe tespiti\n(44 stereo çift)", "kalibrasyon"),
    ("calibrateCamera() ×2\nK₁,D₁ / K₂,D₂", "kalibrasyon"),
    ("stereoCalibrate()\nCALIB_FIX_INTRINSIC → R, T", "kalibrasyon"),
    ("stereoRectify()\nR₁,R₂,P₁,P₂,Q", "kalibrasyon"),
    ("Ton eşlemesi (histogram)\n+ SGBM + WLS filtresi", "derinlik"),
    ("reprojectImageTo3D(Q)\n→ X, Y, Z", "derinlik"),
    ("Tıklanan noktadan bölge büyütme\n(tolerans + parlaklık kısıtı)",
     "olcum"),
    ("PCA ile yönlü sınır kutusu\n→ uzun × orta × kısa", "olcum"),
    ("Kargo kutusu önerisi\n+ kesim yönergesi", "olcum"),
]

RENK = {"hazirlik": "#dbe7f3", "kalibrasyon": "#fbe3cd",
        "derinlik": "#dcecd6", "olcum": "#f5d9dd"}
GRUP_ADI = [("kalibrasyon", "KALİBRASYON"), ("derinlik", "DERİNLİK"),
            ("olcum", "ÖLÇÜM")]


def akis_semasi(yol):
    n = len(ADIMLAR)
    yuk = 0.82
    bosluk = 0.30
    fig, ax = plt.subplots(figsize=(7.4, n * (yuk + bosluk) + 0.4))
    for i, (metin, grup) in enumerate(ADIMLAR):
        y = n - i - 1
        ax.add_patch(FancyBboxPatch(
            (0.06, y * (yuk + bosluk)), 0.88, yuk,
            boxstyle="square,pad=0", linewidth=1.1,
            edgecolor="#444444", facecolor=RENK[grup]))
        ax.text(0.5, y * (yuk + bosluk) + yuk / 2, metin,
                ha="center", va="center", fontsize=10.5)
        if i < n - 1:
            ax.add_patch(FancyArrow(
                0.5, y * (yuk + bosluk) - 0.02, 0, -bosluk + 0.10,
                width=0.004, head_width=0.028, head_length=0.10,
                length_includes_head=True, color="#444444"))

    for grup, ad in GRUP_ADI:
        idx = [i for i, (_, g) in enumerate(ADIMLAR) if g == grup]
        ust = (n - min(idx) - 1) * (yuk + bosluk) + yuk
        alt = (n - max(idx) - 1) * (yuk + bosluk)
        ax.plot([0.965, 0.965], [alt, ust], color="#888888", linewidth=1)
        ax.text(0.985, (alt + ust) / 2, ad, rotation=90, fontsize=9.5,
                ha="center", va="center", color="#666666")

    ax.set_xlim(0, 1.03)
    ax.set_ylim(-0.1, n * (yuk + bosluk))
    ax.axis("off")
    fig.tight_layout(pad=0.3)
    fig.savefig(yol, dpi=150)
    plt.close(fig)
    return yol


def epipolar_histogram(yol):
    """Epipolar hatanin dagilimi - src/epipolar_dogrula.py ile ayni olcum."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import cv2
    import glob
    import calibration as kal

    c = np.load(os.path.join(KOK, "calibration", "calib_result.npz"))
    boyut = tuple(int(x) for x in c["image_size"])
    board, detector, _ = kal.load_config()
    m1x, m1y = cv2.initUndistortRectifyMap(c["K1"], c["D1"], c["R1"],
                                           c["P1"], boyut, cv2.CV_32FC1)
    m2x, m2y = cv2.initUndistortRectifyMap(c["K2"], c["D2"], c["R2"],
                                           c["P2"], boyut, cv2.CV_32FC1)
    hatalar, cift = [], 0
    kareler = os.path.join(KOK, "calibration", "frames")
    for sol in sorted(glob.glob(os.path.join(kareler, "L_*.png"))):
        sag = sol.replace(os.sep + "L_", os.sep + "R_")
        if not os.path.exists(sag):
            continue
        rl = cv2.remap(cv2.imread(sol, 0), m1x, m1y, cv2.INTER_LINEAR)
        rr = cv2.remap(cv2.imread(sag, 0), m2x, m2y, cv2.INTER_LINEAR)
        cl, il = kal.detect_corners(rl, board, detector)
        cr, ir = kal.detect_corners(rr, board, detector)
        if cl is None or cr is None:
            continue
        fl, _, fr, _, _ = kal._filter_common_markers(cl, il, cr, ir, False)
        if fl is None:
            continue
        pl = np.array(fl).reshape(-1, 2)
        pr = np.array(fr).reshape(-1, 2)
        hatalar.extend(np.abs(pl[:, 1] - pr[:, 1]).tolist())
        cift += 1
    if not hatalar:
        return None

    h = np.array(hatalar)
    ort, med = h.mean(), np.median(h)
    fig, ax = plt.subplots(figsize=(7.6, 4.2))
    ax.hist(h, bins=np.arange(0, 2.6, 0.1), color="#4a7ebb",
            edgecolor="white", linewidth=0.6)
    ax.axvline(ort, color="#c0392b", linestyle="--", linewidth=1.6,
               label=f"ortalama {ort:.3f} px".replace(".", ","))
    ax.axvline(med, color="#2e7d32", linestyle=":", linewidth=1.6,
               label=f"medyan {med:.3f} px".replace(".", ","))
    ax.axvline(1.0, color="#777777", linewidth=1.0)
    ax.text(1.02, ax.get_ylim()[1] * 0.93,
            f"1 px üstü: %{100 * (h > 1).mean():.1f}".replace(".", ","),
            fontsize=9.5, color="#555555")
    ax.set_xlabel("Rektifikasyon sonrası satır farkı (piksel)")
    ax.set_ylabel("Köşe sayısı")
    ax.set_title(f"{cift} stereo çift, {len(h)} ortak köşe", fontsize=11)
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(yol, dpi=150)
    plt.close(fig)
    return yol


def main():
    os.makedirs(CIKTI, exist_ok=True)
    a = akis_semasi(os.path.join(CIKTI, "sekil_akis_semasi.png"))
    print(f"  {os.path.relpath(a, KOK)}")
    b = epipolar_histogram(os.path.join(CIKTI, "sekil_epipolar_dagilim.png"))
    print(f"  {os.path.relpath(b, KOK)}" if b else "  epipolar sekli URETILEMEDI")
    return 0


if __name__ == "__main__":
    sys.exit(main())
