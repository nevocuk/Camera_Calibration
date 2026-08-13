# Teori Notları — Kalibrasyondan Ölçüme Matematiksel Zincir

Bu dosya sözlü sınav hazırlığı ve rapor "Yöntem" bölümü için kaynak metindir.
Tüm sayılar bu projenin kendi kalibrasyon sonuçlarındandır (`calibration/calib_result.npz`).

---

## 0. Zincirin özeti

```
3B nokta  →  [K, D]  →  piksel          (tek kamera: ölçek kayıp)
piksel    →  [R, T]  →  epipolar kısıt   (arama 2B'den 1B'ye)
          →  [R1,R2,P1,P2] → rektifiye   (epipolar çizgiler yatay)
rektifiye →  SGBM    →  disparity d
d         →  [Q]     →  metrik 3B nokta
```

Her ok bir OpenCV fonksiyonuna karşılık gelir. Aşağıda her adımın hem sezgisi hem
matematiği var.

---

## 1. İğne deliği modeli — ölçek neden kaybolur

### Matematik

```
u = fx · X/Z + cx
v = fy · Y/Z + cy

s · [u v 1]ᵀ = K · [X Y Z]ᵀ           K = ⌈ fx  0  cx ⌉
                                          |  0 fy  cy |
                                          ⌊  0  0   1 ⌋
```

### Sezgi

Görüntü, dünyanın bir duvara düşen gölgesidir. Her şey `Z`'ye bölünür. `X` ve `Z`
denkleme yalnızca **oranları** ile girdiği için, cismi iki katına büyütüp iki katı
uzağa koyduğunda piksel değeri hiç değişmez. Tek görüntüden bu iki bilinmeyen
ayrıştırılamaz — ölçek bilgisi matematiksel olarak yoktur, bulanıklık ya da
çözünürlük sorunu değildir.

İkinci kamera tam olarak bu kayıp bilgiyi geri getirmek için vardır.

### Bu projenin değerleri

| | fx (px) | fy (px) | cx (px) | cy (px) |
|---|---|---|---|---|
| Sol | 809,56 | 809,98 | 613,73 | 457,63 |
| Sağ | 812,77 | 813,66 | 663,92 | 453,35 |

**Okunacak iki şey:**

- `fx ≈ fy` (809,56 / 809,98 → binde bir fark). Piksel kare olduğu için böyle olmalı.
  Bu kural, grid board kimlik eşleme hatasının teşhisinde kullanıldı: yanlış eşlemede
  fark 24–47 piksele çıkıyordu.
- `cx, cy` görüntü merkezi olmalıydı (639,5 / 479,5) ama sol kamerada
  (613,7 / 457,6) çıktı. Sensör lense göre yaklaşık **26 piksel kaymış** monte
  edilmiş. Bu bir kusur değil, kalibrasyonun ölçtüğü gerçek bir fiziksel değerdir.

---

## 2. Lens distorsiyonu

### Matematik

```
r² = x'² + y'²

radyal      : x'' = x' · (1 + k₁r² + k₂r⁴ + k₃r⁶)
tanjansiyel : + [ 2p₁x'y' + p₂(r² + 2x'²) ]
```

`x', y'` normalize edilmiş koordinatlardır (K uygulanmadan önce).

### Sezgi

Gerçek lens ince bir cam değildir; ışın kenarlara doğru gittikçe olması gereken
yerden sapar. Fıçı distorsiyonunda düz çizgiler dışa doğru kavislenir. Kalibrasyon
bu sapmayı bir polinomla modeller ve tersini uygular.

### Bu projenin değerleri

| Kamera | k₁ | k₂ | p₁ | p₂ | k₃ |
|---|---|---|---|---|---|
| Sol | 0,0749 | −0,0922 | 0,0013 | −0,0007 | 0,0318 |
| Sağ | 0,0763 | −0,1043 | −0,0002 | −0,0007 | 0,0384 |

Görüntünün köşesinde (`r ≈ 1,03`) radyal çarpan 1,0137 çıkıyor; bu **yaklaşık
11,4 piksellik** yer değiştirme demek. Düzeltilmezse 500 mm mesafede yaklaşık 1 mm
doğrudan ölçüm hatası üretir.

**Pratik sonuç:** Distorsiyon katsayıları ancak görüntü kenarlarında veri varsa doğru
çözülür. Kalibrasyon karelerinde deseni hep ortada tutarsan RMS düşük çıkar ama
`k₁, k₂` kötü kestirilir ve hata kenarlarda ortaya çıkar.

---

## 3. calibrateCamera — ne minimize ediliyor

### Matematik

Bilinmeyenler: `K`, `D` ve her kare için tahtanın duruşu `(Rᵢ, tᵢ)`.

```
min  Σᵢ Σⱼ ‖ mᵢⱼ − π(K, D, Rᵢ, tᵢ, Mⱼ) ‖²

mᵢⱼ : i. karede j. noktanın GÖZLENEN piksel konumu
Mⱼ  : j. noktanın tahta üzerindeki BİLİNEN 3B konumu
π   : projeksiyon fonksiyonu (model + distorsiyon)

RMS = √( toplam hata² / nokta sayısı )
```

Çözüm Levenberg–Marquardt ile iteratif yapılır.

### Sezgi

Geometrisini tam olarak bildiğin bir cismi (kalibrasyon tahtası) birçok açıdan
çekersin. Kamera parametrelerini öyle ayarlarsın ki, tahtanın 3B modelini görüntüye
yansıttığında gerçekte gördüğün noktalarla üst üste otursun. RMS, bu üst üste
oturmanın ne kadar iyi olduğudur.

### ⚠ Düşük RMS doğruluk garantisi DEĞİLDİR

Bu, raporun en önemli tek cümlesi. Desen ölçüsünü yanlış girersen (örneğin 26 mm
yerine 25 mm), model kendi içinde mükemmel tutarlı kalır ve **RMS mükemmel çıkar**,
ama tüm ölçümler aynı oranda hatalı olur. RMS yalnızca iç tutarlılığı ölçer, ölçeği
değil.

Bu projede ölçek bağımsız olarak şöyle doğrulandı:

| Kaynak | Baseline |
|---|---|
| Kalibrasyonun çözdüğü ‖T‖ | 71,65 mm |
| Kumpasla fiziksel ölçüm | 72 mm |
| Fark | %0,5 |

---

## 4. stereoCalibrate — R ve T

### Matematik

```
X_sağ = R · X_sol + T
```

`CALIB_FIX_INTRINSIC` bayrağıyla `K` ve `D` sabit tutulur, yalnızca `R` ve `T` aranır.
Gerekçesi: iç parametreler tek kamerada daha çok veriyle ve daha güvenilir çözülür;
stereo adımında onları yeniden oynatmak sonucu bozar.

### Bu projenin değerleri

```
T = [ −71,58 ,  1,99 ,  2,45 ] mm        ‖T‖ = 71,65 mm
R : iki kamera arasında 2,37° bağıl dönme
```

**Bunlar fiziksel olarak okunabilir:** kameralar 71,58 mm yanda, ama aynı zamanda
2,0 mm yükseklik ve 2,4 mm derinlik farkıyla monte edilmiş; ayrıca birbirine göre
2,37° dönük. Bunlar montaj kusurlarıdır, kaçınılmazdır, ve kalibrasyonun işi tam
olarak bunları ölçmektir. Rektifikasyon bu kusurları yazılımda soğurur.

---

## 5. Epipolar kısıt — arama neden 1B'ye iner

### Matematik

```
E = [T]× R                    esas matris (metrik koordinatlar)
F = K₂⁻ᵀ · E · K₁⁻¹           temel matris (piksel koordinatları)

x₂ᵀ · F · x₁ = 0              epipolar kısıt
```

`[T]×` = T vektörünün çapraz çarpım matrisi.

> Sağlama: `[T]× R` çarpımı `calib_result.npz` içindeki `E` ile 10⁻¹⁷ mertebesinde
> uyuşuyor. Kalibrasyon dosyası kendi içinde tutarlı.

### Sezgi

Sol görüntüdeki bir piksel, 3B'de bir **ışın** demektir — o ışın üzerindeki her nokta
aynı piksele düşer. O ışını sağ kameradan seyredersen bir **çizgi** görürsün.
Dolayısıyla eşleşme sağ görüntünün tamamında değil, sadece bu çizgi üzerinde
aranır. Arama alanı bir milyon pikselden birkaç yüz piksele iner.

---

## 6. stereoRectify — çizgileri yatay yapmak

### Ne yapar

İki kamerayı yazılımda döndürerek görüntü düzlemlerini aynı düzleme oturtur ve
öteleme vektörünü saf yatay hale getirir. Sonuç: epipolar çizgiler yataylaşır ve iki
görüntüde **aynı satır numarasına** denk düşer.

Çıktılar: `R1, R2` (döndürme), `P1, P2` (yeni projeksiyon), `Q` (yeniden projeksiyon).

### Sezgi

Rektifikasyondan sonra arama şuna iner: "sol görüntünün 342. satırındaki bu yamayı,
sağ görüntünün 342. satırında sola doğru kaydırarak ara." İki boyutlu arama tek
boyuta indiği için hem çok hızlanır hem çok daha güvenilir olur.

### Bu projenin değerleri

```
P2 = ⌈ 898,25    0     673,99   −64,3625 ⌉
     |   0     898,25  456,81       0    |
     ⌊   0        0       1         0    ⌋
```

- Rektifiye ortak odak uzaklığı: **f' = 898,25 px**. Bu, iki kameranın uzlaştırıldığı
  yeni ortak değerdir; `K` içindeki 809/812 değerlerinden farklıdır ve **derinlik
  hesabında kullanılması gereken f budur.**
- `P2[0,3] = −f'·B`. Sağlama: `64,3625 / 898,25 = 0,07165 m = 71,65 mm` ✓

Epipolar hata (aynı noktanın iki rektifiye görüntüdeki satır farkı):
ortalama **0,250 px**, maksimum **0,750 px**. Rektifikasyonun kalite ölçütü budur.

---

## 7. Disparity → derinlik

### Türetim (tahtada yapılabilmeli)

```
Sol  kamera :  X     = Z · (u_sol − cx) / f
Sağ  kamera :  X − B = Z · (u_sağ − cx) / f     (başlangıç B kadar kaymış)

Çıkar       :  B = Z · (u_sol − u_sağ) / f
                 = Z · d / f

                     Z = f · B / d
```

### Q matrisi ile tek adımda

```
      ⌈ 1  0    0     −673,99 ⌉
 Q =  | 0  1    0     −456,81 |        [X' Y' Z' W]ᵀ = Q · [u v d 1]ᵀ
      | 0  0    0      898,25 |
      ⌊ 0  0  13,956      0   ⌋        3B nokta = (X'/W , Y'/W , Z'/W)
```

`13,956 = 1/B` (1 / 0,07165 m). Buradan `Z = 898,25 / (13,956·d) = 64,36/d` metre —
yukarıdaki formülün aynısı.

### Bu projede disparity–mesafe karşılıkları

| Z (mm) | disparity (px) |
|---|---|
| 300 | 214,5 |
| 400 | 160,9 |
| 500 | 128,7 |
| 600 | 107,3 |
| 700 | 91,9 |
| 900 | 71,5 |
| 1000 | 64,4 |

---

## 8. Hata yayılımı — çalışma zarfının kaynağı

### Türetim

```
Z = f·B/d

dZ/dd = −f·B / d²

d = f·B/Z  olduğundan  d² = f²B²/Z²

dZ/dd = −f·B · Z²/(f²B²) = −Z²/(f·B)

         ΔZ ≈ Z² · Δd / (f · B)
```

### Sezgi

Uzaktaki cisimlerde disparity küçülür. Aynı yarım piksellik eşleştirme belirsizliği,
mesafe büyüdükçe giderek daha büyük bir derinlik farkına karşılık gelir. Hata
mesafenin **karesiyle** büyür — bu, çalışma zarfının üst sınırını belirleyen tek etken.

### Bu projenin sayıları (f' = 898,25 px, B = 71,65 mm)

| Z (mm) | Δd = 0,25 px | Δd = 0,5 px | Δd = 1,0 px |
|---|---|---|---|
| 300 | 0,35 mm | 0,70 mm | 1,40 mm |
| 500 | 0,97 mm | 1,94 mm | 3,88 mm |
| 700 | 1,90 mm | 3,81 mm | 7,61 mm |
| 900 | 3,15 mm | 6,29 mm | 12,59 mm |

`Δd = 0,5 px` varsayımıyla 3 mm hedef doğruluk **621 mm**'ye kadar sağlanıyor.

> `Δd` şu an bir varsayım. Tekrarlanabilirlik testinden (Bölüm 5.3) gelen gerçek
> değerle bu tablo yeniden üretilmeli.

---

## 9. ⚠ Kritik bulgu: numDisparities çalışma aralığını kesiyor

SGBM'nin `numDisparities` parametresi, arayabileceği **en büyük disparity**'dir.
Bu doğrudan **en yakın ölçülebilir mesafeyi** belirler:

```
Z_min = f' · B / numDisparities
```

Bu projede:

| Dosya | numDisparities | Z_min |
|---|---|---|
| `src/measurement.py` | 128 | **503 mm** |
| `src/camera_test.py` | 256 | 251 mm |

**Sonuçlar:**

1. `measurement.py` ile **503 mm'den yakındaki hiçbir cisim ölçülemez.** Disparity
   128'i aştığı için eşleşme bulunamaz, o bölge boş kalır. Sessiz bir sınırdır —
   hata mesajı vermez, sadece sonuç üretmez.
2. Üst sınır ise hedef doğruluktan geliyor: 621 mm.
3. Yani mevcut ayarla kullanılabilir pencere **503–621 mm**, yalnızca 12 cm.
4. İki dosya farklı değer kullanıyor: canlı önizlemede gördüğün derinlik ile ölçümün
   gördüğü aynı değil.

**Yapılacaklar:**

- İki dosyada aynı değeri kullan, tek bir yapılandırma alanından oku
- `numDisparities` artırmak bedava değil — SGBM süresi doğrusal artar, 6 fps'te
  hissedilir. 256 seçilirse Z_min = 251 mm olur ve pencere 251–621 mm'ye genişler
- Bu tabloyu rapora **çalışma zarfı gerekçesi** olarak koy: alt sınır algoritma
  parametresinden, üst sınır fizikten geliyor. İkisinin farklı kaynaklardan gelmesi
  iyi bir mühendislik anlatısıdır

---

## 10. Sözlü sınav için hızlı kontrol listesi

Aşağıdakilerin her birini iki cümleyle cevaplayabilmelisin:

- `fx` neden piksel cinsinden ve neden çözünürlüğe bağlı?
- `fx ≈ fy` neden beklenir, olmadığında ne anlama gelir?
- `calibrateCamera` tam olarak neyi minimize eder?
- Düşük RMS neden doğruluk garantisi değildir? Bu projede ölçek nasıl doğrulandı?
- `CALIB_FIX_INTRINSIC` neden kullanıldı?
- Epipolar kısıt nedir, aramayı nasıl 1B'ye indirir?
- Rektifikasyon ne yapar, kalite ölçütü nedir?
- `Z = f·B/d` bağıntısını türet.
- `ΔZ = Z²Δd/(fB)` bağıntısını türet ve hatanın neden Z² ile büyüdüğünü açıkla.
- `Q` matrisindeki `1/B` terimi nereden geliyor?
- `numDisparities` en yakın ölçülebilir mesafeyi nasıl belirler?
- Sistemin çalışma zarfı nedir ve alt/üst sınırları hangi farklı nedenlerden gelir?
