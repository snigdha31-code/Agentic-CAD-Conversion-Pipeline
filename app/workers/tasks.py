
# Full Celery worker that supports:
# - AI planning (OpenRouter) -> attempts list
# - Provider auto-switching:
#     Prefer CloudConvert when available
#     If CloudConvert credits exceeded and input is DXF -> fallback to Inkscape (open-source local)
# - Strong reliability pipelines:
#     DXF: Inkscape works well for PDF/PNG
#     DWG: CloudConvert works well for PDF
#     DWG -> PNG: uses DWG -> PDF -> PNG pipeline 
# - Validation after each attempt (blank/cropped detection)
# - If PDF blank/cropped: uses CAD->PNG->PDF pipeline as rescue, trying both providers if needed
#
# IMPORTANT: Restart Celery worker after replacing this file.
#
# Run worker:
#   celery -A app.workers.celery_app.celery worker --loglevel=INFO --pool=solo

import os
import asyncio # for running async planner in sync task
import traceback # for better error logging
from sqlalchemy.orm import Session # for DB access

from app.workers.celery_app import celery 
from app.db.session import SessionLocal # for DB access
from app.db.models import Job
from app.storage.local import output_file_path
from app.agent.planner import make_plan
from app.validation.checks import validate_output

from app.providers.inkscape import run_inkscape
from app.providers.cloudconvert import run_cloudconvert

# Helper functions for updating job status, 
# checking specific error types, and 
# running conversions 
def update_job(db: Session, job_id: str, **fields) -> None: # fields is a dict of fields to update on the job record
    # fields include status, progress, message, output_path, error_message - any fields on the Job model
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        return
    for k, v in fields.items(): # k is field name, v is value
        setattr(job, k, v)
    db.commit()


# error checking - if CloudConvert credits exceeded
def _is_cloudconvert_credits_exceeded(exc: Exception) -> bool:
    msg = str(exc).lower()
    return (
        ("402" in msg and "payment required" in msg)
        or ("credits_exceeded" in msg)
        or ("run out of conversion credits" in msg)
        or ("your account has run out of conversion credits" in msg)
    )

# error checking - if PDF is blank/cropped due to viewport issues
def _is_blank_cropped_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return ("blank" in msg) or ("cropped" in msg) or ("extents" in msg) or ("viewport" in msg)

# Core conversion execution function that handles provider-specific logic 
def _execute_conversion(
    *,
    provider: str, # provider to use for conversion, e.g. "cloudconvert" or "inkscape"
    input_path: str, # path to input file to convert
    out_path: str, # path to save converted output file
    output_type: str, # desired output type/format
    params: dict, # additional parameters for conversion, e.g. {"dpi": 600} or {"page_size": "A0"}
    max_runtime_sec: int, # maximum allowed runtime for the conversion process, used to prevent hanging tasks
) -> None:
    """
    Runs a conversion via the chosen provider.

    Special reliability rule:
      - If provider=cloudconvert AND input is DWG AND output is PNG/JPG:
            do DWG -> PDF -> PNG/JPG
        (Because direct DWG raster export may fail or produce blank output.)
    """
    params = params or {} # ensure params is a dict even if None is passed
    ext = os.path.splitext(input_path)[1].lstrip(".").lower() # get file extension of input file

    if provider == "inkscape":
        run_inkscape(
            input_path=input_path,
            output_path=out_path,
            output_type=output_type,
            params=params,
        )
        return

    if provider == "cloudconvert":
        # Reliable pipeline for DWG -> image outputs
        if ext == "dwg" and output_type in ("png", "jpg", "jpeg"):
            tmp_pdf = out_path + ".__tmp__.pdf" 
            # temporary path for intermediate PDF output in DWG->PDF->image pipeline

            # Step 1: DWG -> PDF
            run_cloudconvert(
                input_path=input_path,
                output_path=tmp_pdf,
                output_type="pdf",
                params={
                    # best-effort: some backends respect these, some ignore
                    "page_size": params.get("page_size", "A0"), # A0 to ensure large canvas for complex drawings 
                    "fit_mode": params.get("fit_mode", "drawing"), # fit to drawing extents to avoid blank/cropped issues
                },
                max_runtime_sec=max_runtime_sec, # pass max runtime to prevemt hanging
            )

            # Step 2: PDF -> image
            run_cloudconvert(
                input_path=tmp_pdf,
                output_path=out_path,
                output_type=("png" if output_type == "png" else "jpg"),
                params={"dpi": int(params.get("dpi", 600))},
                max_runtime_sec=max_runtime_sec,
            )

            # Cleanup temp file best-effort
            try:
                os.remove(tmp_pdf)
            except Exception:
                pass

            return

        # Normal CloudConvert conversion
        run_cloudconvert(
            input_path=input_path,
            output_path=out_path,
            output_type=output_type,
            params=params,
            max_runtime_sec=max_runtime_sec,
        )
        return

    raise ValueError(f"Unknown provider: {provider}")

# Rescue pipeline for blank/cropped PDFs: CAD -> PNG (high DPI) -> PDF
def _png_to_pdf_pipeline(
    *, # parameters passed as keyword arguments for clarity
    prefer_provider: str, 
    input_path: str,
    job_id: str,
    final_pdf_path: str,
    max_runtime_sec: int,
) -> None:
    """
    Rescue pipeline for blank/cropped PDFs:
      CAD -> PNG (high DPI) -> PDF

    Tries prefer_provider first, then alternates.
    """
    providers_to_try = [prefer_provider]
    if prefer_provider != "inkscape":
        providers_to_try.append("inkscape")
    if prefer_provider != "cloudconvert":
        providers_to_try.append("cloudconvert")

    tmp_png = str(output_file_path(job_id, "png"))
    last_err = None # to store last error message for better debugging if all attempts fail

    # Try providers in order for the PNG->PDF pipeline rescue
    for prov in providers_to_try:
        try:
            # Step 1: CAD -> PNG (high DPI)
            _execute_conversion(
                provider=prov,
                input_path=input_path,
                out_path=tmp_png,
                output_type="png",
                params={"dpi": 1200, "export_area": "drawing"},
                max_runtime_sec=max_runtime_sec,
            )

            # Step 2: PNG -> PDF
            _execute_conversion(
                provider=prov,
                input_path=tmp_png,
                out_path=final_pdf_path,
                output_type="pdf",
                params={},
                max_runtime_sec=max_runtime_sec,
            )
            return
        except Exception as e:
            last_err = str(e)
            if prov == "cloudconvert" and _is_cloudconvert_credits_exceeded(e):
                # if CloudConvert credits are exceeded, no need to try other provider since it will fail for same reason
                continue

    raise RuntimeError(f"PNG->PDF rescue failed. Last error: {last_err}")


# Celery task that runs the entire conversion process for a given job ID, 
# including planning, execution, validation, and retries.
@celery.task(bind=True)
# This is the main entry point for the Celery worker when processing a conversion job.
def run_conversion(self, job_id: str):
    db = SessionLocal()
    history: list[dict] = []
    last_error=None
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return

        input_path = job.input_path
        input_ext = os.path.splitext(input_path)[1].lstrip(".").lower()
        file_size_mb = os.path.getsize(input_path) / (1024 * 1024)

        # 1) Planning - ask ai to make a plan of conversion attempts based on I/O types and file size
        update_job(db, job_id, status="planning", progress=5, message="Planning conversion strategy (AI)...")
        plan = asyncio.run(
            make_plan(
                input_ext=input_ext,
                output_type=job.output_type,
                file_size_mb=file_size_mb,
                history=history,
            )
        )
        # plan is expected to have a list of attempts, where each attempt specifies a provider, 
        # output type, and parameters for conversion
        attempts = list(getattr(plan, "attempts", []) or [])
        if not attempts:
            raise RuntimeError("Planner returned 0 attempts.")

        max_attempts = len(attempts)

        # 2) Attempt loop
        for idx, attempt in enumerate(attempts, start=1):
            provider = getattr(attempt, "provider", "cloudconvert")
            attempt_output_type = getattr(attempt, "output_type", job.output_type)
            attempt_params = getattr(attempt, "params", {}) or {}

            update_job(
                db,
                job_id,
                status="processing",
                # PROGRESS is calculated as 10% + equal increments for each attempt,
                # e.g. for 5 attempts: 10%, 24%, 38%, 52%, 66%
                # idx starts at 1, so we do (idx - 1) to get 0-based index for progress calculation
                # 70% is allocated for the attempts, divided equally among them
                progress=10 + int((idx - 1) * 70 / max_attempts),
                message=f"Converting via {provider} (attempt {idx}/{max_attempts})...",
            )

            out_path = str(output_file_path(job_id, job.output_type))

            # Execute conversion
            try:
                # If attempt requests png->pdf pipeline and user asked PDF
                if (
                    job.output_type == "pdf"
                    and attempt_output_type == "png"
                    and isinstance(attempt_params, dict) # ensure params is a dict before checking for pipeline_png_to_pdf key
                    and attempt_params.get("pipeline_png_to_pdf")
                ):
                    _png_to_pdf_pipeline(
                        prefer_provider=provider,
                        input_path=input_path,
                        job_id=job_id,
                        final_pdf_path=out_path,
                        max_runtime_sec=plan.validation.max_runtime_sec,
                    )
                else:
                    _execute_conversion(
                        provider=provider,
                        input_path=input_path,
                        out_path=out_path,
                        output_type=job.output_type,
                        params=attempt_params if isinstance(attempt_params, dict) else {},
                        max_runtime_sec=plan.validation.max_runtime_sec,
                    )

            except Exception as e:
                last_error = str(e)
                # If CloudConvert credits exceeded and DXF input, retry locally with Inkscape
                if provider == "cloudconvert" and _is_cloudconvert_credits_exceeded(e) and input_ext == "dxf":
                    update_job(
                        db,
                        job_id,
                        status="processing",
                        progress=80,
                        message="Cloud credits exceeded. Retrying locally with Inkscape...",
                    )
                    try:
                        _execute_conversion(
                            provider="inkscape",
                            input_path=input_path,
                            out_path=out_path,
                            output_type=job.output_type,
                            params={"export_area": "drawing", **(attempt_params if isinstance(attempt_params, dict) else {})},
                            max_runtime_sec=plan.validation.max_runtime_sec,
                        )
                    except Exception as e2:
                        history.append({"attempt": idx, "provider": "inkscape", "stage": "convert", "error": str(e2)})
                        continue
                else:
                    history.append({"attempt": idx, "provider": provider, "stage": "convert", "error": str(e)})
                    continue

            # 3) Validate
            update_job(db, job_id, status="validating", progress=90, message="Validating output...")
            try:
                validate_output(out_path, job.output_type, plan.validation.min_kb)
            except ValueError as ve:
                last_error = str(ve)
                # If PDF blank/cropped -> rescue via CAD->PNG->PDF
                if job.output_type == "pdf" and _is_blank_cropped_error(ve):
                    update_job(
                        db,
                        job_id,
                        status="processing",
                        progress=92,
                        message="Blank/cropped PDF detected. Retrying via PNG pipeline...",
                        # png pipeline is more reliable for CAD->PDF conversions, 
                        # as it avoids issues with PDF viewport that can cause blank/cropped output
                    )
                    try:
                        _png_to_pdf_pipeline(
                            prefer_provider=provider if provider in ("inkscape", "cloudconvert") else "inkscape",
                            input_path=input_path,
                            job_id=job_id,
                            final_pdf_path=out_path,
                            max_runtime_sec=plan.validation.max_runtime_sec,
                        )
                        update_job(db, job_id, status="validating", progress=97, message="Validating (after PNG rescue)...")
                        validate_output(out_path, "pdf", plan.validation.min_kb)
                    except Exception as e3:
                        history.append({"attempt": idx, "provider": "rescue", "stage": "validate/rescue", "error": str(e3)})
                        continue
                else:
                    history.append({"attempt": idx, "provider": provider, "stage": "validate", "error": str(ve)})
                    continue

            # Success
            update_job(
                db,
                job_id,
                status="complete",
                progress=100,
                message="Complete.",
                output_path=out_path,
            )
            return

        # All attempts failed
        update_job(
            db,
            job_id,
            status="failed",
            progress=100,
            message="Failed.",
            error_message=last_error or "Conversion failed after retries.",
        )

    except Exception:
        update_job(
            db,
            job_id,
            status="failed",
            progress=100,
            message="Failed.",
            error_message=traceback.format_exc(),
        )
    finally:
        db.close()