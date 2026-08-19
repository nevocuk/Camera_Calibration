# Stereo Kamera Projesi — Ilerleme Gunlugu

## Proje Ozeti
Nevfel, ATU Bilgisayar Muhendisligi, Sadektech staji.
Stereo kamera ile boyutsal olcum ve kutu onerme sistemi.

---

## Asama 0 — Kamera Test Araci
**Durum: TAMAMLANDI**

- `src/camera_test.py` — Tkinter tabanli GUI uygulamasi
- Iki kameradan eszamanli goruntu yakalama (grab/retrieve)
- Pozlama, gain, beyaz dengesi manuel kilitleme
- SAG kamera telafisi (pozlama/gain/parlaklik offset)
- Laplacian varyans ile netlik skoru
- FPS sayaci
- Cozunurluk secimi (640x480 ~ 2048x1536)
- MSMF backend (DSHOW'dan gecis yapildi)
- Kalibrasyon karesi toplama (S tusu)
- SOL/SAG kamera indeksi degistirme
- Goruntu ayarlari: parlaklik, kontrast, doygunluk, keskinlik
- Ayarlari JSON'a kaydetme/yukleme (`data/camera_settings.json`)

### Kamera Ayarlari (son calisan hali)
- Pozlama: -2 / -3 (ortama gore)
- Gain: 0
- Beyaz dengesi: 4500
- Pozlama telafi (sag): +1
- Kontrast: 32, Doygunluk: 64, Keskinlik: 3

---

## Asama B — Govde ve Baseline
**Durum: TAMAMLANDI**

- 3B basilmis govde kullaniliyor
- Baseline kalibrasyondan gelen ||T|| ile belirlenmis
- Baseline: 71.6 mm (kalibrasyondan)
- Focal length: **K1[0,0] = 1291.8 px** (ham intrinsik),
  **P1[0,0] = 1420.0 px** (rektifiye — mesafe hesabinda BU kullanilir)
  Ayrinti: `docs/PROJE_KONTEXT.md` bolum 8

---

## Asama C — Kalibrasyon
**Durum: TAMAMLANDI**

### Kalibrasyon Detaylari
- **Desen:** ChArUco 9x13, **DICT_4X4_100** (charuco_config.json ile dogrulandi)
- **Cozunurluk:** 2048x1536
- **Kare boyutu:** 20 mm pitch (kumpasla olculmus)
- **RMS:** **0.7407 px** (sol 0.5950 / sag 0.6241)
  Olcekli limit: 0.4 x (2048/960) = 0.853 px → sinirin altinda, gecerli
- **Dosya:** `calibration/calib_result.npz`
  - Icerik: K1, D1, K2, D2, R1, R2, P1, P2, Q, T, image_size
- **Eski kalibrasyon:** `calibration/calib_result_960.npz` (1280x960, eski)

### Kalibrasyon Kareleri
- `calibration/frames/` — Aktif set (2048x1536)
- `calibration/frames_set_1/`, `frames_set_2/` — Onceki denemeler
- `calibration/frames_eski_4x4/` — Eski 4x4 ArUco denemesi

---

## Derinlik Haritasi
**Durum: CALISIYOR**

### camera_test.py — GUI icinde derinlik
- CPU SGBM + WLS filtre (calisma hali)
- numDisparities: 256, **blockSize: 7** (P1=8*3*49, P2=32*3*49)
- WLS Lambda: 8000, SigmaColor: 1.5
- Kaliteli kare (F): blockSize 9, Lambda 12000, 10 kare ortalamasi
- On isleme: CLAHE + istatistiksel parlaklik esleme + GaussianBlur
- Gorsellestirme: JET, TURBO, MAGMA, INFERNO, BONE, HOT renk haritalari
- Post-processing (temizleme) secenegi
- Derinlik konturlari secenegi
- Ham / WLS karsilastirma secenegi
- Merkez mesafe gosterimi (mm)
- Ekran goruntusu kaydetme (D tusu)
- Mesafe hesaplama: `reprojectImageTo3D` ile Q matrisi kullanarak

### depth_view.py — Bagimsiz derinlik goruntuleyici
- 3 pencere: Sol Kamera, Derinlik, Overlay
- CPU SGBM + WLS filtre (GPU dali 2026-08-16'da kaldirildi — WLS'i atliyordu)
- numDisparities: 256, blockSize: 7 (camera_test.py ile ayni)
- UYARI: V tusu sonuclari sadece bellekte, olcum defterine YAZILMIYOR
- Mesafe hesaplama: Z = f * B / d (dogrudan formul + medyan)
- V tusu: dogrulama modu (gercek mesafe giris)
- R tusu: dogrulama raporu
- S tusu: ekran goruntusu kaydet

### GPU Durumu
- CUDA StereoSGM denendi (commit 72cc70a)
- GPU yolunda WLS filtre YOKTU — derinlik kalitesi dusuk cikti
- **Karar:** GPU kodu geri alindi, CPU SGBM + WLS ile devam
- `camera_test.py` commit 59d84ad'ye donuldu (GPU'suz, WLS'li)
- Ileride GPU destegi WLS ile birlikte eklenebilir

---

## Asama D — Zemin Duzlemi Kalibrasyonu
**Durum: TAMAMLANDI**

- `src/ground_plane.py` yazildi
- ChArUco tahtasi ile zemin duzlemi tespiti
- Normal vektor + d katsayisi kaydediliyor
- `calibration/ground_plane.npz`

---

## Asama F — Olcum Pipeline
**Durum: TAMAMLANDI**

- `src/measurement.py` yazildi
- Hibrit olcum: taban konturu + disparity yukseklik
- Oriented bounding box
- Golge bastirma
- Yonelim duyarliligi testi

---

## Asama G — Kutu Ciktisi
**Durum: TAMAMLANDI**

- `src/box_output.py` yazildi
- Standart kutu onerisi (`data/kutu_tablosu.json`)
- Desi hesaplama
- RSC kesim yonergesi PDF uretimi
- Karton kalinligi parametresi

---

## Yardimci Scriptler

| Dosya | Aciklama |
|---|---|
| `src/detect_cameras.py` | Bagli kameralari tespit |
| `src/probe_resolutions.py` | Desteklenen cozunurlukler |
| `src/probe_stereo_bandwidth.py` | USB bant genisligi testi |
| `src/probe_backend.py` | Backend (DSHOW/MSMF) testi |
| `src/probe_msmf_full.py` | MSMF detayli analiz |
| `src/probe_full.py` | Tam kamera profili |
| `src/sistem_planlama.py` | Sistem parametreleri hesaplama |
| `src/test_charuco.py` | ChArUco tespit testi |
| `src/charuco_debug.py` | ChArUco debug goruntusu |
| `src/detect_test.py` | Tespit test araci |
| `src/odak_test.py` | Odak dogrulama |
| `src/mono_verify.py` | Mono kalibrasyon dogrulama |

---

## Kalibrasyon Desenleri

| Dosya | Aciklama |
|---|---|
| `patterns/charuco_board.png` | ChArUco 9x13 kalibrasyon deseni |
| `patterns/generate_charuco.py` | ChArUco desen uretici script |
| `patterns/sgbm_doku_desenleri.pdf` | SGBM doku desenleri v1 |
| `patterns/sgbm_doku_desenleri_v2.pdf` | SGBM doku desenleri v2 (daireler, cizgiler, dikdortgenler) |

---

## Veri Dosyalari

| Dosya | Aciklama |
|---|---|
| `data/camera_settings.json` | Kamera ayarlari (pozlama, gain, WB, telafi) |
| `data/charuco_config.json` | ChArUco desen ayarlari (9x13, 2048x1536, 20mm) |
| `data/kutu_tablosu.json` | Standart kargo kutu olculeri |

---

## Ortam Kurulumu

### Conda Ortami
- **Ortam adi:** `stereo`
- **Python:** 3.11.15
- **OpenCV:** 4.10.0 (CUDA destekli build)
- **Aktivasyon:** `conda activate stereo`
- **Python yolu:** `C:\Users\nvflb\miniconda3\envs\stereo\python.exe`

### VSCode Ayarlari
- `.vscode/settings.json` olusturuldu
- Python interpreter: stereo ortamina ayarlandi
- Terminal: Command Prompt (conda uyumlulugu icin)

### CUDA Durumu
- CUDA destekli OpenCV build mevcut
- GPU StereoSGM calisiyor ama WLS filtre eksik
- Su an CPU SGBM + WLS tercih ediliyor

---

## Git Gecmisi

| Tarih | Commit | Aciklama |
|---|---|---|
| 2026-08-13 | ddf5e64 | Initial commit |
| 2026-08-13 | 4ec57bb | Stereo kamera projesi — ilk commit |
| 2026-08-13 | 57f0c09 | README, requirements.txt ve rapor guncellemesi |
| 2026-08-13 | 59d84ad | DSHOW->MSMF backend gecisi, gorsellestirme, FPS optimizasyonu |
| 2026-08-13 | b714f85 | gitignore: conda ve opencv_build klasorleri eklendi |
| 2026-08-14 | 72cc70a | 2048x1536 ChArUco kalibrasyon, derinlik dogrulama, performans |

### Mevcut Durum (2026-08-16)
- `camera_test.py` — 59d84ad'ye geri donmus (staged, GPU'suz WLS'li hali)
- `camera_settings.json` — Pozlama -4, exp_offset_r 1 (unstaged degisiklik)
- Stash: 72cc70a versiyonu (GPU'lu hali, gerekirse geri alinabilir)

---

## 2026-08-17 — Kamera Dengesizligi Arastirmasi ve Kod Denetimi

Gun boyunca "iki kamera farkli goruntu veriyor, derinlik haritasi bozuk"
sorunu arastirildi. Kok neden bulundu ve tum kaynak dosyalar denetlendi.

### KOK NEDEN: `_apply_all` tum ozellikleri yazmiyordu

`camera_test.py` acilista yalnizca WB/CONTRAST/SATURATION/SHARPNESS ve
pozlama-gain-parlaklik yaziyordu. **GAMMA, HUE, BACKLIGHT hic yazilmiyordu.**

Bu ozellikler kamerada **kalici saklandigi** icin gecmiste yazilan degerler
oylece kalmis ve iki kamerada farkli olmustu:

| Ozellik | SOL (idx2) | SAG (idx1) | Etki |
|---|---|---|---|
| EXPOSURE | −6 | −3 | 3 kademe = 8x parlaklik |
| GAMMA | 200 | 100 | ton egrisi farki |
| SHARPNESS | **50** | 5 | 50, kameranin 0-10 araliginin disinda |
| BACKLIGHT | 0 | 1 | |

**MSMF geri okumasi bozuk** oldugu icin bu fark `cap.get()` ile gorulemiyordu
(ne yazarsan yaz sabit deger doner — pozlama hep −6, kontrast hep 32).

**Kanit:** 11 ozelligin tamami ayni degere yazildiginda kameralar ozdes cikti:

| Pozlama | SOL | SAG | Oran |
|---|---|---|---|
| −5 | 72.0 | 71.1 | 1.01x |
| −4 | 120.0 | 120.5 | **1.00x** |
| −3 | 170.2 | 173.3 | 1.02x |

Ortalama parlaklik orani **1.02x**, kontrast **1.09x**. Onceki 2.7x'lik
farkin tamami ayar kaynakliymis; donanim sorunu YOK.

### Elenen yanlis hipotezler
Sirayla suclanip olcumle elenenler: acilis yarisi (5 tur test, fark hep %62
sabit), lens diyaframi/koruyucu film, sensor duyarlilik farki, ISP/ton egrisi
farki, OpenCV yeniden derlemesi, kalibrasyon degisikligi.

### Duzeltilen kod hatalari

**Kritik (calismiyordu):**
- `measurement.py` — `stereo._use_gpu = True` OpenCV nesnesine attribute
  atamaya calisiyordu, **AttributeError ile cokuyordu**. Dosya hic calismiyormus.
- `measurement.py` — `numDisparities=128` → en yakin olculebilir mesafe 794 mm,
  calisma zarfi (300-900 mm) tamamen disarida. 256'ya cikarildi (→397 mm).
- `measurement.py` + `depth_view.py` — CUDA cihazi mevcut oldugu icin ikisi de
  terk edilmis GPU dalini kullaniyordu (WLS'siz). GPU dali kaldirildi.

**Veri butunlugu:**
- `olcum_defteri.csv` iki farkli semada yaziliyordu; `_verify_distance`
  12 alanli satir + birlesik tarih-saat yaziyordu. Tek semaya oturtuldu
  (`tarih,saat,asama,parametre,ayar,deger,birim,not`), 66 satir tutarli.
  Yedek: `olcum_defteri.csv.bak`

**Ortam:**
- `subprocess.run(["python", ...])` → `sys.executable`. PATH'teki python
  conda base'i gosteriyordu (cv2 YOK), kalibrasyon yanlis yorumlayiciyla
  calisabilirdi.
- `calistir.bat` / `calistir.ps1` baslaticilari eklendi
- `.vscode/launch.json` + `tasks.json` — F5 ve Ctrl+Shift+B ile calistirma

**Digerleri:**
- `ground_plane.py` MJPG ayarlamiyordu ve cozunurluk dogrulamiyordu
- `d/f/v/r/b/m` tuslari Entry icine yazarken tetikleniyordu → `_key_guard`
- `SpinSlider` disaridan `set()` edilince kutu metni guncellenmiyordu
  (parlaklik −64 iken "0" gosteriyordu) → `trace_add` ile senkron
- `box_output.py` `if args.svg or True:` → `--svg` bayragi oluydu
- GUI'de RMS esigi sabit 0.4'tu, `calibration.py` olcekli limit kullaniyor

### Derinlik pipeline duzeltmeleri (olcumle)

**CLAHE kapatildi.** 6 gercek stereo ciftle olculdu:

| Konfigurasyon | Sicrama | >2px |
|---|---|---|
| CLAHE yok + parlaklik esleme + blur | **0.361** | **%1.5** |
| Eski kod (72cc70a) | 0.363 | %1.7 |
| CLAHE 2.0 (bozulma) | 0.419 | %2.1 |

CLAHE duz yuzeylerde gurultuyu yukseltip sahte eslesme uretiyordu.
`uniquenessRatio` da eski degerine (15) donduruldu.

**Histogram (CDF) ton eslemesi** eklendi, varsayilan. Dogrusal mean/std
transferi dogrusal olmayan ton farkini duzeltemiyordu:
ton farki 46.8 → 0.2, harita sicramasi 0.367 → 0.249.

**Sabit renk olcegi** eklendi (Z_min..Z_max). Otomatik olcek calisma
araligini 113-255 bandina sikistiriyordu; sabit olcek 0-255'e yayiyor
(~1.8x daha iyi renk ayrimi, kareler arasi karsilastirilabilir).

### Kamera kimligi duzeltildi
**SOL = idx2, SAG = idx1** (eskiden tersti). Uc bagimsiz yontemle dogrulandi:
disparity kapsama testi (%44.8 vs %18.0), yakin cisim parallaks yonu,
kullanicinin fiziksel gozlemi.

### Backend karari: MSMF'de kaliniyor
DSHOW denendi ve **kullanilamaz** cikti — MJPG anlasmasi yapamiyor, YUY2'ye
dusuyor: SOL 1280x720'a dustu, **1.0 FPS**. MSMF: 2048x1536, **29.1 FPS**.
(Dokumandaki "DSHOW tutarsizdi" notu muhtemelen MSMF'in bozuk geri
okumasindan kaynaklanan yanilgiydi — MSMF her seye ayni sabit degeri
dondurdugu icin "tutarli" gorunuyordu.)

### Kalici koruma mekanizmasi
- `_apply_all` artik **11 ozelligin hepsini** yaziyor, acilistan 1.2 ve 2.5 sn
  sonra tekrarliyor (MSMF ilk yazimi yutabiliyor)
- Ayarlar tabinda **"Ayarlari kameraya yeniden yaz"** butonu — tek adimda
  yazar ve olcerek dogrular
- **30 saniyede bir otomatik saglik kontrolu** — goruntuyu olcer,
  `cap.get()` kullanmaz; dengesizlikte durum cubugunda kirmizi uyari
- Rehber tabina "KAMERALAR DENGESIZ GORUNUYORSA" bolumu

### Odak esitleme
`src/odak_esitleme.py` yazildi — parlakliga duyarsiz metrik
(`var(Laplacian)/ortalama²`), tepe-tutma, canli cubuk.
Sonuc: **SOL 124.5 / SAG 119.1 = 1.05x**, ikisi de tepede.

### Renk farki — kabul edildi
SOL K/M 0.91, SAG 1.01. WB kontrolu **desteklenmiyor** (2800/4500/6500
denendi, goruntu degismedi). Ama etkisi kucuk:
gri tonlamaya yansiyan fark **%5.1**, histogram eslemesi sonrasi ton farki
4.40 → 0.80 (%82 azalma). Renkli ve notr bolgelerde fark ayni (%3.5 vs %3.7),
yani renge bagli degil. **Derinligi etkilemez, gecildi.**

### Yeni teshis araclari
| Dosya | Islev |
|---|---|
| `kalibrasyon_hazirlik.py` | Kalibrasyon on kosul kontrolu |
| `kamera_default_kontrol.py` | Saklanmis ayarlar + kalicilik testi (DSHOW) |
| `kamera_ayar_sifirla.py` | Iki kamerayi ayni ayarlara getir |
| `kamera_kimlik_testi.py` | SOL/SAG dogrulama + default karsilastirma |
| `kamera_denge_testi.py` | Acilis yarisi / kalici fark ayrimi |
| `odak_esitleme.py` | Canli odak esitleme (tepe bulma) |
| `parlaklik_esitle.py` | Pozlama + gain telafisi olcerek bulma |
| `renk_odak_teshis.py` | Renk dengesi + 3x3 odak haritasi |

### Olcum guvenilirlik denetimi eklendi
WLS filtresi bosluklari **tahminle** doldurdugu icin "gecerli piksel sayisi"
kontrolu dokusuz yuzeyde bile geciyordu — gurultu disparity'sinden (3.5 px)
uretilmis 2062 mm gibi sahte olcumlerin nedeni buydu.

Dort olcutlu denetim eklendi (`_measure_point`):

| Olcut | Esik | Yakaladigi |
|---|---|---|
| Yerel doku (std) | < 4.0 | dokusuz yuzey |
| Ham eslesme orani (WLS oncesi) | < %25 | harita dolgudan ibaret |
| Disparity yayilimi (IQR/medyan) | > %20 | ROI derinlik sinirini kesiyor |
| Olculebilir aralik | Z < 397 mm | arama araligi disi |

15 kayitli cekimle dogrulandi: hatali "2062 mm" olcumu **REDDEDILDI**
(doku 0.4). Guvenilmez olcum artik olcum defterine YAZILMIYOR.

Ayrica "Disparity %" gostergesi ikiye ayrildi: **ham** (gercek eslesme)
ve **dolgulu** (WLS sonrasi). Onceki "%99.9" degeri dolgudan geliyordu
ve kalite gostergesi degildi.

### Rapor taslagi olusturuldu
`docs/STAJ_RAPORU_TASLAK.md` — Ek-4'e aktarilmak uzere. Olculmus veriler
`[OLCULDU]`, bekleyen bolumler `[BEKLIYOR]` etiketli; her bekleyen bolumun
altinda olcum protokolu yazili.

---

## 2026-08-18 — Yeni Kalibrasyon ve Kare Kalitesi Analizi

### Ilk deneme basarisiz: stereo RMS 1.0053 (limit 0.853)
Odak degistigi icin yeniden kalibre edildi ama RMS limitin ustunde cikti.
Tekli RMS'ler zaten yuksekti (0.8948 / 0.9771); `CALIB_FIX_INTRINSIC`
kullanildigi icin stereo RMS bunlarin altina inemez — sorun stereo adiminda
degil, **kare kalitesindeydi**.

### Kok neden: az koseli ve karanlik kareler
Kare basina yeniden projeksiyon hatasi hesaplandi:

| Korelasyon | SOL | SAG |
|---|---|---|
| Kose sayisi ↔ hata | **−0.73** | **−0.78** |
| Parlaklik ↔ hata | −0.45 | −0.54 |

Eleme esigi **sabit 15**'ti — 96 kosenin %16'si, cok gevsek. 17-35 koseli
kareler geciyordu ve bunlar hatanin buyuk kismini uretiyordu.

| Esik | Kare | Stereo RMS |
|---|---|---|
| 15 (eski) | 35 | 1.0025 |
| 30 | 26 | 0.8755 |
| **38-40 (yeni)** | 25 | **0.8405** |
| 50 | 24 | 0.8340 |
| 60 | 22 | 0.7962 |

Geometri her senaryoda kararli (B 71.69-71.75 mm, f 1407.8-1412.7 px) —
eleme geometriyi bozmuyor, gurultuyu atiyor.

**Kod duzeltmesi:** `calibration.py` esigi tahta boyutuna **oransal** hale
getirildi (maks kosenin %40'i; 9×13 icin 38).

### Kadraj kapsamasi: sol sutun tamamen bostu
21 iyi karenin dagilimi olculdu — tahtanin merkezi hic kadrajin sol tarafina
getirilmemisti. Lens bozulmasi kenarlarda en buyuk oldugu icin sol kenar
**olculmemis, tahmin edilmis** oluyordu.

```
ONCE (21 kare)        SONRA (44 kare)
   0    0    6            4    3   11
   0    7    5            1    8    6
   0    2    1            5    2    4
```

14 kotu cift `frames/elenen/` klasorune tasindi (silinmedi), 23 yeni kare
cekildi. Yeni araç: `src/yedekle.py` — kare kalitesi + kapsama analizi,
`--uygula` ile eleme.

### Gecerli kalibrasyon (2026-08-18)

| Olcut | Deger |
|---|---|
| Kare sayisi | 44 (hicbiri elenmedi) |
| Stereo RMS | **0.8340** (limit 0.853) ✓ |
| Tekli RMS (sol/sag) | 0.7703 / 0.7682 |
| Baseline | 71.79 mm |
| f (P1, rektifiye) | **1418.18 px** |
| Epipolar y-hatasi | **0.389 px** ortalama |

### METODOLOJIK BULGU: RMS tek basina kalite olcusu degil
16 Agustos kalibrasyonu daha DUSUK RMS'e sahipti (0.7407) ama adil
karsilastirmada daha KOTU cikti:

| | Eski (16 Ağu) | Yeni (18 Ağu) |
|---|---|---|
| Stereo RMS | **0.7407** | 0.8340 |
| Epipolar ortalama | 0.519 px | **0.389 px** |
| Epipolar p95 | 1.489 px | **1.039 px** |
| >1 px hatali kose | **%13.6** | **%5.7** |

Rektifikasyonda %25 daha dusuk hata. Sebep: eski set az ve benzer pozlu
kare iceriyordu (sol sutun bos), model uydurmasi kolaydi → dusuk RMS ama
zayif kisit. **Kalibrasyon kalitesi RMS ile degil, epipolar hata ve kadraj
kapsamasi ile degerlendirilmeli.**

### Kamera dengesinin kalibrasyona etkisi olculdu
| Set | Sol RMS | Sag RMS | Fark |
|---|---|---|---|
| Eski (dengesiz kameralar) | 0.5950 | 0.6241 | 0.0291 |
| **Yeni (dengeli)** | 0.7703 | 0.7682 | **0.0021** |

Kameralar esitlendikten sonra iki tekli kalibrasyon neredeyse ozdes kalitede.
Onceki oturumdaki kamera dengesizligi calismasinin kalibrasyona somut
katkisi bu.

---

### Dogrulanmis referans ayarlar
```
exposure −4 (onerilen), gain 0, brightness 0, contrast 32,
saturation 64, sharpness 3, gamma 100, tum telafiler 0
SOL = idx 2, SAG = idx 1
Normal: parlaklik orani 1.02x, kontrast orani 1.09x
```

> **DUZELTME (2026-08-18, olculdu):** Yukaridaki "SOL kamera 200 altini
> reddediyor, bu yuzden GAMMA=300" sonucu **yanlis teshise dayaniyordu**.
> Gamma iki kameraya da yazildiginda olculen:
>
> | Gamma | Parlaklik orani | Kontrast orani | SOL/SAG |
> |---|---|---|---|
> | 300 | 1.18x | 1.20x | 188 / 159 |
> | **100** | **1.04x** | **1.02x** | **127 / 133** |
>
> 100 hem daha dengeli hem hedef parlaklik bandinin (90-150) ortasinda.
> Gecmiste 100'de olculen 2.76x fark, degerin kotu olmasindan degil,
> gamma'nin yalnizca BIR kameraya ulasmasindan kaynaklaniyordu:
> `kamera_ayar_sifirla.py` DSHOW ile 300 yaziyor, uygulama ise MSMF ile
> 100 yaziyordu ve o donemde `_apply_all` gamma'yi hic yazmiyordu.
>
> **Dogru kural: degerin kendisi degil, iki kamerada AYNI olmasi onemli.**
> `_apply_all` artik gamma'yi iki kameraya da yaziyor ve "Ayarlari
> kameraya yeniden yaz" bunu uc kez tekrarliyor (MSMF ilk yazimi
> yutabiliyor). Varsayilan 100'e dondu.


---

## 2026-08-19 — Tiklayarak Olcum, Zemin Cikarma Semantigi ve Kutu Gorseli

Gunun konusu: "tikladigim cismi olc" akisinin calisir hale getirilmesi.
Butun sonuclar gercek cekimlerle olculdu; referans cisim **termos
250 x 72 x 36 mm**, cekim `q_20260819_170641`, tiklama (1373, 1045),
mesafe ~610 mm.

### Zemin duzlemi yeniden tespit edildi
Uygulama ici tespit (`_detect_ground_plane`) tam cozunurlukte
(2048x1536), 8 kare ortalamasi ile calisiyor. Gunun uc tespiti:
16:05 (92 kose), 16:54 (80 kose, 79.9 derece), 17:01.

Duzlem artik **rektifiye** cercevede cozuluyor: `solvePnP` girdisi
rektifiye goruntu, intrinsik `P1[:3,:3]`, distorsiyon sifir. Dosyaya
`frame="rectified"` yaziliyor. Eski (ham cercevede kaydedilmis)
dosyalar okunurken `n_rekt = R1 @ n_ham` ile cevriliyor.

**Neden onemliydi:** `reprojectImageTo3D` ciktisi rektifiye cercevede,
duzlem ise ham cercevede cozuluyordu. Aradaki R1 rotasyonu 1.567 derece;
200 mm yanal uzaklikta **4.96 mm** yukseklik hatasi demek.

Planar poz belirsizligi icin `SOLVEPNP_IPPE` + `solvePnPGeneric` ile
iki cozum birden alinip derinlik uyumuna gore secilir. Dosyaya
`rms_px`, `aci_derece`, `tarih` de yazilir.

### `esik` parametresinin anlami — sik yanlis anlasiliyor
`esik (mm)` bir **duzlem otelemesi**, boyut filtresi degil. Kesme
duzlemi masadan `esik` kadar yukari tasinir ve **altinda kalan her sey**
silinir. Cisim masada durdugu icin **cismin alt `esik` kadari da gider.**
Bu bir hata degil, tanimin kendisi. Asagidaki "taban geri kazanimi"
bu kaybi olcup geri ekliyor.

### Zemin cikarma neden sahnenin buyuk kismini birakiyor
Sikayet: "zemin cikar" isaretliyken kalan piksel %60'in ustunde.
`q_20260819_165521` uzerinde olculdu (duzlem 16:54, 79.9 derece):

| | Oran |
|---|---|
| Gecerli piksel | %81.2 |
| Duzlem uzerinde (h mutlak deger < 15 mm) | **%11.7** |
| esik 12 mm ile atilan | %26.9 |
| Kalan | %73.1 |

Bagimsiz RANSAC ile sahnenin baskin duzlemi bulundu: kayitli duzlemle
**1.6 derece** fark, yani duzlem **taze ve dogru**, eskimemis.

**Aciklama:** zemin cikarma yalnizca **destek yuzeyini** siler, arka
plani degil. Kamera odaya bakarken masa cercevenin ancak %12'si;
duvar, raflar, oda gercekten masa duzleminin uzerinde:

| Yukseklik yuzdeligi | Deger |
|---|---|
| %25 | 9 mm |
| %50 | 85 mm |
| %75 | 509 mm |
| %90 | 866 mm |

**Ikinci etken: ekstrapolasyon hatasi.** Duzlem ~600 mm'de ~200 mm'lik
bir tahtadan cikariliyor, sonra 2000 mm'ye kadar uzatiliyor. Alt seritte
h medyani -1 mm, %25'lik dilim -17 mm cikiyor; uzak bolgede yamalar
duzlemin bazen ustune bazen altina dusuyor. 1 derecelik fit hatasi
2000 mm'de **35 mm** yukseklik hatasi yapar, 12 mm'lik esigin uc kati.

**Kural:** zemin cikarma yalnizca tespit tahtasinin bulundugu civarda
(+-300-400 mm) guvenilir. Olcum icin sorun degil, cunku tiklayarak
olcum tohum etrafinda ayrica 3B uzaklik siniri (varsayilan 250 mm)
uyguluyor.

### Tiklayarak olcum: uc kisit ve olculen katkilari
Derinlik surekliligi tek basina cismi masadan ayirmiyor; tabanda
derinlik sicramasi yok, bolge masaya siziyor. Uc kisit eklendi:

1. **Mesafeye gore olceklenen tolerans.** Sabit disparity toleransi
   yanlis: 6 px, 730 mm'de 63 mm derinlik kapsarken 1750 mm'de 365 mm
   kapsiyor (5.8 kat). Dogrusu `dd = f*B*dZ / Z^2`; kullaniciya **mm**
   sorulur, disparity degil.
2. **Parlaklik kisiti (`gri tol`).** Tohum pikselin gri degerinden
   `gri tol`'dan fazla sapan pikseller elenir. Olculdu (koyu termos /
   beyaz masa): kisit yok -> 340x272 mm, 45 -> 262x78, 35 -> 262x76,
   25 -> 258x70. Cisim ile yuzey ayni renkteyse ise yaramaz, 0 ile
   kapatilir.
3. **Kenar engeli (`kenar`).** Gauss bulanikligi + Sobel buyuklugu
   esigin ustundeki pikseller sifirlanir; bolge nesne sinirini asamaz.
   Bu sayede parlaklik kisiti gevsetilebiliyor (`gri 60 + kenar 60`
   ile 289x79x34 olculdu).

### Yuvarlak cisimler
Termos gibi silindirik cisimlerde tek kameradan yalnizca **on yay**
gorunur; PCA kutusunun en kisa ekseni gercek capin cok altinda cikar
(bu cekimde 11-28 mm, gercek 36 mm). `_yuvarlak_mi` cember uydurmasiyla
(Kasa yontemi) bunu tespit ediyor: kalinti/yaricap < 0.06 ve
yaricap < 0.60 x uzun kenar ise yuvarlak sayilip cap duzeltiliyor.
Duzlem acisi 60 dereceyi asiyorsa duzeltme uygulanmiyor (yay cok kisa).

### Kaldirilan kati kural: 60 derece kamera acisi
Duzlemle olcumde 60 derecenin ustundeki aci **hata** sayiliyordu.
Mevcut kurulumda kamera masaya ~80 derece ile bakiyor ve tasinamiyor;
bu kural her olcumu reddediyordu. **Uyariya** cevrildi. Yukseklik
gozlenebilirligi `cos(aci)`; 80 derecede 0.177 — sonuc gurultulu ama
uretiliyor, kullanici uyariyi gorup karar veriyor.

### RANSAC ile "masayi at" varsayilan KAPALI
Segmentlenen bolge zaten ince bir derinlik dilimi, yani **kendisi
duzlemsel**. RANSAC bolgenin %69-100'unu "duzlem" bulup cismi siliyordu.
Varsayilan kapatildi. Tohum duzlemin uzerinde kalirsa artik sessizce
baska bir bilesene dusmek yerine "TIKLANAN NOKTA DESTEK YUZEYINDE"
hatasi veriliyor. Onceki sessiz dusus **masa kenarini olcup termos
diye raporlamisti.**

### Kutu gorseli zemin kutucugunu HIC gormuyordu
`kutu_gorsel.py` `disparity_ham` anahtarini okuyor, yani **zemin
cikarilmamis** haritayi. Derinlik tabindaki "Zemin/masa cikar"
kutucugu ekrandaki haritayi degistiriyor ama kutu gorseline hic
girmiyordu. "Esigi 50 yapinca sonuc duzeldi" gozlemi bu yuzden
**yanlis nedene** baglanmisti; iyilesme tolerans/parlaklik
ayarlarindan geliyordu.

### OLCUM: zemin cikarma dogrulugu degil, DUYARSIZLIGI kazandiriyor
Ayni cekim, ayni tohum, iki harita, tolerans taramasi
(gercek 250 x 72 x 36 mm):

**parlaklik 60 + kenar 60 ile**

| tol | HAM (zemin duruyor) | ZEMIN CIKARILMIS (50 mm) |
|---|---|---|
| 8 mm | 162 x 74 x 16 | ayni |
| 12 mm | 190 x 75 x 21 | ayni |
| 20 mm | 274 x 77 x 42 | 205 x 78 x 30 |
| 35 mm | 274 x 83 x 58 | 205 x 86 x 45 |
| 60 mm | 274 x 92 x 87 | **205** x 96 x 73 |

**kisitlarin ikisi de KAPALI iken**

| tol | HAM | ZEMIN CIKARILMIS |
|---|---|---|
| 12 mm | 194 x 77 x 26 | 194 x 77 x 26 |
| 20 mm | **390 x 343** x 44 | **210** x 78 x 37 |
| 35 mm | **418 x 314** x 82 | **210** x 85 x 45 |
| 60 mm | **422 x 304** x 131 | **210** x 96 x 81 |

Dar toleransta (8-12 mm) iki harita **birebir ayni** — bolge zaten
duzlem bandina ulasmiyor. Tolerans buyuyunce ham harita masaya tasiyor
(390x343 = masanin kendisi), zemin cikarilmis harita **sabit kaliyor**
cunku sizinti fiziksel olarak imkansiz.

**Sonuc: zemin cikarmanin degeri, olcumu tol/parlaklik ayarina
duyarsiz kilmasi.** Rapor icin bu dogruluktan daha degerli, cunku
sonuc ayara gore oynamiyor.

### Taban geri kazanimi (`--zemin`)
Esigin kestigi band olculebilir: bolgenin duzleme en yakin noktasi
`h_alt` kadar yukarida kalir. Duzlem normaline en hizali ana eksen
bulunup o eksende `delta = h_alt / |v . n|` kadar uzatiliyor
(eksende delta ilerlemek yuksekligi `delta * (v . n)` kadar degistirir).
Hicbir eksenin normalle hizasi 0.20'nin altindaysa uzatma yonu
belirsiz sayilip dokunulmuyor.

Olculen (tol 30, gri 35, `--zemin`): taban geri kazanimi **+52.2 mm**,
sonuc **250.4 x 67.5 x 11.3 mm**. Gercek 250 x 72 x 36, yani uzun
kenarda **%0.2**, capta %6 hata (en kisa eksen yuvarlak cisimde zaten
gorunen yay kalinligi).

Kararlilik (tol 20 / 35 / 60): 253.9 / 253.8 / 253.9 mm.
Kisitlar tamamen kapaliyken bile 254.2 / 254.1 mm.

**Karar:** varsayilan davranis degismedi (ham harita). Yeni davranis
`kutu_gorsel.py --zemin` bayragi ve Olcum tabindaki **"zemin haritasi"**
kutucugu ile secilir. Cekim sirasinda zemin cikarma kapali idiyse
acikca hata verilir.

### Kutu gorselinde renk kodu
Her ana eksenin 4 kenari kendi renginde ve sol ustteki olcu ayni
renkte: UZUN yesil, ORTA acik mavi, KISA pembe. Hangi sayinin hangi
kenar oldugu tereddutsuz belli oluyor.

**Ders (bu oturumda yasandi):** aday bolgeleri "beklenen olculere
sayisal yakinlik" ile puanlayip en iyisini secmek DOGRULAMA DEGILDIR;
o yontemle masa kenari (234x55x39) termos diye raporlandi. Dogrulama,
gorselde kutunun cismi sarmasidir.

### Arayuz duzeltmeleri
- **Kaydirma yoktu**: Kalibrasyon tabinda 1071 px icerik 799 px alana
  siginiyordu, 272 px erisilemezdi. `_kaydirilabilir()` yardimcisi ve
  `<Enter>/<Leave>` + `bind_all` tekerlek baglamasi eklendi.
- **Olcum butonlari tasiyordu**: iki satira bolundu.
- **Katlanabilir bolumler acilmiyordu**: iki ayri hata vardi.
  (a) Icerigin master'i `parent` oldugu icin `pack(in_=sarmal)` onu
  sarmalin **arkasina** ciziyordu (yer kapliyor, gorunmuyordu).
  (b) Bos cerceve **istenen yuksekligini koruyor**, `configure(height=1)`
  gerekiyor.
  **Ders:** `winfo_ismapped()` bu iki durumda da True doner; arayuz
  gozle bozukken test "basarili" raporladi. Tk testi goruntuyle
  dogrulanmali.
- **Tiklama kaymasi** (iki hata): olcek donusumu Label'in **ortalama
  ofsetini** hesaba katmiyordu (sabit 989 px dikey kayma) ve kirpma
  (zoom) ofseti eklenmiyordu. Dogrusu
  `gx = kirpma_x + (event.x - ofset_x) / olcek`.
  Tekerlekle 1x-8x zoom ve cift tikla sifirlama eklendi.
- **Set yedekleme** (`Yeni Set Baslat`): yedege artik
  `charuco_config.json`, `camera_settings.json` ve `SET_BILGI.txt`
  de giriyor; geri yukleme bunlari yerine koyuyor. Isimler zaman
  damgali, onceki durum `calibration/_oncekiler/` altina aliniyor.
  Gidis-donus test edildi.

### Kalibrasyon kalitesi: sinirlayici etken kalibrasyon DEGIL
44 cift / 3264 kose uzerinde olculen epipolar hata **0.420 px**.
RMS tabani ~0.44 px ve bu **kose lokalizasyon gurultusu**; kare
atarak RMS dusuruluyor ama epipolar hata **kotulesiyor**. Distorsiyon
modelini buyutmek de fayda vermedi. Yani mevcut olcum hatalarinin
kaynagi kalibrasyon degil, goruntu geometrisi ve segmentasyon.
Olcumun kendi oturma sacilimi ~%4.3.

### Yeni/degisen dosyalar
| Dosya | Ne |
|---|---|
| `src/kutu_gorsel.py` | 3 panelli dogrulama gorseli, renk kodlu kutu, `--zemin` |
| `src/tikla_olc.py` | CLI tiklayarak olcum + PCA kutusu |
| `src/cisim_olc.py` | Kayitli cekimden duzlem tabanli boyut olcumu |
| `src/pozlama_teshis.py` | Pozlama taramasi |
| `src/goruntu_ayar_teshis.py` | Goruntu ayari taramasi |

`.gitignore` ile `calibration/frames*/` ve `output/` haric tutuldu
(442 MB -> 0.6 MB). `.gitattributes` eklendi: `*.npz *.npy *.png *.pdf`
ikili olarak isaretli.


---

## Yapilacaklar / Sonraki Adimlar

### Tamamlandi (2026-08-17 / 18 / 19)
- [x] Kamera dengesizligi cozuldu (parlaklik 1.02x, kontrast 1.09x)
- [x] Odak esitlendi (SOL 124.5 / SAG 119.1 = 1.05x)
- [x] Eski kalibrasyon kareleri arsivlendi (odak degistigi icin gecersizdi)
- [x] Yeni kalibrasyon yapildi (2026-08-18) — epipolar hata 0.420 px
- [x] Zemin duzlemi rektifiye cercevede, uygulama icinden tespit
- [x] Tiklayarak olcum + kutu gorseli + taban geri kazanimi

### HEMEN
- [ ] **Lens vidalarini sabitle** (oje/kilit vidasi) — odak oynamamali
- [ ] **Desen olcusunu kumpasla dogrula**: 5 kare olc, 5'e bol.
      `charuco_config.json` 20.0 mm diyor; rapor olcumlerinden ONCE teyit et.
      Yanlissa tum mutlak olcumler ayni oranda kayar.
- [ ] Olcum defterindeki iki GECERSIZ satiri rapora alma
      (metre/mm hatasi ve 80 derece duzlem)

### Oncelikli — rapor verisi
1. [ ] Mesafeye gore hata egrisi (5.2) — en az 4 mesafede olcum
2. [ ] Tekrarlanabilirlik testi (5.3) — 10 olcum, std sapma.
       Not: olcumun kendi oturma sacilimi ~%4.3 olculdu, bunun altina inmez.
3. [ ] Calisma zarfi (5.4) — min/maks mesafe
4. [ ] Kalibrasyon kalitesinin etkisi (5.5)
5. [ ] Yontem karsilastirmasi (5.6) — ham harita vs `--zemin`
       (tablo hazir: zemin cikarma ayara duyarsizlik kazandiriyor)
6. [ ] Ana sonuc tablosu (5.9) — 5 cisim x 3 boyut.
       Her satir icin kutu gorseli uret, gorselle dogrula.

### Orta Vadeli
7. [ ] GPU destegini WLS ile birlikte geri ekle (performans)
8. [ ] Pozlama/aydinlatma duyarliligi testi (5.7)
9. [ ] Mekanik kararlilik testi (5.8) — 0/2/24 saat epipolar hata

### Son Asamalar
9. [ ] Kesim yonergesiyle fiziksel kutu dogrulama (5.10)
10. [ ] Rapor yazimi (Ek-4 sablonu)
11. [ ] Demo hazirligi (canli gosterim)
12. [ ] Mevcut degisiklikleri commit'le

---

## Onemli Notlar

- **Odaga dokunma!** Lens odagi kalibrasyondan sonra degisirse yeniden kalibrasyon gerekir
- Pozlama/gain/WB degisiklikleri kalibrasyonu etkilemez, sadece goruntu kalitesini etkiler
- Kalibrasyon lens geometrisine bagli, aydinlatma ayarlarina degil
- Olcum defteri (`data/olcum_defteri.csv`) her olcumde guncellenecek
- Desen olcusu: yazicidan cikan deseni kumpasla olc, OLCULEN degeri koda gir
