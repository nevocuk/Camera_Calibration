# Staj Raporu — Cowork Devir Dosyasi

> **Bu dosya rapor DEGIL, rapor yazmak icin girdi.**
> Cowork bu dosyadaki metni ve sayilari kullanarak Ek-4 formatinda
> docx uretecek. Sayilarin hicbiri tahmin degil; her biri
> `docs/ilerleme_gunlugu.md` icinde olcum kaydiyla duruyor.
>
> Hazirlayan: Claude Code (donanim/olcum tarafi)
> Tarih: 2026-08-20

---

## 0. GOREV TANIMI

**Rapor:** ATU Bilgisayar Muhendisligi zorunlu staj raporu (Ek-4).
**Ogrenci:** Nevfel — bu **ikinci** staj projesi.
**Kapsam:** Rapor iki projeyi kapsayacak; bu dosya **yalnizca stereo
kamera projesini** anlatiyor. Diger proje ayrica yazilacak.
**Hedef uzunluk:** Bu proje icin ~8 sayfa govde (ornek raporda tum
proje 16 sayfaydi; bizimki daha teknik oldugu icin ayni sayfada daha
yogun icerik olacak).

### Ornek rapora gore FARK — onemli
Ornek rapor (`docs/ornek_staj_raporu.pdf`) gun gun "sunu yaptim"
anlatiyor. Bizimkinde **ogrenilen sey ve karsilasilan hata** one
cikmali:

- Her gun bolumunde en az bir **"ne bekledik / ne cikti / neden"**
- Basarisiz denemeler **gizlenmeyecek**, ayri baslikla anlatilacak —
  raporun en degerli kismi bunlar
- Her iddia bir **sayiya** dayanacak

### KURAL — pazarlama dili yok
- Sirket verisi/kodu **rapora girmeyecek**.
- Senaryo "sirket ihtiyaci" degil **"dogrulama araci"** olarak
  sunulacak: "kargo kutusu onerisi" bir uygulama ornegi, is talebi
  degil.
- "Basariyla tamamlandi", "mukemmel sonuc" gibi ifadeler
  kullanilmayacak. Neyin calistigi, neyin calismadigi, hangi
  sinirlarla — hepsi acikca.

---

## 1. PROJE OZETI (rapor bolum 3 icin)

**Amac:** Iki USB kamera ile stereo derinlik haritasi olusturup
masadaki bir cismin 3B boyutlarini olcmek; cikti olarak uygun kargo
kutusunu onermek. Sistem bir **olcum dogrulama araci** olarak
kurgulandi — her adimin dogrulugu bagimsiz olcumle sinandi.

**Donanim**

| Bilesen | Deger |
|---|---|
| Kamera | 2 x USB, OV5693 sensor, M12 lens |
| Govde | 3B basilmis, sabit baz |
| Cozunurluk | 2048 x 1536, MJPG, ~25-30 fps |
| Baz uzunlugu | 71.79 mm (kalibrasyondan olculdu) |
| Ortam | Windows 11, Python 3.11, OpenCV 4.10 |

**Yazilim mimarisi (islem sirasi)**

```
Yakalama -> Rektifikasyon -> On-isleme -> SGBM+WLS -> Temizleme
  -> reprojectImageTo3D -> Segmentasyon -> PCA kutusu -> Kutu onerisi
```

| Adim | Yontem | Neden |
|---|---|---|
| Yakalama | MSMF + MJPG, `grab()`/`retrieve()` | Iki kameranin es zamanli olmasi sart |
| Kalibrasyon | ChArUco 9x13, `stereoCalibrate` | Alt-piksel kose hassasiyeti |
| Rektifikasyon | `initUndistortRectifyMap` + `remap` | SGBM yalnizca yatay tarama satirinda esler |
| On-isleme | Histogram (CDF) ton esleme | Iki kameranin ton egrisi donanimsal farkli |
| Derinlik | StereoSGBM + WLS filtre | Ham SGBM cok gurultulu |
| 3B | `reprojectImageTo3D(Q)` | Yalnizca mesafe degil X,Y,Z birden |
| Segmentasyon | `floodFill` + parlaklik + 3B sinir | Cismi zeminden ayirmak icin |
| Boyut | PCA (SVD) yonlu sinir kutusu | Cisim goruntu eksenlerine hizali degil |

---

## 2. GUN GUN ICERIK (rapor bolum 4)

> Cowork: her gun icin verilen baslik + anlatilacak icerik + sayilar
> + gorsel dosyasi asagida. Anlatimi akici Turkce paragraflara cevir,
> madde madde birakma. Gun numaralari diger projeyle birlestirilirken
> yeniden numaralandirilacak.

---

### GUN A — Sistem kurulumu ve kamera karakterizasyonu
*(2026-08-13/14)*

**Yapilan:** Iki kameranin ayni anda 2048x1536'da calistirilmasi,
backend secimi, ilk kalibrasyon denemeleri.

**Karsilasilan sorun — backend:** DSHOW arayuzunde bazi kamera
ayarlari (beyaz dengesi, pozlama) iki kamerada tutarsiz
uygulaniyordu. MSMF'ye gecildi.

**Olculen — pozlama siniri:** Pozlama degerleri tarandi ve gercek
kare parlakligi olculdu:

| Pozlama | SOL / SAG parlaklik | Durum |
|---|---|---|
| −2 | 245 / 245 | Doymus — doku kalmiyor |
| −3 | 223 / 219 | Sinirda |
| **−5** | **104 / 150** | Kullanilabilir |
| −7 | 15 / 6 | Cok karanlik |

**Ogrenilen:** Doymus goruntude doku kalmadigi icin SGBM eslesme
yapamiyor. Kullanilabilir bant −5 … −3.

*Gorsel:* `patterns/charuco_board.png` (kalibrasyon deseni)

---

### GUN B — Kamera dengesizligi: uc yanlis teshis ve gercek neden
*(2026-08-17)*

**Bu gunun tamami bir hata avina gitti ve raporun en ogretici
bolumu olmali.**

**Belirti:** Iki kamera ayni sahneye bakarken belirgin farkli
goruntu veriyordu (parlaklik orani 2.7x). Bu, stereo eslemeyi
dogrudan bozuyor.

**Sirayla suclanan ve YANLIS cikan nedenler:**
1. Lens diyafram farki
2. Sensorlerin duyarlilik farki
3. Koruyucu film / uretim toleransi

**Gercek neden:** Kamera ayarlarini yazan fonksiyon 11 ozellikten
yalnizca 8'ini yaziyordu; **GAMMA, HUE ve BACKLIGHT hic
yazilmiyordu**. Bu ozellikler kamerada **kalici** saklandigi icin
gecmiste yazilan degerler oylece kaliyordu (olculdu: GAMMA sol 200,
sag 100).

**Kanit — 11 ozelligin tamami ayni degere yazildiginda:**

| Pozlama | SOL | SAG | Oran |
|---|---|---|---|
| −5 | 72.0 | 71.1 | 1.01x |
| **−4** | **120.0** | **120.5** | **1.00x** |
| −3 | 170.2 | 173.3 | 1.02x |

2.7x'lik farkin **tamami ayar kaynakliymis**; donanimsal degil.

**Ikinci bulgu — MSMF geri okumasi bozuk:** `cap.get()` ne yazilirsa
yazilsin ayni degeri donduruyor, ama ayar **gercekte uygulaniyor**
(kare parlakligi olculunce goruluyor). Bu yuzden koda "ayari geri
okuyup dogrula" mantigi **yazilmamali**.

**Ogrenilen:** Bir cihaz ayari geri okunamiyorsa, dogrulama cihazin
kendi raporundan degil **cikti verisinden** yapilmali.

---

### GUN C — Kalibrasyon ve "RMS iyi ise kalibrasyon iyidir" yanilgisi
*(2026-08-18)*

**Yapilan:** 44 kare cift ile stereo kalibrasyon.

**Sonuclar:**

| Olcut | Deger |
|---|---|
| Stereo RMS | 0.8340 px |
| Tekli RMS (sol / sag) | 0.7703 / 0.7682 px |
| Baz uzunlugu | 71.79 mm |
| f (rektifiye, P1[0,0]) | 1418.18 px |

**METODOLOJIK BULGU (raporda one cikarilmali):** RMS'i dusurmek
icin "kotu" kareler atildi. RMS gercekten dustu — ama **epipolar
hata kotulesti**. RMS, modelin kendi verisine ne kadar uydugunu
olcer; kare atmak veriyi kolaylastirir, modeli iyilestirmez.

Gercek kalite olcutu **epipolar hata**: 44 cift / 3264 kose
uzerinde **0.420 px**.

**Ogrenilen:** Bir uyum olcutunu (RMS) iyilestirmek icin veri
secmek, olcutun anlamini yok eder. Bagimsiz bir olcut gerekir.

**Ikinci bulgu — iki farkli odak uzunlugu var ve karistirilmamali:**

| Deger | Kaynak | Nerede kullanilir |
|---|---|---|
| 1288.28 px | `K1[0,0]` — ham | solvePnP, ham goruntu |
| **1418.18 px** | `P1[0,0]` — rektifiye | **Mesafe hesabi** |

Disparity rektifiye goruntude olculdugu icin mesafe formulunde
`P1[0,0]` kullanilmali.

*Gorseller:*
`output/reports/sekil3_rms_iyilesme.png`,
`output/reports/sekil4_kose_hata_analizi.png`

---

### GUN D — Derinlik haritasi: sezgiye ters cikan uc olcum
*(2026-08-18/19)*

**1. CLAHE (kontrast artirma) haritayi BOZUYOR**

Beklenti: kontrast artarsa esleme iyilesir. Olculen (6 gercek
stereo cift, ayni veri, farkli on-isleme):

| Konfigurasyon | Ort. sicrama | >2px sicrama |
|---|---|---|
| **CLAHE yok** | **0.361** | **%1.5** |
| CLAHE 1.0 | 0.399 | %1.9 |
| CLAHE 2.0 | 0.419 | %2.1 |

Neden: duz/dokusuz yuzeylerde CLAHE'nin yukselttigi sey **sensor
gurultusu**; SGBM bunu gercek doku sanip sahte eslesme uretiyor.
CLAHE varsayilan kapatildi.

**2. Cismin YONU eslesmeyi belirliyor**

SGBM eslesmeyi yatay tarama satirinda arar. Yatay bir kenar tarama
satiri boyunca uzanir; yatay kaydirinca goruntu ayni kalir, kayma
belirlenemez (aperture problem).

| Bolge | Ham eslesme orani |
|---|---|
| Dikey yapili | **%67.1** |
| Yatay yapili | %51.0 |

Ortalama 1.32x, en keskin karede 3.02x.

**3. Yansima zararli, GOLGE ZARARSIZ**

Sezgiye ters: golgeden kaciniriz saniriz. Sol-sag tutarlilik
kontrolu, 6 gercek cift:

| Bolge | Tutarsizlik | Orta tona gore |
|---|---|---|
| Koyu (golge) | %27.1 | 1.12x |
| **Parlak (yansima)** | **%58.7** | **2.44x** |

Golge yuzeye **yapisiktir** — iki kamera onu ayni fiziksel noktada
gorur, gecerli dokudur. Yansima **bakis acisina baglidir** — parlak
leke iki kamerada farkli noktada durur, SGBM lekeyi lekeye
eslestirip hayalet derinlik uretir.

**4. WLS "dolgulu %" bir kalite olcusu DEGIL**

WLS filtresi bosluklari **interpolasyonla** doldurur. Harita %100
dolu gorunurken buyuk kismi tahmin olabilir. Gercek olcut WLS
**oncesi** ham eslesme orani; kod bunu ayrica saklıyor.

*Gorsel:* `output/reports/sekil2_teorik_hata_egrisi.png`

---

### GUN E — Olcum: bes segmentasyon yontemi, ucu calisiyor
*(2026-08-19/20)*

**Problem:** Tiklanan piksel hangi cisme ait? Derinlik surekliligi
tek basina cismi masadan ayirmiyor — cismin masaya degdigi yerde
derinlik **sicramiyor**.

**Denenen bes yontem:**

| # | Yontem | Sonuc |
|---|---|---|
| 1 | Derinlik toleransi | Cisim goruntu duzlemine paralelse calisir |
| 2 | Parlaklik seviyesi | Kismen — cisme bagimli |
| 3 | Kenar + basamak engelleri | Kismen — kararlilik katiyor |
| 4 | Yukseklik kriteri | **Calisiyor** — duzlem gerekir |
| 5 | Watershed | **Calisiyor** — duzlem gerekmez |

**Referans olcum** (ayakta sise, tepeden bakis, gercek ~250 x 72 mm):

| Yontem | Sonuc |
|---|---|
| Derinlik toleransi (tol 15/30/60) | **65 / 83 / 158 mm** |
| Yukseklik kriteri (4 farkli ayar) | 248.4 / 247.4 / 247.7 / 247.0 |
| **Watershed (4 farkli ayar)** | **248.9 / 249.0 / 248.9 / 249.0** |

**1-3'un yapisal siniri (onemli):** Bir engel bolgeyi **buyutemez,
yalnizca kucultebilir**. Cisim bakis dogrultusunda uzaniyorsa bolge
zaten cismin ortasinda durur ve engel hic devreye girmez. Olculdu:
bolge gercek cismin **%25**'i, durdugu yerdeki derinlik basamagi
3.91 mm/px (yani kenar YOK), gercek siluette 48.57 mm/px.

**4 ve 5 neden calisiyor:** Yayilmiyorlar. Her piksel sabit bir
referansa karsi olculur, dolayisiyla ne erken durur ne kacar.

**Denendi ve calismadi — kenar duvarlarini floodFill'e vermek:**
Kenar ayrimi cok iyi (siluet |grad I| 108.3 vs cismin ici 5.7 —
19 kat). Ama duvarla cevrelemek **topolojik** bir sart: duvarin her
yerde kapali olmasi gerekiyor. Olculdu: siluetin en fazla **%86**'si
duvar oluyor, kalan %14'un tek pikselinden bolge kaciyor.

*Gorseller:*
`output/reports/basamak_neden_tutmadi.png`,
`output/reports/bolge_nerede_duruyor.png`

---

### GUN F — Dogrulama yontemi: sayiya degil GORSELE bakmak
*(2026-08-19)*

**Bu bolum raporun metodoloji acisindan en degerli kismi.**

**Yasanan hata:** Birden fazla aday bolge denendi ve sonuclar
termosun **bilinen olculerine yakinliga gore** puanlandi. En iyi
puanli 234 x 55 x 39 mm secilip "termos olculdu" diye sunuldu.
**Gercekte olculen sey masa kenariydi.**

**Ogrenilen:** Beklenen cevaba yakinlik, dogru seyi olctugunun
kaniti degildir. Yanlis bir bolge de tesadufen yakin sayi
uretebilir.

**Alinan onlem:** Her olcum icin olculen 3B kutu **goruntu uzerine
ciziliyor**. Kutu cismi sariyorsa olcum dogru, cevreye tasiyorsa
bolge kacmis. Her ana eksenin kenarlari ve sol ustteki olcusu ayni
renkte (UZUN yesil, ORTA acik mavi, KISA pembe) — hangi sayinin
hangi kenar oldugu tereddutsuz belli.

*Gorsel:* `output/reports/rapor_dogrulama_levhasi.png` **(rapora
mutlaka girmeli)**

---

### GUN G — Kalibrasyon deseninin kendisi bir hata kaynagi
*(2026-08-20)*

**Belirti:** Zemin duzlemi tespiti, tum metrikler temiz gorunmesine
ragmen gercek masadan 30-53 mm sapiyordu (96 kose, izdusum hatasi
0.34 px, bakis acisi 28.6 derece — hepsi iyi).

**Once yanlis teshis:** solvePnP'nin duz hedefteki poz belirsizligi
suclandi. **23 kayitli cekimde olculup curutuldu**: duzlemi
solvePnP yerine tahtanin stereo derinliginden uydurmak ayni sonucu
veriyor (medyan fark 3.4 mm / 0.60 derece).

**Gercek neden:** Tahta masaya duz yatiyor (olculdu: tahta ile
cevre masa duzlemleri arasi aci 0.22 derece, kalinlik 2.1 mm). Ama
tahtanin **uzerindeki derinlik** bozuk:

| | Bu cekim | Saglikli cekim |
|---|---|---|
| Tahtada mesafe dagilimi | **410 – 656 mm** | ~25 mm |
| Disparity salinimi | **37.4 px** | 8.9 px |
| Olculen kare boyu | 21.68 mm | 20.0 mm |

Duz bir tahtanin mesafesi 250 mm'lik bir aralikta saçilamaz.
**ChArUco periyodik bir desendir**; blok esleme bazi bloklarda
yanlis kareye kilitleniyor. Cevredeki duz beyaz masa temiz
olculuyor (kalinti 1.64 mm) — sorun yuzeyde degil desenin
periyodikliginde.

**Ogrenilen:** Kalibrasyon icin ideal olan desen (yuksek kontrastli,
tekrarli), stereo esleme icin **en kotu** durumdur. Ayni desen bir
adimda yardimci, digerinde zararli.

*Gorseller:*
`output/reports/tahta_derinlik_bozuk.png`,
`output/reports/duzlem_kim_hakli.png`

---

### GUN H — Kare olcusunun bagimsiz dogrulanmasi
*(2026-08-20)*

Tum mutlak olcumler `olculen_kare_boyutu_mm = 20.0` degerine
dayaniyor. Bu deger yanlissa **tum olcumler ayni oranda kayar** ve
bu hata sistem icinden fark edilemez.

**Dairesel olmayan kontrol:** Komsu ChArUco koselerinin **3B
mesafesi** olculdu — config'deki degeri hic kullanmadan.

| | Deger |
|---|---|
| 20 cekimde medyan | **20.05 mm** |
| Salinim | ±0.36 mm |
| Config | 20.00 mm |
| Oran | **1.0023 (+%0.2)** |

**Ogrenilen:** Bir sistemin kendi varsayimini kendi ciktisiyla
dogrulamasi dairesel olur. Bagimsiz bir yol bulmak gerekir.

---

### GUN I — Asil bulgu: sonucu belirleyen sey GEOMETRI
*(2026-08-20)*

Ayni kod, ayni ayarlar, farkli kamera yerlesimi. Referans cisim
termos, gercek 250 x 72 mm:

| Bakis | Mesafe | tol 15 / 30 / 60 → UZUN | Yayilim |
|---|---|---|---|
| **YANDAN, cisim dik** | 610 mm | **252.3 / 252.2 / 252.2** | **0.1 mm** |
| **YANDAN, cisim dik** | 609 mm | **256.8 / 256.8 / 256.8** | **0.0 mm** |
| **YANDAN, cisim dik** | 625 mm | **254.5 / 255.2 / 255.2** | **0.7 mm** |
| Tepeden, yatik | 561 mm | 270.9 / 290.5 / 310.1 | 39.2 mm |
| Tepeden, yatik | 718 mm | 177.8 / 204.7 / 264.6 | 86.8 mm |

**Asil kazanc dogruluk degil TOLERANSA DUYARSIZLIK.** Iyi
kurulumda sonuc parametre seciminden bagimsiz cikiyor; kotu
kurulumda ayni cisim icin 177 mm de yazilabilir 264 mm de.

**Kural (tek cumle):** Kamera cismin en buyuk yuzlerini gormeli.
**Kameraya dogru bakan eksen olculemeyen eksendir.**

**Neden:** Cisim bakis dogrultusunda uzaniyorsa, tabandan tepeye
derinlik surekli degisir ve derinlik toleransi cismin ancak bir
dilimini kapsar.

**Ikinci etken — mesafe:** Derinlik hassasiyeti mesafenin
**karesiyle** kotulesir:

| Z | 1 px derinlik hatasi |
|---|---|
| 400 mm | 1.57 mm |
| 550 mm | 2.97 mm |
| 718 mm | 5.06 mm |
| 1000 mm | 9.82 mm |

**Uygulamaya eklenen onlem:** "Kurulum kontrolu" butonu, sahnenin
baskin duzlemini canli derinlikten bulup bakis acisini olcuyor.
Olculdu: yandan 75-80 derece, tepeden 16-29 derece — arada 46
derecelik bosluk. Bes gercek cekimde 5/5 dogru karar verdi.

*Gorsel:* `output/reports/rapor_dogrulama_levhasi.png`

---

### GUN J — Gurultu darbogaz degil, segmentasyon darbogaz
*(2026-08-20)*

Sistemin ne kadar hassas oldugu dogrudan olculdu: 46 adet 120x120
piksellik **duz masa yamasinda** yerel duzlemsel sacilim.

| | Deger |
|---|---|
| Medyan sacilim | **1.15 mm** |
| Disparity karsiligi | 0.44 px |
| Bagimsiz olculen epipolar hata | 0.420 px |

Iki bagimsiz olcum ayni sayiyi veriyor — sistem tutarli.

**Ama gordugumuz olcum hatalari 30-60 mm**, yani sensor
gurultusunun **30-50 kati**. Darbogaz sensor ya da kalibrasyon
degil, **"hangi piksel cisme ait" karari**.

**Bunun pratik sonucu:** Baz uzunlugunu buyutmek ya da daha iyi
kalibrasyon yapmak bu projede **anlamli kazanc getirmez**. Cabayi
segmentasyona ve kamera yerlesimine harcamak gerekir.

Gurultunun yone gore dagilimi (oran = Z / B):

| Z | Yanal | Derinlik | Oran |
|---|---|---|---|
| 400 mm | 0.28 mm | 1.57 mm | 5.6x |
| 550 mm | 0.39 mm | 2.97 mm | 7.7x |
| 1000 mm | 0.71 mm | 9.82 mm | 13.9x |

---

## 3. SONUCLAR (rapor bolum 5)

### Basarilan

| Hedef | Sonuc |
|---|---|
| Calisan uctan uca pipeline | Yakalama → kalibrasyon → derinlik → olcum → kutu onerisi |
| Kalibrasyon dogrulugu | Epipolar hata **0.420 px** |
| Olcek dogrulamasi | Kare olcusu bagimsiz olculdu: 20.05 vs 20.00 mm |
| Sistem gurultusu | **1.15 mm** (iki bagimsiz yontemle tutarli) |
| En iyi kurulumda dogruluk | Uzun kenarda **%0.9 – 2.7** hata |
| Tekrarlanabilirlik (on veri) | Ayni cisme iki tiklama: 204.7 / 202.1 mm (fark %1.3) |
| Parametre duyarsizligi | Iyi kurulumda tolerans yayilimi **0.0 – 0.7 mm** |

### Ana sonuc tablosu

| Bakis | Mesafe | Gercek UZUN | Olculen | Hata |
|---|---|---|---|---|
| Yandan | 610 mm | 250 mm | 252.2 mm | **+%0.9** |
| Yandan | 609 mm | 250 mm | 256.8 mm | +%2.7 |
| Yandan | 625 mm | 250 mm | 255.2 mm | +%2.1 |
| Tepeden | 561 mm | 250 mm | 290.5 mm | +%16.2 |
| Tepeden | 718 mm | 250 mm | 204.7 mm | −%18.1 |

### YAPILAMAYANLAR — raporda acikca yazilacak

| Konu | Durum |
|---|---|
| Fiziksel kutu kesimi ile dogrulama | **Yapilmadi** — sure yetmedi |
| Cok cisimli sonuc tablosu | Yalnizca 1 cisim (termos); 5 hedeflenmisti |
| Tekrarlanabilirlik testi | 1 veri noktasi; 10 olcum hedeflenmisti |
| Kalibrasyon kalitesinin etkisi | Olculmedi |
| Zemin duzlemi kararliligi | **Cozulmedi** — ChArUco'nun periyodik deseni yuzunden duzlem 30-57 mm sapabiliyor |
| Yuvarlak cisimlerde en kisa eksen | Tek bakis acisindan yalnizca on yay goruldugu icin eksik olculuyor |

**Cowork icin not:** Bu tabloyu kucultme ya da yumusatma. Bir staj
raporunda sinirlarin acikca yazilmasi, olmayan sonucu var
gostermekten degerlidir.

### Kazanimlar (metodolojik)

1. **Bir uyum olcutunu iyilestirmek icin veri secmek olcutu yok
   eder.** RMS dustu ama epipolar hata artti.
2. **Beklenen cevaba yakinlik dogrulama degildir.** Bu hata bir kez
   masa kenarini termos diye raporlatti.
3. **Bir sistem kendi varsayimini kendi ciktisiyla
   dogrulayamaz** — bagimsiz yol gerekir (kare olcusu).
4. **Bir adimda ideal olan, digerinde zararli olabilir** — ChArUco
   kalibrasyon icin en iyi desen, stereo esleme icin en kotu.
5. **Darbogazi olcmeden optimize etme.** Gurultu 1.15 mm iken
   hatalar 30-60 mm'ydi; sorun baska yerdeydi.
6. **Sezgi olcume yenilir.** CLAHE, golge ve tepeden bakis —
   ucunde de beklentimiz yanlis cikti.

---

## 4. GORSEL LISTESI

> Dosya yollari proje kokune gore. Cowork bunlari docx'e
> gomecek ve "Sekil N" numaralarini rapordaki siraya gore verecek.

### Mutlaka girmeli

| Dosya | Ne gosteriyor | Hangi bolum |
|---|---|---|
| `output/reports/rapor_dogrulama_levhasi.png` | Bes olcum, kutu cismi sariyor mu | Gun F / Sonuclar |
| `output/reports/sekil1_akis_semasi.png` | Sistem akis semasi | Bolum 3 |
| `output/reports/tahta_derinlik_bozuk.png` | Tahtada bozuk derinlik | Gun G |
| `output/reports/basamak_neden_tutmadi.png` | Bolge cismin ortasinda duruyor | Gun E |

### Isterse girer

| Dosya | Ne gosteriyor |
|---|---|
| `output/reports/sekil2_teorik_hata_egrisi.png` | Mesafeye gore hata |
| `output/reports/sekil3_rms_iyilesme.png` | Kalibrasyon RMS |
| `output/reports/sekil4_kose_hata_analizi.png` | Kose hatasi dagilimi |
| `output/reports/duzlem_kim_hakli.png` | Iki duzlem karsilastirmasi |
| `output/reports/bolge_nerede_duruyor.png` | Segmentasyonun durdugu yer |
| `patterns/charuco_board.png` | Kalibrasyon deseni |
| `output/depth_captures/*_overlay.png` | Ornek derinlik ciktisi (290 adet arasindan secilir) |
| `output/depth_captures/*_kutu_*.png` | Tekil kutu gorselleri (56 adet) |

**Ekran goruntusu gereken (Nevfel alacak):** uygulamanin arayuzu —
Olcum ve Derinlik sekmeleri.

---

## 5. VERI DOSYALARI

Sayilari elle kopyalamak yerine bu dosyalardan alin; hepsi
`src/rapor_verisi.py` ile **yeniden uretilebilir**:

| Dosya | Icerik |
|---|---|
| `output/reports/rapor_tablolari.md` | Hazir markdown tablolar |
| `output/reports/rapor_olcumler.csv` | Her olcum + hata yuzdesi |
| `output/reports/rapor_duyarlilik.csv` | Tolerans taramasi |
| `output/reports/rapor_sistem.csv` | Sistem parametreleri |
| `output/reports/rapor_elenenler.csv` | Degerlendirmeye alinmayanlar + neden |

**Onemli:** `rapor_elenenler.csv`'deki satirlar raporda da
belirtilmeli. Hicbiri "sonucu yanlis" diye elenmedi; gerekceler
girdi kalitesi (yanlis tiklama, cisim yarim, cisimler ic ice).

---

## 6. KAYNAKLAR (rapor sonu icin)

- OpenCV dokumantasyonu — `calib3d`, `ximgproc` modulleri
- Hirschmüller, H. — Semi-Global Matching (SGBM algoritmasinin temeli)
- Zhang, Z. — A Flexible New Technique for Camera Calibration
- OpenCV ArUco/ChArUco dokumantasyonu
- calib.io — kalibrasyon deseni ureteci

---

## 7. COWORK ICIN YAZIM NOTLARI

1. **Kisi:** Birinci tekil gecmis zaman ("gelistirdim", "olctum") —
   ornek raporla ayni.
2. **Sayilar:** Her teknik iddianin yaninda olculen deger olsun.
   Sayisiz cumle yazma.
3. **Hatalar:** "Sorunla karsilasildi ve cozuldu" degil; **ne
   bekledigimiz, ne ciktigi, nedenini nasil buldugumuz** anlatilsin.
4. **Uzunluk:** Bu proje icin ~8 sayfa. Gun bolumleri 1-2 paragraf +
   tablo/gorsel.
5. **Ton:** Abartisiz. "Sistem %0.9 hata ile olcuyor" degil,
   "en iyi kurulumda uzun kenarda %0.9 hata olculdu; kotu
   kurulumda ayni sistem %18 sapiyor" — kosul her zaman yazili.
6. **Birlestirme:** Diger projeyle birlestirilirken gun numaralari
   yeniden verilecek. Bu projenin gunleri A-J olarak isaretlendi ki
   karismasin.
