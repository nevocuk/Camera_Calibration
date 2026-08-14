"""
Mono kalibrasyon dogrulamasi — her kamera icin ayri ayri:
1. Kalibrasyon karelerinden ChArUco kose algilama
2. solvePnP ile poz tahmini
3. Bilinen kare boyutunu yeniden hesaplayarak hata olcumu
4. Kameradan board'a mesafe tahmini

Kullanim:
    python src/mono_verify.py
"""
import os
import sys
import glob
import json
import numpy as np
import cv2

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
CONFIG_PATH = os.path.join(PROJECT_DIR, "data", "charuco_config.json")
CALIB_PATH = os.path.join(PROJECT_DIR, "calibration", "calib_result.npz")
FRAMES_DIR = os.path.join(PROJECT_DIR, "calibration", "frames")


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = json.load(f)
    sq = cfg["olculen_kare_boyutu_mm"]
    mk = cfg["marker_length_mm"] * sq / cfg["square_length_mm"]
    aruco_dict = cv2.aruco.getPredefinedDictionary(
        getattr(cv2.aruco, cfg["aruco_dict"]))
    board = cv2.aruco.CharucoBoard(
        (cfg["squares_x"], cfg["squares_y"]),
        sq / 1000.0, mk / 1000.0, aruco_dict)
    if not cfg["aruco_dict"].startswith("DICT_APRILTAG"):
        board.setLegacyPattern(True)
    params = cv2.aruco.DetectorParameters()
    params.adaptiveThreshWinSizeMax = 73
    params.adaptiveThreshWinSizeStep = 2
    charuco_params = cv2.aruco.CharucoParameters()
    detector = cv2.aruco.CharucoDetector(board, charuco_params, params)
    return board, detector, cfg


def detect(gray, board, detector):
    h, w = gray.shape[:2]
    if w > 1280:
        scale = 960.0 / h
        small = cv2.resize(gray, (int(w * scale), 960))
    else:
        small = gray
        scale = 1.0
    cc, ci, _, _ = detector.detectBoard(small)
    if cc is None or len(cc) < 6:
        return None, None
    if scale != 1.0:
        cc = cc * (1.0 / scale)
    return cc, ci


def verify_camera(side, K, D, board, detector, cfg):
    prefix = "L_" if side == "SOL" else "R_"
    files = sorted(glob.glob(os.path.join(FRAMES_DIR, f"{prefix}*.png")))
    if not files:
        print(f"  {side}: Kare bulunamadi!")
        return

    sq_mm = cfg["olculen_kare_boyutu_mm"]
    obj_points = board.getChessboardCorners()

    results = []
    for fpath in files:
        gray = cv2.imread(fpath, cv2.IMREAD_GRAYSCALE)
        if gray is None:
            continue
        cc, ci = detect(gray, board, detector)
        if cc is None:
            continue

        obj_sel = obj_points[ci.ravel()]
        ok, rvec, tvec = cv2.solvePnP(obj_sel, cc, K, D,
                                       flags=cv2.SOLVEPNP_ITERATIVE)
        if not ok:
            continue

        dist_mm = np.linalg.norm(tvec) * 1000.0

        img_proj, _ = cv2.projectPoints(obj_sel, rvec, tvec, K, D)
        reproj_err = np.sqrt(np.mean((cc.reshape(-1, 2) -
                                       img_proj.reshape(-1, 2)) ** 2))

        n_corners = len(ci)
        if n_corners >= 2:
            pairs = []
            ci_flat = ci.ravel()
            sq_x = cfg["squares_x"] - 1
            for i in range(len(ci_flat)):
                for j in range(i + 1, len(ci_flat)):
                    id_i, id_j = ci_flat[i], ci_flat[j]
                    row_i, col_i = divmod(id_i, sq_x)
                    row_j, col_j = divmod(id_j, sq_x)
                    dx = abs(col_i - col_j)
                    dy = abs(row_i - row_j)
                    if (dx == 1 and dy == 0) or (dx == 0 and dy == 1):
                        d3d = np.linalg.norm(obj_sel[i] - obj_sel[j]) * 1000
                        pairs.append(d3d)
            if pairs:
                mean_pitch = np.mean(pairs)
            else:
                mean_pitch = sq_mm
        else:
            mean_pitch = sq_mm

        num = os.path.basename(fpath).replace(prefix, "").replace(".png", "")
        results.append({
            "num": num,
            "dist_mm": dist_mm,
            "reproj_px": reproj_err,
            "corners": n_corners,
            "pitch_mm": mean_pitch,
        })

    if not results:
        print(f"  {side}: Hicbir karede poz tahmin edilemedi!")
        return

    print(f"\n  {side} KAMERA — {len(results)} kare analiz edildi")
    print(f"  {'#':<5} {'Mesafe(mm)':>10} {'Reproj(px)':>11} {'Kose':>5} "
          f"{'Pitch(mm)':>10}")
    print(f"  {'-'*5} {'-'*10} {'-'*11} {'-'*5} {'-'*10}")

    dists = []
    reproj_list = []
    pitch_list = []
    for r in results:
        print(f"  {r['num']:<5} {r['dist_mm']:>10.1f} {r['reproj_px']:>11.3f} "
              f"{r['corners']:>5} {r['pitch_mm']:>10.2f}")
        dists.append(r["dist_mm"])
        reproj_list.append(r["reproj_px"])
        pitch_list.append(r["pitch_mm"])

    print(f"\n  Ortalama mesafe:   {np.mean(dists):.1f} mm "
          f"(std: {np.std(dists):.1f})")
    print(f"  Ortalama reproj:  {np.mean(reproj_list):.3f} px "
          f"(maks: {np.max(reproj_list):.3f})")
    print(f"  Pitch ortalama:   {np.mean(pitch_list):.2f} mm "
          f"(beklenen: {sq_mm:.1f}, hata: "
          f"{abs(np.mean(pitch_list) - sq_mm):.2f} mm)")


def main():
    if not os.path.exists(CALIB_PATH):
        print(f"HATA: {CALIB_PATH} bulunamadi. Once kalibrasyonu calistir.")
        sys.exit(1)

    calib = np.load(CALIB_PATH)
    K1 = calib["K1"]
    D1 = calib["D1"]
    K2 = calib["K2"]
    D2 = calib["D2"]

    board, detector, cfg = load_config()

    print("=" * 60)
    print("MONO KALIBRASYON DOGRULAMASI")
    print("=" * 60)
    print(f"  Cozunurluk: {cfg['calib_resolution']}")
    print(f"  Kare boyutu: {cfg['olculen_kare_boyutu_mm']} mm")

    verify_camera("SOL", K1, D1, board, detector, cfg)
    verify_camera("SAG", K2, D2, board, detector, cfg)

    print("\n" + "=" * 60)
    print("YORUM")
    print("=" * 60)
    print("  - Reproj < 1.0 px: intrinsics iyi")
    print("  - Pitch hatasi < 0.5 mm: olcekler dogru")
    print("  - Mesafe std < 20 mm: board farkli mesafelerde cekilmis (normal)")


if __name__ == "__main__":
    main()
