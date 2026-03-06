import shutil
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models import Job
from app.storage.local import input_file_path
from app.workers.tasks import run_conversion

# this file defines API routes for Job management, 
# creates DB record, validates input, saves files, sends tasks to Celery

# API routes for job management (create, status, download)
router = APIRouter()

# using sqlalchemy session for DB Access
# to get DB session for API endpoints
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# to create new job
@router.post("/jobs")
async def create_job(
    file: UploadFile = File(...), # accepts file upload, required
    output_type: str = Form(...), # output type (pdf/png), required
    db: Session = Depends(get_db), # DB session dependency 
):
    output_type = output_type.lower()
    if output_type not in {"pdf", "png", "jpg"}:
        raise HTTPException(status_code=400, detail="output_type must be pdf, png, or jpg")

    # after receiving file, create DB record with status "queued", progress 0, message "Queued"
    job = Job(
        original_filename=file.filename,
        output_type=output_type,
        status="queued",
        progress=0,
        message="Queued",
        input_path="",  
    )
    db.add(job) # add job to DB session
    db.commit() # commit to save to DB
    db.refresh(job) # refresh to get generated ID

    # save uploaded file to local storage with path based on job ID and original filename
    in_path = input_file_path(job.id, file.filename)
    
    with in_path.open("wb") as f: # open file for writing in binary mode - tried in n8n
        shutil.copyfileobj(file.file, f) # shutil to save file efficiently

    job.input_path = str(in_path)
    db.commit()

    # Enqueue background work
    run_conversion.delay(job.id) # send job ID to Celery worker to process conversion in background

    return {"job_id": job.id, "status": job.status}

# to get job status and details
@router.get("/jobs/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # return job details including status, progress, message, error, and whether download is ready
    return {
        "job_id": job.id,
        "status": job.status,
        "progress": job.progress,
        "message": job.message,
        "error": job.error_message,
        "download_ready": job.status == "complete" and job.output_path is not None, 
        # download is ready if job is complete and output path exists
    }

# to download converted file when job is complete
@router.get("/jobs/{job_id}/download")
def download(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first() # query DB for job by ID
    
    if not job: # if job not found, return 404
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status != "complete" or not job.output_path: # if job not complete or output path doesn't exist, can't download
        raise HTTPException(status_code=400, detail="Output not ready")

    # return file response to download the converted file, with appropriate filename and media type
    return FileResponse(
        path=job.output_path,
        filename=f"{job_id}.{job.output_type}",
        media_type="application/octet-stream", 
        # OCTET_STREAM for generic binary download - forces download rather than trying to display in browser
    )