# Stereo kamera ile boyut olcumu

Iki USB kamerayla bir cismin 3B boyutlarini olcen bir sistem. Yaz
staji kapsaminda, kendi donanimimla sifirdan kurdugum bir prototip.

Depoda iki sey var:

| Klasor | Ne |
|---|---|
| `stereo_kit/` | **Genel amacli surum.** Herhangi bir kamera cifti ve herhangi bir kalibrasyon deseniyle calisir. Kullanmak isteyen buradan baslasin. |
| `src/` | Kendi donanimima gore gelistirdigim asil calisma. Olcum araclari, deney scriptleri, rapor uretimi. |

Olcumlerin ve denemelerin tamami `docs/` altinda kayitli — neyin
calistigi kadar **neyin calismadigi ve nedeni** de yazili.

---

## Ne yapiyor

```
Iki kameradan es zamanli goruntu
   -> stereo kalibrasyon (ChArUco)
   -> rektifikasyon
   -> SGBM + WLS ile derinlik haritasi
   -> 3B nokta bulutu
   -> tiklanan cismi ayirma
   -> PCA ile yonlu sinir kutusu -> en/orta/kisa kenar (mm)
```

Ek olarak olculen boyuta en uygun standart kargo kutusunu secip
desi hesabi ve RSC kesim sablonu uretiyor.

## Ne kadar dogru

Iyi bir kurulumda (kamera cisme yandan bakiyor, mesafe 550–650 mm),
250 x 72 mm'lik bir referans cisimde:

| Mesafe | Olculen uzun kenar | Hata |
|---|---|---|
| 610 mm | 252.2 mm | %0.9 |
| 609 mm | 256.8 mm | %2.7 |
| 625 mm | 255.2 mm | %2.1 |

Ama asil onemli olan sayi bu degil. **Iyi kurulumda sonuc parametre
secimine duyarsiz** — derinlik toleransini 15'ten 60'a cikarinca
sonuc 0.1 mm degisiyor. Kotu kurulumda (kamera tepeden bakiyor)
ayni kod ayni cisim icin 177 mm de yaziyor 264 mm de. Yani orada
tek bir sayi raporlanamaz.

Sistemin kendi gurultusu 1.15 mm (46 duz masa yamasinda olculdu) ve
bu, bagimsiz olculen epipolar hatayla (0.420 px) tutarli. Gordugumuz
olcum hatalari bunun 30-50 kati — yani darbogaz sensor ya da
kalibrasyon degil, **cismi arka plandan ayirma adimi**.

## Neler calismiyor

Bunlar eksiklik degil, yontemin dogasi:

- **Tek bakis acisi.** Cismin yalnizca gorunen yuzu olculuyor;
  silindirik bir cismin arka yarisi gorunmedigi icin en kisa kenar
  oldugundan kucuk cikiyor.
- **Kameraya dogru uzanan eksen olculemiyor.** Ayakta duran uzun bir
  cisme tepeden bakarsan sistem onun ancak bir dilimini goruyor.
- **Hassasiyet mesafenin karesiyle kotulesiyor** — 550 mm'de
  2.97 mm/px, 718 mm'de 5.06 mm/px.
- **Dokusuz yuzeyler eslesemiyor** (duz beyaz duvar, parlak metal).
- **Zemin duzlemi tespiti kararsiz.** ChArUco periyodik bir desen ve
  blok esleme tahtanin uzerinde bazen yanlis kareye kilitleniyor;
  duzlem 30-57 mm sapabiliyor. Cozulmedi.

Ayrinti: [`docs/YONTEMLER.md`](docs/YONTEMLER.md)

---

## Kurulum

Python 3.9+ ve iki USB kamera gerekiyor.

```bash
pip install -r requirements.txt
```

`opencv-contrib-python` sart — duz `opencv-python` paketinde ChArUco
(`cv2.aruco`) ve WLS filtresi (`cv2.ximgproc`) yok.

## Calistirma

Genel amacli surum (onerilen):

```bash
cd stereo_kit
python stereo_kit.py
```

Dort adimlik rehberli akis: kameralari bul → kalibre et → derinlik →
olc. Her kontrolun uzerine gelince ne yaptigini ve yanlis ayarlarsan
ne olacagini anlatan bir aciklama cikiyor.
Ayrintili anlatim: [`stereo_kit/README.md`](stereo_kit/README.md)

Kendi kurulumuma gore olan surum:

```bash
python src/camera_test.py
```

---

## Donanim

- Iki USB kamera (bende OV5693 sensor, M12 lens)
- Ikisini birbirine gore **sabit** tutan bir govde — bende 3B basilmis
- Baz uzunlugu 71.79 mm (kalibrasyondan olculdu)
- 2048x1536, MJPG, ~25-30 fps

Kameralarin ayni model olmasi sart degil. Ama birbirine gore konumu
kalibrasyondan sonra degisirse kalibrasyon gecersiz oluyor.

---

## Bu projede ogrendiklerim

Kodun kendisinden cok bunlar isime yaradi:

**RMS iyi diye kalibrasyon iyi degil.** RMS'i dusurmek icin veri
setinden zor kareleri attim; RMS gercekten dustu ama **epipolar hata
kotulesti**. RMS modelin kendi verisine uyumunu olcuyor — veriyi
kolaylastirmak modeli iyilestirmiyor, sadece sinavi kolaylastiriyor.

**Beklenen cevaba yakinlik dogrulama degil.** Aday bolgeleri cismin
bilinen olculerine yakinliga gore puanlayip en iyisini sectim.
Secilen sey masanin kenariymis — tesadufen benzer sayilar uretmis.
O gunden sonra her olcumun kutusunu goruntu uzerine cizdirdim.

**Bir sistem kendi varsayimini kendi ciktisiyla dogrulayamaz.** Tum
olcumler kalibrasyon deseninin kare boyuna (20 mm) dayaniyordu.
Bunu dogrulamak icin komsu koselerin 3B mesafesini olctum — o degeri
hic kullanmadan. Sonuc 20.05 mm cikti.

**Bir adimda ideal olan digerinde zararli olabilir.** ChArUco
kalibrasyon icin en iyi desen: yuksek kontrastli, duzenli. Ama tam
bu yuzden stereo esleme icin en kotusu — periyodik desende blok
esleme yanlis kareye kilitlenebiliyor.

**Darbogazi olcmeden optimize etme.** Uzun sure kalibrasyonu
iyilestirmeye calistim. Sonra gurultuyu olctum: 1.15 mm. Hatalar
30-60 mm'ydi. Sorun bambaska yerdeydi.

**Sezgi olcume yeniliyor.** Kontrast artirmanin (CLAHE) eslemeyi
iyilestirecegini sandim — haritayi bozdu. Golgeden kacinmak gerektigini
sandim — golge zararsiz cikti, asil sorun yansimaymis (2.44 kat daha
tutarsiz).

---

## Belgeler

| Dosya | Icerik |
|---|---|
| [`docs/YONTEMLER.md`](docs/YONTEMLER.md) | Her adimda hangi yontem, neden o yontem, neyi denedim de olmadi |
| [`docs/PROJE_KONTEXT.md`](docs/PROJE_KONTEXT.md) | Alinan kararlar, gerekceleri, acik riskler |
| [`docs/ilerleme_gunlugu.md`](docs/ilerleme_gunlugu.md) | Gun gun olcumler ve bulgular |
| [`docs/teori_notlari.md`](docs/teori_notlari.md) | Stereo geometri notlari |

---

## Lisans

MIT — bkz. [LICENSE](LICENSE).
