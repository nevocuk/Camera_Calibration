"""Zemin tespiti, DERINLIK HIC ACILMADAN cagrildiginda cokuyor mu?

Gercek hata (2026-08-20): _depth_olcum yalnizca _depth_worker
calisinca olusuyordu. Kullanici uygulamayi acip dogrudan
"Zemin tespit et" deyince:
    AttributeError: 'CameraApp' object has no attribute '_depth_olcum'
ve tespit TAMAMEN basarisiz oluyordu.

Bu test kameralari acmadan uygulamayi kurar, sahte bir kare verir ve
_detect_ground_plane'i cagirir. Amaci dogru duzlem bulmak DEGIL -
kodun AttributeError ile cokmedigini dogrulamak. Desen olmadigi icin
"Desen bulunamadi" mesaji beklenen ve KABUL EDILEBILIR sonuctur.
"""
import os
import sys
import tkinter as tk

import numpy as np

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJ, "src"))
import camera_test as ct  # noqa: E402

ct.CameraApp._open_cameras = lambda self: None
ct.CameraApp._capture_loop = lambda self: None
ct.CameraApp._depth_worker = lambda self: None
ct.CameraApp._update_display = lambda self: None

root = tk.Tk()
root.geometry("1200x800")
app = ct.CameraApp(root, 1, 2)
root.update_idletasks()

hata = 0

print("1) __init__ sonrasi oznitelikler tanimli mi")
for ad in ("_depth_olcum", "_pre_ground_dsp", "_current_dsp"):
    var = hasattr(app, ad)
    print(f"   {ad:20} {'VAR' if var else 'YOK  <- HATA'}")
    if not var:
        hata += 1

print()
print("2) derinlik hic acilmadan zemin tespiti cagriliyor")
# calib_data TEMBEL yuklenir; _detect_ground_plane zaten
# _ensure_calib_current() cagiriyor, testte de once onu tetikliyoruz
app._ensure_calib_current()
if app.calib_data is None:
    print("   kalibrasyon dosyasi yok - test atlaniyor")
else:
    # KRITIK: bos bir kare yeterli DEGIL. Desen bulunamayinca kod
    # "Desen bulunamadi" ile erken doner ve hatanin bulundugu satira
    # HIC ULASMAZ - test yanlislikla gecerdi. Bu yuzden tahtanin
    # gorundugu gercek bir cekim kare olarak besleniyor.
    import glob
    import cv2
    kare = None
    for yol in sorted(glob.glob(os.path.join(
            PROJ, "output", "depth_captures", "q_*_data.npz")), reverse=True):
        with np.load(yol) as z:
            if "gray_l" not in z.files:
                continue
            g = z["gray_l"]
        # ters rektifikasyon yapmiyoruz; kod kareyi remap'ten geciriyor
        # ama desen yine de bulunuyorsa test amacimiz karsilanir
        app.frame_l = cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)
        cc, _, _, _ = app.detector.detectBoard(g)
        if cc is not None and len(cc) >= 40:
            kare = os.path.basename(yol)
            break
    # GUVENLIK: _detect_ground_plane basarili olursa ground_plane.npz'yi
    # UZERINE YAZAR. Test gercek dosyayi bozmamali - yedekleyip sonunda
    # geri koyuyoruz. (Bir kez yasandi: test gercek duzlemi sildi.)
    import shutil
    GP = os.path.join(PROJ, "calibration", "ground_plane.npz")
    yedek = GP + ".test_yedek"
    if os.path.exists(GP):
        shutil.copy2(GP, yedek)

    if kare is None:
        print("   tahtanin gorundugu cekim yok - bos kare kullanilacak,")
        print("   bu durumda test hatanin oldugu satira ULASAMAZ")
        h, w = [int(v) for v in app.calib_data["image_size"]][::-1]
        app.frame_l = np.full((h, w, 3), 120, np.uint8)
    else:
        print(f"   kaynak kare: {kare} ({len(cc)} kose)")
    try:
        app._detect_ground_plane()
        mesaj = app.lbl_ground.cget("text")
        print(f"   durum: {mesaj[:90]}")
        if "has no attribute" in mesaj or "hatasi:" in mesaj:
            print("   -> HATA: tespit istisna ile bitti")
            hata += 1
        elif "Zemin kaydedildi" in mesaj:
            print("   -> TAMAM: tespit bastan sona calisti")
        elif "Desen bulunamadi" in mesaj:
            print("   -> ATLANDI: desen bulunamadi, hatali satira "
                  "ULASILAMADI (test bu haliyle bir sey kanitlamaz)")
        else:
            print("   -> beklenmeyen mesaj, elle bak")
    except AttributeError as ex:
        print(f"   -> HATA: {ex}")
        hata += 1
    except Exception as ex:
        print(f"   -> baska istisna ({type(ex).__name__}): {ex}")
    finally:
        if os.path.exists(yedek):
            shutil.move(yedek, GP)
            print("   (gercek ground_plane.npz geri yuklendi)")

root.destroy()
print()
print("SONUC: TEST GECTI" if hata == 0 else f"SONUC: {hata} HATA")
sys.exit(1 if hata else 0)
