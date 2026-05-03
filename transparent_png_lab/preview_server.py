from __future__ import annotations
import webbrowser
from pathlib import Path
from threading import Timer
from flask import Flask, jsonify, render_template, request, send_from_directory, url_for
from PIL import Image
from werkzeug.utils import secure_filename
from .alpha import alpha_stats, estimate_corner_background, parse_rgb, sanitize_rgba
from .config import PREVIEW_BACKGROUNDS, SHOW_DOWNLOAD_FALLBACK
from .engines import inspyrenet_variant, multi_shade_background_variant, native_alpha_variant, rembg_variant, solid_background_variant
from .pipeline import PipelineOptions, find_runs, load_manifest, make_run_dir, process_image_progressive, slugify
from .save_dialog import save_png_with_native_dialog

SUPPORTED_BATCH_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

def create_app(project_root: str | Path | None = None) -> Flask:
    project_root = Path(project_root or Path.cwd()).resolve()
    runs_root = project_root / "runs"; inputs_root = project_root / "inputs"
    runs_root.mkdir(parents=True, exist_ok=True); inputs_root.mkdir(parents=True, exist_ok=True)
    app = Flask(__name__, template_folder=str(Path(__file__).parent / "templates"), static_folder=str(Path(__file__).parent / "static"))

    @app.get("/")
    def index():
        runs = [p.name for p in find_runs(runs_root)]
        latest = runs[0] if runs else None
        return render_template("index.html", run_id=latest, backgrounds=PREVIEW_BACKGROUNDS, initial_manifest=None, runs=runs, show_download_fallback=SHOW_DOWNLOAD_FALLBACK)

    @app.get("/run/<run_id>")
    def run_page(run_id: str):
        run_dir = safe_run_dir(runs_root, run_id)
        return render_template("index.html", run_id=run_id, backgrounds=PREVIEW_BACKGROUNDS, initial_manifest=load_manifest(run_dir), runs=[p.name for p in find_runs(runs_root)], show_download_fallback=SHOW_DOWNLOAD_FALLBACK)

    @app.get("/api/run/<run_id>")
    def api_run(run_id: str):
        return jsonify(load_manifest(safe_run_dir(runs_root, run_id)))

    @app.post("/api/upload")
    def api_upload():
        file = request.files.get("image")
        if not file or not file.filename:
            return jsonify({"error": "No image file uploaded."}), 400
        filename = secure_filename(file.filename) or "input.png"
        input_path = inputs_root / filename; file.save(input_path)
        models = request.form.get("models", "u2netp,u2net,isnet-general-use,birefnet-general")
        options = PipelineOptions(rembg_models=[m.strip() for m in models.split(",") if m.strip()], include_inspyrenet=request.form.get("include_inspyrenet") == "on", edge_bg=request.form.get("edge_bg", "auto") or "auto")
        run_dir = process_image_progressive(input_path, output_dir=make_run_dir(input_path, runs_root), options=options)
        return jsonify({"run_id": run_dir.name, "url": url_for("run_page", run_id=run_dir.name)})

    @app.get("/runs/<run_id>/<path:filename>")
    def run_file(run_id: str, filename: str):
        return send_from_directory(safe_run_dir(runs_root, run_id), filename)

    @app.get("/api/run/<run_id>/variant/<variant_id>/file")
    def variant_file(run_id: str, variant_id: str):
        variant_path = find_variant_output(runs_root, run_id, variant_id)
        return send_from_directory(variant_path.parent, variant_path.name, as_attachment=True, download_name=f"{variant_id}.png")

    @app.post("/api/run/<run_id>/variant/<variant_id>/save")
    def variant_save(run_id: str, variant_id: str):
        try:
            return jsonify(save_png_with_native_dialog(find_variant_output(runs_root, run_id, variant_id), f"{variant_id}.png"))
        except Exception as exc:
            return jsonify({"status": "fallback", "error": str(exc)}), 503

    @app.post("/api/run/<run_id>/variant/<variant_id>/folder")
    def variant_folder(run_id: str, variant_id: str):
        try:
            manifest = load_manifest(safe_run_dir(runs_root, run_id))
            variant = find_manifest_variant(manifest, variant_id)
            payload = request.get_json(silent=True) or {}
            source_dir = default_source_dir(manifest)
            if payload.get("source_dir"):
                source_dir = Path(payload["source_dir"]).expanduser().resolve()
            output_dir = Path(payload.get("output_dir") or (source_dir / "true-alpha-output")).expanduser().resolve()
            edge_bg = payload.get("edge_bg", "auto")
            skip_existing = bool(payload.get("skip_existing", True))
            result = process_folder_variant(source_dir, output_dir, variant, manifest, edge_bg, skip_existing)
            return jsonify(result)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400
    return app

def safe_run_dir(runs_root: Path, run_id: str) -> Path:
    safe_id = slugify(run_id); run_dir = (runs_root / safe_id).resolve(); base = runs_root.resolve()
    if base not in run_dir.parents and run_dir != base:
        raise ValueError("Invalid run id")
    if not (run_dir / "manifest.json").exists():
        raise FileNotFoundError(f"No manifest found for run {safe_id}")
    return run_dir

def find_variant_output(runs_root: Path, run_id: str, variant_id: str) -> Path:
    run_dir = safe_run_dir(runs_root, run_id)
    for variant in load_manifest(run_dir).get("variants", []):
        if variant.get("id") == variant_id and variant.get("status") == "ok" and variant.get("output"):
            path = (run_dir / variant["output"]).resolve()
            if run_dir.resolve() not in path.parents: raise ValueError("Invalid variant path")
            if not path.exists(): raise FileNotFoundError(path)
            return path
    raise FileNotFoundError("Variant not found or not ready.")

def find_manifest_variant(manifest: dict, variant_id: str) -> dict:
    for variant in manifest.get("variants", []):
        if variant.get("id") == variant_id and variant.get("status") == "ok":
            return variant
    raise FileNotFoundError("Variant not found or not ready.")

def default_source_dir(manifest: dict) -> Path:
    original_path = manifest.get("source", {}).get("original_path")
    if original_path:
        return Path(original_path).expanduser().resolve().parent
    source_path = manifest.get("source", {}).get("path")
    if source_path:
        return Path(source_path).expanduser().resolve().parent
    raise FileNotFoundError("No source folder is recorded for this run.")

def batch_image_paths(source_dir: Path) -> list[Path]:
    if not source_dir.exists() or not source_dir.is_dir():
        raise FileNotFoundError(f"Source folder does not exist: {source_dir}")
    return sorted(p for p in source_dir.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_BATCH_EXTENSIONS)

def resolve_batch_edge_bg(edge_bg: str | None, source: Image.Image) -> tuple[int, int, int] | None:
    value = (edge_bg or "auto").strip()
    if value.lower() == "auto":
        return estimate_corner_background(source)
    return parse_rgb(value)

def process_folder_variant(source_dir: Path, output_dir: Path, variant: dict, manifest: dict, edge_bg: str | None, skip_existing: bool) -> dict:
    paths = batch_image_paths(source_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    options = manifest.get("options", {})
    processed: list[dict] = []
    skipped: list[dict] = []
    failed: list[dict] = []
    for input_path in paths:
        output_path = output_dir / f"{input_path.stem}.png"
        if skip_existing and output_path.exists():
            skipped.append({"input": str(input_path), "output": str(output_path), "reason": "exists"})
            continue
        try:
            result = run_batch_variant(input_path, variant, bool(options.get("alpha_matting", True)), edge_bg)
            if result.status != "ok" or result.output_image is None:
                raise RuntimeError(result.error or f"{result.label} returned {result.status}")
            image = sanitize_rgba(result.output_image)
            image.save(output_path)
            stats = alpha_stats(image).to_dict()
            processed.append({"input": str(input_path), "output": str(output_path), "stats": stats})
        except Exception as exc:
            failed.append({"input": str(input_path), "error": str(exc)})
    return {
        "status": "complete",
        "method": variant.get("id"),
        "source_dir": str(source_dir),
        "output_dir": str(output_dir),
        "processed": processed,
        "skipped": skipped,
        "failed": failed,
        "counts": {"processed": len(processed), "skipped": len(skipped), "failed": len(failed), "total": len(paths)},
    }

def run_batch_variant(input_path: Path, variant: dict, alpha_matting: bool, edge_bg: str | None):
    source = Image.open(input_path)
    variant_id = variant.get("id", "")
    engine = variant.get("engine", "")
    if variant_id == "source-alpha-sanitize":
        return native_alpha_variant(source)
    if variant_id == "solid-bg-corner-matte":
        bg = resolve_batch_edge_bg(edge_bg, source)
        return solid_background_variant(source.convert("RGB"), bg)
    if variant_id == "multi-shade-bg-matte":
        return multi_shade_background_variant(source.convert("RGB"))
    if engine == "rembg" or variant_id.startswith("rembg-"):
        bg = resolve_batch_edge_bg(edge_bg, source)
        model = variant.get("model") or variant_id.removeprefix("rembg-")
        return rembg_variant(input_path, model=model, decontam_bg=bg, alpha_matting=alpha_matting)
    if engine == "transparent-background" or variant_id.startswith("inspyrenet-"):
        model = variant.get("model") or "base/static"
        mode, _, resize = model.partition("/")
        return inspyrenet_variant(source.convert("RGB"), mode=mode or "base", resize=resize or "static")
    raise ValueError(f"Batch processing is not supported for {variant_id}.")

def serve(project_root: str | Path | None = None, host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True, run_id: str | None = None) -> None:
    app = create_app(project_root)
    url = f"http://{host}:{port}/" + (f"run/{run_id}" if run_id else "")
    if open_browser:
        Timer(0.75, lambda: webbrowser.open(url)).start()
    app.run(host=host, port=port, debug=False)
