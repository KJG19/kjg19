"""Turns a photo into ASCII art for the left side of the profile card.

Usage:
    python make_ascii.py photo.jpg                 # writes ascii.txt
    python make_ascii.py photo.jpg --cols 42 --invert --contrast 1.4

For a busy background, cut it out first (transparent PNG) so it turns into blank space.
Tips: a front-facing headshot on a plain background works best. Crop the
photo close to your head and shoulders before running this.
"""
import argparse
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

# light -> dense. On the dark card, dense characters read as bright.
RAMP = " .'`,:;!|ijlk%HM@"


def convert(path, cols, rows, contrast, invert, crop=None, equalize=False, sharpen=0):
    src = Image.open(path).convert("RGBA")
    if crop:
        src = src.crop(crop)
    alpha = src.getchannel("A").resize((cols, rows), Image.LANCZOS).load()
    mask = src.getchannel("A").point(lambda a: 255 if a > 128 else 0)
    img = src.convert("L")
    if equalize:
        img = ImageOps.equalize(img, mask=mask)     # spreads out tones so eyes/brows stand out on even skin
    else:
        img = ImageOps.autocontrast(img, cutoff=2, mask=mask)
    if sharpen:
        img = img.filter(ImageFilter.UnsharpMask(radius=4, percent=sharpen, threshold=2))
    img = ImageEnhance.Contrast(img).enhance(contrast)
    if not invert:
        img = ImageOps.invert(img)     # default: dark pixels (hair, eyes) become dense characters
    img = img.resize((cols, rows), Image.LANCZOS)
    px = img.load()
    lines = []
    for y in range(rows):
        # transparent pixels (removed background) become blank space
        line = "".join(" " if alpha[x, y] < 100 else RAMP[px[x, y] * (len(RAMP) - 1) // 255] for x in range(cols))
        lines.append(line.rstrip())
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("photo")
    ap.add_argument("--cols", type=int, default=40)
    ap.add_argument("--rows", type=int, default=24)
    ap.add_argument("--contrast", type=float, default=1.3)
    ap.add_argument("--invert", action="store_true", help="flip which areas become dense characters")
    ap.add_argument("--equalize", action="store_true", help="boost detail in evenly lit faces")
    ap.add_argument("--sharpen", type=int, default=0, help="edge sharpening strength, e.g. 150")
    ap.add_argument("--crop", help="x1,y1,x2,y2 box to crop to first")
    ap.add_argument("--out", default=str(Path(__file__).parent / "ascii.txt"))
    args = ap.parse_args()

    crop = tuple(int(v) for v in args.crop.split(",")) if args.crop else None
    lines = convert(args.photo, args.cols, args.rows, args.contrast, args.invert, crop, args.equalize, args.sharpen)
    Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
