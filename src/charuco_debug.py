import cv2
import numpy as np

cap = cv2.VideoCapture(1, cv2.CAP_MSMF)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 960)
for _ in range(10):
    cap.grab()
ret, frame = cap.read()
cap.release()
gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
print(f"Frame: {gray.shape[1]}x{gray.shape[0]}")

aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_100)
params = cv2.aruco.DetectorParameters()
params.adaptiveThreshWinSizeMax = 73
params.adaptiveThreshWinSizeStep = 2
det = cv2.aruco.ArucoDetector(aruco_dict, params)
corners, ids, _ = det.detectMarkers(gray)
print(f"Marker: {len(ids) if ids is not None else 0}")
if ids is not None:
    print(f"ID'ler: {sorted(ids.ravel().tolist())}")

for sx, sy in [(13, 9), (9, 13)]:
    for leg in [True, False]:
        board = cv2.aruco.CharucoBoard((sx, sy), 0.020, 0.01467, aruco_dict)
        try:
            board.setLegacyPattern(leg)
        except:
            pass
        board_ids = board.getIds().ravel().tolist() if board.getIds() is not None else []
        cp = cv2.aruco.CharucoParameters()
        dp = cv2.aruco.DetectorParameters()
        dp.adaptiveThreshWinSizeMax = 73
        dp.adaptiveThreshWinSizeStep = 2
        cd = cv2.aruco.CharucoDetector(board, cp, dp)
        cc, ci, _, _ = cd.detectBoard(gray)
        n = len(cc) if cc is not None else 0
        print(f"({sx}x{sy}) Legacy={leg}: {n} kose, "
              f"Board bekliyor: {len(board_ids)} marker, ID aralik: {min(board_ids)}-{max(board_ids)}")

print("\n--- DICT_4X4_50 ---")
aruco_dict2 = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
for sx, sy in [(13, 9), (9, 13)]:
    for leg in [True, False]:
        board = cv2.aruco.CharucoBoard((sx, sy), 0.020, 0.01467, aruco_dict2)
        try:
            board.setLegacyPattern(leg)
        except:
            pass
        board_ids = board.getIds().ravel().tolist() if board.getIds() is not None else []
        cp = cv2.aruco.CharucoParameters()
        dp = cv2.aruco.DetectorParameters()
        dp.adaptiveThreshWinSizeMax = 73
        dp.adaptiveThreshWinSizeStep = 2
        cd = cv2.aruco.CharucoDetector(board, cp, dp)
        cc, ci, _, _ = cd.detectBoard(gray)
        n = len(cc) if cc is not None else 0
        print(f"({sx}x{sy}) Legacy={leg}: {n} kose, "
              f"Board bekliyor: {len(board_ids)} marker, ID aralik: {min(board_ids)}-{max(board_ids)}")
