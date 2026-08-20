"""'Onerilen ayarlar' butonu dogru degerleri yukluyor mu, deneysel
bolum kapali mi?

Bu bolum kasten sadelestirildi: olculdu ki deneysel kontroller
(kenar/basamak/yukseklik/watershed) IYI geometride sonucu hic
degistirmiyor. Gunluk kullanimda gorunmemeliler.
"""
import os
import sys
import tkinter as tk

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJ, "src"))
import camera_test as ct  # noqa: E402

ct.CameraApp._open_cameras = lambda self: None
ct.CameraApp._capture_loop = lambda self: None
ct.CameraApp._depth_worker = lambda self: None
ct.CameraApp._update_display = lambda self: None

root = tk.Tk()
root.geometry("1300x900")
app = ct.CameraApp(root, 1, 2)
root.update_idletasks()
root.update()

hata = 0

print("1) Deneysel kontrolleri kirletip butona basiyoruz")
app.pca_tol_var.set(99)
app.pca_gri_var.set(99)
app.pca_kenar_var.set(99)
app.pca_basamak_var.set(99.0)
app.pca_yukseklik_var.set(99)
app.pca_watershed_var.set(999)
app.pca_zemin_var.set(True)
app._onerilen_olcum_ayarlari()

BEKLENEN = [("tol", app.pca_tol_var, 30),
            ("gri", app.pca_gri_var, 35),
            ("sinir", app.pca_sinir_var, 300),
            ("kenar", app.pca_kenar_var, 0),
            ("basamak", app.pca_basamak_var, 0.0),
            ("yukseklik", app.pca_yukseklik_var, 0),
            ("watershed", app.pca_watershed_var, 0)]
for ad, var, bek in BEKLENEN:
    v = var.get()
    ok = abs(float(v) - float(bek)) < 1e-9
    print(f"   {ad:12} {v!s:>6}  (beklenen {bek})"
          + ("" if ok else "   <- HATA"))
    if not ok:
        hata += 1
for ad, var in (("zemin haritasi", app.pca_zemin_var),
                ("masayi at", app.pca_duzlem_var)):
    if var.get():
        print(f"   {ad:12} ACIK   <- HATA (kapali olmali)")
        hata += 1

print()
print("2) Deneysel bolum KAPALI baslamis mi")


def bolum_bul(w, ara):
    for ch in w.winfo_children():
        try:
            t = ch.cget("text")
        except Exception:
            t = ""
        if t and ara in str(t):
            return ch
        b = bolum_bul(ch, ara)
        if b is not None:
            return b
    return None


nb = app.notebook
for i in range(nb.index("end")):
    if "lcum" in nb.tab(i, "text"):
        nb.select(i)
        break
root.update_idletasks()
root.update()
sekme = nb.nametowidget(nb.select())
bas = bolum_bul(sekme, "Deneysel yontemler")
if bas is None:
    print("   Deneysel bolum BULUNAMADI   <- HATA")
    hata += 1
else:
    # katlanabilir baslikta ok isareti: kapali ise saga bakan ucgen
    metin = str(bas.cget("text"))
    kapali = metin.strip().startswith(("▸", "▶", ">"))
    # Konsol cp1254; ucgen karakterleri dogrudan yazdirmak cokuyor
    guvenli = metin.encode("ascii", "replace").decode("ascii")
    print(f"   baslik: {guvenli!r}")
    print(f"   {'KAPALI (dogru)' if kapali else 'ACIK <- beklenen kapali'}")
    if not kapali:
        hata += 1

print()
print("3) Kanitlanmis kontroller hala gorunur mu")
for ara in ("tol mm:", "gri tol:", "sinir:", "Onerilen ayarlar",
            "Kutu gorseli"):
    var = bolum_bul(sekme, ara) is not None
    print(f"   {ara:20} {'var' if var else 'YOK  <- HATA'}")
    if not var:
        hata += 1

root.destroy()
print()
print("SONUC: TEST GECTI" if hata == 0 else f"SONUC: {hata} HATA")
sys.exit(1 if hata else 0)
