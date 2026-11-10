"""Step 3 — the automatic quality approver.

A vision model looks at each generated image and answers a fixed set of
multiple-choice questions (schema-enforced, like the text cascade): how many
people, gender, does each profile attribute match, any hat / object over the
mouth / scenery / text, is the face well drawn, and — for expressions — does the
face clearly show the target expression. Whether an expression edit is still the
same character is a deterministic pixel check against the approved base (small
vision models judge "same person?" across two images poorly; pixels don't).

Scoring is deterministic code, not the model's opinion, so it is testable and the
thresholds are visible. Failing images are redrawn automatically (within a budget)
before you ever see them; options are ranked best-first.
"""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path

from babel.art.profile import EMOTIONS, portrait_values, wears_hat
from babel.scenario.ask import extract_json

# Measured on 55 hand-judged images (bad options, good options, expression edits):
#   qwen3-vl:4b-instruct  53/55 agree, 17/17 bad caught, 19/19 expressions, 2.4 s/check, 3.3 GB
#   qwen3-vl:8b-instruct  50/55 agree (more false rejections), 4.0 s/check, 6.2 GB
# Instruct builds only: the default qwen3-vl tags reason at length before answering.
VISION_PREFERRED = ("qwen3-vl:4b-instruct", "qwen3-vl:8b-instruct", "qwen2.5vl:7b", "gemma3:12b")
PASS_SCORE = 0.6

ATTRS = (("hair", "Hair"), ("eyes", "Eyes"), ("outfit", "Clothes"), ("age", "Apparent age"))

SYSTEM = """You are a strict art director checking illustrations of a novel character.
Answer every question about what you actually see, choosing only from the allowed answers.
Reply with JSON only."""


def _img_b64(path: Path | str, max_side: int = 768) -> str:
    from PIL import Image

    with Image.open(path) as im:
        im = im.convert("RGB")
        im.thumbnail((max_side, max_side))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=88)
    return base64.b64encode(buf.getvalue()).decode()


def questions(profile: dict | None, gender: str | None, kind: str, emotion: str | None) -> tuple[list[str], dict]:
    """The numbered questions about ONE image, and the JSON schema that forces an allowed answer for each."""
    yn = {"type": "string", "enum": ["yes", "no"]}
    ynu = {"type": "string", "enum": ["yes", "no", "unclear"]}
    values = portrait_values(profile or {})
    q = ["people: how many people are shown? (one / none / several)",
         "gender: the person looks (male / female / unclear)"]
    props: dict = {"people": {"type": "string", "enum": ["one", "none", "several"]},
                   "gender": {"type": "string", "enum": ["male", "female", "unclear"]}}
    for key, label in ATTRS:
        if values.get(key):
            q.append(f"attr_{key}: does this match the picture — {label}: “{values[key]}”? (yes / no / unclear)")
            props[f"attr_{key}"] = ynu
    q += ["headwear: is there a hat on the person's head (top hat, felt hat, bowler, cap, hood)? (yes / no)",
          "over_mouth: is anything in front of or in the mouth (pipe, cigarette, lamp, hand, object)? (yes / no)",
          "scenery: is there scenery, buildings or objects in the background instead of a plain backdrop? (yes / no)",
          "text: are there any letters, words, signatures or watermarks? (yes / no)",
          "face_ok: is the face well drawn (not distorted, melted or asymmetric)? (yes / no)",
          "hands_ok: are visible hands well drawn? (yes / no / unclear — unclear if no hands are visible)"]
    props |= {"headwear": yn, "over_mouth": yn, "scenery": yn, "text": yn, "face_ok": yn, "hands_ok": ynu}
    if kind == "expression" and emotion and emotion != "neutral":
        q.append(f"expression: does the face clearly show {EMOTIONS[emotion]}? (yes / no)")
        props["expression"] = yn
    return q, {"type": "object", "properties": props, "required": list(props)}


def background_questions(label: str, era: str | None = None) -> tuple[list[str], dict]:
    yn = {"type": "string", "enum": ["yes", "no"]}
    q = ["people: how many people or characters are shown? (none / one / several)",
         f"place: does this show {label}? (yes / no / unclear)",
         "full_scene: does the picture fill the whole frame as a place you could stand in (not an isolated object "
         "on a blank or white background)? (yes / no)",
         "modern: are there modern things in it — fluorescent lights, ceiling tiles, office chairs, projectors, "
         "screens, cars, plastic, modern ships? (yes / no)",
         "text: are there any letters, words, signs, signatures or watermarks? (yes / no)",
         "coherent: is it a coherent, well-drawn scene (no warped or impossible architecture)? (yes / no)"]
    props = {"people": {"type": "string", "enum": ["none", "one", "several"]},
             "place": {"type": "string", "enum": ["yes", "no", "unclear"]}, "full_scene": yn, "modern": yn,
             "text": yn, "coherent": yn}
    return q, {"type": "object", "properties": props, "required": list(props)}


_MODERN_ERAS = ("modern", "contemporary", "present", "20", "21", "future", "sci", "cyber")


def score_background(answers: dict, label: str, era: str | None = None) -> dict:
    issues, hard, s = [], False, 1.0
    if answers.get("full_scene") == "no":
        issues.append("not a full scene (an object on a blank background)")
        s, hard = s - 0.6, True
    if answers.get("modern") == "yes" and not any(m in (era or "").lower() for m in _MODERN_ERAS):
        issues.append(f"modern things in a {era or 'period'} setting")
        s, hard = s - 0.6, True
    if answers.get("people") != "none":
        issues.append("people in the background")
        s, hard = s - 0.6, True
    if answers.get("place") == "no":
        issues.append(f"doesn't look like {label}")
        s, hard = s - 0.6, True
    if answers.get("text") == "yes":
        issues.append("text or signs")
        s -= 0.3
    if answers.get("coherent") == "no":
        issues.append("warped scene")
        s, hard = s - 0.5, True
    s = max(0.0, round(s, 3))
    return {"score": s, "pass": s >= PASS_SCORE and not hard, "issues": issues, "answers": answers}


def messages(image: Path | str, profile: dict | None, gender: str | None, kind: str,
             emotion: str | None = None, background: str | None = None, era: str | None = None) -> tuple[list[dict], dict]:
    if background:
        qs, schema = background_questions(background, era)
    else:
        qs, schema = questions(profile, gender, kind, emotion)
    lines = ["Questions about the image:"] + [f"{i}. {x}" for i, x in enumerate(qs, 1)]
    lines.append('Reply as JSON with one key per question name, e.g. {"people": "one", ...}.')
    return [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": "\n".join(lines), "images": [_img_b64(image)]}], schema


# Headroom: a sprite needs air above the head. Measured as the first row (from the top) where the figure starts —
# more than 2% of the row differs from the plain backdrop — as a fraction of the height.
MIN_HEADROOM = 0.02


MAX_HEAD_WIDTH = 0.45  # framed sprites measured 0.11-0.39; face close-ups 0.5-0.97


def _figure_mask(image: Path | str):
    from PIL import Image, ImageChops

    from babel.art.sprite import _backdrop_color

    with Image.open(image) as src:
        im = src.convert("RGB")
    im.thumbnail((208, 304))
    return ImageChops.difference(im, Image.new("RGB", im.size, _backdrop_color(im))).convert("L").point(
        lambda v: 255 if v > 28 else 0)


def head_width(image: Path | str) -> float:
    """How much of the width the figure fills just below the top of the head (0..1)."""
    mask = _figure_mask(image)
    w, h = mask.size
    top = headroom(image)
    # the crown of the hair can be narrow even in a close-up, so also measure at face level
    return max(mask.crop((0, y, w, y + 1)).histogram()[255] / w
               for y in (min(h - 1, int(h * (top + 0.08))), min(h - 1, int(h * (top + 0.15)))))


def headroom(image: Path | str) -> float:
    diff = _figure_mask(image)
    w, h = diff.size
    for y in range(h):
        if diff.crop((0, y, w, y + 1)).histogram()[255] > 0.02 * w:
            return y / h
    return 1.0


def score(answers: dict, *, profile: dict | None, gender: str | None, kind: str, emotion: str | None,
          outfit_drift: float | None = None, drift: float | None = None, top_space: float | None = None,
          head: float | None = None) -> dict:
    """Turn the model's answers into a score in [0, 1], a verdict and human-readable issues."""
    issues: list[str] = []
    hard = False
    s = 1.0

    def bad(msg: str, penalty: float, is_hard: bool = False) -> None:
        nonlocal s, hard
        issues.append(msg)
        s -= penalty
        hard = hard or is_hard

    if answers.get("people") != "one":
        bad("more than one person" if answers.get("people") == "several" else "no person", 1.0, True)
    want = {"m": "male", "f": "female"}.get(gender or "")
    if want and answers.get("gender") not in (want, "unclear"):
        bad(f"looks {answers.get('gender')}, should be {want}", 0.6, True)
    values = portrait_values(profile or {})
    for key, label in ATTRS:
        if answers.get(f"attr_{key}") == "no":
            # an expression edit that changed the eye colour is a different character (seen: brown → blue)
            drifted = kind == "expression" and key == "eyes"
            bad(f"{label.lower()} doesn't match “{values.get(key, '')}”", 0.35 if key in ("hair", "eyes") else 0.15,
                drifted)
    if top_space is not None and top_space < MIN_HEADROOM:
        bad("the head is cut off by the top of the picture", 0.6, True)
    elif head is not None and kind == "candidate" and head > MAX_HEAD_WIDTH:
        bad("a face close-up, not a full figure", 0.6, True)
    # disqualifying for a talking-character sprite: hats hide the hair, objects hide the mouth
    if answers.get("headwear") == "yes" and not wears_hat(profile or {}):
        bad("wearing a hat", 0.4, True)
    if answers.get("over_mouth") == "yes":
        bad("something in front of the mouth", 0.4, True)
    if answers.get("scenery") == "yes":
        bad("scenery in the background", 0.25)
    if answers.get("text") == "yes":
        bad("text or watermark", 0.3)
    if answers.get("face_ok") == "no":
        bad("face looks distorted", 0.5, True)
    if answers.get("hands_ok") == "no":
        bad("hands look wrong", 0.15)
    if kind == "expression" and emotion and emotion != "neutral" and answers.get("expression") == "no":
        bad(f"doesn't clearly look {emotion}", 0.45)
    if drift is not None and drift > SAME_LIMIT:
        bad("not the same picture any more (face, outfit or pose changed)", 0.7, True)
    elif outfit_drift is not None and outfit_drift > DRIFT_LIMIT:
        bad("outfit or pose changed", 0.4)
    s = max(0.0, round(s, 3))
    return {"score": s, "pass": s >= PASS_SCORE and not hard, "issues": issues, "answers": answers,
            "drift": None if drift is None else round(drift, 3),
            "outfit_drift": None if outfit_drift is None else round(outfit_drift, 3)}


# Pixel checks between an approved base and its expression edits (96×140 grayscale, mean abs difference).
# Calibrated on 19 good edits vs other portraits of the same profile:
DRIFT_LIMIT = 0.07  # lower body: good edits 0.006-0.028, different images 0.125-0.248
SAME_LIMIT = 0.075  # whole image: good edits ≤0.045, different images ≥0.109


def _drift(base: Path | str, image: Path | str, top: float = 0.0) -> float:
    from PIL import Image, ImageChops, ImageStat

    def region(p) -> Image.Image:
        with Image.open(p) as im:
            im = im.convert("L").resize((96, 140))
            return im.crop((0, int(140 * top), 96, 140))

    return ImageStat.Stat(ImageChops.difference(region(base), region(image))).mean[0] / 255


def outfit_drift(base: Path | str, image: Path | str) -> float:
    """How much the lower body (outfit, pose) changed between the base and an expression edit (0..1)."""
    return _drift(base, image, top=0.5)


def picture_drift(base: Path | str, image: Path | str) -> float:
    """How much the whole picture changed — an edit should only move the face."""
    return _drift(base, image)


class Approver:
    """Checks images with a vision model served by Ollama (any client with ``chat(messages, schema=…)``)."""

    def __init__(self, vlm):
        self.vlm = vlm

    @property
    def model(self) -> str:
        return getattr(self.vlm, "model", "?")

    def check(self, image: Path | str, *, profile: dict | None, gender: str | None, kind: str,
              emotion: str | None = None, reference: Path | str | None = None,
              background: str | None = None, era: str | None = None) -> dict:
        """``background`` = the place it should show, for background images (else a character check)."""
        msgs, schema = messages(image, profile, gender, kind, emotion, background, era)
        reply = self.vlm.chat(msgs, schema=schema, max_tokens=400)
        answers = extract_json(reply.content)
        if background:
            out = score_background(answers, background, era)
            out["model"] = self.model
            return out
        pixel = reference is not None and kind == "expression"
        out = score(answers, profile=profile, gender=gender, kind=kind, emotion=emotion,
                    outfit_drift=outfit_drift(reference, image) if pixel else None,
                    drift=picture_drift(reference, image) if pixel else None, top_space=headroom(image),
                    head=head_width(image))
        out["model"] = self.model
        return out


def summary(qc: dict | None) -> str:
    if not qc:
        return ""
    return "looks right" if qc.get("pass") and not qc.get("issues") else "; ".join(qc.get("issues") or [])


def dumps(qc: dict) -> str:
    return json.dumps(qc, ensure_ascii=False)
