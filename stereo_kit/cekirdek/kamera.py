"""Kamera bulma, yetenek tarama ve acma - HERHANGI bir USB kamera icin.

Bu modul hicbir donanim varsayimi yapmaz. Bagli kameralari bulur,
her birinin GERCEKTEN destekledigi cozunurlukleri dener (surucunun
bildirdigine guvenmez) ve ikisini stereo cift olarak acar.

NEDEN GERCEKTEN DENIYORUZ: bir kameraya "3840x2160 yap" dendiginde
surucu cogu zaman "tamam" der ama sessizce en yakin destekledigi
cozunurluge duser. Yalnizca ayari yazip geri okumak yaniltir; kare
alip boyutuna bakmak gerekir.
"""
from __future__ import annotations

import platform
import time

import cv2

# Denenecek yaygin cozunurlukler - kucukten buyuge.
# Liste sabit degil; tarama sirasinda calismayanlar elenir.
ADAY_COZUNURLUKLER = [
    (640, 480), (800, 600), (1024, 768), (1280, 720), (1280, 960),
    (1600, 1200), (1920, 1080), (2048, 1536), (2592, 1944),
    (3264, 2448), (3840, 2160),
]

# Denenecek sikistirma bicimleri. MJPG genelde yuksek cozunurlukte
# USB bant genisligini kurtarir; YUYV sikistirmasizdir ve buyuk
# cozunurlukte kare hizini dusurur.
ADAY_FOURCC = ["MJPG", "YUYV"]


def _backend_listesi():
    """Isletim sistemine gore denenecek yakalama arayuzleri.

    Windows'ta iki arayuz var ve ikisinin de zayifligi var:
      MSMF  - ayar yazma tutarli, ama ayar GERI OKUMASI guvenilmez
      DSHOW - geri okuma dogru, ama bazi ayarlar sessizce uygulanmaz
    Linux'ta V4L2, macOS'ta AVFoundation tek secenek.
    """
    s = platform.system()
    if s == "Windows":
        return [("MSMF", cv2.CAP_MSMF), ("DSHOW", cv2.CAP_DSHOW)]
    if s == "Linux":
        return [("V4L2", cv2.CAP_V4L2)]
    if s == "Darwin":
        return [("AVFOUNDATION", cv2.CAP_AVFOUNDATION)]
    return [("VARSAYILAN", cv2.CAP_ANY)]


def fourcc_metni(deger: float) -> str:
    """Sayisal FourCC kodunu okunur metne cevir."""
    v = int(deger)
    s = "".join(chr((v >> (8 * i)) & 0xFF) for i in range(4))
    return "".join(ch if ch.isprintable() else "?" for ch in s).strip()


def kameralari_bul(max_indeks: int = 8, kare_dogrula: bool = True):
    """Bagli kameralari bul.

    kare_dogrula=True ise her kameradan gercekten bir kare okunur;
    "acildi ama kare vermiyor" durumundaki cihazlar elenir. Sanal
    kameralar ve bazi dahili cihazlar bu tuzaga dusuyor.

    Donen: [{indeks, backend_ad, backend_id, genislik, yukseklik,
             fourcc, kare_okundu}]
    """
    bulunan = []
    for backend_ad, backend_id in _backend_listesi():
        for i in range(max_indeks):
            if any(b["indeks"] == i for b in bulunan):
                continue                      # baska backend'de bulundu
            cap = None
            try:
                cap = cv2.VideoCapture(i, backend_id)
                if not cap.isOpened():
                    continue
                ok = True
                if kare_dogrula:
                    ok = False
                    for _ in range(3):        # ilk kareler bos gelebilir
                        r, kare = cap.read()
                        if r and kare is not None and kare.size:
                            ok = True
                            break
                        time.sleep(0.05)
                if not ok:
                    continue
                bulunan.append({
                    "indeks": i,
                    "backend_ad": backend_ad,
                    "backend_id": backend_id,
                    "genislik": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                    "yukseklik": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                    "fourcc": fourcc_metni(cap.get(cv2.CAP_PROP_FOURCC)),
                    "kare_okundu": ok,
                })
            except Exception:
                continue
            finally:
                if cap is not None:
                    cap.release()
    return sorted(bulunan, key=lambda b: b["indeks"])


def cozunurluk_tara(indeks: int, backend_id: int,
                    adaylar=None, fourcc_adaylar=None, ilerleme=None):
    """Bir kameranin GERCEKTEN destekledigi cozunurlukleri bul.

    Her aday icin cozunurluk ayarlanir, kare alinir ve karenin
    gercek boyutuna bakilir. Istenen ile alinan ayni degilse o
    cozunurluk desteklenmiyor demektir.

    ilerleme: callable(mevcut, toplam, metin) - arayuz icin.

    Donen: [{genislik, yukseklik, fourcc, fps}] - benzersiz,
    kucukten buyuge sirali.
    """
    adaylar = adaylar or ADAY_COZUNURLUKLER
    fourcc_adaylar = fourcc_adaylar or ADAY_FOURCC
    calisan = {}
    toplam = len(adaylar) * len(fourcc_adaylar)
    sayac = 0
    cap = cv2.VideoCapture(indeks, backend_id)
    if not cap.isOpened():
        return []
    try:
        for fcc in fourcc_adaylar:
            for (w, h) in adaylar:
                sayac += 1
                if ilerleme:
                    ilerleme(sayac, toplam, f"{w}x{h} {fcc}")
                try:
                    cap.set(cv2.CAP_PROP_FOURCC,
                            cv2.VideoWriter_fourcc(*fcc))
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
                    r, kare = cap.read()
                    if not r or kare is None or not kare.size:
                        continue
                    gh, gw = kare.shape[:2]
                    if (gw, gh) != (w, h):
                        continue              # surucu baska boyuta dustu
                    fps = float(cap.get(cv2.CAP_PROP_FPS)) or 0.0
                    anahtar = (gw, gh)
                    # ayni cozunurluk iki bicimde de calisiyorsa
                    # ilkini (MJPG) tut
                    if anahtar not in calisan:
                        calisan[anahtar] = {
                            "genislik": gw, "yukseklik": gh,
                            "fourcc": fcc, "fps": round(fps, 1)}
                except Exception:
                    continue
    finally:
        cap.release()
    return [calisan[k] for k in sorted(calisan)]


def ortak_cozunurlukler(liste_a, liste_b):
    """Iki kameranin ORTAK destekledigi cozunurlukler.

    Stereo icin iki kamera ayni cozunurlukte calismali; farkli
    cozunurlukte kalibrasyon matrisleri uyusmaz.
    """
    a = {(r["genislik"], r["yukseklik"]): r for r in liste_a}
    b = {(r["genislik"], r["yukseklik"]): r for r in liste_b}
    ortak = sorted(set(a) & set(b))
    return [{"genislik": w, "yukseklik": h,
             "fourcc": a[(w, h)]["fourcc"],
             "fps": min(a[(w, h)]["fps"], b[(w, h)]["fps"])}
            for (w, h) in ortak]


def kamera_ac(indeks: int, backend_id: int, genislik: int, yukseklik: int,
              fourcc: str = "MJPG"):
    """Kamerayi istenen ayarla ac ve GERCEKTEN oyle acildigini dogrula.

    Donen: (cap, gercek_genislik, gercek_yukseklik) ya da
           (None, 0, 0) acilamadiysa.
    """
    cap = cv2.VideoCapture(indeks, backend_id)
    if not cap.isOpened():
        return None, 0, 0
    try:
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, genislik)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, yukseklik)
        # tampondaki eski kareleri at
        for _ in range(3):
            cap.read()
        r, kare = cap.read()
        if not r or kare is None:
            cap.release()
            return None, 0, 0
        gh, gw = kare.shape[:2]
        return cap, gw, gh
    except Exception:
        cap.release()
        return None, 0, 0


def netlik_skoru(gri) -> float:
    """Laplacian varyansi - odak kontrolu icin.

    Odak bozuldukca yuksek frekans icerik kaybolur ve varyans duser.
    Mutlak bir esik yoktur; ayni sahnede iki kamerayi ya da zaman
    icinde ayni kamerayi KARSILASTIRMAK icin kullanilir.
    """
    return float(cv2.Laplacian(gri, cv2.CV_64F).var())


def kare_parlakligi(gri):
    """(ortalama, standart sapma) - pozlama ayari icin.

    Hedef bant 90-150: altinda goruntu karanlik, ustunde doymaya
    baslar. Doymus goruntude doku kalmadigi icin stereo esleme
    calisamaz.
    """
    return float(gri.mean()), float(gri.std())
