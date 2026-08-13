"""Bagli kameralari tespit et — indeks, backend, cozunurluk, FourCC."""
import cv2

print("Kamera taramasi basliyor...\n")
found = []
for i in range(10):
    cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
    if cap.isOpened():
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fourcc_int = int(cap.get(cv2.CAP_PROP_FOURCC))
        fourcc_str = "".join([chr((fourcc_int >> 8*j) & 0xFF) for j in range(4)])
        ret, frame = cap.read()
        ok = "KARE OKUNDU" if ret else "KARE OKUNAMADI"
        print(f"  Indeks {i}: {w}x{h}, FourCC={fourcc_str}, {ok}")
        found.append(i)
        cap.release()
    else:
        cap.release()

if len(found) < 2:
    print(f"\nUYARI: {len(found)} kamera bulundu, stereo icin 2 gerekli.")
else:
    print(f"\nToplam {len(found)} kamera bulundu: {found}")
    print(f"Onerilen sol/sag: indeks {found[0]} ve {found[1]}")
