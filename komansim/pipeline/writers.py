from __future__ import annotations
from pathlib import Path
import json
import numpy as np
import imageio.v2 as imageio


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def write_sample(out_dir: Path, idx: int, rgb, depth, seg, meta: dict | None) -> None:
    ensure_dir(out_dir / "rgb")
    ensure_dir(out_dir / "depth")
    ensure_dir(out_dir / "seg")
    ensure_dir(out_dir / "meta")

    if rgb is not None:
        imageio.imwrite(out_dir / "rgb" / f"{idx:06d}.png", rgb)

    if depth is not None:
        np.save(out_dir / "depth" / f"{idx:06d}.npy", depth)

    if seg is not None:
        np.save(out_dir / "seg" / f"{idx:06d}.npy", seg)

    with open(out_dir / "meta" / f"{idx:06d}.json", "w", encoding="utf-8") as f:
        json.dump(meta or {}, f, ensure_ascii=False, indent=2)
