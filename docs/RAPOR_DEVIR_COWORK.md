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

> **Cowork: iki alternatif kurgu var. A tavsiye edilen.**
> Hangisini secersen sec, icerik ayni; degisen sey sira ve baslik.

### KURGU A — KRONOLOJIK (ornek rapordaki gibi) — TAVSIYE EDILEN

Ornek rapor gun gun ilerliyor ve **ihtiyac analizi + planlama** ile
basliyor. Bizde de o asama gercekten yasandi (donanim eline gecmeden
once teorik calisma zarfi hesaplandi), o yuzden ayni sirayi
izleyebiliriz. Okuyucu projeyi bastan kurulusuyla goruyor.

| Gun | Baslik |
|---|---|
| 1 | Ihtiyac analizi, gizlilik kisiti ve bagimsiz prototip karari |
| 2 | Teorik sistem planlamasi — calisma zarfinin hesaplanmasi |
| 3 | Donanim kurulumu ve kamera test aracinin gelistirilmesi |
| 4 | Iki kamera arasindaki dengesizlik: uc yanlis teshis |
| 5 | Stereo kalibrasyon ve "RMS iyi ise kalibrasyon iyidir" yanilgisi |
| 6 | Derinlik haritasi: sezgiye ters cikan uc olcum |
| 7 | Nesne olcum hattinin kurulmasi ve segmentasyon denemeleri |
| 8 | Dogrulama yonteminin degistirilmesi — sayidan gorsele |
| 9 | Kalibrasyon deseninin kendisinin hata kaynagi olmasi |
| 10 | Olcek dogrulamasi ve asil bulgu: geometrinin belirleyiciligi |

### KURGU B — KONU BAZLI (alternatif)

Gun sirasi yerine alt sisteme gore gruplamak. Avantaji: teknik
butunluk daha net. Dezavantaji: ornek rapordan uzaklasir ve "gunluk
staj calismalari" basligina tam oturmaz.

| Bolum | Icerik |
|---|---|
| 4.1 | Planlama ve teorik tasarim |
| 4.2 | Donanim karakterizasyonu ve kamera esitleme |
| 4.3 | Kalibrasyon ve dogruluk olcutleri |
| 4.4 | Derinlik haritasi uretimi ve on-isleme |
| 4.5 | Nesne segmentasyonu ve boyut cikarma |
| 4.6 | Dogrulama metodolojisi |
| 4.7 | Sistem sinirlarinin belirlenmesi |

---

> Asagidaki icerik **Kurgu A**'ya gore siralandi. Kurgu B secilirse
> ayni bloklar yukaridaki basliklara dagitilir.

---

### GUN 1 — Ihtiyac analizi, gizlilik kisiti ve bagimsiz prototip karari

**Baglam:** Stajin yurutuldugu kurumda gizlilik sozlesmesi var; sirket
kodu ve verisi raporda kullanilamiyor. Bolumun staj bilgilendirmesinde
bu durum icin oneri var: ogrenci **kendi donanimi ve verisiyle**
ayni teknik yetkinligi gosteren bagimsiz bir prototip gelistirebilir.

Bu dogrultuda, ayni goruntu isleme yetkinligini gosterecek bagimsiz
bir problem secildi: **iki kamerayla bir cismin 3B boyutlarini olcmek
ve uygun kargo kutusunu onermek.**

**Sistem iki bacakli kurgulandi:**
1. Olcum hatti — kalibrasyon, derinlik haritasi, boyut cikarma
2. Cikti hatti — standart kutu esleme, desi hesabi, kesim yonergesi

**Bu gunun asil kazanimi:** Bir problemi cozmeye baslamadan once
**neyin dogrulanabilir olacagina** karar vermek. Projenin en basinda
"her adim bagimsiz bir olcumle sinanacak" kurali konuldu; rapordaki
sayilarin tamami bu kurala dayaniyor.

*Gorsel onerisi:* sistem akis semasi
(`output/reports/sekil1_akis_semasi.png`)

---

### GUN 2 — Teorik sistem planlamasi: calisma zarfinin hesaplanmasi

**Yapilan:** Donanim kurulmadan once, stereo geometrinin temel
bagintilariyla sistemin **nerede calisabilecegi** hesaplandi. Amac,
deneme-yanilmayla zaman kaybetmek yerine beklentiyi onceden
sayilastirmakti.

**Kullanilan bagintilar:**

```
Z = f · B / d                 (mesafe)
ΔZ = Z² · Δd / (f · B)        (derinlik belirsizligi)
```

`Z` mesafe, `f` odak uzakligi (piksel), `B` iki kamera arasi
uzaklik (baz), `d` disparity.

**Kritik cikarim:** Derinlik belirsizligi mesafenin **karesiyle**
buyuyor. Yani sistemi 2 kat uzaga kurmak hatayi 2 degil **4 kat**
artiriyor.

**Hesaplanan calisma zarfi** (planlama degerleriyle: f ≈ 914 px,
B = 60 mm):

| Mesafe | Derinlik belirsizligi | Durum |
|---|---|---|
| 250 mm | 0.57 mm | Cisim goruse sigmiyor |
| 350 mm | 1.12 mm | Uygun |
| **450 mm** | **1.85 mm** | **Uygun** |
| 550 mm | 2.76 mm | Uygun |
| 700 mm | 4.47 mm | Dogruluk yetersiz |
| 1000 mm | 9.11 mm | Dogruluk yetersiz |

**Sonuc:** Calisma bandi **350–550 mm** olarak planlandi. Bu tahmin
projenin sonunda gercek olcumlerle karsilastirilacak (bkz. Gun 10) —
teorinin ne kadar tuttugu raporun dogrulama bolumunun bir parcasi.

**Ogrenilen:** Bir sistemin sinirini olcmeden once **hesaplayabilmek**,
hangi denemenin anlamli oldugunu bastan belirliyor.

---

### GUN 3 — Donanim kurulumu ve kamera test aracinin gelistirilmesi

**Yapilan:** Iki USB kamera modulu 3B basilmis govdeye sabitlendi.
Ikisini ayni anda yonetebilmek icin Python/Tkinter tabanli bir test
araci yazildi: es zamanli goruntu yakalama, manuel pozlama/gain/beyaz
dengesi kilitleme, netlik skoru, kalibrasyon karesi toplama.

**Neden ayri bir arac:** Stereo calismada iki kameranin **ayni anda**
kare vermesi sart. Kameralari sirayla okumak aralarina kod cozme
suresi koyuyor; cisim ya da kamera hareket ederse disparity kayiyor.
Bu yuzden once ikisine "kareyi yakala" (`grab`), sonra "kareyi coz"
(`retrieve`) denmesi gerekiyor.

**Karsilasilan sorun — surucu arayuzu:** Ilk secilen DSHOW arayuzunde
bazi kamera ayarlari (beyaz dengesi, pozlama) iki kamerada tutarsiz
uygulaniyordu. MSMF arayuzune gecildi.

**Olculen — kullanilabilir pozlama bandi:** Pozlama degerleri tarandi
ve her degerde **gercek kare parlakligi** olculdu:

| Pozlama | SOL / SAG parlaklik | Durum |
|---|---|---|
| −2 | 245 / 245 | Doymus — doku kalmiyor |
| −3 | 223 / 219 | Sinirda |
| **−5** | **104 / 150** | Kullanilabilir |
| −7 | 15 / 6 | Cok karanlik |

**Ogrenilen:** Asiri parlak (doymus) goruntude piksel degerleri
tavana yapisip **doku kayboluyor**; esleme algoritmasi tutunacak
yapi bulamiyor. "Aydinlik goruntu iyi goruntudur" varsayimi stereo
icin gecerli degil.

*Gorsel onerisi:* uygulama arayuzu ekran goruntusu (Nevfel alacak)

---

### GUN 4 — Iki kamera arasindaki dengesizlik: uc yanlis teshis

**Bu gun bir hata avina gitti ve raporun en ogretici bolumlerinden.**

**Belirti:** Iki kamera ayni sahneye bakarken belirgin farkli goruntu
veriyordu — parlaklik orani **2.7 kat**. Stereo esleme iki goruntunun
benzer olmasina dayandigi icin bu dogrudan olcumu bozuyor.

**Sirayla suclanan ve olcumle YANLIS cikan nedenler:**
1. Lens diyaframlarinin farkli olmasi
2. Sensorlerin duyarlilik farki
3. Lenslerden birinde koruyucu film kalmis olmasi

**Gercek neden:** Kamera ayarlarini yazan fonksiyon, 11 ozellikten
yalnizca 8'ini yaziyordu — **GAMMA, HUE ve BACKLIGHT hic
yazilmiyordu**. Bu ozellikler kameranin kendi hafizasinda **kalici**
saklandigi icin gecmiste yazilmis degerler oylece kaliyordu. Olculdu:
sol kamerada GAMMA 200, sagda 100.

**Kanit — 11 ozelligin tamami ayni degere yazildiginda:**

| Pozlama | SOL | SAG | Oran |
|---|---|---|---|
| −5 | 72.0 | 71.1 | 1.01x |
| **−4** | **120.0** | **120.5** | **1.00x** |
| −3 | 170.2 | 173.3 | 1.02x |

2.7 katlik farkin **tamami ayar kaynakliymis**; donanimsal degil.

**Ikinci bulgu — ayar geri okumasi guvenilmez:** Surucu arayuzu, hangi
deger yazilirsa yazilsin geri okumada ayni sayiyi donduruyordu; ama
ayar **gercekte uygulaniyordu** (kare parlakligi olculunce goruluyor).
Bu yuzden koda "ayari geri oku ve dogrula" mantigi yazilmadi.

**Ogrenilen:** Bir cihazin kendi raporu dogrulama sayilmaz. Dogrulama
**cihazin urettigi veriden** yapilmali. Ayrica: bir sistemde
"yazilmayan" bir ayar, sifirlanmis degil **eski degerinde kalmis**
demektir.

---

### GUN 5 — Stereo kalibrasyon ve "RMS iyi ise kalibrasyon iyidir" yanilgisi

**Yapilan:** ChArUco deseni (9x13 kare) ile 44 kare cift toplanip
stereo kalibrasyon yapildi.

**Neden ChArUco:** Duz satranc tahtasinda desen kismen gorunurse
tespit basarisiz olur. ChArUco'da her kareye bir isaret gomulu
oldugu icin desenin bir kismi gorunse bile calisir; kose konumlari
ise satranc kesisimlerinden **alt-piksel** hassasiyetle bulunur.

**Sonuclar:**

| Olcut | Deger |
|---|---|
| Stereo RMS | 0.8340 px |
| Tekli RMS (sol / sag) | 0.7703 / 0.7682 px |
| Baz uzunlugu (olculdu) | 71.79 mm |
| Odak uzakligi (rektifiye) | 1418.18 px |

**METODOLOJIK BULGU — raporda one cikarilmali:** RMS degerini
dusurmek icin "kotu" gorunen kareler veri setinden atildi. RMS
gercekten dustu — **ama epipolar hata kotulesti.**

RMS, modelin **kendi verisine** ne kadar uydugunu olcer. Veriden
zor ornekleri atmak, modeli iyilestirmez; yalnizca sinavi
kolaylastirir.

Gercek kalite olcutu **epipolar hata**: rektifikasyondan sonra ayni
noktanin iki goruntude ayni satirda cikip cikmadigi. 44 cift / 3264
kose uzerinde olculdu: **0.420 piksel**.

**Ogrenilen:** Bir uyum olcutunu iyilestirmek icin veri secmek, o
olcutun anlamini yok eder. Bagimsiz bir olcut sart.

**Ikinci bulgu — iki farkli odak uzunlugu var, karistirilmamali:**

| Deger | Kaynak | Nerede kullanilir |
|---|---|---|
| 1288.28 px | Ham kamera matrisi | Ham goruntu geometrisi |
| **1418.18 px** | Rektifiye projeksiyon | **Mesafe hesabi** |

Disparity rektifiye edilmis goruntude olculdugu icin mesafe
formulunde ikincisi kullanilmali. Bu ayrim atlanirsa tum mesafeler
%9 sapar.

*Gorseller:* `output/reports/sekil3_rms_iyilesme.png`,
`output/reports/sekil4_kose_hata_analizi.png`,
`patterns/charuco_board.png`

---

### GUN 6 — Derinlik haritasi: sezgiye ters cikan uc olcum

Derinlik haritasi SGBM algoritmasi ve WLS filtresiyle uretiliyor.
Bu asamada uc beklenti olcumle yanlislandi.

**1. Kontrast artirmak haritayi BOZUYOR**

Beklenti: kontrast artarsa esleme kolaylasir. Olculen (6 gercek
stereo cift, ayni veri, farkli on-isleme):

| Konfigurasyon | Ortalama sicrama | %2'den buyuk sicrama |
|---|---|---|
| **Kontrast artirma yok** | **0.361** | **%1.5** |
| CLAHE 1.0 | 0.399 | %1.9 |
| CLAHE 2.0 | 0.419 | %2.1 |

Neden: duz ve dokusuz yuzeylerde (duvar, masa) kontrast artirmanin
yukselttigi sey **sensor gurultusu**. Algoritma bunu gercek doku
sanip sahte eslesme uretiyor. Ozellik varsayilan olarak kapatildi.

**2. Cismin YONU eslesmeyi belirliyor**

Algoritma eslesmeyi yatay tarama satirinda arar. Yatay bir kenar bu
satir boyunca uzanir; yatay kaydirinca goruntu ayni kalir ve kayma
belirlenemez. (Goruntu islemede *aperture problem* olarak bilinir.)

| Bolge | Ham eslesme orani |
|---|---|
| Dikey yapili | **%67.1** |
| Yatay yapili | %51.0 |

Ortalama 1.32 kat, en keskin karede 3.02 kat fark.

**3. Yansima zararli, GOLGE ZARARSIZ**

Sezgi golgeden kacinmayi soyler. Olculen tam tersi:

| Bolge | Sol-sag tutarsizlik | Orta tona gore |
|---|---|---|
| Koyu (golge) | %27.1 | 1.12x |
| **Parlak (yansima)** | **%58.7** | **2.44x** |

Golge yuzeye **yapisiktir** — iki kamera onu ayni fiziksel noktada
gorur, dolayisiyla gecerli bir dokudur ve eslesmeye yardim eder.
Yansima ise **bakis acisina baglidir** — parlak leke iki kamerada
farkli fiziksel noktada durur, algoritma lekeyi lekeye eslestirip
hayalet derinlik uretir.

**4. Filtrenin "doluluk" orani kalite olcusu DEGIL**

WLS filtresi bosluklari **komsulardan tahmin ederek** doldurur.
Harita %100 dolu gorunurken buyuk kismi tahmin olabilir. Bu yuzden
kod, filtreden **once** gercekten eslesen piksellerin oranini ayrica
sakliyor; guvenilirlik degerlendirmesi o sayiya bakiyor.

**Ogrenilen:** Bir ciktinin "tam" gorunmesi, dogru oldugu anlamina
gelmiyor. Ara asamayi saklamak, sonucun ne kadarinin olcum ne
kadarinin tahmin oldugunu ayirt etmeyi sagliyor.

*Gorsel:* ornek derinlik ciktisi
(`output/depth_captures/*_derinlik.png` arasindan secilecek)

---

### GUN 7 — Nesne olcum hattinin kurulmasi ve segmentasyon denemeleri

**Problem:** Kullanici bir noktaya tikliyor; o noktanin ait oldugu
cismin sinirlari nasil bulunacak?

Ilk yaklasim derinlik surekliligiydi: tiklanan noktadan baslayip
benzer derinlikteki komsulara yayilmak. **Calismadi** — cunku cismin
masaya degdigi yerde derinlik **sicramiyor**; bolge kesintisiz masaya
akiyor.

**Denenen bes yontem:**

| # | Yontem | Sonuc |
|---|---|---|
| 1 | Derinlik toleransi | Cisim goruntu duzlemine paralelse calisiyor |
| 2 | Parlaklik seviyesi | Kismen — cismin rengine bagimli |
| 3 | Kenar/basamak engelleri | Kismen — kararlilik katiyor |
| 4 | Duzlemden yukseklik | **Calisiyor** — zemin duzlemi gerekiyor |
| 5 | Watershed | **Calisiyor** — zemin duzlemi gerekmiyor |

**Referans olcum** (ayakta duran sise, tepeden bakis, gercek ~250 mm):

| Yontem | Sonuc (uc farkli ayarla) |
|---|---|
| Derinlik toleransi | **65 / 83 / 158 mm** |
| Duzlemden yukseklik | 248.4 / 247.4 / 247.7 mm |
| **Watershed** | **248.9 / 249.0 / 248.9 mm** |

**1-3'un yapisal siniri:** Bir engel bolgeyi **buyutemez, yalnizca
kucultebilir**. Cisim bakis dogrultusunda uzaniyorsa bolge zaten
cismin ortasinda duruyor ve engel hic devreye girmiyor. Olculdu:
bolge gercek cismin **%25**'i; durdugu yerdeki derinlik degisimi
3.91 mm/piksel (yani orada kenar YOK), gercek cisim sinirinda ise
48.57 mm/piksel.

**4 ve 5 neden calisiyor:** Yayilmiyorlar. Her piksel **sabit bir
referansa** karsi olculuyor, dolayisiyla bolge ne erken duruyor ne
de kaciyor.

**Ogrenilen:** Yayilarak calisan bir kriterin capasi yoktur; ya erken
durur ya kacar. Mutlak bir referans, kademeli bir kuraldan daha
guvenilir.

*Gorseller:* `output/reports/basamak_neden_tutmadi.png`,
`output/reports/bolge_nerede_duruyor.png`

---

### GUN 8 — Dogrulama yonteminin degistirilmesi: sayidan gorsele

**Bu bolum raporun metodoloji acisindan en degerli kismi.**

**Yasanan hata:** Birden fazla aday bolge denendi ve sonuclar test
cisminin **bilinen olculerine yakinliga gore** puanlandi. En iyi
puanli 234 x 55 x 39 mm secilip "cisim olculdu" diye kaydedildi.
Sonradan goruldu ki **olculen sey masanin kenariydi** — tesadufen
benzer sayilar uretmisti.

**Ogrenilen:** Beklenen cevaba yakinlik, **dogru seyi olctugunun
kaniti degildir.** Yanlis bir bolge de tesadufen makul sayi
uretebilir. Bu, olcum yapan her sistemde gecerli bir tuzak.

**Alinan onlem:** Her olcum icin hesaplanan 3B kutu **goruntu
uzerine ciziliyor.** Kutu cismi sariyorsa olcum dogru; cevreye
tasiyorsa bolge kacmis demektir. Her boyutun kenarlari ve kosedeki
sayisi ayni renkte (uzun kenar yesil, orta acik mavi, kisa pembe) —
hangi sayinin hangi kenar oldugu tereddutsuz belli oluyor.

Bu tarihten sonra hicbir olcum yalnizca sayiya bakilarak kabul
edilmedi.

*Gorsel:* `output/reports/rapor_dogrulama_levhasi.png`
**(rapora mutlaka girmeli)**

---

### GUN 9 — Kalibrasyon deseninin kendisinin hata kaynagi olmasi

**Belirti:** Zemin duzlemi tespiti, tum gostergeler temiz gorunmesine
ragmen gercek masa yuzeyinden 30–53 mm sapiyordu. Tespit metrikleri
iyiydi: 96 kose bulunmus, yeniden izdusum hatasi 0.34 piksel.

**Once yanlis teshis:** Duz bir hedefte poz cozumunun iki matematiksel
karsiliginin olmasi (planar pose ambiguity) suclandi. **23 kayitli
cekim uzerinde olculup curutuldu** — duzlemi bu yontem yerine
tahtanin stereo derinliginden hesaplamak ayni sonucu veriyor
(medyan fark 3.4 mm / 0.60 derece).

**Gercek neden:** Tahta masaya duz yatiyor (olculdu: tahta ile cevre
masa duzlemleri arasinda 0.22 derece, kalinlik 2.1 mm). Sorun
tahtanin **uzerindeki derinlik olcumunde**:

| | Bu cekim | Saglikli cekim |
|---|---|---|
| Tahtada mesafe dagilimi | **410 – 656 mm** | ~25 mm |
| Disparity salinimi | **37.4 px** | 8.9 px |
| Hesaplanan kare boyu | 21.68 mm | 20.0 mm |

Duz bir tahtanin mesafesi 250 mm'lik bir aralikta saçilamaz.
**ChArUco periyodik bir desendir** — birbirinin ayni kareler
tekrarliyor. Blok esleme bazi bolgelerde **yanlis kareye
kilitleniyor.** Cevredeki duz beyaz masa temiz olculuyor (sapma
1.64 mm), yani sorun yuzeyde degil desenin tekrarliliginda.

**Ogrenilen:** Kalibrasyon icin ideal olan desen — yuksek kontrastli,
duzenli tekrarli — stereo esleme icin **en kotu** durumdur. Ayni
nesne bir adimda vazgecilmez, digerinde zararli. Bir bileseni
"iyi/kotu" diye degil, **hangi adimda ne yaptigina** gore
degerlendirmek gerekiyor.

*Gorseller:* `output/reports/tahta_derinlik_bozuk.png`,
`output/reports/duzlem_kim_hakli.png`

---

### GUN 10 — Olcek dogrulamasi ve asil bulgu: geometrinin belirleyiciligi

**Bolum 1 — Olcegin bagimsiz dogrulanmasi**

Sistemdeki tum mutlak olcumler, kalibrasyon deseninin kare boyu
degerine (20.0 mm) dayaniyor. Bu deger yanlissa **tum olcumler ayni
oranda kayar** ve bu hata sistemin kendi icinden fark edilemez.

Dairesel olmayan bir kontrol kuruldu: komsu desen koselerinin **3B
uzayda birbirine uzakligi** olculdu — kayitli kare boyu degeri hic
kullanilmadan.

| | Deger |
|---|---|
| 20 cekimde medyan | **20.05 mm** |
| Salinim | ±0.36 mm |
| Kayitli deger | 20.00 mm |
| Oran | **1.0023 (+%0.2)** |

**Ogrenilen:** Bir sistem kendi varsayimini kendi ciktisiyla
dogrulayamaz. Bagimsiz bir yol bulunmali.

**Bolum 2 — Gurultu darbogaz degil**

Sistemin ne kadar hassas oldugu dogrudan olculdu: 46 adet duz masa
yamasinda yerel sacilim **1.15 mm**. Bu deger, bagimsiz olculen
epipolar hatayla (0.420 piksel) tutarli.

Ama gorulen olcum hatalari **30–60 mm** — sensor gurultusunun 30-50
kati. Yani darbogaz sensor ya da kalibrasyon degil, **"hangi piksel
cisme ait" karari**.

**Pratik sonuc:** Daha uzun baz ya da daha iyi kalibrasyon bu
projede anlamli kazanc getirmez. Caba segmentasyona ve kamera
yerlesimine harcanmali.

**Bolum 3 — Asil bulgu: sonucu belirleyen sey GEOMETRI**

Ayni kod, ayni ayarlar, yalnizca kamera yerlesimi farkli. Referans
cisim 250 x 72 mm:

| Bakis | Mesafe | Uc farkli ayarla sonuc | Yayilim |
|---|---|---|---|
| **Yandan, cisim dik** | 610 mm | **252.3 / 252.2 / 252.2** | **0.1 mm** |
| **Yandan, cisim dik** | 609 mm | **256.8 / 256.8 / 256.8** | **0.0 mm** |
| **Yandan, cisim dik** | 625 mm | **254.5 / 255.2 / 255.2** | **0.7 mm** |
| Tepeden, yatik | 561 mm | 270.9 / 290.5 / 310.1 | 39.2 mm |
| Tepeden, yatik | 718 mm | 177.8 / 204.7 / 264.6 | 86.8 mm |

**Asil kazanc dogruluk degil, PARAMETREYE DUYARSIZLIK.** Iyi
yerlesimde sonuc ayar seciminden bagimsiz cikiyor. Kotu yerlesimde
ayni cisim icin 177 mm de yazilabilir 264 mm de — yani tek bir sayi
olarak raporlanamaz.

**Kural (tek cumle):** Kamera cismin en buyuk yuzlerini gormeli.
**Kameraya dogru bakan eksen, olculemeyen eksendir.**

**Teorik tahminle karsilastirma (Gun 2'ye donus):** Planlamada
calisma bandi 350–550 mm hesaplanmisti. Gercek olcumlerde en iyi
sonuclar **550–650 mm** bandinda alindi. Teori dogru yonu
gostermis; sapma, planlamada varsayilan baz (60 mm) ile gercek
bazin (71.79 mm) farkindan geliyor — daha uzun baz, kullanilabilir
bandi bir miktar uzaga kaydiriyor.

**Uygulamaya eklenen onlem:** "Kurulum kontrolu" islevi, sahnedeki
baskin duzlemi canli derinlikten bulup bakis acisini olcuyor.
Olculdu: yandan bakista 75–80 derece, tepeden 16–29 derece — arada
46 derecelik bosluk. Bes gercek cekimde 5/5 dogru karar verdi. Boylece
kullanici olcum almadan once kurulumun uygun olup olmadigini
goruyor.

*Gorsel:* `output/reports/rapor_dogrulama_levhasi.png`

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
