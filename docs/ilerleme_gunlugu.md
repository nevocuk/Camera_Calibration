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

## 2026-08-20 — Segmentasyon Yontemleri, Duzlem Dogrulama, Arayuz Ipuclari

Gunun konusu: "tikladigim cismi olc" akisinin **guvenilir** hale
getirilmesi. Bes ayri yontem denendi, ucu ise yaradi, ikisi kokten
calismadi ve nedeni olculdu. Referans cisimler: termos 250 x 72 mm,
ayakta sise ~250 x 72 mm.

### KARE OLCUSU DOGRULANDI — bekleyen madde kapandi
Komsu ChArUco koselerinin **3B mesafesi** olculdu. Bu, config'deki
`olculen_kare_boyutu_mm` degerini hic kullanmayan bagimsiz bir
kontrol (dairesel degil):

| | Deger |
|---|---|
| 20 cekimde medyan | **20.05 mm** |
| Ortalama / salinim | 20.14 / 0.36 mm |
| Config | 20.00 mm |
| Oran | **1.0023 (+%0.2)** |

Config dogru, kalibrasyon olcegi dogru. Kumpasla dogrulama gerekmiyor.

### Kamera tepeye alindi — bir sorunu cozdu, bir sorun acti
Kamera masaya ~80 dereceyle bakarken 26-28 dereceye alindi.

**Cozdugu:** egik bakista blok esleme bozuluyordu (7 px'lik blok
boyunca 3.99 px disparity degisimi). Mesafe 610 -> 470-590 mm indi,
derinlik adimi 3.65 -> 2.42 mm.

**Actigi:** cisim AYAKTA dururken uzun ekseni **bakis
dogrultusuna** dondu. Olculdu (termos, tepeden, ayakta):

| tol | UZUN | Gercek |
|---|---|---|
| 30 mm | 87 x 77 x 36 | 250 x 72 |
| 60 mm | 140 x 70 x 32 | |

Bolge cismin 250 mm'sinin ancak 76-139 mm'lik bir **derinlik
dilimini** kapsiyor.

**Kural (tek cumle):** kamera cismin en buyuk yuzlerini gormeli;
**kameraya dogru bakan eksen olculemeyen eksendir.** Tepeden bakis
masada YATAN cisimler icin dogru, AYAKTA duran uzun cisim icin en
kotu acidir. Termos yatirilinca uzun eksen 78 -> 284 mm'ye cikti.

### Sanal kamera dondurme: yapilabilir ama FAYDASIZ
"3B noktalari dondurup baska acidan baksak" fikri olculdu.

Dondurme bir koordinat degisimidir; gurultu de birlikte doner,
buyuklugu degismez. Asil sinir gurultunun YONE GORE esit olmamasi:

| Z | YANAL (Z/f) | DERINLIK (Z²/(f·B)) | oran |
|---|---|---|---|
| 400 mm | 0.28 mm | 1.57 mm | 5.6x |
| 550 mm | 0.39 mm | 2.97 mm | **7.7x** |
| 1000 mm | 0.71 mm | 9.82 mm | 13.9x |

Oran tam olarak **Z / B**, yani tek belirleyici baz uzunlugu
(71.79 mm). 550 mm'de orani 1'e indirmek icin baz 550 mm olmali.

**Ama gurultu zaten darbogaz degil.** 46 adet 120x120 masa yamasinda
yerel duzlemsel sacilim olculdu:

| | Deger |
|---|---|
| Medyan sacilim | **1.15 mm** |
| Disparity karsiligi | 0.44 px |
| Karsilastirma: olculen epipolar hata | 0.420 px |

Iki bagimsiz olcum ayni sayiyi veriyor. Gordugumuz olcum hatalari
30-60 mm, yani sensor gurultusunun **30-50 kati**. Darbogaz
**segmentasyon**, geometri ya da hassasiyet degil. Baz uzunlugunu
buyutmek bu yuzden listede yok.

### Duzlem dogrulama: uyari mekanizmasi ve sinirlari
Tespit metrikleri (kose sayisi, izdusum hatasi) tahtanin NEREDE
oldugunu soylemiyor. Uygulama artik tespit sonrasi duzlemi sahnenin
kendi baskin duzlemiyle (RANSAC) karsilastiriyor; oteleme > 15 mm ya
da aci > 10 derece ise kirmizi uyari veriyor.

Esikler olculdu (5 cekim x 6 RANSAC kosusu): **oteleme kararli**
(48-56 mm, salinim +-1.5 mm), **aci oynak** (2.4-11 derece, RANSAC
bazen masa yerine laptop yuzeyini seciyor). Asil olcut oteleme.

**Yanlis teshis ve duzeltmesi:** 30-53 mm'lik otelemeyi solvePnP'nin
duz desen poz belirsizligine bagladim. **Olcum bunu curuttu.**
Duzlem solvePnP yerine tahtanin stereo derinliginden de uydurulup
23 cekimde karsilastirildi:

| | Deger |
|---|---|
| Iki yontem arasi fark | **3.4 mm / 0.60 derece** (medyan) |
| Tahtanin kendi uzerinde yukseklik | solvePnP 1.04 mm, derinlik 0.33 mm |

Iki bagimsiz yontem ayni duzlemi veriyor. Kose sayisi dustugunde
(13-17 kose) solvePnP cokuyor, derinlik yontemi dayaniyor
(`q_20260819_144828`: solvePnP +259.97 mm, derinlik -1.90 mm).
30+ kose varken ikisi denk.

### Otelemenin gercek nedeni: TEKRARLI DESENDE STEREO ESLEME BOZULMASI
Tahta sahnedeyken cekim alindi ve dogrudan olculdu:

| | d (mm) |
|---|---|
| Tahta duzlemi | 526.8 |
| Cevresindeki masa | 527.8 |
| Aralarindaki aci | **0.22 derece** |
| Tahtanin kalinligi | **2.1 mm** |

Tahta masaya tam duz yatiyor — yerlestirme dogru. Ama tahtanin
UZERINDEKI derinlik bozuk:

| | Bu cekim | Saglikli cekim |
|---|---|---|
| Tahtada mesafe dagilimi | **410 – 656 mm** | ~25 mm |
| Disparity salinimi | **37.4 px** | 8.9 px |
| Olculen kare boyu | **21.68 mm** | 20.0 mm |
| Disparity tepeleri | 168 / 239 / 250 / 260 px | tek tepe 159 px |

Duz bir tahtanin mesafesi 250 mm'lik bir aralikta saçilamaz. ChArUco
**tekrarli** bir desen; blok esleme bazi bloklarda yanlis kareye
kilitleniyor. Cevredeki duz beyaz masa temiz olculuyor (kalinti
1.64 mm) — sorun yuzeyde degil desenin periyodikliginde.

**Eklenen koruma:** sahne karsilastirmasindan once tahtadaki
disparity salinimina bakiliyor; 20 px'i asarsa karsilastirma
yapilmiyor ve "TAHTADA DERINLIK BOZUK" uyarisi veriliyor.
**Pratik cozum:** tahtayi biraz uzaklastir (~650 mm); arsivdeki
saglikli tespitlerin hepsi 590-653 mm arasindaydi.

### Zemin esigi artik NEGATIF olabilir
Alt sinir 3 mm'den **-60 mm**'ye acildi. Gerekce: tespit edilen
duzlem masa degil tahtanin UST yuzeyidir; tahtayi kaldirip cismi
koyunca cismin tabani duzlemin altinda kalir.

**Ama tek basina yetmiyor** (olculdu). Gercek masa pikselleri
uzerinde `kayitli duzlem - gercek duzlem`:

| | Deger | Esikle duzelir mi |
|---|---|---|
| Ortalama | -44.2 mm | **Evet** (sabit oteleme) |
| Salinim | 20.4 mm | **Hayir** (egimden) |
| %5-%95 yayilimi | 69 mm | **Hayir** |

Aci farki 7.8 derece, masanin gorunen genisligi 484 mm ve
`484 x tan(7.8) = 66 mm` — yayilimi tam olarak egim aciklıyor.
Egik bir duzlem kaydirmakla duzelmez.

---

## SEGMENTASYON YONTEMLERI — bes deneme

Hepsi ayni soruya cevap ariyor: "tiklanan piksel hangi cisme ait?"

### 1. Derinlik toleransi (mevcut varsayilan)
`floodFill` + `FLOODFILL_FIXED_RANGE`: her piksel **tohumla**
kiyaslanir, farki `tol`u asan alinmaz. Tolerans mesafeye gore
olceklenir (`dd = f*B*dZ/Z²`).

**Calistigi durum:** cisim goruntu duzlemine paralel uzaniyorsa.
**Coktugu durum:** cisim bakis dogrultusunda uzaniyorsa. Olculdu
(ayakta sise, tepeden): tol 15/30/60 -> **65 / 83 / 158 mm**
(gercek ~250).

### 2. Parlaklik SEVIYESI (`gri tol`) — kismen
Tohumun gri degerinden sapan pikseller elenir.
Olculdu (koyu termos / beyaz masa): kisit yok 340x272, 45 -> 262x78,
25 -> 258x70.
**Sinir:** cisme bagimli. Cismin kendi kapagi/etiketi farkli
renkteyse onu da atar; acik renkli cisimde hic calismaz.

### 3. Kenar + basamak engelleri (`kenar`, `basamak`) — kismen
`kenar` = parlaklik basamagi |grad I|, `basamak` = derinlik basamagi
|grad Z| (mm/px). Esigi asan pikseller duvar yapilir.

Esik dayanagi olculdu: duz yuzey 0.2-2 mm/px, cisim siniri 10+ mm/px.

**Kazanci — kararlilik.** ORTA eksenin tol 15/30/60 yayilimi,
6 cekim:

| Ayar | Yayilimlar |
|---|---|
| gri35 + kenar60 | 15 / 24 / 3 / 31 / 65 / 16 mm |
| gri35 + kenar30 + **basamak3** | **3 / 0 / 3 / 12 / 31** / 24 mm |

**Sinir 1:** cisim destek yuzeyine DEGDIGI yerde basamak yoktur
(yatik silindir masaya tegettir). Tek basina 392.9 mm veriyor ve
esigi 3'ten 12'ye cikarmak hicbir sey degistirmiyor.

**Sinir 2 — asil olan:** bir engel bolgeyi **buyutemez, ancak
kucultebilir.** Bolge zaten cismin ortasinda duruyorsa engel hic
devreye girmez. Olculdu (ayakta sise, tol 30):

| | Deger |
|---|---|
| Bolge | 34.010 px = gercek cismin **%25**'i |
| Bolgenin Z araligi | 444-504 mm |
| **Durdugu yerdeki basamak** | **3.91 mm/px** (yani kenar YOK) |
| Cismin gercek siluetindeki basamak | 48.57 mm/px |

Bu yuzden `kenar`/`basamak` ayakta duran cisme tepeden bakarken
sonucu **hic degistirmiyor**.

### 4. Yukseklik kriteri (`yukseklik`) — CALISIYOR
Yayilma yok. Her piksel sabit bir referansa karsi olculur:
**duzlemden >= h mm yukarida VE tiklamaya duzlem uzerinde <= r mm
yanal uzaklikta.** Tolerans hic kullanilmaz.

Olculdu (ayakta sise, gercek ~250 mm):

| Ayar | Sonuc |
|---|---|
| Derinlik toleransi 15/30/60 | 65 / 83 / 158 mm |
| h=15 yanal=45 | **248.4 mm** |
| h=15 yanal=70 | 247.4 mm |
| h=25 yanal=45 | 247.7 mm |
| h=25 yanal=70 | 247.0 mm |

**Sinir:** gecerli bir zemin duzlemi gerektirir.

### 5. Watershed (`watershed`) — CALISIYOR, duzlem gerektirmez
Once ayrimin gercekten iyi oldugu dogrulandi:

| | \|grad I\| medyan | \|grad Z\| medyan |
|---|---|---|
| Siluet | 108.3 | 22.28 |
| Cismin ici | 5.7 | 0.22 |

19-100 kat ayrim var, yani **esik sorunu yok**. O halde bu duvarlari
`floodFill`'e verip toleransi serbest biraksak?

**Denendi, tutmadi:**

| Ayar | Kapsam | Saflik |
|---|---|---|
| kenar 30 basamak 3 | %43 | %9 |
| kenar 20 basamak 2 | %39 | %87 |
| kenar 80 basamak 10 | %98 | %17 |

Bosluk kapatma (3/5/7/9 px) da duzeltmiyor. Sebep **topolojik**:
floodFill'in tutmasi icin duvarin HER YERDE kapali olmasi gerekiyor;
olculdu, siluetin en fazla **%86**'si duvar oluyor ve kalan %14'un
tek bir pikselinden bolge kaciyor.

**Watershed bu sarti gerektirmiyor** — her piksel gradyan
sirtlarini asmadan ulastigi en yakin isaretciye atanir; tek delik
her seyi bozmaz. Isaretciler: tiklanan nokta cevresi = cisim,
uzak halka = arka plan.

| Ayar | Sonuc | Kapsam | Saflik |
|---|---|---|---|
| ic_r 25, dis_r 400 | **248.9 x 75.9** | %99 | %93 |
| ic_r 25, dis_r 550 | 249.0 x 76.1 | %98 | %93 |
| ic_r 60, dis_r 400 | 248.9 x 75.9 | %99 | %93 |
| ic_r 60, dis_r 550 | 249.0 x 76.0 | %98 | %93 |

Ayara duyarsiz, yukseklik kriteriyle ayni dogrulukta ve **zemin
duzlemi gerektirmiyor**.

**Onemli:** watershed yalnizca PARLAKLIK uzerinde calistirilmali.
Derinligi karistirmak olculdu ve bozuyor (kapsam %99 -> %60-82,
saflik %93 -> %45-69) — WLS ile yumusatilmis derinlik haritasinin
kenarlari parlaklik kadar keskin degil.

### Ozet — hangi durumda hangisi

| Durum | Yontem |
|---|---|
| Cisim goruntu duzlemine paralel yatiyor | derinlik toleransi + `gri`/`kenar`/`basamak` |
| Cisim ayakta, kamera tepeden | **`watershed`** (duzlem gerekmez) ya da `yukseklik` |
| Duzlem guvenilir ve taban olcusu de lazim | `yukseklik` + taban geri kazanimi |

---

### Arayuz: ipucu balonlari
19 kontrole hover aciklamasi, 6 adet `?` isareti eklendi. Metinler
olculen sayilari tasiyor (CLAHE sicrama 0.361->0.419, gri tol
340x272 -> 258x70, watershed 65/83/158 -> 248.9) — kullanici degerin
neden oyle secildigini goruyor.

`Ipucu` sinifi: Toplevel + overrideredirect, 450 ms gecikme, ekran
kenarindan tasmama. Test edildi (balon olusuyor, metni dogru,
konumlaniyor, fare cikinca yok oluyor); `winfo_ismapped()` yerine
pencere nesnesi ve icerik dogrulandi.

### Yeni/degisen dosyalar
| Dosya | Ne |
|---|---|
| `src/kutu_gorsel.py` | `--kenar --basamak --yukseklik --watershed --zemin` |
| `src/camera_test.py` | Ipucu altyapisi, duzlem dogrulama, negatif esik, 4 yeni segmentasyon kutusu |


### GERIYE MI GITTIK? Olculdu - HAYIR, ama geometri bozuldu (2026-08-20)

Sikayet: son olcumler kotulesti. Ayni cekimde eski ve yeni yol
karsilastirildi (`q_20260820_141234`, tikla 1076,674):

| Ayar | UZUN |
|---|---|
| Kullanicinin ayari (kenar 50 + basamak 50) | 203.9 mm |
| **Eski varsayilan (kenar/basamak hic yok)** | **204.8 mm** |

Yeni secenekler o karede **hicbir sey degistirmemis**; eski kod da
ayni sonucu verirdi. Kod geriye gitmemis.

**Degisen sey GEOMETRI.** Ayni kod, ayni ayarlar, farkli cekimler
(termos, gercek 250 x 72 mm):

| Cekim | Z | Bakis | tol 15/30/60 -> UZUN | Yayilim |
|---|---|---|---|---|
| 170641 | 610 mm | YANDAN, dik | 252.3 / 252.2 / 252.2 | **0.1 mm** |
| 172145 | 609 mm | YANDAN, dik | 256.8 / 256.8 / 256.8 | **0.0 mm** |
| 172354 | 625 mm | YANDAN, dik | 254.5 / 255.2 / 255.2 | 0.7 mm |
| 093039 | 561 mm | tepeden, yatik | 270.9 / 290.5 / 310.1 | **39 mm** |
| 141234 | 718 mm | tepeden, yatik | 177.8 / 204.7 / 264.6 | **87 mm** |

Asil fark dogruluk degil **toleransa duyarsizlik**: iyi kurulumda
sonuc tolerans ayarindan bagimsiz, kotu kurulumda 39-87 mm oynuyor.

**Neden 718 mm kotu:** derinlik hassasiyeti mesafenin KARESIYLE
kotulesiyor - 560 mm'de 3.09 mm/px, 718 mm'de 5.06 mm/px (%64 daha
gurultulu) ve cisim cercevede kuculuyor.

**Parlaklik/engel ayarlari sinirlayici DEGIL** (141234 uzerinde):

| Ayar | UZUN |
|---|---|
| gri 45 | 204.8 |
| gri 90 | 205.2 |
| gri KAPALI + kenar 30 | 203.7 |
| gri kapali + kenar 20 + basamak 3 | 203.7 |
| watershed 250 | 214.6 |

Hepsi ayni yerde duruyor - sinirlayici mesafe.

### SADELESTIRME (2026-08-20)

Yukaridaki olcum uzerine Olcum tabi sadelestirildi. Deneysel
kontroller SILINMEDI (olculmus bilgiyi kaybetmemek icin) ama
gunluk kullanimda gorunmuyorlar.

**Onde kalan (kanitlanmis):** tol mm, gri tol, sinir, masayi at,
zemin haritasi, Kutu gorseli, Duzlemle olc.

**"Deneysel yontemler (kotu geometri icin)" bolumune alinan,
VARSAYILAN KAPALI:** kenar, basamak, yukseklik, watershed.
Gerekce: dordunun de IYI geometride sonucu degistirmedigi olculdu
(170641'de kenar/basamak acik ve kapali sonuc ayni).

**Eklenen "Onerilen ayarlar" butonu** her seyi olculen en iyi
degerlere dondurur: tol 30, gri 35, sinir 300, deneyseller sifir.
Bu ayarlarla uc iyi cekimde dogrulandi: 252.2-256.8 mm.

**Tabin ustune kalici rehber eklendi:** "kamera cisme YANDAN
baksin, mesafe 550-650 mm, cisim DIK dursun".

`sinir` varsayilani 250 -> 300 yapildi. Sebep: `sinir` tohumdan
YARICAP; 250 mm'lik bir cismin ucuna tiklanirsa diger uc sinirin
disinda kalabilir. Uc iyi cekimde 250 ve 300 ayni sonucu veriyor,
yani degisiklik zararsiz.

### Zemin duzlemi 14:08'de yine kaydi
`q_20260820_141234` uzerinde: kayitli duzlem 489 mm, sahnenin
gercek duzlemi 529 mm, fark **41 mm**. Tohumun duzleme gore
yuksekligi **-128 mm** (duzlemin ALTINDA), bu yuzden `yukseklik`
kriteri hic sonuc uretmedi. Duzlem sorunu (ChArUco periyodik deseni)
hala acik.


### RAPOR VERISI URETICISI (2026-08-20)

`src/rapor_verisi.py` - staj raporu icin veriyi elle kopyalamak
yerine kayitli cekimlerden YENIDEN olcup uretir. Kod ya da
kalibrasyon degisirse tablolar da degisir; elle kopyalanan sayi
dogrulanamaz.

**Girdi:** `data/rapor_olcumleri.csv` - hangi cekimde nereye
tiklandi, cismin GERCEK olculeri ne. Yeni olcum eklemek icin bu
dosyaya satir eklemek yeterli.

**Cikti:**

| Dosya | Icerik |
|---|---|
| `rapor_olcumler.csv` | her olcum + hata yuzdesi |
| `rapor_duyarlilik.csv` | tol 15/30/60 taramasi ve yayilim |
| `rapor_sistem.csv` | sistem parametreleri ve turevleri |
| `rapor_tablolari.md` | rapora yapistirilabilir markdown tablolar |
| `rapor_dogrulama_levhasi.png` | bes dogrulama gorseli tek levhada |

`--gorsel` bayragi her olcum icin `kutu_gorsel.py` ciktisini da
uretir ve tek levhada birlestirir. Hata %5'in altindaysa serit
basligi yesil, ustundeyse kirmizi.

**Uretilen ana sonuc tablosu (tol 30, gri 35, sinir 300):**

| Cisim | Bakis | Mesafe | Gercek UZUN | Olculen | Hata |
|---|---|---|---|---|---|
| termos | yandan | 610 mm | 250 | 252.2 | **+0.9%** |
| termos | yandan | 609 mm | 250 | 256.8 | +2.7% |
| termos | yandan | 625 mm | 250 | 255.2 | +2.1% |
| termos | tepeden | 561 mm | 250 | 290.5 | +16.2% |
| termos | tepeden | 718 mm | 250 | 204.7 | -18.1% |

Levhada gozle de goruluyor: yandan olcumlerde kutu cismi sariyor,
tepeden olcumlerde sarmıyor.

**Rapor bolumlerinin durumu (araç kendi ciktisinda da yaziyor):**

| Bolum | Durum |
|---|---|
| 5.2 Mesafeye gore hata egrisi | KISMEN - 3 nokta var, ayni bakisla 4+ gerek |
| 5.3 Tekrarlanabilirlik | YOK - ayni kurulumda 10 olcum |
| 5.4 Calisma zarfi | TEORIK - olcumle dogrulanmali |
| 5.5 Kalibrasyon kalitesinin etkisi | YOK |
| 5.6 Yontem karsilastirmasi | **VAR** - duyarlilik tablosu |
| 5.9 Ana sonuc tablosu | KISMEN - 1 cisim, 5 gerek |
| 5.10 Fiziksel dogrulama | YOK |


### KURULUM KONTROLU - uygulama artik geometriyi kendisi denetliyor (2026-08-20)

Olcum tabina "Kurulum kontrolu" butonu eklendi. ChArUco GEREKMEZ;
sahnenin baskin duzlemi canli derinlikten RANSAC ile bulunup
normali ile optik eksen arasindaki aciya bakiliyor.

**Sinyal olculdu, tereddutsuz ayiriyor:**

| Cekim | Gercek bakis | Olculen duzlem acisi |
|---|---|---|
| 170641 | yandan | 75.0 derece |
| 172145 | yandan | 80.5 derece |
| 172354 | yandan | 78.4 derece |
| 093039 | tepeden | 16.4 derece |
| 110729 | tepeden | 20.8 derece |
| 141234 | tepeden | 28.6 derece |
| 144837 | tepeden | 24.7 derece |

Arada **46 derecelik** bosluk var; esik 55 derece secildi.
Ikinci kontrol mesafe: onerilen bant 500-680 mm.

**Dogrulama:** bes gercek cekimde 5/5 dogru karar
(`yandan -> IYI`, `tepeden -> UYGUN DEGIL`).

Butonun soyledigi sey olculmus bir gercek: ayni kod ve ayarlarla
yandan bakista hata %0.9-2.7 ve tolerans yayilimi 0.0-0.7 mm,
tepeden bakista yayilim 39-87 mm - yani sonuc tolerans secimine
bagli hale geliyor ve tek bir sayi olarak raporlanamaz.

---

## Yapilacaklar / Sonraki Adimlar

### Tamamlandi (2026-08-17 / 18 / 19 / 20)
- [x] Kamera dengesizligi cozuldu (parlaklik 1.02x, kontrast 1.09x)
- [x] Odak esitlendi, eski kalibrasyon kareleri arsivlendi
- [x] Yeni kalibrasyon (2026-08-18) - epipolar hata 0.420 px
- [x] Zemin duzlemi rektifiye cercevede, uygulama icinden tespit
- [x] Tiklayarak olcum + kutu gorseli + taban geri kazanimi
- [x] **Kare olcusu dogrulandi** - 20 cekimde 20.05 mm (config 20.00)
- [x] **Segmentasyon: bes yontem denendi**, watershed ve yukseklik
      kriteri calisiyor (ayakta sise 248.9 mm, gercek ~250)
- [x] Duzlem sahneye karsi dogrulama + bozuk-derinlik korumasi
- [x] Arayuz ipucu balonlari (19 kontrol)

### HEMEN — rapor olcumlerinden once
- [ ] **Lens vidalarini sabitle** (oje/kilit vidasi) - odak oynamamali
- [ ] **Zemin duzlemini duzelt**: tahtayi ~650 mm'ye uzaklastir ve
      yeniden tarat. 585 mm'de tekrarli desen blok eslemeyi bozuyor
      (disparity salinimi 37.4 px). Uyari cikmazsa duzlem guvenilir.
- [ ] **Olcum yontemini sabitle**: rapor olcumlerinin tamami ayni
      yontemle alinmali. Onerilen `watershed` (duzlem gerektirmiyor,
      ayara duyarsiz, %99 kapsam / %93 saflik).
- [ ] Olcum defterindeki iki GECERSIZ satiri rapora alma

### Oncelikli — rapor verisi (henuz HIC toplanmadi)
1. [ ] **Mesafeye gore hata egrisi (5.2)** - en az 4 mesafede olcum.
       Calisma araligi 400-900 mm; her mesafede ayni cisim.
2. [ ] **Tekrarlanabilirlik (5.3)** - ayni mesafede 10 olcum, std sapma.
       Not: olcumun kendi oturma sacilimi ~%4.3 olculdu, altina inmez.
3. [ ] **Calisma zarfi (5.4)** - min/maks mesafe.
       numDisparities=256 ile en yakin 397 mm (olculdu).
4. [ ] **Kalibrasyon kalitesinin etkisi (5.5)**
5. [ ] **Yontem karsilastirmasi (5.6)** - tablo BUYUK OLCUDE HAZIR:
       derinlik toleransi / yukseklik kriteri / watershed
       (65-158 vs 247-248 vs 248.9 mm), ham vs zemin haritasi
6. [ ] **Ana sonuc tablosu (5.9)** - 5 cisim x 3 boyut.
       Her satir icin kutu gorseli uret ve GORSELLE dogrula
       (sayisal yakinlik dogrulama degildir - bir kez masa kenari
       termos diye raporlandi).

### Orta Vadeli
7. [ ] Pozlama/aydinlatma duyarliligi testi (5.7)
8. [ ] Mekanik kararlilik testi (5.8) - 0/2/24 saat epipolar hata
9. [ ] GPU destegini WLS ile birlikte geri ekle (performans)

### Son Asamalar
10. [ ] Kesim yonergesiyle fiziksel kutu dogrulama (5.10)
11. [ ] Rapor yazimi (Ek-4 sablonu)
12. [ ] Demo hazirligi (canli gosterim)

### Bilinen acik konular
- Zemin duzlemi sahneden 30-57 mm ve 7.8 derece sapiyor. Kaynak
  ChArUco'nun periyodik deseninde stereo esleme bozulmasi; tahtayi
  uzaklastirmak cozmeli, dogrulanmadi.
- Watershed ve yukseklik kriteri YALNIZCA bir cekimde (ayakta sise)
  karsilastirildi. Rapor oncesi en az 3 cisimde tekrarlanmali.
- Yuvarlak cisimlerde en kisa eksen hala gorunen yay kalinligi
  (tek bakis acisindan kacinilmaz).

---

## Onemli Notlar

- **Odaga dokunma!** Lens odagi kalibrasyondan sonra degisirse yeniden kalibrasyon gerekir
- Pozlama/gain/WB degisiklikleri kalibrasyonu etkilemez, sadece goruntu kalitesini etkiler
- Kalibrasyon lens geometrisine bagli, aydinlatma ayarlarina degil
- Olcum defteri (`data/olcum_defteri.csv`) her olcumde guncellenecek
- Desen olcusu: yazicidan cikan deseni kumpasla olc, OLCULEN degeri koda gir
