import cv2
import sys
import os

cap = cv2.VideoCapture(1, cv2.CAP_MSMF)
if not cap.isOpened():
    cap = cv2.VideoCapture(0, cv2.CAP_MSMF)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 960)

print("Kamera acildi, frame aliniyor...")
for _ in range(10):
    cap.grab()
ret, frame = cap.read()
cap.release()

if not ret:
    print("Frame alinamadi!")
    sys.exit(1)

gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
print(f"Frame: {gray.shape[1]}x{gray.shape[0]}")

dicts = [
    ("DICT_4X4_50", cv2.aruco.DICT_4X4_50),
    ("DICT_4X4_100", cv2.aruco.DICT_4X4_100),
    ("DICT_4X4_250", cv2.aruco.DICT_4X4_250),
    ("DICT_5X5_50", cv2.aruco.DICT_5X5_50),
    ("DICT_5X5_100", cv2.aruco.DICT_5X5_100),
    ("DICT_5X5_250", cv2.aruco.DICT_5X5_250),
    ("DICT_6X6_50", cv2.aruco.DICT_6X6_50),
    ("DICT_6X6_100", cv2.aruco.DICT_6X6_100),
    ("DICT_6X6_250", cv2.aruco.DICT_6X6_250),
    ("DICT_7X7_50", cv2.aruco.DICT_7X7_50),
    ("DICT_7X7_100", cv2.aruco.DICT_7X7_100),
    ("DICT_7X7_250", cv2.aruco.DICT_7X7_250),
    ("DICT_ARUCO_ORIGINAL", cv2.aruco.DICT_ARUCO_ORIGINAL),
    ("DICT_APRILTAG_16h5", cv2.aruco.DICT_APRILTAG_16h5),
    ("DICT_APRILTAG_25h9", cv2.aruco.DICT_APRILTAG_25h9),
    ("DICT_APRILTAG_36h10", cv2.aruco.DICT_APRILTAG_36h10),
    ("DICT_APRILTAG_36h11", cv2.aruco.DICT_APRILTAG_36h11),
]

print("\n--- Sozluk Testi ---")
print(f"{'Sozluk':<25} {'Marker Sayisi':>15}")
print("-" * 42)

best_name = ""
best_count = 0

for name, dict_id in dicts:
    aruco_dict = cv2.aruco.getPredefinedDictionary(dict_id)
    params = cv2.aruco.DetectorParameters()
    if name.startswith("DICT_APRILTAG"):
        params.adaptiveThreshWinSizeMax = 73
        params.adaptiveThreshWinSizeStep = 2
    detector = cv2.aruco.ArucoDetector(aruco_dict, params)
    corners, ids, _ = detector.detectMarkers(gray)
    count = len(ids) if ids is not None else 0
    marker = " <---" if count > best_count else ""
    if count > best_count:
        best_count = count
        best_name = name
    if count > 0:
        print(f"{name:<25} {count:>15}{marker}")

print(f"\nEN IYI: {best_name} ({best_count} marker)")
print("\nBoard'u kameraya tutarak calistirin!")

cv2.imwrite("detect_test_frame.png", frame)
print("Frame kaydedildi: detect_test_frame.png")
