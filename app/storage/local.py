import os
from pathlib import Path
from app.core.config import settings

def job_dir(job_id: str) -> Path:
    p = Path(settings.DATA_DIR) / job_id
    p.mkdir(parents=True, exist_ok=True)
    return p

def input_file_path(job_id: str, filename: str) -> Path:
    return job_dir(job_id) / f"input_{filename}"

def output_file_path(job_id: str, output_type: str) -> Path:
    return job_dir(job_id) / f"output.{output_type}"