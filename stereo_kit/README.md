# Stereo Olcum Kiti

Iki USB kamerayla bir cismin 3B boyutlarini olcen acik bir arac.
Herhangi bir kamera cifti ve herhangi bir kalibrasyon deseniyle
calisir — donanima ozel hicbir varsayim icermez.

---

## Ne yapar

1. Bagli kameralari bulur, hangi cozunurlukleri **gercekten**
   destekledigini tarar
2. Kendi bastigin desenle stereo kalibrasyon yapar
3. Canli derinlik haritasi uretir
4. Tikladigin cismin uzun/orta/kisa kenarini mm cinsinden verir

Arayuzdeki **her kontrolun** uzerine gelince ne yaptigini, ne zaman
degistirmen gerektigini ve yanlis ayarlarsan ne olacagini anlatan
bir aciklama cikar.

---

## Kurulum

Python 3.9+ gerekiyor.

```bash
pip install opencv-contrib-python numpy pillow
```

> **`opencv-contrib-python` sart** — duz `opencv-python` paketinde
> ChArUco (`cv2.aruco`) ve WLS filtresi (`cv2.ximgproc`) yok.
> Ikisi birden kuruluysa once ikisini de kaldirip yalnizca
> contrib surumunu kur.

Calistir:

```bash
python stereo_kit.py
```

---

## Donanim

**Gereken:** iki adet USB kamera ve ikisini birbirine gore **sabit**
tutan bir duzenek.

- Kameralar **yatay** olarak yan yana ve **ayni yone** bakmali
- Aralarindaki mesafe (baz) kalibrasyondan sonra **degismemeli** —
  degisirse kalibrasyon gecersiz olur
- Ayni model olmalari sart degil; farkli lens/sensor de calisir
  ama ortak gorus alani daralir
- Odak ayarlanabiliyorsa kalibrasyondan sonra **dokunma**

**Baz uzunlugu ne olmali:** derinlik hassasiyeti `Z² / (f · B)` ile
belirlenir. Baz ne kadar uzunsa uzak mesafede o kadar hassas olursun,
ama yakin cisimlerde ortak gorus alani daralir. Masa ustu olcum icin
50–100 mm iyi bir baslangic.

---

## Kalibrasyon deseni

Bir ChArUco ya da satranc deseni bas, **duz ve sert** bir yuzeye
kirissiz yapistir (kopuk levha, mukavva, cam).

ChArUco onerilir: desenin bir kismi gorunse bile calisir ve kose
konumlari alt-piksel hassasiyetle bulunur. Ucretsiz uretmek icin
[calib.io/pages/camera-calibration-pattern-generator](https://calib.io/pages/camera-calibration-pattern-generator)
kullanilabilir.

### En kritik adim: kare olcusunu OLC

Yazicidan cikan desen neredeyse hicbir zaman tasarim olcusunde
degildir (olcekleme, kenar bosluklari, kagit gerilmesi).

**Bes karenin toplam uzunlugunu olc, 5'e bol.** Tek kare olcmek
yeterince hassas degil.

Bu deger yanlissa **tum olcumler ayni oranda kayar** ve hata sistemin
icinden fark edilemez — her sey tutarli gorunur ama hepsi yanlistir.

---

## Kullanim

### 1 · Kameralar

"Kameralari tara" → listeden sol ve sag kamerayi sec →
"Cozunurlukleri tara" → bir cozunurluk sec → "Kameralari ac".

Cozunurluk taramasi neden gerekli: bir kameraya desteklemedigi bir
boyut verildiginde surucu cogu zaman hata vermez, sessizce baska bir
boyuta duser. Tarama kare alip **gercek** boyutuna bakar.

Durum panelinde:
- **Netlik** — iki kameranin birbirine yakin olmasi onemli
- **Parlaklik** — 90–150 bandi iyi; 240 ustu doymus demektir ve
  doymus goruntude doku kalmadigi icin stereo esleme calisamaz

### 2 · Kalibrasyon

Desenin olculerini gir → tahtayi iki kameranin da gordugu sekilde
tut → "Kare yakala" → 15–25 kare topla → "KALIBRE ET".

Kare toplarken tahtayi her seferinde biraz farkli tut: egik, yakin,
uzak, goruntunun **kenarlarinda ve koselerinde**. Lens bozulmasi
kenarlarda belirgindir; oralari gostermezsen model oralari
duzeltemez.

**Sonucu nasil degerlendirirsin:** RMS'e degil **epipolar hataya**
bak. 1 pikselin altindaysa kalibrasyon iyi.

> RMS, modelin kendi verisine ne kadar uydugunu olcer. Veriden zor
> kareleri atarak RMS dusurulebilir — ama bu kalibrasyonu
> iyilestirmez, yalnizca sinavi kolaylastirir. Epipolar hata
> bagimsiz bir olcuttur: rektifikasyondan sonra ayni noktanin iki
> goruntude ayni satirda cikip cikmadigini olcer.

### 3 · Derinlik

"Derinligi AC". Sol panelde goruntu uzerine bindirilmis renkli
harita, sag panelde ham derinlik gorunur.

**Arama araligi** en yakin olculebilir mesafeyi belirler; panelde
secili degere gore hesaplanip gosterilir. Buyutmek yakini gorunur
kilar ama islem yavaslar ve goruntunun sol kenarinda o kadar
piksellik bir bant yapisal olarak gecersiz olur.

**"Harita doluluk" bir kalite olcusu DEGILDIR** — filtre bosluklari
komsulardan tahmin ederek doldurur. **"GERCEK eslesme"** satirina
bak; dusukse haritanin buyuk kismi tahmindir.

### 4 · Olcum

Sol goruntude cisme **tikla** → "OLC".

Sonra mutlaka **"Dogrulama gorseli"** uret ve kutunun cismi sarip
sarmadigina bak.

> Sayilara bakip dogrulugu anlamak guvenilir degildir: yanlis bir
> bolge de tesadufen makul sayilar uretebilir. Dogrulama, kutunun
> gorselde cismi sarmasidir.

**Iki segmentasyon yontemi var:**

| Yontem | Ne zaman |
|---|---|
| Tolerans | Cisim goruntu duzlemine paralel uzaniyorsa |
| Watershed | Cisim kameraya dogru uzaniyorsa |

**"Kurulum kontrolu"** butonu kamera yerlesiminin uygun olup
olmadigini olcer.

---

## Sistemin sinirlari

Bunlar hata degil, yontemin dogasi:

- **Tek bakis acisi:** cismin yalnizca gorunen yuzu olculur. Arka
  taraf tahmin edilmez; silindirik bir cismin en kisa kenari
  oldugundan kucuk cikar.
- **Kameraya dogru uzanan eksen olculemez.** Uzun bir cisim
  kameraya dogru bakiyorsa sistem onun ancak bir dilimini gorur.
  Cismi cevir ya da kamerayi yandan bakacak sekilde yerlestir.
- **Hassasiyet mesafenin karesiyle kotulesir.** Iki kat uzaga
  koymak hatayi dort kat artirir.
- **Dokusuz yuzeyler eslesemez.** Duz beyaz duvar, parlak metal,
  cam — bu bolgelerde derinlik uretilemez. Gecici olarak desenli
  bir kagit koymak ise yarar.
- **Yansima zararli, golge zararsiz.** Golge yuzeye yapisiktir ve
  gecerli bir dokudur; parlama bakis acisina bagli oldugu icin iki
  kamerada farkli yerde durur ve hayalet derinlik uretir. Isigi
  yandan ver.

---

## Sorun giderme

| Belirti | Once bunu dene |
|---|---|
| Derinlik haritasi tamamen bos | Sol/sag kamerayi degistir |
| Harita benekli, parcali | Isigi artir; dokusuz yuzeye desenli kagit koy |
| Cismin yalnizca bir kismi olculuyor | "Kurulum kontrolu"; Watershed yontemini dene |
| Olcum cevreye tasiyor | Derinlik toleransini ve yaricap sinirini kucult |
| Kalibrasyon sacma sonuc veriyor | Kare olcusunu kontrol et; "Eski desen duzeni" kutusunu degistir |
| Olcumler sistematik buyuk/kucuk | Kare olcusu yanlis — bes kareyi olcup 5'e bol, yeniden kalibre et |
| Desen hic bulunamiyor | ArUco sozlugu yanlis olabilir; desen ureticide hangisini sectiysen o |
| Kamera bulunamiyor | Baska bir program kamerayi kullaniyor olabilir; kapat ve tekrar tara |

---

## Dosya duzeni

```
stereo_kit/
  stereo_kit.py          ana uygulama
  dogrulama_testi.py     cekirdegi gercek kare setiyle sina
  cekirdek/
    kamera.py            bulma, yetenek tarama, acma
    kalibrasyon.py       desen tanimi, stereo kalibrasyon, epipolar hata
    derinlik.py          SGBM + WLS, ton esleme, renklendirme
    olcum.py             segmentasyon, PCA kutu, kurulum kontrolu
    ipucu.py             aciklama balonlari
  veri/                  kalibrasyon.npz, ayarlar.json, kareler/
  cikti/                 kaydedilen goruntuler ve olcumler
```

### Cekirdegi kendi kodunda kullanmak

```python
from cekirdek import kalibrasyon, derinlik, olcum

tahta = kalibrasyon.TahtaTanimi(kare_x=9, kare_y=13, kare_mm=20.0,
                                marker_mm=14.67)
sonuc, hata = kalibrasyon.stereo_kalibre(ciftler, (genislik, yukseklik),
                                         tahta)
epi, n = kalibrasyon.epipolar_hata(sonuc, ciftler, tahta)

motor = derinlik.DerinlikMotoru()
dsp, ham_maske = motor.hesapla(rektifiye_sol, rektifiye_sag)
noktalar = derinlik.noktalar_3b(dsp, sonuc["Q"])

olcum_sonucu, hata = olcum.olc(dsp, noktalar, gri_sol, x, y,
                               yontem="tolerans")
```

### Kalibrasyonu dogrulamak

Elinde kayitli kare ciftleri varsa:

```bash
python dogrulama_testi.py --kareler <klasor> --kare-mm 20.0
```

Kose tespitinden kurulum kontrolune kadar tum zinciri calistirir ve
her adimin sayisal sonucunu basar.

---

## Lisans

Serbestce kullanilabilir. OpenCV ve NumPy kendi lisanslariyla gelir.
