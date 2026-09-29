"""Epipolar hatayi TUM kalibrasyon ciftleri uzerinde yeniden olc.

`calibration.py` bu degeri yalnizca ilk BES cift uzerinden hesaplayip
ekrana basar (`used_pairs[:5]`). Rapora giren sayi ise tum setin
ortalamasi olmali - bes kare orneklem olarak az ve hangi bes kare
oldugu cekim sirasina bagli.

Cikti: ortalama, medyan, %95'lik dilim, 1 pikselin ustundeki kose
orani ve kac cift / kac kose uzerinden hesaplandigi.

Kullanim:
    python src/epipolar_dogrula.py
    python src/epipolar_dogrula.py --kareler calibration/frames_set_3_20260816_2048x1536
"""
from __future__ import annotations

import argparse
import glob
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import calibration as kal

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kareler",
                    default=os.path.join(KOK, "calibration", "frames"))
    ap.add_argument("--kalib",
                    default=os.path.join(KOK, "calibration",
                                         "calib_result.npz"))
    a = ap.parse_args()

    c = np.load(a.kalib)
    K1, D1, R1, P1 = c["K1"], c["D1"], c["R1"], c["P1"]
    K2, D2, R2, P2 = c["K2"], c["D2"], c["R2"], c["P2"]
    boyut = tuple(int(x) for x in c["image_size"])

    board, detector, _ = kal.load_config()
    m1x, m1y = cv2.initUndistortRectifyMap(K1, D1, R1, P1, boyut,
                                           cv2.CV_32FC1)
    m2x, m2y = cv2.initUndistortRectifyMap(K2, D2, R2, P2, boyut,
                                           cv2.CV_32FC1)

    hatalar, kullanilan, atlanan = [], 0, 0
    for sol in sorted(glob.glob(os.path.join(a.kareler, "L_*.png"))):
        sag = sol.replace(os.sep + "L_", os.sep + "R_")
        if not os.path.exists(sag):
            continue
        gl = cv2.imread(sol, cv2.IMREAD_GRAYSCALE)
        gr = cv2.imread(sag, cv2.IMREAD_GRAYSCALE)
        if gl is None or gr is None:
            continue
        rl = cv2.remap(gl, m1x, m1y, cv2.INTER_LINEAR)
        rr = cv2.remap(gr, m2x, m2y, cv2.INTER_LINEAR)

        cl, il = kal.detect_corners(rl, board, detector)
        cr, ir = kal.detect_corners(rr, board, detector)
        if cl is None or cr is None:
            atlanan += 1
            continue
        fl, _, fr, _, _ = kal._filter_common_markers(cl, il, cr, ir, False)
        if fl is None:
            atlanan += 1
            continue
        pl = np.array(fl).reshape(-1, 2)
        pr = np.array(fr).reshape(-1, 2)
        hatalar.extend(np.abs(pl[:, 1] - pr[:, 1]).tolist())
        kullanilan += 1

    if not hatalar:
        print("Hicbir ciftte ortak kose bulunamadi.")
        return 1

    h = np.array(hatalar)
    print(f"Kare klasoru : {os.path.relpath(a.kareler, KOK)}")
    print(f"Kullanilan   : {kullanilan} cift, {len(h)} kose "
          f"({atlanan} cift atlandi)")
    print()
    print(f"  Ortalama          : {h.mean():.3f} px")
    print(f"  Medyan            : {np.median(h):.3f} px")
    print(f"  %95'lik dilim     : {np.percentile(h, 95):.3f} px")
    print(f"  Maksimum          : {h.max():.3f} px")
    print(f"  1 px ustu kose    : %{100 * (h > 1).mean():.1f}")
    print()
    print("Rapora bu ortalamanin yazilmasi gerekir; calibration.py'nin")
    print("ekrana bastigi deger yalnizca ilk bes cifte aittir.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
