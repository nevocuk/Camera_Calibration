# Stereo Kamera ile Boyutsal Ölçüm ve Kutu Önerme Sistemi
## Staj Projesi Brifi & Claude Code / Cowork Başlangıç Promptu

> **Bu doküman bir plan, şartname değil.** İçindeki teknik kararların çoğu masa başında
> alındı; donanım eline geldiğinde bazıları değişecek. Değiştir. Bir şey çalışmıyorsa
> veya daha iyi bir yol görüyorsan bu dosyaya sadık kalma — güncelle ve devam et.
>
> Kesin olan iki şey:
> 1. **Stereo kalibrasyon yapılacak ve sonuçları sayısal olarak doğrulanacak.**
> 2. **Sistem bir cismi ölçüp kullanıcıya somut bir kutu çıktısı verecek** —
>    hangi standart kutuya sığdığı ve/veya nasıl kesip katlaması gerektiği.
>
> Gerisi (ölçüm yöntemi detayı, arayüz, çıktı formatı) esnetilebilir.

---

## 0. BAĞLAM

ATÜ Bilgisayar Mühendisliği. zorunlu yaz stajı.
Şirket kodu ve verisi gizlilik anlaşması kapsamında — staj raporunda şirketin gerçek
pipeline'ından bahsedilemez. Bunun yerine aynı teknik yetkinliği gösteren, kendi
donanım ve veriyle kurulan bağımsız bir prototip geliştiriliyor.

**Bu yaklaşım bölüm tarafından onaylı:** Staj bilgilendirme sunumunun "Diğer durumlar"
bölümü, gizlilik sözleşmesi durumunda öğrencinin kendi verisiyle prototip oluşturmasını
ve ekran görüntüsü/videoyla desteklemesini açıkça öneriyor.

### Donanım (eldeki gerçek durum)

- İki adet USB kamera modülü (M12 lens, manuel odaklı) + USB kabloları
- **Kameralar için hazırlanmış, 3B basılmış yuvaları olan bir gövde mevcut.**
  İki modül bu gövdeye sabitlenecek, birbirine göre konumları sabit olacak.
- Python ortamı (Windows)

> ⚠️ **Kritik ön kontrol:** Eldeki iki modülün *aynı model olduğu varsayılmamalı.*
> Foto üzerinden kart boyutları ve lens çapları farklı görünüyor. Farklı sensör veya
> farklı odak uzaklığı, stereo çalışmayı engellemez (`stereoCalibrate` ayrı intrinsics
> kabul eder) ama rektifikasyon sonrası **ortak görüş alanını daraltır** ve eşleştirme
> kalitesini düşürür. İlk gün Aşama 0 aracıyla çözünürlük, görüş açısı ve netlik
> profillerini yan yana karşılaştır. Fark varsa gizleme — Bölüm 6'ya kısıt olarak yaz.

### Kapsam dışı

- **3B baskı yapılmayacak.** Gövde hazır. Ancak zorunlu hale gelirse (gövde yetersiz
  kalır, kamera oynarsa) küçük bir ara parça basılabilir — bu bir yedek plan, ana iş değil.
- Şirket verisi/kodu bu projeye hiç girmeyecek.

**Değerlendirme:** Rapor %60 + sözlü sınav %40, geçme notu 70.
Ek-4 şablonu MS Word'de doldurulacak.

**Dil:** Açıklamalar, yorumlar ve rapor metni Türkçe. Kod içi değişken isimleri İngilizce olabilir.

**Tarz:** Kısa, doğrudan, pratik. Bir sayının nereden geldiğini açıkla.

---

## 1. DEĞERLENDİRME KRİTERLERİ (Yasir Kılıç'ın açıklaması)

Rapor bu maddelere göre okunacak:

| Kriter | Bu proje nasıl karşılıyor |
|---|---|
| Gerçek dünya problemi, jenerik tutorial değil | Donanım + kalibrasyon + ölçüm belirsizliği; kopyala-yapıştır çözümü yok |
| Şirket iş vermezse öğrenci türetsin | Türetmeye gerek yok — stereo kalibrasyon zaten verilen gerçek görev |
| %100 çözüme ulaşılmasa da olur, yoğunlaş | Çalışma zarfı ve kısıtların açıkça tanımlanması |
| Özgün figür, akış diyagramı, sözde kod | Kalibrasyon pipeline şeması, hata eğrisi, doğrulama tabloları, kutu açılım çizimi |
| Ön bilgi konularını KISA tut | "Stereo görü nedir", "OpenCV nedir" → en fazla yarım sayfa toplam |
| Canlı (live) demo | Disparity haritası + nokta bulutu + gerçek zamanlı ölçüm + kutu çıktısı |
| Uzun kod dökümü yok | Sadece kritik kod parçaları; gerisi sözde kod |

### ⚠️ Tek risk ve çözümü

Hoca "**staj yerinin ihtiyacına yönelik** çözüm" diyor. Kargo/kutu senaryosu
stajın yürütüldüğü kurumun işiyle doğrudan ilgili olmayabilir. Sözlü sınavda "şirketin bu işi mi var?"
sorusu gelebilir.

**Çerçeveyi böyle kur — senaryoyu "şirket ihtiyacı" değil "doğrulama aracı" olarak sun:**

> Staj kapsamında verilen görev, iki kameralı bir görüş sisteminin kalibrasyonu ve
> derinlik bilgisi elde edilmesiydi. Şirket verisi ve uygulaması gizlilik kapsamında
> olduğundan, aynı kalibrasyon zincirini kendi donanımım ve verimle kurarak, sonuçları
> doğrulanabilir bir uygulama senaryosu üzerinden test ettim. Kutu boyutlandırma
> senaryosunu seçmemin nedeni, üretilen her ölçümün kumpasla bağımsız olarak
> doğrulanabilmesi ve sistemin çıktısının somut biçimde sınanabilmesidir.

Bu cümle gerçek görevi belirtiyor, gizliliği açıklıyor ve senaryonun **neden seçildiğini**
gerekçelendiriyor.

### Ek-3 (Sicil Belgesi) notu

Süpervizörün dolduracağı kriterler arasında **"Problem tanımlama ve modelleme"** var.
Ölçüm defteri tutmak, başlangıç metriklerini kayıt altına almak, çalışma zarfını
formülden türetmek bu maddeye giren davranışlar. Sessizce yapma — süpervizörün görmesi
işine yarar.

---

## 2. UYGULAMA SENARYOSU — KİLİTLİ

**Senaryo: masaüstü cisim ölçümü → kargo kutusu önerisi ve kesim yönergesi.**

Karar gerekçesi: her çıktı kumpasla doğrulanabiliyor (5 cisim × 3 boyut = 15 bağımsız
karşılaştırma) ve sistem sadece sayı değil **kullanılabilir bir çıktı** üretiyor.

Değerlendirilip elenen alternatifler (raporda "neden bu senaryo" bölümüne malzeme):

| Senaryo | Neden seçilmedi |
|---|---|
| Robot kolu için 3B konum | Doğrulanabilir ama çıktısı soyut, demoda etkisi zayıf |
| Mesafe / sanal güvenlik bölgesi | Demosu iyi, ama tek bir sayı üretir; doğruluk analizi zayıf kalır |
| Sahne anlama / oda tarama | SLAM gerektirir, süreye sığmaz |
| Çok açılı 3B tarama | Hizalama gerektirir; "gelecek çalışmalar"a bırakıldı |

> Bölüm 4'teki Aşama 0–E işleri senaryodan tamamen bağımsız. Senaryo kilitli olsa bile
> **önce o zinciri kur**, kutu mantığına en son geç.

---

## 3. ÜRÜN: KUTU ÖNERİSİ VE KESİM YÖNERGESİ ⭐

Projenin kullanıcıya dönük yüzü burası. Sistem ölçtükten sonra iki şey üretir.

### 3.1 Neden stereo gerekiyor

Tek kamerada piksel boyutu mesafeye bağlı değişir, mutlak ölçüm yapılamaz.
Yükseklik ekseni ise derinlik olmadan hiç çıkarılamaz. Bir cismin kutusunu hesaplamak
için üç eksenin de metrik olarak bilinmesi şart.

### 3.2 Çıktı A — Standart kutu önerisi

1. Ölçülen boyutlara **paketleme payı** ekle (her yöne 1–2 cm; dolgu malzemesi payı)
2. Standart kargo kutu tablosundan sığanları filtrele
3. **Üç eksen permütasyonunu dene** — cismi döndürünce daha küçük kutuya sığabilir
4. Hacimce en küçüğünü seç
5. **Desi = (E × B × Y) / 3000**; ücret, desi ile gerçek ağırlıktan büyük olanına göre

Örnek çıktı:

```
Ölçüm    : 18,2 × 12,1 × 7,4 cm   (±3 mm)
Pay ile  : 20 × 14 × 9 cm
Önerilen : No.3 standart koli (25 × 15 × 10 cm)
Desi     : 1,25   →  ücretlendirme desi üzerinden
Boşluk   : %38 (dolgu gerekir)
```

> Standart kutu tablosunu bir JSON/CSV dosyasında tut, koda gömme. Kargo firmalarının
> yayınladığı ölçüleri kullan ve **kaynağını rapora yaz**; uydurma tablo kullanma.

### 3.3 Çıktı B — Cisme özel kesim yönergesi (RSC açılımı)

Standart kutuda çok boşluk kalıyorsa veya kullanıcı isterse, sistem cisme özel bir
**RSC (Regular Slotted Container)** açılımı üretir. Hedef kitle mühendis değil — çıktı
"şu ölçülerde kes, şuradan katla" seviyesinde **basit ve ölçülü** olmalı.

Geometri:

```
Açılım genişliği = 2×(E + B) + yapıştırma payı (~3–4 cm)
Açılım yüksekliği = Y + 2×(B/2) + karton kalınlığı payı
Kanat boyu       = B / 2   (üst ve alt kapaklar ortada birleşir)
Katlama çizgileri = E, E+B, 2E+B, 2E+2B  (genişlik ekseninde)
```

Çıktı formatı: **tek sayfa PDF** (ölçekli değil, ölçü yazılı şematik çizim) +
opsiyonel DXF. Üzerinde:

- Kesim çizgileri düz, katlama çizgileri kesikli
- Her segmentin mm cinsinden ölçüsü yazılı
- Kısa metin yönerge: "1) Kartonu 62 × 21 cm kesin. 2) Kesikli çizgilerden katlayın.
  3) Yan payı yapıştırın. 4) Alt kapakları kapatıp bantlayın."

> **Karton kalınlığı payı unutulmasın.** 3 mm oluklu kartonda payı hesaba katmazsan
> kutu cismi sıkar. Her katlama için ~1× kalınlık ekle; kullandığın kartonu kumpasla
> ölç ve değeri parametre yap.

**Demoda etkisi büyük: ölç → yazdır → kes → katla → cisim tam oturur.**
Bu, "ölçtüm ve sayı yazdırdım"dan farklı olarak sistemin doğruluğunu fiziksel olarak
kanıtlar. Kutu sıkıyor veya boşluk kalıyorsa ölçüm hatası oradan görünür — yani
**kesim yönergesi aynı zamanda bir doğrulama aracıdır.** Raporda böyle sun.

### 3.4 Ticari sistemlerle konumlandırma (KISA TUT — en fazla 1 paragraf)

Referans: Cubiscan 100 sınıfı sabit dimensioner. Ultrasonik, ~2,5 mm adım, 1–2 saniye,
LFT/NTEP/OIML sertifikalı. **Kısıtı:** tekil ürün; tekstil ve küp olmayan cisimlerde
kullanılamıyor. Fiyat bandı sektör analizlerine göre orta segmentte 5.000–15.000 USD+;
Türkiye'ye getirme maliyeti (navlun + gümrük + KDV) bunun üstüne çıkıyor ve üreticinin
uluslararası distribütör listesinde Türkiye yok.

**Konumlandırma cümlesi:**
> "Aynısını ucuza yaptım" değil →
> *"Düşük hacimli kullanım için, yeterli doğrulukta, çok düşük maliyetli bir alternatif."*

> ⚠️ Bu bölümü uzatma. Rakamların hiçbiri birincil kaynaktan doğrulanamıyor; sözlü
> sınavda savunması en zor kısım burası. "Yaklaşık", "sektör kaynaklarına göre" diye
> ve kaynak göstererek yaz, net rakam verme. Rapor puanı Bölüm 5'ten gelecek, buradan değil.

---

## 4. TEKNİK AKIŞ

### Aşama 0 — Kamera test aracı ⭐ İLK YAZILACAK KOD

Küçük tut (~80–100 satır). Sonraki aşamalarda da kullanılacak iskelet bu.
Üç işi birden görecek: **odak eşitleme, kalibrasyon karesi toplama, epipolar kontrol.**

**İçermesi gerekenler:**

- İki kameradan eşzamanlı okuma, tek pencerede yan yana görüntü
- Her kare için **Laplacian varyansı** (netlik skoru), her iki kamera için canlı yaz
- **FPS sayacı** — USB bant genişliği sorununu buradan yakalarsın
- Tuşla anlık kare çifti kaydetme (kalibrasyon kareleri de bununla toplanacak)
- **Her iki kameranın çözünürlük ve görüş açısı karşılaştırması** (ilk gün, bir kez)

**⭐ Otomatik ayarların kapatılması — atlanırsa disparity hiç düzgün çıkmaz:**

İki bağımsız UVC kamera, aynı sahnede farklı pozlama, gain ve beyaz dengesi seçer.
Aradaki parlaklık/renk farkı blok eşleştirmeyi doğrudan bozar — ve bu, senkronizasyon
sorunundan daha çok zarar verir. Araç açılışta şunları **manuele kilitlemeli:**

```python
cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)   # DSHOW'da 0.25 = manuel (sürücüye göre değişir)
cap.set(cv2.CAP_PROP_EXPOSURE, exposure_value)
cap.set(cv2.CAP_PROP_AUTO_WB, 0)
cap.set(cv2.CAP_PROP_WB_TEMPERATURE, wb_value)
cap.set(cv2.CAP_PROP_GAIN, gain_value)
```

- Değerler **iki kamerada da aynı** olmalı, sonra gerekiyorsa histogram eşitlenmeli
- Her `set()` çağrısının dönüş değerini kontrol et — bazı sürücüler sessizce yok sayar,
  `get()` ile geri okuyup doğrula
- Kullandığın değerleri ölçüm defterine yaz; kalibrasyon bu aydınlatma altında yapılacak
- Aydınlatmayı sabitle: gün ışığı değişiyorsa masa lambasıyla çalış, perdeyi kapat

**Windows notları:** `cv2.VideoCapture(0, cv2.CAP_DSHOW)` gerekebilir. Kamera indeksleri
takılı sıraya göre değişir, birkaç deneme normal. Bant genişliği için MJPEG zorla:
`cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))`.
İki kamerayı **farklı USB controller'lara** tak (genelde farklı fiziksel port grupları).

### Aşama A — Odak ayarı (kalibrasyondan ÖNCE)

- Odağı sonsuza değil, **çalışma mesafesine** ayarla (~30–90 cm bandı öngörülüyor)
- İki kamerada net alan derinliği benzer olmalı
- **Sayısal karşılaştır**, göz kararı yapma — Aşama 0'daki Laplacian skoru bunun için
- Odağı bulunca fiziksel olarak kilitle (vida kilit / oje)

> ⚠️ Kalibrasyondan sonra lense dokunursan intrinsics geçersiz olur, baştan başlarsın.

### Aşama B — Gövde ve baseline (**baseline tasarım değil, veri**)

Gövde hazır: kameralar için 3B basılmış yuvaları var, iki modül birbirine sabit.
Yani **baseline seçilmiyor, ölçülüyor.** Bu, brifin önceki halinden farklı bir durum ve
mühendislik argümanını tersine çeviriyor:

**Yapılacaklar:**

1. İki lens merkezi arasındaki mesafeyi **kumpasla ölç** → yaklaşık baseline (B₀)
2. Gerçek baseline zaten kalibrasyondan gelecek: **‖T‖ (öteleme vektörünün normu)**.
   Kumpas ölçümüyle karşılaştır — %5'ten fazla sapma varsa kalibrasyonda sorun var demektir.
   *Bu karşılaştırma raporda ücretsiz bir doğrulama satırı.*
3. Bu sabit B ile **çalışma zarfını türet**, tersini değil:

```
Derinlik belirsizliği:  ΔZ ≈ Z² · Δd / (f · B)

Δd = disparity ölçüm belirsizliği (alt-piksel eşleştirmede ~0,25–0,5 px varsay,
     sonra 5.3'teki tekrarlanabilirlik testiyle GERÇEK değerini bul ve güncelle)
f  = piksel cinsinden odak uzaklığı (K matrisinden)
B  = ‖T‖ (mm)
```

4. Hedef doğruluğu (±3 mm) sağlayan **maksimum Z**'yi bu formülden çöz.
   Minimum Z'yi ise ortak görüş alanı belirler: baseline büyükse yakın mesafede iki
   kamera aynı cismi göremez ve occlusion artar. **Deneysel bul:** cismi yaklaştıra
   yaklaştıra iki görüntüde de tam göründüğü en yakın mesafeyi ölç.

> Raporda böyle anlat: *"Baseline mevcut gövde tarafından sabitlendiği için tasarım
> değişkeni değil, girdiydi. Bu nedenle baseline'ı hedef doğruluğa göre seçmek yerine,
> mevcut baseline'ın hangi çalışma aralığında hedef doğruluğu sağladığını türettim."*
> Bu, formülden bir sayı seçmekten daha dürüst ve daha ilginç bir mühendislik anlatısı.

**Mekanik kararlılık kontrolü:**

- Gövdeyi kalibrasyondan önce sıkıştır; vidalar gevşekse kalibrasyon her seferinde kayar
- Kalibrasyondan sonra vida başlarına oje/işaret koy → oynadığını gözle görürsün
- **Kararlılık testi:** kalibrasyondan hemen sonra ve 2 saat sonra epipolar hatayı ölç.
  Arttıysa gövde oynuyor veya termal genleşme var. Bu tabloyu rapora koy.
- Baskı PLA ise Adana sıcağında deforme olabilir — gövdeyi güneş görmeyen, sıcaklığı
  sabit bir yerde tut ve ölçüm defterine oda sıcaklığını yaz

### Aşama C — Kalibrasyon

```
Her kamera ayrı: calibrateCamera()
       ↓
stereoCalibrate()  [CALIB_FIX_INTRINSIC]
       ↓
stereoRectify()  →  Q matrisi
```

- **ChArUco** tercih edilir (chessboard'a göre kısmi görünürlükte de çalışır)
- ~25–40 kare çifti; köşeler ve farklı eğim açıları dahil
- Hedef RMS < 0,4 px
- Kalibrasyon, Aşama 0'da kilitlenen **aynı pozlama/gain/WB ayarlarıyla** yapılmalı

**⭐ Desen ölçüsü — asıl tuzak burada:**

Kare boyutunu mm cinsinden yanlış girersen her ölçüm o oranda hatalı çıkar ve sistem
*tutarlı şekilde* yanlış olduğu için fark etmesi çok zor. Ama asıl tehlike yazım hatası
değil:

> **Ev/ofis yazıcıları deseni %96–98 ölçekle basar** ("fit to page" varsayılanı).
> Nominal 25 mm dediğin kare kâğıtta 24,1 mm çıkar ve bunu asla fark etmezsin.
>
> **Yapılacak:** Deseni "gerçek boyut / %100 ölçek / ölçeklendirme yok" ayarıyla bas,
> sonra **basılı kareyi kumpasla ölç** ve *ölçtüğün* değeri koda gir. Birkaç kareyi
> ölçüp ortalama al (tek kare ölçmek yazıcı hassasiyetini yakalamaz).

**Desen düzlüğü:** Kâğıt kıvrıksa kalibrasyon RMS'i düşük çıkabilir ama sonuç yanlış
olur. Deseni cama, sert plakaya veya kalın mukavvaya **tamamen düz** yapıştır. Köşelerden
teypleme, tüm yüzeyi yapıştır.

**İlk sağlama:** Kalibrasyondan sonra hemen cetvelle bilinen bir mesafeyi (örn. masaya
çizilen 200 mm) ölç. Sistematik yüzde hatası varsa desen ölçüsünden geliyordur.

### Aşama D — Zemin düzlemi kalibrasyonu ⭐ (yeni, atlanmamalı)

Bölüm 4-F'deki hibrit ölçüm bilinen bir zemin düzlemine dayanıyor. **Bu düzlemi
nokta bulutundan RANSAC ile çıkarmak, yöntemin kendi mantığıyla çelişir:** disparity'ye
güvenmiyorsan düzlemi de disparity'den alma.

**Doğru yol:** ChArUco tahtasını ölçüm yapılacak zemine düz yatır, tek kare çek,
`estimatePoseCharucoBoard()` ile pose'unu çöz. Tahtanın kendi düzlemi = zemin düzlemi.
Normal vektörü ve `d` katsayısını bir dosyaya kaydet, sonraki tüm ölçümlerde kullan.

Avantajları:
- Düzlem, disparity gürültüsünden tamamen bağımsız
- Tek seferlik; gövde ve zemin oynamadıkça geçerli
- Doğruluğu kalibrasyon RMS'i kadar iyi

> **Geçerlilik kontrolü:** Zemin düzlemine sonradan konan düz bir cetvelin yüksekliğini
> ölç — sıfıra yakın çıkmalı. Sapma, düzlemin kaydığını gösterir. Bu kontrolü her
> ölçüm oturumunun başında tekrarla.

### Aşama E — 3B'ye geçiş

Kalibrasyonun kendisi çevirici matrisi veriyor:

```python
disparity  = stereo.compute(rectL, rectR)
points_3d  = cv2.reprojectImageTo3D(disparity, Q)   # metrik nokta bulutu
```

Metrik ölçek: **T vektörünün normu = baseline**, K matrisi = odak uzaklığı.
Kalibrasyon olmadan sadece göreli derinlik olur, milimetre karşılığı olmaz.

### Aşama F — HİBRİT ÖLÇÜM ⭐ (raporun en değerli mühendislik kararı)

**Problem — yoğun disparity'ye güvenmek iki nedenle hatalı:**

1. **Dokusuz yüzey:** Düz beyaz kartonda her yama diğerine benzer, eşleştirme
   belirsizleşir. *Sahnenin temiz olması bunu çözmez* — sorun cismin kendi içindeki
   desensizlik.
2. **Occlusion:** Bir kamera cismin arkasındaki zemini görürken diğeri cismi görür.
   Yani ölçüm için en kritik bölge (kenarlar), disparity'nin en gürültülü olduğu bölge.

**Yaklaşım — geometrik kısıtlardan yararlan:**

| Ölçü | Yöntem | Neden |
|---|---|---|
| **En & Boy** | Cismin **taban konturu** → bilinen zemin düzlemine geri-projeksiyon | Disparity'ye ihtiyaç yok; kalibrasyon + düzlem denklemi yeter |
| **Yükseklik** | Üst yüzeyden birkaç güvenilir nokta → zemine medyan mesafe | Dolu disparity gerekmez, seyrek nokta yeter |

**⭐ Taban konturu — tüm siluet DEĞİL:**

Bu, önceki brifteki geometrik hatanın düzeltilmiş hali. Kamera ~45° eğik baktığında
cismin siluetine **üst yüzey de dahil olur.** Tüm silueti zemine geri-projekte edersen
en ve boy **sistematik olarak büyük** çıkar — üstelik hata mesafeyle değiştiği için
sabit bir düzeltmeyle kapatılamaz.

Kullanılması gereken şey: cismin **zeminle temas ettiği alt kenar.** Pratikte:

- Siluet maskesi çıkar (arka plan çıkarma veya renk/kenar tabanlı segmentasyon)
- Maskenin **zemin düzlemine en yakın kenarını** ayır — görüntüde alt sınır,
  3B'de düzleme mesafesi ~0 olan kontur noktaları
- Sadece bu noktaları zemin düzlemine geri-projekte et → taban dörtgeni
- Taban dörtgenine **oriented bounding box** uydur → en ve boy

> Bu ayrımı yapmazsan sistem çalışır gibi görünür ama %10–20 aralığında sabit şişkin
> ölçer. Kutu önerisinde bu, bir kutu numarası büyük seçmene yol açar — yani hata
> çıktıda görünür. **Bunu bir doğrulama kancası olarak kullan:** kasten tüm silueti
> kullanan bir varyantı da çalıştır, iki sonucu tabloda karşılaştır. Bölüm 5.5'e ek bir
> deney olur ve yöntem seçimini deneysel olarak gerekçelendirir.

**Yükseklik için:** Üst yüzeyden disparity'nin güvenilir olduğu (confidence eşiğini
geçen) noktaları al, zemin düzlemine dik mesafelerinin **medyanını** kullan.
Ortalama değil medyan — birkaç kötü eşleşme ortalamayı bozar.

> **RAPORDA BÖYLE ANLATILABİLİR:**
> "Tam yoğun disparity yerine, sahnenin geometrik kısıtlarından (kalibrasyonla
> belirlenen zemin düzlemi) yararlanan hibrit bir ölçüm yaklaşımı benimsenmiştir. Bu
> karar, disparity'nin en güvenilmez olduğu bölgelerden (dokusuz alanlar ve occlusion
> kaynaklı kenarlar) ölçüm alınmasını engelleyerek doğruluğu artırmıştır. Ayrıca
> yatay boyutlar için tüm siluet yerine yalnızca cismin zeminle temas eden taban
> konturu kullanılmış, böylece eğik bakış açısından kaynaklanan sistematik büyütme
> hatası ortadan kaldırılmıştır."
>
> Projeyi "hazır fonksiyon çağırdım"dan çıkaran kısım bu. Yöntem değişse bile
> **"neden bu yolu seçtim" anlatısı** raporda mutlaka olsun.

**Not:** Naif yoğun disparity yeterince iyi çalışırsa hibrit yola gerek kalmayabilir.
Önce ölç, sonra karar ver. Her iki durumda da gerekçeni yaz.

### Aşama G — Kutu çıktısı üretimi

Bölüm 3'teki mantığın kodlanması. Girdi: (E, B, Y) + belirsizlik.
Çıktı: standart kutu önerisi + desi + (istenirse) kesim yönergesi PDF'i.

> **Belirsizliği çıktıya taşı.** Ölçüm ±3 mm ise paketleme payını buna göre seç.
> "18,2 cm" yerine "18,2 ± 0,3 cm" raporlamak ve payı bunun üstüne eklemek, sistemin
> kendi sınırını bildiğini gösterir. Sözlü sınavda sorulursa hazır cevap olur.

---

## 5. DOĞRULAMA ⭐ (projeyi sıradan olmaktan çıkaran kısım)

Fikir klasik olabilir — sorun değil. **Klasik fikri değerli kılan şey doğruluk analizidir.**
Buradaki tabloların hepsini üretmeye zaman ayır; rapor puanının çoğu buradan gelecek.

**5.1 Başlangıç durumu** (ilk gün, hiçbir ayar yapmadan):
netlik skoru / köşe tespit oranı / kalibrasyon RMS / epipolar hata / FPS —
her iki kamera için ayrı ayrı. **Kullanılan pozlama-gain-WB değerlerini de yaz.**
Aynı tabloyu sonda tekrar doldur → önce/sonra karşılaştırması.

**5.2 Mesafeye göre hata eğrisi** ⭐
Aynı cismi 40, 60, 80, 100 cm'de ölç, hatayı grafikle.
**Teorik Z²·Δd/(f·B) eğrisiyle karşılaştır.** Bu tek grafik projeyi mühendislik işine
dönüştürür. Δd'yi 5.3'ten gelen gerçek değerle besle, varsayımla değil.

**5.3 Tekrarlanabilirlik** — aynı cismi hiç kıpırdatmadan 10 kez ölç, standart sapma ver.
Sonra cismi kaldırıp tekrar koyarak 10 kez daha ölç — ikinci standart sapma daha büyük
çıkacak, aradaki fark **konumlandırma hassasiyetini** gösterir. İki sayıyı ayrı raporla.

**5.4 Çalışma zarfı** — "30–90 cm arasında ±3 mm, dışında güvenilir değil."
Sınırını bilmek, çalıştırmaktan daha olgun. Hocanın "%100 çözüme ulaşılmasa da olur"
maddesini tam karşılar.

**5.5 Kalibrasyon kalitesinin sonuca etkisi** ⭐
Kasten kötü kalibre edilmiş setle (az kare, tek açı, kıvrık desen) ölç; iyi olanla
karşılaştır. Kalibrasyonun neden gerekli olduğunu **deneysel olarak kanıtlarsın** —
projenin asıl konusu bu.

**5.6 Yöntem karşılaştırması** (Aşama F'den)
Aynı 5 cisim üç yöntemle ölçülüp tabloya konur:
naif yoğun disparity · tüm siluet geri-projeksiyonu · taban konturu (seçilen yöntem).
Yöntem seçimi böylece iddia değil, veri olur.

**5.7 Pozlama/aydınlatma duyarlılığı** (yeni, ucuz ve etkili)
Aynı cismi (a) kilitli eşit ayarlarla, (b) otomatik pozlama açıkken ölç.
Disparity geçerli piksel oranını ve ölçüm hatasını karşılaştır. Bölüm 4-Aşama 0'daki
kilitleme kararını deneysel olarak gerekçelendirir. Yarım saatlik iş.

**5.8 Mekanik kararlılık** — kalibrasyondan 0/2/24 saat sonra epipolar hata.

**5.9 Ana sonuç tablosu** — 5 cisim × (kumpas / sistem / hata mm / hata % / önerilen kutu)

**5.10 Fiziksel doğrulama** ⭐ — kesim yönergesiyle üretilen kutunun cisme uyup uymadığı.
Sistemin çıktısının gerçek dünyada sınandığı tek test bu; demoda da en güçlü an.

---

## 6. BİLİNEN KISITLAR (raporda "sistemin sınırları")

Gizleme, **yaz** — kısıtı fark etmek olgunluk göstergesi:

1. **Kamera modülleri özdeş olmayabilir.** Farklı sensör/lens, ortak görüş alanını
   daraltır ve eşleştirmeyi zorlaştırır. Ölçülen FOV/çözünürlük farkını rapora yaz.
2. **Otomatik pozlama/WB:** İki bağımsız UVC kamera farklı ayar seçer; manuel kilit
   şart. Kilit sürücü tarafından yok sayılırsa histogram eşitleme gerekir.
3. **Dokusuz/parlak yüzeyler:** Test cisimlerini dokulu seç (baskılı koli, kitap).
   *Olası çözüm:* telefon/mini projektörle rastgele nokta deseni (yapısal ışık mantığı).
   Bir akşamlık iş, etkisi dramatik olabilir.
4. **Tek görüş:** Kutu benzeri cisimlerde sorun yok, düzensizlerde hata artar.
   Taban konturu yöntemi cismin zeminle temas etmesini varsayar — asılı/eğik cisimlerde
   geçersiz.
5. **Kamera açısı:** ~45° eğik. Tam tepeden bakarsan yükseklik çıkmaz, tam yandan
   bakarsan taban konturu görünmez.
6. **Senkronizasyon:** İki ayrı UVC kamerada donanım senkronu yok. Statik ölçümde
   sorun değil, hareketli sahnede kare kayması olur.
7. **USB bant genişliği:** Aynı controller'a takarsan yetmeyebilir. MJPEG, farklı portlar.
8. **Termal/mekanik kararlılık:** Gövde oynarsa epipolar hata büyür; kalibrasyon
   tekrarlanmalı.
9. **Zemin düzlemi sabit varsayımı:** Kamera veya zemin oynarsa düzlem geçersizleşir.
   Her oturum başında cetvelle sağlama gerekir.
10. **Kesim yönergesi karton kalınlığına duyarlı:** Kullanılan kartonun kalınlığı
    parametre olarak girilmezse kutu sıkar veya bol olur.

---

## 7. RAPOR İSKELETİ (Ek-4 şablonuna uyarlanacak)

1. **Giriş / Problem tanımı** — kısa tut. Tek kameranın neden yetersiz olduğu,
   senaryonun gerekçesi, ticari sistemlerin maliyeti (1 paragraf)
2. **Yöntem** — pozlama/odak eşitleme, baseline'dan çalışma zarfı türetimi, kalibrasyon,
   rektifikasyon, zemin düzlemi kalibrasyonu, hibrit ölçüm, kutu çıktısı üretimi
3. **Akış şeması** (kutu-ok, kod değil):
   `Ayar kilidi → Kare yakalama → Köşe tespiti → Intrinsik → stereoCalibrate
   → stereoRectify → Zemin düzlemi → Taban konturu + Yükseklik → Kutu seçimi → Açılım`
4. **Sözde kod** — 2–3 tane, kısa: odak/pozlama eşitleme döngüsü, kalibrasyon karesi
   kabul kriteri, kutu permütasyon araması
5. **Sistem tasarımı** — gövde, ölçülen baseline, ‖T‖ ile karşılaştırma, fotoğraf
6. **Sonuçlar** — Bölüm 5'teki tablolar ve grafikler
7. **Kısıtlar ve gelecek çalışmalar**

> ⚠️ "Stereo görü nedir", "OpenCV nedir", "disparity nedir" gibi ön bilgi kısımları
> **toplamda yarım sayfayı geçmesin.** Hoca bunu açıkça belirtiyor.

**Gelecek çalışmalar (uğraşmaya gerek yok, yazılması yeterli):**
SQLite nesne kaydı ve "sığar mı" sorgusu · çoklu cisim için kutu istifleme (bin packing) ·
çok açılı tarama + 3B baskı · oda ölçümü (SLAM gerektirir) · YOLO tespit + derinlik
füzyonu · yapısal ışık projeksiyonu · kargo firması fiyat API'si entegrasyonu

---

## 8. DEMO PLANI (sözlü sınav %40)

1. Rektifiye edilmiş yan yana iki görüntü + epipolar çizgiler
2. Renkli disparity haritası (elini uzatınca renk değişir)
3. Open3D nokta bulutu penceresi — dönen 3B küme
4. Cismi koy → ekranda ölçü + **önerilen kutu + desi**
5. ⭐ **Kesim yönergesini bastır → kes → katla → cisim tam oturur**
6. Hata eğrisi grafiği (5.2) — "sistemin nerede çalıştığını biliyorum"

> 5. madde demonun kapanışı olsun. Sayı göstermek değil, **fiziksel olarak doğrulanan
> bir çıktı** göstermek sunumu ayırır.

Ayrıca: iş yerindeki çalışmaya ait ekran görüntüsü/video ile desteklemek sunumun
"Diğer durumlar" maddesinde öneriliyor — gizlilik sınırını aşmayan görseller varsa kullan.

---

## 9. ÇALIŞMA SIRASI (tahmini, sabit değil)

> **İlke: önce uçtan uca kaba çalıştır, sonra iyileştir.**
> Tersini yapıp önce mükemmel disparity peşine düşersen vakit yer.

| # | İş | Süre |
|---|---|---|
| 0 | **Kamera test aracı** + pozlama/gain/WB kilidi (Aşama 0) | 1 gün |
| 1 | İki kameranın karşılaştırması + başlangıç ölçümleri (5.1) | 0,5 gün |
| 2 | Odak eşitleme + gövdeye montaj + baseline kumpas ölçümü | 0,5 gün |
| 3 | Desen basımı, kumpasla doğrulama, sert plakaya montaj | 0,5 gün |
| 4 | Kalibrasyon + rektifikasyon + ‖T‖ karşılaştırması | 1,5–2 gün |
| 5 | Zemin düzlemi kalibrasyonu (Aşama D) | 0,5 gün |
| 6 | Dokulu bir cisimle uçtan uca **kaba** ölçüm | 1 gün |
| 7 | Ölçüm yönteminin iyileştirilmesi (taban konturu, Aşama F) | 2 gün |
| 8 | Kutu önerisi + kesim yönergesi çıktısı (Aşama G) | 1 gün |
| 9 | Doğrulama testleri (Bölüm 5) | 1,5 gün |
| 10 | Rapor + demo hazırlığı | 2 gün |

**En çok zorlanılacak yer: adım 7 (ölçüm yöntemi).** Kalibrasyon→3B geçişi zor değil,
kalibrasyonun kendisi Q matrisini veriyor. Zaman yerse adım 8'i sadeleştir
(kesim yönergesini elle çizilmiş şablona indir), adım 9'u **asla kısma.**

**Ölçüm defterini ilk günden tut:** tarih, ayar (pozlama/gain/WB dahil), oda sıcaklığı,
sayı. Rapor yazarken geriye dönük hatırlamaya çalışmak en çok vakit kaybettiren şey.

---

## 10. ARAÇLAR

Python 3, OpenCV, Open3D, NumPy, matplotlib · `cv2.aruco` (ChArUco kalibrasyon +
`estimatePoseCharucoBoard` zemin düzlemi) · `cv2.reprojectImageTo3D` ·
`get_oriented_bounding_box()` · `remove_statistical_outlier()` ·
kesim yönergesi PDF'i için `reportlab` veya `matplotlib` · DXF için `ezdxf` (opsiyonel) ·
SQLite (opsiyonel)

**Claude Code** kod yazma/çalıştırma/düzeltme döngüsü için uygun (kamera indeksleri,
backend seçimi, pozlama property'lerinin sürücüde tutup tutmadığı gibi şeylerde birkaç
tur deneme olacak).
**Cowork** rapor yazımı ve şekil/grafik üretimi aşamasında düşünülebilir.

---

## 11. CLAUDE'A TALİMAT

- Türkçe yanıt ver, kısa ve doğrudan ol
- Kod yazarken açıklamalı yaz — bir sabitin veya parametrenin nereden geldiğini belirt
- Rapor metni yazarken akademik ama abartısız dil; doğrulanamayan rakam yazma
- **Bölüm 3 (kutu çıktısı), 4-F (ölçüm yaklaşımı) ve 5 (doğrulama)** projenin ayırt
  edici kısımları
- 3B baskı ana iş değil — gövde hazır. Zorunlu olmadıkça baskı önerme.
- Gizlilik: şirket verisi/kodu bu projeye girmeyecek
- Bir şeyin çalışmayacağını düşünüyorsan söyle, iyimser tahmin verme
- **Bu dokümandaki kararlar tartışmaya açık.** Daha iyi bir yol görüyorsan öner;
  "brifte böyle yazıyor" diye kötü bir kararı savunma. Plan değişirse dosyayı güncelle.
