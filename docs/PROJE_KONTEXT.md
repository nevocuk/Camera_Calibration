# Stereo Kamera Projesi — Tam Kontext Dokumani

> Bu dosya, projeye sifirdan baslayacak bir modelin hizlica tam resmi gorebilmesi icin yazildi.
> Son guncelleme: 2026-08-20.
>
> **Yontem ayrintilari icin:** [YONTEMLER.md](YONTEMLER.md) — her
> adimda hangi yontem, neden o yontem, hangi parametrelerle,
> hangi dosyada ve neyi denedik de olmadi.

---

## 1. PROJE AMACI

Iki USB kamera (OV5693 sensor, M12 lens, 3B basilmis govde) ile stereo derinlik haritasi olusturup, masanin uzerindeki bir cismin 3B boyutlarini olcmek ve uygun kargo kutusunu onermek. Proje Nevfel'in ATU Bilgisayar Muhendisligi bolumundeki Sadektech staj calismasi icin hazirlanıyor; cikti olarak staj raporu (Ek-4 sablonu), canli demo ve dogrulama tablolari uretilecek.

Nihai hedef: bilinen mesafelerde %5'in altinda olcum hatasi, tekrarlanabilirlik, ve fiziksel kutu kesimi ile dogrulama.

---

## 2. MIMARI / PIPELINE

```
Kamera Yakalama  →  Stereo Rektifikasyon  →  SGBM + WLS  →  reprojectImageTo3D  →  Olcum / Kutu Onerisi
     (grab/retrieve)     (calib_result.npz)     (disparity)       (Q matrisi, metre)      (measurement.py, box_output.py)
```

### Adim adim:

1. **Kamera Yakalama** (`camera_test.py`): Iki kameradan eszamanli `grab()` + `retrieve()` ile cift frame alinir. MSMF backend. 2048x1536 MJPG, ~25-30 fps.

2. **Stereo Rektifikasyon**: `cv2.initUndistortRectifyMap` + `cv2.remap` ile her iki goruntu hizalanir. Kalibrasyon matrisleri (K1, D1, R1, P1, K2, D2, R2, P2) `calibration/calib_result.npz`'den yuklenir.

3. **Preprocessing**: CLAHE (clipLimit=2.0), istatistiksel parlaklik esleme (mean/std transfer, sol→sag), GaussianBlur (3,3). Amac: iki kamera arasindaki parlaklik farkini gidermek, SGBM'nin tutarli esleme yapmasini saglamak.

4. **Disparity Hesaplama**: CPU StereoSGBM (numDisparities=256, blockSize=7) + WLS filtre (Lambda=8000, SigmaColor=1.5). Canli modda 5-frame temporal median ile stabilite. Kaliteli kare modunda 10-frame ortalama giris + ayri SGBM (blockSize=9, Lambda=12000) ile daha yumusak sonuc.

5. **Derinlik → Mesafe**: `cv2.reprojectImageTo3D(dsp, Q)` — Q matrisi metre biriminde (kalibrasyon sq/1000.0 ile metre kullanir). Cikan Z degeri `* 1000` ile mm'ye cevrilir. Merkez veya tiklanan noktada 30x30 ROI icindeki gecerli (disparity > 0) piksellerin medyan Z degeri alinir.

6. **Nesne Olcumu** (`measurement.py`): Zemin duzlemi cikarma (`ground_plane.npz`) + taban konturu + disparity yukseklik ile 3B boyut (en, boy, yukseklik).

7. **Kutu Onerisi** (`box_output.py`): Olculen boyutlara en yakin standart kargo kutusu (`data/kutu_tablosu.json`), desi hesabi, RSC kesim yonergesi PDF.

### Neden bu sira:
- Rektifikasyon zorunlu: SGBM sadece yatay scanline'da esleme yapar, epipolar geometri duzeltilmeden calismaz.
- WLS filtre zorunlu: ham SGBM ciktisi cok gurultulu, ozellikle kenar bolgelerde. WLS sol-sag tutarlilik kontrolu yapar.
- Preprocessing (CLAHE + brightness matching) zorunlu: iki kameranin ISP'si farkli cevap verir, esleme bozulur.
- reprojectImageTo3D vs dogrudan Z=f*B/d formulu: reprojection Q matrisi uzerinden tum 3B koordinatlari (X, Y, Z) verir, sadece mesafe degil. Ayrica lens distorsiyon duzeltmesini icinde tasiyor.

---

## 3. DOSYA YAPISI

### Ana kod dosyalari
| Dosya | Ne yapar |
|---|---|
| `src/camera_test.py` | **Ana uygulama** — Tkinter GUI, 7 tab, tum pipeline. ~2300 satir. |
| `src/calibration.py` | Stereo kalibrasyon: ChArUco/GridBoard tespit, tekli + stereo kalibrasyon, rektifikasyon dogrulama, sonuc kaydi. |
| `src/measurement.py` | Nesne olcum pipeline: zemin cikarma, kontur bulma, 3B boyut hesaplama. |
| `src/box_output.py` | Kutu onerisi + RSC kesim yonergesi PDF uretimi. |
| `src/ground_plane.py` | ChArUco ile zemin duzlemi (normal + d) tespiti. |
| `src/depth_view.py` | Bagimsiz derinlik goruntuleyici (3 pencere, Z=f*B/d formulu). |
| `src/rapor_verisi.py` | **Rapor verisi ureticisi** - `data/rapor_olcumleri.csv`'deki satirlari kayitli cekimlerden yeniden olcup CSV + markdown tablo + dogrulama levhasi uretir. |
| `src/npz_oku.py` | Cekim/parametre dosyalarini okuma, `--parametreler` ile tum ayarlari tek ciktida dokme. |
| `src/kutu_gorsel.py` | **Dogrulama gorseli** — goruntu uzerine renk kodlu 3B kutu + iki nokta bulutu paneli. `--zemin` ile zemin cikarilmis haritadan olcer ve kesilen tabani geri ekler. |
| `src/tikla_olc.py` | CLI tiklayarak olcum (PCA kutusu). |
| `src/cisim_olc.py` | Kayitli cekimden duzlem tabanli boyut olcumu. |

### Yardimci scriptler
| Dosya | Ne yapar |
|---|---|
| `src/detect_cameras.py` | Bagli USB kameralari listele |
| `src/probe_resolutions.py`, `probe_full.py`, `probe_backend.py`, `probe_msmf_full.py`, `probe_stereo_bandwidth.py` | Kamera yetenekleri, bant genisligi, backend testleri |
| `src/odak_test.py` | Lens odak dogrulama (Laplacian varyans) |
| `src/mono_verify.py` | Tekli kalibrasyon dogrulama |
| `src/test_charuco.py`, `charuco_debug.py`, `detect_test.py` | ChArUco tespit debug araclari |
| `src/sistem_planlama.py` | Teorik derinlik belirsizligi ve calisma zarfi hesaplama |
| `src/pozlama_teshis.py`, `goruntu_ayar_teshis.py` | Pozlama ve goruntu ayari taramasi (gercek kare parlakligi olculur) |

### Veri ve konfigürasyon
| Dosya | Icerik |
|---|---|
| `data/charuco_config.json` | Desen parametreleri: 9x13 ChArUco, DICT_4X4_100, olculen kare=20mm |
| `data/camera_settings.json` | Kamera ayarlari: pozlama, gain, WB, telafiler |
| `data/kutu_tablosu.json` | Standart kargo kutu olculeri |
| `data/olcum_defteri.csv` | Tum olcumlerin kaydi |
| `calibration/calib_result.npz` | Kalibrasyon matrisleri (K, D, R, T, Q, P1, P2, R1, R2, image_size) |
| `calibration/ground_plane.npz` | Zemin duzlemi normal vektoru + d |
| `calibration/frames/` | Kalibrasyon kare ciftleri (L_001.png, R_001.png, ...) |
| `patterns/charuco_board.png` | Basima hazir kalibrasyon deseni |
| `patterns/sgbm_doku_desenleri_v2.pdf` | Stereo esleme icin doku desen kagitlari |
| `output/depth_captures/` | Kaliteli kare cekimleri (overlay, disparity, gray, .npz) |

---

## 4. ALINAN KARARLAR VE GEREKCESI

### CPU SGBM + WLS yerine GPU StereoSGM
GPU StereoSGM (CUDA) 10x hizli (~29ms vs ~283ms, 2048x1536). Ancak GPU kod dalinda WLS filtresi **hic uygulanmiyordu** — `stereo.compute()` ciktisi dogrudan kullaniliyordu. WLS'siz disparity cok gurultulu, kullanisiz. **Karar: CPU SGBM + WLS ile devam.** GPU kodu stash'te sakli (commit 72cc70a).

> **Duzeltme (2026-08-16):** Daha once bu dosyada "createDisparityWLSFilter sadece CPU matcher kabul ediyor" yaziyordu — **bu yanlis**. Test edildi: `cv2.ximgproc.createRightMatcher(cuda_sgm)` ve `createDisparityWLSFilter(cuda_sgm)` sorunsuz olusuyor. Gercek sorun API kisiti degil, **kodun GPU dalinda WLS adiminin atlanmis olmasi**. Yani GPU + WLS ilerde denenebilir; onceki "imkansiz" gerekcesi gecersiz.

### ChArUco yerine ArUco Grid Board denendi, ChArUco'ya donuldu
Ilk denemeler DICT_4X4_100 ArUco grid board ile yapildi. ChArUco daha yuksek hassasiyet veriyor cunku ArUco marker'lari sadece kose tespiti icin rehber, gercek kose konumlari checker kesisimlerinden sub-pixel hassasiyetle bulunuyor. Grid board'da kose hassasiyeti marker boyutuna ve marker tespit dogruluguna bagli.

### MSMF backend yerine DSHOW denendi, MSMF'ye donuldu
DSHOW ile kamera ayarlarinin bir kismi (WB, exposure) her iki kamerada tutarsiz uygulaniyordu. MSMF daha tutarli kontrol veriyor. Gecis commit 59d84ad'de.

### Kalibrasyon birimleri: metre
`calibration.py` objekt noktalarini `sq / 1000.0` ile metreye ceviriyor (satir 71). Bu nedenle T vektoru metre, Q matrisi metre biriminde. `reprojectImageTo3D` ciktisi metre. Koddaki `* 1000` carpani mm'ye cevirir. Bu tutarli ve dogru calisiyor — dogrudan formul (Z = f*B/d) ile de dogrulandi.

### Preprocessing: CLAHE + istatistiksel esleme yerine cv2.normalize denendi
cv2.normalize ile parlaklik esleme denendi, tum piksel degerlerini mean±std araligina sikistirdi, dinamik aralik kaybi yaratti, derinlik haritasi dramatik olarak kotulesdi. **Karar: mean/std transfer yontemi** — sag kameranin ortalamasini ve standart sapmasini sol kameraya gore olcekler, dinamik aralik korunur.

### numDisparities=256
2048 piksel genislikte 256 disparity → sol kenardaki 256 piksel (%12.5) yapisal olarak gecersiz (esleme yapacak referans pikseli yok). Bu kabul edilebilir — merkezdeki cisimler icin sorun degil.

**Mesafe siniri (olculdu, f=1420.04 px, B=71.6 mm):**

| numDisparities | En yakin olculebilir mesafe |
|---|---|
| 128 | 794 mm |
| 256 | **397 mm** |
| 384 | 265 mm |

Yani 256 ile 40 cm'den yakin cisim olculemez. Hesaplama tabindaki `Z_min` varsayilani 300 mm — bu deger **ulasilamaz**, 400 mm'nin altina inmek icin numDisparities 384'e cikarilmali (daha yavas + %18.75 olu kenar).

### Zemin duzlemi REKTIFIYE cercevede cozulur (2026-08-19)
`reprojectImageTo3D` ciktisi rektifiye cercevede, ama duzlem eskiden
`solvePnP(K1, D1, ham goruntu)` ile HAM cercevede cozuluyordu. Aradaki
R1 rotasyonu **1.567 derece**; 200 mm yanal uzaklikta **4.96 mm**
yukseklik hatasi. Artik solvePnP rektifiye goruntude, intrinsik
`P1[:3,:3]`, distorsiyon sifir ile calisiyor ve dosyaya
`frame="rectified"` yaziliyor. Eski dosyalar okunurken `R1 @ n` ile
cevriliyor. Planar poz belirsizligi icin `SOLVEPNP_IPPE` +
`solvePnPGeneric` ile iki cozum alinip derinlik uyumuna gore secilir.

### Zemin cikarma esigi bir DUZLEM OTELEMESIDIR (2026-08-19)
`esik (mm)` boyut filtresi degil. Kesme duzlemi masadan `esik` kadar
yukari tasinir, **altinda kalan her sey** silinir — cisim masada
durdugu icin cismin alt `esik` kadari da gider. Kaybi `kutu_gorsel.py
--zemin` icindeki **taban geri kazanimi** olcup geri ekler: bolgenin
duzleme en yakin noktasi `h_alt` kadar yukaridadir, duzlem normaline
en hizali ana eksende `delta = h_alt / |v . n|` kadar uzatilir.

### Olcum icin zemin cikarma: dogruluk degil DUYARSIZLIK (2026-08-19)
Termos (gercek 250 x 72 x 36 mm), `q_20260819_170641`, tikla (1373,1045):

| tol | HAM (kisitsiz) | ZEMIN CIKARILMIS (kisitsiz) |
|---|---|---|
| 12 mm | 194 x 77 | 194 x 77 |
| 20 mm | **390 x 343** | **210** x 78 |
| 60 mm | **422 x 304** | **210** x 96 |

Dar toleransta iki harita birebir ayni. Tolerans buyuyunce ham harita
masaya tasiyor, zemin cikarilmis harita sabit kaliyor — sizinti
fiziksel olarak imkansiz. Taban geri kazanimiyla sonuc
**250.4 x 67.5 mm** (uzun kenarda %0.2 hata) ve tol 20-60 arasi
253.9 / 253.8 / 253.9 — **ayara duyarsiz**. Rapor icin dogruluktan
degerli, cunku sonuc parametre secimiyle oynamiyor.

**Varsayilan degismedi** (ham harita); yeni davranis `--zemin` bayragi
ve Olcum tabindaki "zemin haritasi" kutucugu ile secilir.

### Tiklayarak olcumde uc kisit (2026-08-19)
Derinlik surekliligi tek basina cismi masadan ayirmiyor (tabanda
derinlik sicramasi yok). Sirasiyla:
1. **Mesafeye gore olceklenen tolerans** — `dd = f*B*dZ/Z^2`.
   Sabit disparity toleransi yanlis: 6 px, 730 mm'de 63 mm, 1750 mm'de
   365 mm derinlik kapsiyor (5.8 kat).
2. **Parlaklik kisiti** — tohumun gri degerinden sapan pikseller
   elenir. Olculdu: kisit yok 340x272, 45 -> 262x78, 25 -> 258x70.
3. **Kenar engeli** — Gauss + Sobel buyuklugu esigin ustundeki
   pikseller sifirlanir; bolge nesne sinirini asamaz. Parlaklik
   kisitinin gevsetilmesine izin verir.

### Yuvarlak cisimlerde cap duzeltmesi (2026-08-19)
Silindirik cisimde tek kameradan **on yay** gorunur; PCA kutusunun en
kisa ekseni gercek capin cok altinda cikar (11-28 mm olculdu, gercek
36 mm). `_yuvarlak_mi` cember uydurmasiyla (Kasa yontemi) tespit eder:
kalinti/yaricap < 0.06 ve yaricap < 0.60 x uzun kenar. Duzlem acisi
60 dereceyi asiyorsa duzeltme uygulanmaz (yay cok kisa).

### En iyi olcum kurulumu OLCULDU (2026-08-20)
Ayni kod ve ayarlarla, termos (gercek 250 x 72 mm):

| Bakis | Z | tol 15/30/60 -> UZUN | Yayilim |
|---|---|---|---|
| **YANDAN, cisim dik** | 610-625 mm | 252-257 mm | **0.0-0.7 mm** |
| Tepeden, yatik | 561 mm | 270.9 / 290.5 / 310.1 | 39 mm |
| Tepeden, yatik | 718 mm | 177.8 / 204.7 / 264.6 | 87 mm |

Asil kazanc dogruluk degil **toleransa duyarsizlik**. Rapor
olcumlerinin tamami yandan bakisla, 550-650 mm'de alinmali.

Derinlik hassasiyeti mesafenin karesiyle kotulesir: 560 mm'de
3.09 mm/px, 718 mm'de 5.06 mm/px.

### Kurulum kontrolu: bakis acisi derinlikten olculebiliyor (2026-08-20)
Sahnenin baskin duzleminin normali ile optik eksen arasindaki aci
bakisi tereddutsuz ayiriyor: **yandan 75-80 derece, tepeden 16-29
derece**. Arada 46 derecelik bosluk; esik 55 derece. ChArUco
gerekmez, canli derinlikten RANSAC yeter. Olcum tabindaki "Kurulum
kontrolu" butonu bunu ve mesafeyi (onerilen 500-680 mm) denetliyor;
bes gercek cekimde 5/5 dogru karar verdi.

### Deneysel kontroller varsayilan GIZLI (2026-08-20)
`kenar`, `basamak`, `yukseklik`, `watershed` yalnizca kotu
geometride ise yariyor; iyi kurulumda sonucu hic degistirmedikleri
olculdu. Olcum tabinda "Deneysel yontemler" adli KAPALI bir bolume
alindilar. "Onerilen ayarlar" butonu hepsini sifirlar ve
kanitlanmis degerleri yukler (tol 30, gri 35, sinir 300).

### Segmentasyon: BES yontem, ucu ise yariyor (2026-08-20)
Ayni soruya cevap ariyorlar: "tiklanan piksel hangi cisme ait?"

| # | Yontem | Durum |
|---|---|---|
| 1 | Derinlik toleransi (`tol`) | Cisim goruntu duzlemine paralelse calisir |
| 2 | Parlaklik seviyesi (`gri`) | Kismen - cisme bagimli |
| 3 | Kenar + basamak engelleri | Kismen - kararlilik kazandirir |
| 4 | Yukseklik kriteri (`yukseklik`) | **Calisiyor** - duzlem gerekir |
| 5 | Watershed (`watershed`) | **Calisiyor** - duzlem gerekmez |

Referans olcum (ayakta sise, tepeden, gercek ~250 x 72 mm):

| Yontem | Sonuc |
|---|---|
| Derinlik toleransi tol 15/30/60 | **65 / 83 / 158 mm** |
| Yukseklik kriteri (4 ayar) | 248.4 / 247.4 / 247.7 / 247.0 |
| Watershed (4 ayar) | **248.9 / 249.0 / 248.9 / 249.0** |

**1-3'un yapisal siniri:** bir engel bolgeyi **buyutemez, yalnizca
kucultebilir**. Cisim bakis dogrultusunda uzaniyorsa bolge zaten
cismin ortasinda durur (olculdu: gercek cismin %25'i, durdugu yerdeki
basamak 3.91 mm/px yani kenar YOK, gercek siluette 48.57 mm/px) ve
engel hic devreye girmez.

**4 ve 5 neden calisiyor:** yayilmiyorlar. Her piksel sabit bir
referansa karsi olculur (duzlem yuksekligi / watershed isaretcisi),
dolayisiyla ne erken durur ne kacar.

**Kural:** kamera cismin en buyuk yuzlerini gormeli. **Kameraya
dogru bakan eksen olculemeyen eksendir.** Tepeden bakis masada
YATAN cisimler icin dogru, AYAKTA duran uzun cisim icin en kotu
acidir (termos yatirilinca uzun eksen 78 -> 284 mm).

### Kare olcusu DOGRULANDI (2026-08-20)
Komsu ChArUco koselerinin 3B mesafesi 20 cekimde olculdu -
`olculen_kare_boyutu_mm` degerini hic kullanmadan, yani dairesel
olmayan bir kontrol: **medyan 20.05 mm**, salinim 0.36, config
20.00 mm, oran 1.0023 (+%0.2). Config ve kalibrasyon olcegi dogru.

### Kaliteli Tek Kare (F modu) vs canli derinlik
Canli derinlik ~3-5 fps, her frame farkli gurultu. Kaliteli kare: 10 farkli frame'in gray ortalamasini alarak sensor gurultusunu azaltir, sonra ayri (daha buyuk blockSize=9, daha yuksek WLS lambda=12000) SGBM ile isler. Sonuc daha temiz disparity haritasi. Hash-based frame change detection ile ayni frame'i tekrar almaz.

### Tiklayarak olcum (son eklenen)
Crosshair her zaman goruntu merkezini olcuyordu. Cisim merkeze denk gelmediyse arkaplan mesafesi okunuyordu (bu, 2260mm okumasinin gercek nedeni — kod hatasi degil, hizalama sorunu). **Karar: sol goruntuye tiklayarak olcum noktasini degistirme** eklendi. [R] tusu merkeze sifirlar.

---

## 5. DENENDI VE ISE YARAMADI

### GPU StereoSGM (WLS'siz)
**Ne oldu:** CUDA StereoSGM 10x hizli ama WLS filtresi CPU matcher'a bagli. WLS olmadan disparity haritasi cok gurultulu — kenarlar parcali, duz yuzeyler benek benek. Uretici ciktisi ozellikle dusuk dokulu alanlarda (beyaz duvar, duz masa) kullanisiz.
**Teknik neden:** `cv2.ximgproc.createDisparityWLSFilter(matcher)` parametresi `cv2.StereoSGBM` veya `cv2.StereoBM` bekler, `cv2.cuda.StereoSGM` kabul etmez.
**Sonuc:** CPU SGBM + WLS ile devam. GPU ancak WLS CUDA'ya port edilirse anlamli.

### cv2.normalize ile parlaklik esleme
**Ne oldu:** Her iki kameranin gray goruntusu `cv2.normalize(src, dst, mu-sigma, mu+sigma, cv2.NORM_MINMAX)` ile eslendi. Sonuc: derinlik haritasi oncekinden dramatik olarak kotu — karincali, parcali, istikrarsiz. Kullanicinin geri bildirimi: "eskisinden daha kotu, baya kotu gibi".
**Teknik neden:** NORM_MINMAX tum piksel degerlerini [mu-sigma, mu+sigma] araligina siksitiriyor. Gercek dinamik aralik (0-255) kayboldu, dusuk kontrastli bolgelerde esleme tutarsiz hale geldi.
**Dogru yontem:** Istatistiksel transfer — `gray_r = (gray_r - mu_r) * (sig_l / sig_r) + mu_l`. Bu, sag kamerayi sol kameranin istatistiklerine eslerken dinamik aralik koruyor.

### CLAHE ile kontrast artirma (2026-08-17'de OLCULDU ve KAPATILDI)
**Ne oldu:** Onceki oturumda iki kamera arasi parlaklik farkini gidermek icin
CLAHE (clipLimit=2.0) eklendi. Derinlik haritasi gozle fark edilir sekilde
**parcalandi** — duz duvarlarda ani derinlik sicramalari, sahte bloblar.

**Olcum (14 Agustos'un 6 gercek stereo cifti, ayni veri, farkli pipeline):**

| Konfigurasyon | Ort. sicrama | >2px sicrama |
|---|---|---|
| CLAHE yok + parlaklik esleme + blur | **0.361** | **%1.5** |
| Eski kod (72cc70a: on-isleme yok) | 0.363 | %1.7 |
| CLAHE 1.0 | 0.399 | %1.9 |
| CLAHE 1.5 | 0.408 | %2.0 |
| CLAHE 2.0 | 0.419 | %2.1 |

**Teknik neden:** CLAHE yerel kontrasti artirir. Duz/dokusuz yuzeylerde
(duvar, tavan, masa) yukselttigi sey **sensor gurultusu** olur — SGBM bunu
gercek doku sanip sahte eslesme uretir. Etki clipLimit ile dogru orantili.
Merkez mesafe degeri etkilenmiyor (557-563 mm, hepsinde ayni), bozulan
**haritanin butunlugu** — yani kontur/hacim tabanli olcum (measurement.py)
icin onemli.

**Karar:** CLAHE varsayilan KAPALI, Derinlik tabinda acilabilir kutucuk.
Parlaklik eslemesi ve GaussianBlur KALDI — o ikisi haritayi bozmuyor,
hafifce iyilestiriyor. `uniquenessRatio` da eski degerine (15) donduruldu;
10'a dusurulmustu, bu dokusuz bolgelerde belirsiz eslesmeleri kabul ediyor.

### DSHOW backend
**Ne oldu:** Bazi kamera ayarlari (WB, exposure) iki kamerada tutarsiz uygulaniyordu.
**Neden:** DSHOW her kamera icin farkli kontrol yolu kullaniyor, bazi property'ler sessizce basarisiz oluyor.
**Sonuc:** MSMF'ye gecildi (commit 59d84ad).

### SGBM parametrelerini agresif kucultme
**Ne oldu:** P1/P2'yi dusurme (blockSize=5, P1=8*3*25, P2=32*3*25), uniquenessRatio=5, speckleWindowSize=100 denendi. Dusuk isikta gurultu patladi.
**Teknik neden:** P1/P2 penalty terimleri komsu pikseller arasindaki disparity farki icin ceza verir. Dusuk P1/P2 = daha az yumusaklastirma = daha fazla gurultu. Dusuk isikta (ev ortami, aksam) gurultu zaten yuksek, dusuk penalty bunu katliyor.
**Dogru degerler:** blockSize=7, P1=8*3*49, P2=32*3*49, uniquenessRatio=10, speckleWindowSize=200.

### Epipolar check scripti (ORB + BFMatcher crossCheck)
**Ne oldu:** Script 84.67 px medyan Y hatasi rapor etti — "kalibrasyon gecersiz" sonucu. Ama ayni kalibrasyon ile makul mesafe okumalari (476-511mm at ~50cm) aliniyordu.
**Teknik neden:** ORB feature'lari dusuk isikli, az dokulu ortamda cok az ve kalitesiz match uretir. BFMatcher crossCheck yeterli degil — ratio test (knnMatch + Lowe's ratio) olmadan outlier'lar baskin. 84px "hata" buyuk ihtimalle yanlis match'lerden, gercek epipolar hatadan degil.
**Sonuc:** Epipolar kontrol scripti guvenilir degil, SIFT + ratio test veya rectified goruntude feature matching yapilmali. Ama mevcut kalibrasyon ile olcumler tutarli oldugu icin acil degil.

---

## 6. BILINEN ACIK RISKLER / COZULMEMIS SORUNLAR

### Kalibrasyon RMS hedefin ustunde
Mevcut (`calib_result.npz`'den okundu): **RMS 0.7407 px** (sol 0.5950, sag 0.6241). CLAUDE.md hedefi < 0.4 px; `calibration.py` cozunurlukle olcekli limit kullanir: `0.4 x (2048/960) = 0.853 px` — bu sinirin altinda, yani gecerli. Rapor icin ideal degil. Iyilestirme: daha fazla ve daha temiz kare, hareket bulanikligi olmadan.

### Yakin mesafede disparity kararsizligi (YENI — 2026-08-16)
Kaydedilmis 10 gercek cekim iki farkli SGBM parametre setiyle yeniden islendi:

| Mesafe bandi | Parametre setleri arasi fark |
|---|---|
| Uzak (d≈45-60 px, ~1700-2000 mm) | %2-10 — **kararli** |
| Yakin (d≈150-215 px, ~480-660 mm) | %2-**69** — **kararsiz** |

Ornek: bir cekimde blockSize=9/λ=12000 → 213.9 px (476 mm), blockSize=7/λ=8000 → 108.5 px (937 mm). Iki olasi neden:
1. **ROI derinlik siniri uzerinde** — merkez ROI cisimle arka plani birlikte kapsiyor, kucuk parametre degisimi medyanin hangi yuzeye dustugunu degistiriyor. (Kaydedilmis overlay goruntuleri bunu destekliyor: nisan isareti kapi kenarinda.)
2. Yuksek disparity (256'lik arama araliginin ust ucu) + yakin cisimde perspektif farki eslemeyi zorlastiriyor.

**Ayirt etmek icin kontrollu test gerekli:** duz, dokulu bir hedefi (doku deseni kagidi) tam merkeze, bilinen mesafeye koy; ROI tek yuzeyde kalsin. Fark kaybolursa neden (1), surerse neden (2).

### Zemin cikarma yalnizca tahtanin civarinda guvenilir (2026-08-19)
Duzlem ~600 mm'de ~200 mm'lik bir tahtadan cikariliyor, sonra tum
sahneye uzatiliyor. `q_20260819_165521` uzerinde olculdu (duzlem
79.9 derece, bagimsiz RANSAC ile **1.6 derece** uyum — yani duzlem
dogru):

| | Oran |
|---|---|
| Duzlem uzerinde (h < 15 mm) | **%11.7** |
| esik 12 mm ile atilan | %26.9 |
| Kalan | %73.1 |

Cerceve genisken masa sahnenin ancak %12'si; duvar/raf/oda gercekten
duzlemin uzerinde (h medyani %50'de 85 mm, %90'da 866 mm) ve dogru
sekilde korunuyor. Ayrica ekstrapolasyon hatasi: **1 derecelik fit
hatasi 2000 mm'de 35 mm** yukseklik hatasi yapar, 12 mm'lik esigin
uc kati; uzak yamalar duzlemin bazen ustune bazen altina duser.

**Kural:** zemin cikarma tespit tahtasinin +-300-400 mm civarinda
guvenilir, genis sahnede bir sey izole etmez. Tiklayarak olcum bundan
bagimsiz calisir (tohum etrafinda ayrica 250 mm'lik 3B uzaklik siniri
uygular).

### Kutu gorseli varsayilan olarak HAM haritayi okur (2026-08-19)
`kutu_gorsel.py` varsayilan olarak `disparity_ham` anahtarini kullanir.
Yani Derinlik tabindaki "Zemin/masa cikar" kutucugu ekrandaki haritayi
degistirir ama **kutu gorseline girmez**. Bu bir kez yanlis nedene
baglandi ("esigi 50 yapinca duzeldi" — aslinda tolerans/parlaklik
ayarindan geliyordu). Zemin cikarilmis haritayi kullanmak icin
`--zemin` bayragi / "zemin haritasi" kutucugu gerekir.

### Egik bakis: cismi destek yuzeyinden ayirmak zor (2026-08-19)
Kamera masaya ~80 derece ile bakiyor. Sonuclari:
- Yukseklik gozlenebilirligi `cos(aci)` = **0.177**
- Blok esleme egimle bozulur: `dd/dx = B*tan(aci)/Z`, 79.8 derecede
  7 px'lik blok boyunca **3.99 px** disparity degisimi
- Derinlik tek basina cisimle masayi ayiramaz (tabanda sicrama yok)

Parlaklik + kenar kisitlari bunun cogunu kurtariyor ama cisim koyu bir
zeminde (orn. laptop) dururken yukseklikte ~%16 tasma kaliyor.
60 derecelik kati kural **uyariya** cevrildi (kamera tasinamiyor).

### ChArUco tekrarli desen: tahtada stereo esleme bozulabiliyor (2026-08-20)
Tahta sahnedeyken olculdu - tahta masaya tam duz yatiyor (tahta ve
cevre masa duzlemleri arasi aci 0.22 derece, kalinlik 2.1 mm), ama
tahtanin UZERINDEKI derinlik bozuk:

| | Bu cekim | Saglikli cekim |
|---|---|---|
| Tahtada mesafe dagilimi | **410 - 656 mm** | ~25 mm |
| Disparity salinimi | **37.4 px** | 8.9 px |
| Olculen kare boyu | 21.68 mm | 20.0 mm |

Duz bir tahtanin mesafesi 250 mm'lik aralikta saçilamaz. ChArUco
periyodik bir desen; blok esleme bazi bloklarda yanlis kareye
kilitleniyor. Cevredeki duz beyaz masa temiz olculuyor (kalinti
1.64 mm) - sorun desenin periyodikliginde.

Uygulama artik tahtadaki disparity salinimi 20 px'i asarsa
"TAHTADA DERINLIK BOZUK" uyarisi veriyor. Pratik cozum: tahtayi
~650 mm'ye uzaklastir (saglikli tespitlerin hepsi 590-653 mm).

### Zemin esigi negatif olabilir ama egimi telafi etmez (2026-08-20)
Esik alt siniri -60 mm'ye acildi (tespit edilen duzlem masa degil
tahtanin UST yuzeyi). Ama gercek masa pikselleri uzerinde olculdu:
ortalama sapma -44.2 mm (esikle kapatilabilir), salinim 20.4 mm ve
%5-%95 yayilimi 69 mm (kapatilamaz - egimden). Aci farki 7.8 derece,
masanin gorunen genisligi 484 mm; 484 x tan(7.8) = 66 mm yayilimi
tam olarak aciklıyor. Egik duzlem kaydirmakla duzelmez.

### Gurultu darbogaz DEGIL - segmentasyon darbogaz (2026-08-20)
46 adet 120x120 masa yamasinda yerel duzlemsel sacilim **1.15 mm**
(0.44 px disparity gurultusu; olculen epipolar hata 0.420 px ile
tutarli). Gordugumuz olcum hatalari 30-60 mm, yani sensor
gurultusunun 30-50 kati.

Gurultunun yone gore dagilimi (oran = Z/B):

| Z | YANAL | DERINLIK | oran |
|---|---|---|---|
| 400 mm | 0.28 mm | 1.57 mm | 5.6x |
| 550 mm | 0.39 mm | 2.97 mm | 7.7x |
| 1000 mm | 0.71 mm | 9.82 mm | 13.9x |

Sanal kamera dondurme bunu degistirmez (gurultu de doner). Baz
uzunlugunu buyutmek de listede yok - gurultu zaten sinirlayici degil.

### Crosshair hizalama sorunu (cozuldu ama dikkat gerekli)
Goruntu merkezindeki olcum noktasi cismin uzerine denk gelmeyebilir. Tiklayarak olcum eklendi ama kullanici bunu bilmeli. Ozellikle:
- Kameralar asagi/yukari egimliyse, merkez arka plana bakabilir
- Kucuk cisimler 50x50 ROI'nin kucuk bir kismini kaplayabilir, medyan arka plana kayar
- Duz/parlak/dokusuz cisim yuzeylerinde SGBM esleme basarisiz olur, disparity=0, o pikseller medyandan cikar, kalan pikseller arka plan olabilir

### KOK NEDEN: _apply_all tum ozellikleri yazmiyordu (2026-08-17, COZULDU)
Uzun sure "iki kamera farkli goruntu veriyor" sorunu arastirildi. Sirayla
sunlar suclandi ve **hepsi yanlis cikti**: acilis yarisi, lens diyaframi,
koruyucu film, sensor duyarlilik farki, ISP/ton egrisi farki.

**Gercek neden:** `_apply_all()` yalnizca WB/CONTRAST/SATURATION/SHARPNESS ve
pozlama-gain-parlaklik yaziyordu. **GAMMA, HUE, BACKLIGHT hic yazilmiyordu.**
Bu ozellikler kamerada KALICI saklandigi icin gecmiste yazilan degerler
oylece kaliyor, iki kamerada farkli oluyordu (olculdu: GAMMA 200 vs 100).
MSMF geri okumasi bozuk oldugu icin bu fark **gorunmez**di.

**Kanit — 11 ozelligin tamami ayni degere yazildiginda:**

| Pozlama | SOL | SAG | Oran | SOL std | SAG std |
|---|---|---|---|---|---|
| −5 | 72.0 | 71.1 | 1.01x | 44.1 | 40.7 |
| −4 | 120.0 | 120.5 | **1.00x** | 65.5 | 61.7 |
| −3 | 170.2 | 173.3 | 1.02x | 75.3 | 71.2 |

Ortalama parlaklik orani **1.02x**, kontrast orani 1.09x → kameralar ozdes.
Onceki 2.7x'lik farkin tamami ayar kaynakliymis.

**Ders:** MSMF'de `cap.get()` ile ayar dogrulanamaz. Tek guvenli yol
TUM ozellikleri her acilista acikca yazmaktir. Bir ozelligi yazmayi
atlamak = o ozelligin kamerada kalmis eski degerini kullanmak.

### Kameralar ayarlari HAFIZASINDA saklıyor — ve ikisi farkliydi (2026-08-17)
Kalicilik testi: bir degeri yaz, kamerayi kapat-ac, deger **duruyor**. Yani
gecmiste yapilan her ayar kamerada kalici iz birakiyor.

DSHOW ile okunan gercek durum (MSMF geri okumasi bozuk oldugu icin DSHOW sart):

| Ozellik | SOL (idx2) | SAG (idx1) | Etki |
|---|---|---|---|
| EXPOSURE | −6 | −3 | **3 kademe = 8x parlaklik** |
| GAMMA | 200 | 100 | ton egrisi farki |
| SHARPNESS | **50** | 5 | 50, kameranin bildirdigi 0-10 araliginin DISINDA |
| GAIN | −1 | 0 | −1 = desteklenmiyor/otomatik |
| BACKLIGHT | 0 | 1 | |

**Bu, uzun sure "donanimsal lens/diyafram farki" sanilan seyin gercek nedeni.**
Onceki teshisler (koruyucu film, diyafram farki, ISP farki) YANLISTI.

### GAMMA: SOL kamerada kismen bozuk
Tarama sonucu:
- **SOL (idx2):** 200'un altini REDDEDIYOR; 200-500 arasi kabul ama parlakliga
  etkisi yok denecek kadar az (145→165).
- **SAG (idx1):** 72-500 tamami calisiyor, parlaklik 49.7 → 175.1.

Ayni gamma degerinde iki kameranin parlakligi: 200→1.32x, 250→1.18x,
**300→1.07x**. Bu yuzden ortak deger **GAMMA=300** secildi (100 degil).


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

`src/kamera_ayar_sifirla.py` iki kameraya ayni degerleri yazar,
`src/kamera_default_kontrol.py` mevcut durumu ve kaliciligi raporlar.
Ayarlar kamerada saklandigi icin DSHOW ile bir kez yazmak yeterli;
camera_test.py MSMF ile acsa bile devralir.

### MSMF geri okumasi BOZUK — kamera ayarlari icin (2026-08-17 olculdu)
`cap.get(...)` MSMF'de yanlis deger donuyor: ne yazarsan yaz EXPOSURE hep -6,
CONTRAST hep 32, SHARPNESS hep 3 okunuyor. **Ama ayar gercekte uygulaniyor** —
gercek kare parlakligi olculunce goruluyor:

| Ozellik | MSMF etki | MSMF geri okuma | DSHOW |
|---|---|---|---|
| EXPOSURE | calisiyor (0.4→238) | BOZUK | calisiyor / dogru |
| GAIN | calisiyor (56→118) | BOZUK | calisiyor / dogru |
| BRIGHTNESS | calisiyor (48→119) | BOZUK | calisiyor / dogru |
| CONTRAST | calisiyor (std 27→44) | BOZUK | calisiyor / dogru |

**Sonuc:** DSHOW'a gecmeye gerek yok, kontrol zaten var. Ama koda `cap.get()`
ile ayar dogrulamasi YAZILMAMALI — durum cubugu artik kameradan okumak yerine
kullanicinin ayarladigi degeri gosteriyor.

### Pozlama -2 sensoru doyuruyor
Olcum (2048x1536, oda isigi): poz=-2 → iki kamera da ~245 (doymus, std 9),
poz=-3 → 223/219, **poz=-5 → 104/150 (saglikli)**, poz=-7 → 15/6 (cok karanlik).
Kullanilabilir bant **-5 … -3**. Doymus goruntude doku kalmadigi icin SGBM
calisamaz — "el mavi cikiyor" tipi hatalarin bir nedeni budur.

### Iki kameranin ton egrisi farkli (donanimsal)
Ayni ayarla olculdu: SOL p5=92 / std=38.6, SAG p5=47 / std=63.3. Ortalama
parlaklik esitlenebiliyor (gain telafisiyle fark 4.3'e iniyor) ama **dagilim
farki kaliyor** — sol duz/yikanmis, sag kontrastli.

Dogrusal mean/std transferi bu **dogrusal olmayan** farki duzeltemez:

| Yontem | Ton farki (gercek cift) | Harita sicramasi |
|---|---|---|
| Duzeltme yok | 46.80 | 0.964 |
| Dogrusal (eski varsayilan) | 4.60 | 0.799 |
| **Histogram (CDF) — yeni varsayilan** | **0.20** | **0.795** |

Derinlik tabinda "Kamera ton eslemesi" secenegi eklendi, varsayilan Histogram.

### Parlaklik farki oturum icinde KARARLI, sahneye gore DEGISKEN
30 sn izleme: SOL salinim 1.1, SAG salinim 0.9, **fark salinimi 0.3** — otomatik
pozlama gercekten kapali, ayarlar tutuyor. Ama fark sahne/isiga gore degisiyor
(bir olcumde SAG 36 birim karanlik, digerinde 46 birim parlak).

**Bu yuzden gain telafisi ayar dosyasina GOMULMEZ.** Ayarlar tabina
**"Otomatik esitle"** butonu eklendi — gain telafisini o anki sahnede olcup
ayarliyor. Isik/sahne degisince tekrar basilmali.

### Renk olcegi: kare-bazli vs sabit
Gorsellestirme `dsp / dsp.max() * 255` ile olcekliyordu. `numDisparities=256`
oldugu icin `dsp.max()` pratikte hep ~250-255 cikiyor, yani bolen sabit —
renkler kareler arasi zaten kabaca karsilastirilabilirdi. **Ancak** bu, calisma
araligini (300-900 mm) yalnizca 113-255 gri bandina sikistiriyor.

Eklenen "Sabit (Z_min..Z_max)" secenegi araligi 0-255'in tamamina yayar
(~1.8x daha iyi renk ayrimi) ve olcek fiziksel anlam tasir. Varsayilan: sabit.

Not: Gorsellestirme kodu 72cc70a ile birebir ayni (28 satir kontrol edildi) —
renk farki algisi buradan gelmiyor.

### Arayuz kasmasi: derinlik ana thread'de hesaplaniyordu (2026-08-17, COZULDU)
FPS sayaci 31 gosteriyordu ama uygulama kasiyordu. Sebep: sayac **yakalama**
thread'ini olcuyor; derinlik hesabi ise `_update_display` icinde, yani **ana
thread'de** yapiliyordu.

Profil (2048x1536):

| Adim | Sure |
|---|---|
| SGBM sag (right matcher) | 396 ms |
| SGBM sol | 347 ms |
| WLS filtre | 100 ms |
| Histogram ton esleme | 30 ms |
| remap + digerleri | 47 ms |
| **TOPLAM** | **920 ms** |

Yani arayuz her karede ~920 ms doniyordu. **Cozum:** `_depth_worker` adli
ayri thread; `_update_display` sadece hazir sonucu okuyor.

### Canli onizlemede cozunurluk dusurme — SADECE onizleme icin
Hiz kazanci gercek: 1.0 → 808 ms, 0.75 → 330 ms, **0.5 → 127 ms**, 0.35 → 72 ms.

**Kalibrasyonu bozmaz** cunku rektifikasyon (`remap`) her zaman TAM
cozunurlukte yapilir — kalibrasyon parametreleri yalnizca orada kullanilir.
Rektifiye cift kucultulunce epipolar hizalama korunur; SGBM sonrasi disparity
haritasi tam cozunurluge buyutulup degerleri `1/olcek` ile carpilir.

**AMA olcum icin kullanilamaz.** Sentetik testte %0 hata cikti, ancak gercek
stereo ciftlerde:

| Cekim | Tam (1.0) | Yari (0.5) | Sapma |
|---|---|---|---|
| 20260814_151242 | 451 mm | 453 mm | %0.3 |
| 20260814_164851 | 678 mm | 672 mm | %0.9 |
| **20260814_151124** | **566 mm** | **904 mm** | **%59.8** |

Kucultme, eslesmeyi saglayan ince yapiyi yok edip medyani baska yuzeye
kaydirabiliyor. Bu yuzden onizleme modunda olcum etiketi "ONIZLEME" olur ve
`[V]` dogrulama **reddedilir**; olcumler yalnizca tam cozunurluklu
"Kaliteli Tek Kare [F]" ile alinir.

> **Ders:** Sentetik veri (duz, sabit disparity'li yuzey) bu tur bir bozulmayi
> gostermez. Olcek/parametre degisiklikleri **gercek stereo ciftlerle**
> dogrulanmalidir.

### Cisim yonu: dikey iyi, yatay kotu (2026-08-18 olculdu)
SGBM eslesmeyi YATAY tarama satirinda arar; disparity yatay bir kaymadir.
Bu yuzden yapinin yonu dogrudan kaliteyi belirler:

- **Dikey kenar** tarama satirini dik keser -> kayma net olculur.
- **Yatay kenar** tarama satiri BOYUNCA uzanir -> yatay kaydirinca goruntu
  ayni kalir, kayma belirlenemez (klasik *aperture problem*).

6 gercek rektifiye ciftte olculen ham eslesme orani:

| Bolge | Eslesme |
|---|---|
| Dikey yapili | **%67.1** |
| Yatay yapili | **%51.0** |

Ortalama **1.32x**, en keskin karede **3.02x** (%69.1 vs %22.9).

**Pratik sonuc:** cisim dik dururken iyi olculur, yatirilinca zorlanir.
Yatay yuzeyler ayrica kameraya egik (bu kurulumda 43.5 derece) baktigi icin
blok eslesmenin "iki goruntude ayni gorunur" varsayimini da zorlar.
Dogrulama olcumlerinde cismi mumkunse dik konumlandirmak, degilse uzerine
dikey bilesenli doku (`patterns/sgbm_doku_desenleri_v2.pdf`) koymak gerekir.

### Yansima hayalet derinlik uretir, golge URETMEZ (2026-08-18 olculdu)
Zeminde beliren anlamsiz derinlik bloblarinin kaynagi arastirildi.
Sol-sag tutarlilik kontrolu, 6 gercek cift:

| Bolge | Tutarsizlik | Orta tona gore |
|---|---|---|
| Koyu (golge adayi) | %27.1 | 1.12x |
| Orta ton (referans) | %24.1 | — |
| **Parlak (yansima)** | **%58.7** | **2.44x** |

**Neden zit yonde davraniyorlar:**
- **Golge** yuzeye YAPISIKTIR. Iki kamera onu ayni fiziksel noktada gorur,
  yani gecerli dokudur ve eslesmeye YARDIM eder. Golgeden kacinmaya gerek
  yok.
- **Yansima/parlama** BAKIS ACISINA BAGLIDIR. Parlak leke iki kamerada
  farkli fiziksel noktada durur; SGBM lekeyi lekeye eslestirip yanlis
  disparity uretir. Sonuc: duzlemin uzerinde duruyormus gibi gorunen
  hayalet bloblar - zemin cikarma bunlari silemez cunku gercekten
  duzlemden uzakta hesaplanirlar.

**Cozum yansimayi kaynaginda azaltmaktir:** mat ortu sermek, isigi
yuzeye dik degil yandan/yayvan vermek, parlak masayi dogrudan
kullanmamak. Yazilimla duzeltilemez.

### minDisparity ile yakina kaydirma - UZAK ARKA PLANDA ZARARLI (2026-08-18)
SGBM `[minDisparity, minDisparity+numDisparities)` tarar. minDisparity'yi
buyutmek pencereyi yakina kaydirir ve maliyeti ARTIRMAZ (maliyet
numDisparities ile orantili):

| md | nd | Aralik | Olu kenar | Maliyet |
|---|---|---|---|---|
| 0 | 256 | 399 mm - sonsuz | %12.5 | 1.0x |
| 128 | 256 | 266 - 795 mm | %18.8 | 1.0x |
| 0 | 384 | 266 mm - sonsuz | %18.8 | 1.5x |

**AMA acik sahnede kullanilamaz.** Gercek ciftlerde olculdu:

| | md=0 | md=192 |
|---|---|---|
| Sahnenin 530 mm otesi orani | %51-79 | **%0-1** |
| Ham eslesme | %96-99 | **%100** |
| Merkez Z (bir cekim) | 442 mm | **261 mm** |

**Teknik neden:** pencerenin disindaki uzak pikseller GECERSIZ OLMUYOR,
pencere icine SIKISTIRILIYOR - yakin gibi hesaplaniyorlar. Ustelik ham
eslesme orani %100'e cikiyor cunku SGBM zorla bir eslesme buluyor;
kalite gostergesi yaniltici derecede iyi gorunuyor.

**Kural:** md>0 yalnizca cercevede uzak hicbir sey yokken (kapali olcum
kutusu, tepeden bakan dar cerceve) kullanilabilir. Suphedeysen md=0.
Uygulama md>0 secilince uyari gosterir ve pencerenin uzak ucunda
yigilma (%10+) tespit ederse cekim satirinda "SAHNE ARALIK DISINA
TASIYOR" yazar.

### Bolgedeki baskin duzlemi RANSAC ile atma (2026-08-19)
**Ne oldu:** Cismi destek yuzeyinden ayirmak icin segmentlenen bolgede
RANSAC ile duzlem arandi ve atildi. RANSAC bolgenin **%69-100'unu**
duzlem bulup cismi sildi.
**Teknik neden:** Bolge zaten ince bir derinlik dilimi, yani **kendisi
duzlemsel**. Ayirmak istedigimiz iki sey de ayni kriteri sagliyor.
**Sonuc:** Varsayilan KAPALI. Ayrica tohum duzlemin uzerinde kalinca
kod sessizce en buyuk bilesene dusuyordu ve bu **masa kenarini olcup
termos diye raporlamisti**; artik "TIKLANAN NOKTA DESTEK YUZEYINDE"
hatasi verir.

### Aday bolgeleri "beklenen olcuye sayisal yakinlik" ile secmek
**Ne oldu:** Birden fazla tohum denenip sonuclar termosun bilinen
olculerine yakinliga gore puanlandi; en iyi puanli 234x55x39 secilip
"termos olculdu" diye sunuldu. **Gercekte masa kenariydi.**
**Teknik neden:** Beklenen cevaba yakinlik, dogru seyi olctugunun
kaniti degil — yanlis bir bolge de tesadufen yakin sayi uretebilir.
**Dogru yontem:** `kutu_gorsel.py` ile kutuyu goruntu uzerine ciz;
kutu cismi sariyorsa dogru, cevreye tasiyorsa bolge kacmis.
**Bu yuzden renk kodu eklendi:** her ana eksenin kenarlari ve sol
ustteki olcusu ayni renkte (UZUN yesil, ORTA acik mavi, KISA pembe).

### Duvarlari floodFill'e verip toleransi serbest birakma (2026-08-20)
**Ne oldu:** kenar/basamak engelleri cismin sinirini cok iyi buluyor
(siluet |grad I| 108.3 vs cismin ici 5.7 - 19 kat ayrim). Toleransi
serbest birakip durdurmayi duvarlara birakmak denendi.
**Olculen:** kenar30+basamak3 kapsam %43 saflik %9; kenar20+basamak2
%39 / %87; kenar80+basamak10 %98 / %17. Bosluk kapatma 3-9 px de
duzeltmiyor.
**Teknik neden:** TOPOLOJIK sart - floodFill'in tutmasi icin duvarin
HER YERDE kapali olmasi gerekir. Olculdu: siluetin en fazla %86'si
duvar oluyor, kalan %14'un tek pikselinden bolge kaciyor.
**Cozum:** watershed - kapali cevrit gerektirmiyor (%99 kapsam,
%93 saflik).

### "Komsuya gore yayil" (FLOODFILL_FIXED_RANGE kapali)
**Ne oldu:** bolge tohumla degil komsuyla kiyaslansin, kademeli
degisimde yayilsin, sicramada dursun.
**Olculen:** bolge karenin **%68-81**'ine yayiliyor - basamak engeli
acikken bile, her toleransta.
**Teknik neden:** masa yumusak bir rampa; cisimden odanin her yerine
dusuk basamakli bir yol var. Yayilarak calisan kriterin capasi yok.

### Watershed'e derinligi karistirma (2026-08-20)
**Ne oldu:** watershed'in ustunde yurudugu goruntuye parlakligin
yanina derinlik de eklendi.
**Olculen:** kapsam %99 -> %60-82, saflik %93 -> %45-69.
**Teknik neden:** derinlik haritasi WLS ile yumusatilmis, kenarlari
parlaklik kadar keskin degil.
**Sonuc:** watershed yalnizca parlaklik uzerinde calistirilir.

### Dokusuz yuzeyler
SGBM blok esleme tabanli — tekrar eden veya tamamen duz yuzeyler (beyaz duvar, parlak metal, cam) icin disparity uretemiyor. `patterns/sgbm_doku_desenleri_v2.pdf` bu amacla basildi: cismin uzerine veya arkasina doku deseni konularak esleme kalitesi artirilabilir.

### Kamera odagi
M12 lens odagi kalibrasyondan sonra degisirse tum kalibrasyon gecersiz olur. Lens vidalari gevsetiyse (3B basili govde titresimle oynayabilir) sessizce bozulma olabilir. Belirtisi: epipolar hata artar, disparity haritasi kotulesir, mesafe okumalari kayar. Kontrol: netlik skoru (Laplacian varyans) zamanla dusuyorsa odak oynamis olabilir.

### USB bant genisligi
Iki kamera tek USB controller'a baglanirsa bant genisligi paylasilir. 2048x1536 MJPG'de genelde sorun yok ama 4K veya YUY2 formatinda frame drop olabilir. Farkli USB controller'lara (farkli fiziksel portlar) baglamak guvenli.

### Sicaklik etkisi
Kalibrasyon oda sicakliginda yapilir. Ciddi sicaklik degisimi (15°C+) lens ve govde boyutlarini degistirebilir — muhtemelen ihmal edilebilir ama raporda bahsedilmeli.

---

## 7. SU ANKI DURUM

### Tamamlanan asamalar
- [x] Kamera test araci (camera_test.py) — tam calisiyor, 7 tab GUI
- [x] Kalibrasyon (calibration.py) — ChArUco 9x13, 2048x1536, RMS 0.73
- [x] Zemin duzlemi (ground_plane.py)
- [x] Olcum pipeline (measurement.py)
- [x] Kutu onerisi (box_output.py)
- [x] Canli derinlik haritasi (SGBM + WLS + renk haritasi + konturlar)
- [x] Kaliteli tek kare (F modu) — 10 frame ortalama + ozenli SGBM
- [x] Tiklayarak olcum — sol goruntuye tikla, o noktanin mesafesini olc
- [x] Mesafe dogrulama (V tusu) — gercek vs olculen karsilastirma + CSV kayit
- [x] Preprocessing: CLAHE + istatistiksel parlaklik esleme + GaussianBlur
- [x] Temporal median (5 frame) canli modda stabilite
- [x] Tiklayarak PCA olcumu (duzlemsiz) — tolerans/parlaklik/kenar kisitli
- [x] Duzlemle olcum + taban geri kazanimi + yuvarlak cisim duzeltmesi
- [x] Kutu gorseli (`kutu_gorsel.py`) — renk kodlu 3B kutu + nokta bulutu
- [x] Zemin duzlemi uygulama icinde tespit (rektifiye cercevede)
- [x] Set yedekleme/geri yukleme (`Yeni Set Baslat`) — gidis-donus test edildi
- [x] Arayuz: kaydirilabilir tablar, katlanabilir bolumler, zoom + tiklama

### Kalibrasyon sinirlayici etken DEGIL (2026-08-19 olculdu)
44 cift / 3264 kose uzerinde epipolar hata **0.420 px**. RMS tabani
~0.44 px ve bu **kose lokalizasyon gurultusu** — kare atarak RMS
dusuruluyor ama epipolar hata **kotulesiyor**. Distorsiyon modelini
buyutmek de fayda vermedi. Mevcut olcum hatalarinin kaynagi
kalibrasyon degil; goruntu geometrisi (egik bakis) ve segmentasyon.
Olcumun kendi oturma sacilimi ~%4.3.

### Sirada ne var
1. **Dogrulama testleri** (rapor icin):
   - Mesafeye gore hata egrisi (5.2) — en az 4 farkli mesafede
   - Tekrarlanabilirlik testi (5.3) — ayni mesafede 10 olcum, std sapma
   - Calisma zarfi (5.4) — minimum/maksimum mesafe
   - Ana sonuc tablosu (5.9) — 5 cisim x 3 boyut
2. **Fiziksel dogrulama** (5.10) — kesim yonergesiyle kutu
3. **Rapor yazimi** (Ek-4 docx sablonu)
4. **Desen olcusunu kumpasla dogrula** — 5 kare olcup 5'e bol
   (`charuco_config.json`'daki 20.0 mm bu sekilde teyit edilmeli)

---

## 8. KOD KONVANSIYONLARI

### Ortam
- **OS:** Windows 11 Pro
- **GPU:** NVIDIA RTX 3050 Laptop (4GB VRAM, compute capability 8.6)
- **Conda env:** `stereo`
- **Python:** 3.11.15
- **OpenCV:** 4.10.0 (CUDA destekli build, ama su an GPU kullanilmiyor)
- **Python yolu:** `C:\Users\nvflb\miniconda3\envs\stereo\python.exe`
- **Diger kutuphaneler:** numpy, Pillow (ImageTk), tkinter (stdlib)

### NASIL CALISTIRILIR — `python` komutu CALISMAZ
PATH'teki `python`, conda **base** ortamini gosteriyor
(`C:\Users\nvflb\miniconda3\python.exe`) ve orada **cv2 YOK**.
Dogrudan `python src\camera_test.py` calistirmak
`ModuleNotFoundError: No module named 'cv2'` verir.

Ayrica **PowerShell profili yok** — `conda init powershell` hic calistirilmamis,
bu yuzden PowerShell'de `conda activate stereo` de calismaz.

Calistirma yollari:

| Yontem | Komut |
|---|---|
| **Baslatici (onerilen)** | `.\calistir.ps1` veya `.\calistir.bat` (cift tikla) |
| Baska script | `.\calistir.ps1 depth_view` / `.\calistir.bat odak_test` |
| Tam yol | `& "C:\Users\nvflb\miniconda3\envs\stereo\python.exe" src\camera_test.py` |
| VS Code terminali | `.vscode/settings.json` PATH'e stereo'yu ekler, orada `python` calisir |

Kalici cozum isteniyorsa: `conda init powershell` (PowerShell profilini olusturur,
sonra `conda activate stereo` calisir). Sistem ayarina dokunmamak icin baslatici
scriptleri tercih edildi.

**Kod icinde:** alt surec baslatirken `"python"` DEGIL `sys.executable` kullanilmali
(camera_test.py'de kalibrasyon/zemin/odak scriptlerini boyle cagiriyor).

### Isimlendirme
- Degisken/fonksiyon: snake_case (Ingilizce)
- UI metinleri, yorumlar, rapor: Turkce
- Dosya isimleri: Ingilizce (camera_test.py) veya Turkce (olcum_defteri.csv)
- Kalibrasyon parametreleri: OpenCV konvansiyonu (K1, D1, R1, P1, Q, T)

### Kamera indeksleri
- Sol kamera: `left_idx` (varsayilan 1)
- Sag kamera: `right_idx` (varsayilan 2)
- `data/camera_settings.json`'dan yuklenir, GUI'den degistirilebilir

### Birim sistemi
- Kalibrasyon (calibration.py): **metre** — `sq / 1000.0` ile mm'den cevrilir
- T vektoru: metre (||T|| = 0.0716m = 71.6mm)
- Q matrisi: metre biriminde
- reprojectImageTo3D ciktisi: metre
- UI'da gosterim: mm (`* 1000` ile cevriliyor)
- camera_settings.json'daki exposure degerleri: log2 skalasi (orn. -2 = 1/4x)

### IKI FARKLI f_px VAR — karistirma!
Bu projede iki ayri odak uzunlugu dolasiyor, ikisi de dogru ama farkli yerlerde kullanilir:

| Deger | Kaynak | Ne zaman kullanilir |
|---|---|---|
| **1291.8 px** | `K1[0,0]` — ham (rektifiye edilmemis) intrinsik | solvePnP, ham goruntu geometrisi. `olcum_defteri.csv`'de `fx_sol` olarak bu yazili. |
| **1420.04 px** | `P1[0,0]` — rektifiye projeksiyon matrisi | **Mesafe/deltaZ hesabi.** Disparity rektifiye goruntude olculdugu icin dogru olan budur. |

`Z = f * B / d` ve `deltaZ = Z² * delta_d / (f * B)` formullerinde **P1[0,0] = 1420** kullanilmali. Hesaplama tabi kalibrasyon yuklendiginde bu degeri otomatik doldurur; hardcoded varsayilan (1292) sadece kalibrasyon yuklenmemisken gorunur ve yaniltir.

### camera_test.py yapisi
```
__init__         → state degiskenleri, _build_ui, _open_cameras
_build_ui        → PanedWindow (cam_label | notebook), 7 tab
_build_tab_*     → Her tab icin UI: settings, calc, calib, depth, measure, status, guide
_open_cameras    → Thread: MSMF backend, MJPG codec, cozunurluk ayari
_capture_loop    → Thread: grab/retrieve, Laplacian netlik, display frame hazirlama
_update_display  → 33ms timer: frame goster, derinlik overlay, crosshair, mesafe
_compute_disparity → CLAHE + brightness match + blur + SGBM + WLS + temporal median
_capture_quality_frame → 10-frame avg + ayri SGBM + freeze
_on_cam_click    → Tiklanan noktada mesafe olcumu
_verify_distance → Gercek vs olculen karsilastirma + CSV kayit
_clean_disparity → Median blur + morfoloji + kucuk bolge silme
```

---

## 9. YAPILMAMASI GEREKENLER

### GPU StereoSGM'i WLS olmadan kullanma
WLS filtresi olmadan GPU disparity haritasi cok gurultulu. Bu yol denendi ve basarisiz oldu (bolum 5). GPU ancak WLS CUDA uyumlu hale getirilirse anlamli.

### cv2.normalize ile parlaklik esleme
Dinamik aralik kaybina yol acar, derinlik haritasini dramatik olarak bozar (bolum 5). Dogru yontem: istatistiksel mean/std transfer.

### Kalibrasyon sirasinda farkli cozunurluk kullanma
Kalibrasyon 2048x1536'da yapildi. Farkli cozunurlukle (orn. 1280x960) alinmis frame'ler icin ayni kalibrasyon matrisleri KULLANILAMAZ — intrinsic parametreler cozunurluge baglidir. Ya ayni cozunurlukle calis ya da yeniden kalibre et.

### Disparity yuzdesini tum goruntu uzerinden hesaplama
numDisparities=256 ile soldaki 256 piksel daima gecersiz. Disparity yuzdesini `dsp[:, 256:]` uzerinden hesapla (bolum 4, numDisparities=256 maddesi).

### P1/P2 penalty degerlerini dusurme
Dusuk isikli ortamlarda gurultu patlar (bolum 5). Mevcut degerler (blockSize=7 bazli: P1=8*3*49, P2=32*3*49) dogru calisiyor.

### Epipolar kontrolu ORB + crossCheck ile yapma
Dusuk isik/dokusuz ortamda yaniltici sonuc veriyor (bolum 5). SIFT + ratio test veya kalibrasyon frame'leri uzerinde kontrol yapmak daha guvenilir.

### Mesafe olcumunde goruntu merkezini varsaymak
Cisim merkezde olmayabilir — arka plan mesafesi okunur. Tiklayarak olcum kullan veya cismi kesinlikle merkeze hizala.

### Olcumu "beklenen degere yakinlik" ile dogrulama
Yanlis bir bolge de tesadufen dogru sayilar uretebilir; bu bir kez
masa kenarini termos diye raporlatti. Dogrulama `kutu_gorsel.py`
ciktisinda kutunun cismi sarmasidir.

### Zemin cikarmayi "arka plani siler" diye kullanma
Yalnizca destek yuzeyini siler. Genis sahnede duvar/raf/oda gercekten
duzlemin uzerindedir ve dogru sekilde korunur (olculdu: sahnenin
%11.7'si duzlem uzerinde, %73.1 kaliyor).

### RANSAC "masayi at" secenegini varsayilan acma
Bolge zaten ince bir derinlik dilimi, yani duzlemsel; RANSAC cismi de
siler (bolgenin %69-100'unu duzlem bulur).

### Lens odagina dokunduktan sonra eski kalibrasyonu kullanma
Odak degisirse tum intrinsic parametreler gecersiz olur. Yeniden kalibrasyon sart.
