"""
Generate OG image for engine.crelytic.ai (1200x630).

Dark navy gradient background with CRELYTIC Engine branding.
Uses only Pillow built-in capabilities -- no external TTF files required.
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def lerp_color(c1: tuple, c2: tuple, t: float) -> tuple:
    """Linearly interpolate between two RGB colours."""
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def draw_gradient(draw: ImageDraw.Draw, width: int, height: int,
                  top_color: tuple, bottom_color: tuple):
    """Fill the image with a vertical gradient."""
    for y in range(height):
        color = lerp_color(top_color, bottom_color, y / height)
        draw.line([(0, y), (width, y)], fill=color)


def generate_og_image(output_path: str | Path):
    W, H = 1200, 630

    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)

    # --- gradient background ---
    top = (10, 22, 40)      # #0A1628
    bottom = (15, 34, 54)   # #0F2236
    draw_gradient(draw, W, H, top, bottom)

    # --- subtle accent line ---
    accent_teal = (0, 191, 165)    # #00BFA5
    line_y = H // 2 + 100
    draw.line([(200, line_y), (W - 200, line_y)], fill=(*accent_teal, 60), width=2)

    # --- load fonts (Pillow default at various sizes) ---
    try:
        font_brand = ImageFont.truetype("arial.ttf", 96)
        font_engine = ImageFont.truetype("arial.ttf", 96)
        font_tagline = ImageFont.truetype("arial.ttf", 32)
        font_url = ImageFont.truetype("arial.ttf", 22)
    except (OSError, IOError):
        # Fall back to Pillow's built-in bitmap font (much smaller, but works everywhere)
        font_brand = ImageFont.load_default()
        font_engine = font_brand
        font_tagline = font_brand
        font_url = font_brand

    white = (255, 255, 255)
    teal = (0, 191, 165)        # #00BFA5
    slate = (148, 163, 184)     # #94A3B8
    muted = (100, 116, 139)     # #64748B

    # --- "CRELYTIC" + "Engine" on the same line, centered ---
    brand_text = "CRELYTIC"
    engine_text = " Engine"

    brand_bbox = draw.textbbox((0, 0), brand_text, font=font_brand)
    engine_bbox = draw.textbbox((0, 0), engine_text, font=font_engine)

    brand_w = brand_bbox[2] - brand_bbox[0]
    engine_w = engine_bbox[2] - engine_bbox[0]
    total_w = brand_w + engine_w

    x_start = (W - total_w) // 2
    y_title = H // 2 - 100

    draw.text((x_start, y_title), brand_text, fill=white, font=font_brand)
    draw.text((x_start + brand_w, y_title), engine_text, fill=teal, font=font_engine)

    # --- tagline ---
    tagline = "AI-Powered CRE Deal Underwriting"
    tag_bbox = draw.textbbox((0, 0), tagline, font=font_tagline)
    tag_w = tag_bbox[2] - tag_bbox[0]
    draw.text(((W - tag_w) // 2, y_title + 120), tagline, fill=slate, font=font_tagline)

    # --- URL at bottom ---
    url_text = "engine.crelytic.ai"
    url_bbox = draw.textbbox((0, 0), url_text, font=font_url)
    url_w = url_bbox[2] - url_bbox[0]
    draw.text(((W - url_w) // 2, H - 70), url_text, fill=muted, font=font_url)

    # --- small decorative teal rectangles ---
    rect_w, rect_h = 40, 4
    draw.rectangle([(W // 2 - rect_w // 2 - 60, y_title + 105),
                     (W // 2 - rect_w // 2 - 60 + rect_w, y_title + 105 + rect_h)],
                    fill=teal)
    draw.rectangle([(W // 2 + rect_w // 2 + 20, y_title + 105),
                     (W // 2 + rect_w // 2 + 20 + rect_w, y_title + 105 + rect_h)],
                    fill=teal)

    # --- save ---
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output_path), "PNG", optimize=True)
    print(f"OG image saved to {output_path}  ({W}x{H})")


if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "frontend" / "static" / "og-image.png"
    generate_og_image(out)
