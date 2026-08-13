"""MSMF backend tam cozunurluk testi.

MSMF ile tum cozunurluklerde gercek FPS ve format kontrolu.
"""
import cv2
import time

RESOLUTIONS = [
    (640, 480), (800, 600), (1024, 768), (1280, 720),
    (1280, 960), (1600, 1200), (1920, 1080), (2048, 1536),
    (2560, 1440), (3840, 2160),
]

def fourcc_str(code):
    if code == 0:
        return "????"
    chars = []
    for j in range(4):
        c = (code >> 8*j) & 0xFF
        if 32 <= c <= 126:
            chars.append(chr(c))
        else:
            return f"0x{code:08X}"
    return "".join(chars)

def measure_fps(cap, n_frames=30):
    for _ in range(5):
        cap.read()
    t0 = time.time()
    ok = 0
    for _ in range(n_frames):
        ret, _ = cap.read()
        if ret:
            ok += 1
    elapsed = time.time() - t0
    return ok / elapsed if elapsed > 0 and ok > 0 else 0

print("=" * 85)
print("  MSMF BACKEND — TAM COZUNURLUK TESTİ (MJPG istegi ile)")
print("=" * 85)

for cam_idx in range(4):
    cap = cv2.VideoCapture(cam_idx, cv2.CAP_MSMF)
    if not cap.isOpened():
        cap.release()
        continue
    cap.release()

    print(f"\n  KAMERA {cam_idx}")
    print(f"  {'Istenen':>16s}  {'Gercek boyut':>14s}  {'FourCC':>10s}  {'FPS':>6s}  {'Veri':>10s}  Not")
    print(f"  {'-'*16}  {'-'*14}  {'-'*10}  {'-'*6}  {'-'*10}  {'-'*20}")

    for w, h in RESOLUTIONS:
        cap = cv2.VideoCapture(cam_idx, cv2.CAP_MSMF)
        if not cap.isOpened():
            continue

        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)

        aw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        ah = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        af = int(cap.get(cv2.CAP_PROP_FOURCC))
        af_str = fourcc_str(af)

        ret, frame = cap.read()
        if not ret:
            print(f"  {w}x{h:>10s}  {'KARE YOK':>14s}")
            cap.release()
            continue

        real_w, real_h = frame.shape[1], frame.shape[0]
        fps = measure_fps(cap, 30)
        mb_per_sec = (real_w * real_h * 3 * fps) / (1024 * 1024)

        not_str = ""
        if real_w == w and real_h == h:
            not_str = "OK"
        else:
            not_str = f"boyut degisti"

        istenen = f"{w}x{h}"
        gercek = f"{real_w}x{real_h}"
        veri = f"{mb_per_sec:.1f} MB/s"

        print(f"  {istenen:>16s}  {gercek:>14s}  {af_str:>10s}  {fps:>5.1f}  {veri:>10s}  {not_str}")
        cap.release()

print(f"\n{'='*85}")
print("  30 FPS olan satirlarda MJPG sikistirma calisiyor demektir.")
print("  Dusuk FPS = muhtemelen YUY2'ye dustu veya USB bant genisligi yetmiyor.")
print(f"{'='*85}")
