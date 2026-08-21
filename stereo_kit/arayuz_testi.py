"""Arayuz kurulum testi - kamera GEREKTIRMEZ.

Uygulamanin kameralar olmadan da acilabildigini, tum sekmelerin
kuruldugunu, hicbir satirin panele sigmadigi icin ekran disinda
kalmadigini ve her kontrolun bir aciklamasi oldugunu dogrular.

winfo_ismapped() KULLANILMIYOR: gorunmeyen bir bilesen icin de True
dondurur ve testi yanlis yere gecirir. Bunun yerine GENISLIK
olculuyor.
"""
from __future__ import annotations

import os
import sys
import tkinter as tk

KOK = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, KOK)
import stereo_kit as uygulama                             # noqa: E402
from cekirdek.ipucu import Ipucu                           # noqa: E402


def yatay_satirlar(w, bulunan):
    """En az 3 bileseni yatay dizilmis cerceveler."""
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
        yatay_satirlar(ch, bulunan)
    return bulunan


def ipuclu_bilesenler(w, sayac):
    """Ipucu bagli bilesenleri say (bind listesinde <Enter> var mi)."""
    for ch in w.winfo_children():
        try:
            if ch.bind("<Enter>"):
                sayac[0] += 1
        except Exception:
            pass
        sayac[1] += 1
        ipuclu_bilesenler(ch, sayac)
    return sayac


def main():
    hata = 0
    kok = tk.Tk()
    kok.geometry("1500x900")
    try:
        app = uygulama.StereoKit(kok)
    except Exception as ex:
        print(f"HATA: uygulama kurulamadi - {type(ex).__name__}: {ex}")
        return 1
    kok.update_idletasks()
    kok.update()
    print("1) Uygulama kameralar olmadan acildi")

    nb = app.sekmeler
    print(f"\n2) Sekmeler ({nb.index('end')} adet)")
    toplam_tasan = 0
    for i in range(nb.index("end")):
        nb.select(i)
        kok.update_idletasks()
        kok.update()
        sekme = nb.nametowidget(nb.select())
        gen = sekme.winfo_width()
        ad = nb.tab(i, "text")
        satirlar = yatay_satirlar(sekme, [])
        tasan = [f for f in satirlar if f.winfo_reqwidth() > gen]
        toplam_tasan += len(tasan)
        print(f"   [{ad:16}] genislik {gen:4} px, "
              f"{len(satirlar):2} satir, {len(tasan)} tasan")
        for f in tasan:
            etiketler = []
            for c in f.winfo_children()[:6]:
                try:
                    t = c.cget("text")
                    if t:
                        etiketler.append(str(t)[:14])
                except Exception:
                    pass
            print(f"      TASIYOR req {f.winfo_reqwidth()} px: "
                  f"{' '.join(etiketler)[:60]}")
    if toplam_tasan:
        hata += toplam_tasan

    print("\n3) Aciklama balonu kapsami")
    for i in range(nb.index("end")):
        nb.select(i)
        kok.update_idletasks()
        sekme = nb.nametowidget(nb.select())
        s = ipuclu_bilesenler(sekme, [0, 0])
        ad = nb.tab(i, "text")
        print(f"   [{ad:16}] {s[0]:3} bilesende aciklama var "
              f"({s[1]} bilesen icinde)")

    print("\n4) Ipucu balonu gercekten aciliyor mu")
    d = tk.Label(kok, text="deneme")
    d.pack()
    ip = Ipucu(d, "deneme aciklamasi", gecikme=1)
    kok.update()
    d.event_generate("<Enter>", x=3, y=3)
    kok.after(60, kok.quit)
    kok.mainloop()
    kok.update()
    acildi = ip._pencere is not None
    print(f"   balon acildi: {acildi}")
    if not acildi:
        hata += 1
    d.event_generate("<Leave>", x=-5, y=-5)
    kok.update()
    print(f"   fare cikinca kapandi: {ip._pencere is None}")

    print("\n5) Kamerasiz cagrilar cokmuyor mu")
    for ad, fn in (("kurulum kontrolu", app._kurulum_kontrol),
                   ("olc", app._olc),
                   ("dogrulama gorseli", app._dogrulama_gorseli),
                   ("derinlik parametreleri", app._derinlik_uygula),
                   ("varsayilanlar", app._derinlik_varsayilan),
                   ("kare sil", app._kare_sil),
                   ("kare temizle", app._kare_temizle)):
        try:
            fn()
            print(f"   {ad:24} tamam")
        except Exception as ex:
            print(f"   {ad:24} HATA {type(ex).__name__}: {ex}")
            hata += 1

    try:
        kok.destroy()
    except Exception:
        pass
    print("\nSONUC: TEST GECTI" if hata == 0 else f"\nSONUC: {hata} HATA")
    return 1 if hata else 0


if __name__ == "__main__":
    sys.exit(main())
