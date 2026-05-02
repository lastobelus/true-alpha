from __future__ import annotations
import webbrowser
from pathlib import Path
from threading import Timer
from flask import Flask, jsonify, render_template, request, send_from_directory, url_for
from werkzeug.utils import secure_filename
from .config import PREVIEW_BACKGROUNDS
from .pipeline import PipelineOptions, find_runs, load_manifest, make_run_dir, process_image, slugify
from .save_dialog import save_png_with_native_dialog

def create_app(project_root: str | Path | None = None) -> Flask:
    project_root = Path(project_root or Path.cwd()).resolve()
    runs_root = project_root / "runs"; inputs_root = project_root / "inputs"
    runs_root.mkdir(parents=True, exist_ok=True); inputs_root.mkdir(parents=True, exist_ok=True)
    app = Flask(__name__, template_folder=str(Path(__file__).parent / "templates"), static_folder=str(Path(__file__).parent / "static"))

    @app.get("/")
    def index():
        runs = [p.name for p in find_runs(runs_root)]
        latest = runs[0] if runs else None
        return render_template("index.html", run_id=latest, backgrounds=PREVIEW_BACKGROUNDS, initial_manifest=None, runs=runs)

    @app.get("/run/<run_id>")
    def run_page(run_id: str):
        run_dir = safe_run_dir(runs_root, run_id)
        return render_template("index.html", run_id=run_id, backgrounds=PREVIEW_BACKGROUNDS, initial_manifest=load_manifest(run_dir), runs=[p.name for p in find_runs(runs_root)])

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
        models = request.form.get("models", "u2netp,u2net,isnet-general-use,birefnet-general,birefnet-general-lite")
        options = PipelineOptions(rembg_models=[m.strip() for m in models.split(",") if m.strip()], include_inspyrenet=request.form.get("include_inspyrenet") == "on", edge_bg=request.form.get("edge_bg", "auto") or "auto")
        run_dir = process_image(input_path, output_dir=make_run_dir(input_path, runs_root), options=options)
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

def serve(project_root: str | Path | None = None, host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True, run_id: str | None = None) -> None:
    app = create_app(project_root)
    url = f"http://{host}:{port}/" + (f"run/{run_id}" if run_id else "")
    if open_browser:
        Timer(0.75, lambda: webbrowser.open(url)).start()
    app.run(host=host, port=port, debug=False)
