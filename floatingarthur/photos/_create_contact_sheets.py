from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).parent
SETS = {
    "line2_opening_1983_contact_sheet.jpg": ROOT / "history_photo" / "euljiro_line2_opening_1983",
    "underpass_construction_1976_contact_sheet.jpg": ROOT / "history_photo" / "euljiro_entrance_underpass_construction_1976",
    "entrance_surroundings_1983_contact_sheet.jpg": ROOT / "history_photo" / "euljiro_entrance_surroundings_1983",
}
OUT = ROOT / "contact_sheets"
OUT.mkdir(exist_ok=True)


def make_sheet(output_name: str, source_dir: Path) -> None:
    paths = sorted(p for p in source_dir.rglob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    columns, cell_w, cell_h, label_h, gap = 4, 320, 220, 40, 16
    rows = (len(paths) + columns - 1) // columns
    canvas = Image.new("RGB", (gap + columns * (cell_w + gap), gap + rows * (cell_h + label_h + gap)), "#1b1b1b")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()

    for index, path in enumerate(paths):
        col, row = index % columns, index // columns
        x, y = gap + col * (cell_w + gap), gap + row * (cell_h + label_h + gap)
        with Image.open(path) as image:
            image = image.convert("RGB")
            image.thumbnail((cell_w, cell_h))
            frame = Image.new("RGB", (cell_w, cell_h), "#303030")
            frame.paste(image, ((cell_w - image.width) // 2, (cell_h - image.height) // 2))
        canvas.paste(frame, (x, y))
        draw.text((x, y + cell_h + 10), f"{index + 1:02d}. {path.name[:35]}", fill="white", font=font)

    canvas.save(OUT / output_name, quality=90)


for output, source in SETS.items():
    make_sheet(output, source)
