# Staj Raporu — Stereo Kamera Projesi Bolumu

> **Bu dosya rapora YAPISTIRILMAYA HAZIR metindir.**
> Resmi sablonun (`20032023143940_Icerik_D_452`) numaralandirma,
> atif ve sekil altyazi kurallarina gore yazildi.
>
> **Bolum numaralari 4'ten basliyor** — 1-3 arasi giris, kurum
> tanimi ve birinci proje icin ayrilmistir. Diger proje eklendikten
> sonra numaralar kaydirilirsa metin icindeki "Bolum 4.2" gibi
> atiflar da guncellenmeli.
>
> **Sekil numaralari 1'den basliyor** — birinci projede kac sekil
> varsa o kadar kaydirilmali. Metin icindeki her "Sekil N" atfi da
> ayni miktarda kaydirilacak.

---

## SABLON KURALLARI (Word'de uygulanacak)

| Ogo | Bicim |
|---|---|
| Bolum basligi | 14 punto, **kalin**, BUYUK HARF, sirali numarali |
| Alt bolum | 12 punto, **kalin**, sirali numarali |
| Alt alt bolum | Normal metin boyutu, **kalin**, numarasiz, onunde ve arkasinda bir satir bosluk |
| Govde metni | 11 punto, normal, 1.15 satir araligi |
| Sekil/cizelge altyazisi | 11 punto, **kalin**, siyah |
| Sekiller | Satir ortalanmis, metne gomulu DEGIL |
| Sayfa altligi | Ogrenci ad-soyad ve numara |
| Atif | Kose parantez `[1]`, atif sirasina gore numarali |

Her sekil ve cizelge metin icinde **alintilanmali** — "Sekil 5'te
gosterilmektedir" gibi. Asagidaki metinde bu atiflar zaten yazili.

---

# 4. STEREO KAMERA ILE BOYUTSAL OLCUM SISTEMI

Stajin ikinci bolumunde, iki kameradan alinan goruntu cifti
uzerinden bir cismin uc boyutlu olculerini hesaplayan bir sistem
gelistirdim. Calismanin cikti hedefi, olculen boyuta uygun standart
kargo kutusunu secmek ve gerekirse kesim sablonu uretmekti.

Projeyi bir urun gelistirme isi olarak degil, bir **olcum dogrulama
calismasi** olarak kurguladim. Bu ayrim raporun geri kalanini
belirledi: her adimin ciktisi, o adimdan bagimsiz bir yontemle
sinandi. Asagidaki bolumlerde hem calisan cozumler hem de
**calismayan denemeler ve nedenleri** yer aliyor; ikincisi bu
calismada birincisinden daha ogretici oldu.

## 4.1. Problemin Tanimi ve Sistem Mimarisi

Bir cismin fotografindan olcu cikarmanin onundeki temel engel,
tek bir goruntude **olcek bilgisinin bulunmamasidir**. Ayni cisim
kameraya yaklastikca buyur, uzaklastikca kucultur; goruntuye
bakarak hangisinin gecerli oldugu anlasilmaz.

Stereo goru bu sorunu iki kamerayi bilinen bir mesafeye
yerlestirerek cozer. Ayni nokta iki goruntude farkli yatay
konumlarda gorunur; bu konum farkina **disparity** denir ve mesafe
ile ters orantilidir:

    Z = f · B / d

Burada `Z` mesafe, `f` odak uzakligi (piksel), `B` iki kamera
arasindaki uzaklik (baz), `d` ise disparity degeridir.

Sistemi Sekil 1'de gosterilen islem sirasina gore kurdum. Her adim
bir onceki adimin ciktisini girdi olarak alir.

**[SEKIL 1 BURAYA]**
Dosya: `output/reports/sekil1_akis_semasi.png`
Altyazi: **Sekil 1 Sistemin islem akisi**

Cizelge 1'de her adimda hangi yontemin secildigi ve bu secimin
gerekcesi ozetlenmektedir.

**[CIZELGE 1 BURAYA]**

| Adim | Secilen yontem | Secim gerekcesi |
|---|---|---|
| Goruntu yakalama | MSMF arayuzu, MJPG, es zamanli yakalama | Iki kameranin ayni ani goruntulemesi zorunlu |
| Kalibrasyon | ChArUco deseni, `stereoCalibrate` | Desen kismen gorunse bile calisir, koseler alt-piksel bulunur |
| Rektifikasyon | `initUndistortRectifyMap` + `remap` | Esleme algoritmasi yalnizca yatay tarama satirinda arama yapar |
| On-isleme | Histogram (CDF) ton eslemesi | Iki kameranin ton egrisi donanimsal olarak farkli |
| Derinlik | SGBM + WLS filtresi | Filtresiz cikti kenar bolgelerde kullanilamayacak kadar gurultulu |
| Uc boyuta gecis | `reprojectImageTo3D` | Yalnizca mesafeyi degil X, Y, Z koordinatlarini birlikte verir |
| Nesne ayirma | Bolge buyutme + parlaklik ve uzaklik kisitlari | Cismi destek yuzeyinden ayirmak icin |
| Boyut cikarma | Temel bilesen analizi ile yonlu sinir kutusu | Cisim goruntu eksenlerine hizali olmak zorunda degil |

Altyazi: **Cizelge 1 Islem adimlari ve yontem secimleri**

Sistemi Python dilinde, OpenCV kutuphanesini kullanarak gelistirdim.
Arayuz icin Tkinter tercih ettim; boylece ek bagimlilik olmadan
kalibrasyon, derinlik haritasi ve olcum adimlarini tek pencerede
toplayabildim.

## 4.2. Teorik Calisma Araliginin Belirlenmesi

Donanimi kurmadan once sistemin **hangi mesafe araliginda anlamli
sonuc verebilecegini** hesapladim. Amacim, deneme yanilma ile zaman
kaybetmek yerine beklentiyi bastan sayisallastirmakti.

Mesafe bagintisinin turevi alinarak derinlik belirsizligi elde
edilir:

    ΔZ = Z² · Δd / (f · B)

Bu bagintinin en onemli sonucu, belirsizligin mesafenin **karesiyle**
buyumesidir. Sistemi iki kat uzaga kurmak hatayi iki degil **dort
kat** artirir.

Cizelge 2'de planlama asamasinda kullanilan kestirim degerleriyle
(f ≈ 914 piksel, B = 60 mm) hesaplanan calisma arali
gosterilmektedir.

**[CIZELGE 2 BURAYA]**

| Mesafe (mm) | Derinlik belirsizligi (mm) | Degerlendirme |
|---|---|---|
| 250 | 0,57 | Cisim gorus alanina sigmiyor |
| 350 | 1,12 | Uygun |
| 450 | 1,85 | Uygun |
| 550 | 2,76 | Uygun |
| 700 | 4,47 | Dogruluk yetersiz |
| 1000 | 9,11 | Dogruluk yetersiz |

Altyazi: **Cizelge 2 Hesaplanan teorik calisma araligi**

Bu hesaba dayanarak calisma bandini **350–550 mm** olarak belirledim.
Tahminin ne kadar tuttugunu Bolum 4.9'da gercek olcumlerle
karsilastirdim.

**Bu asamanin kazanimi.** Bir sistemin sinirini olcmeden once
hesaplayabilmek, hangi denemenin anlamli olacagini bastan belirliyor.
Hesap yapilmasaydi, 1 metre mesafede alinan kotu sonuclar yazilim
hatasi sanilip bosuna aranacakti.

## 4.3. Donanim Kurulumu ve Kamera Karakterizasyonu

Iki USB kamera modulunu, birbirlerine gore konumlari sabit kalacak
sekilde uc boyutlu yazicidan cikan bir govdeye sabitledim.
Kalibrasyondan sonra bu konumun degismemesi zorunludur; degisirse
tum kalibrasyon gecersiz olur.

Iki kamerayi ayni anda yonetmek icin bir test araci yazdim. Bu
araclarin en kritik islevi, kareleri **es zamanli** almaktir.
Kameralari sirayla okumak, aralarina goruntu cozme suresi koyar; bu
surede cisim veya kamera hareket ederse disparity degeri kayar.
Bunu onlemek icin once iki kameraya da "kareyi yakala", ardindan
"kareyi coz" komutu verilir.

**Pozlama siniri.** Pozlama degerlerini tarayip her degerde gercek
kare parlakligini olctum. Sonuclar Cizelge 3'te verilmektedir.

**[CIZELGE 3 BURAYA]**

| Pozlama degeri | Sol kamera parlaklik | Sag kamera parlaklik | Degerlendirme |
|---|---|---|---|
| −2 | 245 | 245 | Doymus, doku kalmiyor |
| −3 | 223 | 219 | Sinirda |
| −5 | 104 | 150 | Kullanilabilir |
| −7 | 15 | 6 | Cok karanlik |

Altyazi: **Cizelge 3 Pozlama degerine gore olculen kare parlakligi**

Bu olcumun sonucu sezgiye aykiridir: asiri aydinlik goruntu stereo
esleme icin **kotudur**. Piksel degerleri ust sinira dayandiginda
yuzeydeki doku kaybolur ve esleme algoritmasi tutunacak yapi
bulamaz.

## 4.4. Iki Kamera Arasindaki Dengesizlik ve Hatali Teshisler

Ilk denemelerde iki kamera ayni sahneye bakarken belirgin sekilde
farkli goruntu veriyordu; olculen parlaklik orani **2,7 kat**
seviyesindeydi. Stereo esleme iki goruntunun benzer olmasi
varsayimina dayandigi icin bu fark olcumu dogrudan bozuyordu.

Nedeni ararken sirasiyla uc varsayimda bulundum ve **ucu de olcumle
yanlislandi**:

1. Lens diyaframlarinin farkli olmasi
2. Sensorlerin duyarlilik farki
3. Lenslerden birinde koruyucu filmin kalmis olmasi

Gercek neden yazilim tarafindaydi. Kamera ayarlarini yazan fonksiyon,
on bir ozellikten yalnizca sekizini yaziyordu; gama, renk tonu ve
arka isik ozellikleri **hic yazilmiyordu**. Bu ozellikler kameranin
kendi hafizasinda kalici olarak saklandigi icin, gecmiste yazilmis
degerler oylece kaliyordu. Olcum sonucunda sol kamerada gama
degerinin 200, sag kamerada 100 oldugu goruldu.

On bir ozelligin tamami ayni degere yazildiginda elde edilen sonuc
Cizelge 4'te verilmektedir.

**[CIZELGE 4 BURAYA]**

| Pozlama degeri | Sol kamera | Sag kamera | Oran |
|---|---|---|---|
| −5 | 72,0 | 71,1 | 1,01 |
| −4 | 120,0 | 120,5 | 1,00 |
| −3 | 170,2 | 173,3 | 1,02 |

Altyazi: **Cizelge 4 Tum ayarlar esitlendikten sonra olculen parlaklik**

Iki buçuk kati askin farkin tamami ayar kaynakliymis; donanimsal bir
sorun yokmus.

Bu arastirma sirasinda ikinci bir bulgu daha ortaya cikti: kullanilan
surucu arayuzu, hangi deger yazilirsa yazilsin geri okumada ayni
sayiyi donduruyordu. Ancak ayar **gercekte uygulaniyordu**; bunu
kare parlakligini olcerek dogruladim. Bu nedenle programa "ayari geri
oku ve dogrula" mantigi yazmadim.

**Bu asamanin kazanimi.** Bir cihazin kendi bildirdigi durum,
dogrulama yerine gecmez. Dogrulama, cihazin **urettigi veriden**
yapilmalidir. Ayrica bir sistemde yazilmayan bir ayar, sifirlanmis
degil **eski degerinde kalmis** demektir.

## 4.5. Stereo Kalibrasyon ve Kalite Olcutu Secimi

Kalibrasyon icin ChArUco desenini sectim. Duz satranc deseninde
tespitin basarili olmasi icin desenin tamaminin gorunmesi gerekir;
ChArUco'da her kareye bir isaret gomulu oldugu icin desenin bir
kismi kapali olsa bile calisir. Kose konumlari ise satranc
kesisimlerinden alt-piksel hassasiyetle bulunur.

Kalibrasyonu uc adimda gerceklestirdim. Once her kamera ayri ayri
kalibre edilerek ic parametreleri (odak uzakligi, ana nokta,
distorsiyon katsayilari) bulundu. Ardindan stereo adiminda yalnizca
iki kamera arasindaki donme ve oteleme arandi; ic parametreler sabit
tutuldu. Hepsinin birlikte serbest birakilmasi parametreleri
birbirine karistirir ve cozumu kararsizlastirir. Son adimda
rektifikasyon donusumleri hesaplandi.

Kirk dort kare cifti ile yapilan kalibrasyonun sonuclari Cizelge
5'te verilmektedir.

**[CIZELGE 5 BURAYA]**

| Buyukluk | Deger |
|---|---|
| Stereo RMS | 0,834 piksel |
| Tekli RMS (sol / sag) | 0,770 / 0,768 piksel |
| Baz uzunlugu | 71,79 mm |
| Odak uzakligi (rektifiye) | 1418,18 piksel |
| Epipolar hata | **0,420 piksel** |

Altyazi: **Cizelge 5 Stereo kalibrasyon sonuclari**

**Metodolojik bulgu.** Kalibrasyon kalitesini iyilestirmek amaciyla
RMS degerini dusurmeye calistim ve veri setinden kotu gorunen
kareleri cikardim. RMS gercekten dustu, **ancak epipolar hata
kotulesti.**

Bu sonuc RMS'in ne olctugunu anlamami sagladi: RMS, modelin **kendi
verisine** ne kadar uydugunu gosterir. Veri setinden zor ornekleri
cikarmak modeli iyilestirmez, yalnizca sinavi kolaylastirir.

Bu nedenle kalite olcutu olarak **epipolar hatayi** kullandim.
Rektifikasyondan sonra ayni fiziksel noktanin iki goruntude ayni
satirda cikmasi gerekir; epipolar hata bu satir farkini olcer ve
kalibrasyondan bagimsiz bir dogrulamadir. Sekil 2'de kalibrasyon
karelerindeki kose hatasinin dagilimi gosterilmektedir.

**[SEKIL 2 BURAYA]**
Dosya: `output/reports/sekil4_kose_hata_analizi.png`
Altyazi: **Sekil 2 Kalibrasyon karelerinde kose hatasinin dagilimi**

**Iki farkli odak uzakligi.** Calisma sirasinda karistirilmaya
elverisli bir ayrim fark ettim. Ham kamera matrisinden okunan odak
uzakligi 1288,28 piksel, rektifikasyon sonrasi projeksiyon
matrisinden okunan ise 1418,18 pikseldir. Disparity degeri rektifiye
edilmis goruntude olculdugu icin mesafe hesabinda **ikincisi**
kullanilmalidir. Bu ayrim atlansaydi tum mesafeler yaklasik yuzde
dokuz sapacakti.

## 4.6. Derinlik Haritasi ve Sezgiye Aykiri Olcumler

Derinlik haritasini SGBM algoritmasi ve WLS filtresi ile urettim.
Bu asamada uc beklentim olcum sonucunda yanlislandi.

**Kontrast artirmak haritayi bozuyor.** Yerel kontrast artirmanin
(CLAHE) esleme kalitesini yukseltecegini varsaymistim. Alti gercek
goruntu cifti uzerinde ayni veriyi farkli on-islemelerle
karsilastirdim; sonuclar Cizelge 6'da verilmektedir.

**[CIZELGE 6 BURAYA]**

| Konfigurasyon | Ortalama derinlik sicramasi | %2'den buyuk sicrama orani |
|---|---|---|
| Kontrast artirma yok | **0,361** | **%1,5** |
| CLAHE, sinir 1,0 | 0,399 | %1,9 |
| CLAHE, sinir 2,0 | 0,419 | %2,1 |

Altyazi: **Cizelge 6 Kontrast artirmanin derinlik haritasina etkisi**

Nedeni sudur: duz ve dokusuz yuzeylerde kontrast artirmanin
yukselttigi sey gercek doku degil **sensor gurultusudur**. Algoritma
bu gurultuyu doku sanip sahte eslesme uretir. Ozelligi varsayilan
olarak kapattim.

**Cismin yonu esleme kalitesini belirliyor.** Esleme algoritmasi
aramayi yatay tarama satirinda yapar. Yatay bir kenar bu satir
boyunca uzandigi icin, goruntu yatay kaydirildiginda ayni gorunur ve
kayma miktari belirlenemez. Goruntu islemede *aperture problem*
olarak bilinen bu durumun olculen etkisi Cizelge 7'de verilmistir.

**[CIZELGE 7 BURAYA]**

| Bolge turu | Ham eslesme orani |
|---|---|
| Dikey yapili | %67,1 |
| Yatay yapili | %51,0 |

Altyazi: **Cizelge 7 Yapi yonune gore eslesme orani**

**Yansima zararli, golge zararsiz.** Golgeli bolgelerden kacinmak
gerektigini dusunuyordum. Sol-sag tutarlilik kontrolu bunun tersini
gosterdi: golgeli bolgelerde tutarsizlik %27,1 iken parlama olan
bolgelerde %58,7 olcüldü. Golge yuzeye yapisiktir; iki kamera onu
ayni fiziksel noktada gorur ve gecerli bir doku olusturur. Yansima
ise bakis acisina baglidir; parlak leke iki goruntude farkli
fiziksel noktada durdugu icin algoritma lekeyi lekeye eslestirip
hayalet derinlik uretir.

**Filtre doluluk orani kalite olcusu degildir.** WLS filtresi
bosluklari komsu piksellerden tahmin ederek doldurur. Harita tamamen
dolu gorunurken buyuk kisminin tahmin olmasi mumkundur. Bu nedenle
programda, filtreden **once** gercekten eslesen piksellerin orani
ayrica saklanir ve guvenilirlik degerlendirmesi bu degere bakar.

## 4.7. Nesne Segmentasyonu

Olcum icin kullanicinin tikladigi noktanin hangi cisme ait oldugunun
belirlenmesi gerekir. Ilk yaklasimim derinlik surekliligi oldu:
tiklanan noktadan baslayip benzer derinlikteki komsulara yayilmak.
Bu yontem calismadi, cunku cismin destek yuzeyine degdigi noktada
derinlik **sicrama yapmaz**; bolge kesintisiz olarak masaya akar.

Toplam bes yontem denedim. Sonuclari Cizelge 8'de ozetlenmistir.

**[CIZELGE 8 BURAYA]**

| Yontem | Sonuc |
|---|---|
| Derinlik toleransi | Cisim goruntu duzlemine paralelse calisiyor |
| Parlaklik seviyesi | Kismen calisiyor, cismin rengine bagimli |
| Kenar ve basamak engelleri | Kismen calisiyor, kararlilik katiyor |
| Duzlemden yukseklik | Calisiyor, zemin duzlemi gerektiriyor |
| Watershed | Calisiyor, zemin duzlemi gerektirmiyor |

Altyazi: **Cizelge 8 Denenen segmentasyon yontemleri**

Ayakta duran bir siseyi tepeden goruntuleyerek yaptigim referans
olcumde (gercek uzunluk yaklasik 250 mm) uc yontem karsilastirildi;
sonuclar Cizelge 9'da verilmektedir.

**[CIZELGE 9 BURAYA]**

| Yontem | Uc farkli ayarla elde edilen sonuc (mm) |
|---|---|
| Derinlik toleransi | 65 / 83 / 158 |
| Duzlemden yukseklik | 248,4 / 247,4 / 247,7 |
| Watershed | 248,9 / 249,0 / 248,9 |

Altyazi: **Cizelge 9 Segmentasyon yontemlerinin karsilastirilmasi**

Ilk uc yontemin **yapisal bir siniri** vardir: bir engel, bolgeyi
buyutemez, yalnizca kucultebilir. Cisim bakis dogrultusunda
uzaniyorsa bolge zaten cismin ortasinda durur ve engel hic devreye
girmez. Sekil 3'te bu durum gorulmektedir: yesil bolge cismin
ortasinda kesilmis, turuncu cizgiyle gosterilen gercek sinira
ulasamamistir. Olculen degerlere gore bolge gercek cismin yalnizca
%25'ini kapsamakta, durdugu noktadaki derinlik degisimi 3,91 mm/piksel
iken gercek cisim sinirinda bu deger 48,57 mm/pikseldir.

**[SEKIL 3 BURAYA]**
Dosya: `output/reports/basamak_neden_tutmadi.png`
Altyazi: **Sekil 3 Bolge buyutmenin cismin ortasinda durmasi**

Dorduncu ve besinci yontemlerin calismasinin nedeni **yayilmiyor
olmalaridir**. Her piksel sabit bir referansa karsi olculur;
dolayisiyla bolge ne erken durur ne de kacar.

## 4.8. Dogrulama Yonteminin Degistirilmesi

Bu bolum, calismanin yontem acisindan en onemli asamasini anlatir.

Birden fazla aday bolgeyi deneyip sonuclari test cisminin bilinen
olculerine yakinliga gore puanladim ve en iyi puanli sonucu
(234 × 55 × 39 mm) "cisim olculdu" diye kaydettim. Sonradan
gorulduki **olculen sey masanin kenariydi**; tesadufen benzer
sayilar uretmisti.

Bu olay bir hatanin duzeltilmesinden ibaret degil, dogrulama
anlayisimin degismesine yol acti: **beklenen cevaba yakinlik, dogru
seyi olctugunun kaniti degildir.** Yanlis bir bolge de rastlantisal
olarak makul sayilar uretebilir.

Bunun uzerine her olcum icin hesaplanan uc boyutlu kutuyu goruntu
uzerine cizdiren bir dogrulama araci yazdim. Kutu cismi sariyorsa
olcum dogru, cevreye tasiyorsa bolge kacmis demektir. Her boyutun
kenarlari ve kosedeki sayisal degeri ayni renkte cizilir; boylece
hangi sayinin hangi kenara ait oldugu tereddutsuz goruluru. Sekil
4'te bes olcumun dogrulama gorseli bir arada sunulmaktadir.

**[SEKIL 4 BURAYA]**
Dosya: `output/reports/rapor_dogrulama_levhasi.png`
Altyazi: **Sekil 4 Olcumlerin gorsel dogrulamasi. Ust uc seritte kutu cismi sarmakta, alt iki seritte sarmamaktadir**

Bu tarihten sonra hicbir olcumu yalnizca sayisal sonuca bakarak
kabul etmedim.

## 4.9. Olcek Dogrulamasi ve Belirleyici Etkenin Bulunmasi

**Olcek dogrulamasi.** Sistemdeki tum mutlak olcumler, kalibrasyon
deseninin kare boyu degerine (20,0 mm) dayanir. Bu deger yanlis
olsaydi tum olcumler ayni oranda kayar ve hata sistemin icinden fark
edilemezdi; her sey tutarli gorunur ama hepsi yanlis olurdu.

Dairesel olmayan bir kontrol kurdum: komsu desen koselerinin uc
boyutlu uzaydaki uzakligini, kayitli kare boyu degerini hic
kullanmadan olctum. Yirmi cekim uzerinde elde edilen medyan deger
**20,05 mm**, salinim ise 0,36 mm oldu. Kayitli deger ile arasindaki
oran 1,0023'tur; yani yuzde 0,2'lik bir fark vardir.

**Gurultunun darbogaz olmadigi bulgusu.** Sistemin hassasiyetini
dogrudan olctum: kirk alti adet duz masa yamasinda yerel sacilim
**1,15 mm** cikti. Bu deger, bagimsiz olarak olculen epipolar hata
(0,420 piksel) ile tutarlidir.

Buna karsilik gozlenen olcum hatalari 30–60 mm araligindaydi, yani
sensor gurultusunun otuz ila elli kati. Bu karsilastirma darbogazin
sensor veya kalibrasyon degil, **cismi arka plandan ayirma adimi**
oldugunu gosterdi. Bulgunun pratik sonucu, baz uzunlugunu buyutmenin
ya da kalibrasyonu daha da iyilestirmenin bu projede anlamli kazanc
getirmeyecegidir.

**Belirleyici etken: kamera yerlesimi.** Ayni kod ve ayni ayarlarla,
yalnizca kamera yerlesimini degistirerek yaptigim olcumler Cizelge
10'da verilmektedir. Referans cisim 250 × 72 mm olculerindedir.

**[CIZELGE 10 BURAYA]**

| Bakis | Mesafe (mm) | Uc farkli ayarla sonuc (mm) | Yayilim (mm) |
|---|---|---|---|
| Yandan, cisim dik | 610 | 252,3 / 252,2 / 252,2 | **0,1** |
| Yandan, cisim dik | 609 | 256,8 / 256,8 / 256,8 | **0,0** |
| Yandan, cisim dik | 625 | 254,5 / 255,2 / 255,2 | 0,7 |
| Tepeden, cisim yatik | 561 | 270,9 / 290,5 / 310,1 | 39,2 |
| Tepeden, cisim yatik | 718 | 177,8 / 204,7 / 264,6 | 86,8 |

Altyazi: **Cizelge 10 Kamera yerlesiminin olcum kararliligina etkisi**

Bu tablonun asil gosterdigi sey dogruluk degil **parametreye
duyarsizliktir**. Uygun yerlesimde sonuc ayar seciminden bagimsiz
cikmaktadir. Uygun olmayan yerlesimde ise ayni cisim icin 177 mm de
264 mm de yazilabilmektedir; boyle bir olcum tek bir sayi olarak
raporlanamaz.

Bulgunun ozeti su kuralla ifade edilebilir: **kameraya dogru uzanan
eksen, olculemeyen eksendir.** Cisim bakis dogrultusunda uzaniyorsa
tabandan tepeye derinlik surekli degisir ve derinlik toleransi
cismin ancak bir dilimini kapsar.

**Teorik tahminle karsilastirma.** Bolum 4.2'de calisma bandini
350–550 mm olarak hesaplamistim. Gercek olcumlerde en iyi sonuclari
550–650 mm bandinda aldim. Teorik hesap dogru yonu gostermis; sapma
ise planlamada varsayilan baz uzunlugu (60 mm) ile gerceklesen deger
(71,79 mm) arasindaki farktan kaynaklanmaktadir. Daha uzun baz,
kullanilabilir bandi bir miktar uzaga kaydirmaktadir.

Bu bulgu uzerine programa bir **kurulum kontrolu** islevi ekledim.
Islev, sahnedeki baskin duzlemin normali ile optik eksen arasindaki
aciyi canli derinlik verisinden hesaplar. Olculen degerler yandan
bakista 75–80 derece, tepeden bakista 16–29 derecedir; aradaki 46
derecelik bosluk iki durumu tereddutsuz ayirmaktadir. Islev bes
gercek cekimde bes dogru karar vermistir.

## 4.10. Sonuclar

Gelistirilen sistem, uygun kurulum kosullarinda bir cismin en uzun
kenarini yuzde bir ile yuzde uc arasinda bir hatayla olcebilmektedir.
Cizelge 11'de referans cisim uzerinde alinan olcumler ozetlenmistir.

**[CIZELGE 11 BURAYA]**

| Bakis | Mesafe (mm) | Gercek (mm) | Olculen (mm) | Hata |
|---|---|---|---|---|
| Yandan | 610 | 250 | 252,2 | %0,9 |
| Yandan | 609 | 250 | 256,8 | %2,7 |
| Yandan | 625 | 250 | 255,2 | %2,1 |
| Tepeden | 561 | 250 | 290,5 | %16,2 |
| Tepeden | 718 | 250 | 204,7 | %−18,1 |

Altyazi: **Cizelge 11 Referans cisim uzerinde alinan olcumler**

Sistemin dogrulanmis nitelikleri sunlardir: epipolar hata 0,420
piksel, olcek dogrulugu yuzde 0,2, kendi gurultusu 1,15 mm ve uygun
kurulumda parametre duyarsizligi 0,0–0,7 mm.

**Tamamlanamayan calismalar.** Sure kisiti nedeniyle asagidaki
basliklar tamamlanamamistir:

- Kesim sablonuyla fiziksel kutu uretilerek yapilacak dogrulama
- Bes farkli cisim uzerinde ana sonuc tablosunun olusturulmasi
  (yalnizca bir cisim olculebilmistir)
- Tekrarlanabilirlik testi (tek veri noktasi elde edilmis, ayni
  cisme iki ayri tiklamada 204,7 ve 202,1 mm olculmus, fark %1,3)
- Zemin duzlemi tespitindeki kararsizligin giderilmesi

**Zemin duzlemi sorunu.** Kalibrasyon deseninin periyodik yapisi,
tahtanin uzerinde blok eslemenin yanlis kareye kilitlenmesine yol
aciyor. Bu durumda duzlem konumu 30–57 mm sapabilmektedir. Sorun
tanimlanmis ancak cozulememistir. Sekil 5'te tahtanin uzerindeki
bozuk derinlik olcumu gorulmektedir; duz bir tahtanin mesafesi
410–656 mm araliginda saçilmaktadir.

**[SEKIL 5 BURAYA]**
Dosya: `output/reports/tahta_derinlik_bozuk.png`
Altyazi: **Sekil 5 Periyodik desen uzerinde bozulan derinlik olcumu**

Bu bulgu, bir bileseni tek basina "iyi" veya "kotu" olarak
degerlendirmenin yaniltici oldugunu gostermektedir. ChArUco deseni
kalibrasyon icin en uygun secimdir; tam bu ozelligi nedeniyle stereo
esleme icin en zorlayici durumu olusturur.

## 4.11. Kazanimlar

Bu calismada yazilim gelistirmenin otesinde, olcum yapan bir sistemi
dogrulama konusunda deneyim kazandim. One cikan basliklar sunlardir:

**Uyum olcutu ile dogruluk ayni sey degildir.** RMS degerini
iyilestirmek icin veri secmek, olcutun anlamini ortadan kaldirdi.
Bagimsiz bir olcut kullanmak zorunlu oldu.

**Beklenen sonuca yakinlik dogrulama sayilmaz.** Bu hata bir kez
masa kenarinin olculen cisim olarak raporlanmasina yol acti.

**Bir sistem kendi varsayimini kendi ciktisiyla dogrulayamaz.**
Kalibrasyon deseninin olcusunu, o olcuyu kullanmayan bagimsiz bir
yolla dogrulamak gerekti.

**Darbogaz olculmeden optimizasyon yapilmamali.** Uzun sure
kalibrasyon iyilestirilmeye calisildi; gurultu olculdugunde sorunun
tamamen baska bir adimda oldugu goruldu.

**Sezgi olcumle sinanmali.** Kontrast artirma, golge ve tepeden
bakis konularinda beklentilerimin ucu de yanlis cikti.

---

## SEKIL VE CIZELGE YERLESIM OZETI

Bu proje bolumunde **5 sekil** ve **11 cizelge** vardir. Birinci
projeninkiler eklendikten sonra numaralar kaydirilacak.

| No | Dosya | Nereye |
|---|---|---|
| Sekil 1 | `output/reports/sekil1_akis_semasi.png` | Bolum 4.1, "islem sirasina gore kurdum" cumlesinden sonra |
| Sekil 2 | `output/reports/sekil4_kose_hata_analizi.png` | Bolum 4.5, epipolar hata paragrafindan sonra |
| Sekil 3 | `output/reports/basamak_neden_tutmadi.png` | Bolum 4.7, yapisal sinir paragrafindan sonra |
| Sekil 4 | `output/reports/rapor_dogrulama_levhasi.png` | Bolum 4.8, dogrulama araci paragrafindan sonra |
| Sekil 5 | `output/reports/tahta_derinlik_bozuk.png` | Bolum 4.10, zemin duzlemi sorunu paragrafindan sonra |

Cizelgelerin tamami metin icinde bulunduklari yerdedir; ayri dosya
gerekmez.

**Istege bagli ek sekiller** (sayfa sayisi yeterse):

| Dosya | Nereye |
|---|---|
| `output/reports/sekil2_teorik_hata_egrisi.png` | Bolum 4.2, Cizelge 2'nin yanina |
| `output/reports/duzlem_kim_hakli.png` | Bolum 4.10, zemin duzlemi anlatimina |
| `output/reports/bolge_nerede_duruyor.png` | Bolum 4.7 |
| Uygulama arayuzu ekran goruntusu | Bolum 4.3 — **bu goruntuyu ogrencinin alması gerekiyor** |

---

## KAYNAKLAR (bu bolume ait)

Numaralar birinci projenin kaynaklarindan sonra devam etmelidir.

```
[n]  Hirschmuller, H., "Stereo Processing by Semiglobal Matching
     and Mutual Information", IEEE Transactions on Pattern Analysis
     and Machine Intelligence, Cilt 30, Sayi 2, 2008, s. 328-341.

[n+1] Zhang, Z., "A Flexible New Technique for Camera Calibration",
     IEEE Transactions on Pattern Analysis and Machine Intelligence,
     Cilt 22, Sayi 11, 2000, s. 1330-1334.

[n+2] Bradski, G., "The OpenCV Library", Dr. Dobb's Journal of
     Software Tools, 2000.

[n+3] OpenCV Dokumantasyonu, "Camera Calibration and 3D
     Reconstruction", https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html
     Cevrimici, erisim tarihi: 20.08.2026.

[n+4] OpenCV Dokumantasyonu, "Detection of ChArUco Boards",
     https://docs.opencv.org/4.x/df/d4a/tutorial_charuco_detection.html
     Cevrimici, erisim tarihi: 20.08.2026.
```

---

## KONTROL LISTESI (Word'e aktarirken)

- [ ] Bolum numaralari birinci projeye gore kaydirildi
- [ ] Sekil numaralari kaydirildi, metin icindeki atiflar guncellendi
- [ ] Cizelge numaralari kaydirildi, metin icindeki atiflar guncellendi
- [ ] Her sekil ve cizelge metin icinde en az bir kez alintilanmis
- [ ] Sekil altyazilari sekillerin ALTINDA, cizelge altyazilari
      cizelgelerin ALTINDA
- [ ] Altyazilar 11 punto kalin
- [ ] Bolum basliklari 14 punto kalin buyuk harf
- [ ] Alt bolumler 12 punto kalin
- [ ] Govde 11 punto, 1.15 satir araligi
- [ ] Sekiller satir ortalanmis, metne gomulu degil
- [ ] Sayfa altliginda ogrenci ad-soyad ve numara
- [ ] Icindekiler, Sekiller ve Cizelgeler listeleri guncellendi
- [ ] Kaynak numaralari atif sirasina gore
- [ ] Ondalik ayraci olarak virgul kullanildi (Turkce yazim)
