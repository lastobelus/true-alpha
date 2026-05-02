from __future__ import annotations
import json, re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image
from .alpha import alpha_stats, estimate_corner_background, parse_rgb, save_alpha_mask, save_audits
from .config import DEFAULT_REMBG_MODELS, RUNS_DIR
from .engines import EngineResult, inspyrenet_variant, native_alpha_variant, rembg_variant, solid_background_variant

@dataclass
class PipelineOptions:
    rembg_models: list[str] = field(default_factory=lambda: list(DEFAULT_REMBG_MODELS))
    include_inspyrenet: bool = False
    include_solid_bg: bool = True
    include_native_alpha: bool = True
    alpha_matting: bool = True
    edge_bg: str = "auto"

def slugify(value: str, fallback: str = "image") -> str:
    value = re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-_.").lower()
    return value or fallback

def make_run_dir(input_path: Path, runs_root: Path = RUNS_DIR) -> Path:
    return runs_root / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{slugify(input_path.stem)}"

def process_image(input_path: str | Path, output_dir: str | Path | None = None, options: PipelineOptions | None = None) -> Path:
    options = options or PipelineOptions()
    input_path = Path(input_path).expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(input_path)
    run_dir = Path(output_dir).expanduser().resolve() if output_dir else make_run_dir(input_path).resolve()
    variants_dir = run_dir / "variants"
    variants_dir.mkdir(parents=True, exist_ok=True)
    source = Image.open(input_path)
    source_rgb = source.convert("RGB")
    source_png = run_dir / "source.png"
    source_rgb.save(source_png)
    try:
        corner_bg = estimate_corner_background(source_rgb)
    except Exception:
        corner_bg = None
    decontam_bg = None
    if options.edge_bg and options.edge_bg.lower() != "none":
        decontam_bg = corner_bg if options.edge_bg.lower() == "auto" else parse_rgb(options.edge_bg)
    manifest = {
        "schema": "transparent-png-lab/v1", "created_at": datetime.now(timezone.utc).isoformat(), "run_dir": str(run_dir),
        "source": {"original_path": str(input_path), "path": "source.png", "width": source.width, "height": source.height, "mode": source.mode, "corner_background_rgb": list(corner_bg) if corner_bg else None},
        "options": {"rembg_models": options.rembg_models, "include_inspyrenet": options.include_inspyrenet, "include_solid_bg": options.include_solid_bg, "include_native_alpha": options.include_native_alpha, "alpha_matting": options.alpha_matting, "edge_bg": options.edge_bg, "edge_bg_resolved": list(decontam_bg) if decontam_bg else None},
        "variants": [],
    }
    results: list[EngineResult] = []
    if options.include_native_alpha:
        results.append(native_alpha_variant(source))
    if options.include_solid_bg:
        results.append(solid_background_variant(source_rgb, corner_bg))
    for model in options.rembg_models:
        if model.strip():
            results.append(rembg_variant(source_png, model=model.strip(), decontam_bg=decontam_bg, alpha_matting=options.alpha_matting))
    if options.include_inspyrenet:
        results.append(inspyrenet_variant(source_rgb, mode="base", resize="static"))
        results.append(inspyrenet_variant(source_rgb, mode="fast", resize="static"))
    seen_ids: set[str] = set()
    for result in results:
        base_id = result.id; suffix = 2
        while result.id in seen_ids:
            result.id = f"{base_id}-{suffix}"; suffix += 1
        seen_ids.add(result.id)
        entry = result.to_manifest_dict(); entry["relative_dir"] = f"variants/{result.id}"
        if result.status == "ok" and result.output_image is not None:
            variant_dir = variants_dir / result.id; variant_dir.mkdir(parents=True, exist_ok=True)
            final_path = variant_dir / "final.png"; alpha_path = variant_dir / "alpha.png"
            result.output_image.save(final_path)
            save_alpha_mask(result.output_image, alpha_path)
            audit_paths = save_audits(result.output_image, variant_dir)
            stats = alpha_stats(result.output_image).to_dict()
            entry.update({"output": f"variants/{result.id}/final.png", "alpha": f"variants/{result.id}/alpha.png", "audits": [str(Path(p).relative_to(run_dir)) for p in audit_paths], "stats": stats, "accepted_by_numeric_alpha_check": bool(stats["has_real_alpha"] and stats["fully_transparent_hidden_rgb_nonzero"] == 0)})
        else:
            entry["accepted_by_numeric_alpha_check"] = False
        manifest["variants"].append(entry)
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return run_dir

def load_manifest(run_dir: str | Path) -> dict:
    return json.loads((Path(run_dir) / "manifest.json").read_text(encoding="utf-8"))

def find_runs(runs_root: str | Path = RUNS_DIR) -> list[Path]:
    root = Path(runs_root)
    return sorted([p for p in root.iterdir() if (p / "manifest.json").exists()], reverse=True) if root.exists() else []
