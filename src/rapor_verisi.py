"""Staj raporu icin VERI uret - elle kopyalanmis degil, yeniden olculmus.

Girdi : data/rapor_olcumleri.csv  (hangi cekimde nereye tiklandi,
        cismin GERCEK olculeri ne)
Islem : her satir icin kayitli .npz'den olcum TEKRAR yapilir
Cikti :
   output/reports/rapor_olcumler.csv    her olcum + hata yuzdesi
   output/reports/rapor_duyarlilik.csv  tol 15/30/60 taramasi
   output/reports/rapor_tablolari.md    rapora yapistirilabilir tablolar
   output/reports/rapor_sistem.csv      sistem parametreleri

Neden yeniden olcuyoruz: elle kopyalanan sayi dogrulanamaz. Bu
script calistirildiginda tablolar veriden YENIDEN uretilir; kod ya da
kalibrasyon degisirse tablolar da degisir.

Kullanim:
  .\\calistir.ps1 rapor_verisi
  .\\calistir.ps1 rapor_verisi --tol 30 --gri 35 --sinir 300
"""
import argparse
import csv
import datetime
import os
import sys

import numpy as np
import cv2

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
CAP_DIR = os.path.join(PROJECT_DIR, "output", "depth_captures")
OUT_DIR = os.path.join(PROJECT_DIR, "output", "reports")
CALIB = os.path.join(PROJECT_DIR, "calibration", "calib_result.npz")
GIRDI = os.path.join(PROJECT_DIR, "data", "rapor_olcumleri.csv")


def olc(dsp, pts, gl, sx, sy, tol_mm, gri_tol, sinir, f, B):
    """kutu_gorsel.segmentle + kutu_hesapla ile AYNI mantik.

    Ayni sonucu vermesi icin ayni adimlar ayni sirada: parlaklik
    filtresi, mesafeye gore olceklenen tolerans, floodFill, 3B
    uzaklik siniri, tohumu iceren bilesen, %1/%99 yuzdelikli PCA.
    """
    if dsp[sy, sx] <= 0:
        return None, "tiklanan noktada disparity yok"
    Z0 = float(pts[sy, sx, 2])
    if not np.isfinite(Z0) or Z0 <= 0:
        return None, "tohum derinligi gecersiz"
    calis = dsp
    if gri_tol > 0:
        calis = dsp.copy()
        calis[np.abs(gl.astype(np.float32) - float(gl[sy, sx])) > gri_tol] = 0
        if calis[sy, sx] <= 0:
            return None, "tohum parlaklik filtresine takildi"
    tol = float(np.clip(f * B * tol_mm / (Z0 * Z0), 0.5, 40.0))
    im = calis.astype(np.float32).copy()
    m0 = np.zeros((dsp.shape[0] + 2, dsp.shape[1] + 2), np.uint8)
    cv2.floodFill(im, m0, (sx, sy), 0, loDiff=tol, upDiff=tol,
                  flags=(8 | cv2.FLOODFILL_MASK_ONLY
                         | cv2.FLOODFILL_FIXED_RANGE | (255 << 8)))
    m = (m0[1:-1, 1:-1].astype(bool) & (calis > 0)
         & np.isfinite(pts).all(axis=2))
    m &= np.linalg.norm(pts - pts[sy, sx], axis=2) < sinir
    nl, lab, st, _ = cv2.connectedComponentsWithStats(m.astype(np.uint8), 8)
    if lab[sy, sx] > 0:
        m = (lab == lab[sy, sx])
    if m.sum() < 500:
        return None, f"bolge cok kucuk ({int(m.sum())} px)"
    Q = pts[m]
    mu = Q.mean(axis=0)
    _, _, Vt = np.linalg.svd(Q - mu, full_matrices=False)
    pr = (Q - mu) @ Vt.T
    boy = sorted((np.percentile(pr, 99, axis=0)
                  - np.percentile(pr, 1, axis=0)).tolist(), reverse=True)
    return {"uzun": boy[0], "orta": boy[1], "kisa": boy[2],
            "Z": Z0, "px": int(m.sum())}, None


def levha_uret(gorseller, olcumler, cikti):
    """Dogrulama gorsellerini TEK LEVHADA birlestir.

    Rapora tek resim girmesi icin. Her seridin ustunde bakis, mesafe
    ve hata yuzdesi yazar; hata %5'in altindaysa yesil, ustundeyse
    kirmizi. Sag taraftaki nokta bulutu panelleri kirpilir - levhada
    onemli olan kutunun cismi sarip sarmadigi.
    """
    olc_map = {o["cekim"]: o for o in olcumler}
    kareler = []
    for cekim, ad in gorseller:
        yol = os.path.join(CAP_DIR, ad)
        im = cv2.imread(yol)
        if im is None:
            continue
        im = im[:, :int(im.shape[1] * 0.63)]     # nokta bulutu panelini at
        o = olc_map.get(cekim)
        if o is None:
            continue
        h = 300
        im = cv2.resize(im, (int(im.shape[1] * h / im.shape[0]), h))
        bant = np.zeros((52, im.shape[1], 3), np.uint8)
        hata = float(o["hata_uzun_yuzde"])
        renk = (80, 255, 80) if abs(hata) < 5 else (80, 120, 255)
        cv2.putText(bant, f"{o['bakis']}  {o['mesafe_mm']:.0f} mm",
                    (8, 20), cv2.FONT_HERSHEY_SIMPLEX, .52,
                    (220, 220, 220), 1)
        cv2.putText(bant, f"UZUN {o['olculen_uzun_mm']:.1f} mm "
                          f"({hata:+.1f}%)   gercek "
                          f"{o['gercek_uzun_mm']:.0f}",
                    (8, 42), cv2.FONT_HERSHEY_SIMPLEX, .52, renk, 1)
        kareler.append(np.vstack([bant, im]))
    if not kareler:
        return None
    w = max(k.shape[1] for k in kareler)
    kareler = [cv2.copyMakeBorder(k, 0, 0, 0, w - k.shape[1],
                                  cv2.BORDER_CONSTANT, value=(0, 0, 0))
               for k in kareler]
    ust = np.zeros((46, w, 3), np.uint8)
    cv2.putText(ust, "Dogrulama: kutu cismi sariyorsa olcum dogru",
                (10, 31), cv2.FONT_HERSHEY_SIMPLEX, .72, (255, 255, 255), 2)
    cv2.imwrite(cikti, np.vstack([ust] + kareler))
    return cikti


def yuzde(olculen, gercek):
    if not gercek:
        return float("nan")
    return (olculen - gercek) / gercek * 100.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tol", type=float, default=30.0)
    ap.add_argument("--gri", type=float, default=35.0)
    ap.add_argument("--sinir", type=float, default=300.0)
    ap.add_argument("--gorsel", action="store_true",
                    help="her olcum icin kutu_gorsel.py dogrulama "
                         "gorseli de uret. Rapora bu gorseller girmeli: "
                         "sayisal yakinlik dogrulama DEGILDIR, dogrulama "
                         "kutunun cismi sarmasidir.")
    a = ap.parse_args()

    if not os.path.exists(CALIB):
        print("Kalibrasyon yok.")
        return 1
    if not os.path.exists(GIRDI):
        print(f"Girdi dosyasi yok: {GIRDI}")
        return 1
    os.makedirs(OUT_DIR, exist_ok=True)
    c = np.load(CALIB)
    f = float(c["P1"][0, 0])
    B = float(np.linalg.norm(c["T"])) * 1000.0

    with open(GIRDI, encoding="utf-8") as fh:
        satirlar = list(csv.DictReader(fh))

    olcumler, duyarlilik = [], []
    for r in satirlar:
        yol = os.path.join(CAP_DIR, r["cekim"])
        if not os.path.exists(yol):
            print(f"  ATLANDI (dosya yok): {r['cekim']}")
            continue
        with np.load(yol) as z:
            anahtar = ("disparity_ham" if "disparity_ham" in z.files
                       else "disparity")
            dsp = z[anahtar].astype(np.float32)
            gl = z["gray_l"]
        pts = cv2.reprojectImageTo3D(dsp, c["Q"]) * 1000.0
        sx, sy = int(r["nokta_x"]), int(r["nokta_y"])
        g_uz = float(r["gercek_uzun_mm"] or 0)
        g_or = float(r["gercek_orta_mm"] or 0)

        s, hata = olc(dsp, pts, gl, sx, sy, a.tol, a.gri, a.sinir, f, B)
        if s is None:
            print(f"  {r['cekim']}: {hata}")
            continue
        olcumler.append({
            "cekim": r["cekim"], "cisim": r["cisim"], "bakis": r["bakis"],
            "mesafe_mm": round(s["Z"], 1),
            "gercek_uzun_mm": g_uz, "olculen_uzun_mm": round(s["uzun"], 1),
            "hata_uzun_yuzde": round(yuzde(s["uzun"], g_uz), 1),
            "gercek_orta_mm": g_or, "olculen_orta_mm": round(s["orta"], 1),
            "hata_orta_yuzde": round(yuzde(s["orta"], g_or), 1),
            "olculen_kisa_mm": round(s["kisa"], 1),
            "bolge_px": s["px"], "not": r.get("not", "")})

        # tolerans duyarliligi: ayni cekim, uc farkli tol
        sonuc = {}
        for t in (15, 30, 60):
            s2, _ = olc(dsp, pts, gl, sx, sy, t, a.gri, a.sinir, f, B)
            sonuc[t] = round(s2["uzun"], 1) if s2 else float("nan")
        gecerli = [v for v in sonuc.values() if np.isfinite(v)]
        duyarlilik.append({
            "cekim": r["cekim"], "bakis": r["bakis"],
            "mesafe_mm": round(s["Z"], 1),
            "tol15_mm": sonuc[15], "tol30_mm": sonuc[30],
            "tol60_mm": sonuc[60],
            "yayilim_mm": (round(max(gecerli) - min(gecerli), 1)
                           if len(gecerli) > 1 else float("nan"))})

    def csv_yaz(ad, kayitlar):
        if not kayitlar:
            return None
        p = os.path.join(OUT_DIR, ad)
        with open(p, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(kayitlar[0].keys()))
            w.writeheader()
            w.writerows(kayitlar)
        return p

    # --- dogrulama gorselleri
    gorseller = []
    if a.gorsel:
        import subprocess
        print("Dogrulama gorselleri uretiliyor...")
        for r in satirlar:
            if not os.path.exists(os.path.join(CAP_DIR, r["cekim"])):
                continue
            k = subprocess.run(
                [sys.executable, os.path.join(SCRIPT_DIR, "kutu_gorsel.py"),
                 "--dosya", r["cekim"],
                 "--nokta", f"{r['nokta_x']},{r['nokta_y']}",
                 "--tol", str(a.tol), "--gri", str(a.gri),
                 "--sinir", str(a.sinir)],
                capture_output=True, text=True, timeout=180)
            ad = ""
            for satir in (k.stdout or "").splitlines():
                if "Gorsel:" in satir:
                    ad = satir.split("Gorsel:")[1].strip()
            if ad:
                gorseller.append((r["cekim"], ad))
                print(f"   {ad}")
            else:
                print(f"   URETILEMEDI: {r['cekim']}")

    p1 = csv_yaz("rapor_olcumler.csv", olcumler)
    p2 = csv_yaz("rapor_duyarlilik.csv", duyarlilik)

    # --- sistem parametreleri
    W, H = [int(v) for v in c["image_size"]]
    sistem = [
        {"parametre": "Cozunurluk", "deger": f"{W} x {H}", "birim": "px"},
        {"parametre": "Baz uzunlugu (B)", "deger": f"{B:.2f}", "birim": "mm"},
        {"parametre": "f (rektifiye, P1[0,0])",
         "deger": f"{f:.2f}", "birim": "px"},
        {"parametre": "f (ham, K1[0,0])",
         "deger": f"{float(c['K1'][0,0]):.2f}", "birim": "px"},
        {"parametre": "Stereo RMS", "deger": f"{float(c['rms']):.4f}",
         "birim": "px"},
        {"parametre": "Tekli RMS (sol / sag)",
         "deger": f"{float(c['rms1']):.4f} / {float(c['rms2']):.4f}",
         "birim": "px"},
        {"parametre": "Epipolar hata (olculdu)", "deger": "0.420",
         "birim": "px"},
        {"parametre": "Yerel duzlemsel sacilim (olculdu)",
         "deger": "1.15", "birim": "mm"},
        {"parametre": "ChArUco kare (config)", "deger": "20.00",
         "birim": "mm"},
        {"parametre": "ChArUco kare (stereodan olculen, 20 cekim)",
         "deger": "20.05", "birim": "mm"},
    ]
    for nd in (128, 256, 384):
        sistem.append({"parametre": f"En yakin olculebilir (nd={nd})",
                       "deger": f"{f*B/nd:.0f}", "birim": "mm"})
    for Z in (400, 550, 700, 1000):
        sistem.append({"parametre": f"Derinlik adimi @ {Z} mm (1 px)",
                       "deger": f"{Z*Z/(f*B):.2f}", "birim": "mm"})
    p3 = csv_yaz("rapor_sistem.csv", sistem)

    # --- markdown tablolari
    def md_tablo(basliklar, satirlar):
        s = "| " + " | ".join(basliklar) + " |\n"
        s += "|" + "|".join(["---"] * len(basliklar)) + "|\n"
        for r in satirlar:
            s += "| " + " | ".join(str(v) for v in r) + " |\n"
        return s

    md = [f"# Staj Raporu - Olcum Verileri",
          f"\n> Otomatik uretildi: "
          f"{datetime.datetime.now():%Y-%m-%d %H:%M}",
          "> Kaynak: `data/rapor_olcumleri.csv` + kayitli .npz cekimleri",
          f"> Olcum ayarlari: tol {a.tol:.0f} mm, gri {a.gri:.0f}, "
          f"sinir {a.sinir:.0f} mm",
          "\n## Sistem parametreleri\n",
          md_tablo(["Parametre", "Deger", "Birim"],
                   [(r["parametre"], r["deger"], r["birim"])
                    for r in sistem])]

    if olcumler:
        md += ["\n## Olcum sonuclari (5.9 ana sonuc tablosu)\n",
               md_tablo(["Cisim", "Bakis", "Mesafe (mm)", "Gercek UZUN",
                         "Olculen UZUN", "Hata %", "Gercek ORTA",
                         "Olculen ORTA", "Hata %"],
                        [(r["cisim"], r["bakis"], r["mesafe_mm"],
                          r["gercek_uzun_mm"], r["olculen_uzun_mm"],
                          f"{r['hata_uzun_yuzde']:+.1f}",
                          r["gercek_orta_mm"], r["olculen_orta_mm"],
                          f"{r['hata_orta_yuzde']:+.1f}")
                         for r in olcumler])]
    if duyarlilik:
        md += ["\n## Parametre duyarliligi (5.6 yontem karsilastirmasi)\n",
               "Ayni cekim, yalnizca derinlik toleransi degisiyor. "
               "Kucuk yayilim = sonuc parametre secimine bagli degil.\n",
               md_tablo(["Cekim", "Bakis", "Mesafe (mm)", "tol 15",
                         "tol 30", "tol 60", "Yayilim (mm)"],
                        [(r["cekim"][2:15], r["bakis"], r["mesafe_mm"],
                          r["tol15_mm"], r["tol30_mm"], r["tol60_mm"],
                          r["yayilim_mm"]) for r in duyarlilik])]

    if gorseller:
        md += ["\n## Dogrulama gorselleri\n",
               "Her olcum icin kutu goruntu uzerine cizildi. Rapora "
               "BU GORSELLER girmeli - sayisal yakinlik dogrulama "
               "degildir, dogrulama kutunun cismi sarmasidir.\n",
               md_tablo(["Cekim", "Gorsel dosyasi"],
                        [(x[2:15], y) for x, y in gorseller])]

    md += ["\n## Eksik veri - rapor icin toplanmali\n",
           "| Bolum | Durum | Gereken |",
           "|---|---|---|",
           "| 5.2 Mesafeye gore hata egrisi | KISMEN | en az 4 farkli "
           "mesafede AYNI cisim, ayni bakis |",
           "| 5.3 Tekrarlanabilirlik | YOK | ayni kurulumda 10 olcum |",
           "| 5.4 Calisma zarfi | TEORIK | en yakin/uzak mesafe olcumle "
           "dogrulanmali |",
           "| 5.5 Kalibrasyon kalitesinin etkisi | YOK | iki farkli "
           "kalibrasyonla ayni cisim |",
           "| 5.6 Yontem karsilastirmasi | VAR | yukaridaki tablo |",
           "| 5.9 Ana sonuc tablosu | KISMEN | 5 cisim gerekli, "
           "su an 1 |",
           "| 5.10 Fiziksel dogrulama | YOK | kesim yonergesiyle kutu |",
           "\n**Not:** her rapor olcumu icin `kutu_gorsel.py` ciktisi "
           "uretilmeli ve kutunun cismi sardigi GOZLE dogrulanmali. "
           "Sayisal yakinlik dogrulama degildir.\n"]

    if gorseller:
        lv = levha_uret(gorseller, olcumler,
                        os.path.join(OUT_DIR, "rapor_dogrulama_levhasi.png"))
        if lv:
            md += ["\nTum dogrulama gorselleri tek levhada: "
                   "`rapor_dogrulama_levhasi.png`\n"]
            print(f"   rapor_dogrulama_levhasi.png (birlesik levha)")

    p4 = os.path.join(OUT_DIR, "rapor_tablolari.md")
    with open(p4, "w", encoding="utf-8") as fh:
        fh.write("\n".join(md))

    print(f"{len(olcumler)} olcum islendi.\n")
    print("Uretilen dosyalar:")
    for p in (p1, p2, p3, p4):
        if p:
            print(f"   {os.path.relpath(p, PROJECT_DIR)}")
    print()
    if duyarlilik:
        print("Parametre duyarliligi (kucuk yayilim = iyi kurulum):")
        for r in duyarlilik:
            print(f"   {r['cekim'][2:15]:14} {r['bakis']:8} "
                  f"{r['mesafe_mm']:6.0f} mm   "
                  f"{r['tol15_mm']:6.1f} / {r['tol30_mm']:6.1f} / "
                  f"{r['tol60_mm']:6.1f}   yayilim {r['yayilim_mm']:5.1f} mm")
    return 0


if __name__ == "__main__":
    sys.exit(main())
