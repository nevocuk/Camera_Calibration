"""Kalibrasyon karelerini ele: kotuleri ayir, kalanlarin kapsamasini raporla.

Kullanim:
    .\\calistir.ps1 yedekle                 # sadece analiz, DOSYAYA DOKUNMAZ
    .\\calistir.ps1 yedekle -- --uygula     # kotuleri 'elenen/' klasorune tasi

Kotu kare olcutu (olculdu, 35 gercek cift uzerinde):
    kose sayisi <-> yeniden projeksiyon hatasi korelasyonu -0.73 / -0.78
    esik 15 -> stereo RMS 1.0025 (kaldi)
    esik 40 -> stereo RMS 0.8405 (gecer)

Silmez, TASIR — istersen geri alabilirsin.
"""
import argparse
import glob
import json
import os
import shutil
import numpy as np
import cv2

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
FRAMES = os.path.join(PROJECT_DIR, "calibration", "frames")
ELENEN = os.path.join(FRAMES, "elenen")
CFG = os.path.join(PROJECT_DIR, "data", "charuco_config.json")

MIN_KOSE_ORAN = 0.40      # maks kosenin %40'i
MIN_PARLAKLIK = 70


def kur():
    cfg = json.load(open(CFG, encoding="utf-8"))
    sq = cfg["olculen_kare_boyutu_mm"]
    mk = cfg["marker_length_mm"] * sq / cfg["square_length_mm"]
    ad = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, cfg["aruco_dict"]))
    board = cv2.aruco.CharucoBoard((cfg["squares_x"], cfg["squares_y"]),
                                   sq / 1000.0, mk / 1000.0, ad)
    board.setLegacyPattern(True)
    par = cv2.aruco.DetectorParameters()
    par.adaptiveThreshWinSizeMax = 73
    par.adaptiveThreshWinSizeStep = 2
    det = cv2.aruco.CharucoDetector(board, cv2.aruco.CharucoParameters(), par)
    maks = (cfg["squares_x"] - 1) * (cfg["squares_y"] - 1)
    return cfg, board, det, maks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uygula", action="store_true",
                    help="Kotuleri elenen/ klasorune tasi")
    args = ap.parse_args()

    cfg, board, det, maks = kur()
    min_kose = max(12, int(round(maks * MIN_KOSE_ORAN)))
    print("=" * 74)
    print("KALIBRASYON KARESI ELEME VE KAPSAMA ANALIZI")
    print("=" * 74)
    print(f"Desen {cfg['squares_x']}x{cfg['squares_y']}, maks {maks} kose")
    print(f"Esikler: ortak kose >= {min_kose}   parlaklik >= {MIN_PARLAKLIK}\n")

    K = D = None
    calib = os.path.join(PROJECT_DIR, "calibration", "calib_result.npz")
    if os.path.exists(calib):
        c = np.load(calib)
        K, D = c["K1"], c["D1"]

    kayit = []
    for lf in sorted(glob.glob(os.path.join(FRAMES, "L_*.png"))):
        num = os.path.basename(lf).replace("L_", "").replace(".png", "")
        rf = os.path.join(FRAMES, f"R_{num}.png")
        if not os.path.exists(rf):
            continue
        gl = cv2.imread(lf, cv2.IMREAD_GRAYSCALE)
        gr = cv2.imread(rf, cv2.IMREAD_GRAYSCALE)
        ccl, cil, _, _ = det.detectBoard(gl)
        ccr, cir, _, _ = det.detectBoard(gr)
        nl = 0 if ccl is None else len(ccl)
        nr = 0 if ccr is None else len(ccr)
        ortak = 0
        if cil is not None and cir is not None:
            ortak = len(np.intersect1d(cil.ravel(), cir.ravel()))
        par = (gl.mean() + gr.mean()) / 2

        # Tahtanin kadrajdaki konumu ve egimi
        kx = ky = aci = np.nan
        if ccl is not None and len(ccl) >= 6:
            pts = ccl.reshape(-1, 2)
            h, w = gl.shape
            kx = float(pts[:, 0].mean() / w)
            ky = float(pts[:, 1].mean() / h)
            if K is not None:
                op, ip = board.matchImagePoints(ccl.reshape(-1, 1, 2),
                                                cil.reshape(-1, 1))
                if op is not None and len(op) >= 6:
                    ok, rv, tv = cv2.solvePnP(op, ip, K, D)
                    if ok:
                        R, _ = cv2.Rodrigues(rv)
                        aci = float(np.degrees(np.arccos(min(1.0, abs(R[2, 2])))))
        neden = []
        if ortak < min_kose:
            neden.append(f"az kose ({ortak})")
        if par < MIN_PARLAKLIK:
            neden.append(f"karanlik ({par:.0f})")
        kayit.append(dict(num=num, nl=nl, nr=nr, ortak=ortak, par=par,
                          kx=kx, ky=ky, aci=aci, neden=neden))

    iyi = [k for k in kayit if not k["neden"]]
    kotu = [k for k in kayit if k["neden"]]

    print(f"{'kare':>5} {'SOL':>4} {'SAG':>4} {'ortak':>6} {'parlak':>7} "
          f"{'konum':>12} {'egim':>7}  durum")
    print("-" * 74)
    for k in kayit:
        konum = (f"({k['kx']:.2f},{k['ky']:.2f})"
                 if not np.isnan(k["kx"]) else "  --  ")
        aci = f"{k['aci']:5.0f}°" if not np.isnan(k["aci"]) else "   -- "
        durum = "TUT" if not k["neden"] else "ELE: " + ", ".join(k["neden"])
        print(f"{k['num']:>5} {k['nl']:4d} {k['nr']:4d} {k['ortak']:6d} "
              f"{k['par']:7.0f} {konum:>12} {aci:>7}  {durum}")

    print("-" * 74)
    print(f"  TUT: {len(iyi)} cift    ELE: {len(kotu)} cift\n")

    # --- Kapsama analizi ---
    print("=" * 74)
    print("KALAN SETIN KAPSAMASI — eksikler yeni cekimde tamamlanmali")
    print("=" * 74)
    gecerli = [k for k in iyi if not np.isnan(k["kx"])]

    print("\n  KADRAJ KAPSAMASI (3x3 bolge, tahta merkezine gore):")
    grid = np.zeros((3, 3), dtype=int)
    for k in gecerli:
        i = min(2, int(k["ky"] * 3))
        j = min(2, int(k["kx"] * 3))
        grid[i, j] += 1
    for i in range(3):
        print("    " + "  ".join(f"{grid[i, j]:3d}" for j in range(3)))
    bos = [(i, j) for i in range(3) for j in range(3) if grid[i, j] == 0]
    az = [(i, j) for i in range(3) for j in range(3) if 0 < grid[i, j] < 2]
    adlar = {(0, 0): "sol-ust", (0, 1): "orta-ust", (0, 2): "sag-ust",
             (1, 0): "sol-orta", (1, 1): "MERKEZ", (1, 2): "sag-orta",
             (2, 0): "sol-alt", (2, 1): "orta-alt", (2, 2): "sag-alt"}
    if bos:
        print(f"    BOS bolgeler : {', '.join(adlar[b] for b in bos)}")
    if az:
        print(f"    Zayif (1 kare): {', '.join(adlar[a] for a in az)}")
    if not bos and not az:
        print("    Tum bolgeler yeterli.")

    if any(not np.isnan(k["aci"]) for k in gecerli):
        aci = [k["aci"] for k in gecerli if not np.isnan(k["aci"])]
        print(f"\n  EGIM DAGILIMI (0° = tahta kameraya tam dik):")
        bantlar = [(0, 15, "neredeyse duz"), (15, 30, "hafif egik"),
                   (30, 45, "iyi egik"), (45, 90, "cok egik")]
        for lo, hi, ad in bantlar:
            n = sum(1 for a in aci if lo <= a < hi)
            cubuk = "#" * n
            print(f"    {lo:2d}-{hi:2d}° {ad:<15} {n:3d}  {cubuk}")
        if sum(1 for a in aci if a >= 30) < 5:
            print("    UYARI: 30°+ egik kare AZ. Duz tutulan tahtalar fx ile")
            print("           mesafeyi ayirt edemez — kalibrasyon zayif kalir.")

    print(f"\n  ORTAK KOSE: ort {np.mean([k['ortak'] for k in iyi]):.0f}, "
          f"en dusuk {min(k['ortak'] for k in iyi)}, "
          f"en yuksek {max(k['ortak'] for k in iyi)}  (maks {maks})")
    print(f"  PARLAKLIK : ort {np.mean([k['par'] for k in iyi]):.0f}, "
          f"aralik {min(k['par'] for k in iyi):.0f}-"
          f"{max(k['par'] for k in iyi):.0f}")

    # --- Tasima ---
    print()
    print("=" * 74)
    if not args.uygula:
        print(f"ANALIZ MODU — hicbir dosya tasinmadi.")
        print(f"Uygulamak icin:  .\\calistir.ps1 yedekle -- --uygula")
    elif not kotu:
        print("Elenecek kare yok.")
    else:
        os.makedirs(ELENEN, exist_ok=True)
        n = 0
        for k in kotu:
            for onek in ("L", "R"):
                s = os.path.join(FRAMES, f"{onek}_{k['num']}.png")
                if os.path.exists(s):
                    shutil.move(s, os.path.join(ELENEN, f"{onek}_{k['num']}.png"))
                    n += 1
        print(f"{n} dosya ({len(kotu)} cift) tasindi -> {ELENEN}")
        print("SILINMEDI — geri almak istersen oradan geri tasi.")
        print(f"\nKalan: {len(iyi)} cift. Yeni kare ekleyip tekrar kalibre et.")


if __name__ == "__main__":
    main()
