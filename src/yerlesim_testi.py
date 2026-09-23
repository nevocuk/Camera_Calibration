"""Olcum tabindaki satirlar panele SIGIYOR MU?

winfo_ismapped() yaniltir (daha once katlanabilir bolumde yasandi):
gorunmeyen bir bilesen icin de True doner. Burada GENISLIK olculuyor:
her satirin istedigi genislik (reqwidth) panelin genisligini asiyorsa
sagdaki bilesenler ekran disinda kalir.

Kameralari acmadan test etmek icin _open_cameras devre disi birakilir.
"""
import os
import sys
import tkinter as tk

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJ, "src"))
import camera_test as ct  # noqa: E402

ct.CameraApp._open_cameras = lambda self: None      # kamera acma
ct.CameraApp._capture_loop = lambda self: None
ct.CameraApp._depth_worker = lambda self: None
ct.CameraApp._update_display = lambda self: None

root = tk.Tk()
root.geometry("1400x900")
app = ct.CameraApp(root, 1, 2)
root.update_idletasks()
root.update()

nb = app.notebook
toplam_tasan = 0


def satirlar(w, bulunan):
    for ch in w.winfo_children():
        try:
            cocuk = ch.winfo_children()
        except Exception:
            cocuk = []
        if ch.winfo_class() == "Frame" and len(cocuk) >= 3:
            sol = 0
            for c in cocuk:
                try:
                    if str(c.pack_info().get("side", "")) == "left":
                        sol += 1
                except Exception:
                    pass
            if sol >= 3:
                bulunan.append(ch)
        satirlar(ch, bulunan)
    return bulunan


def etiket(c):
    try:
        t = c.cget("text")
        if t:
            return str(t)[:14]
    except Exception:
        pass
    return c.winfo_class()


for i in range(nb.index("end")):
    nb.select(i)
    root.update_idletasks()
    root.update()
    sekme = nb.nametowidget(nb.select())
    gen = sekme.winfo_width()
    ad = nb.tab(i, "text")
    bul = satirlar(sekme, [])
    tasan = [f for f in bul if f.winfo_reqwidth() > gen]
    toplam_tasan += len(tasan)
    print(f"[{ad:12}] genislik {gen:4} px, {len(bul):2} satir, "
          f"{len(tasan)} tasan")
    for f in tasan:
        cocuk = f.winfo_children()
        isim = " ".join(etiket(c) for c in cocuk[:10])
        print(f"     TASIYOR req {f.winfo_reqwidth():5} px "
              f"({len(cocuk)} bilesen)  {isim[:60]}")
    # dikey tasma: icerik yuksekligi gorunen alani asiyor mu
    ic = sekme.winfo_reqheight()
    if ic > sekme.winfo_height() + 5:
        print(f"     dikey: icerik {ic} px / gorunen "
              f"{sekme.winfo_height()} px -> kaydirma gerekli")

print()
print(f"TOPLAM {toplam_tasan} tasan satir" if toplam_tasan
      else "TOPLAM: hicbir sekmede yatay tasma yok")
root.destroy()
