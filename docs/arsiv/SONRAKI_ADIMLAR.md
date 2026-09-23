# Durum Değerlendirmesi ve Sonraki Adımlar

**Tarih:** 9 Ağustos 2026
**Değerlendiren:** Cowork (kayıtlı kareler ve kaynak kod incelenerek)

---

## 0. ÖZET

Aşama 0 (kamera test aracı) beklenenden iyi durumda — GUI, çözünürlük seçici, ayar
kaydırıcıları, ChArUco köşe sayacı ve kare kabul kriteri hazır. Ancak **kalibrasyon
zinciri henüz başlamadı** ve `calibration/frames/` altındaki 12 kare çifti kullanılamaz.

En kritik iki tespit:

1. **Kayıtlı 12 kare çiftinde ChArUco deseni yok ve kareler neredeyse siyah**
   (ortalama parlaklık 11–15 / 255). 24 görüntünün hiçbirinde köşe tespit edilemedi.
2. **Ölçüm defteri (`data/olcum_defteri.csv`) hiç oluşturulmadı.** Brief ve CLAUDE.md
   "ilk günden tutulacak" diyor; şu an kayıp veri birikiyor.

---

## 1. YAPILMIŞ OLANLAR ✅

| Dosya | Durum | Not |
|---|---|---|
| `src/camera_test.py` | 462 satır, çalışır durumda | GUI, çift kamera, Laplacian, FPS, pozlama/gain/WB kaydırıcıları, çözünürlük seçici, ChArUco köşe sayacı, %50 köşe kabul kriteri, kare kaydet/sil |
| `src/detect_cameras.py` | Hazır | İndeks tarama — briefte yoktu, iyi ek |
| `src/probe_resolutions.py` | Hazır | Desteklenen çözünürlük tespiti — iyi ek |
| `patterns/generate_charuco.py` | Hazır | Desen üretici + basım uyarısı doğru yazılmış |
| `patterns/charuco_board.png` | Üretildi | 1240×885 px, 150 DPI |
| `data/charuco_config.json` | Üretildi | `olculen_kare_boyutu_mm: null` — **doldurulmayı bekliyor** |
| `data/kutu_tablosu.json` | Hazır | 13 standart koli, desi değerleriyle |
| `CLAUDE.md` | Hazır | Klasör yapısı ve kurallar tanımlı |
| Klasör iskeleti | Hazır | `calibration/`, `data/`, `output/`, `docs/`, `patterns/` |

---

## 2. BULUNAN SORUNLAR

### 🔴 S1 — Kayıtlı 12 kare çifti kullanılamaz, silinmeli

Analiz sonucu:

```
Toplam çift: 12
Her iki kamerada ≥6 ChArUco köşesi olan: 0
Ortalama parlaklık: L=11–16 / 255, R=11–16 / 255
```

Kareler masanın/monitörün karanlık görüntüleri; desen sahnede yok. Bunlar kalibrasyona
girerse `calibrateCamera()` ya hata verir ya da sessizce bozuk sonuç üretir.

**Aksiyon:** `calibration/frames/` içeriğini tamamen sil, sayaç sıfırlansın.

### 🔴 S2 — Ciddi düşük pozlama

Ortalama parlaklık 11–15/255. Kullanılabilir bir görüntü için ~90–130 bandı hedeflenmeli.
Sebebi ya `exposure_var` varsayılanı (-6) çok düşük ya da oda karanlık ya da
`CAP_PROP_EXPOSURE` sürücüde hiç uygulanmıyor.

**Aksiyon:**
- Ortam ışığını sabitle (masa lambası, perde kapalı, gün ışığına bağımlı olma)
- Pozlamayı, ortalama parlaklık 90–130 bandına gelene kadar yükselt
- Aşağıdaki S3 göstergesini ekleyip değerin gerçekten uygulanıp uygulanmadığını gör

### 🔴 S3 — Ayar kilidi doğrulanmıyor

`_apply_settings()` beş `set()` çağrısı yapıyor ama hiçbirinin dönüş değerine bakmıyor.
Bazı UVC sürücüleri `set()` çağrısını sessizce yok sayar; kod "kilitledim" sanır,
kamera otomatik moda devam eder. Brief'in özellikle uyardığı tuzak bu.

**Aksiyon — `camera_test.py` içine ekle:**

```python
def _apply_and_verify(self, cap, prop, value, name):
    """Ayari uygula, geri okuyup dogrula. Tutmazsa uyari dondur."""
    cap.set(prop, value)
    actual = cap.get(prop)
    ok = abs(actual - value) < max(1.0, abs(value) * 0.05)
    return ok, actual
```

Panele "KİLİT DURUMU" bölümü ekle: her ayar için ✓ / ⚠ göster. Tutmayan ayar varsa
kırmızı uyarı — kalibrasyona başlamadan görmek gerekiyor.

### 🟠 S4 — İki kameranın parlaklık farkı ölçülmüyor

Aynı `set()` değerleri iki kameraya uygulanıyor ama **aynı değer aynı parlaklık demek
değil** — farklı sensör farklı tepki verir. Aradaki fark blok eşleştirmeyi doğrudan bozar.

**Aksiyon:** Panele her iki kamera için ortalama parlaklık (`gray.mean()`) ekle ve
%15'ten fazla fark varsa uyar. Bu aynı zamanda Bölüm 5.7 (pozlama duyarlılığı testi)
için gereken ölçümü ücretsiz üretir.

### 🟠 S5 — Çalışma çözünürlüğü seçilmedi, kareler 640×480

**Bu, kalibrasyondan önce kilitlenmesi gereken bir karar.** Sebebi:

- Intrinsics (K matrisi) **çözünürlüğe bağlıdır.** 640×480'de kalibre edip 1280×960'ta
  ölçersen her sonuç yanlış çıkar
- Disparity hassasiyeti çözünürlükle doğrudan artar → ölçüm doğruluğu artar
- Ama FPS düşer ve USB bant genişliği sınıra dayanır

**Aksiyon sırası:**
1. `probe_resolutions.py` çalıştır, iki kamerada da desteklenen çözünürlükleri gör
2. **İki kamerada ortak** olan en yüksek çözünürlüğü seç (≥10 FPS veriyorsa)
3. Seçilen değeri `charuco_config.json`'a `calib_resolution` alanı olarak yaz
4. `camera_test.py` varsayılanını bu değere çek
5. Kalibrasyon ve ölçüm **aynı çözünürlükte** yapılacak — koda bir kontrol koy

### 🟠 S6 — Desen A4'e dik basılmaz

Desen: 7×5 kare × 30 mm = **210 × 150 mm**, kenar payıyla **240 × 180 mm**.
A4 dikey 210 mm geniş → **sığmaz.** A4 yatay 297 × 210 mm → sığar.

**Aksiyon:** Yazıcıda **yatay (landscape)** ve **%100 ölçek / ölçeklendirme yok** seç.
A3 erişimin varsa daha büyük desen kalibrasyon doğruluğunu artırır.

### 🟠 S7 — Ölçülen kare boyutu sessizce nominale düşüyor

`camera_test.py` satır 57:

```python
sq = cfg.get("olculen_kare_boyutu_mm") or cfg["square_length_mm"]
```

`olculen_kare_boyutu_mm` null olduğunda kod uyarı vermeden 30 mm kullanıyor. Config'in
kendi notu "None bırakılırsa kalibrasyon hata verir" diyor ama kod hata vermiyor.
Bu, brief'te "fark etmesi çok zor" diye uyarılan sistematik hatanın tam kaynağı.

**Aksiyon:** `calibration.py` yazılırken bu değer null ise **çalışmayı durdur**:

```python
if cfg.get("olculen_kare_boyutu_mm") is None:
    raise SystemExit(
        "HATA: Basili desen kumpasla olculmemis. "
        "charuco_config.json -> olculen_kare_boyutu_mm doldurulmali."
    )
```

Test aracında nominal değerle çalışmak sorun değil (sadece köşe sayar), ama kalibrasyonda
kesinlikle engellenmeli.

### 🟡 S8 — İki kamera ardışık okunuyor, senkron kayması var

```python
ret_l, fl = self.cap_l.read()    # once sol
ret_r, fr = self.cap_r.read()    # sonra sag  → aralarinda 10-30 ms olabilir
```

Kalibrasyon karesi çekerken tahtayı elde tutuyorsan bu kayma köşe konumlarını kaydırır.

**Aksiyon — ucuz ve etkili düzeltme:**

```python
self.cap_l.grab()                 # ikisini de once tetikle
self.cap_r.grab()
ret_l, fl = self.cap_l.retrieve() # sonra coz
ret_r, fr = self.cap_r.retrieve()
```

Kaymayı yarıya indirir. Donanım senkronu yerine geçmez ama statik ölçüm için yeterli.
Bu düzeltmeyi raporda kısıt maddesi 6'nın altında "kısmi çözüm" olarak yazabilirsin.

### 🟡 S9 — Ölçüm defteri yok

`data/olcum_defteri.csv` hiç oluşturulmamış. CLAUDE.md'de zorunlu, Ek-3'te
"Problem tanımlama ve modelleme" maddesine giren davranış bu.

**Aksiyon:** `_save_frame()` her kare çiftinde CSV'ye bir satır eklesin:

```
tarih,saat,asama,kare_no,cozunurluk,pozlama,gain,wb,parlaklik_L,parlaklik_R,
netlik_L,netlik_R,kose_L,kose_R,oda_sicakligi,not
```

Oda sıcaklığını elle sonradan doldurabilirsin ama sütun baştan olsun. Bu dosya sonradan
üretilemez — geçmişe dönük veri yok.

### 🟡 S10 — Lens distorsiyonu belirgin

Kayıtlı karelerde masa kenarı gözle görülür şekilde kavisli — geniş açı M12 lens,
kuvvetli fıçı (barrel) distorsiyonu var. Sorun değil, kalibrasyon bunu düzeltir,
**ama şart var:** distorsiyon katsayıları ancak görüntü kenarlarında köşe gördüğün
sürece doğru çözülür.

**Aksiyon:** Kalibrasyon karelerinin en az üçte birinde desen görüntünün **kenarlarında
ve köşelerinde** olsun. Sadece ortada tutarsan RMS düşük çıkar ama distorsiyon modeli
yanlış olur — ve bunu ölçüm hatası olarak sonradan görürsün.

---

## 3. AŞAMA Ö — ÖN ADIMLAR (kalibrasyondan ÖNCE, sırayla)

> **Bu bölüm atlandı ve sıra ters işletildi.** Desen basıldı ama hangi mesafede
> kullanılacağı bilinmiyordu; kareler toplandı ama odak, çözünürlük ve pozlama
> kararları verilmemişti. Aşağıdaki sıra bağlayıcıdır — her adım bir sonrakinin
> girdisini üretir.

### Ö1 — Mekanik montaj ve rijitlik 🔴 EN KRİTİK

Fotoğrafta **iki kamera ayrı ayrı kutularda.** Bu, tek parça gövdeden farklı bir
durum ve projenin en büyük riski:

> Stereo kalibrasyon, iki kamera arasındaki **R (dönme) ve T (öteleme)** ilişkisini
> çözer. Bu ilişki değişirse kalibrasyon çöp olur. İki ayrı kutu, ortak ve rijit bir
> tabana cıvatalanmadıysa baseline her dokunuşta değişir.

Yapılacaklar:

- İki kutuyu **ortak, bükülmeyen bir tabana** sabitle (fotoğraftaki "f" braket veya
  düz bir plaka/profil). Kutular arasında hiçbir esneme kalmamalı
- Tüm vidaları sık, vida başlarına **oje/işaret** koy → oynadığını gözle görürsün
- **Kablo gerilimi:** USB kablosu modülü çekiyorsa kamera milimetrik kayar.
  Kabloyu gövdeye kelepçele (strain relief), yük modüle binmesin
- Kutuları taban üzerinde işaretle; sökmek zorunda kalırsan aynı yere geri koy

**Rijitlik testi (rapora girecek):** Kalibrasyondan sonra gövdeye hafifçe bastır,
kaldır, tekrar epipolar hatayı ölç. Değiştiyse montaj yetersiz demektir. Bu testi
Bölüm 5.8 olarak raporla.

### Ö2 — Vinyetleme kontrolü (deliğin görüş alanını kesip kesmediği)

Fotoğraftaki ön plakada yuvarlak bir delik var, lens onun arkasında oturuyor.
Geniş açı M12 lensle bu, **mekanik vinyetlemeye** yol açabilir: görüntünün köşeleri
kararır veya görüş alanı kırpılır.

Bu neden önemli: distorsiyon katsayıları (k1, k2) ancak **görüntü kenarlarında**
veri varsa doğru çözülür. Köşeler karanlıksa oradan köşe tespit edemezsin ve
distorsiyon modeli yanlış çıkar — ölçüm hatası olarak geri döner.

**Test:** Kamerayı düzgün aydınlatılmış beyaz bir duvara/kağıda çevir, kare çek,
köşe parlaklığını merkez parlaklığıyla karşılaştır:

```python
h, w = gray.shape
merkez = gray[h//3:2*h//3, w//3:2*w//3].mean()
kose   = np.mean([gray[:h//6,:w//6].mean(), gray[:h//6,-w//6:].mean(),
                  gray[-h//6:,:w//6].mean(), gray[-h//6:,-w//6:].mean()])
print(f"Kose/merkez orani: {kose/merkez:.2f}")   # 0.6'nin altiysa sorun var
```

Sorun varsa: deliği büyüt, lensi öne al veya ön plakayı çıkar. **Kalibrasyondan
önce çöz** — sonra çözersen kalibrasyon geçersizleşir.

### Ö3 — Hizalama: roll, yükseklik, tilt

İki kutu birbirine göre dönmüş olmamalı:

- **Roll (optik eksen etrafında dönme):** İkisi de aynı düzlemde durmalı.
  Test: sahnede yatay bir çizgi (masa kenarı, cetvel) her iki görüntüde de yatay
  görünmeli. Rektifikasyon roll'ü matematiksel olarak düzeltir ama düzeltirken
  görüntüyü döndürür ve **ortak alanı daraltır** — mekanik olarak düzeltmek bedavaya gelir
- **Yükseklik:** İki lens merkezi aynı yükseklikte olmalı
- **Tilt:** İkisi de aynı açıyla baksın. Hafif içe yakınsama (converge) kabul edilebilir
  ama simetrik olmalı

Kaba ama etkili kontrol: iki görüntüyü üst üste bindir (`cv2.addWeighted`), uzaktaki
bir cismin dikey konumu ikisinde de aynı olmalı.

### Ö4 — Çalışma çözünürlüğünü seç 🔴 KALİBRASYONDAN ÖNCE KİLİTLE

**Neden kritik:** K matrisi piksel cinsindendir. 640×480'de kalibre edip 1280×960'ta
ölçersen `fx` iki katı yanlış olur ve her ölçüm bozulur. Bir kez seç, bir daha değiştirme.

1. `probe_resolutions.py` çalıştır, **iki kamerada da** desteklenen listeyi al
2. Ortak olanlardan ≥10 FPS veren en yükseğini aday seç
3. **Gerçek mi, interpolasyon mu testi:** Birçok ucuz USB modül, sensörün fiziksel
   çözünürlüğünün üstündeki modları yazılımla büyüterek verir — dosya büyür, detay artmaz.
   Test: sabit bir metin sayfasını her çözünürlükte çek, en küçük okunabilir yazı
   boyutunu karşılaştır. 1280→1920 geçişinde gerçek detay artmıyorsa 1280 seç,
   fazlası sadece FPS ve bant genişliği yer
4. Seçilen değeri `charuco_config.json`'a yaz ve `camera_test.py` varsayılanını değiştir
5. `calibration.py`'a kontrol koy: kalibrasyon çözünürlüğü ile ölçüm çözünürlüğü
   farklıysa çalışmayı durdur

> Genel eğilim: **daha yüksek çözünürlük = daha iyi doğruluk.** `f_px` büyür,
> `ΔZ = Z²·Δd/(f·B)` küçülür. USB bant genişliği ve FPS izin verdiği sürece yükselt.

### Ö5 — Pozlama / gain / WB kilidi ve parlaklık eşitleme

S2, S3, S4'teki düzeltmeler. Sıra:

1. Ortam ışığını sabitle (perde kapalı, masa lambası, gün ışığına bağımlı olma)
2. Pozlamayı ortalama parlaklık **90–130** bandına getir
3. Her `set()` sonrası `get()` ile doğrula, panelde ✓/⚠ göster
4. İki kameranın ortalama parlaklığı **%15'ten fazla** farklıysa, farkı kapatana kadar
   birinin pozlamasını ayrı ayarla (aynı değer aynı parlaklık demek değil)
5. Nihai değerleri ölçüm defterine yaz — kalibrasyon bu ayarlarla yapılacak

### Ö6 — Odak eşitleme

**Kalibrasyondan önce, çözünürlük seçildikten sonra.** Sıra önemli: yüksek
çözünürlükte odak hatası daha görünür olur.

1. Dokulu bir hedefi (gazete, baskılı sayfa) planlanan çalışma mesafesine koy
2. Her kamerayı **tek tek** çevirerek Laplacian skorunu maksimuma çıkar
3. İki kameranın tepe skorları birbirine yakın olmalı. Biri belirgin düşükse:
   lens kirli, sensör eğik veya modüller farklı — kaydet, rapora kısıt olarak yaz
4. Hedefi 30→90 cm arasında gezdir, skorun eşiğin üstünde kaldığı aralığı not et
   → bu senin **net alan derinliğin**, çalışma zarfının bir sınırı
5. Odağı fiziksel kilitle (vida kilidi / bir damla oje). **Bundan sonra lense dokunma**

### Ö7 — Cetvel testi: odak uzaklığı ve görüş açısı

Kalibrasyon olmadan `f_px`'i kestirmenin pratik yolu — planlama için gerekli:

1. Bir metre/cetveli kameradan bilinen mesafeye (örn. 500 mm) **kameraya paralel** koy
2. Görüntünün sol kenarından sağ kenarına kaç mm göründüğünü oku
3. `f_px = görüntü_genişliği_px × mesafe_mm / görünen_mm`

Bu değeri Ö9'da kullanacaksın. Kalibrasyon bittiğinde K matrisindeki `fx` ile
karşılaştır — %10'dan fazla sapma varsa biri hatalı.

### Ö8 — Baseline ölçümü

İki lens merkezi arasını **kumpasla** ölç. Lens merkezini gözle kestirmek zor;
kutuların aynı referans kenarları arası + kutu içindeki lens offseti şeklinde hesapla.

Bu değer kalibrasyondan gelen **‖T‖** ile karşılaştırılacak. %5'ten fazla sapma
kalibrasyonda sorun demektir — bedava bir doğrulama satırı.

### Ö9 — Sistem planlama hesabı ⭐

`src/sistem_planlama.py` yazıldı. Ö4, Ö7, Ö8'den gelen ölçülen değerleri dosyanın
başındaki bölüme gir ve çalıştır:

```
python src/sistem_planlama.py
```

Çıktısı:
- Odak uzaklığı (px), yatay/dikey görüş açısı
- Mesafeye göre tablo: görüş genişliği, ortak alan oranı, `ΔZ`, desen doluluk oranı,
  marker piksel boyutu
- **Çalışma zarfı** — hangi mesafe aralığında hedef doğruluğu sağlıyorsun
- **Desen boyutu kararı** — mevcut 30 mm kare yeterli mi, değilse kaç mm olmalı
- **Kalibrasyon karelerini hangi mesafede toplaman gerektiği**

Örnek çıktı (1280×960, f=914 px, B=60 mm, Δd=0,5 px varsayımıyla):

```
Calisma araligi : 350 – 550 mm,  en kotu ±2,76 mm
Kalibrasyon mesafesi : 350 – 500 mm
UYARI: desen 550 mm'de goruntunun sadece %27'sini kapliyor (min %30 gerekli)
       %40 doluluk icin kare boyutu 44 mm olmali → 7 x 44 = 308 mm → A3 gerekli
```

> **Buradaki ders:** desen boyutu keyfi bir seçim değil, çalışma mesafesinin
> sonucudur. Mevcut 30 mm'lik desen çalışma aralığının üst ucunda yetersiz kalıyor.
> Gerçek sayılarını girdiğinde sonuç değişebilir — ama kararı **hesapla ver, tahminle değil.**
> Bu hesap raporun "Yöntem" bölümüne doğrudan girer.

### Ö10 — Desen basımı (boyut kararı Ö9'dan gelir)

- **Mat kağıt kullan.** Parlak/fotoğraf kağıdı ve laminasyon **YASAK** — parlama
  köşe tespitini bozar
- **%100 ölçek / gerçek boyut / ölçeklendirme yok** ile bas
- Genişlik 240 mm'yi geçiyorsa A4'e dikey sığmaz → yatay bas veya A3 al
- Sert plakaya (cam, mukavva, MDF) **tüm yüzeyden** yapıştır. Sadece köşelerden
  bantlama — kâğıt kıvrılırsa RMS düşük çıkar ama kalibrasyon yanlış olur
- **3–4 farklı kareyi kumpasla ölç, ortalamayı** `charuco_config.json` →
  `olculen_kare_boyutu_mm` alanına yaz

**Parlama (yansıma) sorunu — sorduğun konu:**

Desen eğildiğinde lamba ışığı doğrudan yansırsa o bölgedeki siyah kareler beyaz
görünür. İki farklı sonuç doğurur:

| Durum | Sonuç | Tehlike |
|---|---|---|
| Şiddetli parlama | Marker hiç bulunmaz, köşe sayısı düşer | **Zararsız** — kabul kriteri kareyi zaten eler |
| Hafif/kısmi parlama | Köşe bulunur ama konumu kayar | **Tehlikeli** — RMS'i sessizce bozar |

Önlem: ışığı **yayılmış** tut (lambayı tavana/duvara yansıt, deseni doğrudan
aydınlatma), mat kağıt kullan, desen eğimini parlamanın olmadığı açılarda seç.
Ekrandan (monitör) desen göstermeyi deneme — hem parlar, hem piksel ızgarası moiré yapar.

### Ö11 — Başlangıç ölçümleri (Bölüm 5.1)

Yukarıdaki tüm adımların sayısal sonuçlarını `data/olcum_defteri.csv`'ye yaz:
çözünürlük, pozlama/gain/WB, iki kameranın Laplacian tepe skoru, ortalama parlaklık,
köşe/merkez parlaklık oranı, ölçülen baseline, `f_px`, FOV, oda sıcaklığı.

Bu tablo raporda "önce" sütunu olacak; sonda aynısını doldurup karşılaştıracaksın.

### Ö12 — Ancak şimdi: kalibrasyon karesi toplama

`calibration/frames/*` silinmiş olmalı. Ö9'un söylediği mesafe aralığında,
25–40 çift, üçte biri kenar/köşede, farklı eğim açılarıyla.

---

## 4. YAPILACAKLAR — ÖNCELİK SIRASI

### Bugün

1. `calibration/frames/*` sil
2. Ö1 → Ö3: mekanik montaj, vinyetleme kontrolü, hizalama
3. `camera_test.py`'a ekle: ayar kilidi doğrulama (S3), parlaklık göstergesi (S4),
   `grab/retrieve` (S8), CSV kaydı (S9), köşe/merkez parlaklık oranı (Ö2)
4. Ö4 → Ö8: çözünürlük, pozlama, odak, cetvel testi, baseline

### Yarın

5. Ö9: `sistem_planlama.py`'ı gerçek değerlerle çalıştır → çalışma zarfı ve desen kararı
6. Ö10: deseni (gerekiyorsa yeni boyutta) bas, kumpasla ölç, config'e yaz
7. Ö11: başlangıç ölçümlerini deftere yaz
8. Ö12: kalibrasyon kareleri

### Sonra (kalibrasyon zinciri)

8. Odak eşitleme: Laplacian skorlarını iki kamerada yakınsat, odağı fiziksel kilitle
9. 25–40 kare çifti topla — üçte biri kenar/köşe, farklı eğim açılarıyla (S10)
10. `src/calibration.py` yaz:
    - Null kare boyutunda `SystemExit` (S7)
    - `calibrateCamera()` × 2 → `stereoCalibrate(CALIB_FIX_INTRINSIC)` → `stereoRectify()`
    - Çıktı: `calibration/calib_result.npz` (K, D, R, T, Q)
    - **‖T‖ ile kumpasla ölçtüğün baseline'ı karşılaştır** — %5'ten fazla sapma varsa uyar
    - RMS'i ekrana ve ölçüm defterine yaz, hedef < 0,4 px
    - Kötü kareleri eleyip tekrar çalıştırma seçeneği (5.5 için "kötü set" de saklanacak)
11. Rektifikasyon sağlaması: epipolar çizgi hatası ölç, yatay hizalamayı gözle doğrula
12. **Cetvel sağlaması:** bilinen 200 mm'lik mesafeyi ölç. Sistematik yüzde hatası varsa
    desen ölçüsünden gelir — buradan geri dön

### Sonra (ölçüm ve ürün)

13. `src/ground_plane.py` — ChArUco'yu zemine yatır, pose'undan düzlem çıkar,
    `calibration/ground_plane.npz` olarak kaydet (Brief Aşama D)
14. `src/measurement.py` — taban konturu + yükseklik (Brief Aşama F)
15. `src/box_output.py` — kutu önerisi + desi + kesim yönergesi (Brief Aşama G)
16. Bölüm 5 doğrulama testleri
17. Rapor (Cowork tarafında)

---

## 5. ÖĞRENİLMESİ GEREKENLER (sözlü sınav %40)

Kod çalışsa bile bunları anlatamıyorsan puan kaybı olur. Her biri bir-iki cümleyle
cevaplanabilmeli:

**Kamera modeli**
- K matrisindeki `fx, fy, cx, cy` ne anlama gelir, birimi nedir
- **Neden çözünürlüğe bağlıdır** — `fx` piksel cinsindendir, çözünürlük değişince değişir
- Distorsiyon katsayıları (k1, k2, p1, p2) neyi düzeltir; fıçı vs. yastık distorsiyonu

**Kalibrasyon**
- `calibrateCamera` neyi minimize eder → yeniden-projeksiyon hatası (reprojection error)
- **RMS düşük olması doğru olduğu anlamına gelmez.** Yanlış kare boyutu girersen RMS
  mükemmel çıkar ama tüm ölçümler aynı oranda yanlış olur. Bu ayrımı anlatabilmek,
  raporun en güçlü savunma noktası
- `CALIB_FIX_INTRINSIC` neden kullanılıyor → intrinsics tek tek daha güvenilir çözülür,
  stereo adımında sadece R ve T aranır

**Stereo geometri**
- Epipolar kısıt nedir, rektifikasyon ne işe yarar → arama 2B'den 1B'ye iner
- Q matrisi ne yapar → disparity + piksel koordinatını metrik 3B noktaya çevirir
- `Z = f·B / d` bağıntısı ve buradan `ΔZ ≈ Z²·Δd/(f·B)` türetimi.
  **Bu türetimi tahtada yapabilmelisin** — hata eğrisi grafiğinin dayanağı bu

**Ölçüm ve belirsizlik**
- Neden hata mesafenin karesiyle büyür
- Tekrarlanabilirlik (precision) ile doğruluk (accuracy) farkı — 5.3'te ikisini de ölçüyorsun
- Neden medyan kullanıyorsun, ortalama değil → aykırı eşleşmelere dayanıklılık

**Yöntem gerekçeleri (senin özgün katkın)**
- Neden yoğun disparity'ye güvenmiyorsun → dokusuzluk + occlusion
- Neden zemin düzlemini ChArUco'dan alıyorsun, RANSAC'tan değil → disparity'ye
  güvenmiyorsan düzlemi de disparity'den alma
- Neden tüm siluet değil taban konturu → eğik bakışta üst yüzey silüete karışır,
  sistematik büyütme yapar
- Neden pozlama/WB manuel kilitli → iki bağımsız UVC kamera farklı ayar seçer,
  parlaklık farkı eşleştirmeyi bozar

**Sistem sınırları**
- Çalışma zarfın nedir ve **neden** o aralık (yakında ortak görüş alanı, uzakta Z² hatası)
- Sistemin çalışmadığı durumlar (dokusuz/parlak yüzey, asılı cisim, tepeden bakış)

---

## 6. ATLANMASI RİSKLİ OLANLAR

Zaman daralırsa kesilebilecekler ile kesilemeyecekler:

| Kesilebilir | Kesilemez |
|---|---|
| DXF çıktısı (PDF yeter) | Ölçüm defteri |
| Yöntem karşılaştırması 3 varyant → 2 varyant | Mesafeye göre hata eğrisi (5.2) |
| Kesim yönergesinin şık görselleştirmesi | Tekrarlanabilirlik testi (5.3) |
| SQLite, YOLO, yapısal ışık (zaten "gelecek çalışmalar") | Kalibrasyon kalitesi karşılaştırması (5.5) |
| Kutu permütasyon optimizasyonu | Ana sonuç tablosu (5.9) |
| | Cetvel sağlaması (ölçek doğrulaması) |

Sağ sütun rapor puanının kaynağı. Sol sütun demoyu güzelleştirir ama not getirmez.
