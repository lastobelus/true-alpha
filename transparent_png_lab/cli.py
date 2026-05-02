from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from PIL import Image
from .alpha import alpha_stats
from .config import DEFAULT_REMBG_MODELS
from .engines import tool_status
from .pipeline import PipelineOptions, load_manifest, process_image

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tpng", description="Transparent PNG Lab: background-removal variants, alpha QA, and HTML preview.")
    sub = parser.add_subparsers(dest="command", required=True)
    process = sub.add_parser("process", help="Process an input image into transparent PNG variants.")
    process.add_argument("input", type=Path); process.add_argument("--out", type=Path, default=None)
    process.add_argument("--models", default=",".join(DEFAULT_REMBG_MODELS), help="Comma-separated rembg models. Use empty string to skip rembg.")
    process.add_argument("--edge-bg", default="auto"); process.add_argument("--no-solid-bg", action="store_true"); process.add_argument("--no-native-alpha", action="store_true"); process.add_argument("--no-alpha-matting", action="store_true"); process.add_argument("--inspyrenet", action="store_true"); process.add_argument("--open", action="store_true"); process.add_argument("--host", default="127.0.0.1"); process.add_argument("--port", type=int, default=8765)
    web = sub.add_parser("web", help="Start the local upload/preview web app.")
    web.add_argument("--input", type=Path, default=None); web.add_argument("--run", default=None); web.add_argument("--models", default=",".join(DEFAULT_REMBG_MODELS)); web.add_argument("--edge-bg", default="auto"); web.add_argument("--inspyrenet", action="store_true"); web.add_argument("--host", default="127.0.0.1"); web.add_argument("--port", type=int, default=8765); web.add_argument("--no-open", action="store_true")
    verify = sub.add_parser("verify", help="Verify one PNG numerically."); verify.add_argument("image", type=Path); verify.add_argument("--json", action="store_true")
    warm = sub.add_parser("warm-models", help="Pre-download rembg model weights by creating sessions."); warm.add_argument("--models", default=",".join(DEFAULT_REMBG_MODELS))
    doctor = sub.add_parser("doctor", help="Check installed tools."); doctor.add_argument("--json", action="store_true")
    prompt = sub.add_parser("agent-prompt", help="Print a reusable prompt for agents."); prompt.add_argument("description", nargs="*")
    return parser

def options_from_args(args: argparse.Namespace) -> PipelineOptions:
    return PipelineOptions(rembg_models=[m.strip() for m in (args.models or "").split(",") if m.strip()], include_inspyrenet=bool(getattr(args, "inspyrenet", False)), include_solid_bg=not bool(getattr(args, "no_solid_bg", False)), include_native_alpha=not bool(getattr(args, "no_native_alpha", False)), alpha_matting=not bool(getattr(args, "no_alpha_matting", False)), edge_bg=getattr(args, "edge_bg", "auto"))

def cmd_process(args):
    run_dir = process_image(args.input, output_dir=args.out, options=options_from_args(args))
    print(f"run: {run_dir}"); print(f"manifest: {run_dir / 'manifest.json'}")
    manifest = load_manifest(run_dir); ok = [v for v in manifest.get("variants", []) if v.get("status") == "ok"]; failed = [v for v in manifest.get("variants", []) if v.get("status") == "failed"]; skipped = [v for v in manifest.get("variants", []) if v.get("status") == "skipped"]
    print(f"variants: {len(ok)} ok, {len(failed)} failed, {len(skipped)} skipped")
    if args.open:
        from .preview_server import serve
        project_root = run_dir.parent.parent if run_dir.parent.name == "runs" else Path.cwd()
        serve(project_root, host=args.host, port=args.port, run_id=run_dir.name)
    return 0

def cmd_web(args):
    run_id = args.run; project_root = Path.cwd()
    if args.input:
        run_dir = process_image(args.input, options=PipelineOptions(rembg_models=[m.strip() for m in (args.models or "").split(",") if m.strip()], include_inspyrenet=args.inspyrenet, edge_bg=args.edge_bg))
        run_id = run_dir.name; print(f"run: {run_dir}"); project_root = run_dir.parent.parent if run_dir.parent.name == "runs" else Path.cwd()
    from .preview_server import serve
    serve(project_root, host=args.host, port=args.port, open_browser=not args.no_open, run_id=run_id)
    return 0

def cmd_verify(args):
    stats = alpha_stats(Image.open(args.image)).to_dict()
    if args.json: print(json.dumps(stats, indent=2))
    else:
        print(f"file: {args.image}")
        for k, v in stats.items(): print(f"{k}: {v}")
        print("PASS" if stats["has_real_alpha"] and stats["fully_transparent_hidden_rgb_nonzero"] == 0 else "FAIL")
    return 0 if stats["has_real_alpha"] else 1

def cmd_warm_models(args):
    try:
        from rembg import new_session
    except Exception as exc:
        print(f"rembg is not installed or failed to import: {exc}", file=sys.stderr); return 1
    for model in [m.strip() for m in (args.models or "").split(",") if m.strip()]:
        print(f"warming {model}...")
        try: new_session(model); print(f"ok: {model}")
        except Exception as exc: print(f"failed: {model}: {exc}", file=sys.stderr)
    return 0

def cmd_doctor(args):
    status = tool_status(); status["python"] = {"version": sys.version.split()[0], "executable": sys.executable}
    if args.json: print(json.dumps(status, indent=2))
    else:
        print("Transparent PNG Lab doctor"); print(f"Python: {status['python']['version']} ({status['python']['executable']})")
        for name, info in status.items():
            if name == "python": continue
            mark = "OK" if info.get("available") else "MISSING"; version = f" {info.get('version')}" if info.get("version") else ""; extra = f" — {info.get('error')}" if info.get("error") else ""
            print(f"{mark:7} {name}{version}{extra}")
        print("\nRerun ./install.sh or ./update.sh to update installed packages.")
    return 0

def cmd_agent_prompt(args):
    description = " ".join(args.description).strip() or "[describe the desired transparent image here]"
    print(f"""You are working inside Transparent PNG Lab.

Create this transparent-image source asset:

    {description}

Rules:
- Do not generate a checkerboard, transparency grid, or fake PNG preview.
- Generate the subject isolated on a flat matte light-gray background, preferably #e6e6e6.
- Keep the full object visible. Avoid floor, shadow, reflection, border, frame, and textured background.
- Save the generated source image as inputs/generated.png.
- Then run:

    ./tpng process inputs/generated.png --open

- Inspect every variant in the browser over black, white, magenta, blue, and other swatch colours.
- Choose only a variant whose PNG has real alpha and no baked checkerboard traces.""")
    return 0

def main(argv=None) -> int:
    parser = build_parser(); args = parser.parse_args(argv)
    try:
        if args.command == "process": return cmd_process(args)
        if args.command == "web": return cmd_web(args)
        if args.command == "verify": return cmd_verify(args)
        if args.command == "warm-models": return cmd_warm_models(args)
        if args.command == "doctor": return cmd_doctor(args)
        if args.command == "agent-prompt": return cmd_agent_prompt(args)
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr); return 130
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr); return 1
    parser.print_help(); return 2

if __name__ == "__main__":
    raise SystemExit(main())
