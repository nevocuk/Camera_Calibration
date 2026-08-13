# Stereo Kamera Projesi — Gelistirme Gunlugu

## Asama 0: Proje Kurulumu
- CLAUDE.md, klasor yapisi, kutu_tablosu.json, charuco desen PDF olusturuldu
- camera_test.py: Tkinter tabanli GUI, 7 tab (Ayarlar, Hesaplama, Kalibrasyon, Derinlik, Olcum, Durum, Rehber)
- calibration.py, ground_plane.py, measurement.py, box_output.py yazildi

---

## Asama 1: CharucoBoard ile Ilk Kalibrasyon (evde, A4 baski)
- Standart CharucoBoard (7x5, DICT_5X5_50) ile ev ortaminda test
- Rasgele basilmis A4 kagitlarla bile **RMS ~0.7 px** elde edildi
- Temel pipeline calisiyordu

---

## Asama 2: calib.io AprilTag Board'a Gecis

### Neden gecis yapildi
- Evdeki A4 baski CharucoBoard profesyonel degil, kagit bukulmesi/olcek hatasi var
- calib.io'dan profesyonel kalibrasyon tahtasi alindi: 15x10 AprilTag 36h11 grid board
- Daha buyuk, daha hassas, aluminyum zemin uzerine basilmis

### Sorun: Board turu uyumsuzlugu
- Ilk bakista "ArUco marker'lar var, CharucoBoard'dur" diye dusunuldu — **YANLIS**
- CharucoBoard = dama tahtasi deseni + aralarda ArUco marker'lar (marker'lar sadece yardimci)
- GridBoard = her pozisyonda marker var, dama tahtasi yok (marker'lar ana olcum noktasi)
- calib.io board'u GridBoard — OpenCV'de tamamen farkli sinif ve API
- CharucoDetector.detectBoard() bu board'da hic kose bulamiyordu cunku dama tahtasi deseni yok

### Cozum: GridBoard destegi eklendi
- `charuco_config.json`'a `"board_type": "grid"` alani eklendi
- `load_charuco()` fonksiyonu (camera_test.py, calibration.py, ground_plane.py) her iki board turunu de destekleyecek sekilde guncellendi
- CharucoBoard → `CharucoDetector.detectBoard()` kullanir, koseleri dama tahtasi kesisimlerinden bulur
- GridBoard → `ArucoDetector.detectMarkers()` kullanir, koseleri marker kenarlarindan bulur
- AprilTag icin ozel detector parametreleri: `adaptiveThreshWinSizeMax=73, adaptiveThreshWinSizeStep=2` (standart ArUco ayarlari AprilTag'i bulamiyor)

---

## Asama 3: Kalibrasyon Hatasi — RMS = 2,740,626,181,555,898

### Belirti
- 31 kare cifti cekildi, `calibration.py` calistirildi
- RMS = 2.7 katrilyon piksel — tamamen anlamsiz bir sonuc
- Kalibrasyon basarisiz, depth haritasi kullanilamaz durumda

### Neden bu kadar kotu?
Stereo kalibrasyonda her algilanan marker kosesinin 3D uzaydaki "gercek" konumuna eslemesi gerekir.
GridBoard bu eslemeyi marker ID'lerine gore yapar: ID 0 → (0,0) konumu, ID 1 → (0, pitch) konumu, vs.
Eger ID sirasi yanlis ise, algilanan koseler **tamamen yanlis 3D noktalara** eslenir.
Ornegin: kameranin sol ustunde gordugu marker, GridBoard'a gore sag altta olmali — bu 400+ piksel hata demek.

### Sorun 1: ID-pozisyon esleme hatasi
- **OpenCV GridBoard varsayilan ID atamasi**: soldan saga, yukaridan asagiya sirayla
  ```
  ID:  0   1   2   3  ...  14
      15  16  17  18  ...  29
      ...
  ```
- **calib.io board'un gercek ID atamasi**: sagdan sola, asagidan yukariya
  ```
  ID: 140 130 120 110 ... 0
      141 131 121 111 ... 1
      ...
      149 139 129 119 ... 9
  ```
- Formul: `ID = (14 - sutun) * 10 + satir`
- Bu uyumsuzluk yuzunden marker ID=0 OpenCV'ye gore sol-ust konumda olmali ama fiziksel board'da sag-alt konumda

### Nasil tespit edildi
- "fx ve fy birbirine yakin olmali" kuralini kullandik
- Dogru kalibrasyonda fx ≈ fy olur (kare piksel sensoru)
- 4 farkli ID mapping formulu denendi, her birinin fx/fy oranina bakildi

### Test: 4 farkli ID mapping denendi
| Mapping | Formul | fx | fy | fx≈fy? |
|---------|--------|----|----|--------|
| A (OpenCV varsayilan) | `r*15+c` | 878 | 854 | Hayir (24 fark) |
| **B (calib.io)** | `(14-c)*10+r` | **891.9** | **889.3** | **Evet (2.6 fark)** ✓ |
| C | `c*10+r` | 879 | 841 | Hayir (38 fark) |
| D | `(14-c)*10+(9-r)` | 871 | 824 | Hayir (47 fark) |

### Sonuc
Mapping B dogru: `ids_arr = [(14-c)*10+r for r in range(10) for c in range(15)]`
Custom ID'ler GridBoard constructor'ina verildi.
Ama RMS hala **~58 px** — astronomik degil ama yine cok yuksek (hedef < 1 px). Baska bir sorun daha var.

---

## Asama 4: Kose Siralama Hatasi — RMS = 58 px (custom ID'ler ile)

### Belirti
- Custom ID mapping ile fx ≈ fy oldu (dogru esleme) ama RMS 58 px
- Toplam 400 noktanin tam 200'u (yuzde 50) cok buyuk hatali
- Rastgele degil, bir duzene uyuyor

### Analiz yontemi
- `cv2.calibrateCamera` sonrasi her noktanin reprojection hatasini hesapladik
- Hatalari kose indeksine gore grupladik (her marker'in 4 kosesi: c0, c1, c2, c3)

### Bulgu: Per-kose hata analizi
| Kose | Ortalama hata | Medyan hata | Durum |
|------|--------------|-------------|-------|
| **c0** | **70.8 px** | **65.7 px** | KOTU |
| c1 | 9.0 px | 7.3 px | Kabul edilebilir |
| **c2** | **70.8 px** | **65.1 px** | KOTU |
| c3 | 9.4 px | 7.9 px | Kabul edilebilir |

- c0 ve c2 **capraz koseler** — ikisi de ~70 px hata
- c1 ve c3 **capraz koseler** — ikisi de ~9 px hata
- Bu desen gosteriyor ki: AprilTag detector koseleri, ArUco'nun beklediginden farkli sirada donduruyor

### Neden boyle oluyor?
- ArUco marker'lar koseleri **saat yonunde** siralar: TL → TR → BR → BL
- AprilTag marker'lar koseleri **farkli** siralar (internal bit pattern'a gore)
- GridBoard'un `matchImagePoints()` fonksiyonu ArUco sirasini varsayar
- Sonuc: c0 (TL olmali) aslinda BR'ye denk geliyor, c2 (BR olmali) aslinda TL'ye — capraz takas

### Denenen cozumler — 7 farkli kose sirasi
| Yontem | Kose sirasi | RMS | fx | fy |
|--------|------------|-----|----|----|
| Orijinal | [0,1,2,3] | 54.6 | 878 | 854 |
| Ters cevirme | [3,2,1,0] | 54.1 | 819 | 808 |
| **c0↔c2 swap** | **[2,1,0,3]** | **6.1** | **809** | **808** |
| c1↔c3 swap | [0,3,2,1] | 76.3 | 824 | 794 |
| Rotasyon 1 | [1,2,3,0] | 55.1 | 821 | 832 |
| Rotasyon 2 | [2,3,0,1] | 54.6 | 830 | 826 |
| Rotasyon 3 | [3,0,1,2] | 53.9 | 872 | 824 |

### Sonuc
- c0↔c2 swap ile RMS 54.6 → **6.1** (9x iyilesme)
- fx ≈ fy = 809 (dogru)
- Ama 6.1 px hala cok yuksek — hedef < 1 px
- Sub-pixel iyilestirme (`cornerSubPix`) eklendi → 6.1 → **4.5** (biraz daha iyi ama yetersiz)
- Sorun: AprilTag marker koselerinin kendisi yeterli hassasiyette degil (~5-6 px belirsizlik)

---

## Asama 5: Marker Merkezleri Yaklasimi — RMS = 0.75 px

### Temel kavrayis
AprilTag'in 4 kosesi hassas degil (~6px hata), ama 4 kosenin **ortalamasi** (merkez) cok daha hassas.

### Karsilastirma
| Yontem | RMS | fx | fy | Not |
|--------|-----|----|----|-----|
| 4 kose (orijinal) | 54.6 | 878 | 854 | Yanlis kose sirasi |
| 4 kose (swap c0↔c2) | 6.1 | 809 | 808 | Kose hassasiyeti yetersiz |
| **Marker merkezleri** | **0.75** | **805** | **805** | En iyi sonuc |

### Uygulama
- Her marker icin 4 kosenin ortalamasini al → tek nokta (merkez)
- Nesne noktalarini ID'den hesapla: `col = 14 - ID//10, row = ID%10, center = (col*pitch + mk/2, row*pitch + mk/2)`
- `board.matchImagePoints()` kullanmak yerine manuel hesaplama
- Bu yaklasim kose siralama sorununu tamamen atliyor

### Degistirilen dosyalar
- `src/calibration.py`: `_grid_custom_ids()`, `_grid_id_to_center()` fonksiyonlari eklendi, `calibrate_single()` ve `_filter_common_markers()` guncellendi
- `src/camera_test.py`: `load_charuco()`'ya custom ID'ler eklendi
- `src/ground_plane.py`: Ayni custom ID ve marker merkezi yaklasimi

---

## Asama 6: Stereo Kalibrasyon Sonuclari

### Final kalibrasyon (31 kare cifti)
| Parametre | Deger |
|-----------|-------|
| Sol RMS | 0.7617 px |
| Sag RMS | 0.6635 px |
| Stereo RMS | 0.7993 px |
| Baseline | 71.6 mm (olculen: 72 mm, %0.6 fark) |
| fx (sol) | 803.9 px |
| fx (sag) | 803.2 px |

### Hedef RMS karsilastirmasi
- CharucoBoard hedefi: < 0.4 px (sub-pixel dama tahtasi koseleri)
- AprilTag grid board beklentisi: 0.5-1.0 px (marker merkezleri)
- Sonuc: 0.80 px — **AprilTag icin kabul edilebilir**

### Teorik derinlik hassasiyeti
| Mesafe | Hata |
|--------|------|
| 300 mm | 0.55 mm |
| 500 mm | 1.52 mm |
| 700 mm | 2.98 mm |
| 900 mm | 4.93 mm |

---

## Asama 7: Derinlik Haritasi Iyilestirmesi

### Sorun: Disparity'de gurultu ve sahte degerler
- Duz, dokusuz yuzeyler (beyaz tavan) yuzunden SGBM yanlis eslesme uretiyor
- Tavanda sahte kirmizi lekeler (yakin gibi gorunen uzak noktalar)
- Genel olarak noktali, gurultulu disparity

### Cozum 1: SGBM parametreleri guclendirildi
| Parametre | Eski | Yeni | Etki |
|-----------|------|------|------|
| P1 | 8×3×25=600 | 8×3×49=1176 | Daha puruzsuz yuzeyler |
| P2 | 32×3×25=2400 | 32×3×49=4704 | Daha puruzsuz yuzeyler |
| uniquenessRatio | 10 | 15 | Belirsiz eslesmeleri reddet |
| speckleWindowSize | 100 | 200 | Buyuk gurultu lekeleri temizle |
| speckleRange | 32 | 2 | Daha siki speckle filtresi |

### Cozum 2: WLS (Weighted Least Squares) filtresi eklendi
- `cv2.ximgproc.createDisparityWLSFilter` kullanildi
- Sol ve sag disparity hesaplanip birlestiriliyor
- Lambda=8000, SigmaColor=1.5
- Kenar koruyarak puruzsuzlestirme
- 3 yere eklendi: canli derinlik, D kayit, olcum fonksiyonu

### Sonuc
- Tavandaki sahte kirmizi lekeler yok oldu
- Disparity haritasi puruzsuz gecisler gosteriyor
- Derinlik katmanlari net ve dogru

---

## Diger Duzeltmeler (kronolojik)

### FPS dususu — Kare atlama
- **Sorun**: Marker tespiti her karede calisinca goruntu kasiyor
- **Cozum**: Tespit her 3. karede calisir, aradaki kareler onceki sonucu gosterir
- **Dosya**: camera_test.py, detection loop

### Oto yakalama esigi cok yuksek
- **Sorun**: max_corners GridBoard icin 150 (CharucoBoard'da 126), eski esik 0.4×150=60 marker gerektiriyordu, kamera 39-48 goruyordu
- **Cozum**: Esik 0.4 → 0.15 (23 marker yeterli)
- **Dosya**: camera_test.py

### Ayarlar kayboluyordu
- **Sorun**: Her acilista ayarlar default'a donuyordu
- **Cozum**: `_on_close()`'a `_save_settings()` eklendi, `camera_settings.json`'a kaydediliyor
- **Dosya**: camera_test.py

### Board ayarlari paneli
- **Sorun**: Board turunu ve boyutlarini degistirmek icin JSON duzenlemek gerekiyordu
- **Cozum**: Kalibrasyon tab'ina kilitli board ayarlari paneli eklendi, degistirmek icin onay soruyor
- **Dosya**: camera_test.py

### Kalibre Et butonu
- **Sorun**: Kalibrasyonu calistirmak icin komut satirina gitmek gerekiyordu
- **Cozum**: Kalibrasyon tab'ina "Kalibre Et" butonu eklendi, calibration.py'yi arka planda calistiriyor
- **Dosya**: camera_test.py

### D tusu sadece sol kaydediyordu
- **Sorun**: Ekran goruntusu sag kamerayi kaydetmiyordu
- **Cozum**: `_save_depth()`'a `rect_r` kaydi eklendi (4 dosya: sol, sag, derinlik, overlay)
- **Dosya**: camera_test.py

### Unicode hatasi
- **Sorun**: `→` karakteri cp1254 encoding'de basilamiyordu
- **Cozum**: `→` yerine `->` kullanildi
- **Dosya**: calibration.py

---

## Asama 8: Kalibrasyon Kalite Filtreleme

### Amac
Dusuk kaliteli kareleri otomatik eleyerek kalibrasyon sonucunu iyilestirmek.

### Eklenen filtreler (calibration.py, collect_frames)
| Filtre | Esik | Gerekcesi |
|--------|------|-----------|
| Minimum parlaklik | avg_bright >= 40 | Karanlik karelerde marker kenar kontrastlari zayif, merkez hesabi kayiyor |
| Minimum ortak marker | >= 15 | Az noktali kareler lens distortion modelini kotu kestiriyor |

### RMS esigi guncellendi
- Eski: tum board turleri icin sabit 0.4 px
- Yeni: GridBoard (AprilTag) icin **1.0 px**, CharucoBoard icin **0.4 px**
- Sebep: marker merkezleri sub-pixel dama koseleri kadar hassas degil, 0.5-1.0 arasi normal

### Karsilastirma: filtresiz vs filtreli
| Metrik | 31 cift (filtresiz) | 17 cift (filtreli) |
|--------|--------------------|--------------------|
| Sol RMS | 0.518 | **0.438** |
| Sag RMS | 0.527 | **0.446** |
| Stereo RMS | 0.636 | **0.611** |
| Epipolar ort | **0.250** | 0.310 |
| Epipolar max | **0.750** | 1.250 |

### Karar
Filtreli versiyonda tekli ve stereo RMS daha iyi, ama epipolar max hata 0.75 → 1.25'e cikti.
Sebep: 14 kare elenince farkli aci/mesafe cesitliligi azaldi, lens distortion modeli kenar bolgelerde zayifladi.
**Sonuc: 31 ciftli filtresiz kalibrasyona geri donuldu.** RMS farki kucuk (%4), ama epipolar tutarlilik daha onemli.

### Kalibrasyon set yonetimi
- `frames_set_1`: Ilk denemeler
- `frames_set_2`: 31 ciftli kalibrasyon (aktif, geri yuklendi)
- Her set `calib_result.npz` + tum frame PNG'lerini iceriyor
- GUI'de "Yeni Set Baslat" / "Eski Seti Yukle" butonlari mevcut

---

## Asama 9: Kamera FPS ve USB Hiz Testi

### Amac
Hocanin "4K@10fps" iddiasini dogrulamak, kameranin gercek fps sinirlarini olcmek.

### Test yontemi
- Python + OpenCV ile gercek kare okuma suresi olculdu (DirectShow backend)
- YUY2 ve MJPG format farki test edildi
- Tek kamera ve cift kamera birlikte test edildi

### Bulgu 1: Kamera sadece MJPG destekliyor
YUY2 istense bile surucu MJPG donduruyor. Kamera donanimi sadece MJPG cikis veriyor.

### Bulgu 2: FPS tablosu (16MP USB Camera, VID_32E4 PID_0298)
| Cozunurluk | Tek kamera | Iki kamera birlikte |
|---|---|---|
| 3840×2160 (4K) | 1.0 fps | — |
| 1920×1080 | 5.0 fps | — |
| 1280×960 | 10.0 fps | 10.0 fps |
| 640×480 | 15.0 fps | — |

### Bulgu 3: USB bant genisligi sorun degil
- Iki kamera ayni anda 1280×960'da 10 fps — dusme yok
- Kameralar USB 3.0 Root Hub'a bagli (Intel USB 3.10/3.20 xHCI)
- Darbogaz USB degil, sensor/ISP donanim siniri

### Bulgu 4: 4K@10fps mumkun degil
- Hocanin iddiasi bu kamera moduluyle dogrulanamadi
- MJPG ile bile 4K'da max 1 fps
- Surucu degistirmek cozmez — sensor fiziksel olarak daha hizli kare uretemiyor

### Sonuc
1280×960@10fps en iyi denge: yeterli cozunurluk, yeterli hiz, iki kamera birlikte calisiyor.

---

## Asama 10: Disparity Post-Processing ve 4K Foto Modu

### Sorun
Disparity haritasinda gurultu, kucuk lekeler ve kenar bozukluklari var. Internet'teki benchmark goruntuler (Tsukuba, KITTI, Middlebury) cok daha temiz — bunlar kontrollü ortam + offline isleme urunleri.

### Cozum: _clean_disparity() post-processing
WLS filtresinden sonra 3 ek adim eklendi:
1. **Median filtre (5x5)** — tuz-biber gurultusunu temizler, tekil yanlis pikselleri yok eder
2. **Morfolojik kapama (7x7 elips)** — disparity'deki kucuk delikleri doldurur, kenarlari duzeltir
3. **Kucuk bolge silme (< 500 piksel)** — izole sahte lekeler silinir

### Kod organizasyonu
- `_compute_disparity(gray_l, gray_r)` — WLS + clean_disparity birlestiren tek fonksiyon
- 3 yerde kullaniliyor: canli depth, D kayit, olcum

### 4K Foto Modu
- Derinlik tab'ina "4K Foto Modu" butonu eklendi
- Kameralari gecici olarak 3840x2160'a cikarir, tek kare cifti ceker
- Kalibrasyon matrislerini 4K'ya olcekler (K, P matrisleri sx/sy ile carpilir)
- numDisparities=512 (1280'de 256 idi — 3x cozunurlukte ~2x artis)
- Ayri thread'de calisir, UI donmuyor
- Sonuc: 5 dosya kaydedilir (sol, sag, derinlik, overlay, disparity)

### Post-processing toggle
- Derinlik tab'ina "Post-processing (temizleme)" checkbox'i eklendi
- Varsayilan acik, canli goruntuude aninda kapatilabilir
- Kalibrasyon/egitimle ilgisi yok, sadece disparity uzerinde goruntu isleme

### Geri donus
Degisiklikler geri alinabilir:
- Post-processing: checkbox ile acip kapatilabilir, veya `_clean_disparity` icindeki 3 adim yorum satirina alinabilir
- 4K modu: canli depth'i etkilemiyor, bagimsiz buton

---

## Asama 11: SGBM Doku Desenleri

### Sorun
Dokusuz yuzeyler (beyaz masa, duz duvar) SGBM'de siyah bolge uretiyor — eslestirme yapilamiyor.

### Cozum
A4 boyutunda 3 sayfa rasgele doku deseni olusturuldu (`patterns/sgbm_doku_desenleri.pdf`):
1. Rasgele noktalar (farkli boyut + yogunluk)
2. Karisik (kareler + cizgiler + ucgenler)
3. Speckle pattern (yogun, ince, yuksek kontrastli)

### Kullanim
- Siyah beyaz yazicida bas, her sayfadan 2-3 kopya
- Masayi ve arka plani kapla
- Uzerine olcecek nesneyi koy
- SGBM her bolgeyi benzersiz gorur, siyah alan azalir

### Neden gazete/rasgele desen?
- Tekrarlayan desenler (kareli ortu, cizgili kagit) SGBM'i kandiriyor — ayni blogu birden fazla yerde buluyor
- Rasgele desen her bolgeyi benzersiz yapar, yanlis eslestirme riski dusuk
- Siyah beyaz yeterli — SGBM zaten gri tonlamada calisiyor

---

## Dosya Degisiklikleri Ozeti

| Dosya | Degisiklik |
|-------|-----------|
| data/charuco_config.json | board_type, olculen_kare_boyutu_mm, pitch=26mm |
| src/camera_test.py | GridBoard + custom ID, WLS filtre, kare atlama, board paneli, kalibre et, ayar kayit, D kayit, post-processing toggle, 4K foto modu, _clean_disparity, _compute_disparity |
| src/calibration.py | Marker merkezleri, custom ID mapping, WLS, unicode fix, parlaklik/marker filtreleme, board turune gore RMS esigi |
| src/ground_plane.py | GridBoard + custom ID + marker merkezleri |
| patterns/sgbm_doku_desenleri.pdf | 3 sayfa A4 rasgele doku deseni |
