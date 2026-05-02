from __future__ import annotations
from dataclasses import asdict, dataclass
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter
from .config import AUDIT_BACKGROUNDS

@dataclass
class AlphaStats:
    mode: str
    width: int
    height: int
    alpha_min: int
    alpha_max: int
    transparent_pixels: int
    opaque_pixels: int
    semi_transparent_pixels: int
    has_real_alpha: bool
    fully_transparent_hidden_rgb_nonzero: int
    checkerboard_suspect_score: float
    def to_dict(self) -> dict:
        return asdict(self)

def has_alpha(image: Image.Image) -> bool:
    return image.mode in ("RGBA", "LA") or "transparency" in image.info

def to_rgba(image: Image.Image) -> Image.Image:
    return image.convert("RGBA")

def alpha_stats(image: Image.Image) -> AlphaStats:
    rgba = to_rgba(image)
    arr = np.asarray(rgba)
    alpha = arr[:, :, 3]
    transparent = alpha == 0
    opaque = alpha == 255
    semi = (alpha > 0) & (alpha < 255)
    hidden_nonzero = int(np.sum(np.any(arr[:, :, :3] != 0, axis=2) & transparent))
    return AlphaStats(
        mode=rgba.mode, width=rgba.width, height=rgba.height,
        alpha_min=int(alpha.min()), alpha_max=int(alpha.max()),
        transparent_pixels=int(np.sum(transparent)), opaque_pixels=int(np.sum(opaque)),
        semi_transparent_pixels=int(np.sum(semi)),
        has_real_alpha=bool(alpha.min() < 255 and alpha.max() > 0),
        fully_transparent_hidden_rgb_nonzero=hidden_nonzero,
        checkerboard_suspect_score=checkerboard_suspect_score(rgba),
    )

def sanitize_rgba(image: Image.Image) -> Image.Image:
    rgba = to_rgba(image)
    arr = np.array(rgba)
    alpha = arr[:, :, 3]
    arr[alpha == 0, :3] = 0
    return Image.fromarray(arr, "RGBA")

def decontaminate_edges(image: Image.Image, bg_rgb: tuple[int, int, int]) -> Image.Image:
    rgba = to_rgba(image)
    arr = np.array(rgba)
    rgb = arr[:, :, :3].astype(np.float32)
    alpha = arr[:, :, 3].astype(np.float32) / 255.0
    bg = np.array(bg_rgb, dtype=np.float32)
    semi = (alpha > 0.02) & (alpha < 0.98)
    if np.any(semi):
        a = alpha[semi][:, None]
        rgb[semi] = np.clip((rgb[semi] - (1.0 - a) * bg) / np.maximum(a, 1e-6), 0, 255)
        arr[:, :, :3] = rgb.astype(np.uint8)
    return sanitize_rgba(Image.fromarray(arr, "RGBA"))

def estimate_corner_background(image: Image.Image, patch: int = 24) -> tuple[int, int, int]:
    rgb = image.convert("RGB")
    arr = np.asarray(rgb)
    h, w, _ = arr.shape
    p = max(1, min(patch, max(1, h // 3), max(1, w // 3)))
    samples = np.concatenate([arr[:p, :p].reshape(-1, 3), arr[:p, w-p:].reshape(-1, 3), arr[h-p:, :p].reshape(-1, 3), arr[h-p:, w-p:].reshape(-1, 3)], axis=0)
    return tuple(int(x) for x in np.median(samples, axis=0))

def solid_background_matte(image: Image.Image, bg_rgb: tuple[int, int, int] | None = None, low: float = 10.0, high: float = 80.0, feather: float = 1.0) -> Image.Image:
    rgb_image = image.convert("RGB")
    if bg_rgb is None:
        bg_rgb = estimate_corner_background(rgb_image)
    arr = np.asarray(rgb_image).astype(np.float32)
    bg = np.array(bg_rgb, dtype=np.float32)
    dist = np.sqrt(np.sum((arr - bg) ** 2, axis=2))
    alpha = np.clip((dist - low) / max(high - low, 1.0), 0.0, 1.0)
    alpha_img = Image.fromarray((alpha * 255.0).astype(np.uint8), "L")
    if feather > 0:
        alpha_img = alpha_img.filter(ImageFilter.GaussianBlur(radius=feather))
    rgba = rgb_image.convert("RGBA")
    rgba.putalpha(alpha_img)
    return decontaminate_edges(rgba, bg_rgb)

def save_alpha_mask(image: Image.Image, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    to_rgba(image).getchannel("A").save(output_path)

def composite_on(image: Image.Image, rgb: tuple[int, int, int]) -> Image.Image:
    rgba = to_rgba(image)
    bg = Image.new("RGBA", rgba.size, (*rgb, 255))
    return Image.alpha_composite(bg, rgba).convert("RGB")

def save_audits(image: Image.Image, out_dir: Path, stem: str = "final") -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, rgb in AUDIT_BACKGROUNDS.items():
        path = out_dir / f"{stem}.on_{name}.jpg"
        composite_on(image, rgb).save(path, quality=95)
        written.append(str(path))
    return written

def checkerboard_suspect_score(image: Image.Image) -> float:
    rgba = to_rgba(image)
    arr = np.asarray(rgba)
    alpha = arr[:, :, 3]
    visible = alpha > 20
    if np.sum(visible) < 1024:
        return 0.0
    gray = np.mean(arr[:, :, :3].astype(np.float32), axis=2)
    yy, xx = np.indices(gray.shape)
    scores = []
    for tile in (8, 10, 12, 16, 20, 24, 32):
        parity = ((xx // tile) + (yy // tile)) % 2
        a = gray[(parity == 0) & visible]
        b = gray[(parity == 1) & visible]
        if len(a) >= 256 and len(b) >= 256:
            scores.append(min(abs(float(np.mean(a)) - float(np.mean(b))) / 64.0, 1.0))
    return round(max(scores) if scores else 0.0, 4)

def parse_rgb(value: str | None) -> tuple[int, int, int] | None:
    if value is None or value.lower() in {"none", "off", "false"}:
        return None
    if value.lower() == "auto":
        raise ValueError("auto is handled by the caller")
    cleaned = value.strip().lstrip("#")
    if "," in cleaned:
        parts = [int(p.strip()) for p in cleaned.split(",")]
        if len(parts) != 3:
            raise ValueError("RGB value must have 3 components")
        return tuple(max(0, min(255, p)) for p in parts)  # type: ignore[return-value]
    if len(cleaned) == 6:
        return tuple(int(cleaned[i:i+2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    raise ValueError(f"Unsupported RGB value: {value!r}")
