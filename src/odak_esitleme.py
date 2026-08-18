"""Canli odak esitleme araci — iki M12 lensi olcerek ayni netlige getir.

Kullanim (camera_test.py KAPALI olmali):
    .\\calistir.ps1 odak_esitleme

HAZIRLIK:
  1. Dokulu bir hedef koy (patterns/sgbm_doku_desenleri_v2.pdf basili hali,
     gazete, yazi dolu sayfa). DUZ olmali, kivrik degil.
  2. Calisma mesafesine koy (~500 mm) ve KAREYI DOLDURSUN.
  3. Isik sabit olsun, hedefe golge dusmesin.

YONTEM:
  Lensi yavasca cevir. Cubuk yukselirse dogru yone gidiyorsun.
  TEPE degerini gecip geri don — "TEPEDE" yazisi cikinca orasi en net nokta.
  Ayni islemi diger lens icin tekrarla. Iki kameranin skoru yakin olmali.

TUSLAR:
  R = tepe degerlerini sifirla (yeni aramaya basla)
  S = ekran goruntusu kaydet
  ESC = cikis

NEDEN "normalize netlik"?
  Ham Laplacian varyansi parlaklikla olceklenir; iki kamera farkli
  parlakliktaysa ham sayilar KARSILASTIRILAMAZ. var(Laplacian)/ortalama^2
  carpimsal parlaklik farkina duyarsizdir, o yuzden onu kullaniyoruz.
"""
import json
import os
import sys
import time
import numpy as np
import cv2

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
SETTINGS = os.path.join(PROJECT_DIR, "data", "camera_settings.json")
OUT = os.path.join(PROJECT_DIR, "output", "odak")
os.makedirs(OUT, exist_ok=True)

W, H = 1280, 960          # canli tepki icin dusuk cozunurluk yeterli
ROI = 0.5                 # merkez %50


def netlik(gray):
    """Parlakliga duyarsiz netlik: var(Laplacian) / ortalama^2."""
    m = float(gray.mean())
    if m < 5:
        return 0.0
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    return float(lap.var() / (m * m) * 1000.0)


def merkez(g):
    h, w = g.shape[:2]
    y = int(h * (1 - ROI) / 2)
    x = int(w * (1 - ROI) / 2)
    return g[y:h - y, x:w - x]


def cubuk(img, x, y, gen, yuk, oran, renk):
    cv2.rectangle(img, (x, y), (x + gen, y + yuk), (70, 70, 70), 1)
    dolu = int(gen * max(0.0, min(1.0, oran)))
    if dolu > 0:
        cv2.rectangle(img, (x + 1, y + 1), (x + dolu, y + yuk - 1), renk, -1)


def main():
    s = {}
    if os.path.exists(SETTINGS):
        s = json.load(open(SETTINGS, encoding="utf-8"))
    li, ri = s.get("left_idx", 1), s.get("right_idx", 2)

    caps = {}
    for ad, idx in (("SOL", li), ("SAG", ri)):
        c = cv2.VideoCapture(idx, cv2.CAP_MSMF)
        if not c.isOpened():
            print(f"HATA: {ad} (idx {idx}) acilamadi. camera_test.py acik mi?")
            for x in caps.values():
                x.release()
            sys.exit(1)
        c.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        c.set(cv2.CAP_PROP_FRAME_WIDTH, W)
        c.set(cv2.CAP_PROP_FRAME_HEIGHT, H)
        c.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
        c.set(cv2.CAP_PROP_AUTO_WB, 0)
        if s:
            c.set(cv2.CAP_PROP_EXPOSURE, s.get("exposure", -5))
            c.set(cv2.CAP_PROP_GAIN, s.get("gain", 0))
            c.set(cv2.CAP_PROP_BRIGHTNESS, s.get("brightness", 0))
        caps[ad] = c

    time.sleep(1.2)
    for _ in range(10):
        for c in caps.values():
            c.grab()
    # akis basladiktan sonra ayarlari TEKRAR yaz (MSMF gereksinimi)
    for ad, c in caps.items():
        c.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
        if s:
            c.set(cv2.CAP_PROP_EXPOSURE, s.get("exposure", -5))

    print(__doc__)
    print("Pencere aciliyor...")

    tepe = {"SOL": 0.0, "SAG": 0.0}
    gecmis = {"SOL": [], "SAG": []}
    kayit = 0

    while True:
        for c in caps.values():
            c.grab()
        kareler, skor, parlak = {}, {}, {}
        for ad, c in caps.items():
            ok, f = c.retrieve()
            if not ok:
                continue
            g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
            kareler[ad] = f
            m = merkez(g)
            skor[ad] = netlik(m)
            parlak[ad] = float(g.mean())
            gecmis[ad].append(skor[ad])
            if len(gecmis[ad]) > 5:
                gecmis[ad].pop(0)
        if len(kareler) < 2:
            continue

        # 5 karelik ortalama — titremeyi azalt
        for ad in skor:
            skor[ad] = float(np.mean(gecmis[ad]))
            tepe[ad] = max(tepe[ad], skor[ad])

        panolar = []
        for ad in ("SOL", "SAG"):
            f = kareler[ad]
            h, w = f.shape[:2]
            y = int(h * (1 - ROI) / 2)
            x = int(w * (1 - ROI) / 2)
            gorsel = cv2.resize(f, (560, 420))
            # ROI cercevesi
            cv2.rectangle(gorsel,
                          (int(560 * (1 - ROI) / 2), int(420 * (1 - ROI) / 2)),
                          (int(560 * (1 + ROI) / 2), int(420 * (1 + ROI) / 2)),
                          (0, 255, 0), 2)
            pano = np.zeros((560, 560, 3), dtype=np.uint8)
            pano[:420] = gorsel
            sk, tp = skor[ad], tepe[ad]
            oran = sk / tp if tp > 0 else 0
            tepede = oran > 0.97 and tp > 0.5
            renk = (0, 255, 0) if tepede else ((0, 200, 255) if oran > 0.85
                                               else (0, 100, 255))
            cv2.putText(pano, ad, (10, 452), cv2.FONT_HERSHEY_SIMPLEX,
                        0.8, (255, 255, 255), 2)
            cv2.putText(pano, f"netlik {sk:7.1f}", (90, 452),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, renk, 2)
            cv2.putText(pano, f"tepe {tp:7.1f}", (300, 452),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 180), 1)
            cubuk(pano, 10, 465, 540, 22, oran, renk)
            cv2.putText(pano, "TEPEDE - LENSI SABITLE" if tepede
                        else f"tepenin %{oran*100:.0f}'i",
                        (10, 505), cv2.FONT_HERSHEY_SIMPLEX, 0.6, renk, 2)
            pb = parlak[ad]
            prenk = (160, 160, 160) if 70 <= pb <= 200 else (0, 140, 255)
            cv2.putText(pano, f"parlaklik {pb:.0f}/255"
                        + ("  COK KARANLIK" if pb < 70 else
                           ("  COK PARLAK" if pb > 200 else "")),
                        (10, 535), cv2.FONT_HERSHEY_SIMPLEX, 0.5, prenk, 1)
            panolar.append(pano)

        ekran = np.hstack(panolar)

        # Kameralar arasi karsilastirma SADECE parlakliklar yakinsa gecerlidir.
        # Karanlik karede sensor gurultusu Laplacian'i sisirir ve /ortalama^2
        # bolmesi bunu daha da buyutur -> sahte yuksek netlik skoru.
        a, b = skor["SOL"], skor["SAG"]
        pa, pb2 = parlak["SOL"], parlak["SAG"]
        p_oran = max(pa, pb2) / max(min(pa, pb2), 1e-6)
        alt = np.zeros((72, ekran.shape[1], 3), dtype=np.uint8)
        if p_oran > 1.35:
            msg = f"PARLAKLIK FARKI {p_oran:.2f}x - kameralar KARSILASTIRILAMAZ"
            mrenk = (0, 100, 255)
            alt2 = "Her lensi KENDI tepesine ayarla; capraz kiyas gecersiz."
        else:
            oran_ab = max(a, b) / max(min(a, b), 1e-6)
            if oran_ab < 1.15:
                msg, mrenk = "IKI KAMERA DENGELI", (0, 255, 0)
            elif oran_ab < 1.4:
                msg, mrenk = f"hafif fark ({oran_ab:.2f}x)", (0, 200, 255)
            else:
                dusuk = "SOL" if a < b else "SAG"
                msg = f"DENGESIZ ({oran_ab:.2f}x) - {dusuk} lensini ayarla"
                mrenk = (0, 100, 255)
            alt2 = "Parlakliklar yakin, kiyas gecerli."
        cv2.putText(alt, msg, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.72, mrenk, 2)
        cv2.putText(alt, alt2, (12, 56), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, (150, 150, 150), 1)
        cv2.putText(alt, "R=tepeyi sifirla  S=kaydet  ESC=cikis",
                    (ekran.shape[1] - 430, 28), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, (150, 150, 150), 1)
        ekran = np.vstack([ekran, alt])

        cv2.imshow("Odak Esitleme", ekran)
        k = cv2.waitKey(30) & 0xFF
        if k == 27:
            break
        if k in (ord('r'), ord('R')):
            tepe = {"SOL": 0.0, "SAG": 0.0}
            print("Tepe degerleri sifirlandi.")
        if k in (ord('s'), ord('S')):
            kayit += 1
            p = os.path.join(OUT, f"odak_{kayit:02d}.png")
            cv2.imwrite(p, ekran)
            print(f"Kaydedildi: {p}   SOL={a:.1f} SAG={b:.1f}")

    for c in caps.values():
        c.release()
    cv2.destroyAllWindows()
    print(f"\nSon durum:  SOL tepe={tepe['SOL']:.1f}   SAG tepe={tepe['SAG']:.1f}")
    if max(tepe.values()) > 0:
        o = max(tepe.values()) / max(min(tepe.values()), 1e-6)
        print(f"Tepe orani: {o:.2f}x  "
              f"{'-> dengeli' if o < 1.25 else '-> hala dengesiz'}")
    print("\nNOT: Parlakliklar birbirinden %35'ten fazla farkliysa bu oran")
    print("     ANLAMSIZDIR — karanlik karede gurultu netlik skorunu sisirir.")
    print("     Once parlakligi esitle, sonra odak kiyasi yap.")


if __name__ == "__main__":
    main()
