"""Generate printable Avery label PDFs for plant data."""

from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from plant_scraper import simplify_light, simplify_water

# Avery specs: label size and grid on US Letter (8.5" x 11").
# 5160/5260: labels exactly 2.125" × 1", no vertical gaps, 1/8" column gutters.
AVERY_TEMPLATES: dict[str, dict] = {
    "5160": {
        # Exact label size: 2.125" × 1". No vertical gaps (10 rows = 10").
        # 1/8" column gutters; left/right margins centered on letter page.
        "label": "Avery 5160 / 8460 — 1\" × 2.125\" (30 per sheet)",
        "label_width": 2.125 * inch,
        "label_height": 1.0 * inch,
        "margin_left": ((8.5 - (3 * 2.125) - (2 * (1 / 8))) / 2) * inch,
        "margin_top": 0.5 * inch,
        "columns": 3,
        "rows": 10,
        "h_gap": (1 / 8) * inch,
        "v_gap": 0.0,
    },
    "5161": {
        "label": "Avery 5161 / 8461 — 1\" × 4\" (20 per sheet)",
        "label_width": 4.0 * inch,
        "label_height": 1.0 * inch,
        "margin_left": 0.15625 * inch,
        "margin_top": 0.5 * inch,
        "columns": 2,
        "rows": 10,
        "h_gap": 0.1875 * inch,
        "v_gap": 0.0,
    },
    "5162": {
        "label": "Avery 5162 / 8462 — 1⅓\" × 4\" (14 per sheet)",
        "label_width": 4.0 * inch,
        "label_height": 1.333 * inch,
        "margin_left": 0.15625 * inch,
        "margin_top": 0.83 * inch,
        "columns": 2,
        "rows": 7,
        "h_gap": 0.1875 * inch,
        "v_gap": 0.0,
    },
    "5163": {
        "label": "Avery 5163 / 8463 — 2\" × 4\" (10 per sheet)",
        "label_width": 4.0 * inch,
        "label_height": 2.0 * inch,
        "margin_left": 0.15625 * inch,
        "margin_top": 0.5 * inch,
        "columns": 2,
        "rows": 5,
        "h_gap": 0.1875 * inch,
        "v_gap": 0.0,
    },
    "5164": {
        "label": "Avery 5164 / 8464 — 3⅓\" × 4\" (6 per sheet)",
        "label_width": 4.0 * inch,
        "label_height": 3.333 * inch,
        "margin_left": 0.15625 * inch,
        "margin_top": 0.5 * inch,
        "columns": 2,
        "rows": 3,
        "h_gap": 0.1875 * inch,
        "v_gap": 0.0,
    },
    "5260": {
        # Same exact sheet layout as 5160.
        "label": "Avery 5260 / 5520 — 1\" × 2.125\" (30 per sheet)",
        "label_width": 2.125 * inch,
        "label_height": 1.0 * inch,
        "margin_left": ((8.5 - (3 * 2.125) - (2 * (1 / 8))) / 2) * inch,
        "margin_top": 0.5 * inch,
        "columns": 3,
        "rows": 10,
        "h_gap": (1 / 8) * inch,
        "v_gap": 0.0,
    },
}

FONT_FAMILIES = {
    "Helvetica (clean sans-serif)": {
        "regular": "Helvetica",
        "bold": "Helvetica-Bold",
        "italic": "Helvetica-Oblique",
    },
    "Times (classic serif)": {
        "regular": "Times-Roman",
        "bold": "Times-Bold",
        "italic": "Times-Italic",
    },
    "Courier (monospace)": {
        "regular": "Courier",
        "bold": "Courier-Bold",
        "italic": "Courier-Oblique",
    },
}


@dataclass
class LabelStyle:
    font_family: str = "Helvetica (clean sans-serif)"
    common_size: int = 8
    scientific_size: int = 7
    care_size: int = 6


def template_choices() -> dict[str, str]:
    return {code: spec["label"] for code, spec in AVERY_TEMPLATES.items()}


def _label_positions(template: dict) -> list[tuple[float, float]]:
    """Return bottom-left (x, y) for each label slot, row-major from top-left.

    Vertical pitch is exactly label_height + v_gap so lower rows cannot
    drift upward into the row above.
    """
    positions = []
    page_height = 11 * inch
    label_w = template["label_width"]
    label_h = template["label_height"]
    margin_left = template["margin_left"]
    margin_top = template["margin_top"]
    h_gap = template["h_gap"]
    v_gap = template["v_gap"]
    # Top edge of row 0, then step down by exact pitch each row.
    top_of_first = page_height - margin_top
    pitch = label_h + v_gap

    for row in range(template["rows"]):
        top_y = top_of_first - row * pitch
        bottom_y = top_y - label_h
        for col in range(template["columns"]):
            x = margin_left + col * (label_w + h_gap)
            positions.append((x, bottom_y))

    return positions


def _fit_icon(image_bytes: bytes | None, max_size: float) -> ImageReader | None:
    if not image_bytes:
        return None

    image = Image.open(io.BytesIO(image_bytes))
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGBA")

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return ImageReader(buffer)


def _truncate_to_width(
    pdf: canvas.Canvas,
    text: str,
    font_name: str,
    font_size: float,
    max_width: float,
) -> str:
    if pdf.stringWidth(text, font_name, font_size) <= max_width:
        return text

    trimmed = text
    while trimmed and pdf.stringWidth(trimmed + "…", font_name, font_size) > max_width:
        trimmed = trimmed[:-1]
    return (trimmed + "…") if trimmed else ""


def _draw_single_label(
    pdf: canvas.Canvas,
    x: float,
    y: float,
    width: float,
    height: float,
    plant: dict,
    icon_reader: ImageReader | None,
    style: LabelStyle,
) -> None:
    """Draw one label clipped to its exact  bounding box."""
    fonts = FONT_FAMILIES[style.font_family]
    pad = 3  # points; keep content inside the die-cut
    content_left = x + pad
    content_right = x + width - pad
    content_bottom = y + pad
    content_top = y + height - pad
    content_width = max(0, content_right - content_left)
    content_height = max(0, content_top - content_bottom)

    pdf.saveState()
    clip = pdf.beginPath()
    clip.rect(x, y, width, height)
    pdf.clipPath(clip, stroke=0, fill=0)

    icon_slot = 0.0
    if icon_reader and content_height > 0:
        icon_slot = min(content_height, content_width * 0.22)

    text_x = content_left + (icon_slot + pad if icon_slot else 0)
    text_width = max(0, content_right - text_x)

    if icon_reader and icon_slot > 0:
        pdf.drawImage(
            icon_reader,
            content_left,
            y + (height - icon_slot) / 2,
            width=icon_slot,
            height=icon_slot,
            preserveAspectRatio=True,
            anchor="sw",
            mask="auto",
        )

    common = plant.get("Common Name", "")
    scientific = plant.get("Scientific Name", "")
    light = simplify_light(plant.get("Light", ""))
    water = simplify_water(plant.get("Water", ""))

    line_gap = 1
    cursor_y = content_top

    def draw_line(text: str, font_key: str, size: float) -> None:
        nonlocal cursor_y
        # Baseline must stay above the content bottom; skip if no room.
        if cursor_y - size < content_bottom - 0.01:
            return
        font_name = fonts[font_key]
        pdf.setFont(font_name, size)
        fitted = _truncate_to_width(pdf, text, font_name, size, text_width)
        cursor_y -= size
        pdf.drawString(text_x, cursor_y, fitted)
        cursor_y -= line_gap

    draw_line(common, "bold", style.common_size)
    draw_line(f"({scientific})", "italic", style.scientific_size)
    draw_line(f"Light: {light}", "regular", style.care_size)
    draw_line(f"Water: {water}", "regular", style.care_size)

    pdf.restoreState()


def build_labels_pdf(
    plants: list[dict],
    template_code: str,
    style: LabelStyle | None = None,
    icon_bytes: bytes | None = None,
) -> bytes:
    """Build a multi-page Avery label PDF and return raw bytes."""
    if template_code not in AVERY_TEMPLATES:
        raise ValueError(f"Unknown Avery template: {template_code}")

    style = style or LabelStyle()
    template = AVERY_TEMPLATES[template_code]
    slots = _label_positions(template)
    labels_per_sheet = len(slots)

    if not plants:
        raise ValueError("No plant data to print.")

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(8.5 * inch, 11 * inch))
    icon_reader = _fit_icon(icon_bytes, template["label_height"])

    for index, plant in enumerate(plants):
        if index > 0 and index % labels_per_sheet == 0:
            pdf.showPage()

        slot_index = index % labels_per_sheet
        x, y = slots[slot_index]
        _draw_single_label(
            pdf,
            x,
            y,
            template["label_width"],
            template["label_height"],
            plant,
            icon_reader,
            style,
        )

    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()
