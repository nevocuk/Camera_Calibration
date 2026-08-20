"""kutu_gorsel.py'nin TUM secenek kombinasyonlari cokmeden calisiyor mu?

Bu oturumda bes yeni bayrak eklendi (--kenar --basamak --yukseklik
--watershed --zemin). Her biri ayri bir kod yolu aciyor ve bazilari
birbirini disliyor. Amac: hicbir kombinasyon ISTISNA ile bitmesin.

"Hata" ile "anlamli reddetme" ayrilir:
  ISTISNA (traceback)         -> KABUL EDILEMEZ
  "HATA: ..." mesaji + cikis  -> kabul edilebilir (kod dogru davraniyor)
"""
import glob
import os
import subprocess
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAP = os.path.join(PROJ, "output", "depth_captures")
KG = os.path.join(PROJ, "src", "kutu_gorsel.py")

kayitlar = sorted(glob.glob(os.path.join(CAP, "q_*_data.npz")))
if not kayitlar:
    print("Cekim yok, test atlaniyor")
    sys.exit(0)

# zemin cikarilmis bir cekim de lazim (--zemin onu gerektiriyor)
import numpy as np
zeminli = None
for y in reversed(kayitlar):
    with np.load(y) as z:
        if "zemin_cikarildi" in z.files and bool(z["zemin_cikarildi"]):
            zeminli = os.path.basename(y)
            break
ham = os.path.basename(kayitlar[-1])
print(f"ham cekim    : {ham}")
print(f"zeminli cekim: {zeminli or 'YOK (--zemin testi atlanacak)'}\n")

NOKTA = "1049,581"
DENEMELER = [
    ("varsayilan", ham, ["--tol", "30", "--gri", "35"]),
    ("kenar", ham, ["--tol", "30", "--gri", "35", "--kenar", "30"]),
    ("basamak", ham, ["--tol", "30", "--gri", "35", "--basamak", "3"]),
    ("kenar+basamak", ham,
     ["--tol", "30", "--gri", "35", "--kenar", "30", "--basamak", "3"]),
    ("gri kapali", ham, ["--tol", "30", "--gri", "0"]),
    ("watershed", ham, ["--watershed", "450"]),
    ("watershed dar", ham, ["--watershed", "200"]),
    ("yukseklik", ham, ["--yukseklik", "20", "--sinir", "60"]),
    ("yukseklik+zemin", ham,
     ["--yukseklik", "20", "--sinir", "60", "--zemin"]),
    ("watershed+yukseklik", ham,
     ["--watershed", "450", "--yukseklik", "20"]),   # watershed onceligi
    ("duzlem-at", ham, ["--tol", "30", "--gri", "35", "--duzlem-at"]),
    ("asiri deger", ham,
     ["--tol", "200", "--gri", "120", "--kenar", "200", "--basamak", "50"]),
    ("sifir tol", ham, ["--tol", "5", "--gri", "35"]),
]
if zeminli:
    DENEMELER += [
        ("zemin", zeminli, ["--tol", "30", "--gri", "35", "--zemin"]),
        ("zemin+watershed", zeminli, ["--watershed", "450", "--zemin"]),
    ]
# zemin cikarma KAPALI bir cekimde --zemin: anlamli hata vermeli
DENEMELER.append(("zemin ama cekim uygun degil", ham,
                  ["--tol", "30", "--zemin"]))

istisna = 0
print(f"{'senaryo':<28}{'sonuc':<14}{'cikti':<40}")
print("-" * 84)
for ad, dosya, bayraklar in DENEMELER:
    r = subprocess.run(
        [sys.executable, KG, "--dosya", dosya, "--nokta", NOKTA] + bayraklar,
        capture_output=True, text=True, timeout=180)
    cikti = (r.stdout or "") + (r.stderr or "")
    if "Traceback" in cikti:
        durum = "ISTISNA <-!"
        istisna += 1
        ozet = [l for l in cikti.splitlines() if l.strip()][-1][:38]
    elif "HATA:" in cikti:
        durum = "reddetti"
        ozet = next((l for l in cikti.splitlines() if "HATA:" in l),
                    "")[:38]
    else:
        durum = "calisti"
        ozet = next((l.strip() for l in cikti.splitlines()
                     if "Ana eksen 1" in l), "")[:38]
    print(f"{ad:<28}{durum:<14}{ozet:<40}")

print()
print(f"SONUC: {istisna} istisna" if istisna
      else "SONUC: hicbir kombinasyon ISTISNA ile bitmedi")
sys.exit(1 if istisna else 0)
