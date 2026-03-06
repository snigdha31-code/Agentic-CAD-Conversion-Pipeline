import os
import numpy as np
from pypdf import PdfReader
import fitz  # PyMuPDF
from PIL import Image

def _blank_ratio_from_pixmap(pix: fitz.Pixmap) -> float:
    """Return fraction of pixels that are near-white."""
    if pix.alpha:
        pix = fitz.Pixmap(pix, 0)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if img.shape[2] > 3:
        img = img[:, :, :3]
    gray = (0.299 * img[:, :, 0] + 0.587 * img[:, :, 1] + 0.114 * img[:, :, 2]).astype(np.uint8)
    return float((gray >= 245).mean())


def is_visually_blank_pdf(path: str, zoom: float = 3.0, blank_ratio_threshold: float = 0.99) -> bool:
    doc = fitz.open(path)
    try:
        if doc.page_count < 1:
            return True
        page = doc.load_page(0)
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        ratio = _blank_ratio_from_pixmap(pix)
        return ratio >= blank_ratio_threshold
    finally:
        doc.close()


def validate_output(path: str, output_type: str, min_kb: int = 1) -> None:
    """
    PDF: structural validity + not visually blank/cropped.
    PNG: basic file existence + optional minimum size.
    """
    if not os.path.exists(path):
        raise ValueError("Output file not created.")

    output_type = (output_type or "").lower().strip()

    if output_type == "pdf":
        # Structural PDF check
        try:
            reader = PdfReader(path)
            if len(reader.pages) < 1:
                raise ValueError("PDF has 0 pages.")
        except Exception as e:
            raise ValueError(f"Invalid PDF: {e}")

        # Visual blank/crop check
        if is_visually_blank_pdf(path):
            raise ValueError("PDF appears visually blank/cropped (extents/viewport issue).")

        return

    if output_type == "png":
        try:
            with Image.open(path) as im:
                im.verify()  # checks file isn't corrupted
            with Image.open(path) as im:
                w, h = im.size
            if w < 10 or h < 10:
                raise ValueError(f"PNG dimensions too small: {w}x{h}")
        except Exception as e:
            raise ValueError(f"Invalid PNG: {e}")
        return

    raise ValueError("Only pdf and png outputs are supported.")