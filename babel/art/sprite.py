"""Cut a character out of its plain backdrop so it can stand on a background (no extra model).

Portraits are drawn on a plain light-gray backdrop on purpose. The backdrop
colour is estimated from the image border, the backdrop region is flood-filled from
the edges on a downscaled copy (fast), the edge is refined at full resolution, and
the result is feathered by a pixel. Cached next to the image as ``<id>.sprite.png``.
"""

from __future__ import annotations

from pathlib import Path

from PIL import ImageChops


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


def _flat_pockets(holes, dist, min_px: int = 12, max_mean: float = 9.0, max_std: float = 4.0):
    """Enclosed near-backdrop pockets (on the small image) that are flat enough to be backdrop, as a mask."""
    from PIL import Image, ImageDraw, ImageStat

    out = Image.new("L", holes.size, 0)
    holes = holes.copy()
    for _ in range(400):
        box = holes.getbbox()
        if not box:
            break
        x0, y0, x1, _ = box
        row = holes.crop((x0, y0, x1, y0 + 1))
        seed = (x0 + next(i for i, v in enumerate(row.tobytes()) if v), y0)
        ImageDraw.floodfill(holes, seed, 128)
        comp = holes.point(lambda v: 255 if v == 128 else 0)
        n = comp.histogram()[255]
        if n >= min_px:
            st = ImageStat.Stat(dist, mask=comp)
            if st.mean[0] <= max_mean and st.stddev[0] <= max_std:
                out.paste(255, mask=comp)
        holes.paste(0, mask=comp)
    return out


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
    # backdrop trapped between hair strands or an arm and the body isn't connected to the border: clear the
    # enclosed pockets that are as flat as the backdrop (clothing and skin are shaded, so they stay)
    region_small = ImageChops.lighter(region_small, _flat_pockets(near.point(lambda v: 255 if v == 255 else 0),
                                                                  _distance(small, color)))
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


def frame_sprite(path: Path | str, size: tuple[int, int] = (832, 1216), headroom: float = 0.06,
                 keep: float = 0.58) -> float:
    """Crop a full-body render to a thighs-up visual-novel sprite, in place.

    Portraits are drawn full-body (asked for head-and-shoulders, the model crops the hair at the top edge),
    then cut here so every character has the same air above the head and the same scale on stage. ``keep``
    is how much of the figure's height to keep from the top of the head (≈ to mid-thigh). If the render cut
    the head anyway, the crop is not padded, so the checker can see it. Returns the figure's top (0..1)."""
    from PIL import Image, ImageChops

    path = Path(path)
    with Image.open(path) as src:
        im = src.convert("RGB")
    w, h = im.size
    color = _backdrop_color(im)
    small = im.resize((w // 4, h // 4))
    sw, sh = small.size
    mask = ImageChops.difference(small, Image.new("RGB", small.size, color)).convert("L").point(
        lambda v: 255 if v > 28 else 0)
    rows = [y for y in range(sh) if mask.crop((0, y, sw, y + 1)).histogram()[255] > 0.01 * sw]
    if not rows:
        return 0.0
    top, bottom = rows[0] * 4, (rows[-1] + 1) * 4
    if rows[-1] >= sh - 2:
        # the figure runs off the bottom: a close-up, not a full figure — cropping would only zoom it further.
        # Leave it as drawn; the checker rejects it ("a face close-up") and a new option is drawn.
        return top / h
    head = mask.crop((0, rows[0], sw, rows[0] + max(1, (rows[-1] - rows[0]) // 7)))
    cols = [head.crop((x, 0, x + 1, head.height)).histogram()[255] for x in range(sw)]
    cx = (sum(x * n for x, n in enumerate(cols)) / sum(cols)) * 4 if sum(cols) else w / 2
    fig_h = bottom - top
    ch = keep * fig_h / (1 - headroom)
    cw = ch * size[0] / size[1]
    y0 = top - headroom * ch if top > 4 else 0  # head cut by the render: leave it visible to the checker
    x0 = cx - cw / 2
    canvas = Image.new("RGB", (round(cw), round(ch)), color)
    canvas.paste(im.crop((round(x0), round(y0), round(x0 + cw), round(y0 + ch))), (0, 0))
    # PIL fills out-of-bounds crops with black: repaint those strips in the backdrop colour
    from PIL import ImageDraw

    d = ImageDraw.Draw(canvas)
    if x0 < 0:
        d.rectangle((0, 0, round(-x0), round(ch)), fill=color)
    if x0 + cw > w:
        d.rectangle((round(w - x0), 0, round(cw), round(ch)), fill=color)
    if y0 < 0:
        d.rectangle((0, 0, round(cw), round(-y0)), fill=color)
    if y0 + ch > h:
        d.rectangle((0, round(h - y0), round(cw), round(ch)), fill=color)
    canvas.resize(size, Image.Resampling.LANCZOS).save(path)
    return top / h
