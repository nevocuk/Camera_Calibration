"""
ChArUco kalibrasyon deseni uretici.
Ciktisi: patterns/charuco_board.png + data/charuco_config.json
Basim notu: %100 olcek / gercek boyut ile bas, kumpasla dogrula.
"""
import cv2
import json
import os
import numpy as np

SQUARES_X = 7
SQUARES_Y = 5
SQUARE_LENGTH_MM = 30
MARKER_LENGTH_MM = 22
ARUCO_DICT_NAME = "DICT_5X5_50"
DPI = 150

aruco_dict = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, ARUCO_DICT_NAME))
board = cv2.aruco.CharucoBoard(
    (SQUARES_X, SQUARES_Y),
    SQUARE_LENGTH_MM / 1000.0,
    MARKER_LENGTH_MM / 1000.0,
    aruco_dict
)

board_width_mm = SQUARES_X * SQUARE_LENGTH_MM
board_height_mm = SQUARES_Y * SQUARE_LENGTH_MM

px_per_mm = DPI / 25.4
img_w = int(board_width_mm * px_per_mm)
img_h = int(board_height_mm * px_per_mm)

margin_mm = 15
margin_px = int(margin_mm * px_per_mm)

board_img = board.generateImage((img_w, img_h), marginSize=margin_px, borderBits=1)

script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)

img_path = os.path.join(script_dir, "charuco_board.png")
cv2.imwrite(img_path, board_img)
print(f"Desen kaydedildi: {img_path}")
print(f"Desen boyutu: {board_width_mm} x {board_height_mm} mm")
print(f"Goruntu boyutu: {img_w} x {img_h} px ({DPI} DPI)")
print()
print("!!! BASIM UYARISI !!!")
print("1) Yazicida '%100 olcek' / 'gercek boyut' / 'olceklendirme yok' sec")
print("2) Basili desendeki bir kareyi kumpasla olc")
print(f"3) Beklenen kare boyutu: {SQUARE_LENGTH_MM} mm")
print("4) Olculen degeri asagidaki config dosyasina ve koda gir")

config = {
    "squares_x": SQUARES_X,
    "squares_y": SQUARES_Y,
    "square_length_mm": SQUARE_LENGTH_MM,
    "marker_length_mm": MARKER_LENGTH_MM,
    "aruco_dict": ARUCO_DICT_NAME,
    "olculen_kare_boyutu_mm": None,
    "not": "Basili deseni kumpasla olcup bu degeri doldur. None birakilirsa kalibrasyon hata verir."
}

config_path = os.path.join(project_dir, "data", "charuco_config.json")
with open(config_path, "w", encoding="utf-8") as f:
    json.dump(config, f, indent=2, ensure_ascii=False)
print(f"\nConfig kaydedildi: {config_path}")
