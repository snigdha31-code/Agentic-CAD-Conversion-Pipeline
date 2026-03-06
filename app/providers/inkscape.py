import subprocess
import os

INKSCAPE_PATH = r"C:\Program Files\Inkscape\bin\inkscape.exe"

def run_inkscape(input_path: str, output_path: str, output_type: str, params: dict):
    if not os.path.exists(INKSCAPE_PATH):
        raise RuntimeError(f"Inkscape not found at: {INKSCAPE_PATH}")

    params = params or {}
    cmd = [INKSCAPE_PATH, input_path, "--batch-process", "--export-overwrite"]

    export_area = params.get("export_area", "drawing")
    if export_area == "drawing":
        cmd += ["--export-area-drawing"]
    else:
        cmd += ["--export-area-page"]

    # Defaults that help raster exports
    if output_type == "png":
        cmd += ["--export-background=white", "--export-background-opacity=1"]

    if output_type == "pdf":
        cmd += ["--export-type=pdf", f"--export-filename={output_path}"]
    elif output_type == "png":
        cmd += ["--export-type=png", f"--export-filename={output_path}"]
        cmd += [f"--export-dpi={int(params.get('dpi', 600))}"]
    else:
        raise ValueError("output_type must be pdf or png")

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"Inkscape failed.\nCMD: {' '.join(cmd)}\nSTDERR: {result.stderr}\nSTDOUT: {result.stdout}")