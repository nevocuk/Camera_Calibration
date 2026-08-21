"""Cekirdek modullerin GERCEK veriyle dogrulanmasi.

Bu test uydurma veriyle degil, elde bulunan gercek kalibrasyon
kareleriyle calisir. Amac: yeni (genel amacli) kalibrasyon kodunun,
bilinen bir veri setinde makul ve tekrarlanabilir sonuc uretmesi.

Kullanim:
    python dogrulama_testi.py --kareler <klasor> --kare-mm 20.0
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import sys

import numpy as np
import cv2

KOK = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, KOK)
from cekirdek import kalibrasyon, derinlik, olcum       # noqa: E402


def cift_bul(klasor):
    """L_###.png / R_###.png ya da S_###.png / G_###.png ciftleri."""
    ciftler = []
    for sol_on, sag_on in (("L", "R"), ("S", "G")):
        for p in sorted(glob.glob(os.path.join(klasor, f"{sol_on}_*.png"))):
            m = re.search(rf"{sol_on}_(\d+)\.png$", os.path.basename(p))
            if not m:
                continue
            q = os.path.join(klasor, f"{sag_on}_{m.group(1)}.png")
            if os.path.exists(q):
                ciftler.append((p, q))
        if ciftler:
            break
    return ciftler


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kareler", required=True)
    ap.add_argument("--kare-mm", type=float, default=20.0)
    ap.add_argument("--marker-mm", type=float, default=None)
    ap.add_argument("--kare-x", type=int, default=9)
    ap.add_argument("--kare-y", type=int, default=13)
    ap.add_argument("--sozluk", default="DICT_4X4_100")
    ap.add_argument("--en-fazla", type=int, default=25)
    a = ap.parse_args()

    yollar = cift_bul(a.kareler)
    if len(yollar) < 5:
        print(f"Yeterli cift bulunamadi: {len(yollar)}")
        return 1
    yollar = yollar[:a.en_fazla]
    print(f"{len(yollar)} kare cifti okunuyor...")
    ciftler = []
    for pl, pr in yollar:
        gl = cv2.imread(pl, cv2.IMREAD_GRAYSCALE)
        gr = cv2.imread(pr, cv2.IMREAD_GRAYSCALE)
        if gl is not None and gr is not None and gl.shape == gr.shape:
            ciftler.append((gl, gr))
    if not ciftler:
        print("Kare okunamadi")
        return 1
    h, w = ciftler[0][0].shape[:2]
    print(f"Cozunurluk: {w} x {h}\n")

    marker = a.marker_mm if a.marker_mm else a.kare_mm * 11.0 / 15.0
    tahta = kalibrasyon.TahtaTanimi(
        tur="charuco", kare_x=a.kare_x, kare_y=a.kare_y,
        kare_mm=a.kare_mm, marker_mm=marker, sozluk=a.sozluk)
    print(f"Tahta: {a.kare_x}x{a.kare_y} kare, kare {a.kare_mm} mm, "
          f"isaret {marker:.2f} mm, {a.sozluk}\n")

    print("--- 1) Kose tespiti ---")
    board, det = tahta.olustur()
    bulunan = 0
    kose_sayilari = []
    for gl, gr in ciftler:
        _, _, _, nl = kalibrasyon.kose_bul(gl, tahta, board, det)
        _, _, _, nr = kalibrasyon.kose_bul(gr, tahta, board, det)
        if nl >= 6 and nr >= 6:
            bulunan += 1
            kose_sayilari.append((nl, nr))
    print(f"   {bulunan}/{len(ciftler)} karede iki tarafta da desen var")
    if kose_sayilari:
        k = np.array(kose_sayilari)
        print(f"   kose sayisi: sol medyan {np.median(k[:,0]):.0f}, "
              f"sag medyan {np.median(k[:,1]):.0f}  "
              f"(maks {tahta.maks_kose})")
    if bulunan < 5:
        print("   YETERSIZ - kalibrasyon yapilamaz")
        return 1

    print("\n--- 2) Stereo kalibrasyon ---")
    sonuc, hata = kalibrasyon.stereo_kalibre(
        ciftler, (w, h), tahta,
        ilerleme=lambda i, n, m: None)
    if sonuc is None:
        print("   BASARISIZ:", hata)
        return 1
    o = kalibrasyon.ozet(sonuc)
    print(f"   RMS (stereo)   : {o['rms']:.4f} px")
    print(f"   RMS (sol/sag)  : {o['rms_sol']:.4f} / {o['rms_sag']:.4f}")
    print(f"   Baz uzunlugu   : {o['baz_mm']:.2f} mm")
    print(f"   f (rektifiye)  : {o['f_rektifiye_px']:.2f} px")
    print(f"   f (ham)        : {o['f_ham_px']:.2f} px")
    print(f"   Kullanilan kare: {o['kare_sayisi']}")

    print("\n--- 3) Epipolar hata (asil kalite olcutu) ---")
    epi, n = kalibrasyon.epipolar_hata(sonuc, ciftler, tahta)
    print(f"   {epi:.4f} px  ({n} kose uzerinde)")
    print("   " + ("IYI (< 1 px)" if epi < 1.0 else
                   "SINIRDA (1-2 px)" if epi < 2.0 else "KOTU (> 2 px)"))

    print("\n--- 4) Derinlik hassasiyeti (turev) ---")
    for Z, d in o["derinlik_adimi"].items():
        print(f"   {Z:5} mm  ->  1 piksel = {d:6.2f} mm")

    print("\n--- 5) Derinlik motoru gercek cift uzerinde ---")
    m1x, m1y, m2x, m2y = kalibrasyon.rektifikasyon_haritalari(sonuc)
    gl, gr = ciftler[len(ciftler) // 2]
    rl = cv2.remap(gl, m1x, m1y, cv2.INTER_LINEAR)
    rr = cv2.remap(gr, m2x, m2y, cv2.INTER_LINEAR)
    motor = derinlik.DerinlikMotoru(
        derinlik.DerinlikAyarlari(arama_araligi=128))
    dsp, ham = motor.hesapla(rl, rr)
    olu = motor.ayarlar.arama_araligi
    print(f"   harita doluluk : %{(dsp[:, olu:] > 0).mean()*100:.1f}")
    print(f"   GERCEK eslesme : %{ham[:, olu:].mean()*100:.1f}")
    pts = derinlik.noktalar_3b(dsp, sonuc["Q"])
    gec = (dsp > 0) & np.isfinite(pts).all(axis=2)
    if gec.sum() > 1000:
        Z = pts[gec][:, 2]
        print(f"   mesafe araligi : {np.percentile(Z,5):.0f} .. "
              f"{np.percentile(Z,95):.0f} mm")

    print("\n--- 6) Kurulum kontrolu ---")
    k = olcum.kurulum_kontrolu(dsp, pts)
    print(f"   yuzey acisi : {k['aci']:.1f} derece")
    print(f"   mesafe      : {k['mesafe']:.0f} mm")
    for uy in k["uyarilar"]:
        print(f"   UYARI: {uy}")
    if not k["uyarilar"]:
        print("   uyari yok")

    print("\nTUM ADIMLAR CALISTI")
    return 0


if __name__ == "__main__":
    sys.exit(main())
