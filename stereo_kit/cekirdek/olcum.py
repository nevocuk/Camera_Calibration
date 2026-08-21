"""Nesne olcumu - tiklanan cismi ayirip 3B boyutlarini cikar.

Iki segmentasyon yontemi sunulur. Ikisi de gercek olcumle
karsilastirilarak secildi:

  "tolerans"  - tiklanan noktayla AYNI derinlikteki komsulari al.
                Cisim goruntu duzlemine paralel uzaniyorsa iyi calisir.
  "watershed" - gradyan sirtlarini kullanir; cisim bakis dogrultusunda
                uzaniyorsa (orn. ayakta duran uzun cisme tepeden
                bakiliyorsa) tolerans yontemi cismin ancak bir dilimini
                yakalarken watershed tamamini alir.

SECIM KURALI: cisim goruntude uzun gorunuyorsa "tolerans", kisa
gorunuyor ama gercekte uzunsa (yani kameraya dogru uzaniyorsa)
"watershed" dene. Sonucu her zaman GORSELLE dogrula.
"""
from __future__ import annotations

import numpy as np
import cv2


def _pca_kutu(noktalar, alt_yuzde=1, ust_yuzde=99):
    """Nokta bulutuna YONLU sinir kutusu.

    Neden PCA: cisim goruntu eksenlerine hizali olmak zorunda degil.
    SVD nokta bulutunun kendi dogal eksenlerini bulur, kutu cisme oturur.

    Neden %1/%99: tek bir aykiri nokta min/max kutusunu uzatir.
    """
    orta = noktalar.mean(axis=0)
    Q = noktalar - orta
    _, _, Vt = np.linalg.svd(Q, full_matrices=False)
    pr = Q @ Vt.T
    alt = np.percentile(pr, alt_yuzde, axis=0)
    ust = np.percentile(pr, ust_yuzde, axis=0)
    boy = ust - alt
    koseler = []
    for i in (0, 1):
        for j in (0, 1):
            for k in (0, 1):
                koseler.append([ust[0] if i else alt[0],
                                ust[1] if j else alt[1],
                                ust[2] if k else alt[2]])
    return boy, np.array(koseler) @ Vt + orta, Vt, orta, pr


def segmentle_tolerans(dsp, pts, gri, sx, sy, tolerans_mm=30.0,
                       parlaklik_tol=35, sinir_mm=300.0,
                       f_px=None, baz_mm=None):
    """Derinlik toleransiyla bolge buyutme.

    tolerans_mm DERINLIK toleransidir, disparity degil. Mesafeye gore
    otomatik cevrilir:  dd = f * B * dZ / Z^2

    Neden mesafeye gore: sabit bir disparity toleransi yakinda dogru
    calisirken uzakta cok genis bir derinlik araligini kapsar (ayni
    6 piksel, 730 mm'de 63 mm, 1750 mm'de 365 mm eder).

    parlaklik_tol: tiklanan pikselin gri degerinden bu kadardan fazla
    sapan pikseller elenir. Cisimle zemin ayni renkteyse ise yaramaz;
    0 vererek kapatilir.

    sinir_mm: tiklanan noktadan 3B kus ucusu uzaklik siniri. Bolgenin
    sahnenin yarisina yayilmasini yapisal olarak engeller. Cismin en
    uzun kenarindan BUYUK secilmeli (yaricap oldugu icin).
    """
    if dsp[sy, sx] <= 0:
        return None, "Tikladigin noktada derinlik olculememis"
    Z0 = float(pts[sy, sx, 2])
    if not np.isfinite(Z0) or Z0 <= 0:
        return None, "Tikladigin noktanin derinligi gecersiz"

    calis = dsp
    if parlaklik_tol > 0:
        calis = dsp.copy()
        fark = np.abs(gri.astype(np.float32) - float(gri[sy, sx]))
        calis[fark > parlaklik_tol] = 0
        if calis[sy, sx] <= 0:
            calis = dsp                      # tohum elendi, filtreyi atla

    if f_px and baz_mm:
        tol = float(np.clip(f_px * baz_mm * tolerans_mm / (Z0 * Z0),
                            0.5, 60.0))
    else:
        tol = 6.0

    im = calis.astype(np.float32).copy()
    m0 = np.zeros((dsp.shape[0] + 2, dsp.shape[1] + 2), np.uint8)
    m0[1:-1, 1:-1][calis <= 0] = 1
    cv2.floodFill(im, m0, (sx, sy), 0, loDiff=tol, upDiff=tol,
                  flags=(8 | cv2.FLOODFILL_MASK_ONLY
                         | cv2.FLOODFILL_FIXED_RANGE | (255 << 8)))
    m = (m0[1:-1, 1:-1] == 255) & (calis > 0) & np.isfinite(pts).all(axis=2)
    if sinir_mm:
        m &= np.linalg.norm(pts - pts[sy, sx], axis=2) < sinir_mm
    return _bileseni_sec(m, sx, sy)


def segmentle_watershed(dsp, pts, gri, sx, sy, ic_yaricap=40,
                        dis_yaricap=450, sinir_mm=300.0):
    """Watershed - gradyan sirtlarini kullanan bolge ayirma.

    Isaretciler: tiklanan nokta cevresi = cisim, uzak halka = arka
    plan, arasi = algoritma karar verir.

    Kenar engellerini floodFill'e vermekten farki: floodFill'in
    tutmasi icin engelin HER YERDE kapali olmasi gerekir; tek bir
    boslukta bolge kacar. Watershed'de bu sart yok - her piksel
    gradyan sirtlarini asmadan ulastigi en yakin isaretciye atanir.

    dis_yaricap cismin goruntudeki yaricapindan BUYUK olmali; kucuk
    secilirse arka plan isaretcisi cismin uzerine duser.

    NOT: yalnizca PARLAKLIK uzerinde calisir. Derinligi karistirmak
    sonucu bozar - filtrelenmis derinlik haritasinin kenarlari
    parlaklik kadar keskin degildir.
    """
    H, W = dsp.shape
    yy, xx = np.mgrid[0:H, 0:W]
    r = np.hypot(xx - sx, yy - sy)
    isaret = np.zeros((H, W), np.int32)
    isaret[r <= ic_yaricap] = 1
    isaret[r >= dis_yaricap] = 2
    if not (isaret == 2).any():
        return None, ("Arka plan halkasi goruntunun disinda kaldi - "
                      "dis yaricapi kucult")
    im3 = cv2.cvtColor(cv2.GaussianBlur(gri, (5, 5), 0), cv2.COLOR_GRAY2BGR)
    etiket = isaret.copy()
    cv2.watershed(im3, etiket)
    m = (etiket == 1) & (dsp > 0) & np.isfinite(pts).all(axis=2)
    if sinir_mm and dsp[sy, sx] > 0:
        m &= np.linalg.norm(pts - pts[sy, sx], axis=2) < sinir_mm
    m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_CLOSE,
                         np.ones((7, 7), np.uint8)).astype(bool)
    m &= (dsp > 0)
    return _bileseni_sec(m, sx, sy)


def _bileseni_sec(m, sx, sy, min_px=500):
    """Tiklanan pikseli ICEREN bileseni sec.

    En buyuk bileseni degil - kucuk bir cisme tiklarken yanindaki
    buyuk cisim secilebilirdi.
    """
    n, etiket, ist, _ = cv2.connectedComponentsWithStats(
        m.astype(np.uint8), 8)
    if etiket[sy, sx] > 0:
        m = (etiket == etiket[sy, sx])
    elif n > 1:
        return None, "Tikladigin nokta bolgenin disinda kaldi"
    if m.sum() < min_px:
        return None, f"Bulunan bolge cok kucuk ({int(m.sum())} piksel)"
    return m, None


def olc(dsp, pts, gri, sx, sy, yontem="tolerans", f_px=None,
        baz_mm=None, **ayar):
    """Tiklanan cismi olc.

    Donen: (sonuc_sozlugu, hata_metni)
    sonuc: {uzun, orta, kisa, mesafe, piksel, maske, koseler,
            eksenler, merkez}
    """
    if yontem == "watershed":
        m, hata = segmentle_watershed(
            dsp, pts, gri, sx, sy,
            ic_yaricap=ayar.get("ic_yaricap", 40),
            dis_yaricap=ayar.get("dis_yaricap", 450),
            sinir_mm=ayar.get("sinir_mm", 300.0))
    else:
        m, hata = segmentle_tolerans(
            dsp, pts, gri, sx, sy,
            tolerans_mm=ayar.get("tolerans_mm", 30.0),
            parlaklik_tol=ayar.get("parlaklik_tol", 35),
            sinir_mm=ayar.get("sinir_mm", 300.0),
            f_px=f_px, baz_mm=baz_mm)
    if m is None:
        return None, hata

    P = pts[m]
    boy, koseler, Vt, orta, _ = _pca_kutu(P)
    sirali = sorted(boy, reverse=True)
    return {
        "uzun": float(sirali[0]),
        "orta": float(sirali[1]),
        "kisa": float(sirali[2]),
        "mesafe": float(np.median(P[:, 2])),
        "piksel": int(m.sum()),
        "maske": m,
        "koseler": koseler,
        "eksenler": Vt,
        "merkez": orta,
        "boy_ham": boy,
    }, None


EKSEN_KENARLARI = {
    0: [(0, 4), (1, 5), (2, 6), (3, 7)],
    1: [(0, 2), (1, 3), (4, 6), (5, 7)],
    2: [(0, 1), (2, 3), (4, 5), (6, 7)],
}


def kutu_ciz(gri, sonuc, P1, sx, sy):
    """Olculen kutuyu GORUNTU UZERINE ciz - dogrulama icin.

    Sayilara bakip dogrulugu anlamak guvenilir degil: yanlis bir
    bolge de tesadufen makul sayilar uretebilir. Kutu cismi
    sariyorsa olcum dogru, cevreye tasiyorsa bolge kacmis demektir.

    Her boyutun kenarlari ve kosedeki sayisi AYNI renkte - hangi
    sayinin hangi kenar oldugu tereddutsuz belli olsun diye.
    """
    vis = cv2.cvtColor(gri, cv2.COLOR_GRAY2BGR)
    kont, _ = cv2.findContours(sonuc["maske"].astype(np.uint8),
                               cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(vis, kont, -1, (0, 165, 255), 2)

    X = sonuc["koseler"] / 1000.0
    h = np.hstack([X, np.ones((len(X), 1))])
    p = h @ np.asarray(P1).T
    uv = (p[:, :2] / p[:, 2:3]).astype(int)

    boy = sonuc["boy_ham"]
    sira = list(np.argsort(-np.asarray(boy)))
    RENK = {sira[0]: (80, 255, 80), sira[1]: (255, 220, 60),
            sira[2]: (180, 120, 255)}
    AD = {sira[0]: "UZUN", sira[1]: "ORTA", sira[2]: "KISA"}
    for eks, kenarlar in EKSEN_KENARLARI.items():
        for i, j in kenarlar:
            cv2.line(vis, tuple(uv[i]), tuple(uv[j]), RENK[eks], 3)
    cv2.drawMarker(vis, (sx, sy), (0, 0, 255), cv2.MARKER_CROSS, 40, 3)
    for satir, eks in enumerate(sira):
        yer = (30, 44 + satir * 40)
        cv2.putText(vis, f"{AD[eks]:<5} {boy[eks]:7.1f} mm", yer,
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 6)
        cv2.putText(vis, f"{AD[eks]:<5} {boy[eks]:7.1f} mm", yer,
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, RENK[eks], 2)
    return vis


def kurulum_kontrolu(dsp, pts, f_px=None, tikla=None):
    """Kamera yerlesimi olcum icin uygun mu?

    Iki sey olculur:
      1. Sahnedeki baskin duzlemin normali ile optik eksen arasindaki
         aci. Kameranin yuzeye YANDAN mi TEPEDEN mi baktigini soyler.
      2. Olcum mesafesi.

    Neden onemli: cismin kameraya DOGRU uzanan ekseni olculemez.
    Ayni sistem, ayni ayarlarla, yalnizca yerlesim degistiginde
    sonucun parametre secimine duyarli hale geldigi olculdu.

    Donen: {aci, mesafe, uyarilar[]}
    """
    gec = (dsp > 0) & np.isfinite(pts).all(axis=2)
    if gec.sum() < 20000:
        return {"aci": float("nan"), "mesafe": float("nan"),
                "uyarilar": ["Yeterli derinlik verisi yok"]}
    X = pts[gec]
    rng = np.random.default_rng(0)
    S = X[rng.choice(len(X), min(50000, len(X)), replace=False)]
    en, nn, dd = 0, None, None
    for _ in range(500):
        a, b, c = S[rng.choice(len(S), 3, replace=False)]
        v = np.cross(b - a, c - a)
        L = float(np.linalg.norm(v))
        if L < 1e-9:
            continue
        v = v / L
        e = float(-v @ a)
        s = int((np.abs(S @ v + e) < 6).sum())
        if s > en:
            en, nn, dd = s, v, e
    uyarilar = []
    if nn is None:
        return {"aci": float("nan"), "mesafe": float("nan"),
                "uyarilar": ["Sahnede duzlem bulunamadi"]}
    aci = float(np.degrees(np.arccos(np.clip(abs(float(nn[2])), 0, 1))))
    if tikla is not None and gec[tikla[1], tikla[0]]:
        Z = float(pts[tikla[1], tikla[0], 2])
    else:
        h, w = dsp.shape
        Z = float(pts[h // 2, w // 2, 2]) if gec[h // 2, w // 2] else float("nan")
    if aci < 55:
        uyarilar.append(
            f"Yuzeye TEPEDEN bakiyorsun ({aci:.0f} derece). Ayakta "
            "duran uzun bir cismi olcuyorsan uzun ekseni kameraya "
            "dogru bakiyor ve olculemez. Kamerayi yandan bakacak "
            "sekilde cevir ya da cismi yatir.")
    return {"aci": aci, "mesafe": Z, "uyarilar": uyarilar}
