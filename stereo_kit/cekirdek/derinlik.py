"""Derinlik haritasi uretimi - SGBM + WLS.

Parametrelerin hepsi disaridan ayarlanabilir ve her birinin ne
yaptigi burada yazili. Varsayilan degerler genel amacli secildi;
uygulama arayuzunden degistirilebilir.
"""
from __future__ import annotations

import numpy as np
import cv2


class DerinlikAyarlari:
    """SGBM + WLS parametreleri.

    arama_araligi (numDisparities)
        Kac piksellik kayma araninacagi. EN YAKIN olculebilir mesafeyi
        belirler: Z_min = f * B / arama_araligi. Buyutmek yakini
        gorunur kilar ama maliyeti ve sol kenardaki olu bandi artirir
        (soldaki `arama_araligi` kadar piksel yapisal olarak gecersiz -
        eslesecek referans yok). 16'nin kati olmali.

    blok (blockSize)
        Esleme penceresi. Kucuk = ince ayrinti ama gurultulu.
        Buyuk = yumusak ama ince yapiyi kaybeder. Tek sayi olmali.

    ceza_1 / ceza_2 (P1 / P2)
        Komsu pikseller arasindaki disparity farkina verilen ceza.
        Dusurmek daha az yumusaklastirma, yani daha cok gurultu
        demektir - ozellikle dusuk isikta. Genelde blok boyutuna
        bagli olarak 8*3*blok^2 ve 32*3*blok^2 secilir.

    benzersizlik (uniquenessRatio)
        En iyi eslesme, ikinciden bu oran kadar iyi degilse eslesme
        REDDEDILIR. Dusurmek dokusuz bolgelerde belirsiz eslesmeleri
        kabul etmek demektir.

    wls_lambda / wls_sigma
        Sonrasi filtre. Kenarlari goruntu kenarlarina hizalar ve
        bosluklari doldurur.
    """

    def __init__(self, arama_araligi=128, arama_basi=0, blok=7,
                 benzersizlik=15, benek_pencere=200, benek_araligi=2,
                 wls_lambda=8000.0, wls_sigma=1.5,
                 ton_esleme="histogram", temizle=True):
        self.arama_araligi = int(arama_araligi)
        self.arama_basi = int(arama_basi)
        self.blok = int(blok)
        self.benzersizlik = int(benzersizlik)
        self.benek_pencere = int(benek_pencere)
        self.benek_araligi = int(benek_araligi)
        self.wls_lambda = float(wls_lambda)
        self.wls_sigma = float(wls_sigma)
        self.ton_esleme = ton_esleme     # "histogram" | "dogrusal" | "yok"
        self.temizle = bool(temizle)

    def en_yakin_mesafe(self, f_px, baz_mm):
        """Bu ayarla olculebilen EN YAKIN mesafe (mm)."""
        toplam = self.arama_basi + self.arama_araligi
        return f_px * baz_mm / toplam if toplam else float("inf")

    def olu_kenar_yuzde(self, genislik):
        """Sol kenarda yapisal olarak gecersiz kalan bant (%)."""
        return (self.arama_basi + self.arama_araligi) / genislik * 100.0


def _sgbm_kur(a: DerinlikAyarlari):
    b = max(3, a.blok | 1)                 # tek sayi olmali
    nd = max(16, (a.arama_araligi // 16) * 16)
    return cv2.StereoSGBM_create(
        minDisparity=a.arama_basi, numDisparities=nd, blockSize=b,
        P1=8 * 3 * b * b, P2=32 * 3 * b * b, disp12MaxDiff=1,
        uniquenessRatio=a.benzersizlik,
        speckleWindowSize=a.benek_pencere, speckleRange=a.benek_araligi,
        preFilterCap=63, mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY)


def ton_esle(sol, sag, yontem="histogram"):
    """Iki kameranin parlaklik/ton farkini gider.

    NEDEN GEREKLI: iki kamera ayni sahneyi farkli tonda gorebilir
    (sensor/ISP farki). Blok esleme "ayni nokta iki goruntude ayni
    parlaklikta gorunur" varsayimina dayanir.

    "dogrusal" ortalamayi ve sacilimi esitler ama DAGILIM farkini
    birakir; ton egrisi farki dogrusal olmadigi icin genelde
    "histogram" (CDF eslemesi) daha iyi sonuc verir.
    """
    if yontem == "yok":
        return sag
    if yontem == "dogrusal":
        ml, sl = float(sol.mean()), float(sol.std())
        mr, sr = float(sag.mean()), float(sag.std())
        if sr < 1e-6:
            return sag
        d = (sag.astype(np.float32) - mr) * (sl / sr) + ml
        return np.clip(d, 0, 255).astype(np.uint8)
    # histogram: sag goruntunun CDF'ini solunkine esle
    hl = cv2.calcHist([sol], [0], None, [256], [0, 256]).ravel()
    hr = cv2.calcHist([sag], [0], None, [256], [0, 256]).ravel()
    if hl.sum() < 1 or hr.sum() < 1:
        return sag
    cl = np.cumsum(hl) / hl.sum()
    cr = np.cumsum(hr) / hr.sum()
    esleme = np.interp(cr, cl, np.arange(256)).astype(np.uint8)
    return esleme[sag]


def temizle_harita(dsp, min_alan=500):
    """Median + morfolojik kapama + kucuk bolge silme.

    SIRA ONEMLI: once nokta gurultusu gider, sonra kalan bolgelerin
    delikleri kapanir, en son izole yamalar atilir. Ters sirada kucuk
    gurultu yamalari birlesip "buyuk bolge" gibi gorunurdu.
    """
    maske = dsp > 0
    dsp = np.where(maske, cv2.medianBlur(dsp, 5), 0)
    cek = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    kapali = cv2.morphologyEx(maske.astype(np.uint8), cv2.MORPH_CLOSE, cek)
    n, etiket, ist, _ = cv2.connectedComponentsWithStats(kapali, 8)
    for i in range(1, n):
        if ist[i, cv2.CC_STAT_AREA] < min_alan:
            dsp[etiket == i] = 0
    dsp[kapali == 0] = 0
    return dsp


class DerinlikMotoru:
    """Rektifiye gri cift -> disparity haritasi.

    ham_maske: WLS DOLDURMADAN once gercekten eslesen pikseller.
    Kalite olcusu BUDUR; WLS sonrasi maske her yeri dolu gosterdigi
    icin yaniltir.
    """

    def __init__(self, ayarlar: DerinlikAyarlari | None = None):
        self.ayarlar = ayarlar or DerinlikAyarlari()
        self._kur()

    def _kur(self):
        self.sgbm = _sgbm_kur(self.ayarlar)
        self.sag_esleyici = cv2.ximgproc.createRightMatcher(self.sgbm)
        self.wls = cv2.ximgproc.createDisparityWLSFilter(self.sgbm)
        self.wls.setLambda(self.ayarlar.wls_lambda)
        self.wls.setSigmaColor(self.ayarlar.wls_sigma)

    def ayarla(self, ayarlar: DerinlikAyarlari):
        self.ayarlar = ayarlar
        self._kur()

    def hesapla(self, gri_sol, gri_sag):
        """Donen: (disparity_float32, ham_maske_bool)"""
        a = self.ayarlar
        sag = ton_esle(gri_sol, gri_sag, a.ton_esleme)
        sol = cv2.GaussianBlur(gri_sol, (3, 3), 0)
        sag = cv2.GaussianBlur(sag, (3, 3), 0)
        dl = self.sgbm.compute(sol, sag)
        dr = self.sag_esleyici.compute(sag, sol)
        ham_maske = dl > 0
        dsp = self.wls.filter(dl, sol, disparity_map_right=dr)
        dsp = dsp.astype(np.float32) / 16.0
        dsp[dsp <= 0] = 0
        if a.temizle:
            dsp = temizle_harita(dsp)
        return dsp, ham_maske


def noktalar_3b(dsp, Q, mm=True):
    """Disparity -> 3B nokta bulutu. Q metre biriminde oldugu icin
    varsayilan olarak 1000 ile carpip mm veriyoruz."""
    p = cv2.reprojectImageTo3D(dsp.astype(np.float32), Q)
    return p * 1000.0 if mm else p


def renklendir(dsp, z_min=None, z_max=None, f_px=None, baz_mm=None,
               harita=cv2.COLORMAP_JET):
    """Disparity haritasini renklendirin.

    z_min/z_max verilirse olcek SABIT olur ve renkler kareler arasi
    karsilastirilabilir; verilmezse kare bazli olceklenir.
    """
    gecerli = dsp > 0
    if (z_min and z_max and f_px and baz_mm):
        d_max = f_px * baz_mm / max(z_min, 1e-6)
        d_min = f_px * baz_mm / max(z_max, 1e-6)
        n = np.clip((dsp - d_min) / max(d_max - d_min, 1e-6) * 255, 0, 255)
    else:
        m = float(dsp.max()) or 1.0
        n = np.clip(dsp / m * 255, 0, 255)
    renk = cv2.applyColorMap(n.astype(np.uint8), harita)
    renk[~gecerli] = (0, 0, 0)
    return renk
