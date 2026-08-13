# Stereo Kamera ile Boyutsal Olcum ve Kutu Onerme Sistemi

ATU Bilgisayar Muhendisligi — Yaz Staji Projesi

Iki USB kamerayla stereo gorus sistemi kurarak nesnelerin 3 boyutlu olcumunu yapar,
uygun kargo kutusunu onerir ve cisme ozel kesim yonergesi uretir.

## Ozellikler

- Stereo kalibrasyon (AprilTag grid board, calib.io)
- Canli derinlik haritasi (SGBM + WLS filtre)
- Disparity post-processing (median, morfoloji, connected components)
- 4K foto modu
- Nesne olcumu (en, boy, yukseklik)
- Standart kutu onerisi + desi hesabi
- RSC kesim yonergesi (PDF)
- Tek pencere GUI (7 tab)

## Kurulum

```bash
pip install -r requirements.txt
```

**Not:** `opencv-contrib-python` gerekli — standart `opencv-python` paketi
`cv2.aruco` ve `cv2.ximgproc` (WLS filtre) modullerini icermiyor.

## Calistirma

```bash
python src/camera_test.py
```

Iki USB kamera baglamadan da GUI acilir, ancak goruntu icin kameralar gereklidir.

## Kullanim Adimlari

1. **Ayarlar** — Cozunurluk, pozlama, gain, WB ayarlarini yap ve kilitle
2. **Kalibrasyon** — Board'u farkli aci ve mesafelerden goster, kare topla, kalibre et
3. **Derinlik** — Canli disparity/derinlik haritasini gor
4. **Olcum** — Arka plan kaydet (B), nesne koy, olc (M)

## Proje Yapisi

```
src/
  camera_test.py     — Ana GUI uygulamasi (tum pipeline)
  calibration.py     — Stereo kalibrasyon scripti
  measurement.py     — Nesne olcum pipeline
  ground_plane.py    — Zemin duzlemi tespiti
  box_output.py      — Kutu onerisi + kesim sablonu
calibration/
  calib_result.npz   — Kalibrasyon matrisleri (K, D, R, T, Q)
data/
  charuco_config.json — Board parametreleri
  kutu_tablosu.json   — Standart kargo kutu olculeri
  olcum_defteri.csv   — Tum olcum kayitlari
patterns/
  sgbm_doku_desenleri.pdf — Basima hazir SGBM doku desenleri
docs/
  gelistirme_gunlugu.md  — Gelistirme gunlugu
```

## Teknik Detaylar

| Parametre | Deger |
|---|---|
| Kamera | 16MP USB Camera (VID_32E4) x2 |
| Cozunurluk | 1280 x 960 @ 10fps |
| Board | calib.io AprilTag 15x10 (tag:20mm, pitch:26mm) |
| Stereo RMS | 0.636 px |
| Baseline | 71.6 mm (kumpas: 72mm) |
| Calisma mesafesi | ~200–900 mm |
| SGBM numDisparities | 256 |

## Gereksinimler

- Python 3.10+
- Windows 10/11
- 2x USB kamera (ayni model onerilir)
- Kalibrasyon board'u (calib.io AprilTag)
