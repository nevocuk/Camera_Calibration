"""Kaliteli kare (.npz) dosyalarini oku, ozetle, disari aktar.

.npz NumPy'nin sikistirilmis arsiv formatidir - icinde birden fazla
dizi bir sozluk gibi durur. Normal bir gorsel programiyla acilmaz.

Bir cekim dosyasinin icerigi:
  disparity      : zemin cikarilmis disparity (float32, piksel)
  disparity_ham  : zemin cikarma ONCESI disparity  <- olcumler bunu kullanir
  raw_mask       : WLS DOLDURMADAN once gercekten eslesen pikseller.
                   Kalite olcusu budur; WLS sonrasi maske her yeri
                   dolu gosterdigi icin yaniltir.
  gray_l/gray_r  : rektifiye edilmis gri goruntuler (uint8)
  zemin_cikarildi/zemin_esik_mm : cekim anindaki ayar

Kullanim:
  .\\calistir.ps1 npz_oku                       (en son cekim, ozet)
  .\\calistir.ps1 npz_oku --dosya q_2026...npz
  .\\calistir.ps1 npz_oku --png                 (PNG olarak disari aktar)
  .\\calistir.ps1 npz_oku --csv 1049,581        (o noktanin degerleri)
  .\\calistir.ps1 npz_oku --nokta 1049,581      (tek nokta 3B olcum)
"""
import argparse
import glob
import os
import sys

import numpy as np
import cv2

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
CAP_DIR = os.path.join(PROJECT_DIR, "output", "depth_captures")
CALIB = os.path.join(PROJECT_DIR, "calibration", "calib_result.npz")

ACIKLAMA = {
    "disparity": "zemin cikarilmis disparity (piksel)",
    "disparity_ham": "zemin cikarma ONCESI disparity - OLCUMLER BUNU KULLANIR",
    "raw_mask": "WLS oncesi GERCEK eslesme - asil kalite olcusu",
    "gray_l": "rektifiye SOL gri goruntu",
    "gray_r": "rektifiye SAG gri goruntu",
    "zemin_cikarildi": "cekim aninda zemin cikarma acik miydi",
    "zemin_esik_mm": "cekim anindaki zemin esigi (mm)",
    "normal": "duzlem normali (birim vektor)",
    "d": "duzlem sabiti (METRE) - h = n.X + d",
    "K": "kullanilan intrinsik matris",
    "D": "distorsiyon katsayilari",
    "frame": "hangi cercevede cozuldu (rectified/raw)",
    "n_corners": "tespit edilen kose sayisi",
    "rms_px": "yeniden izdusum hatasi (piksel)",
    "aci_derece": "kamera-duzlem normali arasindaki aci",
    "yontem": "duzlem hangi yontemle bulundu",
    "tarih": "tespit tarihi",
}


def dosya_bul(ad):
    if ad and os.path.isabs(ad):
        return ad
    if ad:
        return os.path.join(CAP_DIR, ad)
    liste = sorted(glob.glob(os.path.join(CAP_DIR, "q_*_data.npz")))
    if not liste:
        return None
    return liste[-1]


def ozet(z, yol):
    print("=" * 72)
    print(f"DOSYA: {os.path.basename(yol)}")
    print(f"       {os.path.getsize(yol) / 1e6:.1f} MB, "
          f"{len(z.files)} dizi")
    print("=" * 72)
    print(f"{'anahtar':<18}{'tip':<10}{'boyut':<16}{'MB':>7}  aciklama")
    print("-" * 72)
    for k in z.files:
        a = z[k]
        print(f"{k:<18}{str(a.dtype):<10}{str(a.shape):<16}"
              f"{a.nbytes / 1e6:7.2f}  {ACIKLAMA.get(k, '')}")
    print()
    for k in z.files:
        a = z[k]
        if a.ndim == 0:                      # skaler
            print(f"  {k} = {a}")
    print()
    if "disparity_ham" in z.files:
        d = z["disparity_ham"]
        gec = d > 0
        print(f"  disparity_ham: gecerli %{gec.mean() * 100:.1f}, "
              f"aralik {d[gec].min():.1f}..{d[gec].max():.1f} px")
    if "raw_mask" in z.files:
        print(f"  raw_mask     : GERCEK eslesme "
              f"%{z['raw_mask'].mean() * 100:.1f}")
        print("                 (bu deger dusukse harita cogunlukla "
              "WLS TAHMINI demektir)")


def mesafeye_cevir(z, yol):
    """disparity -> mm. Kalibrasyon varsa gercek olcek kullanilir."""
    if not os.path.exists(CALIB):
        return None, None
    c = np.load(CALIB)
    d = z["disparity_ham" if "disparity_ham" in z.files
          else "disparity"].astype(np.float32)
    pts = cv2.reprojectImageTo3D(d, c["Q"]) * 1000.0
    return d, pts


def png_yaz(z, yol):
    kok = yol.replace("_data.npz", "")
    yazilan = []
    for k in ("gray_l", "gray_r"):
        if k in z.files:
            p = f"{kok}_{k}_export.png"
            cv2.imwrite(p, z[k])
            yazilan.append(p)
    for k in ("disparity", "disparity_ham"):
        if k not in z.files:
            continue
        d = z[k].astype(np.float32)
        # 0-255'e olcekle; gecersiz pikseller siyah
        n = np.zeros(d.shape, np.uint8)
        gec = d > 0
        if gec.any():
            n[gec] = np.clip((d[gec] - d[gec].min())
                             / max(d[gec].ptp(), 1e-6) * 255, 0, 255)
        p = f"{kok}_{k}_export.png"
        cv2.imwrite(p, cv2.applyColorMap(n, cv2.COLORMAP_TURBO)
                    * gec[:, :, None])
        yazilan.append(p)
    if "raw_mask" in z.files:
        p = f"{kok}_raw_mask_export.png"
        cv2.imwrite(p, z["raw_mask"].astype(np.uint8) * 255)
        yazilan.append(p)
    print("Yazilan dosyalar:")
    for p in yazilan:
        print("   ", os.path.basename(p))


def nokta_oku(z, yol, sx, sy):
    d, pts = mesafeye_cevir(z, yol)
    if d is None:
        print("Kalibrasyon yok, yalnizca disparity gosterilebilir.")
        d = z["disparity_ham" if "disparity_ham" in z.files
              else "disparity"]
        print(f"  ({sx},{sy}) disparity = {d[sy, sx]:.2f} px")
        return
    print(f"NOKTA ({sx}, {sy})")
    print(f"  disparity : {d[sy, sx]:.2f} px")
    if d[sy, sx] <= 0:
        print("  -> bu pikselde esleme YOK, 3B konum hesaplanamaz")
        return
    X, Y, Z = pts[sy, sx]
    print(f"  3B konum  : X {X:8.1f}   Y {Y:8.1f}   Z {Z:8.1f}  (mm)")
    # 31x31 pencerede medyan - tek piksel gurultulu olabilir
    y0, y1 = max(0, sy - 15), sy + 16
    x0, x1 = max(0, sx - 15), sx + 16
    yama = pts[y0:y1, x0:x1].reshape(-1, 3)
    dd = d[y0:y1, x0:x1].reshape(-1)
    iyi = (dd > 0) & np.isfinite(yama).all(axis=1)
    if iyi.sum() > 20:
        print(f"  31x31 medyan Z: {np.median(yama[iyi][:, 2]):.1f} mm "
              f"({iyi.sum()} gecerli piksel)")
    if "raw_mask" in z.files:
        rm = z["raw_mask"][y0:y1, x0:x1]
        print(f"  cevrede gercek eslesme: %{rm.mean() * 100:.0f}"
              + ("   <- DUSUK, deger WLS tahmini olabilir"
                 if rm.mean() < 0.5 else ""))


def main():
    ap = argparse.ArgumentParser(
        description="Kaliteli kare (.npz) dosyasini oku ve disari aktar")
    ap.add_argument("--dosya", default=None,
                    help="dosya adi; verilmezse en son cekim")
    ap.add_argument("--liste", action="store_true",
                    help="mevcut cekimleri listele")
    ap.add_argument("--png", action="store_true",
                    help="dizileri PNG olarak disari aktar")
    ap.add_argument("--nokta", default=None,
                    help="x,y - o noktanin disparity ve 3B degeri")
    a = ap.parse_args()

    if a.liste:
        liste = sorted(glob.glob(os.path.join(CAP_DIR, "q_*_data.npz")))
        print(f"{len(liste)} cekim:")
        for p in liste:
            print("   ", os.path.basename(p))
        return 0

    yol = dosya_bul(a.dosya)
    if yol is None or not os.path.exists(yol):
        print(f"Dosya bulunamadi: {yol}")
        return 1
    z = np.load(yol)
    ozet(z, yol)
    if a.nokta:
        print()
        sx, sy = [int(float(v)) for v in a.nokta.replace(" ", "").split(",")]
        nokta_oku(z, yol, sx, sy)
    if a.png:
        print()
        png_yaz(z, yol)
    return 0


if __name__ == "__main__":
    sys.exit(main())
