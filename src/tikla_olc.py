"""Tiklanan cismi derinlik surekliligiyle ayir ve EN/BOY/YUKSEKLIK olc.

Neden bu yontem: zemin duzlemi tabanli olcum, cismin bir DUZLEM uzerinde
durmasini ve o duzlemin tespit edilmis olmasini gerektirir. Tezgahta,
rafta veya elde duran bir cisimde bu sart saglanmaz.

Bu script cismi TIKLANAN NOKTADAN buyuyerek bulur: komsu piksellerin
disparity farki esigin altindaysa ayni cisme aittir. Cisim komsularindan
derinlikce ayrildigi anda sinir kendiliginden olusur - ayri bir esik veya
calisma hacmi gerekmez.

Boyutlar PCA ile: nokta bulutunun ana eksenleri bulunur, kutu O EKSENLERE
gore olculur. Boylece cisim egik dursa bile gercek boyutlari cikar
(eksenlere hizali kutu, egik cisimde koseden koseye olcup sisirir).

NE ZAMAN CALISIR, NE ZAMAN CALISMAZ (2026-08-19 olculdu):

  CALISIR  - cisim arka planindan DERINLIKCE ayriysa
             (havada tutulan, masa kenarinda, arkasi bos)

  CALISMAZ - cisim bir YUZEYIN UZERINDE duruyorsa. Termos deneyi:
             termos ve altindaki masa ikisi de ~830 mm. Derinlik
             ikisini ayirmiyor cunku GERCEKTEN ayri degiller.
             Olculen bolge en/boy orani 0.86-1.28 cikti; dik bir
             silindirde ~0.3 olmaliydi -> bolge masaya yayilmis.
             Bu durumda ZEMIN DUZLEMI yontemi kullanilmali
             (uygulamada Olcum tabi > "Duzlemle olc"): duzlem
             cikarilinca cisim yuzeyden yukseklige gore ayrilir.

Kullanim:
  .\calistir.ps1 tikla_olc --nokta 1300,1050
  .\calistir.ps1 tikla_olc --dosya q_20260819_113659_data.npz --nokta 1300,1050
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


def bolge_buyut(dsp, seed_yx, tol_px=12.0, min_alan=800):
    """Tiklanan noktadan disparity surekliligiyle bolge buyut.

    SABIT ARALIK (FIXED_RANGE) kullanilir: her piksel TOHUMLA
    karsilastirilir, komsusuyla degil.

    Neden: komsu bazli buyutme surekli bir yuzeyde HIC DURMAZ. Olculdu -
    masa kameradan uzaga duzgun azaldigi icin komsu farklari hep kucuk
    kaliyor ve bolge termostan baslayip arka duvara kadar yayildi
    (%62-81 kare, 386-7721 mm). Sabit aralik, cismin derinlik kalinligi
    kadar bir bant tanimlar ve arka plana kacmayi engeller.

    tol_px: tohumdan izin verilen disparity sapmasi. Kalin/egik cisimde
    buyutulmeli, ince cisimde kucultulmeli.
    """
    h, w = dsp.shape
    sy, sx = seed_yx
    if not (0 <= sy < h and 0 <= sx < w) or dsp[sy, sx] <= 0:
        return None, "tiklanan noktada disparity yok"
    mask = np.zeros((h + 2, w + 2), np.uint8)
    im = dsp.astype(np.float32).copy()
    cv2.floodFill(im, mask, (int(sx), int(sy)), 0,
                  loDiff=tol_px, upDiff=tol_px,
                  flags=(8 | cv2.FLOODFILL_MASK_ONLY
                         | cv2.FLOODFILL_FIXED_RANGE | (255 << 8)))
    m = mask[1:-1, 1:-1].astype(bool) & (dsp > 0)
    # Guvenlik: bolge karenin cok buyuk kismini kapliyorsa kacmistir
    if m.mean() > 0.35:
        return None, (f"bolge kareye tasti (%{m.mean()*100:.0f}) - "
                      "tolerans dusur veya cisim arka planla ayni derinlikte")
    if m.sum() < min_alan:
        return None, f"bolge cok kucuk ({int(m.sum())} px)"
    # tek tuk kopuk parcalari at, delikleri kapat
    mm = m.astype(np.uint8)
    mm = cv2.morphologyEx(mm, cv2.MORPH_CLOSE,
                          cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    n, lab, st, _ = cv2.connectedComponentsWithStats(mm, 8)
    if n > 1:
        i = int(np.argmax(st[1:, cv2.CC_STAT_AREA])) + 1
        mm = (lab == i).astype(np.uint8)
    return mm.astype(bool) & (dsp > 0), None


def pca_kutu(P):
    """Nokta bulutunun ana eksenlerine hizali kutu -> uc boyut (mm)."""
    orta = P.mean(axis=0)
    Q = P - orta
    # kovaryansin ozvektorleri = ana eksenler
    _, s, Vt = np.linalg.svd(Q, full_matrices=False)
    proj = Q @ Vt.T
    # her eksende %1-%99 aralik (aykiri noktalari disla)
    boy = []
    for k in range(3):
        a, b = np.percentile(proj[:, k], [1, 99])
        boy.append(float(b - a))
    return sorted(boy, reverse=True), Vt, orta


def olc(yol, nokta, tol=12.0, goster=True):
    c = np.load(CALIB)
    z = np.load(yol)
    dsp = z["disparity_ham" if "disparity_ham" in z.files
            else "disparity"].astype(np.float32)
    ham = z["raw_mask"] if "raw_mask" in z.files else None
    h, w = dsp.shape
    sx, sy = int(nokta[0]), int(nokta[1])

    m, hata = bolge_buyut(dsp, (sy, sx), tol_px=tol)
    if m is None:
        print(f"HATA: {hata}")
        return None

    pts = cv2.reprojectImageTo3D(dsp, c["Q"]) * 1000.0     # mm
    ok = m & np.isfinite(pts).all(axis=2)
    P = pts[ok]
    if len(P) < 500:
        print("HATA: yeterli 3B nokta yok")
        return None

    boy, eksen, orta = pca_kutu(P)
    Z = P[:, 2]

    print("=" * 62)
    print(f"CEKIM  : {os.path.basename(yol)}")
    print(f"TIKLAMA: ({sx}, {sy})   tolerans {tol:.1f} px")
    print("=" * 62)
    print(f"  Bolge         : {int(ok.sum()):,} piksel "
          f"(%{ok.mean()*100:.2f} kare)")
    print(f"  Mesafe        : {np.median(Z):.0f} mm "
          f"({Z.min():.0f} - {Z.max():.0f})")
    if ham is not None:
        print(f"  Ham eslesme   : %{ham[ok].mean()*100:.1f}"
              "   (dusukse boyutlar WLS tahminine dayanir)")
    print()
    # SEKIL KONTROLU: bolge cismin degil altindaki yuzeyin sekliyse
    # piksel kutusu kareye yakin cikar. Uyar ki yanlis olcum
    # rapora girmesin.
    ys, xs = np.where(ok)
    kw, kh = xs.max()-xs.min(), ys.max()-ys.min()
    oran = kw / max(kh, 1)
    if 0.7 < oran < 1.4 and ok.mean() > 0.02:
        print("  !! UYARI: bolge kareye yakin (en/boy "
              f"{oran:.2f}) ve genis.")
        print("     Cisim bir yuzeyin uzerinde duruyorsa bolge o")
        print("     yuzeye yayilmis olabilir - derinlik ikisini")
        print("     ayirmaz. Zemin duzlemi yontemini kullan:")
        print("     Olcum tabi > 'Duzlemle olc'")
        print()
    print(f"  UZUN kenar    : {boy[0]:7.1f} mm")
    print(f"  ORTA kenar    : {boy[1]:7.1f} mm")
    print(f"  KISA kenar    : {boy[2]:7.1f} mm")
    print(f"  Desi          : {boy[0]*boy[1]*boy[2]/3e6:.2f}")
    print()
    print("  Not: kisa kenar cismin GORUNEN yuzunun kalinligidir.")
    print("       Stereo yalnizca kameraya bakan yuzu gorur; arka yuz")
    print("       olculemez. Silindir/kutu icin gercek derinlik bunun")
    print("       yaklasik 2 katidir.")

    if goster:
        vis = cv2.cvtColor(z["gray_l"], cv2.COLOR_GRAY2BGR)
        kont, _ = cv2.findContours(ok.astype(np.uint8), cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(vis, kont, -1, (0, 255, 0), 3)
        cv2.drawMarker(vis, (sx, sy), (0, 0, 255), cv2.MARKER_CROSS, 60, 4)
        cv2.putText(vis, f"{boy[0]:.0f} x {boy[1]:.0f} x {boy[2]:.0f} mm",
                    (60, 90), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (0, 255, 0), 4)
        cikti = yol.replace("_data.npz", "_tikla.png")
        cv2.imwrite(cikti, vis)
        print(f"\n  Gorsel: {os.path.basename(cikti)}")
    return boy


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dosya", default=None)
    p.add_argument("--nokta", required=True, help="x,y")
    p.add_argument("--tol", type=float, default=12.0,
                   help="TOHUMDAN izin verilen disparity sapmasi (px)")
    a = p.parse_args()
    yol = (a.dosya if a.dosya and os.path.isabs(a.dosya)
           else os.path.join(CAP_DIR, a.dosya) if a.dosya
           else sorted(glob.glob(os.path.join(CAP_DIR, "q_*_data.npz")))[-1])
    nk = [float(v) for v in a.nokta.replace(" ", "").split(",")]
    olc(yol, nk, tol=a.tol)
    return 0


if __name__ == "__main__":
    sys.exit(main())
