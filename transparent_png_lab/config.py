from __future__ import annotations
from pathlib import Path
PROJECT_ROOT = Path.cwd()
INPUTS_DIR = PROJECT_ROOT / "inputs"
RUNS_DIR = PROJECT_ROOT / "runs"
DEFAULT_REMBG_MODELS = ["u2netp", "u2net", "isnet-general-use", "birefnet-general"]
SHOW_DOWNLOAD_FALLBACK = False
PREVIEW_BACKGROUNDS = [
    {"name": "black", "hex": "#000000", "rgb": [0, 0, 0]},
    {"name": "white", "hex": "#ffffff", "rgb": [255, 255, 255]},
    {"name": "near white", "hex": "#f2f2f2", "rgb": [242, 242, 242]},
    {"name": "mid gray", "hex": "#808080", "rgb": [128, 128, 128]},
    {"name": "charcoal", "hex": "#242424", "rgb": [36, 36, 36]},
    {"name": "red", "hex": "#d62828", "rgb": [214, 40, 40]},
    {"name": "orange", "hex": "#f77f00", "rgb": [247, 127, 0]},
    {"name": "yellow", "hex": "#fcbf49", "rgb": [252, 191, 73]},
    {"name": "green", "hex": "#2a9d8f", "rgb": [42, 157, 143]},
    {"name": "cyan", "hex": "#00b4d8", "rgb": [0, 180, 216]},
    {"name": "blue", "hex": "#4361ee", "rgb": [67, 97, 238]},
    {"name": "purple", "hex": "#7209b7", "rgb": [114, 9, 183]},
    {"name": "magenta", "hex": "#ff00ff", "rgb": [255, 0, 255]},
    {"name": "warm tan", "hex": "#d4a373", "rgb": [212, 163, 115]},
    {"name": "deep teal", "hex": "#005f73", "rgb": [0, 95, 115]},
    {"name": "pink", "hex": "#ffafcc", "rgb": [255, 175, 204]},
]
AUDIT_BACKGROUNDS = {bg["name"].replace(" ", "_"): tuple(bg["rgb"]) for bg in PREVIEW_BACKGROUNDS}
