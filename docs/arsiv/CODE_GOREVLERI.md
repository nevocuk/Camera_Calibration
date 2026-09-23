# Claude Code Görev Listesi — 10 Ağustos

Kaynak: `DURUM_10AGUSTOS.md` → "COWORK DOĞRULAMA" bölümü.
Bulgular sandbox'ta çalıştırılarak doğrulandı, tahmin değil.

Sırayla yap. Her görevin sonunda **kabul kriteri** var — onu sağlamadan sonrakine geçme.

---

## G1 — Kutu tablosu okuma hatası 🔴

**Sorun:** `data/kutu_tablosu.json` şu şemada:

```json
{"kaynak": "...", "birim": "cm",
 "kutular": [{"no": 0, "ad": "Mini koli", "olcu": [10, 10, 10], "desi": 0.33}]}
```

`measurement.py:196` ve `box_output.py:37` ise düz liste + `en_mm/boy_mm/yukseklik_mm`
bekliyor. Ayrıca JSON **cm**, kod **mm**.

Doğrulanmış hatalar:
```
measurement.suggest_box(180,120,74) -> TypeError: string indices must be integers
box_output.load_boxes()             -> TypeError: unhashable type: 'slice'
```

**Yapılacak:** `box_output.py` içindeki `load_boxes()` fonksiyonunu şöyle değiştir:

```python
def load_boxes():
    """kutu_tablosu.json'u oku, cm -> mm cevir, tek tip sozluk dondur."""
    with open(BOX_PATH, encoding="utf-8") as f:
        data = json.load(f)
    boxes = []
    for k in data["kutular"]:
        en, boy, yuk = k["olcu"]                  # JSON'da cm
        boxes.append({
            "no": k["no"], "ad": k["ad"],
            "en_mm": en * 10, "boy_mm": boy * 10, "yukseklik_mm": yuk * 10,
            "desi": k["desi"],
        })
    return boxes
```

`measurement.py` içindeki `suggest_box()` kopyasını **sil**, yerine
`box_output.load_boxes()` ve `box_output.suggest_boxes()` import et. İki dosyada iki
farklı kutu okuma mantığı kalmasın.

JSON'daki `kaynak` alanına dokunma — rapora kaynak göstermek için lazım.

**Kabul kriteri:**
```
python -c "import sys; sys.path.insert(0,'src'); import box_output as b; \
print(b.suggest_boxes(180,120,74,b.load_boxes())[0][1]['ad'])"
```
hatasız çalışmalı ve makul bir kutu adı basmalı.

---

## G2 — Kontur disparity dolgusu arka planı nesne sanıyor 🔴

**Sorun:** `measurement.py:118` `fill_disparity_on_contour()` — kontur pikselinin
etrafındaki 5 px pencerenin medyanını alıyor. Kontur nesne/arka plan sınırıdır;
pencerenin yaklaşık yarısı arka plandır. Medyan arka plana düşerse o nokta nesnenin
arkasına taşınır ve bounding box şişer. **Sessiz hata** — kod çalışır, sayı yanlıştır.

**Yapılacak:** Fonksiyona `mask` parametresi ekle, sadece maske içinden örnekle:

```python
def fill_disparity_on_contour(contour, disparity, mask, r=7):
    """
    Kontur uzerindeki gecersiz disparity'leri doldurur.
    ONEMLI: sadece maskenin ICINDEN ornekler — kontur uzerinde occlusion oldugu
    icin disaridan ornekleme arka plan derinligini nesneye atar.
    """
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    mask_ic = cv2.erode(mask, kernel, iterations=1)
    gecerli = (disparity > 0) & (mask_ic > 0)

    h, w = disparity.shape
    filled = disparity.copy()
    for px, py in contour.reshape(-1, 2):
        px, py = int(px), int(py)
        if gecerli[py, px]:
            continue
        y_lo, y_hi = max(0, py - r), min(h, py + r + 1)
        x_lo, x_hi = max(0, px - r), min(w, px + r + 1)
        patch = disparity[y_lo:y_hi, x_lo:x_hi]
        pmask = gecerli[y_lo:y_hi, x_lo:x_hi]
        valid = patch[pmask]
        if len(valid) > 0:
            filled[py, px] = np.median(valid)
        else:
            filled[py, px] = 0      # doldurulamadi, 3B'ye tasima
    return filled
```

`measure_3d_bbox()` çağrısını da güncelle (`mask` parametresini geçir).

**Ek olarak:** Kaç kontur noktasının doldurulamadığını (disparity=0 kaldığını) say ve
ekrana yaz. Bu oran %30'u geçiyorsa "ölçüm güvenilmez" uyarısı ver — bu sayı rapora
"disparity kapsama oranı" olarak girecek.

**Kabul kriteri:** Ölçüm ekranında `Kontur noktasi: 412, gecerli: 380 (%92)` gibi bir
satır görünmeli.

---

## G3 — `sorted()` yükseklik eksenini yok ediyor 🟠

**Sorun:** `measurement.py:200`

```python
dims = sorted([width, length, height], reverse=True)
width, length, height = dims[0], dims[1], dims[2]
```

`height` zemin normali yönündeki uzanım olarak doğru hesaplanıyor, sonra sıralamayla
anlamını kaybediyor. Uzun ince cisimde (şişe) yükseklik "en" olarak raporlanır.
Rapor tablosunda kumpasla eksen eksen karşılaştırma yapacağız, eksenler karışmamalı.

**Yapılacak:**
- `measure_3d_bbox()` **sıralama yapmadan** dönsün: `en` ve `boy` zemin düzlemindeki
  iki eksen, `yukseklik` her zaman zemin normali yönü
- Sıralamayı sadece `suggest_boxes()` içinde yap (kutu seçimi zaten permütasyon deniyor)
- Ekrana ve ölçüm defterine `en / boy / yukseklik` olarak, anlamı korunmuş biçimde yaz

**Kabul kriteri:** Dik duran uzun bir cisim ölçüldüğünde `yukseklik` en büyük değer
olarak raporlanmalı.

---

## G4 — Gölge nesne sanılıyor 🟠

**Sorun:** `find_object_contour()` `absdiff` + sabit eşik kullanıyor. Gölge de fark
üretir, maskeye girer, en/boy sistematik olarak büyük çıkar.

**Yapılacak:** HSV tabanlı gölge bastırma ekle. Gölge parlaklığı (V) düşürür ama
renk tonunu (H) ve doygunluğu (S) fazla değiştirmez:

```python
def find_object_contour(frame, bg_frame, golge_bastir=True):
    if golge_bastir:
        hsv     = cv2.cvtColor(frame,    cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv_bg  = cv2.cvtColor(bg_frame, cv2.COLOR_BGR2HSV).astype(np.float32)
        v_oran  = hsv[:, :, 2] / (hsv_bg[:, :, 2] + 1e-6)
        h_fark  = np.abs(hsv[:, :, 0] - hsv_bg[:, :, 0])
        s_fark  = np.abs(hsv[:, :, 1] - hsv_bg[:, :, 1])
        # golge: parlaklik dustu ama renk degismedi
        golge   = (v_oran > 0.35) & (v_oran < 0.90) & (h_fark < 10) & (s_fark < 40)
    ...
    mask[golge] = 0     # esikleme sonrasi golgeyi maskeden cikar
```

Bunu **açılıp kapanabilir** yap (`--golge-bastir` argümanı veya tuş). Sebebi: Bölüm 5'e
"gölge bastırma açık/kapalı" karşılaştırma testi girecek, iki modun da çalışması lazım.

**Kabul kriteri:** Tek yönlü lamba altında, gölge bastırma açık/kapalı ölçüm farkı
ekrana yazılabilmeli.

---

## G5 — Çözünürlük: 1280×960 test et 🟠

Probe çıktısına göre `1280x720 YUY2 @6fps` ve `1280x960 YUY2 @6fps` — aynı FPS.
960 dikeyde %33 daha fazla piksel ve daha geniş dikey görüş alanı veriyor. 45° eğik
bakışta dikey görüş alanı doğrudan "cisim kadraja sığıyor mu"yu belirliyor.
4:3 muhtemelen sensörün doğal oranı, 720p onun kırpılmışı.

**Yapılacak:**
1. `probe_stereo_bandwidth.py`'ı 1280×960 ile çalıştır — **iki kamera aynı anda**
   6 fps'i koruyor mu?
2. Koruyorsa çalışma çözünürlüğünü 1280×960 yap, `charuco_config.json`'a
   `"calib_resolution": [1280, 960]` olarak yaz
3. `camera_test.py` varsayılanını değiştir
4. `calibration.py` ve `measurement.py`'a kontrol koy: kare boyutu
   `calib_resolution` ile uyuşmuyorsa `SystemExit` ver

Sonucu (fps ölçümleriyle) `data/olcum_defteri.csv`'ye yaz ve bana bildir.

**Kabul kriteri:** Seçilen çözünürlük tek bir yerde tanımlı ve üç script de oradan okuyor.

---

## G6 — Odak doğrulaması 🟠

Durum raporunda "fabrika ayarında, şu an yeterli görünüyor" yazıyor. Netlik skorları
(706 / 662) farklı sahnelerden alınmışsa karşılaştırılamaz — Laplacian varyansı
sahnenin kendi detayına bağlıdır.

**Yapılacak:** `src/odak_test.py` yaz:
- Tek bir dokulu hedef (baskılı sayfa) her iki kameranın kadrajında olsun
- Hedefi 200, 300, 400, 500, 600, 700, 800 mm'ye koy (elle, tuşla ilerle)
- Her mesafede iki kameranın Laplacian skorunu kaydet
- Sonunda tabloyu yazdır + `data/olcum_defteri.csv`'ye ekle
- Skorun tepe yaptığı mesafeyi ve eşiğin üstünde kaldığı aralığı (net alan derinliği) raporla

Bu tablo raporda Bölüm 5.1'e ve çalışma zarfı gerekçesine giriyor.

**Kabul kriteri:** İki kamera için mesafe–netlik tablosu üretilmeli.

---

## G7 — Yönelim duyarlılığı testi (yeni) 🟡

Bölüm 5'e yeni doğrulama maddesi. Cismi döndürüp birleştirme **yapmıyoruz** —
sadece iki yönelimde ölçüp farkı raporluyoruz. Ucuz ve rapor değeri yüksek.

**Yapılacak:** `measurement.py` içine `O` tuşu ekle:
1. Cismi ölç, sonucu sakla ("0° yönelim")
2. Kullanıcıya "cismi 90° çevir ve tuşa bas" de
3. Tekrar ölç ("90° yönelim")
4. Aynı fiziksel boyut için iki yönelim arasındaki farkı hesapla ve yazdır
5. Ölçüm defterine `yonelim_duyarliligi` etiketiyle yaz

Bu, tek görüşlü ölçümün occlusion kaynaklı yanlılığını sayısal olarak verir.

**Kabul kriteri:** Bir cisimde çalıştırıldığında iki yönelim ve fark tabloya yazılmalı.

---

## G8 — Temizlik 🟡

1. `calibration/frames/` içindeki 12 çifti sil (karanlık, desen yok, kullanılamaz)
2. `data/olcum_defteri.csv` yoksa başlıklarıyla birlikte şimdi oluştur:
   ```
   tarih,saat,asama,parametre,ayar,deger,birim,not
   ```
3. `sistem_planlama.py`'ı henüz çalıştırma — kumpasla ölçülen baseline ve cetvel
   testinden gelen `f_px` gerekiyor, o fiziksel ölçümler bende

---

## YAPMA

- **ICP / çok görüşlü nokta bulutu kaydı yazma.** 2–3 gün sürer, 6 fps ve dokusuz
  yüzeylerle yakınsamaz. G7 aynı bilgiyi bir saatte veriyor.
- Kalibrasyon verisi gerektiren doğrulama scriptlerini (5.2 hata eğrisi, 5.5 kalibrasyon
  kalitesi) şimdi yazma — `calib_result.npz` oluştuktan sonra.
- Çözünürlüğü G5 dışında hiçbir yerde değiştirme.

---

## BİTİRİNCE

`DURUM_10AGUSTOS.md` dosyasının sonuna hangi görevlerin tamamlandığını ve kabul
kriterlerinin sağlanıp sağlanmadığını yaz. Çözemediğin bir şey varsa "çözüldü" deme,
neyin takıldığını yaz.
