"""Kameranin destekledigi cozunurlukleri tespit et."""
import cv2

COMMON_RESOLUTIONS = [
    (320, 240), (640, 480), (800, 600), (960, 720),
    (1024, 768), (1280, 720), (1280, 960), (1280, 1024),
    (1600, 1200), (1920, 1080), (2048, 1536), (2560, 1440),
    (2560, 1920), (3200, 2400), (3840, 2160), (4096, 2160),
]

for cam_idx in [1, 2]:
    print(f"\n=== Kamera {cam_idx} ===")
    supported = []
    for w, h in COMMON_RESOLUTIONS:
        cap = cv2.VideoCapture(cam_idx, cv2.CAP_DSHOW)
        if not cap.isOpened():
            break
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if actual_w == w and actual_h == h:
            ret, frame = cap.read()
            if ret:
                fps = cap.get(cv2.CAP_PROP_FPS)
                supported.append((w, h, fps))
                print(f"  {w}x{h} @ {fps:.0f} FPS  OK")
        cap.release()
    if not supported:
        print("  Hicbir cozunurluk bulunamadi!")
    else:
        print(f"  Toplam: {len(supported)} cozunurluk destekleniyor")
