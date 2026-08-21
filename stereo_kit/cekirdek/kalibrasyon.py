"""Stereo kalibrasyon - HERHANGI bir ChArUco ya da satranc tahtasi ile.

Tahta parametreleri disaridan verilir; hicbir sey sabit degil.
Kullanici kendi bastigi deseni olcup girer.

KRITIK: kare boyu MUTLAKA kumpasla/cetvelle OLCULMELI. Yazicidan
cikan desen neredeyse hicbir zaman tasarim olcusunde degildir
(olcekleme, kenar bosluklari). Bu deger yanlissa TUM olcumler ayni
oranda kayar ve hata sistemin icinden fark edilemez.
"""
from __future__ import annotations

import os

import numpy as np
import cv2


class TahtaTanimi:
    """Kalibrasyon deseninin tanimi.

    tur          : "charuco" ya da "satranc"
    kare_x/y     : KARE sayisi (satrancta ic kose sayisi degil - kare)
    kare_mm      : bir karenin OLCULEN kenar uzunlugu (mm)
    marker_mm    : ChArUco'da isaretin olculen kenari (mm)
    sozluk       : ChArUco sozluk adi, orn. "DICT_4X4_100"
    eski_desen   : calib.io gibi araclarla uretilmis eski duzen icin
    """

    def __init__(self, tur="charuco", kare_x=9, kare_y=13, kare_mm=20.0,
                 marker_mm=15.0, sozluk="DICT_4X4_100", eski_desen=True):
        self.tur = tur
        self.kare_x = int(kare_x)
        self.kare_y = int(kare_y)
        self.kare_mm = float(kare_mm)
        self.marker_mm = float(marker_mm)
        self.sozluk = sozluk
        self.eski_desen = bool(eski_desen)

    # ---- ic kose izgarasi: satrancta kose sayisi kare sayisindan 1 az
    @property
    def ic_kose(self):
        return (self.kare_x - 1, self.kare_y - 1)

    @property
    def maks_kose(self):
        return self.ic_kose[0] * self.ic_kose[1]

    def sozluk_nesnesi(self):
        if not hasattr(cv2.aruco, self.sozluk):
            raise ValueError(f"Bilinmeyen ArUco sozlugu: {self.sozluk}")
        return cv2.aruco.getPredefinedDictionary(
            getattr(cv2.aruco, self.sozluk))

    def olustur(self):
        """(board, detector) dondur. Satrancta board None olur."""
        if self.tur == "satranc":
            return None, None
        board = cv2.aruco.CharucoBoard(
            (self.kare_x, self.kare_y),
            self.kare_mm / 1000.0,        # METRE - bkz. asagidaki not
            self.marker_mm / 1000.0,
            self.sozluk_nesnesi())
        if self.eski_desen:
            try:
                board.setLegacyPattern(True)
            except Exception:
                pass
        return board, cv2.aruco.CharucoDetector(board)

    def sozluge(self):
        return {"tur": self.tur, "kare_x": self.kare_x,
                "kare_y": self.kare_y, "kare_mm": self.kare_mm,
                "marker_mm": self.marker_mm, "sozluk": self.sozluk,
                "eski_desen": self.eski_desen}

    @staticmethod
    def sozlukten(d):
        return TahtaTanimi(**d)


# BIRIM NOTU: tahta olculeri METREYE cevrilerek veriliyor. Bunun
# sonucu olarak stereoCalibrate'ten donen T (baz) metre, Q matrisi
# metre ve reprojectImageTo3D ciktisi metre olur. Milimetre isteyen
# her yerde 1000 ile carpilir. Karisiklik olmasin diye bu tek yerde
# yapiliyor.


def kose_bul(gri, tahta: TahtaTanimi, board, detector):
    """Bir karede kalibrasyon koselerini bul.

    Donen: (obj_pts, img_pts, kimlikler, kose_sayisi)

    KIMLIKLER NEDEN GEREKLI: stereo kalibrasyon icin iki goruntude
    AYNI fiziksel noktalar gerekir. ChArUco her karede farkli sayida
    kose bulabilir (tahtanin bir kismi bir kamerada gorunmeyebilir);
    yalnizca sayilari karsilastirmak yanlis eslestirmeye yol acar ya
    da kareyi bosuna eler. Kose kimlikleri uzerinden kesisim almak
    gerekiyor.
    """
    if tahta.tur == "satranc":
        nx, ny = tahta.ic_kose
        ok, kose = cv2.findChessboardCorners(
            gri, (nx, ny),
            cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE)
        if not ok:
            return None, None, None, 0
        kose = cv2.cornerSubPix(
            gri, kose, (11, 11), (-1, -1),
            (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001))
        obj = np.zeros((nx * ny, 3), np.float32)
        obj[:, :2] = np.mgrid[0:nx, 0:ny].T.reshape(-1, 2)
        obj *= tahta.kare_mm / 1000.0
        # satrancta tum kosler her zaman ayni sirada bulunur; kimlik
        # olarak sira numarasi yeterli
        kimlik = np.arange(nx * ny, dtype=np.int32)
        return obj.reshape(-1, 1, 3), kose, kimlik, len(kose)

    cc, ci, _, _ = detector.detectBoard(gri)
    if cc is None or ci is None or len(cc) < 6:
        return None, None, None, 0 if cc is None else len(cc)
    obj, img = board.matchImagePoints(cc, ci)
    if obj is None or len(obj) < 6:
        return None, None, None, len(cc)
    return obj, img, np.asarray(ci).ravel().astype(np.int32), len(cc)


def stereo_kalibre(ciftler, goruntu_boyu, tahta: TahtaTanimi,
                   ilerleme=None):
    """Kare ciftlerinden stereo kalibrasyon.

    ciftler: [(gri_sol, gri_sag), ...]
    Donen  : (sonuc_sozlugu, hata_metni)

    UC ADIM:
      1. Her kamera AYRI kalibre edilir (K, D bulunur)
      2. Stereo kalibrasyon YALNIZCA R ve T arar (CALIB_FIX_INTRINSIC)
      3. Rektifikasyon haritalari cikarilir

    Neden 2. adimda intrinsikler sabitleniyor: hepsini birlikte
    serbest birakmak parametreleri birbirine karistirir ve cozum
    kararsizlasir. Tekli kalibrasyonlar K ve D'yi zaten iyi cozuyor.
    """
    board, detector = tahta.olustur()
    obj_l, img_l, obj_r, img_r, ortak_obj, ortak_l, ortak_r = \
        [], [], [], [], [], [], []

    for i, (gl, gr) in enumerate(ciftler):
        if ilerleme:
            ilerleme(i + 1, len(ciftler), f"kare {i+1} inceleniyor")
        ol, il, kl, nl = kose_bul(gl, tahta, board, detector)
        orr, ir, kr, nr = kose_bul(gr, tahta, board, detector)
        if ol is not None:
            obj_l.append(ol)
            img_l.append(il)
        if orr is not None:
            obj_r.append(orr)
            img_r.append(ir)
        # STEREO: iki goruntude de bulunan koseleri KIMLIK uzerinden
        # kesistir. Sayilari karsilastirmak yanlis - ChArUco her
        # goruntude farkli sayida kose bulabilir.
        if ol is None or orr is None:
            continue
        sol_h = {int(k): (ol[j], il[j]) for j, k in enumerate(kl)}
        sag_h = {int(k): ir[j] for j, k in enumerate(kr)}
        ortak_k = sorted(set(sol_h) & set(sag_h))
        if len(ortak_k) < 6:
            continue
        ortak_obj.append(np.array([sol_h[k][0] for k in ortak_k],
                                  dtype=np.float32).reshape(-1, 1, 3))
        ortak_l.append(np.array([sol_h[k][1] for k in ortak_k],
                                dtype=np.float32).reshape(-1, 1, 2))
        ortak_r.append(np.array([sag_h[k] for k in ortak_k],
                                dtype=np.float32).reshape(-1, 1, 2))

    if len(obj_l) < 5 or len(obj_r) < 5:
        return None, (f"Yeterli kare yok - sol {len(obj_l)}, "
                      f"sag {len(obj_r)} karede desen bulundu. "
                      "En az 5 gerekli, 15-25 onerilir.")
    if len(ortak_obj) < 5:
        return None, (f"Iki kamerada AYNI anda desen goren kare sayisi "
                      f"yetersiz ({len(ortak_obj)}). Tahtanin iki "
                      "goruntude de TAM gorundugunden emin ol.")

    if ilerleme:
        ilerleme(0, 0, "sol kamera kalibre ediliyor")
    rms1, K1, D1, _, _ = cv2.calibrateCamera(
        obj_l, img_l, goruntu_boyu, None, None)
    if ilerleme:
        ilerleme(0, 0, "sag kamera kalibre ediliyor")
    rms2, K2, D2, _, _ = cv2.calibrateCamera(
        obj_r, img_r, goruntu_boyu, None, None)

    if ilerleme:
        ilerleme(0, 0, "stereo cozuluyor")
    olcut = (cv2.TERM_CRITERIA_MAX_ITER + cv2.TERM_CRITERIA_EPS, 100, 1e-5)
    rms, K1, D1, K2, D2, R, T, E, F = cv2.stereoCalibrate(
        ortak_obj, ortak_l, ortak_r, K1, D1, K2, D2, goruntu_boyu,
        criteria=olcut, flags=cv2.CALIB_FIX_INTRINSIC)

    R1, R2, P1, P2, Q, roi1, roi2 = cv2.stereoRectify(
        K1, D1, K2, D2, goruntu_boyu, R, T,
        flags=cv2.CALIB_ZERO_DISPARITY, alpha=0)

    sonuc = {
        "K1": K1, "D1": D1, "K2": K2, "D2": D2,
        "R": R, "T": T, "E": E, "F": F,
        "R1": R1, "R2": R2, "P1": P1, "P2": P2, "Q": Q,
        "image_size": np.array(goruntu_boyu),
        "rms": np.array(rms), "rms1": np.array(rms1), "rms2": np.array(rms2),
        "baseline_mm": np.array(float(np.linalg.norm(T)) * 1000.0),
        "kare_sayisi": np.array(len(ortak_obj)),
        "tahta_kare_mm": np.array(tahta.kare_mm),
    }
    return sonuc, None


def epipolar_hata(sonuc, ciftler, tahta: TahtaTanimi):
    """Kalibrasyonun GERCEK kalite olcutu.

    Rektifikasyondan sonra ayni fiziksel nokta iki goruntude AYNI
    satirda cikmali. Bu fonksiyon o satir farkinin medyanini olcer.

    NEDEN RMS YETMEZ: RMS, modelin kendi verisine ne kadar uydugunu
    olcer. Veri setinden zor kareleri atarak RMS dusurulebilir ama bu
    kalibrasyonu iyilestirmez - yalnizca sinavi kolaylastirir.
    Epipolar hata bagimsiz bir olcuttur.

    Donen: (medyan_px, olculen_kose_sayisi) ya da (nan, 0)
    """
    board, detector = tahta.olustur()
    boyut = tuple(int(v) for v in sonuc["image_size"])
    m1x, m1y = cv2.initUndistortRectifyMap(
        sonuc["K1"], sonuc["D1"], sonuc["R1"], sonuc["P1"],
        boyut, cv2.CV_32FC1)
    m2x, m2y = cv2.initUndistortRectifyMap(
        sonuc["K2"], sonuc["D2"], sonuc["R2"], sonuc["P2"],
        boyut, cv2.CV_32FC1)
    farklar = []
    for gl, gr in ciftler:
        rl = cv2.remap(gl, m1x, m1y, cv2.INTER_LINEAR)
        rr = cv2.remap(gr, m2x, m2y, cv2.INTER_LINEAR)
        if tahta.tur == "satranc":
            nx, ny = tahta.ic_kose
            okl, kl = cv2.findChessboardCorners(rl, (nx, ny))
            okr, kr = cv2.findChessboardCorners(rr, (nx, ny))
            if not (okl and okr):
                continue
            farklar += list(np.abs(kl.reshape(-1, 2)[:, 1]
                                   - kr.reshape(-1, 2)[:, 1]))
        else:
            ccl, cil, _, _ = detector.detectBoard(rl)
            ccr, cir, _, _ = detector.detectBoard(rr)
            if ccl is None or ccr is None or cil is None or cir is None:
                continue
            hl = {int(k): p for k, p in zip(cil.ravel(), ccl.reshape(-1, 2))}
            hr = {int(k): p for k, p in zip(cir.ravel(), ccr.reshape(-1, 2))}
            for k in set(hl) & set(hr):
                farklar.append(abs(float(hl[k][1]) - float(hr[k][1])))
    if not farklar:
        return float("nan"), 0
    return float(np.median(farklar)), len(farklar)


def kaydet(sonuc, yol):
    os.makedirs(os.path.dirname(yol) or ".", exist_ok=True)
    np.savez(yol, **sonuc)
    return yol


def yukle(yol):
    if not os.path.exists(yol):
        return None
    with np.load(yol) as z:
        return {k: z[k] for k in z.files}


def rektifikasyon_haritalari(sonuc):
    boyut = tuple(int(v) for v in sonuc["image_size"])
    m1x, m1y = cv2.initUndistortRectifyMap(
        sonuc["K1"], sonuc["D1"], sonuc["R1"], sonuc["P1"],
        boyut, cv2.CV_32FC1)
    m2x, m2y = cv2.initUndistortRectifyMap(
        sonuc["K2"], sonuc["D2"], sonuc["R2"], sonuc["P2"],
        boyut, cv2.CV_32FC1)
    return m1x, m1y, m2x, m2y


def ozet(sonuc):
    """Kalibrasyon sonucundan insan okunur ozet + TUREV degerler."""
    f = float(sonuc["P1"][0, 0])
    B = float(np.linalg.norm(sonuc["T"])) * 1000.0
    W, H = [int(v) for v in sonuc["image_size"]]
    return {
        "cozunurluk": f"{W} x {H}",
        "baz_mm": B,
        "f_rektifiye_px": f,
        "f_ham_px": float(sonuc["K1"][0, 0]),
        "rms": float(sonuc["rms"]),
        "rms_sol": float(sonuc["rms1"]),
        "rms_sag": float(sonuc["rms2"]),
        "kare_sayisi": int(sonuc["kare_sayisi"]),
        # mesafeye gore 1 piksellik derinlik hatasi: dZ = Z^2/(f*B)
        "derinlik_adimi": {Z: Z * Z / (f * B) for Z in
                           (300, 500, 700, 1000, 1500)},
    }
