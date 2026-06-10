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
AVERY_TEMPLATES: dict[str, dict] = {
    "5160": {
        "label": "Avery 5160 / 8460 — 1\" × 2⅝\" (30 per sheet)",
        "label_width": 2.625 * inch,
        "label_height": 1.0 * inch,
        "margin_left": 0.1875 * inch,
        "margin_top": 0.5 * inch,
        "columns": 3,
        "rows": 10,
        "h_gap": 0.125 * inch,
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
        "label": "Avery 5260 / 5520 — 1\" × 2⅝\" (30 per sheet)",
        "label_width": 2.625 * inch,
        "label_height": 1.0 * inch,
        "margin_left": 0.1875 * inch,
        "margin_top": 0.5 * inch,
        "columns": 3,
        "rows": 10,
        "h_gap": 0.125 * inch,
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
    """Return bottom-left (x, y) for each label slot, row-major from top-left."""
    positions = []
    page_height = 11 * inch

    for row in range(template["rows"]):
        for col in range(template["columns"]):
            x = template["margin_left"] + col * (
                template["label_width"] + template["h_gap"]
            )
            y = (
                page_height
                - template["margin_top"]
                - (row + 1) * template["label_height"]
                - row * template["v_gap"]
            )
            positions.append((x, y))

    return positions


def _prepare_icon_png(image_bytes: bytes | None, max_pixels: int = 200) -> bytes | None:
    """Resize and flatten an uploaded icon for reliable PDF embedding."""
    if not image_bytes:
        return None

    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.load()
    except Exception:
        return None

    image = image.convert("RGBA")
    image.thumbnail((max_pixels, max_pixels), Image.Resampling.LANCZOS)

    # Flatten transparency onto white — works reliably in ReportLab PDFs.
    flat = Image.new("RGB", image.size, (255, 255, 255))
    flat.paste(image, mask=image.split()[3])

    out = io.BytesIO()
    flat.save(out, format="PNG")
    return out.getvalue()


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
    icon_png: bytes | None,
    style: LabelStyle,
) -> None:
    fonts = FONT_FAMILIES[style.font_family]
    pad = 2
    icon_slot = min(height - 2 * pad, width * 0.25) if icon_png else 0
    text_x = x + pad + (icon_slot + pad if icon_png else 0)
    text_width = width - (text_x - x) - pad

    if icon_png and icon_slot > 0:
        icon_y = y + (height - icon_slot) / 2
        pdf.drawImage(
            ImageReader(io.BytesIO(icon_png)),
            x + pad,
            icon_y,
            width=icon_slot,
            height=icon_slot,
            preserveAspectRatio=True,
            mask=None,
        )

    common = plant.get("Common Name", "")
    scientific = plant.get("Scientific Name", "")
    light = simplify_light(plant.get("Light", ""))
    water = simplify_water(plant.get("Water", ""))
    care_line = f"Light: {light}  |  Water: {water}"

    line_gap = 1
    cursor_y = y + height - pad

    pdf.setFont(fonts["bold"], style.common_size)
    common = _truncate_to_width(pdf, common, fonts["bold"], style.common_size, text_width)
    cursor_y -= style.common_size
    pdf.drawString(text_x, cursor_y, common)

    pdf.setFont(fonts["italic"], style.scientific_size)
    sci_text = f"({scientific})"
    sci_text = _truncate_to_width(
        pdf, sci_text, fonts["italic"], style.scientific_size, text_width
    )
    cursor_y -= line_gap + style.scientific_size
    pdf.drawString(text_x, cursor_y, sci_text)

    pdf.setFont(fonts["regular"], style.care_size)
    care_line = _truncate_to_width(
        pdf, care_line, fonts["regular"], style.care_size, text_width
    )
    cursor_y -= line_gap + style.care_size
    pdf.drawString(text_x, cursor_y, care_line)


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
    icon_png = _prepare_icon_png(icon_bytes)

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
            icon_png,
            style,
        )

    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()


def render_pdf_preview_png(pdf_bytes: bytes, zoom: float = 2.0) -> bytes:
    """Render the first PDF page to PNG for in-app preview (Chrome-safe)."""
    import fitz

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    return pix.tobytes("png")
