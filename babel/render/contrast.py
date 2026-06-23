"""WCAG contrast utilities for validating character/text colors.

Parses hex and HSL colors, computes relative luminance and contrast ratios,
and checks WCAG AA compliance (>= 4.5:1) on the dark reader background.

Reconstructed from tests/test_contrast.py.
"""

import re
from typing import Tuple

# Default dark reader background.
DEFAULT_BACKGROUND = "#1a1a1a"
WCAG_AA_THRESHOLD = 4.5

RGB = Tuple[int, int, int]


def parse_hex_color(value: str) -> RGB:
    """Parse a hex color (#rgb, #rrggbb, with or without #) to an (r,g,b) tuple."""
    s = value.strip().lstrip("#")

    if len(s) == 3:
        s = "".join(ch * 2 for ch in s)

    if len(s) != 6 or not re.fullmatch(r"[0-9a-fA-F]{6}", s):
        raise ValueError(f"Invalid hex color: {value!r}")

    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def parse_hsl_color(value: str) -> RGB:
    """Parse an 'hsl(h, s%, l%)' string to an (r,g,b) tuple."""
    match = re.fullmatch(
        r"\s*hsl\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)%\s*,\s*(\d+(?:\.\d+)?)%\s*\)\s*",
        value.strip(),
        re.IGNORECASE,
    )
    if not match:
        raise ValueError(f"Invalid HSL color: {value!r}")

    h = float(match.group(1)) % 360 / 360.0
    s = float(match.group(2)) / 100.0
    l = float(match.group(3)) / 100.0

    if s == 0:
        v = round(l * 255)
        return v, v, v

    def hue_to_rgb(p: float, q: float, t: float) -> float:
        if t < 0:
            t += 1
        if t > 1:
            t -= 1
        if t < 1 / 6:
            return p + (q - p) * 6 * t
        if t < 1 / 2:
            return q
        if t < 2 / 3:
            return p + (q - p) * (2 / 3 - t) * 6
        return p

    q = l * (1 + s) if l < 0.5 else l + s - l * s
    p = 2 * l - q
    r = hue_to_rgb(p, q, h + 1 / 3)
    g = hue_to_rgb(p, q, h)
    b = hue_to_rgb(p, q, h - 1 / 3)
    return round(r * 255), round(g * 255), round(b * 255)


def _parse_color(value: str) -> RGB:
    """Parse either an hsl(...) or hex color string."""
    if value.strip().lower().startswith("hsl"):
        return parse_hsl_color(value)
    return parse_hex_color(value)


def get_relative_luminance(rgb: RGB) -> float:
    """WCAG relative luminance of an (r,g,b) tuple in [0, 1]."""
    def channel(c: int) -> float:
        cs = c / 255.0
        return cs / 12.92 if cs <= 0.03928 else ((cs + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def calculate_contrast_ratio(color1: str, color2: str) -> float:
    """WCAG contrast ratio between two colors (hex or hsl); order-independent."""
    l1 = get_relative_luminance(_parse_color(color1))
    l2 = get_relative_luminance(_parse_color(color2))
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def meets_wcag_aa(foreground: str, background: str) -> bool:
    """True if foreground/background meet WCAG AA (>= 4.5:1)."""
    return calculate_contrast_ratio(foreground, background) >= WCAG_AA_THRESHOLD


def validate_character_color(color: str, background: str = DEFAULT_BACKGROUND) -> bool:
    """True if a character color is readable on the (dark) background."""
    return meets_wcag_aa(color, background)
