import fitz  # pymupdf
import numpy as np


def autocrop_pdf_inplace(pdf_path: str, zoom: float = 3.0, white_thresh: int = 245, pad_px: int = 20) -> bool:
    """
    Crops each page's CropBox to the bounding box of non-white pixels (render-based).
    Returns True if crop was applied, False if no content detected.
    """
    doc = fitz.open(pdf_path)
    changed = False

    for i in range(doc.page_count):
        page = doc.load_page(i)
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)

        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        if img.shape[2] > 3:
            img = img[:, :, :3]

        # grayscale
        gray = (0.299 * img[:, :, 0] + 0.587 * img[:, :, 1] + 0.114 * img[:, :, 2]).astype(np.uint8)

        # non-white mask
        mask = gray < white_thresh
        if not mask.any():
            continue

        ys, xs = np.where(mask)
        x0, x1 = xs.min(), xs.max()
        y0, y1 = ys.min(), ys.max()

        # add padding (in pixels)
        x0 = max(0, x0 - pad_px)
        y0 = max(0, y0 - pad_px)
        x1 = min(pix.width - 1, x1 + pad_px)
        y1 = min(pix.height - 1, y1 + pad_px)

        # map pixel coords back to PDF coords
        # pix coords -> page coords: divide by zoom
        rect = fitz.Rect(x0 / zoom, y0 / zoom, x1 / zoom, y1 / zoom)

        # Clamp to page bounds
        rect = rect & page.rect
        if rect.is_empty or rect.width < 2 or rect.height < 2:
            continue

        page.set_cropbox(rect)
        changed = True

    if changed:
        doc.saveIncr()  # in-place incremental save
    doc.close()
    return changed