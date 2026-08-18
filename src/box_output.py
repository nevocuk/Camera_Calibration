"""
Kutu onerisi ve RSC kesim sablonu uretici.

Kullanim:
    python src/box_output.py --en 250 --boy 180 --yukseklik 120
    python src/box_output.py --en 250 --boy 180 --yukseklik 120 --no-svg

Cikti:
    - Terminale kutu onerisi
    - output/box_templates/ altina RSC kesim sablonu (SVG — yazdirmadan
      once PDF'e cevir; SVG olculer mm cinsinden 1:1'dir)
"""
import os
import sys
import json
import math
import argparse
import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
BOX_PATH = os.path.join(PROJECT_DIR, "data", "kutu_tablosu.json")
TEMPLATE_DIR = os.path.join(PROJECT_DIR, "output", "box_templates")
DIARY_PATH = os.path.join(PROJECT_DIR, "data", "olcum_defteri.csv")
os.makedirs(TEMPLATE_DIR, exist_ok=True)


def load_boxes():
    """kutu_tablosu.json'u oku, cm -> mm cevir, tek tip sozluk dondur."""
    with open(BOX_PATH, encoding="utf-8") as f:
        data = json.load(f)
    boxes = []
    for k in data["kutular"]:
        en, boy, yuk = k["olcu"]
        boxes.append({
            "isim": k["ad"],
            "no": k["no"],
            "en_mm": en * 10,
            "boy_mm": boy * 10,
            "yukseklik_mm": yuk * 10,
            "desi": k["desi"],
        })
    return boxes


def suggest_boxes(width, length, height, boxes, margin=10):
    dims = sorted([width, length, height], reverse=True)
    candidates = []

    for box in boxes:
        bw = box["en_mm"]
        bl = box["boy_mm"]
        bh = box["yukseklik_mm"]
        bdims = sorted([bw, bl, bh], reverse=True)

        if (bdims[0] >= dims[0] + margin and
            bdims[1] >= dims[1] + margin and
            bdims[2] >= dims[2] + margin):
            waste = (bdims[0] * bdims[1] * bdims[2]) - (dims[0] * dims[1] * dims[2])
            candidates.append((waste, box))

    candidates.sort(key=lambda x: x[0])
    return candidates


def calculate_desi(en_cm, boy_cm, yuk_cm):
    return en_cm * boy_cm * yuk_cm / 3000


def generate_rsc_template_svg(en_mm, boy_mm, yuk_mm, out_path):
    """
    RSC (Regular Slotted Container) kesim sablonu.
    Bir karton parcasindan katlanarak kutu olusturulur.

    Sablon yapisi:
    ┌─────────┬─────────┬─────────┬─────────┬───┐
    │  klape  │  klape  │  klape  │  klape  │   │
    ├─────────┼─────────┼─────────┼─────────┤   │
    │         │         │         │         │yap│
    │   boy   │   en    │   boy   │   en    │   │
    │         │         │         │         │   │
    ├─────────┼─────────┼─────────┼─────────┤   │
    │  klape  │  klape  │  klape  │  klape  │   │
    └─────────┴─────────┴─────────┴─────────┴───┘
    """
    e = en_mm
    b = boy_mm
    h = yuk_mm
    flap = h / 2
    glue = 25

    total_w = b + e + b + e + glue
    total_h = flap + h + flap

    margin = 20
    svg_w = total_w + 2 * margin
    svg_h = total_h + 2 * margin + 60

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" '
                 f'width="{svg_w:.0f}" height="{svg_h:.0f}" '
                 f'viewBox="0 0 {svg_w:.0f} {svg_h:.0f}">')
    lines.append('<style>')
    lines.append('  .cut { stroke: red; stroke-width: 0.5; fill: none; }')
    lines.append('  .fold { stroke: blue; stroke-width: 0.5; fill: none; '
                 'stroke-dasharray: 5,3; }')
    lines.append('  .dim { font-size: 10px; fill: #333; '
                 'font-family: sans-serif; text-anchor: middle; }')
    lines.append('  .title { font-size: 12px; fill: #333; '
                 'font-family: sans-serif; font-weight: bold; }')
    lines.append('</style>')

    ox = margin
    oy = margin

    # Dis cerceve (kesim)
    lines.append(f'<rect x="{ox}" y="{oy}" '
                 f'width="{total_w}" height="{total_h}" class="cut"/>')

    # Dikey katlama cizgileri
    x_folds = [b, b + e, b + e + b, b + e + b + e]
    for xf in x_folds:
        lines.append(f'<line x1="{ox + xf}" y1="{oy}" '
                     f'x2="{ox + xf}" y2="{oy + total_h}" class="fold"/>')

    # Yatay katlama cizgileri (ust ve alt klape)
    lines.append(f'<line x1="{ox}" y1="{oy + flap}" '
                 f'x2="{ox + total_w - glue}" y2="{oy + flap}" class="fold"/>')
    lines.append(f'<line x1="{ox}" y1="{oy + flap + h}" '
                 f'x2="{ox + total_w - glue}" y2="{oy + flap + h}" class="fold"/>')

    # Klape kesim cizgileri (ust)
    for i, xf in enumerate(x_folds):
        lines.append(f'<line x1="{ox + xf}" y1="{oy}" '
                     f'x2="{ox + xf}" y2="{oy + flap}" class="cut"/>')
    # Klape kesim cizgileri (alt)
    for i, xf in enumerate(x_folds):
        lines.append(f'<line x1="{ox + xf}" y1="{oy + flap + h}" '
                     f'x2="{ox + xf}" y2="{oy + total_h}" class="cut"/>')

    # Olcu yazilari
    ty = oy + total_h + 15
    sections = [("BOY", b), ("EN", e), ("BOY", b), ("EN", e), ("YAP", glue)]
    sx = ox
    for label, width in sections:
        cx = sx + width / 2
        lines.append(f'<text x="{cx}" y="{ty}" class="dim">'
                     f'{label} {width:.0f}mm</text>')
        sx += width

    # Yukseklik
    rx = ox + total_w + 5
    cy = oy + flap + h / 2
    lines.append(f'<text x="{rx}" y="{cy}" class="dim" '
                 f'transform="rotate(90,{rx},{cy})">'
                 f'YUKSEKLIK {h:.0f}mm</text>')

    # Baslik
    lines.append(f'<text x="{svg_w/2}" y="{svg_h - 15}" class="title" '
                 f'text-anchor="middle">'
                 f'RSC Kesim Sablonu — {e:.0f} x {b:.0f} x {h:.0f} mm</text>')

    # Lejant
    lines.append(f'<line x1="{ox}" y1="{svg_h - 35}" '
                 f'x2="{ox + 20}" y2="{svg_h - 35}" '
                 f'stroke="red" stroke-width="1"/>')
    lines.append(f'<text x="{ox + 25}" y="{svg_h - 31}" class="dim" '
                 f'text-anchor="start">Kesim</text>')
    lines.append(f'<line x1="{ox + 70}" y1="{svg_h - 35}" '
                 f'x2="{ox + 90}" y2="{svg_h - 35}" '
                 f'stroke="blue" stroke-width="1" stroke-dasharray="5,3"/>')
    lines.append(f'<text x="{ox + 95}" y="{svg_h - 31}" class="dim" '
                 f'text-anchor="start">Katlama</text>')

    lines.append('</svg>')
    svg_content = '\n'.join(lines)

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(svg_content)

    return svg_content


def main():
    p = argparse.ArgumentParser(description="Kutu onerisi ve kesim sablonu")
    p.add_argument("--en", type=float, required=True, help="Nesne eni (mm)")
    p.add_argument("--boy", type=float, required=True, help="Nesne boyu (mm)")
    p.add_argument("--yukseklik", type=float, required=True, help="Nesne yuksekligi (mm)")
    p.add_argument("--margin", type=float, default=10, help="Kutu pay (mm)")
    p.add_argument("--no-svg", action="store_true",
                   help="SVG kesim sablonu uretme (varsayilan: uretir)")
    args = p.parse_args()

    boxes = load_boxes()
    candidates = suggest_boxes(args.en, args.boy, args.yukseklik, boxes, margin=args.margin)
    desi = calculate_desi(args.en / 10, args.boy / 10, args.yukseklik / 10)

    print("=" * 55)
    print("KUTU ONERISI")
    print("=" * 55)
    print(f"\n  Nesne: {args.en:.0f} x {args.boy:.0f} x {args.yukseklik:.0f} mm")
    print(f"  Nesne desi: {desi:.2f}")
    print()

    if not candidates:
        print("  Standart kutularin hicbiri yeterli degil!")
        print("  Ozel kesim gerekli.")
    else:
        print(f"  Uygun kutular ({len(candidates)} adet):\n")
        for i, (waste, box) in enumerate(candidates[:5]):
            marker = " <<<" if i == 0 else ""
            print(f"  {i+1}. {box['isim']:12s}  "
                  f"{box['en_mm']}x{box['boy_mm']}x{box['yukseklik_mm']} mm  "
                  f"desi={box['desi']:.1f}  "
                  f"fire={waste/1000:.0f} cm³{marker}")

        best = candidates[0][1]
        print(f"\n  ONERILEN: {best['isim']}")

    if not args.no_svg:
        box_en = args.en + args.margin
        box_boy = args.boy + args.margin
        box_yuk = args.yukseklik + args.margin

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        svg_path = os.path.join(
            TEMPLATE_DIR,
            f"kesim_{args.en:.0f}x{args.boy:.0f}x{args.yukseklik:.0f}_{timestamp}.svg")

        generate_rsc_template_svg(box_en, box_boy, box_yuk, svg_path)
        print(f"\n  Kesim sablonu: {svg_path}")

    # Deftere yaz
    now = datetime.datetime.now()
    os.makedirs(os.path.dirname(DIARY_PATH), exist_ok=True)
    exists = os.path.exists(DIARY_PATH)
    with open(DIARY_PATH, "a", encoding="utf-8") as f:
        # Sema: tarih,saat,asama,parametre,ayar,deger,birim,not (8 sutun)
        if not exists:
            f.write("tarih,saat,asama,parametre,ayar,deger,birim,not\n")
        date = now.strftime("%Y-%m-%d")
        time_ = now.strftime("%H:%M")
        if candidates:
            best = candidates[0][1]
            f.write(f"{date},{time_},kutu_onerisi,{best['isim']},"
                    f"{args.en:.0f}x{args.boy:.0f}x{args.yukseklik:.0f},"
                    f"{best['desi']:.1f},desi,\n")


if __name__ == "__main__":
    main()
