"""
Canli derinlik haritasi goruntuleyici.

Kullanim:
    python src/depth_view.py [--left 1] [--right 2]

On kosul:
    calibration/calib_result.npz (once calibration.py calistir)

Cikti:
    3 pencere: Sol kamera | Renkli derinlik | Overlay (gercek + derinlik)
    S: ekran goruntusu kaydet
    ESC: cikis
"""
import os
import sys
import json
import argparse
import numpy as np
import cv2

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
CALIB_PATH = os.path.join(PROJECT_DIR, "calibration", "calib_result.npz")
CONFIG_PATH = os.path.join(PROJECT_DIR, "data", "charuco_config.json")
OUTPUT_DIR = os.path.join(PROJECT_DIR, "output", "depth_captures")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def main():
    # Varsayilan kamera indexlerini ayarlardan oku
    settings_path = os.path.join(PROJECT_DIR, "data", "camera_settings.json")
    default_left, default_right = 1, 2
    if os.path.exists(settings_path):
        try:
            with open(settings_path, encoding="utf-8") as f:
                s = json.load(f)
            default_left = s.get("left_idx", default_left)
            default_right = s.get("right_idx", default_right)
        except Exception:
            pass

    p = argparse.ArgumentParser(description="Canli derinlik haritasi")
    p.add_argument("--left", type=int, default=default_left)
    p.add_argument("--right", type=int, default=default_right)
    args = p.parse_args()

    # Kalibrasyon yukle
    if not os.path.exists(CALIB_PATH):
        print("=" * 55)
        print("HATA: Kalibrasyon dosyasi yok!")
        print(f"  Beklenen: {CALIB_PATH}")
        print()
        print("Once su adimlari tamamla:")
        print("  1. ChArUco tahtasini farkli acilarda tut, S ile kare kaydet")
        print("  2. python src/calibration.py")
        print("=" * 55)
        sys.exit(1)

    calib = np.load(CALIB_PATH)
    K1, D1 = calib["K1"], calib["D1"]
    K2, D2 = calib["K2"], calib["D2"]
    R1, R2 = calib["R1"], calib["R2"]
    P1, P2 = calib["P1"], calib["P2"]
    Q = calib["Q"]
    image_size = tuple(calib["image_size"])
    w, h = image_size

    # Rektifikasyon haritalari (bir kere hesapla, her karede kullan)
    map1x, map1y = cv2.initUndistortRectifyMap(K1, D1, R1, P1, image_size, cv2.CV_32FC1)
    map2x, map2y = cv2.initUndistortRectifyMap(K2, D2, R2, P2, image_size, cv2.CV_32FC1)

    # Stereo eslestirici
    num_disp = 384
    block_size = 5
    try:
        use_gpu = cv2.cuda.getCudaEnabledDeviceCount() > 0
    except Exception:
        use_gpu = False

    if use_gpu:
        stereo = cv2.cuda.createStereoSGM(
            minDisparity=0, numDisparities=num_disp, P1=10, P2=120,
            uniquenessRatio=10, mode=0)
        print("  GPU: CUDA StereoSGM aktif")
    else:
        stereo = cv2.StereoSGBM_create(
            minDisparity=0,
            numDisparities=num_disp,
            blockSize=block_size,
            P1=8 * 3 * block_size ** 2,
            P2=32 * 3 * block_size ** 2,
            disp12MaxDiff=1,
            uniquenessRatio=10,
            speckleWindowSize=100,
            speckleRange=32,
            preFilterCap=63,
            mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY,
        )

    # WLS filtre — gurultu temizleme
    use_wls = True
    try:
        right_matcher = cv2.ximgproc.createRightMatcher(stereo)
        wls_filter = cv2.ximgproc.createDisparityWLSFilter(stereo)
        wls_filter.setLambda(8000)
        wls_filter.setSigmaColor(1.5)
    except AttributeError:
        use_wls = False
        print("  [!] cv2.ximgproc yok — WLS filtre devre disi")

    # Cozunurluk
    fmt = "MJPG"
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
        cr = cfg.get("calib_resolution")
        if cr:
            w, h = cr

    # Kameralari ac
    cap_l = cv2.VideoCapture(args.left, cv2.CAP_MSMF)
    cap_r = cv2.VideoCapture(args.right, cv2.CAP_MSMF)
    for cap in [cap_l, cap_r]:
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fmt))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)

    if not cap_l.isOpened() or not cap_r.isOpened():
        print("HATA: Kameralar acilamadi!")
        sys.exit(1)

    print("=" * 55)
    print("CANLI DERINLIK HARITASI")
    print("=" * 55)
    print()
    print("  Pencereler:")
    print("    1. Sol Kamera — gercek goruntu")
    print("    2. Derinlik   — renkli derinlik haritasi")
    print("    3. Overlay    — gercek + derinlik ust uste")
    print()
    print("  S = ekran goruntusu kaydet")
    print("  V = dogrulama — gercek mesafeyi gir, hatayi gor")
    print("  R = dogrulama sonuclarini raporla")
    print("  ESC = cikis")
    print()
    print(f"  Cozunurluk: {w}x{h}")
    print(f"  Baseline: {np.linalg.norm(calib['T'])* 1000:.1f} mm")
    print(f"  fx: {K1[0,0]:.0f} px")
    print()

    capture_count = 0
    verify_log = []
    last_center_z = None

    while True:
        # Senkron yakalama
        cap_l.grab()
        cap_r.grab()
        ret_l, frame_l = cap_l.retrieve()
        ret_r, frame_r = cap_r.retrieve()
        if not ret_l or not ret_r:
            continue

        # 1. Rektifikasyon — lens bozulmasini duzelt + satirlari hizala
        rect_l = cv2.remap(frame_l, map1x, map1y, cv2.INTER_LINEAR)
        rect_r = cv2.remap(frame_r, map2x, map2y, cv2.INTER_LINEAR)

        # 2. Disparity hesapla (gri tonlamada)
        gray_l = cv2.cvtColor(rect_l, cv2.COLOR_BGR2GRAY)
        gray_r = cv2.cvtColor(rect_r, cv2.COLOR_BGR2GRAY)
        if use_gpu:
            gpu_l = cv2.cuda_GpuMat()
            gpu_r = cv2.cuda_GpuMat()
            gpu_l.upload(gray_l)
            gpu_r.upload(gray_r)
            gpu_disp = stereo.compute(gpu_l, gpu_r)
            disparity = gpu_disp.download().astype(np.float32) / 16.0
        else:
            disp_left = stereo.compute(gray_l, gray_r)
            if use_wls:
                disp_right = right_matcher.compute(gray_r, gray_l)
                disparity = wls_filter.filter(
                    disp_left, gray_l, None, disp_right
                ).astype(np.float32) / 16.0
            else:
                disparity = disp_left.astype(np.float32) / 16.0

        # 3. Normalizasyon (0-255 arasi)
        disp_valid = disparity.copy()
        disp_valid[disp_valid <= 0] = 0
        disp_max = disp_valid.max() if disp_valid.max() > 0 else 1
        disp_norm = (disp_valid / disp_max * 255).astype(np.uint8)

        # 4. Renkli derinlik haritasi
        depth_color = cv2.applyColorMap(disp_norm, cv2.COLORMAP_JET)
        # Gecersiz pikselleri siyah yap
        depth_color[disp_valid <= 0] = [0, 0, 0]

        # 5. Overlay — gercek goruntu + derinlik renkleri
        mask = disp_valid > 0
        overlay = rect_l.copy()
        overlay[mask] = cv2.addWeighted(rect_l, 0.4, depth_color, 0.6, 0)[mask]

        # 6. Derinlik bilgisi (merkez bolge medyani — 21x21 piksel)
        cy, cx = h // 2, w // 2
        r = 10
        roi_disp = disparity[cy - r:cy + r + 1, cx - r:cx + r + 1]
        valid = roi_disp[roi_disp > 0]
        if len(valid) > 5:
            med_disp = np.median(valid)
            # Z = f * B / d  (f=P1[0,0], B=|T|, d=disparity)
            focal = P1[0, 0]
            baseline_m = np.linalg.norm(calib["T"])
            center_z = (focal * baseline_m / med_disp) * 1000
            if 0 < center_z < 10000:
                info = f"Merkez: {center_z:.0f} mm"
                last_center_z = center_z
            else:
                info = "Merkez: ---"
                last_center_z = None
        else:
            info = "Merkez: ---"
            last_center_z = None

        # Gosterim icin kucult
        scale = min(640 / w, 480 / h)
        show_l = cv2.resize(rect_l, None, fx=scale, fy=scale)
        show_d = cv2.resize(depth_color, None, fx=scale, fy=scale)
        show_o = cv2.resize(overlay, None, fx=scale, fy=scale)

        # Bilgi yazisi
        cv2.putText(show_l, "Sol Kamera", (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
        cv2.putText(show_d, "Derinlik Haritasi", (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        cv2.putText(show_o, f"Overlay | {info}", (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)

        # Nisan isareti (merkez)
        ch = int(show_o.shape[0] / 2)
        cw_s = int(show_o.shape[1] / 2)
        cv2.drawMarker(show_o, (cw_s, ch), (0, 255, 0),
                       cv2.MARKER_CROSS, 20, 1)

        # Renk skalasi (legenda)
        bar_h = show_d.shape[0] - 60
        bar_w = 20
        bar_x = show_d.shape[1] - 40
        for i in range(bar_h):
            val = int(255 * (1 - i / bar_h))
            color = cv2.applyColorMap(np.array([[val]], dtype=np.uint8),
                                      cv2.COLORMAP_JET)[0][0]
            cv2.line(show_d, (bar_x, 30 + i), (bar_x + bar_w, 30 + i),
                     color.tolist(), 1)
        cv2.putText(show_d, "Yakin", (bar_x - 5, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1)
        cv2.putText(show_d, "Uzak", (bar_x - 5, 30 + bar_h + 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1)

        cv2.imshow("Sol Kamera", show_l)
        cv2.imshow("Derinlik", show_d)
        cv2.imshow("Overlay", show_o)

        key = cv2.waitKey(30) & 0xFF
        if key == 27:
            break
        elif key == ord('s'):
            capture_count += 1
            prefix = os.path.join(OUTPUT_DIR, f"capture_{capture_count:03d}")
            cv2.imwrite(f"{prefix}_sol.png", rect_l)
            cv2.imwrite(f"{prefix}_derinlik.png", depth_color)
            cv2.imwrite(f"{prefix}_overlay.png", overlay)
            cv2.imwrite(f"{prefix}_disparity_raw.png", disp_norm)
            print(f"  Kaydedildi: {prefix}_*.png")
        elif key == ord('v'):
            if last_center_z is None:
                print("  [!] Merkez mesafe hesaplanamadi — cismi ortala")
            else:
                try:
                    gercek = input(f"  Gercek mesafe (mm)? [olculen: {last_center_z:.0f}] > ")
                    gercek = float(gercek.strip())
                    hata_mm = last_center_z - gercek
                    hata_pct = (hata_mm / gercek) * 100
                    print(f"  Olculen: {last_center_z:.0f} mm | "
                          f"Gercek: {gercek:.0f} mm | "
                          f"Hata: {hata_mm:+.1f} mm ({hata_pct:+.1f}%)")
                    verify_log.append({
                        "gercek_mm": gercek,
                        "olculen_mm": last_center_z,
                        "hata_mm": hata_mm,
                        "hata_pct": hata_pct,
                    })
                except (ValueError, EOFError):
                    print("  [!] Gecersiz giris")
        elif key == ord('r'):
            if not verify_log:
                print("  Henuz dogrulama yapilmadi — V ile test et")
            else:
                print(f"\n  {'Gercek':>8} {'Olculen':>8} {'Hata':>8} {'%':>6}")
                print(f"  {'-'*8} {'-'*8} {'-'*8} {'-'*6}")
                for v in verify_log:
                    print(f"  {v['gercek_mm']:>8.0f} {v['olculen_mm']:>8.0f} "
                          f"{v['hata_mm']:>+8.1f} {v['hata_pct']:>+6.1f}")
                hata_list = [abs(v['hata_pct']) for v in verify_log]
                print(f"\n  Ort. mutlak hata: {np.mean(hata_list):.1f}%")
                print(f"  Maks. mutlak hata: {np.max(hata_list):.1f}%")

    cap_l.release()
    cap_r.release()
    cv2.destroyAllWindows()
    print(f"\nToplam {capture_count} ekran goruntusu kaydedildi.")


if __name__ == "__main__":
    main()
