"""Cut a character out of its plain backdrop so it can stand on a background (no extra model).

Portraits are drawn on a plain light-gray backdrop on purpose. The backdrop
colour is estimated from the image border, the backdrop region is flood-filled from
the edges on a downscaled copy (fast), the edge is refined at full resolution, and
the result is feathered by a pixel. Cached next to the image as ``<id>.sprite.png``.
"""

from __future__ import annotations

from pathlib import Path


def _backdrop_color(im) -> tuple[int, int, int]:
    w, h = im.size
    px = []
    for x in range(0, w, max(1, w // 64)):
        px += [im.getpixel((x, 0)), im.getpixel((x, h - 1))]
    for y in range(0, h, max(1, h // 64)):
        px += [im.getpixel((0, y)), im.getpixel((w - 1, y))]
    return tuple(sorted(p[i] for p in px)[len(px) // 2] for i in range(3))  # per-channel median


def _distance(im, color):
    from PIL import Image, ImageChops

    diff = ImageChops.difference(im, Image.new("RGB", im.size, color))
    r, g, b = diff.split()
    return ImageChops.lighter(ImageChops.lighter(r, g), b)  # max channel difference


def make_sprite(path: Path | str, threshold: int = 22) -> Path:
    from PIL import Image, ImageDraw, ImageFilter

    path = Path(path)
    out = path.with_suffix(".sprite.png")
    if out.exists() and out.stat().st_mtime >= path.stat().st_mtime:
        return out
    with Image.open(path) as src:
        im = src.convert("RGB")
    color = _backdrop_color(im)
    w, h = im.size
    # 1) backdrop region connected to the border, on a small copy
    scale = 4
    small = im.resize((w // scale, h // scale), Image.Resampling.BILINEAR)
    near = _distance(small, color).point(lambda v: 255 if v < threshold else 0)
    sw, sh = small.size
    # seeds on the top and sides only: half-body portraits are cut off at the bottom by design, so the
    # bottom edge is clothing (a pale dress there would otherwise be flooded away)
    seeds = [(x, 0) for x in range(0, sw, 4)] + [(0, y) for y in range(0, int(sh * 0.7), 4)] + \
            [(sw - 1, y) for y in range(0, int(sh * 0.7), 4)] + \
            [(x, sh - 1) for x in list(range(0, int(sw * 0.1), 2)) + list(range(int(sw * 0.9), sw, 2))]
    for xy in seeds:
        if near.getpixel(xy) == 255:
            ImageDraw.floodfill(near, xy, 128)
    region_small = near.point(lambda v: 255 if v == 128 else 0)
    # 2) keep only the main figure: specks of textured backdrop not connected to it are dropped
    figure = region_small.point(lambda v: 0 if v else 255)
    cx, cy = sw // 2, int(sh * 0.6)
    if figure.getpixel((cx, cy)) == 255:
        ImageDraw.floodfill(figure, (cx, cy), 128)
        islands = figure.point(lambda v: 255 if v == 255 else 0)  # opaque but not part of the figure
    else:
        islands = Image.new("L", small.size, 0)
    region = region_small.filter(ImageFilter.MaxFilter(3))
    region = region.resize((w, h), Image.Resampling.BILINEAR).point(lambda v: 255 if v > 64 else 0)
    islands = islands.resize((w, h), Image.Resampling.BILINEAR).point(lambda v: 255 if v > 128 else 0)
    # 3) at full size, only pixels that also look like the backdrop are removed at the figure's edge (crisp)
    full_near = _distance(im, color).point(lambda v: 255 if v < threshold + 6 else 0)
    from PIL import ImageChops

    backdrop = ImageChops.lighter(ImageChops.multiply(region, full_near), islands)
    # opening (erode, then dilate) shaves off slivers of backdrop stuck to the outline; then feather
    alpha = ImageChops.invert(backdrop).filter(ImageFilter.MinFilter(5)).filter(ImageFilter.MinFilter(3))
    alpha = alpha.filter(ImageFilter.MaxFilter(3))  # net: ~2px in, so no light halo from the backdrop
    alpha = alpha.filter(ImageFilter.GaussianBlur(1))
    sprite = im.convert("RGBA")
    sprite.putalpha(alpha)
    # trim empty margins at the top/sides so sprites line up on stage
    box = alpha.point(lambda v: 255 if v > 16 else 0).getbbox()
    if box:
        sprite = sprite.crop((box[0], box[1], box[2], h))
    sprite.save(out, "PNG", optimize=True)
    return out
