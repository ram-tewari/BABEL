"""Image worker — runs in the separate art environment (``.venv-art``, with mflux/MLX).

Deliberately imports nothing from BABEL: the server starts it as a child process
and talks JSON lines over stdin/stdout. Stopping the process frees all of the
image models' memory at once, which is how BABEL time-shares a single machine
between the text model and the image models.

Requests:  {"id": 1, "op": "generate", "model": "anima-turbo", "prompt": "...", "negative": "...",
            "seed": 11, "width": 832, "height": 1216, "out": "/path.png"}
           {"id": 2, "op": "edit", "model": "flux2-klein-4b", "prompt": "...", "image": "/base.png",
            "seed": 7, "width": 832, "height": 1216, "out": "/path.png"}
           {"id": 3, "op": "ping"}
Replies:   {"id": 1, "ok": true, "secs": 8.1}  |  {"id": 1, "ok": false, "error": "..."}
"""

from __future__ import annotations

import json
import sys
import time
import traceback

_models: dict[str, object] = {}


def _load(name: str):
    if name in _models:
        return _models[name]
    from mflux.models.common.config import ModelConfig

    if name in ("anima-turbo", "anima-aesthetic"):
        from mflux.models.anima import Anima

        cfg = ModelConfig.anima_turbo() if name == "anima-turbo" else ModelConfig.anima_aesthetic()
        model = Anima(model_config=cfg, quantize=8)
    elif name == "flux2-klein-4b":
        from mflux.models.flux2.variants import Flux2KleinEdit

        model = Flux2KleinEdit(model_config=ModelConfig.flux2_klein_4b(), quantize=8)
    else:
        raise ValueError(f"unknown image model {name!r}")
    _models[name] = model
    return model


def handle(req: dict) -> dict:
    op = req.get("op")
    if op == "ping":
        return {"ok": True, "loaded": sorted(_models)}
    t = time.time()
    model = _load(req["model"])
    if op == "generate":
        img = model.generate_image(seed=int(req["seed"]), prompt=req["prompt"],
                                   negative_prompt=req.get("negative") or None,
                                   width=int(req["width"]), height=int(req["height"]))
    elif op == "edit":
        img = model.generate_image(seed=int(req["seed"]), prompt=req["prompt"], image_paths=[req["image"]],
                                   width=int(req["width"]), height=int(req["height"]), num_inference_steps=4)
    else:
        raise ValueError(f"unknown op {op!r}")
    img.save(path=req["out"])
    return {"ok": True, "secs": round(time.time() - t, 1)}


def main() -> None:
    out = sys.stdout
    sys.stdout = sys.stderr  # libraries print progress; keep the protocol channel clean
    for line in sys.stdin:
        if not line.strip():
            continue
        req: dict = {}
        try:
            req = json.loads(line)
            rep = handle(req)
        except Exception as e:  # report and keep serving
            rep = {"ok": False, "error": f"{type(e).__name__}: {e}", "trace": traceback.format_exc()[-1500:]}
        rep["id"] = req.get("id")
        out.write(json.dumps(rep) + "\n")
        out.flush()


if __name__ == "__main__":
    main()
