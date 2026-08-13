"""DirectShow vs Media Foundation karsilastirma testi.

Her backend icin: format negotiate, gercek FPS, gercek dondurulen format.
Amac: MSMF ile MJPG alabilir miyiz?
"""
import cv2
import time

BACKENDS = [
    ("DSHOW", cv2.CAP_DSHOW),
    ("MSMF",  cv2.CAP_MSMF),
]

TESTS = [
    ("MJPG", 640,  480),
    ("MJPG", 1280, 960),
    ("MJPG", 1920, 1080),
    ("YUY2", 640,  480),
    ("YUY2", 1280, 960),
    ("YUY2", 1920, 1080),
]

def fourcc_str(code):
    if code == 0:
        return "????"
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
    return ok / elapsed if elapsed > 0 and ok > 0 else 0

print("=" * 80)
print("  DSHOW vs MSMF BACKEND KARSILASTIRMA TESTİ")
print("  Soru: MSMF ile MJPG alabilir miyiz?")
print("=" * 80)

for cam_idx in range(4):
    cap = cv2.VideoCapture(cam_idx, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap.release()
        cap = cv2.VideoCapture(cam_idx, cv2.CAP_MSMF)
        if not cap.isOpened():
            cap.release()
            continue
    cap.release()

    print(f"\n{'='*80}")
    print(f"  KAMERA {cam_idx}")
    print(f"{'='*80}")

    for backend_name, backend_code in BACKENDS:
        print(f"\n  --- {backend_name} ---")
        print(f"  {'Istenen':>18s}  {'Alinan':>18s}  {'FPS':>6s}  {'Boyut':>12s}  {'Not'}")
        print(f"  {'-'*18}  {'-'*18}  {'-'*6}  {'-'*12}  {'-'*25}")

        for fmt_name, w, h in TESTS:
            fmt_code = cv2.VideoWriter_fourcc(*fmt_name)
            cap = cv2.VideoCapture(cam_idx, backend_code)
            if not cap.isOpened():
                print(f"  {fmt_name+' '+str(w)+'x'+str(h):>18s}  {'ACILAMADI':>18s}")
                continue

            cap.set(cv2.CAP_PROP_FOURCC, fmt_code)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)

            aw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            ah = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            af = int(cap.get(cv2.CAP_PROP_FOURCC))
            af_str = fourcc_str(af)

            ret, frame = cap.read()
            if not ret:
                print(f"  {fmt_name+' '+str(w)+'x'+str(h):>18s}  {'KARE ALINAMADI':>18s}")
                cap.release()
                continue

            real_shape = f"{frame.shape[1]}x{frame.shape[0]}"
            fps = measure_fps(cap, 30)

            istenen = f"{fmt_name} {w}x{h}"
            alinan = f"{af_str} {aw}x{ah}"

            not_str = ""
            if af_str == fmt_name and aw == w and ah == h:
                not_str = "OK — tam eslesme!"
            elif af_str == fmt_name:
                not_str = f"format OK, cozunurluk farkli"
            elif af_str != fmt_name:
                not_str = f"FORMAT DEGISTI ({fmt_name}->{af_str})"

            print(f"  {istenen:>18s}  {alinan:>18s}  {fps:>5.1f}  {real_shape:>12s}  {not_str}")
            cap.release()

print(f"\n{'='*80}")
print("  SONUC TABLOSU")
print("  Eger MSMF satirlarinda MJPG 1280x960 = OK ve FPS > 20 ise,")
print("  camera_test.py'yi MSMF backend'e gecirmemiz lazim!")
print(f"{'='*80}")
