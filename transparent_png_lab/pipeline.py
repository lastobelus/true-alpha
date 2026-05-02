from __future__ import annotations
import json, re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Thread
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

def result_id_for_rembg_model(model: str) -> str:
    return f"rembg-{model}".replace("_", "-")

def write_manifest(run_dir: Path, manifest: dict) -> None:
    manifest_path = run_dir / "manifest.json"
    tmp_path = run_dir / "manifest.json.tmp"
    tmp_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    tmp_path.replace(manifest_path)

def append_result_manifest(run_dir: Path, manifest: dict, result: EngineResult, seen_ids: set[str]) -> None:
    variants_dir = run_dir / "variants"
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
    write_manifest(run_dir, manifest)

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
        append_result_manifest(run_dir, manifest, result, seen_ids)
    return run_dir

def create_run_manifest(input_path: str | Path, output_dir: str | Path | None = None, options: PipelineOptions | None = None) -> tuple[Path, dict, Image.Image, tuple[int, int, int] | None, tuple[int, int, int] | None]:
    options = options or PipelineOptions()
    input_path = Path(input_path).expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(input_path)
    run_dir = Path(output_dir).expanduser().resolve() if output_dir else make_run_dir(input_path).resolve()
    (run_dir / "variants").mkdir(parents=True, exist_ok=True)
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
        "options": {"rembg_models": options.rembg_models, "include_inspyrenet": options.include_inspyrenet, "include_solid_bg": options.include_solid_bg, "include_native_alpha": options.include_native_alpha, "alpha_matting": options.alpha_matting, "edge_bg": options.edge_bg, "edge_bg_resolved": list(decontam_bg) if decontam_bg else None, "progressive": True},
        "variants": [],
        "progress": {"status": "running", "completed": 0, "total": 0},
    }
    write_manifest(run_dir, manifest)
    return run_dir, manifest, source, corner_bg, decontam_bg

def pending_entry(variant_id: str, label: str, engine: str, model: str | None = None) -> dict:
    return {"id": variant_id, "label": label, "engine": engine, "model": model, "status": "pending", "notes": ["Waiting for this variant to run."], "error": None, "relative_dir": f"variants/{variant_id}", "accepted_by_numeric_alpha_check": False}

def replace_pending_with_result(run_dir: Path, manifest: dict, result: EngineResult) -> None:
    manifest["variants"] = [v for v in manifest.get("variants", []) if v.get("id") != result.id]
    seen_ids = {v["id"] for v in manifest.get("variants", [])}
    append_result_manifest(run_dir, manifest, result, seen_ids)

def run_remaining_variants(run_dir: Path, options: PipelineOptions, remaining_models: list[str], include_inspyrenet: bool, decontam_bg: tuple[int, int, int] | None) -> None:
    manifest = load_manifest(run_dir)
    total = len([v for v in manifest.get("variants", []) if v.get("status") in {"ok", "failed", "skipped", "pending", "running"}])
    for model in remaining_models:
        variant_id = result_id_for_rembg_model(model)
        for variant in manifest["variants"]:
            if variant.get("id") == variant_id:
                variant["status"] = "running"; variant["notes"] = ["Running this model now."]; break
        write_manifest(run_dir, manifest)
        result = rembg_variant(run_dir / "source.png", model=model, decontam_bg=decontam_bg, alpha_matting=options.alpha_matting)
        replace_pending_with_result(run_dir, manifest, result)
        manifest["progress"] = {"status": "running", "completed": len([v for v in manifest["variants"] if v.get("status") != "pending" and v.get("status") != "running"]), "total": total}
        write_manifest(run_dir, manifest)
    if include_inspyrenet:
        source_rgb = Image.open(run_dir / "source.png").convert("RGB")
        for mode in ["base", "fast"]:
            variant_id = f"inspyrenet-{mode}-static"
            for variant in manifest["variants"]:
                if variant.get("id") == variant_id:
                    variant["status"] = "running"; variant["notes"] = ["Running this model now."]; break
            write_manifest(run_dir, manifest)
            replace_pending_with_result(run_dir, manifest, inspyrenet_variant(source_rgb, mode=mode, resize="static"))
            manifest["progress"] = {"status": "running", "completed": len([v for v in manifest["variants"] if v.get("status") != "pending" and v.get("status") != "running"]), "total": total}
            write_manifest(run_dir, manifest)
    manifest["progress"] = {"status": "complete", "completed": len([v for v in manifest["variants"] if v.get("status") != "pending" and v.get("status") != "running"]), "total": total}
    write_manifest(run_dir, manifest)

def process_image_progressive(input_path: str | Path, output_dir: str | Path | None = None, options: PipelineOptions | None = None, background: bool = True, initial_rembg_count: int = 1) -> Path:
    options = options or PipelineOptions()
    run_dir, manifest, source, corner_bg, decontam_bg = create_run_manifest(input_path, output_dir=output_dir, options=options)
    source_rgb = source.convert("RGB")
    initial_models = options.rembg_models[:initial_rembg_count]
    remaining_models = options.rembg_models[initial_rembg_count:]
    pending = [pending_entry(result_id_for_rembg_model(model), f"rembg {model}", "rembg", model) for model in remaining_models]
    if options.include_inspyrenet:
        pending.extend([pending_entry("inspyrenet-base-static", "InSPyReNet base/static", "transparent-background", "base/static"), pending_entry("inspyrenet-fast-static", "InSPyReNet fast/static", "transparent-background", "fast/static")])
    manifest["progress"] = {"status": "running", "completed": 0, "total": len(pending) + int(options.include_native_alpha) + int(options.include_solid_bg) + len(initial_models)}
    write_manifest(run_dir, manifest)
    seen_ids: set[str] = set()
    if options.include_native_alpha:
        append_result_manifest(run_dir, manifest, native_alpha_variant(source), seen_ids)
    if options.include_solid_bg:
        append_result_manifest(run_dir, manifest, solid_background_variant(source_rgb, corner_bg), seen_ids)
    for model in initial_models:
        append_result_manifest(run_dir, manifest, rembg_variant(run_dir / "source.png", model=model, decontam_bg=decontam_bg, alpha_matting=options.alpha_matting), seen_ids)
    manifest["variants"].extend(pending)
    manifest["progress"] = {"status": "running" if pending else "complete", "completed": len([v for v in manifest["variants"] if v.get("status") != "pending" and v.get("status") != "running"]), "total": manifest["progress"]["total"]}
    write_manifest(run_dir, manifest)
    if pending and background:
        Thread(target=run_remaining_variants, args=(run_dir, options, remaining_models, options.include_inspyrenet, decontam_bg), daemon=True).start()
    elif pending:
        run_remaining_variants(run_dir, options, remaining_models, options.include_inspyrenet, decontam_bg)
    return run_dir

def load_manifest(run_dir: str | Path) -> dict:
    return json.loads((Path(run_dir) / "manifest.json").read_text(encoding="utf-8"))

def find_runs(runs_root: str | Path = RUNS_DIR) -> list[Path]:
    root = Path(runs_root)
    return sorted([p for p in root.iterdir() if (p / "manifest.json").exists()], reverse=True) if root.exists() else []
