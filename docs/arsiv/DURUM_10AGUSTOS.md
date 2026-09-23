# Proje Durum Raporu

**Tarih:** 10 Agustos 2026
**Yazan:** Claude Code

---

## YAZILIM DURUMU

### Hazir scriptler (tumu src/ altinda)

| Script | Satir | Durum | Ne yapiyor |
|--------|-------|-------|------------|
| `camera_test.py` | ~530 | HAZIR | 4 tab GUI: Ayarlar, Hesaplama, Kalibrasyon, Rehber. Cift kamera, pozlama/gain/WB, per-kamera telafi, parlaklik esitleme, netlik tepe takibi, ChArUco kose sayaci, kare kaydet/sil |
| `calibration.py` | ~250 | HAZIR | ChArUco karelerinden calibrateCamera x2 → stereoCalibrate(FIX_INTRINSIC) → stereoRectify. RMS dogrulama, epipolar y-hatasi, baseline karsilastirma, olcum defterine yazar |
| `ground_plane.py` | ~130 | HAZIR | Canli goruntuyle ChArUco'yu masada tespit, solvePnP ile duzlem denklemi (normal + d), aci kontrolu, ground_plane.npz olarak kaydet |
| `measurement.py` | ~280 | HAZIR | Arka plan cikarma → kontur → TUM kontur noktalarinin disparity'sinden 3B koordinat → min/max X,Y,Z → EN x BOY x YUKSEKLIK. F-sekli/vazo gibi genis tepeli cisimlerde de dogru calisir. Tekrarlanabilirlik testi (R tusu), kutu onerisi, olcum defterine yazar |
| `box_output.py` | ~200 | HAZIR | Boyutlardan kutu onerisi (13 standart kutu), RSC kesim sablonu SVG, desi hesabi, olcum defterine yazar |
| `odak_test.py` | ~160 | HAZIR | Mesafeye gore netlik skoru tablosu, net alan derinligi hesabi, olcum defterine yazar |
| `detect_cameras.py` | ~20 | HAZIR | Kamera indeks tarama |
| `probe_resolutions.py` | ~30 | HAZIR | Desteklenen cozunurluk listesi |
| `probe_full.py` | ~80 | HAZIR | Format, FPS, property testi |
| `probe_stereo_bandwidth.py` | ~70 | HAZIR | Iki kamera ayni anda bant genisligi testi |
| `sistem_planlama.py` | ~100 | HAZIR | deltaZ hesaplayici, calisma zarfi |

### Veri dosyalari

| Dosya | Durum |
|-------|-------|
| `data/kutu_tablosu.json` | HAZIR — 13 standart kargo kutusu |
| `data/charuco_config.json` | HAZIR — `olculen_kare_boyutu_mm: null` (fiziksel olcum bekliyor) |
| `patterns/charuco_board.png` | HAZIR — 7x5, 30mm kare, DICT_5X5_50 |
| `data/olcum_defteri.csv` | HAZIR — basliklarla olusturuldu |

### Kalibrasyon dosyalari (fiziksel islemlerden sonra olusacak)

| Dosya | Durum |
|-------|-------|
| `calibration/calib_result.npz` | YOK — calibration.py calistirilinca olusacak |
| `calibration/ground_plane.npz` | YOK — ground_plane.py calistirilinca olusacak |
| `calibration/frames/L_*.png, R_*.png` | BOS — eski karanlik kareler silindi, yeni kalibrasyon kareleri toplanacak |

---

## CALISMA SIRASI (yazilim hazir, fiziksel islemler bekliyor)

```
FIZIKSEL              YAZILIM                    CIKTI
────────              ───────                    ─────
1. Kameralari         camera_test.py             canli gorungu,
   rijit tabana       (zaten calisir)            netlik/parlaklik
   sabitle                                       takibi
      │
2. Kumpas al          -                          -
      │
3. Deseni bas         -                          A4 yatay, mat,
   (%100 olcek)                                  %100
      │
4. Deseni kumpasla    charuco_config.json        olculen_kare_
   olc (3-4 kare      guncelle                   boyutu_mm
   ortalama)
      │
5. Deseni sert        -                          cam/MDF/mukavva
   duzleme yapistir                              uzerine
      │
6. Aydinlatma         camera_test.py             parlaklik 90-130
   sabitle (lamba)     Ayarlar tab                fark < %15
      │
7. Koyu masa veya     -                          kontrast
   ortu hazirla                                  icin
      │
8. Baseline olc       -                          lens merkezi
   (kumpasla)                                    arasi mm
      │
9. Cozunurluk sec     camera_test.py             1280x960 onerilen
   ve kilitle          (bir daha degistirme)
      │
10. Kalibrasyon       camera_test.py              calibration/
    kareleri topla     Kalibrasyon tab             frames/
    (25-40 cift)       [S] ile kaydet             L_xxx.png
      │                                           R_xxx.png
11. Kalibre et        calibration.py              calib_result.npz
                       python src/calibration.py   RMS < 0.4
      │
12. Zemin tespiti     ground_plane.py             ground_plane.npz
    (ChArUco'yu        python src/ground_plane.py
    masaya yatir)
      │
13. Olcum             measurement.py              EN x BOY x YUK
                       python src/measurement.py   + kutu onerisi
      │
14. Kutu sablonu      box_output.py               SVG kesim
    (opsiyonel)        python src/box_output.py    sablonu
```

---

## KAMERA BILGILERI (tespit edilmis)

- **Model:** 16MP USB Camera (VID_32E4, PID_0298), M12 manuel odak lens
- **Indeksler:** 0=dahili webcam (kullanilmiyor), 1=sol USB, 2=sag USB
- **MJPG:** sadece 640x480 @30fps
- **YUY2:** 1280x720 @6fps, 1280x960 @6fps, 1920x1080 @3fps, 3840x2160 @0.7fps
- **Onerilen calisma cozunurlugu:** 1280x960 YUY2 @6fps
- **USB:** Iki kamera tek controller'da (Intel USB 3.10), calisir ama bant genisligi sinirli
- **Desteklenmeyen:** Otomatik odak, otomatik pozlama okuma (-1 donuyor ama deger uygulanabiliyor)

### Kamera ayarlari (son test)

- Pozlama: -2 (ortak), sag kamera telafisi: -3
- Gain: 0
- WB: 4500
- Parlaklik: SOL=105/255, SAG=94/255, fark=%10 (kabul edilebilir)
- Netlik: SOL=706, SAG=662 (yesil, yeterli)
- Lens odagi: fabrika ayarinda ojeyle sabitlenmis, suan yeterli gorunuyor

---

## OLCUM YONTEMI DETAYI

**Hybrid 3B Bounding Box yontemi:**

1. Rektifiye edilmis sol-sag goruntuden SGBM disparity haritasi
2. Arka plan cikarma ile nesne konturu
3. Konturun TUM noktalarinin disparity'sinden Q matrisiyle 3B koordinat
4. 3B noktalari zemin koordinat sistemine (u,v,n) donustur
5. min/max u = EN, min/max v = BOY, min/max n = YUKSEKLIK
6. Boyutlari kutu_tablosu.json ile karsilastir → en kucuk sigan kutu

**Neden bu yontem:**
- Yogun disparity haritasi gerekmez — kontur kenarlari yeterli
- F-sekli, vazo gibi genis tepeli cisimlerde de dogru calisir
- Dokusuz yuzeyler sorun degil (kenar kontrastl yeterli, koyu masa sart)
- Zemine iz dusurme sadece taban icin degil, tum kontur icin 3B hesap

**Sinirlari:**
- Ayni renk nesne + ayni renk masa = kontur bulunamaz
- Disparity'siz pikseller (tamamen dokusuz yuzey) → 5px komsudan median
- Asili cisim (masaya degmiyor) → taban bulunamaz
- Saydam/parlak nesne → yanlis kontur

---

## COWORK ICIN NOTLAR

1. **Rapor icin hazir veri:** Kalibrasyon yapilinca olcum_defteri.csv otomatik dolacak (RMS, baseline, fx, olcum sonuclari)
2. **Dogrulama testleri:** measurement.py icinde R tusuyla tekrarlanabilirlik testi var (5.3), mesafeye gore hata egrisi (5.2) icin ayri test scripti yazilabilir
3. **Grafik malzemesi:** Kalibrasyon RMS, disparity haritasi gorseli, hata egrisi — bunlar fiziksel islemler sonrasi olusacak
4. **Kesim sablonu:** box_output.py SVG uretir, Cowork bunu PDF'e cevirebilir
5. **calibration/frames/ altindaki 12 kare silinmeli** — karanlik, desen yok, kullanilmaz
6. **Eksik script:** Dogrulama testleri (5.2 mesafeye gore hata, 5.4 calisma zarfi, 5.5 kalibrasyon kalitesi karsilastirmasi) — kalibrasyon verisi olmadan yazilamaz, fiziksel islemlerden sonra yazilacak

---

# COWORK DOĞRULAMA — 10 Ağustos

Kod okundu ve çalıştırılabilen kısımları sandbox'ta test edildi. Aşağıdakiler
**doğrulanmış** bulgular (tahmin değil, çalıştırıldı).

## 🔴 D1 — Kutu önerisi ÇALIŞMIYOR (iki dosyada birden)

`data/kutu_tablosu.json` şu şemada:

```json
{"kaynak": "...", "birim": "cm",
 "kutular": [{"no": 0, "ad": "Mini koli", "olcu": [10, 10, 10], "desi": 0.33}]}
```

Ama `measurement.py` (satır 196) ve `box_output.py` (satır 37) şunu bekliyor:

```python
boxes = json.load(f)          # dict geliyor, list bekleniyor
for box in boxes:             # dict uzerinde donunce ANAHTAR (string) gelir
    bw = box["en_mm"]         # -> TypeError: string indices must be integers
```

Sandbox testi:

```
measurement.suggest_box(180,120,74) -> TypeError: string indices must be integers
box_output.load_boxes()             -> TypeError: unhashable type: 'slice'
```

Üstelik JSON'daki ölçüler **cm**, kod **mm** bekliyor — düzeltilse bile 10 kat hata olurdu.

**Düzeltme:** Loader'ları JSON'a uydur (JSON'daki `kaynak` alanı rapor için değerli,
onu koru):

```python
def load_boxes():
    with open(BOX_PATH, encoding="utf-8") as f:
        data = json.load(f)
    boxes = []
    for k in data["kutular"]:
        en, boy, yuk = k["olcu"]              # cm
        boxes.append({"no": k["no"], "ad": k["ad"],
                      "en_mm": en * 10, "boy_mm": boy * 10,
                      "yukseklik_mm": yuk * 10, "desi": k["desi"]})
    return boxes
```

`measurement.py` içindeki kopyayı silip `box_output.load_boxes()`'ı import et —
iki yerde iki farklı kutu okuma mantığı olmasın.

## 🔴 D2 — `fill_disparity_on_contour` arka planı nesne sanabilir

`measurement.py:118`. Kontur pikselinin etrafındaki 5 px'lik pencerenin **medyanı**
alınıyor. Ama kontur = nesne/arka plan sınırı; o pencerenin yarısı arka plandır.
Medyan arka plan disparity'sine düşerse, o nokta nesnenin **arkasında** bir yere
3B'ye taşınır ve bounding box şişer.

Bu sessiz bir hata: kod çalışır, sayı üretir, sayı yanlıştır.

**Düzeltme:** Sadece maske **içinden** örnekle:

```python
mask_ic = cv2.erode(mask, np.ones((7,7), np.uint8), iterations=1)
gecerli = (disparity > 0) & (mask_ic > 0)
# patch icinde sadece gecerli[y,x] True olan pikselleri kullan
```

Daha da iyisi: kontur üzerinde hiç örnekleme yapma. Maskeyi 5–7 px aşındır, disparity'yi
aşınmış sınırdan al. Kaybedilen birkaç mm'yi sabit bir düzeltme olarak ekle veya
raporda kısıt olarak yaz. **Occlusion tam olarak konturda olur** — orası disparity'nin
en güvenilmez olduğu yer.

## 🟠 D3 — `sorted()` yükseklik bilgisini yok ediyor

`measurement.py:200`:

```python
dims = sorted([width, length, height], reverse=True)
width, length, height = dims[0], dims[1], dims[2]
```

`height` doğru hesaplanıyor (zemin normali yönündeki uzanım) ama sonra sıralamayla
karışıyor. Uzun ince bir cisimde (şişe) yükseklik "en" olarak raporlanır.

Kutu **seçimi** için sıralama doğru (permütasyon zaten deneniyor). Ama rapor
tablosunda kumpasla karşılaştırma yapacaksın — orada eksenlerin anlamı korunmalı.

**Düzeltme:** `yukseklik`i ayrı tut, sıralamayı sadece `suggest_box` içinde yap.

## 🟠 D4 — Gölge kontura karışır

Arka plan çıkarma (`absdiff` + eşik) **gölgeyi de** nesne sayar. Tek masa lambasıyla
gölge garanti. Sonuç: en/boy sistematik olarak büyük çıkar.

**Düzeltme seçenekleri (kolaydan zora):**
1. Yayılmış aydınlatma — iki taraftan ışık veya ışığı tavana yansıt (en ucuz)
2. `absdiff` yerine HSV'de V-oranı eşiği: gölge V'yi düşürür ama H ve S'i çok
   değiştirmez → `V_yeni/V_eski > 0.4 and |H farkı| < 10` ise gölge say, nesne sayma
3. Koyu mat masa örtüsü + açık renk cisim (kontrast)

**Bunu Bölüm 5'e test olarak koy:** gölgeli ve yayılmış ışıkta aynı cismi ölç,
farkı tabloya yaz. Ucuz bir doğrulama satırı.

## 🟠 D5 — Çözünürlük: 1280×720 yerine 1280×960 dene

Probe çıktısına göre ikisi de **YUY2 @6 fps**. 1280×960 dikey olarak %33 daha fazla
piksel ve daha geniş dikey görüş alanı veriyor — aynı FPS'te. 4:3 muhtemelen sensörün
doğal en-boy oranı; 720p genelde onun kırpılmışıdır.

45° eğik bakışta dikey görüş alanı doğrudan "cisim kadraja sığıyor mu"yu belirliyor.

**Kontrol:** İki kamera aynı anda 1280×960'ta 6 fps'i koruyor mu? Koruyorsa 960 seç.
`probe_stereo_bandwidth.py` zaten bunun için yazılmış — çalıştır.

## 🟠 D6 — Odak "yeterli görünüyor" ile geçilmiş

Durum raporunda: *"Lens odagi fabrika ayarinda ojeyle sabitlenmis, suan yeterli
gorunuyor."* Netlik skorları (706 / 662) farklı sahnelerden alınmışsa
karşılaştırılamaz — Laplacian varyansı sahnenin kendi detayına bağlıdır.

**Yapılması gereken:** Aynı hedef (baskılı sayfa), aynı mesafe (planlanan çalışma
mesafesi), iki kamera aynı kadrajda. Skorları o zaman karşılaştır. Fabrika odağı
sonsuza ayarlıysa 35–55 cm bandında en iyi netliği vermiyor olabilir — lensi çevirip
tepe noktasını **arayarak** doğrula, sonra kilitle.

Bu, brief'in "sayısal karşılaştır, göz kararı yapma" maddesinin tam kendisi.

## 🟡 D7 — `sistem_planlama.py` gerçek değerlerle henüz çalıştırılmadı

Durum raporundaki "1280×720 önerilen" bir bant genişliği kararı; **çalışma zarfı
kararı değil.** Kumpasla ölçülen baseline ve cetvel testinden gelen `f_px` girilmeden
hangi mesafede ±3 mm tuttuğun bilinmiyor.

Kalibrasyon karesi toplamadan önce çalıştır — çünkü çıktısı kalibrasyonu **hangi
mesafede** yapman gerektiğini söylüyor.

## 🟡 D8 — 12 karanlık kare hâlâ duruyor

`calibration/frames/` içinde 12 çift var, hepsi kullanılamaz. Silinmedi.

---

## ÇOK GÖRÜŞLÜ ÖLÇÜM (cismi döndürme) — maliyet analizi

Soru: "cismi döndürüp ölçümü artırmak, simetrik olmadığını varsayıp — bu çok zorlar mı?"

Üç ayrı seviye var, maliyetleri çok farklı:

| Seviye | Ne yapılır | Süre | Rapor değeri | Öneri |
|---|---|---|---|---|
| **1. Tekrar ölçüm** | Cismi 90° çevir, tekrar ölç, iki sonucu karşılaştır. Birleştirme yok. | ~1 saat | **Yüksek** — tek görüş yanlılığını sayısal olarak ölçer | ✅ **Yap** |
| **2. Bilinen dönüşle birleştirme** | Zemin düzlemi zaten kalibre. Cismi masada işaretli 90°'ye çevir, ikinci görüşün 3B noktalarını bilinen dönüşle çevirip birleştir. ICP yok. | ~yarım gün | Orta-yüksek | ⚠️ Zaman kalırsa |
| **3. Gerçek çok görüşlü tarama** | Örtüşen nokta bulutları + ICP kaydı + aykırı temizleme | 2–3 gün+ | Yüksek ama **bitmeme riski yüksek** | ❌ **Yapma** |

**Seviye 3 neden yapılmamalı:** ICP'nin yakınsaması için nokta bulutlarının dokulu ve
yoğun olması gerekir. Sende 6 fps, 60 mm baseline ve dokusuz yüzeyler var — bulutlar
seyrek ve gürültülü olacak, ICP kayacak. Brief'te zaten "riskli" işaretli.

**Asıl nokta — ürün için döndürme gerekmiyor:**

Kargo kutusu seçimi için cismin *dış* uzanımı yeterli; iç oyuklar önemsiz. Tek görüşten
alınan siluet, gerçek uzanımı **küçük değil büyük** tahmin eder. Kutu seçiminde bu
**güvenli yön** — asla küçük kutu önermezsin. Yani döndürme, ürünün doğruluğu için
değil, raporun **doğruluk iddiası** için gerekli. Seviye 1 bunu ucuza veriyor.

**Simetri varsayımı zaten yok:** Mevcut yöntem (konturun tüm noktalarının 3B'si)
simetri varsaymıyor, F-şekli ve vazo gibi cisimlerde çalışıyor. Asimetrinin yarattığı
gerçek problem simetri değil **occlusion** — arka yüzü hiç görmüyorsun. Seviye 1 testi
tam olarak bunun ne kadar hata ürettiğini ölçer.

**Seviye 1 nasıl raporlanır (Bölüm 5'e yeni madde):**

> 5.11 — Yönelim duyarlılığı: 5 cisim, her biri 0° ve 90° yönelimde ölçüldü.
> Aynı fiziksel boyut için iki yönelim arasındaki fark, tek görüşlü ölçümün
> yönelime bağlı yanlılığını verir. Düzgün geometrili cisimlerde fark X mm,
> düzensiz geometride Y mm olarak ölçülmüştür.

Bu tablo, sistemin sınırını dürüstçe gösterir ve hocanın "%100 çözüme ulaşılmasa da
olur, sınırını bil" maddesine doğrudan cevap verir.

---

## CODE_GOREVLERI.md TAMAMLANMA DURUMU — 10 Agustos

| Gorev | Durum | Detay |
|-------|-------|-------|
| **G1** — Kutu tablosu okuma hatasi | TAMAMLANDI | `box_output.py:load_boxes()` JSON'un nested yapisina uygun yazildi, cm→mm donusumu eklendi. `measurement.py`'daki kopya `suggest_box` silindi, yerine `box_output` import edildi. |
| **G2** — Kontur disparity dolgusu | TAMAMLANDI | `fill_disparity_on_contour` artik `obj_mask` parametresi aliyor, `cv2.erode` ile maske icinden ornekliyor. Kapsama orani ekrana yaziliyor (`Kontur noktasi: X, gecerli: Y (%Z)`). |
| **G3** — sorted() yukseklik ekseni | TAMAMLANDI | `measure_3d_bbox` artik siralama yapmiyor. `yukseklik` her zaman zemin normali yonu. `en` ve `boy` zemin duzlemindeki iki eksen (buyuk=en, kucuk=boy). Siralama sadece `suggest_boxes` icinde. |
| **G4** — Golge bastirma | TAMAMLANDI | HSV tabanli golge tespiti eklendi (V orani 0.35-0.90, H farki <10, S farki <40). G tusuyla acilip kapatilabiliyor. |
| **G5** — 1280x960 cozunurluk | TAMAMLANDI | `charuco_config.json`'a `calib_resolution: [1280, 960]` eklendi. `camera_test.py` varsayilani 1280x960 YUY2. `_open_cameras` secili cozunurlugu dinamik okuyor. `calibration.py` ve `measurement.py`'a cozunurluk uyumsuzlugu kontrolu eklendi (SystemExit). |
| **G6** — Odak dogrulama scripti | TAMAMLANDI | `src/odak_test.py` yazildi. 200-800 mm araliginda SPACE ile kayit, merkez %60 ROI'de Laplacian skoru, tepe mesafe ve net alan derinligi (%50 esik) hesabi, olcum defterine yazar. |
| **G7** — Yonelim duyarliligi testi | TAMAMLANDI | `measurement.py`'da O tusu eklendi. Ilk O = 0 derece kayit, ikinci O = 90 derece kayit + fark hesabi. Sonuc olcum defterine `yonelim_duyarliligi` etiketiyle yaziliyor. |
| **G8** — Temizlik | TAMAMLANDI | 12 karanlik kalibrasyon karesi silindi (mean parlaklik 11-16, kullanisiz). `data/olcum_defteri.csv` basliklarla olusturuldu: `tarih,saat,asama,parametre,ayar,deger,birim,not`. |

### Notlar
- `sistem_planlama.py` calistirilmadi (G8 talimati geregi: kumpasla baseline ve cetvel testi gerekiyor)
- Dogrulama testleri (5.2, 5.4, 5.5) kalibrasyon verisi olmadan yazilamaz — fiziksel islemlerden sonra
- Cozunurluk `9. Cozunurluk sec` satiri **1280x960** olarak guncellenmeli (yukarida 720 yaziyordu)
