"""
Odak dogrulama — mesafeye gore netlik (Laplacian) skoru olcer.

Kullanim:
    python src/odak_test.py [--left 1] [--right 2]

Yontem:
    Dokulu bir hedef (basili sayfa) kameralarin onune konur.
    Her mesafede SPACE ile kayit alinir (200-800 mm).
    Sonunda mesafe-netlik tablosu yazdirilir ve olcum_defteri.csv'ye eklenir.
"""
import os
import sys
import json
import datetime
import argparse
import numpy as np
import cv2

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
CONFIG_PATH = os.path.join(PROJECT_DIR, "data", "charuco_config.json")
DIARY_PATH = os.path.join(PROJECT_DIR, "data", "olcum_defteri.csv")

DISTANCES = [200, 300, 400, 500, 600, 700, 800]


def laplacian_score(gray):
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    return lap.var()


def main():
    p = argparse.ArgumentParser(description="Odak dogrulama testi")
    p.add_argument("--left", type=int, default=1)
    p.add_argument("--right", type=int, default=2)
    args = p.parse_args()

    # Cozunurluk ayari
    w, h, fmt = 1280, 960, "YUY2"
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
        cr = cfg.get("calib_resolution")
        if cr:
            w, h = cr

    cap_l = cv2.VideoCapture(args.left, cv2.CAP_DSHOW)
    cap_r = cv2.VideoCapture(args.right, cv2.CAP_DSHOW)
    for cap in [cap_l, cap_r]:
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fmt))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)

    print("=" * 55)
    print("ODAK DOGRULAMA TESTI")
    print("=" * 55)
    print()
    print("Dokulu bir hedefi (basili sayfa, gazete vb.) kameralarin")
    print("onune koyun. Her mesafede SPACE ile kayit alin.")
    print("ESC ile iptal.")
    print()

    results = []
    dist_idx = 0

    while dist_idx < len(DISTANCES):
        target_mm = DISTANCES[dist_idx]
        cap_l.grab()
        cap_r.grab()
        ret_l, frame_l = cap_l.retrieve()
        ret_r, frame_r = cap_r.retrieve()
        if not ret_l or not ret_r:
            continue

        gray_l = cv2.cvtColor(frame_l, cv2.COLOR_BGR2GRAY)
        gray_r = cv2.cvtColor(frame_r, cv2.COLOR_BGR2GRAY)
        score_l = laplacian_score(gray_l)
        score_r = laplacian_score(gray_r)

        # ROI: merkez %60
        rh, rw = gray_l.shape
        y1, y2 = int(rh * 0.2), int(rh * 0.8)
        x1, x2 = int(rw * 0.2), int(rw * 0.8)
        roi_score_l = laplacian_score(gray_l[y1:y2, x1:x2])
        roi_score_r = laplacian_score(gray_r[y1:y2, x1:x2])

        display = np.hstack([frame_l, frame_r])
        dh, dw = display.shape[:2]
        scale = min(1280 / dw, 720 / dh)
        if scale < 1:
            display = cv2.resize(display, (int(dw * scale), int(dh * scale)))

        # ROI cercevesi
        sx1, sy1 = int(x1 * scale), int(y1 * scale)
        sx2, sy2 = int(x2 * scale), int(y2 * scale)
        cv2.rectangle(display, (sx1, sy1), (sx2, sy2), (0, 255, 0), 1)
        offset_x = int(frame_l.shape[1] * scale)
        cv2.rectangle(display, (offset_x + sx1, sy1), (offset_x + sx2, sy2), (0, 255, 0), 1)

        info = (f"Mesafe: {target_mm} mm  |  "
                f"SOL: {roi_score_l:.0f}  SAG: {roi_score_r:.0f}  |  "
                f"SPACE=kaydet  ESC=cikis  ({dist_idx+1}/{len(DISTANCES)})")
        cv2.putText(display, info, (10, 25), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, (0, 255, 255), 1)

        cv2.imshow("Odak Testi", display)
        key = cv2.waitKey(30) & 0xFF

        if key == 27:
            break
        elif key == ord(' '):
            results.append({
                "mesafe_mm": target_mm,
                "sol_skor": roi_score_l,
                "sag_skor": roi_score_r,
                "sol_full": score_l,
                "sag_full": score_r,
            })
            print(f"  {target_mm} mm → SOL: {roi_score_l:.0f}  SAG: {roi_score_r:.0f}")
            dist_idx += 1

    cap_l.release()
    cap_r.release()
    cv2.destroyAllWindows()

    if not results:
        print("\nHicbir olcum alinmadi.")
        return

    # Sonuc tablosu
    print()
    print("=" * 55)
    print("ODAK DOGRULAMA SONUCLARI")
    print("=" * 55)
    print(f"{'Mesafe':>8}  {'SOL':>8}  {'SAG':>8}  {'Ort':>8}")
    print("-" * 40)

    best_l = max(results, key=lambda r: r["sol_skor"])
    best_r = max(results, key=lambda r: r["sag_skor"])

    for r in results:
        ort = (r["sol_skor"] + r["sag_skor"]) / 2
        marker = ""
        if r["mesafe_mm"] == best_l["mesafe_mm"]:
            marker += " ◄SOL"
        if r["mesafe_mm"] == best_r["mesafe_mm"]:
            marker += " ◄SAG"
        print(f"{r['mesafe_mm']:>6} mm  {r['sol_skor']:>8.0f}  "
              f"{r['sag_skor']:>8.0f}  {ort:>8.0f}{marker}")

    # Net alan derinligi: skor tepe degerinin %50'sinin uzerinde kaldigi aralik
    peak_l = best_l["sol_skor"]
    peak_r = best_r["sag_skor"]
    threshold_l = peak_l * 0.5
    threshold_r = peak_r * 0.5

    dof_l = [r["mesafe_mm"] for r in results if r["sol_skor"] >= threshold_l]
    dof_r = [r["mesafe_mm"] for r in results if r["sag_skor"] >= threshold_r]

    print()
    print(f"SOL tepe: {peak_l:.0f} @ {best_l['mesafe_mm']} mm")
    if dof_l:
        print(f"  Net alan derinligi (>%50): {min(dof_l)}-{max(dof_l)} mm")
    print(f"SAG tepe: {peak_r:.0f} @ {best_r['mesafe_mm']} mm")
    if dof_r:
        print(f"  Net alan derinligi (>%50): {min(dof_r)}-{max(dof_r)} mm")

    # Deftere yaz
    now = datetime.datetime.now()
    date = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")
    os.makedirs(os.path.dirname(DIARY_PATH), exist_ok=True)
    exists = os.path.exists(DIARY_PATH)
    with open(DIARY_PATH, "a", encoding="utf-8") as f:
        if not exists:
            f.write("tarih,saat,asama,parametre,ayar,deger,birim,not\n")
        for r in results:
            ort = (r["sol_skor"] + r["sag_skor"]) / 2
            f.write(f"{date},{time_str},odak_testi,mesafe,{r['mesafe_mm']},"
                    f"{ort:.0f},laplacian_var,"
                    f"sol={r['sol_skor']:.0f} sag={r['sag_skor']:.0f}\n")
        if dof_l:
            f.write(f"{date},{time_str},odak_testi,net_alan_sol,,"
                    f"{min(dof_l)}-{max(dof_l)},mm,tepe={peak_l:.0f}\n")
        if dof_r:
            f.write(f"{date},{time_str},odak_testi,net_alan_sag,,"
                    f"{min(dof_r)}-{max(dof_r)},mm,tepe={peak_r:.0f}\n")

    print(f"\nSonuclar {DIARY_PATH} dosyasina yazildi.")


if __name__ == "__main__":
    main()
