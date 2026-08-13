"""Kameralarin tam yeteneklerini kesfet: format, cozunurluk, gercek FPS.

Her cozunurluk+format icin:
  1. Istenen formati ayarla
  2. Gercekte dondurulen formati oku
  3. Gercek FPS olc
  4. Format donusumu olup olmadigini raporla
"""
import cv2
import time

RESOLUTIONS = [
    (640, 480), (800, 600), (1024, 768), (1280, 720),
    (1280, 960), (1600, 1200), (1920, 1080), (2048, 1536),
    (2560, 1440), (3840, 2160),
]
FORMATS = [
    ("MJPG", cv2.VideoWriter_fourcc(*'MJPG')),
    ("YUY2", cv2.VideoWriter_fourcc(*'YUY2')),
]

def fourcc_str(code):
    return "".join([chr((code >> 8*j) & 0xFF) for j in range(4)])

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
    return ok / elapsed if ok > 0 else 0

print("=" * 72)
print("  KAMERA FORMAT VE COZUNURLUK TESTI")
print("  Her satir: istenen → gercek alinan formati gosterir")
print("=" * 72)

for cam_idx in range(4):
    cap = cv2.VideoCapture(cam_idx, cv2.CAP_DSHOW)
    if not cap.isOpened():
        continue
    cap.release()

    print(f"\n--- KAMERA {cam_idx} ---")
    print(f"  {'Istenen':>16s}  {'Alinan':>16s}  {'Format':>6s}  {'FPS':>6s}  {'Not':s}")
    print(f"  {'-'*16}  {'-'*16}  {'-'*6}  {'-'*6}  {'-'*20}")

    for fmt_name, fmt_code in FORMATS:
        for w, h in RESOLUTIONS:
            cap = cv2.VideoCapture(cam_idx, cv2.CAP_DSHOW)
            if not cap.isOpened():
                break
            cap.set(cv2.CAP_PROP_FOURCC, fmt_code)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)

            aw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            ah = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            af = int(cap.get(cv2.CAP_PROP_FOURCC))
            af_str = fourcc_str(af)

            ret, frame = cap.read()
            if not ret:
                cap.release()
                continue

            fps = measure_fps(cap, 20)

            istenen = f"{fmt_name} {w}x{h}"
            alinan = f"{af_str} {aw}x{ah}"
            not_str = ""
            if af_str != fmt_name:
                not_str = f"FORMAT FARKLI! ({fmt_name}→{af_str})"
            elif aw != w or ah != h:
                not_str = f"cozunurluk degisti"
            else:
                not_str = "OK"

            print(f"  {istenen:>16s}  {alinan:>16s}  {af_str:>6s}  {fps:>5.1f}  {not_str}")
            cap.release()

    # Tek kamera, MJPG, 1280x960 — detayli bilgi
    cap = cv2.VideoCapture(cam_idx, cv2.CAP_DSHOW)
    if cap.isOpened():
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 960)
        ret, frame = cap.read()
        if ret:
            print(f"\n  Detay (MJPG 1280x960):")
            print(f"    Frame boyutu: {frame.shape}")
            print(f"    dtype: {frame.dtype}")
            bs = int(cap.get(cv2.CAP_PROP_BUFFERSIZE)) if hasattr(cv2, 'CAP_PROP_BUFFERSIZE') else -1
            print(f"    Buffer size: {bs}")
            backend = cap.getBackendName()
            print(f"    Backend: {backend}")
        cap.release()

print("\n" + "=" * 72)
print("  SONUC: Eger YUY2 isteyip MJPG aliyorsaniz, kamera")
print("  donanimi sadece MJPG destekliyor. Bu bir surucu siniri,")
print("  yazilimla degistirilemez.")
print("=" * 72)
