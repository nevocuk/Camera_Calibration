"""Aciklama balonlari - arayuzdeki her kontrolun ne yaptigini anlatir.

Tk'nin yerlesik tooltip'i yok. Toplevel + overrideredirect ile
kuruluyor. Gecikme, farenin ustunden gecerken balon patlamasin diye.

TASARIM KURALI: bu uygulamada HER kontrolun bir aciklamasi olmali.
Aciklama yalnizca "ne yapar" degil, "ne zaman degistirmelisin" ve
"yanlis ayarlarsan ne olur" da soylemeli.
"""
from __future__ import annotations

import tkinter as tk

KENARLIK = "#3a3a5c"
ZEMIN = "#2b2b40"
YAZI = "#d4d4e8"
VURGU = "#7aa2f7"


class Ipucu:
    def __init__(self, widget, metin, gecikme=400, genislik=460):
        self.widget = widget
        self.metin = metin
        self.gecikme = gecikme
        self.genislik = genislik
        self._is = None
        self._pencere = None
        widget.bind("<Enter>", self._gir, add="+")
        widget.bind("<Leave>", self._cik, add="+")
        widget.bind("<ButtonPress>", self._cik, add="+")

    def _gir(self, _=None):
        self._iptal()
        self._is = self.widget.after(self.gecikme, self._goster)

    def _cik(self, _=None):
        self._iptal()
        self._gizle()

    def _iptal(self):
        if self._is is not None:
            try:
                self.widget.after_cancel(self._is)
            except Exception:
                pass
            self._is = None

    def _goster(self):
        if self._pencere is not None:
            return
        try:
            x = self.widget.winfo_rootx() + 16
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        except Exception:
            return
        self._pencere = tk.Toplevel(self.widget)
        self._pencere.wm_overrideredirect(True)
        try:
            self._pencere.wm_attributes("-topmost", True)
        except Exception:
            pass
        cerceve = tk.Frame(self._pencere, bg=KENARLIK, bd=0)
        cerceve.pack()
        tk.Label(cerceve, text=self.metin, bg=ZEMIN, fg=YAZI,
                 font=("Segoe UI", 9), justify="left",
                 wraplength=self.genislik, padx=10, pady=7).pack(padx=1, pady=1)
        self._pencere.update_idletasks()
        gen = self._pencere.winfo_width()
        yuk = self._pencere.winfo_height()
        ekran_g = self._pencere.winfo_screenwidth()
        ekran_y = self._pencere.winfo_screenheight()
        if x + gen > ekran_g - 10:
            x = max(10, ekran_g - gen - 10)
        if y + yuk > ekran_y - 10:                 # asagi sigmiyorsa yukari ac
            y = max(10, self.widget.winfo_rooty() - yuk - 6)
        self._pencere.wm_geometry(f"+{int(x)}+{int(y)}")

    def _gizle(self):
        if self._pencere is not None:
            try:
                self._pencere.destroy()
            except Exception:
                pass
            self._pencere = None


def ipucu(widget, metin):
    """Bir bilesene aciklama balonu bagla."""
    Ipucu(widget, metin)
    return widget


def soru(parent, metin, bg=None):
    """Yanina konulan kucuk '?' isareti."""
    lbl = tk.Label(parent, text="?", bg=bg or ZEMIN, fg=VURGU,
                   font=("Segoe UI", 9, "bold"), cursor="question_arrow")
    Ipucu(lbl, metin)
    return lbl


def etiketli_kontrol(parent, metin, aciklama, kontrol_uret, bg=None):
    """Etiket + kontrol + '?' uclusunu tek seferde kur.

    kontrol_uret(cerceve) -> widget. Etiket, kontrol ve '?' isaretinin
    ucune de ayni aciklama baglanir; kullanici nereye gelirse gelsin
    aciklamayi gorur.
    """
    cerceve = tk.Frame(parent, bg=bg or ZEMIN)
    lbl = tk.Label(cerceve, text=metin, bg=bg or ZEMIN, fg=YAZI,
                   font=("Segoe UI", 9))
    lbl.pack(side=tk.LEFT, padx=(0, 4))
    w = kontrol_uret(cerceve)
    if w is not None:
        w.pack(side=tk.LEFT)
        Ipucu(w, aciklama)
    Ipucu(lbl, aciklama)
    soru(cerceve, aciklama, bg=bg).pack(side=tk.LEFT, padx=(4, 0))
    return cerceve, w
