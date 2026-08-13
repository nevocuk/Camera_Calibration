"""ChArUco tespit debug scripti — sorunu bulmak icin."""
import os, sys, json
import numpy as np
import cv2

print(f"OpenCV: {cv2.__version__}")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
CONFIG_PATH = os.path.join(PROJECT_DIR, "data", "charuco_config.json")

with open(CONFIG_PATH, encoding="utf-8") as f:
    cfg = json.load(f)
print(f"Config: {cfg['squares_x']}x{cfg['squares_y']}, "
      f"{cfg['square_length_mm']}mm, dict={cfg['aruco_dict']}")

aruco_dict = cv2.aruco.getPredefinedDictionary(
    getattr(cv2.aruco, cfg["aruco_dict"]))

sq = cfg.get("olculen_kare_boyutu_mm") or cfg["square_length_mm"]
mk = cfg["marker_length_mm"] * sq / cfg["square_length_mm"]

# Kamerayi ac
cap = cv2.VideoCapture(2, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"YUY2"))
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 960)

if not cap.isOpened():
    cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"YUY2"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 960)

print("Kamera acildi" if cap.isOpened() else "KAMERA ACILAMADI")
print("Deseni kameraya goster, SPACE ile test et, ESC ile cik\n")

# Tum kombinasyonlari dene
configs = [
    ("8x12 legacy=True",  (8, 12), True),
    ("8x12 legacy=False", (8, 12), False),
    ("12x8 legacy=True",  (12, 8), True),
    ("12x8 legacy=False", (12, 8), False),
]

while True:
    ret, frame = cap.read()
    if not ret:
        continue

    cv2.imshow("Test", frame)
    key = cv2.waitKey(30) & 0xFF
    if key == 27:
        break
    if key != 32:  # SPACE
        continue

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    print("=" * 60)
    print(f"Kare boyutu: {gray.shape[1]}x{gray.shape[0]}")

    # Oncelikle sadece ArUco marker tespiti
    aruco_det = cv2.aruco.ArucoDetector(aruco_dict)
    m_corners, m_ids, rejected = aruco_det.detectMarkers(gray)
    m_count = len(m_ids) if m_ids is not None else 0
    print(f"\nArUco marker sayisi: {m_count}")
    if m_ids is not None and m_count > 0:
        print(f"  Marker ID'leri: {sorted(m_ids.ravel().tolist())}")
        print(f"  corners[0] shape: {m_corners[0].shape}")

    for name, size, legacy in configs:
        board = cv2.aruco.CharucoBoard(
            size, sq / 1000.0, mk / 1000.0, aruco_dict)
        if legacy:
            board.setLegacyPattern(True)

        # Yontem 1: CharucoDetector.detectBoard
        try:
            det = cv2.aruco.CharucoDetector(board)
            result = det.detectBoard(gray)
            cc, ci = result[0], result[1]
            mk_c, mk_i = result[2], result[3]
            cc_count = len(cc) if cc is not None else 0
            mk_count = len(mk_i) if mk_i is not None else 0
            print(f"\n[{name}] detectBoard: "
                  f"charuco={cc_count}, markers={mk_count}")
        except Exception as e:
            print(f"\n[{name}] detectBoard HATA: {e}")

        # Yontem 2: Eski API (interpolateCornersCharuco)
        if m_ids is not None and m_count > 0:
            try:
                ret2, cc2, ci2 = cv2.aruco.interpolateCornersCharuco(
                    m_corners, m_ids, gray, board)
                print(f"[{name}] interpolate: ret={ret2}, "
                      f"corners={len(cc2) if cc2 is not None else 0}")
            except Exception as e:
                print(f"[{name}] interpolate HATA: {e}")

    print()

cap.release()
cv2.destroyAllWindows()
