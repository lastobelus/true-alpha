from __future__ import annotations
import os, platform, shutil, subprocess
from pathlib import Path

def save_png_with_native_dialog(src_path: Path, suggested_name: str) -> dict:
    dest = choose_save_path(suggested_name)
    if dest is None:
        return {"status": "cancelled"}
    if dest.suffix.lower() != ".png":
        dest = dest.with_suffix(".png")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_path, dest)
    return {"status": "saved", "path": str(dest)}

def choose_save_path(suggested_name: str) -> Path | None:
    system = platform.system()
    if system == "Darwin":
        return _macos_save_path(suggested_name)
    if system == "Linux":
        return _linux_save_path(suggested_name)
    raise RuntimeError("Native save dialog is supported only on macOS and Linux.")

def choose_folder_path(prompt: str = "Choose image folder:") -> Path | None:
    system = platform.system()
    if system == "Darwin":
        return _macos_folder_path(prompt)
    if system == "Linux":
        return _linux_folder_path(prompt)
    raise RuntimeError("Native folder picker is supported only on macOS and Linux.")

def choose_file_path(prompt: str = "Choose input image:") -> Path | None:
    system = platform.system()
    if system == "Darwin":
        return _macos_file_path(prompt)
    if system == "Linux":
        return _linux_file_path(prompt)
    raise RuntimeError("Native file picker is supported only on macOS and Linux.")

def _macos_save_path(suggested_name: str) -> Path | None:
    if not shutil.which("osascript"):
        raise RuntimeError("osascript not found")
    safe_name = suggested_name.replace('\\', '\\\\').replace('"', '\\"')
    cmd = ["osascript", "-e", f'set savePath to choose file name with prompt "Save selected transparent PNG as:" default name "{safe_name}"', "-e", "POSIX path of savePath"]
    result = subprocess.run(cmd, text=True, capture_output=True)
    if result.returncode == 0:
        path = result.stdout.strip()
        return Path(path).expanduser() if path else None
    if "User canceled" in result.stderr or "-128" in result.stderr:
        return None
    raise RuntimeError(result.stderr.strip() or "macOS save dialog failed")

def _macos_folder_path(prompt: str) -> Path | None:
    if not shutil.which("osascript"):
        raise RuntimeError("osascript not found")
    safe_prompt = prompt.replace('\\', '\\\\').replace('"', '\\"')
    cmd = ["osascript", "-e", f'set folderPath to choose folder with prompt "{safe_prompt}"', "-e", "POSIX path of folderPath"]
    result = subprocess.run(cmd, text=True, capture_output=True)
    if result.returncode == 0:
        path = result.stdout.strip()
        return Path(path).expanduser() if path else None
    if "User canceled" in result.stderr or "-128" in result.stderr:
        return None
    raise RuntimeError(result.stderr.strip() or "macOS folder picker failed")

def _macos_file_path(prompt: str) -> Path | None:
    if not shutil.which("osascript"):
        raise RuntimeError("osascript not found")
    safe_prompt = prompt.replace('\\', '\\\\').replace('"', '\\"')
    cmd = ["osascript", "-e", f'set filePath to choose file with prompt "{safe_prompt}"', "-e", "POSIX path of filePath"]
    result = subprocess.run(cmd, text=True, capture_output=True)
    if result.returncode == 0:
        path = result.stdout.strip()
        return Path(path).expanduser() if path else None
    if "User canceled" in result.stderr or "-128" in result.stderr:
        return None
    raise RuntimeError(result.stderr.strip() or "macOS file picker failed")

def _linux_save_path(suggested_name: str) -> Path | None:
    default = str(Path.home() / suggested_name)
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        raise RuntimeError("No DISPLAY or WAYLAND_DISPLAY; cannot open a graphical save dialog.")
    if shutil.which("zenity"):
        result = subprocess.run(["zenity", "--file-selection", "--save", "--confirm-overwrite", f"--filename={default}"], text=True, capture_output=True)
        if result.returncode == 0: return Path(result.stdout.strip()).expanduser()
        if result.returncode in {1, 5}: return None
        raise RuntimeError(result.stderr.strip() or "zenity save dialog failed")
    if shutil.which("kdialog"):
        result = subprocess.run(["kdialog", "--getsavefilename", default, "*.png|PNG image"], text=True, capture_output=True)
        if result.returncode == 0: return Path(result.stdout.strip()).expanduser()
        if result.returncode == 1: return None
        raise RuntimeError(result.stderr.strip() or "kdialog save dialog failed")
    if shutil.which("yad"):
        result = subprocess.run(["yad", "--file-selection", "--save", "--confirm-overwrite", f"--filename={default}"], text=True, capture_output=True)
        if result.returncode == 0: return Path(result.stdout.strip()).expanduser()
        if result.returncode == 1: return None
        raise RuntimeError(result.stderr.strip() or "yad save dialog failed")
    raise RuntimeError("No Linux save dialog helper found. Install zenity, kdialog, or yad.")

def _linux_folder_path(prompt: str) -> Path | None:
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        raise RuntimeError("No DISPLAY or WAYLAND_DISPLAY; cannot open a graphical folder picker.")
    if shutil.which("zenity"):
        result = subprocess.run(["zenity", "--file-selection", "--directory", f"--title={prompt}"], text=True, capture_output=True)
        if result.returncode == 0: return Path(result.stdout.strip()).expanduser()
        if result.returncode in {1, 5}: return None
        raise RuntimeError(result.stderr.strip() or "zenity folder picker failed")
    if shutil.which("kdialog"):
        result = subprocess.run(["kdialog", "--getexistingdirectory", str(Path.home())], text=True, capture_output=True)
        if result.returncode == 0: return Path(result.stdout.strip()).expanduser()
        if result.returncode == 1: return None
        raise RuntimeError(result.stderr.strip() or "kdialog folder picker failed")
    if shutil.which("yad"):
        result = subprocess.run(["yad", "--file-selection", "--directory", f"--title={prompt}"], text=True, capture_output=True)
        if result.returncode == 0: return Path(result.stdout.strip()).expanduser()
        if result.returncode == 1: return None
        raise RuntimeError(result.stderr.strip() or "yad folder picker failed")
    raise RuntimeError("No Linux folder picker helper found. Install zenity, kdialog, or yad.")

def _linux_file_path(prompt: str) -> Path | None:
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        raise RuntimeError("No DISPLAY or WAYLAND_DISPLAY; cannot open a graphical file picker.")
    if shutil.which("zenity"):
        result = subprocess.run(["zenity", "--file-selection", f"--title={prompt}", "--file-filter=Images | *.png *.jpg *.jpeg *.webp"], text=True, capture_output=True)
        if result.returncode == 0: return Path(result.stdout.strip()).expanduser()
        if result.returncode in {1, 5}: return None
        raise RuntimeError(result.stderr.strip() or "zenity file picker failed")
    if shutil.which("kdialog"):
        result = subprocess.run(["kdialog", "--getopenfilename", str(Path.home()), "*.png *.jpg *.jpeg *.webp|Images"], text=True, capture_output=True)
        if result.returncode == 0: return Path(result.stdout.strip()).expanduser()
        if result.returncode == 1: return None
        raise RuntimeError(result.stderr.strip() or "kdialog file picker failed")
    if shutil.which("yad"):
        result = subprocess.run(["yad", "--file-selection", f"--title={prompt}", "--file-filter=Images | *.png *.jpg *.jpeg *.webp"], text=True, capture_output=True)
        if result.returncode == 0: return Path(result.stdout.strip()).expanduser()
        if result.returncode == 1: return None
        raise RuntimeError(result.stderr.strip() or "yad file picker failed")
    raise RuntimeError("No Linux file picker helper found. Install zenity, kdialog, or yad.")
