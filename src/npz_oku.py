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

Projede parametreler NEREDE:
  calibration/calib_result.npz  K, D, R, T, R1, R2, P1, P2, Q, RMS
  calibration/ground_plane.npz  zemin duzlemi (normal, d) + tespit bilgisi
  data/charuco_config.json      desen tanimi ve OLCULEN kare boyu
  data/camera_settings.json     pozlama, gain, WB, gamma...
  data/kutu_tablosu.json        standart kargo kutu olculeri
  data/olcum_defteri.csv        tum olcumlerin kaydi

Kullanim:
  .\\calistir.ps1 npz_oku --parametreler        (HEPSI tek ciktida)
  .\\calistir.ps1 npz_oku                       (en son cekim, ozet)
  .\\calistir.ps1 npz_oku --dosya q_2026...npz
  .\\calistir.ps1 npz_oku --png                 (PNG olarak disari aktar)
  .\\calistir.ps1 npz_oku --csv 1049,581        (o noktanin degerleri)
  .\\calistir.ps1 npz_oku --nokta 1049,581      (tek nokta 3B olcum)
"""
import argparse
import glob
import io
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


def parametreler():
    """Projedeki tum parametreleri tek ciktida topla ve TUREVLERI hesapla.

    Turev degerler onemli: kullanicinin gordugu sayilarin cogu
    dosyada dogrudan yazmiyor, matrislerden cikiyor. Ozellikle
    P1[0,0] ile K1[0,0] karistirilmamali (bkz. YONTEMLER.md bolum 4).
    """
    import json

    def baslik(t):
        print()
        print("=" * 72)
        print(t)
        print("=" * 72)

    # ---------------------------------------------------- kalibrasyon
    baslik("calibration/calib_result.npz  -  STEREO KALIBRASYON")
    if not os.path.exists(CALIB):
        print("  YOK - once kalibrasyon yapilmali")
    else:
        c = np.load(CALIB)
        for k in c.files:
            a = c[k]
            if a.ndim == 0:
                print(f"  {k:14} {float(a):.4f}")
        print()
        f_ham = float(c["K1"][0, 0])
        f_rekt = float(c["P1"][0, 0])
        B = float(np.linalg.norm(c["T"])) * 1000.0
        W, H = [int(v) for v in c["image_size"]]
        print(f"  Cozunurluk        : {W} x {H}")
        print(f"  Baz uzunlugu B    : {B:.2f} mm")
        print(f"  f (HAM, K1[0,0])  : {f_ham:.2f} px"
              f"   <- solvePnP, ham goruntu geometrisi")
        print(f"  f (REKT, P1[0,0]) : {f_rekt:.2f} px"
              f"   <- MESAFE HESABI BUNU KULLANIR")
        print(f"  Ana nokta (rekt)  : "
              f"({float(c['P1'][0,2]):.1f}, {float(c['P1'][1,2]):.1f})")
        print()
        print("  Turev: mesafe hassasiyeti  dZ = Z^2 / (f*B)")
        print(f"     {'Z (mm)':>8}{'1 px derinlik':>16}{'1 px yanal':>13}")
        for Z in (400, 550, 800, 1000):
            print(f"     {Z:8}{Z*Z/(f_rekt*B):13.2f} mm"
                  f"{Z/f_rekt:11.2f} mm")
        print()
        print("  Turev: arama araligina gore EN YAKIN olculebilir mesafe")
        for nd in (128, 256, 384):
            print(f"     numDisparities={nd:4} -> {f_rekt*B/nd:6.0f} mm"
                  f"   (sol kenarda olu bant %{nd/W*100:.1f})")

    # ---------------------------------------------------- zemin duzlemi
    baslik("calibration/ground_plane.npz  -  ZEMIN DUZLEMI")
    gp = os.path.join(PROJECT_DIR, "calibration", "ground_plane.npz")
    if not os.path.exists(gp):
        print("  YOK - Derinlik tabinda 'Zemin tespit et'")
    else:
        g = np.load(gp)
        for k in g.files:
            if k in ("K", "D"):
                continue
            a = g[k]
            print(f"  {k:14} {a}")
        nn = np.asarray(g["normal"], np.float64).ravel()
        print()
        print(f"  Duzlem denklemi : n.X + d = 0")
        print(f"  Kameradan uzaklik: {abs(float(g['d']))*1000:.1f} mm")
        print(f"  d METRE biriminde - koda mm gerektiginde *1000")

    # ---------------------------------------------------- json dosyalari
    for ad, dosya in (("data/charuco_config.json  -  DESEN",
                       "charuco_config.json"),
                      ("data/camera_settings.json  -  KAMERA AYARLARI",
                       "camera_settings.json")):
        baslik(ad)
        yol = os.path.join(PROJECT_DIR, "data", dosya)
        if not os.path.exists(yol):
            print("  YOK")
            continue
        d = json.load(open(yol, encoding="utf-8"))
        for k, v in d.items():
            if k == "not":
                print(f"  {k:26} {str(v)[:150]}")
            else:
                print(f"  {k:26} {v}")
        if dosya == "charuco_config.json":
            sq = d.get("olculen_kare_boyutu_mm")
            print()
            print(f"  KRITIK: olculen_kare_boyutu_mm = {sq} tum mutlak")
            print(f"  olceklerin dayanagi. Dogrulandi (2026-08-20): komsu")
            print(f"  koselerin 3B mesafesi 20 cekimde medyan 20.05 mm.")

    # ---------------------------------------------------- olcum defteri
    baslik("data/olcum_defteri.csv  -  OLCUM KAYDI")
    csv = os.path.join(PROJECT_DIR, "data", "olcum_defteri.csv")
    if not os.path.exists(csv):
        print("  YOK")
    else:
        satir = io.open(csv, encoding="utf-8").read().splitlines()
        print(f"  {len(satir)-1} kayit. Son 5:")
        for s2 in satir[-5:]:
            print(f"     {s2[:110]}")
    return 0


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
            # NumPy 2'de ndarray.ptp kaldirildi; np.ptp kullaniliyor
            aralik = float(np.ptp(d[gec]))
            n[gec] = np.clip((d[gec] - d[gec].min())
                             / max(aralik, 1e-6) * 255, 0, 255)
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
    ap.add_argument("--parametreler", action="store_true",
                    help="projedeki TUM parametre dosyalarini "
                         "ve turev degerleri dok")
    ap.add_argument("--liste", action="store_true",
                    help="mevcut cekimleri listele")
    ap.add_argument("--png", action="store_true",
                    help="dizileri PNG olarak disari aktar")
    ap.add_argument("--nokta", default=None,
                    help="x,y - o noktanin disparity ve 3B degeri")
    a = ap.parse_args()

    if a.parametreler:
        return parametreler()

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
