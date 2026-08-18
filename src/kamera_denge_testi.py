"""Iki kamera neden farkli parlaklik veriyor? Teshis araci.

Kullanim (camera_test.py KAPALI olmali):
    .\\calistir.ps1 kamera_denge_testi

Test ettigi hipotez:
    MSMF'de akis baslamadan yazilan ayarlar sessizce yok sayilabilir.
    Hangi kamera once hazir olursa ayari o alir -> iki kamera farkli kalir.
    Ayarlar kareler aktiktan SONRA tekrar yazilirsa fark kapanmali.
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


def ayarlari_yaz(cap, s, sag=False):
    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
    cap.set(cv2.CAP_PROP_AUTO_WB, 0)
    cap.set(cv2.CAP_PROP_WB_TEMPERATURE, s["wb"])
    cap.set(cv2.CAP_PROP_CONTRAST, s["contrast"])
    cap.set(cv2.CAP_PROP_SATURATION, s["saturation"])
    cap.set(cv2.CAP_PROP_SHARPNESS, s["sharpness"])
    exp = s["exposure"] + (s.get("exp_offset_r", 0) if sag else 0)
    gain = s["gain"] + (s.get("gain_offset_r", 0) if sag else 0)
    br = s["brightness"] + (s.get("bright_offset_r", 0) if sag else 0)
    cap.set(cv2.CAP_PROP_EXPOSURE, max(-13, min(0, exp)))
    cap.set(cv2.CAP_PROP_GAIN, max(0, min(100, gain)))
    cap.set(cv2.CAP_PROP_BRIGHTNESS, max(-64, min(64, br)))


def olc(caps, n=6):
    out = {}
    for _ in range(n):
        for c in caps.values():
            c.grab()
    for ad, c in caps.items():
        vals = []
        for _ in range(n):
            c.grab()
            ok, f = c.retrieve()
            if ok:
                vals.append(float(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).mean()))
        out[ad] = float(np.mean(vals)) if vals else float("nan")
    return out


def tur(no, s, w, h, gecikmeli_tekrar):
    caps = {}
    for ad, idx in (("SOL", s["left_idx"]), ("SAG", s["right_idx"])):
        c = cv2.VideoCapture(idx, cv2.CAP_MSMF)
        if not c.isOpened():
            print(f"  {ad} acilamadi")
            for x in caps.values():
                x.release()
            return None
        c.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        c.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        c.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        caps[ad] = c

    # 1) Ayarlari HEMEN yaz (camera_test.py'nin eski davranisi)
    for ad, c in caps.items():
        ayarlari_yaz(c, s, sag=(ad == "SAG"))
    time.sleep(1.2)
    ilk = olc(caps)

    ikinci = None
    if gecikmeli_tekrar:
        # 2) Kareler aktiktan SONRA tekrar yaz (yeni davranis)
        for ad, c in caps.items():
            ayarlari_yaz(c, s, sag=(ad == "SAG"))
        time.sleep(1.0)
        ikinci = olc(caps)

    for c in caps.values():
        c.release()
    time.sleep(0.6)
    return ilk, ikinci


def fark(d):
    return abs(d["SOL"] - d["SAG"]) / max(d["SOL"], d["SAG"], 1) * 100


def main():
    if not os.path.exists(SETTINGS):
        print("camera_settings.json yok")
        sys.exit(1)
    s = json.load(open(SETTINGS, encoding="utf-8"))
    w, h = 1280, 960
    print("=" * 68)
    print("KAMERA DENGE TESTI")
    print("=" * 68)
    print(f"Ayarlar: poz={s['exposure']} gain={s['gain']} "
          f"parlaklik={s['brightness']} kontrast={s['contrast']}")
    print(f"Telafiler: poz={s.get('exp_offset_r',0)} "
          f"gain={s.get('gain_offset_r',0)} parlaklik={s.get('bright_offset_r',0)}")
    print()
    print("Her turda kameralar YENIDEN aciliyor (acilis yarisi test ediliyor).")
    print()
    print(f"{'tur':>4} | {'HEMEN yazinca':^28} | {'TEKRAR yazinca':^28}")
    print(f"{'':>4} | {'SOL':>8} {'SAG':>8} {'fark':>9} | {'SOL':>8} {'SAG':>8} {'fark':>9}")
    print("-" * 72)

    ilk_farklar, son_farklar = [], []
    for i in range(1, 6):
        r = tur(i, s, w, h, gecikmeli_tekrar=True)
        if r is None:
            continue
        a, b = r
        ilk_farklar.append(fark(a))
        line = f"{i:>4} | {a['SOL']:8.1f} {a['SAG']:8.1f} {fark(a):8.1f}%"
        if b:
            son_farklar.append(fark(b))
            line += f" | {b['SOL']:8.1f} {b['SAG']:8.1f} {fark(b):8.1f}%"
        print(line)

    print("-" * 72)
    if ilk_farklar:
        print(f"HEMEN yazinca  : ortalama fark %{np.mean(ilk_farklar):.1f}  "
              f"(min %{min(ilk_farklar):.1f}  max %{max(ilk_farklar):.1f})")
    if son_farklar:
        print(f"TEKRAR yazinca : ortalama fark %{np.mean(son_farklar):.1f}  "
              f"(min %{min(son_farklar):.1f}  max %{max(son_farklar):.1f})")
        print()
        if np.mean(son_farklar) < np.mean(ilk_farklar) - 5:
            print(">>> TEKRAR yazmak farki KAPATIYOR — acilis yarisi dogrulandi.")
            print("    camera_test.py artik 1.2 sn ve 2.5 sn sonra tekrar uyguluyor.")
        elif max(ilk_farklar) - min(ilk_farklar) > 15:
            print(">>> Fark turdan ture cok degisiyor (kararsiz acilis).")
            print("    Tekrar yazmak tek basina yetmiyor; 'Otomatik esitle' kullan.")
        else:
            print(">>> Fark tekrar yazmakla degismiyor — kalici donanim/ISP farki.")
            print("    Cozum: 'Otomatik esitle' + ton eslemesi 'Histogram'.")


if __name__ == "__main__":
    main()
