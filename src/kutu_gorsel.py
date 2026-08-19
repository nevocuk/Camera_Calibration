"""Olculen 3B kutuyu GORUNTU UZERINE cizer - dogrulama icin.

Sayilara bakip "dogru mu" demek zor. Kutuyu cismin uzerine cizince
hata aninda gorunur: kutu termosu sariyorsa olcum dogru, masaya
tasiyorsa bolge kacmis demektir.

Uc panel uretir:
  1. Sol goruntu + bolge konturu + 3B kutu tel kafesi
  2. USTTEN gorunum (ana eksen 1-2 duzlemi)  - nokta bulutu
  3. YANDAN gorunum (ana eksen 1-3 duzlemi)

Kullanim:
  .\calistir.ps1 kutu_gorsel --nokta 1250,1150
  .\calistir.ps1 kutu_gorsel --nokta 1250,1150 --sinir 250
  .\calistir.ps1 kutu_gorsel --nokta 1250,1150 --zemin
"""
import argparse
import glob
import os
import sys

import numpy as np
import cv2

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
CAP_DIR = os.path.join(PROJECT_DIR, "output", "depth_captures")
CALIB = os.path.join(PROJECT_DIR, "calibration", "calib_result.npz")


def segmentle(dsp, pts, sx, sy, sinir, tol_mm=40.0, f=None, B=None,
              gri=None, gri_tol=0):
    """tol_mm: DERINLIK toleransi (mm). Disparity'ye mesafeye gore cevrilir.

    Sabit disparity toleransi kullanmak YANLIS: olculdu, 6 px 730 mm'de
    63 mm derinlik kapsarken 1750 mm'de 365 mm kapsiyor (5.8 kat). Ayni
    ayar yakinda dogru calisirken uzakta bolgeyi masaya kaciriyor.
    dd = f*B*dZ / Z^2
    """
    H, W = dsp.shape
    if dsp[sy, sx] <= 0:
        return None, "tiklanan noktada disparity yok"
    Z0 = float(pts[sy, sx, 2])
    if not np.isfinite(Z0) or Z0 <= 0:
        return None, "tohum derinligi gecersiz"
    tol = float(f * B * tol_mm / (Z0 * Z0)) if (f and B) else 6.0
    tol = max(0.5, min(tol, 40.0))
    # PARLAKLIK OLCUTU: derinlik tek basina cismi destek yuzeyinden
    # ayirmiyor (tabanda derinlik sicramasi yok). Ama cisim ile yuzeyin
    # RENGI genelde farkli. Olculdu (koyu termos / beyaz masa):
    #   gri tolerans yok -> 340x272 mm (bolge masaya kacmis)
    #   45 -> 262x78 | 35 -> 262x76 | 25 -> 258x70
    #   gercek 250x72x36  => hata %3
    # Cisim ile yuzey ayni renkteyse ise yaramaz; 0 vererek kapatilir.
    if gri is not None and gri_tol > 0:
        dsp = dsp.copy()
        fark = np.abs(gri.astype(np.float32) - float(gri[sy, sx]))
        dsp[fark > gri_tol] = 0
        if dsp[sy, sx] <= 0:
            return None, "tohum parlaklik filtresine takildi"
    m0 = np.zeros((H + 2, W + 2), np.uint8)
    im = dsp.astype(np.float32).copy()
    cv2.floodFill(im, m0, (sx, sy), 0, loDiff=tol, upDiff=tol,
                  flags=(8 | cv2.FLOODFILL_MASK_ONLY
                         | cv2.FLOODFILL_FIXED_RANGE | (255 << 8)))
    m = m0[1:-1, 1:-1].astype(bool) & (dsp > 0) & np.isfinite(pts).all(axis=2)
    tohum = pts[sy, sx]
    if sinir and np.isfinite(tohum).all():
        m &= np.linalg.norm(pts - tohum, axis=2) < sinir
    n, lab, st, _ = cv2.connectedComponentsWithStats(m.astype(np.uint8), 8)
    if lab[sy, sx] > 0:
        m = (lab == lab[sy, sx])
    elif n > 1:
        m = (lab == int(np.argmax(st[1:, cv2.CC_STAT_AREA])) + 1)
    if m.sum() < 500:
        return None, f"bolge cok kucuk ({int(m.sum())} px)"
    return m, None


def baskin_duzlemi_at(m, pts, sy, sx, esik=8.0, tur=300):
    """Bolgedeki baskin duzlemi (destek yuzeyi) at. Bkz. camera_test."""
    P3 = pts[m]
    if len(P3) < 1000:
        return m, 0.0
    rng = np.random.default_rng(0)
    en, en_n, en_d = 0, None, None
    for _ in range(tur):
        i = rng.choice(len(P3), 3, replace=False)
        a, b, cc = P3[i]
        nn = np.cross(b - a, cc - a)
        L = float(np.linalg.norm(nn))
        if L < 1e-9:
            continue
        nn = nn / L
        dd = float(-nn @ a)
        say = int((np.abs(P3 @ nn + dd) < esik).sum())
        if say > en:
            en, en_n, en_d = say, nn, dd
    if en_n is None:
        return m, 0.0
    oran = en / len(P3)
    if oran < 0.25:
        return m, oran
    h = np.full(m.shape, 1e9)
    h[m] = np.abs(pts[m] @ en_n + en_d)
    m2 = m & (h >= esik)
    n, lab, st, _ = cv2.connectedComponentsWithStats(m2.astype(np.uint8), 8)
    if lab[sy, sx] > 0:
        m2 = (lab == lab[sy, sx])
        return (m2 if m2.sum() > 300 else m), oran
    # Tohum duzlemin uzerindeydi -> kullanici destek yuzeyine tiklamis
    return None, oran


def zemin_duzlemi(calib):
    """ground_plane.npz -> (normal, d_mm). Eski dosyalar HAM cercevede
    kaydedilmis olabilir; o durumda R1 ile rektifiye cerceveye cevrilir.
    Bkz. PROJE_KONTEXT bolum 6 (koordinat cercevesi uyusmazligi)."""
    yol = os.path.join(PROJECT_DIR, "calibration", "ground_plane.npz")
    if not os.path.exists(yol):
        return None, None, "ground_plane.npz yok - once 'Zemin tespit et'"
    g = np.load(yol)
    n = np.asarray(g["normal"], np.float64).ravel()
    n = n / np.linalg.norm(n)
    rekt = ("frame" in g.files and str(g["frame"]) == "rectified")
    if not rekt:
        n = np.asarray(calib["R1"]) @ n
    return n, float(g["d"]) * 1000.0, None


def taban_geri_kazan(boy, alt, ust, Vt, orta, P, n, d_mm):
    """Zemin cikarma esigi cismin ALT kismini de kesiyor (tanim geregi:
    duzlemin esik kadar ustundeki her sey siliniyor). Kesilen band
    olculebilir - bolgenin duzleme en yakin noktasi h_alt kadar yukarida
    kaliyor. Kutuyu duzleme kadar uzatmak bu farki geri verir.

    Duzlem normaline en cok hizali ana ekseni bulup o eksende uzatiyoruz.
    Eksende Delta kadar ilerlemek yuksekligi Delta*(v.n) kadar degistirir,
    yani h_alt'i kapatmak icin Delta = h_alt / |v.n| gerekir.
    """
    h = P @ n + d_mm
    h_alt = float(np.percentile(h, 1))
    if h_alt <= 0:                      # zaten duzleme degiyor
        return boy, alt, ust, 0.0, -1
    cos = np.abs(np.asarray(Vt) @ n)    # her ana eksenin normalle hizasi
    k = int(np.argmax(cos))
    if cos[k] < 0.20:                   # hicbir eksen normale hizali degil
        return boy, alt, ust, 0.0, -1   # uzatma yonu belirsiz, dokunma
    delta = h_alt / cos[k]
    alt = alt.copy(); ust = ust.copy(); boy = boy.copy()
    if float(np.asarray(Vt)[k] @ n) > 0:
        alt[k] -= delta                 # +k yonu yukari -> alcak uc alt[k]
    else:
        ust[k] += delta
    boy[k] += delta
    return boy, alt, ust, delta, k


def kutu_hesapla(P):
    orta = P.mean(axis=0)
    Q = P - orta
    _, _, Vt = np.linalg.svd(Q, full_matrices=False)
    pr = Q @ Vt.T
    alt = np.percentile(pr, 1, axis=0)
    ust = np.percentile(pr, 99, axis=0)
    boy = ust - alt
    # 8 kose (ana eksen uzayinda) -> dunya koordinatina
    koseler = []
    for i in (0, 1):
        for j in (0, 1):
            for k in (0, 1):
                koseler.append([alt[0] if i == 0 else ust[0],
                                alt[1] if j == 0 else ust[1],
                                alt[2] if k == 0 else ust[2]])
    koseler = np.array(koseler) @ Vt + orta
    return boy, koseler, Vt, orta, pr, alt, ust


def koseleri_kur(alt, ust, Vt, orta):
    """alt/ust sinirlarindan 8 koseyi dunya koordinatinda yeniden kur."""
    k = []
    for i in (0, 1):
        for j in (0, 1):
            for t in (0, 1):
                k.append([ust[0] if i else alt[0],
                          ust[1] if j else alt[1],
                          ust[2] if t else alt[2]])
    return np.array(k) @ Vt + orta


def izdusur(X, P1):
    """3B (mm) -> rektifiye goruntu pikseli."""
    Xm = X / 1000.0
    h = np.hstack([Xm, np.ones((len(Xm), 1))])
    p = h @ np.asarray(P1).T
    return p[:, :2] / p[:, 2:3]


KENARLAR = [(0,1),(0,2),(0,4),(1,3),(1,5),(2,3),(2,6),(3,7),
            (4,5),(4,6),(5,7),(6,7)]


def bulut_paneli(pr, eks_a, eks_b, ad_a, ad_b, boyut=520, kenar=40):
    """Nokta bulutunu iki ana eksen duzleminde ciz (mm olcekli)."""
    img = np.full((boyut, boyut, 3), 22, np.uint8)
    a, b = pr[:, eks_a], pr[:, eks_b]
    if len(a) > 30000:
        i = np.random.default_rng(0).choice(len(a), 30000, replace=False)
        a, b = a[i], b[i]
    ra = max(a.max() - a.min(), b.max() - b.min(), 1e-6)
    olcek = (boyut - 2 * kenar) / ra
    ax = ((a - a.mean()) * olcek + boyut / 2).astype(int)
    by = ((b - b.mean()) * olcek + boyut / 2).astype(int)
    ok = (ax >= 0) & (ax < boyut) & (by >= 0) & (by < boyut)
    img[by[ok], ax[ok]] = (90, 220, 90)
    # olcek cubugu: 50 mm
    L = int(50 * olcek)
    cv2.line(img, (kenar, boyut - 20), (kenar + L, boyut - 20), (255,255,255), 2)
    cv2.putText(img, "50 mm", (kenar, boyut - 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255,255,255), 1)
    cv2.putText(img, f"{ad_a} (yatay) x {ad_b} (dikey)", (kenar, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200,200,255), 1)
    cv2.putText(img, f"{a.max()-a.min():.0f} x {b.max()-b.min():.0f} mm",
                (kenar, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (120,220,255), 1)
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dosya", default=None)
    ap.add_argument("--nokta", required=True, help="x,y")
    ap.add_argument("--sinir", type=float, default=250.0)
    ap.add_argument("--duzlem-at", action="store_true",
                    help="baskin duzlemi at - VARSAYILAN KAPALI, bolge "
                         "zaten ince derinlik dilimi oldugu icin genelde "
                         "cismi de siler")
    ap.add_argument("--gri", type=float, default=35.0,
                    help="parlaklik toleransi (0-255). 0 = kapali")
    ap.add_argument("--tol", type=float, default=30.0,
                    help="DERINLIK toleransi (mm) - disparity degil")
    ap.add_argument("--zemin", action="store_true",
                    help="zemin cikarilmis haritayi kullan + kesilen tabani "
                         "geri ekle. Sonucu tol/parlaklik ayarina duyarsiz "
                         "kilar (olculdu: tol 20-60 mm arasi ayni sonuc), "
                         "ama cekim sirasinda zemin cikarma acik olmali.")
    a = ap.parse_args()

    yol = (a.dosya if a.dosya and os.path.isabs(a.dosya)
           else os.path.join(CAP_DIR, a.dosya) if a.dosya
           else sorted(glob.glob(os.path.join(CAP_DIR, "q_*_data.npz")))[-1])
    c = np.load(CALIB)
    z = np.load(yol)
    zn, zd, zhata = (None, None, None)
    if a.zemin:
        acik = ("zemin_cikarildi" in z.files and bool(z["zemin_cikarildi"]))
        if not acik:
            print("HATA: bu cekimde zemin cikarma KAPALIYDI.")
            print("      Derinlik tabinda 'Zemin/masa cikar' isaretli "
                  "olarak [F] ile yeni kare al.")
            return 1
        dsp = z["disparity"].astype(np.float32)
        zn, zd, zhata = zemin_duzlemi(c)
        if zn is None:
            print("HATA:", zhata)
            return 1
    else:
        dsp = z["disparity_ham" if "disparity_ham" in z.files
                else "disparity"].astype(np.float32)
    pts = cv2.reprojectImageTo3D(dsp, c["Q"]) * 1000.0
    sx, sy = [int(float(v)) for v in a.nokta.replace(" ", "").split(",")]

    f_px = float(c['P1'][0, 0])
    B_mm = float(np.linalg.norm(c['T'])) * 1000.0
    m, hata = segmentle(dsp, pts, sx, sy, a.sinir, a.tol,
                        f_px, B_mm, gri=z["gray_l"], gri_tol=a.gri)
    if m is None:
        print("HATA:", hata); return 1
    d_oran = 0.0
    if a.duzlem_at:
        m_yeni, d_oran = baskin_duzlemi_at(m, pts, sy, sx)
        if m_yeni is None:
            print(f"HATA: tiklanan nokta DESTEK YUZEYINDE "
                  f"(bolgenin %{d_oran*100:.0f}'i duzlem).")
            print("      Masaya degil CISMIN uzerine tikla.")
            return 1
        m = m_yeni
    P = pts[m]
    boy, koseler, Vt, orta, pr, alt, ust = kutu_hesapla(P)
    geri, geri_eks = 0.0, -1
    if a.zemin and zn is not None:
        boy, alt, ust, geri, geri_eks = taban_geri_kazan(
            boy, alt, ust, Vt, orta, P, zn, zd)
        if geri > 0:
            koseler = koseleri_kur(alt, ust, Vt, orta)
    s = sorted(boy, reverse=True)

    print("=" * 60)
    print(f"CEKIM  : {os.path.basename(yol)}")
    print(f"TIKLAMA: ({sx},{sy})  sinir {a.sinir:.0f} mm  "
          f"derinlik tol {a.tol:.0f} mm  gri tol {a.gri:.0f}")
    print(f"HARITA : {'zemin cikarilmis' if a.zemin else 'ham (zemin duruyor)'}"
          + (f"  esik {float(z['zemin_esik_mm']):.0f} mm"
             if a.zemin and "zemin_esik_mm" in z.files else ""))
    print("=" * 60)
    if a.zemin:
        if geri > 0:
            print(f"  Taban geri kazanimi: ana eksen {geri_eks + 1}'e "
                  f"+{geri:.1f} mm (kesilen band duzleme kadar uzatildi)")
        elif geri_eks == -1:
            print("  Taban geri kazanimi: uygulanmadi "
                  "(bolge zaten duzleme deger ya da hicbir eksen "
                  "duzlem normaline hizali degil)")
    print(f"  Bolge      : {int(m.sum()):,} px"
          + (f"   (duzlem atildi: %{d_oran*100:.0f})" if d_oran >= 0.25 else ""))
    print(f"  Mesafe     : {np.median(P[:,2]):.0f} mm")
    print(f"  Ana eksen 1: {s[0]:7.1f} mm   (en uzun)")
    print(f"  Ana eksen 2: {s[1]:7.1f} mm")
    print(f"  Ana eksen 3: {s[2]:7.1f} mm   (en kisa = gorunen yuz kalinligi)")

    # --- panel 1: goruntu + kontur + RENK KODLU kutu
    # Her ana eksenin 4 kenari kendi renginde. Sol ustteki olculer de
    # ayni renkte - hangi sayinin hangi kenar oldugu tereddutsuz belli.
    gl = z["gray_l"]
    vis = cv2.cvtColor(gl, cv2.COLOR_GRAY2BGR)
    kont, _ = cv2.findContours(m.astype(np.uint8), cv2.RETR_EXTERNAL,
                               cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(vis, kont, -1, (0, 165, 255), 3)
    uv = izdusur(koseler, c["P1"]).astype(int)

    # kose indisi = i*4 + j*2 + k  (i,j,k = 0/1, eksen 0/1/2)
    EKSEN_KENARLARI = {
        0: [(0, 4), (1, 5), (2, 6), (3, 7)],
        1: [(0, 2), (1, 3), (4, 6), (5, 7)],
        2: [(0, 1), (2, 3), (4, 5), (6, 7)],
    }
    sira = list(np.argsort(-np.asarray(boy)))       # uzundan kisaya
    RENK = {sira[0]: (80, 255, 80),                 # uzun  - yesil
            sira[1]: (255, 220, 60),                # orta  - acik mavi
            sira[2]: (180, 120, 255)}               # kisa  - pembe
    AD = {sira[0]: "UZUN", sira[1]: "ORTA", sira[2]: "KISA"}
    for eks, kenarlar in EKSEN_KENARLARI.items():
        for i, j in kenarlar:
            cv2.line(vis, tuple(uv[i]), tuple(uv[j]), RENK[eks], 4)
    cv2.drawMarker(vis, (sx, sy), (0, 0, 255), cv2.MARKER_CROSS, 60, 4)

    for satir, eks in enumerate(sira):
        cv2.putText(vis, f"{AD[eks]:<5} {boy[eks]:6.1f} mm",
                    (50, 80 + satir * 62), cv2.FONT_HERSHEY_SIMPLEX,
                    1.5, (0, 0, 0), 8)
        cv2.putText(vis, f"{AD[eks]:<5} {boy[eks]:6.1f} mm",
                    (50, 80 + satir * 62), cv2.FONT_HERSHEY_SIMPLEX,
                    1.5, RENK[eks], 4)
    h0 = 760
    vis = cv2.resize(vis, (int(vis.shape[1] * h0 / vis.shape[0]), h0))

    # --- panel 2/3: nokta bulutu iki gorunumden
    p2 = bulut_paneli(pr, 0, 1, "eksen1", "eksen2")
    p3 = bulut_paneli(pr, 0, 2, "eksen1", "eksen3")
    sag = np.vstack([p2, p3])
    sag = cv2.resize(sag, (int(sag.shape[1] * h0 / sag.shape[0]), h0))
    birlesik = np.hstack([vis, sag])

    cikti = yol.replace("_data.npz", f"_kutu_{sx}_{sy}.png")
    cv2.imwrite(cikti, birlesik)
    print(f"\n  Gorsel: {os.path.basename(cikti)}")
    print("  Sol: goruntu + bolge konturu (turuncu) + 3B kutu (yesil)")
    print("  Sag: nokta bulutu iki ana eksen duzleminde")
    return 0


if __name__ == "__main__":
    sys.exit(main())
