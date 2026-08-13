"""
Zemin duzlemi tespiti — ChArUco'yu masaya yatir, bir kare cek,
duzlem denklemini kaydet.

Kullanim:
    python src/ground_plane.py [--left 1] [--right 2]

Adimlar:
    1. Kameralari acar, canli gosterir
    2. ChArUco masada gorunuyorken SPACE ile cek
    3. solvePnP ile duzlem normal + d hesaplar
    4. calibration/ground_plane.npz olarak kaydeder

On kosul: calibration/calib_result.npz mevcut olmali.
"""
import os
import sys
import json
import argparse
import numpy as np
import cv2
from PIL import Image, ImageTk

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
CALIB_PATH = os.path.join(PROJECT_DIR, "calibration", "calib_result.npz")
CONFIG_PATH = os.path.join(PROJECT_DIR, "data", "charuco_config.json")
OUT_PATH = os.path.join(PROJECT_DIR, "calibration", "ground_plane.npz")


def load_calib():
    if not os.path.exists(CALIB_PATH):
        print("HATA: Kalibrasyon dosyasi bulunamadi!")
        print(f"  Beklenen: {CALIB_PATH}")
        print("  Once calibration.py calistirilmali.")
        sys.exit(1)
    data = np.load(CALIB_PATH)
    return data


def load_charuco():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = json.load(f)
    sq = cfg.get("olculen_kare_boyutu_mm")
    if sq is None:
        print("HATA: olculen_kare_boyutu_mm doldurulmamis!")
        sys.exit(1)
    mk = cfg["marker_length_mm"] * sq / cfg["square_length_mm"]
    aruco_dict = cv2.aruco.getPredefinedDictionary(
        getattr(cv2.aruco, cfg["aruco_dict"]))
    board_type = cfg.get("board_type", "charuco")

    if board_type == "grid":
        cols, rows = cfg["squares_x"], cfg["squares_y"]
        ids_arr = np.array([(cols - 1 - c) * rows + r
                            for r in range(rows) for c in range(cols)],
                           dtype=np.int32)
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
        detector = cv2.aruco.CharucoDetector(board)
    return board, detector


def detect_and_solve(gray, board, detector, K, D):
    is_grid = isinstance(detector, cv2.aruco.ArucoDetector)

    if is_grid:
        corners, ids, _ = detector.detectMarkers(gray)
        if ids is None or len(ids) < 4:
            return None, None, None, 0
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
        cols, rows = cfg["squares_x"], cfg["squares_y"]
        sq = cfg.get("olculen_kare_boyutu_mm") or cfg["square_length_mm"]
        mk_mm = cfg["marker_length_mm"] * sq / cfg["square_length_mm"]
        pitch_m, mk_m = sq / 1000.0, mk_mm / 1000.0
        obj_pts = np.array([
            [(cols - 1 - int(m) // rows) * pitch_m + mk_m / 2.0,
             (int(m) % rows) * pitch_m + mk_m / 2.0, 0]
            for m in ids.ravel()], dtype=np.float32)
        img_pts = np.array([c[0].mean(axis=0) for c in corners],
                           dtype=np.float32)
        n_detected = len(ids)
    else:
        cc, ci, _, _ = detector.detectBoard(gray)
        if cc is None or len(cc) < 6:
            return None, None, None, 0
        obj_pts, img_pts = board.matchImagePoints(cc, ci)
        n_detected = len(cc)

    if obj_pts is None:
        return None, None, None, n_detected

    success, rvec, tvec = cv2.solvePnP(
        obj_pts.reshape(-1, 1, 3), img_pts.reshape(-1, 1, 2),
        K, D, flags=cv2.SOLVEPNP_ITERATIVE)
    if not success:
        return None, None, None, n_detected

    R_mat, _ = cv2.Rodrigues(rvec)
    normal = R_mat[:, 2]
    if normal[2] > 0:
        normal = -normal
    point_on_plane = tvec.ravel()
    d = -np.dot(normal, point_on_plane)

    display_pts = img_pts.reshape(-1, 2)
    return normal, d, display_pts if is_grid else cc, n_detected


def main():
    p = argparse.ArgumentParser(description="Zemin duzlemi tespiti")
    p.add_argument("--left", type=int, default=1)
    p.add_argument("--right", type=int, default=2)
    args = p.parse_args()

    calib = load_calib()
    K1 = calib["K1"]
    D1 = calib["D1"]
    board, detector = load_charuco()

    image_size = tuple(calib["image_size"])
    w, h = image_size

    cap = cv2.VideoCapture(args.left, cv2.CAP_MSMF)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)

    print("=" * 50)
    print("ZEMIN DUZLEMI TESPITI")
    print("=" * 50)
    print()
    print("ChArUco desenini masaya/zemine DUZGUN yatir.")
    print("Desen kamerada gorunuyorken SPACE tusuna bas.")
    print("ESC ile cikis.")
    print()

    saved = False

    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        normal, d, cc, n_corners = detect_and_solve(
            gray, board, detector, K1, D1)

        display = frame.copy()
        if cc is not None:
            for pt in cc:
                cv2.circle(display, tuple(pt.ravel().astype(int)),
                           5, (0, 255, 0), -1)

        status = f"Kose: {n_corners}"
        if normal is not None:
            angle = np.degrees(np.arccos(abs(normal[2])))
            status += f" | Aci: {angle:.1f} derece"
            if angle < 10:
                status += " | UYGUN"
                cv2.rectangle(display, (0, 0),
                              (display.shape[1]-1, display.shape[0]-1),
                              (0, 255, 0), 3)
            else:
                status += " | EGIK — duzelt"
                cv2.rectangle(display, (0, 0),
                              (display.shape[1]-1, display.shape[0]-1),
                              (0, 0, 255), 3)

        cv2.putText(display, status, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        if saved:
            cv2.putText(display, "KAYDEDILDI — ESC ile cik", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

        cv2.imshow("Zemin Duzlemi Tespiti", display)
        key = cv2.waitKey(30) & 0xFF

        if key == 27:
            break
        elif key == 32 and normal is not None:
            angle = np.degrees(np.arccos(abs(normal[2])))
            if angle > 15:
                print(f"UYARI: Desen {angle:.1f} derece egik. Duzeltin.")
                continue

            np.savez(OUT_PATH,
                     normal=normal,
                     d=d,
                     K=K1, D=D1)
            print(f"\nZemin duzlemi kaydedildi: {OUT_PATH}")
            print(f"  Normal: [{normal[0]:.4f}, {normal[1]:.4f}, {normal[2]:.4f}]")
            print(f"  d: {d:.4f}")
            print(f"  Aci: {angle:.1f} derece")
            saved = True

    cap.release()
    cv2.destroyAllWindows()

    if not saved:
        print("\nKaydedilmeden cikildi.")


if __name__ == "__main__":
    main()
