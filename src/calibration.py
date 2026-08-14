"""
Stereo kalibrasyon — calibration/frames/ altindaki L_xxx.png ve R_xxx.png
ciftlerinden K, D, R, T, Q matrislerini hesaplar.

Kullanim:
    python src/calibration.py [--frames calibration/frames] [--out calibration/calib_result.npz]

Cikti:
    calibration/calib_result.npz  (K1, D1, K2, D2, R, T, E, F, Q, image_size, rms)
"""
import os
import sys
import glob
import json
import argparse
import numpy as np
import cv2

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
CONFIG_PATH = os.path.join(PROJECT_DIR, "data", "charuco_config.json")
DIARY_PATH = os.path.join(PROJECT_DIR, "data", "olcum_defteri.csv")


def _grid_custom_ids(cols, rows):
    """calib.io AprilTag board ID mapping: ID = (cols-1-col)*rows + row."""
    return np.array([(cols - 1 - c) * rows + r
                     for r in range(rows) for c in range(cols)], dtype=np.int32)


def _grid_id_to_center(mid, cols, rows, pitch_m, mk_m):
    """calib.io marker ID -> nesne uzayi merkez koordinati (metre)."""
    col = (cols - 1) - mid // rows
    row = mid % rows
    return np.array([col * pitch_m + mk_m / 2.0,
                     row * pitch_m + mk_m / 2.0, 0], dtype=np.float32)


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = json.load(f)

    sq = cfg.get("olculen_kare_boyutu_mm")
    if sq is None:
        print("=" * 60)
        print("HATA: Basili desen kumpasla olculmedmis!")
        print("charuco_config.json -> olculen_kare_boyutu_mm doldurulmali.")
        print("Kumpasla 3-4 kareyi olc, ortalamayi yaz.")
        print("=" * 60)
        sys.exit(1)

    mk = cfg["marker_length_mm"] * sq / cfg["square_length_mm"]
    aruco_dict = cv2.aruco.getPredefinedDictionary(
        getattr(cv2.aruco, cfg["aruco_dict"]))
    board_type = cfg.get("board_type", "charuco")

    if board_type == "grid":
        cols, rows = cfg["squares_x"], cfg["squares_y"]
        ids_arr = _grid_custom_ids(cols, rows)
        sep = (sq - mk) / 1000.0
        board = cv2.aruco.GridBoard(
            (cols, rows), mk / 1000.0, sep, aruco_dict, ids_arr)
        params = cv2.aruco.DetectorParameters()
        if cfg["aruco_dict"].startswith("DICT_APRILTAG"):
            params.adaptiveThreshWinSizeMax = 73
            params.adaptiveThreshWinSizeStep = 2
        detector = cv2.aruco.ArucoDetector(aruco_dict, params)
    else:
        board = cv2.aruco.CharucoBoard(
            (cfg["squares_x"], cfg["squares_y"]),
            sq / 1000.0, mk / 1000.0, aruco_dict)
        use_legacy = not cfg["aruco_dict"].startswith("DICT_APRILTAG")
        if use_legacy:
            board.setLegacyPattern(True)
        params = cv2.aruco.DetectorParameters()
        params.adaptiveThreshWinSizeMax = 73
        params.adaptiveThreshWinSizeStep = 2
        charuco_params = cv2.aruco.CharucoParameters()
        detector = cv2.aruco.CharucoDetector(board, charuco_params,
                                              params)

    return board, detector, cfg


def detect_corners(gray, board, detector):
    h, w = gray.shape[:2]
    if w > 1280:
        scale = 960.0 / h
        small = cv2.resize(gray, (int(w * scale), 960))
    else:
        small = gray
        scale = 1.0
    if isinstance(detector, cv2.aruco.ArucoDetector):
        corners, ids, _ = detector.detectMarkers(small)
        if ids is None or len(ids) < 4:
            return None, None
        if scale != 1.0:
            corners = tuple(c / scale for c in corners)
        return corners, ids
    else:
        charuco_corners, charuco_ids, _, _ = detector.detectBoard(small)
        if charuco_corners is None or len(charuco_corners) < 6:
            return None, None
        if scale != 1.0:
            charuco_corners = charuco_corners / scale
        return charuco_corners, charuco_ids


def _filter_common_markers(cc_l, ci_l, cc_r, ci_r, is_grid):
    """Her iki kamerada da gorunen marker/kose ID'lerini filtrele ve sirala.
    Grid modunda marker merkezlerini hesaplar (4 kosenin ortalamasi)."""
    common_ids = np.intersect1d(ci_l.ravel(), ci_r.ravel())
    min_count = 4 if is_grid else 6
    if len(common_ids) < min_count:
        return None, None, None, None, common_ids

    mask_l = np.isin(ci_l.ravel(), common_ids)
    mask_r = np.isin(ci_r.ravel(), common_ids)

    if is_grid:
        centers_l = np.array([c[0].mean(axis=0) for c, m in zip(cc_l, mask_l) if m],
                             dtype=np.float32)
        centers_r = np.array([c[0].mean(axis=0) for c, m in zip(cc_r, mask_r) if m],
                             dtype=np.float32)
        fi_l = ci_l[mask_l]
        fi_r = ci_r[mask_r]
        order_l = np.argsort(fi_l.ravel())
        order_r = np.argsort(fi_r.ravel())
        filt_l = centers_l[order_l].reshape(-1, 1, 2)
        filt_r = centers_r[order_r].reshape(-1, 1, 2)
        fi_l = fi_l[order_l]
        fi_r = fi_r[order_r]
    else:
        filt_l = cc_l[mask_l]
        fi_l = ci_l[mask_l]
        filt_r = cc_r[mask_r]
        fi_r = ci_r[mask_r]
        order_l = np.argsort(fi_l.ravel())
        order_r = np.argsort(fi_r.ravel())
        filt_l = filt_l[order_l]
        fi_l = fi_l[order_l]
        filt_r = filt_r[order_r]
        fi_r = fi_r[order_r]

    return filt_l, fi_l, filt_r, fi_r, common_ids


def collect_frames(frames_dir, board, detector, cfg=None):
    left_files = sorted(glob.glob(os.path.join(frames_dir, "L_*.png")))
    if not left_files:
        print(f"HATA: {frames_dir} altinda L_*.png bulunamadi.")
        sys.exit(1)

    all_corners_l = []
    all_corners_r = []
    all_ids_l = []
    all_ids_r = []
    used_pairs = []
    skipped = []
    image_size = None
    calib_res = cfg.get("calib_resolution") if cfg else None
    is_grid = isinstance(detector, cv2.aruco.ArucoDetector)

    print(f"\n{len(left_files)} kare cifti taraniyor...\n")

    for lf in left_files:
        name = os.path.basename(lf)
        num = name.replace("L_", "").replace(".png", "")
        rf = os.path.join(os.path.dirname(lf), f"R_{num}.png")
        if not os.path.exists(rf):
            skipped.append((num, "sag kare yok"))
            continue

        img_l = cv2.imread(lf, cv2.IMREAD_GRAYSCALE)
        img_r = cv2.imread(rf, cv2.IMREAD_GRAYSCALE)
        if img_l is None or img_r is None:
            skipped.append((num, "okunamadi"))
            continue

        if image_size is None:
            image_size = (img_l.shape[1], img_l.shape[0])
            if calib_res and list(image_size) != calib_res:
                print(f"HATA: Kare boyutu {image_size[0]}x{image_size[1]}, "
                      f"beklenen {calib_res[0]}x{calib_res[1]}")
                print("charuco_config.json -> calib_resolution ile uyusmali.")
                sys.exit(1)

        if (img_l.shape[1], img_l.shape[0]) != image_size:
            skipped.append((num, f"boyut uyumsuz {img_l.shape[1]}x{img_l.shape[0]}"))
            continue

        cc_l, ci_l = detect_corners(img_l, board, detector)
        cc_r, ci_r = detect_corners(img_r, board, detector)

        if cc_l is None or cc_r is None:
            skipped.append((num, "yetersiz kose"))
            continue

        filt_l, fi_l, filt_r, fi_r, common_ids = _filter_common_markers(
            cc_l, ci_l, cc_r, ci_r, is_grid)
        if filt_l is None:
            label = "marker" if is_grid else "kose"
            skipped.append((num, f"ortak {label} az ({len(common_ids)})"))
            continue

        all_corners_l.append(filt_l)
        all_corners_r.append(filt_r)
        all_ids_l.append(fi_l)
        all_ids_r.append(fi_r)
        used_pairs.append(num)

        avg_bright = (img_l.mean() + img_r.mean()) / 2
        n_common = len(common_ids)
        label = "marker" if is_grid else "kose"

        min_markers = 15
        min_bright = 40
        skip_reason = None
        if avg_bright < min_bright:
            skip_reason = "KARANLIK"
        elif n_common < min_markers:
            skip_reason = "AZ MARKER"

        if skip_reason:
            print(f"  #{num}: {n_common} ortak {label}, "
                  f"parlaklik={avg_bright:.0f} [{skip_reason} - ELENDI]")
            all_corners_l.pop()
            all_corners_r.pop()
            all_ids_l.pop()
            all_ids_r.pop()
            used_pairs.pop()
            skipped.append((num, skip_reason.lower()))
            continue

        status = "OK"
        print(f"  #{num}: {n_common} ortak {label}, "
              f"parlaklik={avg_bright:.0f} [{status}]")

    if skipped:
        print(f"\nAtlanan: {len(skipped)}")
        for num, reason in skipped:
            print(f"  #{num}: {reason}")

    print(f"\nKullanilabilir: {len(used_pairs)} / {len(left_files)} cift")

    if len(used_pairs) < 10:
        print("\nUYARI: 10'dan az gecerli cift. Kalibrasyon guvenilir olmayabilir.")
        print("En az 25-40 cift onerilir.")
    if len(used_pairs) < 5:
        print("HATA: 5'ten az gecerli cift. Kalibrasyon yapilamaz.")
        sys.exit(1)

    return all_corners_l, all_corners_r, all_ids_l, all_ids_r, used_pairs, image_size


def calibrate_single(board, corners_list, ids_list, image_size, name, cfg=None):
    obj_points = []
    img_points = []
    is_grid = isinstance(board, cv2.aruco.GridBoard)
    for cc, ci in zip(corners_list, ids_list):
        if is_grid:
            cols, rows = cfg["squares_x"], cfg["squares_y"]
            sq = cfg["olculen_kare_boyutu_mm"]
            mk_mm = cfg["marker_length_mm"] * sq / cfg["square_length_mm"]
            pitch_m = sq / 1000.0
            mk_m = mk_mm / 1000.0
            op = np.array([_grid_id_to_center(int(m), cols, rows, pitch_m, mk_m)
                           for m in ci.ravel()], dtype=np.float32).reshape(-1, 1, 3)
            ip = cc.reshape(-1, 1, 2).astype(np.float32)
        else:
            op, ip = board.matchImagePoints(
                cc.reshape(-1, 1, 2), ci.reshape(-1, 1))
        if op is not None:
            obj_points.append(op)
            img_points.append(ip)

    rms, K, D, rvecs, tvecs = cv2.calibrateCamera(
        obj_points, img_points, image_size, None, None)

    print(f"\n  {name} intrinsics:")
    print(f"    fx={K[0,0]:.1f}  fy={K[1,1]:.1f}  cx={K[0,2]:.1f}  cy={K[1,2]:.1f}")
    print(f"    RMS = {rms:.4f} px")
    return K, D, obj_points, img_points, rms


def calibrate_stereo(board, corners_l, corners_r, ids_l, ids_r, image_size, cfg=None):
    print("\n" + "=" * 50)
    print("ADIM 1: Tekli kalibrasyon")
    print("=" * 50)

    K1, D1, obj_pts, img_pts_l, rms1 = calibrate_single(
        board, corners_l, ids_l, image_size, "SOL", cfg)
    K2, D2, _, img_pts_r, rms2 = calibrate_single(
        board, corners_r, ids_r, image_size, "SAG", cfg)

    print("\n" + "=" * 50)
    print("ADIM 2: Stereo kalibrasyon (CALIB_FIX_INTRINSIC)")
    print("=" * 50)

    flags = cv2.CALIB_FIX_INTRINSIC
    criteria = (cv2.TERM_CRITERIA_MAX_ITER + cv2.TERM_CRITERIA_EPS,
                100, 1e-6)

    rms, K1, D1, K2, D2, R, T, E, F = cv2.stereoCalibrate(
        obj_pts, img_pts_l, img_pts_r,
        K1, D1, K2, D2, image_size,
        criteria=criteria, flags=flags)

    baseline_mm = np.linalg.norm(T) * 1000
    print(f"\n  Stereo RMS = {rms:.4f} px")
    print(f"  Baseline ||T|| = {baseline_mm:.1f} mm")

    is_grid = isinstance(board, cv2.aruco.GridBoard)
    base_limit = 1.0 if is_grid else 0.4
    rms_limit = base_limit * (image_size[0] / 960.0)
    if rms > rms_limit:
        print(f"\n  UYARI: RMS ({rms:.4f}) hedefin ({rms_limit}) ustunde!")
        print("  Olasi nedenler:")
        print("    - Bazi karelerde hareket bulanikligi")
        print("    - Desen duz degil (kivrik kagit)")
        print("    - Kamera montaji oynamis")
        print("    - Yetersiz kose sayisi")
    else:
        print(f"\n  RMS {rms:.4f} < {rms_limit} — BASARILI")

    print("\n" + "=" * 50)
    print("ADIM 3: Rektifikasyon (stereoRectify)")
    print("=" * 50)

    R1, R2, P1, P2, Q, roi1, roi2 = cv2.stereoRectify(
        K1, D1, K2, D2, image_size, R, T,
        flags=cv2.CALIB_ZERO_DISPARITY, alpha=0)

    print(f"  ROI sol: {roi1}")
    print(f"  ROI sag: {roi2}")

    return {
        "K1": K1, "D1": D1,
        "K2": K2, "D2": D2,
        "R": R, "T": T, "E": E, "F": F,
        "R1": R1, "R2": R2, "P1": P1, "P2": P2, "Q": Q,
        "roi1": np.array(roi1), "roi2": np.array(roi2),
        "image_size": np.array(image_size),
        "rms": rms, "rms1": rms1, "rms2": rms2,
        "baseline_mm": baseline_mm,
    }


def verify_rectification(frames_dir, result, board, detector, used_pairs):
    print("\n" + "=" * 50)
    print("ADIM 4: Rektifikasyon dogrulamasi")
    print("=" * 50)

    K1, D1, K2, D2 = result["K1"], result["D1"], result["K2"], result["D2"]
    R1, R2, P1, P2 = result["R1"], result["R2"], result["P1"], result["P2"]
    image_size = tuple(result["image_size"])

    map1x, map1y = cv2.initUndistortRectifyMap(K1, D1, R1, P1, image_size, cv2.CV_32FC1)
    map2x, map2y = cv2.initUndistortRectifyMap(K2, D2, R2, P2, image_size, cv2.CV_32FC1)

    errors = []
    for num in used_pairs[:5]:
        lf = os.path.join(frames_dir, f"L_{num}.png")
        rf = os.path.join(frames_dir, f"R_{num}.png")
        img_l = cv2.imread(lf, cv2.IMREAD_GRAYSCALE)
        img_r = cv2.imread(rf, cv2.IMREAD_GRAYSCALE)

        rect_l = cv2.remap(img_l, map1x, map1y, cv2.INTER_LINEAR)
        rect_r = cv2.remap(img_r, map2x, map2y, cv2.INTER_LINEAR)

        cc_l, ci_l = detect_corners(rect_l, board, detector)
        cc_r, ci_r = detect_corners(rect_r, board, detector)
        if cc_l is None or cc_r is None:
            continue

        is_grid = isinstance(detector, cv2.aruco.ArucoDetector)
        filt_l, fi_l, filt_r, fi_r, common = _filter_common_markers(
            cc_l, ci_l, cc_r, ci_r, is_grid)
        if filt_l is None:
            continue

        pts_l = np.array(filt_l).reshape(-1, 2)
        pts_r = np.array(filt_r).reshape(-1, 2)
        yl = pts_l[:, 1]
        yr = pts_r[:, 1]
        err = np.abs(yl - yr)
        errors.extend(err.tolist())

    if errors:
        mean_err = np.mean(errors)
        max_err = np.max(errors)
        print(f"  Epipolar y-hatasi (rektifiye sonrasi):")
        print(f"    Ortalama: {mean_err:.3f} px")
        print(f"    Maksimum: {max_err:.3f} px")
        if mean_err > 1.0:
            print("  UYARI: Ortalama hata 1 px'i asiyor!")
        else:
            print("  Epipolar hizalama BASARILI")
    else:
        print("  Rektifiye karelerde kose bulunamadi, dogrulama atlandi")


def save_results(out_path, result):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    np.savez(out_path, **result)
    print(f"\nSonuclar kaydedildi: {out_path}")


def append_diary(result):
    import datetime
    os.makedirs(os.path.dirname(DIARY_PATH), exist_ok=True)
    exists = os.path.exists(DIARY_PATH)
    with open(DIARY_PATH, "a", encoding="utf-8") as f:
        if not exists:
            f.write("tarih,saat,asama,not1,not2,deger,birim\n")
        now = datetime.datetime.now()
        date = now.strftime("%Y-%m-%d")
        time = now.strftime("%H:%M")
        f.write(f"{date},{time},kalibrasyon,RMS_stereo,,"
                f"{result['rms']:.4f},px\n")
        f.write(f"{date},{time},kalibrasyon,RMS_sol,,"
                f"{result['rms1']:.4f},px\n")
        f.write(f"{date},{time},kalibrasyon,RMS_sag,,"
                f"{result['rms2']:.4f},px\n")
        f.write(f"{date},{time},kalibrasyon,baseline,,"
                f"{result['baseline_mm']:.1f},mm\n")
        f.write(f"{date},{time},kalibrasyon,fx_sol,,"
                f"{result['K1'][0,0]:.1f},px\n")
        f.write(f"{date},{time},kalibrasyon,fx_sag,,"
                f"{result['K2'][0,0]:.1f},px\n")
    print(f"Olcum defterine yazildi: {DIARY_PATH}")


def print_summary(result):
    print("\n" + "=" * 50)
    print("OZET")
    print("=" * 50)
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg_tmp = json.load(f)
    base_limit = 1.0 if cfg_tmp.get("board_type") == "grid" else 0.4
    img_w = result.get("image_size", (960,))[0]
    rms_limit = base_limit * (img_w / 960.0)
    rms_ok = result["rms"] < rms_limit
    print(f"  Stereo RMS:  {result['rms']:.4f} px "
          f"{'BASARILI' if rms_ok else 'YETERSIZ'} (esik: {rms_limit})")
    print(f"  Sol RMS:     {result['rms1']:.4f} px")
    print(f"  Sag RMS:     {result['rms2']:.4f} px")
    print(f"  Baseline:    {result['baseline_mm']:.1f} mm")
    print(f"  fx (sol):    {result['K1'][0,0]:.1f} px")
    print(f"  fx (sag):    {result['K2'][0,0]:.1f} px")
    print()
    print("  Kumpasla olctugun baseline ile ||T|| degerini karsilastir.")
    print("  %5'ten fazla fark varsa kalibrasyonda sorun olabilir.")
    print()
    b = result["baseline_mm"]
    f = result["K1"][0, 0]
    dd = 0.35
    for z in [300, 500, 700, 900]:
        dz = z**2 * dd / (f * b)
        print(f"  Z={z:4d} mm -> deltaZ = {dz:.2f} mm")


def main():
    p = argparse.ArgumentParser(description="Stereo kalibrasyon")
    p.add_argument("--frames", default=os.path.join(PROJECT_DIR, "calibration", "frames"))
    p.add_argument("--out", default=os.path.join(PROJECT_DIR, "calibration", "calib_result.npz"))
    args = p.parse_args()

    board, detector, cfg = load_config()
    corners_l, corners_r, ids_l, ids_r, used, image_size = collect_frames(
        args.frames, board, detector, cfg)
    result = calibrate_stereo(board, corners_l, corners_r, ids_l, ids_r, image_size, cfg)
    verify_rectification(args.frames, result, board, detector, used)
    save_results(args.out, result)
    append_diary(result)
    print_summary(result)


if __name__ == "__main__":
    main()
