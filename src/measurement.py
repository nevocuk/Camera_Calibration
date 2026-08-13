"""
Nesne olcum pipeline — stereo kameradan EN x BOY x YUKSEKLIK hesapla.

Kullanim:
    python src/measurement.py [--left 1] [--right 2]

Yontem:
    1. Sol-sag goruntuleri rektifiye et
    2. Arka plan cikarma ile nesne konturunu bul
    3. Disparity haritasindan kontur noktalarinin 3B koordinatlarini hesapla
    4. 3B noktalarin min/max X,Y,Z → EN x BOY x YUKSEKLIK
       (F-sekli, vazo gibi genis tepeli cisimler icin de dogru calisir)

On kosul:
    - calibration/calib_result.npz
    - calibration/ground_plane.npz
"""
import os
import sys
import json
import argparse
import datetime
import numpy as np
import cv2

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
CALIB_PATH = os.path.join(PROJECT_DIR, "calibration", "calib_result.npz")
GROUND_PATH = os.path.join(PROJECT_DIR, "calibration", "ground_plane.npz")
DIARY_PATH = os.path.join(PROJECT_DIR, "data", "olcum_defteri.csv")
CONFIG_PATH = os.path.join(PROJECT_DIR, "data", "charuco_config.json")


def check_resolution(image_size):
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
        calib_res = cfg.get("calib_resolution")
        if calib_res and list(image_size) != calib_res:
            print(f"HATA: Kalibrasyon {image_size[0]}x{image_size[1]} ile yapilmis, "
                  f"beklenen {calib_res[0]}x{calib_res[1]}")
            print("Ayni cozunurlukle kalibre et veya charuco_config.json guncelle.")
            sys.exit(1)


def load_all():
    if not os.path.exists(CALIB_PATH):
        print("HATA: Kalibrasyon dosyasi bulunamadi. Once calibration.py calistir.")
        sys.exit(1)
    if not os.path.exists(GROUND_PATH):
        print("HATA: Zemin duzlemi bulunamadi. Once ground_plane.py calistir.")
        sys.exit(1)

    calib = np.load(CALIB_PATH)
    ground = np.load(GROUND_PATH)
    return calib, ground


def setup_rectify(calib):
    K1, D1 = calib["K1"], calib["D1"]
    K2, D2 = calib["K2"], calib["D2"]
    R1, R2 = calib["R1"], calib["R2"]
    P1, P2 = calib["P1"], calib["P2"]
    image_size = tuple(calib["image_size"])

    map1x, map1y = cv2.initUndistortRectifyMap(K1, D1, R1, P1, image_size, cv2.CV_32FC1)
    map2x, map2y = cv2.initUndistortRectifyMap(K2, D2, R2, P2, image_size, cv2.CV_32FC1)
    return map1x, map1y, map2x, map2y


def setup_stereo_matcher():
    block_size = 5
    stereo = cv2.StereoSGBM_create(
        minDisparity=0,
        numDisparities=128,
        blockSize=block_size,
        P1=8 * 3 * block_size**2,
        P2=32 * 3 * block_size**2,
        disp12MaxDiff=1,
        uniquenessRatio=10,
        speckleWindowSize=100,
        speckleRange=32,
        mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY
    )
    return stereo


def find_object_contour(frame, bg_frame, golge_bastir=True):
    diff = cv2.absdiff(frame, bg_frame)
    gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(gray_diff, 30, 255, cv2.THRESH_BINARY)

    if golge_bastir:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv_bg = cv2.cvtColor(bg_frame, cv2.COLOR_BGR2HSV).astype(np.float32)
        v_oran = hsv[:, :, 2] / (hsv_bg[:, :, 2] + 1e-6)
        h_fark = np.abs(hsv[:, :, 0] - hsv_bg[:, :, 0])
        s_fark = np.abs(hsv[:, :, 1] - hsv_bg[:, :, 1])
        golge = (v_oran > 0.35) & (v_oran < 0.90) & (h_fark < 10) & (s_fark < 40)
        mask[golge] = 0

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None, mask

    largest = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(largest)
    if area < 500:
        return None, mask

    return largest, mask


def contour_points_to_3d(contour, disparity, Q):
    """Kontur noktalarinin disparity'sinden 3B koordinat hesapla."""
    points_3d = []
    contour_pts = contour.reshape(-1, 2)

    for px, py in contour_pts:
        d = disparity[int(py), int(px)]
        if d <= 0:
            continue
        # Q matrisi ile 3B donusum: [X,Y,Z,W] = Q * [px, py, d, 1]
        vec = np.array([px, py, d, 1.0])
        p4d = Q @ vec
        if abs(p4d[3]) < 1e-9:
            continue
        p3d = p4d[:3] / p4d[3]
        points_3d.append(p3d)

    return np.array(points_3d) if points_3d else None


def fill_disparity_on_contour(contour, disparity, obj_mask, r=7):
    """
    Kontur uzerindeki gecersiz disparity'leri doldurur.
    Sadece nesne maskesinin ICINDEN ornekler — kontur sinirinda
    disaridan ornekleme arka plan derinligini nesneye atar.
    """
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    mask_ic = cv2.erode(obj_mask, kernel, iterations=1)
    gecerli = (disparity > 0) & (mask_ic > 0)

    h, w = disparity.shape
    filled = disparity.copy()
    doldurulan = 0
    doldurulamayan = 0

    for px, py in contour.reshape(-1, 2):
        px, py = int(px), int(py)
        if gecerli[py, px]:
            continue
        y_lo = max(0, py - r)
        y_hi = min(h, py + r + 1)
        x_lo = max(0, px - r)
        x_hi = min(w, px + r + 1)
        patch = disparity[y_lo:y_hi, x_lo:x_hi]
        pmask = gecerli[y_lo:y_hi, x_lo:x_hi]
        valid = patch[pmask]
        if len(valid) > 0:
            filled[py, px] = np.median(valid)
            doldurulan += 1
        else:
            filled[py, px] = 0
            doldurulamayan += 1

    return filled, doldurulan, doldurulamayan


def measure_3d_bbox(contour, disparity, Q, ground_normal, ground_d, obj_mask):
    """
    Konturun TUM noktalarinin 3B koordinatindan bounding box cikar.
    F-sekli, vazo gibi nesnelerde de en genis yeri yakalar.
    """
    filled_disp, doldurulan, doldurulamayan = fill_disparity_on_contour(
        contour, disparity, obj_mask)

    total_pts = len(contour.reshape(-1, 2))
    pts_3d = contour_points_to_3d(contour, filled_disp, Q)
    gecerli = len(pts_3d) if pts_3d is not None else 0
    oran = gecerli / total_pts * 100 if total_pts > 0 else 0
    print(f"  Kontur noktasi: {total_pts}, gecerli: {gecerli} (%{oran:.0f})")
    if doldurulan > 0 or doldurulamayan > 0:
        print(f"  Doldurulan: {doldurulan}, doldurulamayan: {doldurulamayan}")
    if oran < 70:
        print("  UYARI: Disparity kapsama orani dusuk — olcum guvenilmez!")

    if pts_3d is None or len(pts_3d) < 4:
        return None, None, None, None

    # Zemin duzlemi koordinat sistemine donustur
    # Normal vektoru z-ekseni, zemin uzerindeki iki eksen x ve y olsun
    n = ground_normal / np.linalg.norm(ground_normal)

    # Zemin uzerinde iki ortogonal eksen olustur
    if abs(n[0]) < 0.9:
        u = np.cross(n, np.array([1, 0, 0]))
    else:
        u = np.cross(n, np.array([0, 1, 0]))
    u = u / np.linalg.norm(u)
    v = np.cross(n, u)
    v = v / np.linalg.norm(v)

    # Her 3B noktayi zemin koordinat sistemine yansit
    # u,v = zemin uzerindeki eksenler, n = zemine dik (yukseklik)
    proj_u = pts_3d @ u
    proj_v = pts_3d @ v
    proj_n = pts_3d @ n + ground_d

    # EN ve BOY: zemin uzerindeki min/max aralik (metre → mm)
    dim_u = (proj_u.max() - proj_u.min()) * 1000
    dim_v = (proj_v.max() - proj_v.min()) * 1000

    # YUKSEKLIK: zeminden en yuksek noktaya olan dik mesafe (metre → mm)
    # Her zaman zemin normali yonunde — siralama YAPMA
    height = (proj_n.max() - proj_n.min()) * 1000

    # Zemin uzerindeki iki ekseni buyukten kucuge sirala
    en = max(dim_u, dim_v)
    boy = min(dim_u, dim_v)

    return en, boy, height, pts_3d


def suggest_box(width, length, height):
    from box_output import load_boxes, suggest_boxes
    try:
        boxes = load_boxes()
    except Exception:
        return None
    candidates = suggest_boxes(width, length, height, boxes)
    return candidates[0][1] if candidates else None


def append_diary(width, length, height, box_name):
    os.makedirs(os.path.dirname(DIARY_PATH), exist_ok=True)
    exists = os.path.exists(DIARY_PATH)
    with open(DIARY_PATH, "a", encoding="utf-8") as f:
        if not exists:
            f.write("tarih,saat,asama,not1,not2,deger,birim\n")
        now = datetime.datetime.now()
        date = now.strftime("%Y-%m-%d")
        time_ = now.strftime("%H:%M")
        f.write(f"{date},{time_},olcum,en,,{width:.1f},mm\n")
        f.write(f"{date},{time_},olcum,boy,,{length:.1f},mm\n")
        f.write(f"{date},{time_},olcum,yukseklik,,{height:.1f},mm\n")
        if box_name:
            f.write(f"{date},{time_},olcum,kutu_onerisi,,{box_name},\n")


def main():
    p = argparse.ArgumentParser(description="Nesne olcum")
    p.add_argument("--left", type=int, default=1)
    p.add_argument("--right", type=int, default=2)
    args = p.parse_args()

    calib, ground = load_all()
    map1x, map1y, map2x, map2y = setup_rectify(calib)
    stereo = setup_stereo_matcher()
    Q = calib["Q"]
    ground_normal = ground["normal"]
    ground_d = float(ground["d"])

    image_size = tuple(calib["image_size"])
    check_resolution(image_size)
    w, h = image_size

    cap_l = cv2.VideoCapture(args.left, cv2.CAP_DSHOW)
    cap_r = cv2.VideoCapture(args.right, cv2.CAP_DSHOW)
    for cap in [cap_l, cap_r]:
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'YUY2'))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)

    print("=" * 50)
    print("NESNE OLCUM MODU")
    print("=" * 50)
    print()
    print("Adimlar:")
    print("  1. Masayi bos birak, B tusuna bas → arka plan kaydedilir")
    print("  2. Nesneyi masaya koy")
    print("  3. M tusuna bas → olcum yapilir")
    print("  4. Tekrar olcmek icin yeni nesne koy ve M bas")
    print("  R: tekrar olcumu → tekrarlanabilirlik testi")
    print("  ESC ile cikis")
    print()

    bg_frame_l = None
    bg_frame_r = None
    last_result = None
    repeat_measurements = []
    golge_bastir = True
    orientation_0 = None

    while True:
        cap_l.grab()
        cap_r.grab()
        ret_l, frame_l = cap_l.retrieve()
        ret_r, frame_r = cap_r.retrieve()
        if not ret_l or not ret_r:
            continue

        rect_l = cv2.remap(frame_l, map1x, map1y, cv2.INTER_LINEAR)
        rect_r = cv2.remap(frame_r, map2x, map2y, cv2.INTER_LINEAR)

        display = rect_l.copy()

        if last_result:
            wi, le, he, box = last_result
            text = f"EN:{wi:.0f} BOY:{le:.0f} YUK:{he:.0f} mm"
            cv2.putText(display, text, (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            if box:
                cv2.putText(display, f"Kutu: {box['isim']}", (10, 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            if len(repeat_measurements) > 1:
                arr = np.array(repeat_measurements)
                std = arr.std(axis=0)
                cv2.putText(display,
                            f"Tekrar:{len(arr)} STD: {std[0]:.1f}/{std[1]:.1f}/{std[2]:.1f}",
                            (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 0), 1)

        golge_txt = "ACIK" if golge_bastir else "KAPALI"
        if bg_frame_l is None:
            cv2.putText(display, "B: arka plan kaydet", (10, h - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
        else:
            cv2.putText(display,
                        f"M:olcum R:tekrar O:yonelim G:golge({golge_txt}) B:arkaplan",
                        (10, h - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)

        cv2.imshow("Olcum", display)
        key = cv2.waitKey(30) & 0xFF

        if key == 27:
            break

        elif key == ord('b') or key == ord('B'):
            bg_frame_l = rect_l.copy()
            bg_frame_r = rect_r.copy()
            repeat_measurements = []
            print("Arka plan kaydedildi. Simdi nesneyi koy ve M bas.")

        elif key in (ord('g'), ord('G')):
            golge_bastir = not golge_bastir
            print(f"  Golge bastirma: {'ACIK' if golge_bastir else 'KAPALI'}")

        elif key in (ord('m'), ord('M'), ord('r'), ord('R'),
                     ord('o'), ord('O')):
            if bg_frame_l is None:
                print("  Once B ile arka plan kaydet!")
                continue

            is_repeat = key in (ord('r'), ord('R'))
            is_orient = key in (ord('o'), ord('O'))

            contour, mask = find_object_contour(rect_l, bg_frame_l, golge_bastir)
            if contour is None:
                print("  Nesne bulunamadi! Kontrast yetersiz veya nesne yok.")
                continue

            disp = stereo.compute(
                cv2.cvtColor(rect_l, cv2.COLOR_BGR2GRAY),
                cv2.cvtColor(rect_r, cv2.COLOR_BGR2GRAY)
            ).astype(np.float32) / 16.0

            width, length, height, pts_3d = measure_3d_bbox(
                contour, disp, Q, ground_normal, ground_d, mask)
            if width is None:
                print("  3B olcum basarisiz — disparity yetersiz.")
                print("  Nesne-masa kontrasti yeterli mi? Isik yeterli mi?")
                continue

            box = suggest_box(width, length, height)
            last_result = (width, length, height, box)

            if is_orient:
                if orientation_0 is None:
                    orientation_0 = (width, length, height)
                    print("\n  0 derece yonelim kaydedildi.")
                    print("  Simdi cismi 90 derece cevir ve tekrar O bas.")
                    continue
                else:
                    o0 = orientation_0
                    o90 = (width, length, height)
                    print("\n  YONELIM DUYARLILIGI TESTI:")
                    print(f"    0 derece:  {o0[0]:.1f} x {o0[1]:.1f} x {o0[2]:.1f} mm")
                    print(f"    90 derece: {o90[0]:.1f} x {o90[1]:.1f} x {o90[2]:.1f} mm")
                    d_en = abs(o0[0] - o90[1])
                    d_boy = abs(o0[1] - o90[0])
                    d_yuk = abs(o0[2] - o90[2])
                    print(f"    Fark:      en={d_en:.1f} boy={d_boy:.1f} yuk={d_yuk:.1f} mm")

                    now = datetime.datetime.now()
                    os.makedirs(os.path.dirname(DIARY_PATH), exist_ok=True)
                    with open(DIARY_PATH, "a", encoding="utf-8") as f:
                        date = now.strftime("%Y-%m-%d")
                        time_ = now.strftime("%H:%M")
                        f.write(f"{date},{time_},yonelim_duyarliligi,fark_en,,{d_en:.1f},mm\n")
                        f.write(f"{date},{time_},yonelim_duyarliligi,fark_boy,,{d_boy:.1f},mm\n")
                        f.write(f"{date},{time_},yonelim_duyarliligi,fark_yuk,,{d_yuk:.1f},mm\n")
                    print("  Olcum defterine yazildi.")
                    orientation_0 = None
                    continue

            if is_repeat:
                repeat_measurements.append([width, length, height])
            else:
                repeat_measurements = [[width, length, height]]

            print(f"\n  SONUC {'(tekrar #' + str(len(repeat_measurements)) + ')' if is_repeat else ''}:")
            print(f"    En:        {width:.1f} mm")
            print(f"    Boy:       {length:.1f} mm")
            print(f"    Yukseklik: {height:.1f} mm")
            if box:
                print(f"    Kutu:      {box['isim']} "
                      f"({box['en_mm']}x{box['boy_mm']}x{box['yukseklik_mm']} mm)")
                print(f"    Desi:      {box['desi']}")
            else:
                print("    Kutu:      Standart kutu bulunamadi")

            if len(repeat_measurements) > 1:
                arr = np.array(repeat_measurements)
                mean = arr.mean(axis=0)
                std = arr.std(axis=0)
                print(f"\n    Tekrarlanabilirlik ({len(arr)} olcum):")
                print(f"      Ortalama: {mean[0]:.1f} x {mean[1]:.1f} x {mean[2]:.1f}")
                print(f"      Std:      {std[0]:.1f} x {std[1]:.1f} x {std[2]:.1f}")

            append_diary(width, length, height,
                         box["isim"] if box else "yok")

            result_display = rect_l.copy()
            cv2.drawContours(result_display, [contour], -1, (0, 255, 0), 2)
            x, y, cw, ch = cv2.boundingRect(contour)
            cv2.rectangle(result_display, (x, y), (x+cw, y+ch), (0, 255, 255), 1)
            cv2.putText(result_display,
                        f"{width:.0f}x{length:.0f}x{height:.0f}mm",
                        (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            cv2.imshow("Sonuc", result_display)

    cap_l.release()
    cap_r.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
