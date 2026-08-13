"""Iki kamerayi AYNI ANDA acip hangi cozunurluklerde calistigini test et."""
import cv2
import time

TESTS = [
    ("640x480 MJPG",   640,  480,  cv2.VideoWriter_fourcc(*'MJPG')),
    ("1280x720 YUY2",  1280, 720,  cv2.VideoWriter_fourcc(*'YUY2')),
    ("1280x960 YUY2",  1280, 960,  cv2.VideoWriter_fourcc(*'YUY2')),
    ("1920x1080 YUY2", 1920, 1080, cv2.VideoWriter_fourcc(*'YUY2')),
    ("2048x1536 YUY2", 2048, 1536, cv2.VideoWriter_fourcc(*'YUY2')),
    ("3840x2160 YUY2", 3840, 2160, cv2.VideoWriter_fourcc(*'YUY2')),
]

print("Stereo bant genisligi testi — iki kamera ayni anda\n")

for name, w, h, fourcc in TESTS:
    cap1 = cv2.VideoCapture(1, cv2.CAP_DSHOW)
    cap2 = cv2.VideoCapture(2, cv2.CAP_DSHOW)

    for cap in [cap1, cap2]:
        cap.set(cv2.CAP_PROP_FOURCC, fourcc)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)

    ok1 = cap1.isOpened()
    ok2 = cap2.isOpened()

    if not ok1 or not ok2:
        print(f"  {name:20s}  ACILAMADI")
        cap1.release()
        cap2.release()
        continue

    aw1 = int(cap1.get(cv2.CAP_PROP_FRAME_WIDTH))
    ah1 = int(cap1.get(cv2.CAP_PROP_FRAME_HEIGHT))
    aw2 = int(cap2.get(cv2.CAP_PROP_FRAME_WIDTH))
    ah2 = int(cap2.get(cv2.CAP_PROP_FRAME_HEIGHT))

    if aw1 != w or ah1 != h or aw2 != w or ah2 != h:
        print(f"  {name:20s}  COZUNURLUK TUTMADI (L={aw1}x{ah1} R={aw2}x{ah2})")
        cap1.release()
        cap2.release()
        continue

    # grab/retrieve ile senkron test
    fail_count = 0
    success_count = 0
    t0 = time.time()
    for i in range(20):
        g1 = cap1.grab()
        g2 = cap2.grab()
        if g1 and g2:
            ret1, f1 = cap1.retrieve()
            ret2, f2 = cap2.retrieve()
            if ret1 and ret2:
                success_count += 1
            else:
                fail_count += 1
        else:
            fail_count += 1
    elapsed = time.time() - t0

    fps = success_count / elapsed if elapsed > 0 else 0
    bw_mbps = w * h * 2 * fps * 2 / 1_000_000  # 2 byte/px, 2 kamera

    status = "OK" if success_count >= 15 else "SORUNLU" if success_count >= 5 else "BASARISIZ"
    print(f"  {name:20s}  {status:10s}  {success_count}/20 kare  "
          f"{fps:.1f} FPS  ~{bw_mbps:.0f} MB/s")

    cap1.release()
    cap2.release()
