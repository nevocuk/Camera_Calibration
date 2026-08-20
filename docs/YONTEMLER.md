# Kullanilan Yontemler — Tam Referans

> Her adimda **hangi yontem**, **neden o yontem**, **hangi parametrelerle**,
> **hangi dosyada** ve **neyi denedik de olmadi**.
> Sayilarin tamami gercek cekimlerle olculdu; teorik degil.
> Son guncelleme: 2026-08-20.

## Icindekiler
1. [Boru hatti ozeti](#1-boru-hatti-ozeti)
2. [Goruntu yakalama](#2-goruntu-yakalama)
3. [Kamera ayar kontrolu](#3-kamera-ayar-kontrolu)
4. [Kalibrasyon](#4-kalibrasyon)
5. [Rektifikasyon](#5-rektifikasyon)
6. [On-isleme](#6-on-isleme)
7. [Disparity hesabi](#7-disparity-hesabi)
8. [Disparity temizleme](#8-disparity-temizleme)
9. [3B geri projeksiyon](#9-3b-geri-projeksiyon)
10. [Zemin duzlemi tespiti](#10-zemin-duzlemi-tespiti)
11. [Zemin cikarma](#11-zemin-cikarma)
12. [Nesne segmentasyonu](#12-nesne-segmentasyonu)
13. [Boyut cikarma](#13-boyut-cikarma)
14. [Kutu onerisi ve kesim](#14-kutu-onerisi-ve-kesim)
15. [Dogrulama ve gorsellestirme](#15-dogrulama-ve-gorsellestirme)
16. [Teshis araclari](#16-teshis-araclari)
17. [Reddedilen yontemler — ozet tablo](#17-reddedilen-yontemler--ozet-tablo)

---

## 1. Boru hatti ozeti

```
Yakalama -> Rektifikasyon -> On-isleme -> SGBM+WLS -> Temizleme
   -> reprojectImageTo3D -> [Zemin cikarma] -> Segmentasyon -> PCA kutusu
   -> Duzeltmeler -> Kutu onerisi / Kesim sablonu
```

| Adim | Yontem | Dosya |
|---|---|---|
| Yakalama | MSMF + MJPG, `grab()`/`retrieve()` | `camera_test.py::_capture_loop` |
| Rektifikasyon | `initUndistortRectifyMap` + `remap` | `camera_test.py::_open_cameras` |
| On-isleme | Histogram (CDF) ton esleme + GaussianBlur | `camera_test.py::_tone_match` |
| Disparity | StereoSGBM + WLS | `camera_test.py::_compute_disparity` |
| Temizleme | Median + morfolojik kapama + kucuk bolge silme | `camera_test.py::_clean_disparity` |
| 3B | `reprojectImageTo3D(dsp, Q)` | her yerde |
| Zemin | ChArUco + `solvePnP` (IPPE) | `camera_test.py::_detect_ground_plane` |
| Segmentasyon | `floodFill` + parlaklik + kenar + 3B sinir | `camera_test.py::_measure_click_pca` |
| Boyut | PCA (SVD) yonlu sinir kutusu | `kutu_gorsel.py::kutu_hesapla` |
| Kutu | Hacim israfi minimizasyonu | `box_output.py::suggest_boxes` |

---

## 2. Goruntu yakalama

**Yontem:** OpenCV `VideoCapture` + **MSMF** backend, **MJPG** codec,
2048x1536, iki kamerada once `grab()` sonra `retrieve()`.

**Neden `grab()`/`retrieve()` ayri:** `read()` her kamerada yakalama +
kod cozmeyi birlikte yapar; iki kamerayi sirayla `read()` etmek aralarina
kod cozme suresi koyar. Once ikisine `grab()` (sadece sensorden al),
sonra `retrieve()` (kod coz) demek zaman farkini kucultur. Stereo icin
esszamanlilik sart — cisim ya da kamera hareket ederse disparity kayar.

**Neden MJPG:** Ham YUY2 2048x1536'da USB bant genisligini doldurur ve
kare duser. MJPG sikistirilmis geldigi icin iki kamera ayni anda
calisabiliyor (~25-30 fps).

**Neden MSMF (DSHOW degil):** DSHOW'da bazi ayarlar (WB, exposure) iki
kamerada tutarsiz uygulaniyordu — her kamera icin farkli kontrol yolu
kullaniyor, bazi property'ler sessizce basarisiz oluyor.
Gecis: commit `59d84ad`.

**Netlik olcumu:** `cv2.Laplacian(gray, CV_64F).var()` — ikinci turev
enerjisi. Odak bozulunca yuksek frekans kaybolur, varyans duser.
Kullanildigi yer: `odak_test.py`, `odak_esitleme.py`, canli durum cubugu.

---

## 3. Kamera ayar kontrolu

**Yontem:** Her acilista **11 ozelligin tamami** acikca yazilir
(`_apply_all`): EXPOSURE, GAIN, BRIGHTNESS, CONTRAST, SATURATION,
SHARPNESS, GAMMA, HUE, BACKLIGHT, WB_TEMPERATURE, AUTO_WB.

**Neden hepsi:** Ayarlar kamerada **kalici** saklaniyor (test edildi:
yaz, kapat, ac -> deger duruyor). Yazilmayan bir ozellik gecmisten
kalan degerini korur; iki kamerada farkli olur. Olculdu: GAMMA
SOL 200 / SAG 100, EXPOSURE -6 / -3 (3 kademe = 8x parlaklik).
Bu, uzun sure "donanimsal lens/diyafram farki" sanilan seyin gercek
nedeniydi.

**11 ozellik ayni degere yazildiginda olculen:**

| Pozlama | SOL | SAG | Oran |
|---|---|---|---|
| -4 | 120.0 | 120.5 | **1.00x** |
| -3 | 170.2 | 173.3 | 1.02x |

**MSMF geri okumasi BOZUK:** `cap.get()` ne yazarsan yaz EXPOSURE hep
-6, CONTRAST hep 32 okuyor — ama **ayar gercekte uygulaniyor** (kare
parlakligi olculunce goruluyor). Bu yuzden koda `cap.get()` ile ayar
dogrulamasi **yazilmaz**; durum cubugu kullanicinin ayarladigi degeri
gosterir.

**Debounce:** `SpinSlider._on_scale` her fare hareketinde tetikleniyordu,
MSMF yazimlari dusuruyordu (kameralar 1.04x'ten 3.14x'e ayrisiyordu).
`_gecikmeli(anahtar, fn, ms=250)` ile 250 ms geciktirildi; "Ayarlari
kameraya yeniden yaz" ayni yazimi **uc kez** tekrarlar (MSMF ilk
yazimi yutabiliyor).

**Kural:** Degerin kendisi degil, **iki kamerada AYNI olmasi** onemli.

---

## 4. Kalibrasyon

**Desen:** ChArUco 9x13, `DICT_4X4_100`, olculen kare 20.0 mm.

**Neden ChArUco (ArUco grid degil):** ArUco grid'de kose hassasiyeti
marker boyutuna ve marker tespit dogruluguna bagli. ChArUco'da
marker'lar sadece **rehber**; gercek kose konumlari **checker
kesisimlerinden alt-piksel** hassasiyetle bulunur.

**Adimlar** (`calibration.py`):

| Adim | Cagri | Not |
|---|---|---|
| Tespit | `cv2.aruco.CharucoDetector` | kare/marker olculeri metre (`sq/1000.0`) |
| 1. Tekli | `cv2.calibrateCamera` | her kamera ayri, K ve D bulunur |
| 2. Stereo | `cv2.stereoCalibrate(flags=CALIB_FIX_INTRINSIC)` | sadece R, T aranir |
| 3. Rektifikasyon | `cv2.stereoRectify(flags=CALIB_ZERO_DISPARITY, alpha=0)` | R1,R2,P1,P2,Q |

**Neden `CALIB_FIX_INTRINSIC`:** Tekli kalibrasyonlar zaten K ve D'yi
iyi cozuyor. Stereo adiminda hepsini birlikte serbest birakmak
parametreleri birbirine karistirir; sadece R ve T aranirsa cozum daha
kararli.

**Neden `alpha=0`:** Rektifiye goruntude gecersiz (siyah) kenar
kalmaz — tum piksel gecerli. Bedeli: gorus alaninin bir kismi kirpilir.

**Birim: metre.** `sq / 1000.0` ile mm'den cevriliyor, dolayisiyla
T, Q ve `reprojectImageTo3D` ciktisi metre. UI'da `* 1000` ile mm.

**IKI FARKLI f_px — karistirma:**

| Deger | Kaynak | Nerede |
|---|---|---|
| 1288.28 px | `K1[0,0]` — ham intrinsik | `solvePnP`, ham goruntu geometrisi |
| **1418.18 px** | `P1[0,0]` — rektifiye projeksiyon | **Mesafe/deltaZ hesabi** |

(Guncel degerler `npz_oku --parametreler` ile okunur; yukaridakiler
2026-08-18 kalibrasyonundan. Yeniden kalibre edilince degisirler —
belgedeki sayiya degil dosyadaki degere guven.)

Disparity rektifiye goruntude olculdugu icin `Z = f*B/d` ve
`dZ = Z^2*dd/(f*B)` formullerinde **P1[0,0]** kullanilir.

**Kalite olcutu — RMS DEGIL:** RMS 0.8340 px (sol 0.7703, sag 0.7682) (limit: cozunurlukle
olcekli `0.4 x 2048/960 = 0.853`). Ama asil olcut **epipolar hata**:
44 cift / 3264 kose uzerinde **0.420 px**. Kare atarak RMS
dusuruluyor ama epipolar hata **kotulesiyor** — RMS tek basina
yaniltici. RMS tabani ~0.44 px ve bu kose lokalizasyon gurultusu.

---

## 5. Rektifikasyon

**Yontem:** `cv2.initUndistortRectifyMap(K, D, R, P, size, CV_32FC1)`
ile bir kez harita uretilir, her karede `cv2.remap(..., INTER_LINEAR)`.

**Neden zorunlu:** SGBM eslesmeyi **yalnizca yatay tarama satirinda**
arar. Epipolar geometri duzeltilmeden ayni satirda karsilik yoktur,
esleme calismaz.

**Neden harita onceden uretilir:** `initUndistortRectifyMap` pahali ve
kamera parametreleri sabit; her karede yeniden uretmek bosuna.

**Onemli:** Canli onizlemede cozunurluk dusurulse bile `remap`
**her zaman tam cozunurlukte** yapilir — kalibrasyon parametreleri
yalnizca orada kullanilir, dolayisiyla olcek dusurmek kalibrasyonu
bozmaz. (Ama olcum icin yine de kullanilamaz, bkz. bolum 17.)

---

## 6. On-isleme

**Yontem sirasi:** Ton esleme -> GaussianBlur(3,3). CLAHE varsayilan **kapali**.

### Ton esleme — uc secenek, varsayilan Histogram (CDF)

| Yontem | Nasil | Ton farki | Harita sicramasi |
|---|---|---|---|
| Yok | — | 46.80 | 0.964 |
| Dogrusal | `g_r = (g_r - mu_r) * (sig_l/sig_r) + mu_l` | 4.60 | 0.799 |
| **Histogram** | CDF eslemesi (`np.cumsum`) | **0.20** | **0.795** |

**Neden histogram gerekli:** Iki kameranin ton egrisi **donanimsal**
farkli (SOL p5=92/std=38.6, SAG p5=47/std=63.3). Bu fark
**dogrusal degil**; mean/std transferi ortalamayi esitler ama
dagilim farkini birakir. CDF eslemesi dagilimin tamamini esler.

**Neden `cv2.normalize` DEGIL:** `NORM_MINMAX` tum piksel degerlerini
`[mu-sigma, mu+sigma]` araligina sikistirir, dinamik aralik (0-255)
kaybolur, dusuk kontrastli bolgelerde esleme tutarsizlasir. Denendi,
derinlik haritasi dramatik olarak kotulesti.

### CLAHE — olculdu ve KAPATILDI

| Konfigurasyon | Ort. sicrama | >2px sicrama |
|---|---|---|
| **CLAHE yok** | **0.361** | **%1.5** |
| CLAHE 1.0 | 0.399 | %1.9 |
| CLAHE 2.0 | 0.419 | %2.1 |

**Teknik neden:** CLAHE yerel kontrasti artirir. Duz/dokusuz
yuzeylerde (duvar, masa) yukselttigi sey **sensor gurultusu** olur;
SGBM bunu gercek doku sanip sahte eslesme uretir. Etki clipLimit ile
dogru orantili. Merkez mesafe degeri etkilenmiyor — bozulan
**haritanin butunlugu**, yani kontur/hacim tabanli olcum icin onemli.

**GaussianBlur(3,3) kaldi** — haritayi bozmuyor, hafifce iyilestiriyor.

---

## 7. Disparity hesabi

**Yontem:** `cv2.StereoSGBM_create` + `cv2.ximgproc` WLS filtresi.

### Canli mod parametreleri (`camera_test.py:2852`)

```
minDisparity=0, numDisparities=256, blockSize=7
P1=8*3*49,  P2=32*3*49
disp12MaxDiff=1, uniquenessRatio=15
speckleWindowSize=200, speckleRange=2, preFilterCap=63
mode=STEREO_SGBM_MODE_SGBM_3WAY
WLS: Lambda=8000, SigmaColor=1.5
```

### Kaliteli tek kare [F] (`camera_test.py:3628`)

```
blockSize=9, P1=8*3*81, P2=32*3*81, speckleWindowSize=250
WLS: Lambda=12000, SigmaColor=1.2
Giris: 10 karenin gray ORTALAMASI
```

**Neden ayri parametre seti:** 10 kare ortalamasi sensor gurultusunu
zaten azaltir; daha buyuk blok ve daha yuksek lambda ile daha yumusak,
temiz bir harita cikar. Canli modda bu pahali olurdu.

**Neden `numDisparities=256`:** Arama araligi en yakin olculebilir
mesafeyi belirler (f=1420.04 px, B=71.6 mm):

| numDisparities | En yakin mesafe | Olu sol kenar |
|---|---|---|
| 128 | 794 mm | %6.3 |
| **256** | **397 mm** | %12.5 |
| 384 | 265 mm | %18.8 |

Soldaki `numDisparities` kadar piksel **yapisal olarak** gecersizdir
(esleme yapacak referans yok). Disparity yuzdesi bu yuzden
`dsp[:, 256:]` uzerinden hesaplanir.

**Neden `SGBM_3WAY`:** Tam 8 yonlu SGBM'ye gore belirgin hizli, kalite
farki bu sahnelerde gorulmedi.

**Neden P1/P2 buyuk:** P1/P2 komsu pikseller arasi disparity farkina
ceza verir. Dusurmek (blockSize=5, uniquenessRatio=5) denendi — dusuk
isikta gurultu patladi. Dusuk penalty = az yumusaklastirma = cok gurultu.

### WLS filtresi — zorunlu

Ham SGBM ciktisi cok gurultulu, ozellikle kenarlarda. WLS
**sol-sag tutarlilik** kontrolu yapip agirlikli en kucuk kareler ile
bosluklari doldurur ve kenarlari goruntu kenarlarina hizalar.

**KRITIK:** WLS bosluklari **interpolasyonla** doldurdugu icin
"dolgulu %" bir kalite olcusu **degildir**. Gercek olcut WLS oncesi
ham eslesme orani: `raw_mask = (dsp_l > 0)` ayrica saklanir.

### Temporal median
Canli modda son 5 karenin piksel bazinda medyani alinir — tek karelik
gurultu sicramalarini bastirir. Kaliteli karede gerek yok (giris zaten
10 kare ortalamasi).

### GPU StereoSGM — kullanilmiyor
CUDA StereoSGM 10x hizli (~29 ms vs ~283 ms) ama kodun GPU dalinda
**WLS adimi atlanmisti**; WLS'siz harita kullanilmaz. Not: onceki
belgelerdeki "WLS CUDA matcher kabul etmiyor" iddiasi **yanlis** —
test edildi, `createDisparityWLSFilter(cuda_sgm)` sorunsuz olusuyor.
Yani GPU + WLS ilerde denenebilir.

---

## 8. Disparity temizleme

**Yontem** (`_clean_disparity`), sirayla:
1. `cv2.medianBlur(dsp, 5)` — tuz-biber gurultusu
2. `MORPH_CLOSE` eliptik 7x7 — kucuk delikleri doldur
3. `connectedComponentsWithStats` — **500 pikselden kucuk** bolgeleri sil

**Neden bu sira:** Once nokta gurultusu gider, sonra kalan bolgelerin
delikleri kapanir, en son izole yamalar atilir. Ters sirada kucuk
gurultu yamalari once birlestirilip "buyuk bolge" gibi gorunurdu.

---

## 9. 3B geri projeksiyon

**Yontem:** `cv2.reprojectImageTo3D(dsp, Q)`, cikti metre, `* 1000` ile mm.

**Neden Q matrisi (dogrudan `Z = f*B/d` degil):** Q tum 3B koordinatlari
(X, Y, Z) verir, sadece mesafeyi degil — boyut olcumu icin X ve Y sart.
Ayrica lens distorsiyon duzeltmesini icinde tasir. (Dogru calistigi
`Z = f*B/d` ile capraz dogrulandi.)

**Nokta olcumu:** Tiklanan ya da merkez noktada 30x30 ROI icindeki
**gecerli** (disparity > 0) piksellerin **medyan** Z degeri.
Medyan, cunku ROI cismin kenarina denk gelirse ortalama arka planla
karisir; medyan baskin yuzeye tutunur.

---

## 10. Zemin duzlemi tespiti

**Yontem:** ChArUco tahtasi + `cv2.solvePnP` -> duzlem normali ve d.
8 kare ortalamasi, tam cozunurluk (2048x1536).

**KRITIK — rektifiye cercevede cozulur:** `solvePnP` girdisi
**rektifiye** goruntu, intrinsik **`P1[:3,:3]`**, distorsiyon **sifir**.

**Neden:** `reprojectImageTo3D` ciktisi rektifiye cercevede. Duzlem
ham cercevede cozulurse aradaki **R1 rotasyonu (1.567 derece)** kadar
kayar — 200 mm yanal uzaklikta **4.96 mm** yukseklik hatasi.
Eski dosyalar okunurken `n_rekt = R1 @ n_ham` ile cevrilir; dosyaya
`frame="rectified"` yazilir.

**Planar poz belirsizligi:** Duz bir desende `solvePnP`'nin iki
matematiksel cozumu vardir (tahta ileri ya da geri egik). `SOLVEPNP_IPPE`
+ `solvePnPGeneric` ile **iki cozum birden** alinip disparity'den gelen
derinlikle uyumlu olan secilir.

**Kalite olcutu — kose sayisi degil, yeniden izdusum hatasi.**
Onceki 25 derecelik aci kapisi 20 gecerli kareden 16'sini reddediyordu;
kaldirildi.

---

## 11. Zemin cikarma

**Yontem:** `h = n . X + d` (duzleme dik uzaklik). `h < esik` olan
pikseller maskelenir.

**`esik` bir DUZLEM OTELEMESIDIR, boyut filtresi degil.** Kesme duzlemi
masadan `esik` kadar yukari tasinir, altinda kalan her sey silinir —
cisim masada durdugu icin **cismin alt `esik` kadari da gider**.

**Kapsami sinirli.** `q_20260819_165521` uzerinde olculdu (duzlem
79.9 derece, bagimsiz RANSAC ile 1.6 derece uyum, yani duzlem dogru):

| | Oran |
|---|---|
| Duzlem uzerinde (h < 15 mm) | **%11.7** |
| esik 12 mm ile atilan | %26.9 |
| Kalan | %73.1 |

Zemin cikarma yalnizca **destek yuzeyini** siler, arka plani degil.
Genis cercevede masa sahnenin %12'si; duvar/raf/oda gercekten
duzlemin uzerinde (h medyani 85 mm, %90'da 866 mm).

**Ekstrapolasyon hatasi:** Duzlem ~600 mm'de ~200 mm'lik tahtadan
cikarilip 2000 mm'ye uzatiliyor. **1 derecelik fit hatasi 2000 mm'de
35 mm** yukseklik hatasi yapar — 12 mm esigin uc kati.
**Kural:** tahtanin +-300-400 mm civarinda guvenilir.

**Olcumdeki gercek degeri: DUYARSIZLIK.** Ayni cekim, iki harita,
tolerans taramasi (termos 250x72x36 mm):

| tol | HAM (kisitsiz) | ZEMIN CIKARILMIS (kisitsiz) |
|---|---|---|
| 12 mm | 194 x 77 | 194 x 77 |
| 20 mm | **390 x 343** | **210** x 78 |
| 60 mm | **422 x 304** | **210** x 96 |

Dar toleransta ikisi ayni. Tolerans buyuyunce ham harita masaya tasiyor,
zemin cikarilmis harita **sabit kaliyor** — sizinti fiziksel olarak
imkansiz. Yani zemin cikarma dogrulugu degil, **sonucun parametre
secimine duyarsizligini** kazandiriyor.

---

## 12. Nesne segmentasyonu

Iki bagimsiz yol var.

### A) Arka plan farki (`measurement.py::find_object_contour`)
Bos masa karesi kaydedilir, sonra `cv2.absdiff` + `threshold(30)`.

**Golge bastirma:** HSV'de golge, parlaklik oranini dusurur ama ton ve
doygunlugu korur. Kural: `0.35 < V_oran < 0.90` **ve** `H_fark < 10`
**ve** `S_fark < 40` -> golge, maskeden cikar.

Sonra `MORPH_CLOSE` (2 tur) + `MORPH_OPEN` (1 tur) eliptik 7x7,
`findContours(RETR_EXTERNAL)`, en buyuk kontur (>500 px).

**Sinir:** Arka plan karesi gerekir; sahne degisirse bozulur.

> **Bes yontem denendi, ucu ise yariyor.** Ozet tablo bolum 12C'de.

### B) Tiklayarak bolge buyutme (`_measure_click_pca`, `kutu_gorsel.py::segmentle`)
`cv2.floodFill` ile **disparity uzerinde** tohumdan bolge buyutulur
(`FLOODFILL_FIXED_RANGE` — tohuma gore sabit esik, komsu farki degil).

Uzerine **dort kisit**:

1. **Mesafeye gore olceklenen tolerans.** Kullaniciya **mm** sorulur,
   disparity'ye `dd = f*B*dZ / Z^2` ile cevrilir.
   *Neden:* sabit disparity toleransi yanlis — 6 px, 730 mm'de 63 mm,
   1750 mm'de 365 mm derinlik kapsiyor (5.8 kat).
2. **Parlaklik kisiti.** Tohum pikselin gri degerinden `gri tol`'dan
   fazla sapan pikseller sifirlanir.
   *Olculdu:* kisit yok 340x272, 45 -> 262x78, 25 -> 258x70.
   *Sinir:* cisim ve yuzey ayni renkteyse ise yaramaz, 0 ile kapatilir.
3. **Kenar engeli.** GaussianBlur + Sobel buyuklugu esigin ustundeki
   pikseller sifirlanir; bolge nesne sinirini gecemez. Bu sayede
   parlaklik kisiti gevsetilebilir (`gri 60 + kenar 60`).
4. **3B uzaklik siniri.** `|X - X_tohum| < sinir` (varsayilan 250 mm).

Son adim: `connectedComponentsWithStats` ile **tohumu iceren** bilesen
secilir (en buyuk bilesen degil).

**Neden derinlik tek basina yetmiyor:** Cisim masaya degdigi noktada
derinlik **sicramaz**; bolge kesintisiz masaya akar. Kamera yuzeye
~80 derece ile baktigi icin masa da genis bir derinlik araligina yayilir.

5. **Kenar engeli** (`kenar`, |grad I|) ve **basamak engeli**
   (`basamak`, |grad Z| mm/px). Esigi asan pikseller duvar yapilir.
   Seviye esiginin (gri) aksine cismin **icini bolmez**, yalnizca
   sinirini duvar yapar.
   *Esik dayanagi olculdu:* duz yuzey 0.2-2 mm/px, cisim siniri
   10+ mm/px; iyi deger 3.
   *Kazanci — kararlilik.* ORTA eksenin tol 15/30/60 yayilimi,
   6 cekim: `gri35+kenar60` 15/24/3/31/65/16 mm,
   `gri35+kenar30+basamak3` **3/0/3/12/31**/24 mm.

**Bu ailenin YAPISAL SINIRI (2026-08-20 olculdu):** bir engel bolgeyi
**buyutemez, yalnizca kucultebilir**. Cisim bakis dogrultusunda
uzaniyorsa bolge zaten cismin ortasinda durur ve engel hic devreye
girmez:

| | Deger |
|---|---|
| Bolge (ayakta sise, tol 30) | gercek cismin **%25**'i |
| Bolgenin durdugu yerdeki basamak | **3.91 mm/px** (kenar YOK) |
| Cismin gercek siluetindeki basamak | 48.57 mm/px |

Ayrica cisim yuzeye **degdigi** yerde basamak yoktur (yatik silindir
masaya tegettir); basamak tek basina 392.9 mm veriyor ve esigi 3'ten
12'ye cikarmak sonucu degistirmiyor.

**"Komsuya gore yayil" (FIXED_RANGE kapali) denendi:** bolge karenin
**%68-81**'ine yayiliyor, basamak engeli acikken bile. Masa yumusak
bir rampa; cisimden odanin her yerine dusuk basamakli bir yol var.
Yayilarak calisan her kriter ya erken durur ya kacar.

---

## 13. Boyut cikarma

### PCA yonlu sinir kutusu (`kutu_gorsel.py::kutu_hesapla`)
```
orta = P.mean(0);  _,_,Vt = np.linalg.svd(P - orta)
pr   = (P - orta) @ Vt.T
alt, ust = percentile(pr, 1), percentile(pr, 99)
```

**Neden PCA:** Cisim goruntu eksenlerine hizali olmak zorunda degil.
SVD, nokta bulutunun kendi dogal eksenlerini bulur — kutu cisme oturur.

**Neden %1/%99 (min/max degil):** Tek bir aykiri nokta kutuyu uzatir.
Yuzdelik kirpma bunu engeller.

### B2) Yukseklik kriteri (`--yukseklik`) — yayilma YOK
Her piksel **sabit bir referansa** karsi olculur:
**duzlemden >= h mm yukarida VE tiklamaya duzlem uzerinde <= r mm
yanal uzaklikta.** Tolerans hic kullanilmaz, dolayisiyla sonuc ona
duyarsizdir; mutlak bir olcut oldugu icin ne erken durur ne kacar.

Olculdu (ayakta sise, tepeden, gercek ~250 mm):

| Yontem | Sonuc |
|---|---|
| Derinlik toleransi 15/30/60 | 65 / 83 / 158 mm |
| h=15 yanal=45 | **248.4 mm** |
| h=15 yanal=70 | 247.4 mm |
| h=25 yanal=45 | 247.7 mm |
| h=25 yanal=70 | 247.0 mm |

**Sinir:** gecerli bir zemin duzlemi gerektirir.

### B3) Watershed (`--watershed`) — duzlem GEREKTIRMEZ
Kenar haritasinin ayrimi zaten cok iyi:

| | \|grad I\| medyan | \|grad Z\| medyan |
|---|---|---|
| Siluet | 108.3 | 22.28 |
| Cismin ici | 5.7 | 0.22 |

19-100 kat ayrim — esik sorunu yok. Ama bu duvarlari `floodFill`'e
verip toleransi serbest birakmak **tutmuyor**:

| Ayar | Kapsam | Saflik |
|---|---|---|
| kenar 30 basamak 3 | %43 | %9 |
| kenar 20 basamak 2 | %39 | %87 |
| kenar 80 basamak 10 | %98 | %17 |

Sebep **topolojik**: floodFill'in tutmasi icin duvarin HER YERDE
kapali olmasi gerekir; olculdu, siluetin en fazla **%86**'si duvar
oluyor ve kalan %14'un tek pikselinden bolge kaciyor. Bosluk kapatma
(3-9 px) da cozmuyor.

**Watershed'de bu sart yok** — her piksel gradyan sirtlarini asmadan
ulastigi en yakin isaretciye atanir, tek delik bozmaz. Isaretciler:
tiklanan nokta cevresi = cisim, uzak halka = arka plan.

| Ayar | Sonuc | Kapsam | Saflik |
|---|---|---|---|
| ic_r 25, dis_r 400 | **248.9 x 75.9** | %99 | %93 |
| ic_r 25, dis_r 550 | 249.0 x 76.1 | %98 | %93 |
| ic_r 60, dis_r 400 | 248.9 x 75.9 | %99 | %93 |
| ic_r 60, dis_r 550 | 249.0 x 76.0 | %98 | %93 |

**Yalnizca PARLAKLIK uzerinde calistirilmali.** Derinligi karistirmak
bozuyor (kapsam %99 -> %60-82, saflik %93 -> %45-69): WLS ile
yumusatilmis derinlik haritasinin kenarlari parlaklik kadar keskin
degil.

### C) EN IYI KURULUM - once buna bak (2026-08-20 olculdu)

Yontem secmeden once **geometriyi** duzelt. Ayni kod, ayni ayarlar,
termos (gercek 250 x 72 mm):

| Bakis | Z | tol 15/30/60 -> UZUN | Yayilim |
|---|---|---|---|
| **YANDAN, cisim DIK** | 610-625 mm | 252-257 mm | **0.0-0.7 mm** |
| Tepeden, yatik | 561 mm | 270.9 / 290.5 / 310.1 | 39 mm |
| Tepeden, yatik | 718 mm | 177.8 / 204.7 / 264.6 | 87 mm |

Asil kazanc dogruluk degil **toleransa duyarsizlik**: iyi kurulumda
sonuc ayardan bagimsiz, kotu kurulumda 39-87 mm oynuyor.

Kotu geometride hicbir ayar kurtarmiyor (141234, 718 mm):
gri 45 -> 204.8 | gri 90 -> 205.2 | gri kapali + kenar 30 -> 203.7 |
+ basamak 3 -> 203.7 | watershed 250 -> 214.6. Hepsi ayni yerde.

**Onerilen:** kamera cisme YANDAN baksin, 550-650 mm, cisim DIK.
Ayarlar `tol 30, gri 35, sinir 300`, deneyseller kapali
(Olcum tabinda "Onerilen ayarlar" butonu bunu yukler).

### D) Hangi durumda hangisi

| Durum | Yontem |
|---|---|
| Cisim goruntu duzlemine paralel yatiyor | derinlik toleransi + `gri`/`kenar`/`basamak` |
| Cisim ayakta, kamera tepeden | **`watershed`** (duzlem gerekmez) ya da `yukseklik` |
| Duzlem guvenilir, taban olcusu de lazim | `yukseklik` + taban geri kazanimi |

**Altta yatan kural:** kamera cismin en buyuk yuzlerini gormeli.
**Kameraya dogru bakan eksen olculemeyen eksendir.** Tepeden bakis
masada YATAN cisimler icin dogru, AYAKTA duran uzun cisim icin en
kotu acidir (termos yatirilinca uzun eksen 78 -> 284 mm'ye cikti).

### Duzlem tabanli olcum (`measurement.py::measure_3d_bbox`)
Zemin normali `n` yukseklik ekseni; duzlem uzerinde iki dik eksen
`u = n x e`, `v = n x u` kurulur. En/boy `u,v` izdusumlerinin araligi,
yukseklik `n` izdusumunun araligi.

**Neden ayri:** Yukseklik **her zaman zemine dik** olmali; PCA'da en
uzun eksen yukseklik olmayabilir. Bu yontemde siralama yapilmaz.

### Taban geri kazanimi (`--zemin`)
Esigin kestigi band olculebilir: bolgenin duzleme en yakin noktasi
`h_alt` kadar yukaridadir. Duzlem normaline en hizali ana eksen bulunup
`delta = h_alt / |v . n|` kadar uzatilir (eksende `delta` ilerlemek
yuksekligi `delta * (v . n)` kadar degistirir). Hicbir eksenin hizasi
0.20'nin altindaysa uzatma yonu belirsiz sayilip dokunulmaz.

**Olculen:** +52.2 mm geri kazanim -> **250.4 x 67.5 mm**
(gercek 250 x 72), uzun kenarda **%0.2** hata.
tol 20/35/60'ta 253.9 / 253.8 / 253.9 — ayara duyarsiz.

### Yuvarlak cisim duzeltmesi (`_yuvarlak_mi`)
Silindirik cisimde tek kameradan yalnizca **on yay** gorunur; PCA
kutusunun en kisa ekseni gercek capin cok altinda cikar (11-28 mm
olculdu, gercek 36 mm). Cember uydurma (Kasa yontemi) ile yaricap
bulunur. Yuvarlak sayilma kosulu: `kalinti/yaricap < 0.06` **ve**
`yaricap < 0.60 x uzun kenar`. Duzlem acisi 60 dereceyi asiyorsa
duzeltme uygulanmaz (yay cok kisa, uydurma guvenilmez).

### Kontur uzerinde disparity doldurma
`fill_disparity_on_contour` — kontur noktasinda disparity yoksa
`r=7` yaricapli komsulukta gecerli deger aranir. Kontur cismin
**kenarinda** olduğu icin orada eslesme sik basarisiz olur.

---

## 14. Kutu onerisi ve kesim

**Secim olcutu — hacim israfi** (`box_output.py::suggest_boxes`):
Cismin ve kutunun boyutlari **ayri ayri buyukten kucuge siralanir**
(cisim kutuya cevrilerek konabilir), her boyutta `margin=10 mm` pay
aranir, gecen adaylar `kutu_hacmi - cisim_hacmi` ile siralanir.

**Neden siralama:** 250x72x36 bir cisim 100x300x50 kutuya sigar —
eksen eslesmesi degil, boyut eslesmesi onemli.

**Desi:** `en_cm * boy_cm * yuk_cm / 3000` (Turkiye kargo standardi).

**Kesim sablonu:** RSC (Regular Slotted Container) SVG, tek karton
parcasindan katlanarak kutu. `generate_rsc_template_svg`.

---

## 15. Dogrulama ve gorsellestirme

### Kutu gorseli (`kutu_gorsel.py`) — asil dogrulama araci
Uc panel: (1) gray goruntu + turuncu kontur + **renk kodlu 3B kutu**,
(2) nokta bulutu eksen1 x eksen2, (3) eksen1 x eksen3 — 50 mm olcek
cubuklariyla.

**Renk kodu:** Her ana eksenin 4 kenari kendi renginde ve sol ustteki
olcu **ayni renkte** — UZUN yesil, ORTA acik mavi, KISA pembe.

**Neden bu araç kritik:** Sayilara bakip "dogru mu" demek guvenilir
degil. Bir kez aday bolgeler "beklenen olcuye sayisal yakinlik" ile
puanlandi ve 234x55x39 secilip "termos" diye sunuldu — **gercekte masa
kenariydi**. Dogrulama, kutunun gorselde cismi sarmasidir.

### Mesafe dogrulama [V]
Gercek mesafe elle girilir, olculenle karsilastirilir, `olcum_defteri.csv`'ye
yazilir. Onizleme (yari cozunurluk) modunda **reddedilir**.

### Renk olcegi: Sabit (Z_min..Z_max)
Kare bazli olcekleme (`dsp/dsp.max()`) calisma araligini 113-255 gri
bandina sikistiriyordu. Sabit olcek araligi 0-255'in tamamina yayar
(~1.8x daha iyi ayrim) ve olcek fiziksel anlam tasir.

---

## 16. Teshis araclari

| Script | Yontem | Ne olcer |
|---|---|---|
| `odak_test.py`, `odak_esitleme.py` | Laplacian varyansi | Lens odagi |
| `pozlama_teshis.py` | Pozlama taramasi + kare parlakligi | Kullanilabilir poz bandi (-5..-3) |
| `goruntu_ayar_teshis.py` | Ayar taramasi + SGBM | Ayarin haritaya etkisi |
| `kamera_denge_testi.py` | Iki kamera parlaklik/kontrast orani | Denge (hedef ~1.0x) |
| `kamera_default_kontrol.py` | DSHOW ile geri okuma | Gercek kamera durumu + kalicilik |
| `kamera_ayar_sifirla.py` | DSHOW ile 11 ozelligi yazma | Iki kamerayi esitleme |
| `mono_verify.py` | `solvePnP` + `projectPoints` | Tekli kalibrasyon dogrulugu |
| `kalibrasyon_hazirlik.py` | ChArUco tespit + ayar kontrolu | "Kalibrasyona hazir mi" |
| `sistem_planlama.py` | `dZ = Z^2*dd/(f*B)` | Teorik belirsizlik, calisma zarfi |

**DSHOW neden teshiste kullaniliyor:** MSMF **yazar ama okuyamaz**.
Kameranin gercek durumunu gormek icin DSHOW ile acmak gerekir.
Ayarlar kamerada saklandigi icin DSHOW ile bir kez yazmak yeterli —
uygulama MSMF ile acsa bile devralir.

---

## 17. Reddedilen yontemler — ozet tablo

| Yontem | Neden reddedildi | Olcum |
|---|---|---|
| GPU StereoSGM (WLS'siz) | Kod GPU dalinda WLS'yi atliyordu; harita kullanilmaz | 29 ms vs 283 ms ama gurultulu |
| `cv2.normalize` ile parlaklik esleme | Dinamik aralik kaybi | Harita "dramatik olarak kotu" |
| CLAHE | Dokusuz yuzeyde **gurultuyu** yukseltip sahte eslesme uretir | sicrama 0.361 -> 0.419 |
| DSHOW backend (uygulama icin) | Ayarlar iki kamerada tutarsiz uygulaniyor | — |
| Dusuk P1/P2, dusuk uniquenessRatio | Dusuk isikta gurultu patlamasi | — |
| ORB + BFMatcher crossCheck epipolar kontrolu | Dusuk dokuda kotu eslesme, outlier baskin | "84.67 px hata" sahte |
| ArUco Grid Board | Kose hassasiyeti marker tespitine bagli | ChArUco alt-piksel veriyor |
| RANSAC ile bolgedeki duzlemi atma | Bolge zaten ince derinlik dilimi = duzlemsel | bolgenin %69-100'u "duzlem" |
| minDisparity > 0 (acik sahnede) | Uzak pikseller gecersiz olmuyor, pencereye **sikisiyor** | merkez Z 442 -> 261 mm; ham eslesme yaniltici %100 |
| Onizleme olceginde olcum | Kucultme eslesmeyi saglayan ince yapiyi yok eder | bir cekimde 566 -> 904 mm (%59.8) |
| Sayisal yakinlikla dogrulama | Yanlis bolge de tesadufen dogru sayi uretir | masa kenari termos diye raporlandi |
| `cap.get()` ile ayar dogrulama | MSMF geri okumasi bozuk | ne yazarsan yaz EXPOSURE -6 okunuyor |
| RMS'i tek kalite olcusu sayma | Kare atinca RMS duser, epipolar hata **artar** | epipolar 0.420 px asil olcut |
| 25 / 60 derecelik kati aci kapilari | Gecerli olcumleri reddediyordu | 20 kareden 16'si reddedildi |

---

## Fiziksel sinirlar (yazilimla cozulemez)

| Olgu | Olcum | Sonuc |
|---|---|---|
| **Dikey vs yatay yapi** | eslesme %67.1 vs %51.0 (ort. 1.32x, en keskin 3.02x) | Cismi **dik** konumlandir |
| **Yansima** | tutarsizlik %58.7 (orta tona gore 2.44x) | Mat ortu, yandan isik |
| **Golge** | %27.1 (1.12x) — zararsiz | Golgeden kacinmaya gerek yok |
| **Egik bakis (80 derece)** | yukseklik gozlenebilirligi cos(80) = **0.177** | Tepeden bakis daha iyi |
| **Yuzey egimi** | `dd/dx = B*tan(aci)/Z`; 79.8 derecede 7 px blok boyunca **3.99 px** | Blok esleme bozulur |
| **Dokusuz yuzey** | SGBM disparity uretemez | Doku deseni kagidi koy |
| **Olcumun kendi sacilimi** | ~%4.3 | Tekrarlanabilirlik bunun altina inmez |

**Neden dikey yapi daha iyi:** SGBM eslesmeyi yatay tarama satirinda
arar. Yatay bir kenar tarama satiri **boyunca** uzanir; yatay
kaydirinca goruntu ayni kalir, kayma belirlenemez (klasik *aperture
problem*). Dikey kenar tarama satirini dik keser, kayma net olculur.

**Neden yansima zararli ama golge degil:** Golge yuzeye **yapisiktir**,
iki kamera onu ayni fiziksel noktada gorur — gecerli dokudur, eslesmeye
**yardim eder**. Yansima **bakis acisina baglidir**; parlak leke iki
kamerada farkli fiziksel noktada durur, SGBM lekeyi lekeye eslestirip
yanlis disparity uretir. Sonuc duzlemin uzerinde duruyormus gibi
gorunen hayalet bloblar — zemin cikarma bunlari silemez cunku gercekten
duzlemden uzakta hesaplanirlar.
