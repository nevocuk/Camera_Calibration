@docs/PROJE_KONTEXT.md

# Stereo Kamera Projesi — Ortak Kurallar

## Dil
- Aciklamalar, yorumlar, rapor metni: Turkce
- Kod ici degisken isimleri: Ingilizce olabilir
- Kisa ve dogrudan ol, gereksiz uzatma

## Gizlilik
- Sirket verisi/kodu bu projeye girmeyecek
- Senaryo "sirket ihtiyaci" degil "dogrulama araci" olarak sunulacak

## Klasor yapisi
```
camera proje/
├── PROJE_BRIEF.md          # Ana plan dokumani
├── CLAUDE.md               # Bu dosya — ortak kurallar
├── src/                    # Python kaynak kodlari
│   ├── camera_test.py      # Asama 0: kamera test araci
│   ├── calibration.py      # Asama C: kalibrasyon
│   ├── measurement.py      # Asama F: olcum pipeline
│   └── box_output.py       # Asama G: kutu onerisi + kesim
├── data/
│   ├── olcum_defteri.csv   # Tum olcumler, ayarlar, sicaklik
│   ├── kutu_tablosu.json   # Standart kargo kutu olculeri
│   └── charuco_config.json # Desen parametreleri
├── calibration/
│   ├── frames/             # Kalibrasyon kare ciftleri (L_001.png, R_001.png)
│   ├── calib_result.npz    # K, D, R, T, Q matrisleri
│   └── ground_plane.npz    # Zemin duzlemi normal + d
├── output/
│   ├── reports/            # Dogrulama tablolari, grafikler
│   └── box_templates/      # Kesim yonergesi PDF/DXF
├── patterns/               # Basima hazir kalibrasyon desenleri
└── docs/                   # Rapor (Ek-4 docx)
    ├── PROJE_KONTEXT.md    # Tam kontext (kararlar, riskler)
    ├── YONTEMLER.md        # Hangi adimda hangi yontem, neden
    └── ilerleme_gunlugu.md # Gun gun olcumler
```

## Olcum defteri kurallari
Her olcum satirinda: tarih, asama, pozlama, gain, WB, oda sicakligi, olcum degeri, birim, not.
Ilk gunden tutulmaya baslanacak.

## Kalibrasyon kurallari
- Desen olcusu: yazicidan cikan deseni kumpasla olc, OLCULEN degeri koda gir
- Pozlama/gain/WB: kalibrasyon sirasinda kilitli, olcum defterine yazili
- Odaga kalibrasyondan sonra dokunma
- RMS hedefi < 0.4 px

## Dogrulama oncelikleri (rapor puaninin cogu buradan)
1. Mesafeye gore hata egrisi + teorik karsilastirma (5.2)
2. Tekrarlanabilirlik testi (5.3)
3. Calisma zarfi (5.4)
4. Kalibrasyon kalitesinin etkisi (5.5)
5. Yontem karsilastirmasi (5.6)
6. Ana sonuc tablosu (5.9)
7. Fiziksel dogrulama — kesim yonergesiyle kutu (5.10)

## Is bolumu
- **Claude Code**: Kamera, kalibrasyon, olcum — donanima dokunan her sey
- **Cowork**: Rapor (docx), grafik, sema, kesim sablonu — donanim gerektirmeyen isler
- Iletisim kanali: dosyalar (PROJE_BRIEF.md, data/*.csv, calibration/*.npz)
- **Rapor devri:** `docs/RAPOR_DEVIR_COWORK.md` — gun gun icerik,
  olculen sayilar, gorsel listesi ve YAPILAMAYANLAR. Cowork raporu
  bu dosyadan yazar; sayilari elle kopyalamaz, `output/reports/`
  altindaki CSV'lerden alir.
