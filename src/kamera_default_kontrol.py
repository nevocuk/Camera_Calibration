"""Kameralarin mevcut/fabrika ayarlari normal mi? Biz mi bozduk?

Kullanim (camera_test.py KAPALI olmali):
    .\\calistir.ps1 kamera_default_kontrol

DSHOW backend kullanilir: MSMF'de geri okuma BOZUK (ne yazarsan yaz sabit
deger doner), DSHOW'da dogru calisiyor — olculdu.

Uc sey kontrol edilir:
  1) Iki kameranin MEVCUT degerleri ayni mi?
  2) Degerler makul araliklarda mi (fabrika varsayilani gibi mi)?
  3) Ayarlar kalici mi? (kapat-ac sonrasi kaliyor mu = kamera hafizasi var mi)
"""
import json
import os
import sys
import time
import cv2

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
SETTINGS = os.path.join(PROJECT_DIR, "data", "camera_settings.json")

PROPS = [
    ("EXPOSURE",       cv2.CAP_PROP_EXPOSURE),
    ("AUTO_EXPOSURE",  cv2.CAP_PROP_AUTO_EXPOSURE),
    ("GAIN",           cv2.CAP_PROP_GAIN),
    ("BRIGHTNESS",     cv2.CAP_PROP_BRIGHTNESS),
    ("CONTRAST",       cv2.CAP_PROP_CONTRAST),
    ("SATURATION",     cv2.CAP_PROP_SATURATION),
    ("SHARPNESS",      cv2.CAP_PROP_SHARPNESS),
    ("HUE",            cv2.CAP_PROP_HUE),
    ("GAMMA",          cv2.CAP_PROP_GAMMA),
    ("AUTO_WB",        cv2.CAP_PROP_AUTO_WB),
    ("WB_TEMPERATURE", cv2.CAP_PROP_WB_TEMPERATURE),
    ("BACKLIGHT",      cv2.CAP_PROP_BACKLIGHT),
]

# UVC tipik fabrika araliklari (OV5693 sinifi modulller icin yaygin)
BEKLENEN = {
    "BRIGHTNESS": (-64, 64, 0),
    "CONTRAST": (0, 100, 32),
    "SATURATION": (0, 128, 64),
    "SHARPNESS": (0, 10, 3),
    "GAMMA": (72, 500, 100),
    "GAIN": (0, 100, 0),
    "HUE": (-180, 180, 0),
}


def oku(idx):
    c = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
    if not c.isOpened():
        return None
    time.sleep(0.8)
    for _ in range(5):
        c.grab()
    d = {ad: c.get(p) for ad, p in PROPS}
    c.release()
    time.sleep(0.5)
    return d


def main():
    s = json.load(open(SETTINGS, encoding="utf-8"))
    li, ri = s["left_idx"], s["right_idx"]
    print("=" * 74)
    print("KAMERA VARSAYILAN AYAR KONTROLU  (DSHOW ile okuma)")
    print("=" * 74)
    print(f"SOL = idx {li}    SAG = idx {ri}")
    print("Hicbir deger YAZILMIYOR, sadece mevcut durum okunuyor.\n")

    a = oku(li)
    b = oku(ri)
    if a is None or b is None:
        print("HATA: kamera acilamadi. camera_test.py acik mi?")
        sys.exit(1)

    print(f"{'OZELLIK':<16} {'SOL(idx'+str(li)+')':>12} {'SAG(idx'+str(ri)+')':>12}"
          f" {'ayni mi':>9}  {'beklenen varsayilan':>20}")
    print("-" * 74)
    farkli = []
    supheli = []
    for ad, _ in PROPS:
        va, vb = a[ad], b[ad]
        ayni = "EVET" if abs(va - vb) < 1e-6 else "HAYIR"
        if ayni == "HAYIR":
            farkli.append(ad)
        bek = ""
        if ad in BEKLENEN:
            lo, hi, df = BEKLENEN[ad]
            bek = f"{df} ({lo}..{hi})"
            for v, kim in ((va, "SOL"), (vb, "SAG")):
                if not (lo <= v <= hi):
                    supheli.append(f"{kim} {ad}={v:.0f} araligin DISINDA ({lo}..{hi})")
        print(f"{ad:<16} {va:12.2f} {vb:12.2f} {ayni:>9}  {bek:>20}")

    print()
    print("=" * 74)
    print("DEGERLENDIRME")
    print("=" * 74)
    if farkli:
        print(f"  Iki kamerada FARKLI olan: {', '.join(farkli)}")
    else:
        print("  Tum okunan degerler iki kamerada AYNI.")
    if supheli:
        print("  Arailk disi degerler:")
        for x in supheli:
            print("    - " + x)
    else:
        print("  Tum degerler beklenen araliklarda.")

    # --- Kalicilik testi ---
    print()
    print("=" * 74)
    print("KALICILIK TESTI — ayarlar kamerada saklaniyor mu?")
    print("=" * 74)
    print("  SOL kameraya gecici bir deger yazilip kapatilacak,")
    print("  yeniden acildiginda kaliyor mu bakilacak. Sonra geri alinacak.")
    orij = a["BRIGHTNESS"]
    test_deger = 30 if abs(orij - 30) > 5 else -30
    c = cv2.VideoCapture(li, cv2.CAP_DSHOW)
    if c.isOpened():
        time.sleep(0.6)
        c.set(cv2.CAP_PROP_BRIGHTNESS, test_deger)
        time.sleep(0.4)
        yazilan = c.get(cv2.CAP_PROP_BRIGHTNESS)
        c.release()
        time.sleep(1.0)
        print(f"  Yazildi: BRIGHTNESS={test_deger}  (kamera onayi: {yazilan:.0f})")

        c2 = cv2.VideoCapture(li, cv2.CAP_DSHOW)
        time.sleep(0.8)
        sonra = c2.get(cv2.CAP_PROP_BRIGHTNESS)
        # geri al
        c2.set(cv2.CAP_PROP_BRIGHTNESS, orij)
        time.sleep(0.3)
        geri = c2.get(cv2.CAP_PROP_BRIGHTNESS)
        c2.release()
        print(f"  Kapat-ac sonrasi okunan: {sonra:.0f}")
        print(f"  Orijinale geri alindi  : {geri:.0f}  (orijinal {orij:.0f})")
        print()
        if abs(sonra - test_deger) < 1e-6:
            print("  >>> AYARLAR KALICI. Kamera degeri hafizasinda tutuyor.")
            print("      Yani gecmiste yapilan ayarlar hala uzerinde olabilir.")
            print("      Fabrika ayarina donmek icin: Windows Kamera uygulamasi")
            print("      veya AMCap gibi bir araçtan 'Default' butonuna bas.")
        else:
            print("  >>> AYARLAR KALICI DEGIL. Her acilista fabrika degerine doner.")
            print("      Yani yaptigimiz ayarlar kamerayi KALICI bozmadi.")
    print()
    print("NOT: Pozlama farki donanimsal (lens/diyafram) ise bu testte")
    print("     gorunmez — o zaman ayarlar ayni ama goruntu farkli olur.")


if __name__ == "__main__":
    main()
