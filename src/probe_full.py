"""Kameralarin tam yeteneklerini kesfet: format, cozunurluk, gercek FPS."""
import cv2
import time

RESOLUTIONS = [
    (640, 480), (800, 600), (1024, 768), (1280, 720),
    (1280, 960), (1600, 1200), (1920, 1080), (2048, 1536), (3840, 2160),
]
FORMATS = [
    ("MJPG", cv2.VideoWriter_fourcc(*'MJPG')),
    ("YUY2", cv2.VideoWriter_fourcc(*'YUY2')),
    ("NV12", cv2.VideoWriter_fourcc(*'NV12')),
    ("H264", cv2.VideoWriter_fourcc(*'H264')),
]

def measure_fps(cap, n_frames=30):
    for _ in range(5):
        cap.read()
    t0 = time.time()
    ok_count = 0
    for _ in range(n_frames):
        ret, _ = cap.read()
        if ret:
            ok_count += 1
    elapsed = time.time() - t0
    if ok_count == 0:
        return 0
    return ok_count / elapsed

for cam_idx in [1, 2]:
    print(f"\n{'='*60}")
    print(f"  KAMERA {cam_idx} — Tam Yetenek Raporu")
    print(f"{'='*60}")

    for fmt_name, fmt_code in FORMATS:
        results = []
        for w, h in RESOLUTIONS:
            cap = cv2.VideoCapture(cam_idx, cv2.CAP_DSHOW)
            if not cap.isOpened():
                break
            cap.set(cv2.CAP_PROP_FOURCC, fmt_code)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)

            actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
            actual_fmt = "".join([chr((actual_fourcc >> 8*j) & 0xFF) for j in range(4)])

            if actual_w == w and actual_h == h and actual_fmt == fmt_name:
                fps = measure_fps(cap, 20)
                results.append((w, h, fps))
            cap.release()

        if results:
            print(f"\n  Format: {fmt_name}")
            print(f"  {'Cozunurluk':>12s}  {'Gercek FPS':>10s}  {'Megapiksel':>10s}")
            print(f"  {'-'*12}  {'-'*10}  {'-'*10}")
            for w, h, fps in results:
                mp = w * h / 1_000_000
                print(f"  {w:>5d}x{h:<5d}  {fps:>8.1f}    {mp:>8.2f}")

    # Ek bilgiler
    cap = cv2.VideoCapture(cam_idx, cv2.CAP_DSHOW)
    if cap.isOpened():
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        props = {
            "BRIGHTNESS": cv2.CAP_PROP_BRIGHTNESS,
            "CONTRAST": cv2.CAP_PROP_CONTRAST,
            "SATURATION": cv2.CAP_PROP_SATURATION,
            "HUE": cv2.CAP_PROP_HUE,
            "SHARPNESS": cv2.CAP_PROP_SHARPNESS,
            "GAMMA": cv2.CAP_PROP_GAMMA,
            "BACKLIGHT": cv2.CAP_PROP_BACKLIGHT,
            "FOCUS": cv2.CAP_PROP_FOCUS,
            "AUTOFOCUS": cv2.CAP_PROP_AUTOFOCUS,
            "ZOOM": cv2.CAP_PROP_ZOOM,
            "PAN": cv2.CAP_PROP_PAN,
            "TILT": cv2.CAP_PROP_TILT,
        }
        print(f"\n  Ek Ozellikler:")
        for name, prop in props.items():
            val = cap.get(prop)
            if val != 0 and val != -1:
                print(f"    {name:16s}: {val}")
            else:
                # 0 olabilir ama var olabilir, set deneyelim
                old = cap.get(prop)
                ok = cap.set(prop, 1)
                new = cap.get(prop)
                cap.set(prop, old)
                if ok and new != old:
                    print(f"    {name:16s}: {old} (ayarlanabilir)")
                else:
                    print(f"    {name:16s}: desteklenmiyor")
        cap.release()
