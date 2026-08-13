"""
Asama O — Sistem Planlama Hesaplayicisi (kalibrasyondan ONCE calistirilir)

Kalibrasyon oncesi cevaplanmasi gereken sorulari sayisal olarak cevaplar:
  - Odak uzakligi kac piksel? Gorus acisi kac derece?
  - Hangi mesafede calisabilirim? (dogruluk + ortak gorus alani + cisim sigmasi)
  - Bu mesafede ChArUco deseni kac mm kare olmali?
  - Mevcut desenim yeterli mi?

KULLANIM:
  1. Asagidaki OLCULEN DEGERLER bolumunu doldur (hepsi elle olculur, kalibrasyon gerekmez)
  2. python sistem_planlama.py

Hicbir donanim gerektirmez, saf hesap. Ciktisi olcum defterine ve rapora girer.
"""
import math
import json
import os

# =============================================================================
# OLCULEN DEGERLER — BURAYI DOLDUR
# =============================================================================

# --- 1) Secilen calisma cozunurlugu (probe_resolutions.py ciktisindan) ---
IMG_W_PX = 1280          # goruntu genisligi (piksel)
IMG_H_PX = 960           # goruntu yuksekligi (piksel)

# --- 2) Cetvel testi: odak uzakligini kalibrasyonsuz kestirmek icin ---
# Kamerayi duz tut, bilinen mesafeye bir cetvel/metre koy.
# Goruntunun SOL kenarindan SAG kenarina kadar kac mm gorunuyor, oku.
RULER_DIST_MM = 500.0    # cetvelin kameraya uzakligi (mm)
RULER_SPAN_MM = 700.0    # goruntu genisliginin kapsadigi mm

# --- 3) Baseline: iki lens merkezi arasi, kumpasla ---
BASELINE_MM = 60.0

# --- 4) Hedefler ---
TARGET_ACCURACY_MM = 3.0     # istenen derinlik dogrulugu
DISPARITY_UNCERT_PX = 0.5    # disparity belirsizligi; ilk tahmin 0.5,
                             # 5.3 tekrarlanabilirlik testinden sonra GERCEK degeri gir
MAX_OBJECT_MM = 350.0        # olculecek en buyuk cismin en uzun kenari
MIN_OVERLAP_RATIO = 0.70     # iki kameranin ortak gormesi gereken minimum alan orani

# --- 5) Mevcut ChArUco deseni ---
CHARUCO_SQUARES_X = 7
CHARUCO_SQUARE_MM = 30.0
CHARUCO_MARKER_RATIO = 22.0 / 30.0   # marker / kare orani
MIN_MARKER_PX = 20.0                 # ArUco marker guvenilir tespiti icin min piksel

# =============================================================================
# HESAP
# =============================================================================

def hesapla():
    # Odak uzakligi (piksel). Pinhole: f_px = W_px * Z / gorunen_genislik
    f_px = IMG_W_PX * RULER_DIST_MM / RULER_SPAN_MM

    # Gorus acilari
    hfov = 2 * math.degrees(math.atan(IMG_W_PX / (2 * f_px)))
    vfov = 2 * math.degrees(math.atan(IMG_H_PX / (2 * f_px)))

    print("=" * 72)
    print("1) OPTIK PARAMETRELER (cetvel testinden, kalibrasyonsuz kestirim)")
    print("=" * 72)
    print(f"  Cozunurluk           : {IMG_W_PX} x {IMG_H_PX} px")
    print(f"  Odak uzakligi f      : {f_px:.0f} px")
    print(f"  Yatay gorus acisi    : {hfov:.1f}°")
    print(f"  Dikey gorus acisi    : {vfov:.1f}°")
    print(f"  Baseline B           : {BASELINE_MM:.1f} mm")
    print()
    print("  NOT: Bu degerler planlama icindir. Gercek f, kalibrasyondan gelen K")
    print("       matrisinden okunacak. Ikisi %10'dan fazla sapiyorsa cetvel testi")
    print("       veya kalibrasyon hatalidir — kontrol et.")
    print()

    # --- Mesafe taramasi ---
    print("=" * 72)
    print("2) MESAFE TARAMASI")
    print("=" * 72)
    print(f"  {'Z(mm)':>6} {'GorusGen':>9} {'Ortak%':>7} {'dZ(mm)':>8} "
          f"{'DesenDolu%':>11} {'MarkerPx':>9}  Durum")
    print("  " + "-" * 68)

    uygun = []
    for Z in range(200, 1401, 50):
        # Bu mesafede goruntunun kapsadigi genislik
        gorus_mm = 2 * Z * math.tan(math.radians(hfov / 2))

        # Iki kamera paralelse ortak goren alan = gorus - baseline
        ortak_mm = max(0.0, gorus_mm - BASELINE_MM)
        ortak_oran = ortak_mm / gorus_mm if gorus_mm > 0 else 0

        # Derinlik belirsizligi:  dZ = Z^2 * dd / (f * B)
        dZ = (Z ** 2) * DISPARITY_UNCERT_PX / (f_px * BASELINE_MM)

        # Desen bu mesafede goruntunun yuzde kacini kapliyor
        desen_mm = CHARUCO_SQUARES_X * CHARUCO_SQUARE_MM
        desen_oran = desen_mm / gorus_mm if gorus_mm > 0 else 0

        # ArUco marker bu mesafede kac piksel
        marker_mm = CHARUCO_SQUARE_MM * CHARUCO_MARKER_RATIO
        marker_px = f_px * marker_mm / Z

        # Kriterler
        k_dogruluk = dZ <= TARGET_ACCURACY_MM
        k_ortak = ortak_oran >= MIN_OVERLAP_RATIO
        k_cisim = ortak_mm >= MAX_OBJECT_MM * 1.2   # %20 kenar payi

        durum = []
        if not k_ortak:
            durum.append("ortak alan az")
        if not k_cisim:
            durum.append("cisim sigmaz")
        if not k_dogruluk:
            durum.append("dogruluk yetersiz")
        d = "UYGUN" if not durum else " / ".join(durum)

        if not durum:
            uygun.append(Z)

        print(f"  {Z:>6} {gorus_mm:>9.0f} {ortak_oran*100:>6.0f}% {dZ:>8.2f} "
              f"{desen_oran*100:>10.0f}% {marker_px:>9.0f}  {d}")

    print()
    print("=" * 72)
    print("3) CALISMA ZARFI")
    print("=" * 72)
    if uygun:
        zmin, zmax = min(uygun), max(uygun)
        dZ_max = (zmax ** 2) * DISPARITY_UNCERT_PX / (f_px * BASELINE_MM)
        print(f"  Calisma araligi : {zmin} – {zmax} mm")
        print(f"  En kotu durumda : ±{dZ_max:.2f} mm ({zmax} mm mesafede)")
        print(f"  Onerilen olcum  : {(zmin+zmax)//2} mm civari")
        print()
        print(f"  RAPOR CUMLESI: \"Sistem {zmin/10:.0f}–{zmax/10:.0f} cm araliginda")
        print(f"  ±{dZ_max:.1f} mm derinlik belirsizligiyle calismaktadir. Alt sinir iki")
        print(f"  kameranin ortak gorus alani, ust sinir Z² ile buyuyen derinlik")
        print(f"  belirsizligi tarafindan belirlenmistir.\"")
    else:
        print("  !!! HICBIR MESAFE TUM KRITERLERI SAGLAMIYOR !!!")
        print()
        print("  Cozum secenekleri:")
        print("   - Cozunurlugu artir  → f_px buyur, dZ kucultur (en ucuz cozum)")
        print("   - Baseline'i artir   → dZ kucultur ama yakin mesafede ortak alan azalir")
        print("   - Hedef dogrulugu gevset (3 mm yerine 5 mm)")
        print("   - Daha kucuk cisimlerle calis")
    print()

    # --- Desen boyutu onerisi ---
    print("=" * 72)
    print("4) CHARUCO DESEN KONTROLU")
    print("=" * 72)

    if uygun:
        z_kalib_max = max(uygun)
    else:
        z_kalib_max = 800

    gorus_max = 2 * z_kalib_max * math.tan(math.radians(hfov / 2))
    desen_mm = CHARUCO_SQUARES_X * CHARUCO_SQUARE_MM
    desen_oran = desen_mm / gorus_max

    marker_mm = CHARUCO_SQUARE_MM * CHARUCO_MARKER_RATIO
    marker_px_max = f_px * marker_mm / z_kalib_max

    print(f"  Mevcut desen         : {CHARUCO_SQUARES_X} kare x {CHARUCO_SQUARE_MM:.0f} mm "
          f"= {desen_mm:.0f} mm genislik")
    print(f"  Calisma araligi ustu : {z_kalib_max} mm")
    print(f"  Bu mesafede desen    : goruntunun %{desen_oran*100:.0f}'ini kapliyor")
    print(f"  Bu mesafede marker   : {marker_px_max:.0f} px (min {MIN_MARKER_PX:.0f} px gerekli)")
    print()

    sorun = False
    if marker_px_max < MIN_MARKER_PX:
        sorun = True
        gerekli_kare = MIN_MARKER_PX * z_kalib_max / (f_px * CHARUCO_MARKER_RATIO)
        print(f"  ⚠ MARKER COK KUCUK. Bu mesafede tespit guvenilmez olur.")
        print(f"    Gereken minimum kare boyutu: {gerekli_kare:.0f} mm")
    if desen_oran < 0.30:
        sorun = True
        gerekli_kare = 0.40 * gorus_max / CHARUCO_SQUARES_X
        print(f"  ⚠ DESEN COK KUCUK GORUNUYOR (%{desen_oran*100:.0f}).")
        print(f"    Kalibrasyon kalitesi icin goruntunun %30-60'ini kaplamali.")
        print(f"    Ya kalibrasyonu daha yakinda yap, ya kareyi buyut.")
        print(f"    %40 doluluk icin gereken kare boyutu: {gerekli_kare:.0f} mm")
        print(f"    ({CHARUCO_SQUARES_X} x {gerekli_kare:.0f} mm = "
              f"{CHARUCO_SQUARES_X*gerekli_kare:.0f} mm genislik — kagida sigiyor mu kontrol et)")
    if not sorun:
        print("  ✓ Mevcut desen bu calisma araligi icin yeterli.")

    # Kagit kontrolu
    print()
    board_w = CHARUCO_SQUARES_X * CHARUCO_SQUARE_MM + 30   # 15 mm kenar payi x2
    print(f"  Basim kontrolu: desen + kenar payi = {board_w:.0f} mm genislik")
    if board_w <= 210:
        print(f"    → A4 DIKEY sigar (210 mm)")
    elif board_w <= 297:
        print(f"    → A4 DIKEY SIGMAZ. A4 YATAY bas (297 mm)")
    elif board_w <= 420:
        print(f"    → A4 SIGMAZ. A3 gerekli (420 mm yatay / 297 dikey)")
    else:
        print(f"    → A3'e de sigmaz. Kare boyutunu kucult veya poster baski al")

    print()
    print("=" * 72)
    print("5) KALIBRASYON MESAFESI ONERISI")
    print("=" * 72)
    # Desenin %40-60 doldurdugu mesafe araligi
    z_dolu_60 = desen_mm / (0.60 * 2 * math.tan(math.radians(hfov / 2)))
    z_dolu_30 = desen_mm / (0.30 * 2 * math.tan(math.radians(hfov / 2)))
    print(f"  Desen goruntunun %60'ini kapladigi mesafe : {z_dolu_60:.0f} mm")
    print(f"  Desen goruntunun %30'unu kapladigi mesafe : {z_dolu_30:.0f} mm")
    print(f"  → Kalibrasyon karelerini {z_dolu_60:.0f}–{z_dolu_30:.0f} mm arasinda topla")
    if uygun:
        print(f"  → Bu aralik calisma araligiyla ({min(uygun)}–{max(uygun)} mm) ortusuyor mu?")
        ort_alt = max(z_dolu_60, min(uygun))
        ort_ust = min(z_dolu_30, max(uygun))
        if ort_alt < ort_ust:
            print(f"    ✓ Ortusuyor: {ort_alt:.0f}–{ort_ust:.0f} mm. Kareleri burada topla.")
        else:
            print(f"    ⚠ Ortusmuyor. Desen buyutulmeli, yoksa kalibrasyon calisma")
            print(f"      mesafesini temsil etmez ve ekstrapolasyon hatasi olur.")
    print()


if __name__ == "__main__":
    hesapla()
