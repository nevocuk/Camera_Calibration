"""Kaydedilmis bir cekimden cismin EN / BOY / YUKSEKLIK degerlerini olc.

Nasil calisir:
  1. Zemin duzlemi (n, d) ile her 3B noktanin duzleme uzakligi h bulunur.
  2. Esigin ustundeki en buyuk baglantili bolge = cisim.
  3. Cismin noktalari DUZLEM KOORDINATLARINA cevrilir:
        u, v = duzlem icinde iki dik yon,  h = duzlemden yukseklik
  4. (u, v) duzleminde minAreaRect -> EN ve BOY (donmus dikdortgen,
     yani cisim egik durursa bile dogru olcer)
     h'nin ust yuzdeligi -> YUKSEKLIK

Neden duzlem koordinatlari: goruntudeki piksel en/boyu kameraya olan
mesafeye ve bakis acisina gore degisir. Duzlem uzerine izdusurunce
olcu gercek fiziksel boyut olur.

Kullanim:
  .\calistir.ps1 cisim_olc                 (en son cekim)
  .\calistir.ps1 cisim_olc --dosya q_20260818_151052_data.npz
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
GROUND = os.path.join(PROJECT_DIR, "calibration", "ground_plane.npz")


def zemin_yukle(calib):
    if not os.path.exists(GROUND):
        print("HATA: zemin duzlemi yok. Derinlik tabi > 'Zemin tespit et'.")
        sys.exit(1)
    with np.load(GROUND) as g:
        n = np.asarray(g["normal"], np.float64).ravel()
        d = float(g["d"])
        cerceve = str(g["frame"]) if "frame" in g.files else "raw"
        tarih = str(g["tarih"]) if "tarih" in g.files else "?"
    if cerceve != "rectified":
        n = np.asarray(calib["R1"], np.float64) @ n
    return n / np.linalg.norm(n), d, tarih


def olc(yol, esik_mm=12, maks_yuk=400, z_tol=150, min_alan=3000,
        nokta=None, goster=True):
    calib = np.load(CALIB)
    n, d, g_tarih = zemin_yukle(calib)
    z = np.load(yol)
    # Zemin cikarilmamis harita kullanilir: cismin TABANI da lazim,
    # yoksa yukseklik ve taban alani eksik olculur.
    dsp = z["disparity_ham" if "disparity_ham" in z.files
            else "disparity"].astype(np.float32)

    pts = cv2.reprojectImageTo3D(dsp, calib["Q"])
    gec = (dsp > 0) & np.isfinite(pts).all(axis=2)
    h = np.full(dsp.shape, -1e9, np.float64)
    h[gec] = (pts[gec] @ n + d) * 1000.0        # mm

    # --- CALISMA HACMI
    # Zemin cikarma yalnizca MASA DUZLEMINI siler. Arkadaki duvar, raf,
    # kutular da duzlemin "uzerinde"dir ve cisim sanilir - ilk denemede
    # en buyuk bolge arka plan cikti (boy 3219 mm). Bu yuzden olculecek
    # cisim bir hacimle sinirlanir: masaya yakin ve makul yukseklikte.
    # Duzlem SONSUZDUR - tahtanin durdugu kare degil, onun uzandigi
    # tum duzlem. Bu yuzden odanin obur ucundaki raf/duvar da
    # "duzlemin uzerinde" cikar. Yukseklik siniri bunu elemiyor
    # (olculdu: cisim 419-2804 mm'ye yayildi). Gercek ayirici
    # KAMERA MESAFESIDIR: cisim masanin uzerinde, arka plan uzakta.
    Zmm = pts[:, :, 2] * 1000.0
    duzlem = gec & (np.abs(h) < 15)          # masa yuzeyi pikselleri
    if duzlem.sum() > 5000:
        z_masa = float(np.median(Zmm[duzlem]))
    else:
        z_masa = float(np.median(Zmm[gec]))
    z_sinir = z_masa + z_tol
    print(f"  Masa mesafesi ~{z_masa:.0f} mm -> {z_sinir:.0f} mm otesi "
          "arka plan sayiliyor")

    m = ((h >= esik_mm) & (h <= maks_yuk) & gec
         & (Zmm < z_sinir)).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE,
                         cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN,
                         cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    # Morfoloji maskeyi gecersiz piksellere tasirabilir -> inf/NaN uretir
    m = (m.astype(bool) & gec).astype(np.uint8)

    nlab, lab, st, cen = cv2.connectedComponentsWithStats(m, 8)
    if nlab < 2:
        print("Cisim bulunamadi (calisma hacminde bolge yok).")
        return None
    # Goruntu MERKEZINE en yakin yeterli buyuklukteki bolge secilir -
    # "en buyuk" olcut degil, cunku arka plan her zaman daha buyuk.
    H, W = dsp.shape
    # Kalabalik sahnede "merkeze en yakin" yetmez: masadaki diger
    # cisimler ayni mesafe penceresinde olup birlesebiliyor (olculdu:
    # boy 315 mm cikti, esik degistirmek DEGISTIRMEDI - demek ki
    # havlu degil, komsu cisimler). Hedef noktayi kullanici verebilir.
    hedef = (np.array(nokta, float) if nokta is not None
             else np.array([W / 2.0, H / 2.0]))
    aday = [(np.linalg.norm(cen[k] - hedef), k) for k in range(1, nlab)
            if st[k, cv2.CC_STAT_AREA] >= min_alan]
    if not aday:
        print(f"Yeterli buyuklukte bolge yok (min {min_alan} px).")
        return None
    aday.sort()
    i = aday[0][1]
    cisim = (lab == i)
    print(f"  {len(aday)} aday bolgeden merkeze en yakini secildi "
          f"({int(st[i, cv2.CC_STAT_AREA]):,} px)")

    # --- duzlem koordinat sistemi: n'e dik iki yon
    yardim = np.array([1.0, 0, 0]) if abs(n[0]) < 0.9 else np.array([0, 1.0, 0])
    u = np.cross(n, yardim); u /= np.linalg.norm(u)
    v = np.cross(n, u);      v /= np.linalg.norm(v)

    P = pts[cisim] * 1000.0        # mm
    uu = P @ u
    vv = P @ v
    hh = h[cisim]

    # --- EN x BOY: duzlem uzerinde donmus minimum dikdortgen
    xy = np.stack([uu, vv], 1).astype(np.float32)
    (cx, cy), (w1, w2), aci = cv2.minAreaRect(xy)
    en, boy = sorted((w1, w2))

    # --- YUKSEKLIK: ust yuzdelik (tek tuk aykiri degeri disla)
    yukseklik = float(np.percentile(hh, 98))

    print("=" * 62)
    print(f"CEKIM : {os.path.basename(yol)}")
    print(f"Zemin : {g_tarih}   esik={esik_mm} mm")
    print("=" * 62)
    print(f"  Cisim pikseli   : {int(cisim.sum()):,}")
    print(f"  Kamera mesafesi : {np.median(P[:, 2]):.0f} mm")
    print()
    print(f"  EN        : {en:7.1f} mm")
    print(f"  BOY       : {boy:7.1f} mm")
    print(f"  YUKSEKLIK : {yukseklik:7.1f} mm")
    print()
    print(f"  Desi      : {en*boy*yukseklik/3000000:.2f}"
          "   (en*boy*yuk / 3000)")
    print()
    print("  Yuzeyin derinlik yayilimi (cismin kendi kalinligi + egim):")
    zr = P[:, 2]
    print(f"    en yakin {zr.min():.0f} mm | en uzak {zr.max():.0f} mm"
          f" | fark {zr.max()-zr.min():.0f} mm")
    print(f"    yukseklik dagilimi: %5={np.percentile(hh,5):.1f}"
          f"  %50={np.percentile(hh,50):.1f}"
          f"  %95={np.percentile(hh,95):.1f} mm")

    if goster:
        vis = cv2.cvtColor(z["gray_l"], cv2.COLOR_GRAY2BGR)
        kont, _ = cv2.findContours(cisim.astype(np.uint8),
                                   cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(vis, kont, -1, (0, 255, 0), 3)
        cv2.putText(vis, f"{en:.0f} x {boy:.0f} x {yukseklik:.0f} mm",
                    (60, 90), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (0, 255, 0), 4)
        cikti = yol.replace("_data.npz", "_olcum.png")
        cv2.imwrite(cikti, vis)
        print(f"\n  Gorsel: {os.path.basename(cikti)}")
    return en, boy, yukseklik


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dosya", default=None)
    p.add_argument("--esik", type=int, default=12,
                   help="duzlemden en az bu kadar yuksek (mm)")
    p.add_argument("--maks", type=int, default=400,
                   help="duzlemden en fazla bu kadar yuksek (mm) - "
                        "arka plani disarida tutar")
    p.add_argument("--ztol", type=int, default=150,
                   help="masa mesafesinden bu kadar OTESI arka plan (mm)")
    p.add_argument("--nokta", default=None,
                   help="cismin uzerinde bir piksel: 'x,y'. Verilmezse "
                        "goruntu merkezi kullanilir.")
    a = p.parse_args()
    if a.dosya:
        yol = a.dosya if os.path.isabs(a.dosya) else os.path.join(CAP_DIR, a.dosya)
    else:
        f = sorted(glob.glob(os.path.join(CAP_DIR, "q_*_data.npz")))
        if not f:
            print("Cekim bulunamadi."); return 1
        yol = f[-1]
    nk = None
    if a.nokta:
        nk = [float(v) for v in a.nokta.replace(" ", "").split(",")]
    olc(yol, esik_mm=a.esik, maks_yuk=a.maks, z_tol=a.ztol, nokta=nk)
    return 0


if __name__ == "__main__":
    sys.exit(main())
