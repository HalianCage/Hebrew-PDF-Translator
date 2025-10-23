# ==============================================================================
# ALL API ENDPOINTS FILE
# ==============================================================================
import uuid
import logging
import os
from pydantic import BaseModel
from typing import List
from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from utils.pdf_queue_handler import start_serial_processing

from core import job_state as job_state

logger = logging.getLogger(__name__)
router = APIRouter()


# Defining pydantic base model
class FilePathRequest(BaseModel):
    paths: List[str]


# ==============================================================================
# ENDPOINT TO START THE TRANSLATION TASK FOR EACH PDF
# ==============================================================================
@router.post("/start-translation/")
async def start_translation(background_tasks: BackgroundTasks, request: FilePathRequest):

    """Endpoint to start the translation job."""

    logger.info('Translation API has been hit...')

    job_id = str(uuid.uuid4())

    background_tasks.add_task(start_serial_processing, request.paths, job_id)
    
    return {"job_id": job_id}



# ==============================================================================
# ENDPOINT TO GET THE STATUS OF CURRENT RUNNING JOB
# ==============================================================================
@router.get("/job-status/{job_id}")
async def get_job_status(job_id: str):

    """Endpoint to check the status of a job."""

    job = job_state.get_job(job_id)
    if job is None:
        return JSONResponse(status_code=404, content={"status": "error", "error": "Job not found"})
    
    logger.info(f"Job {job_id}: Status check requested. Current status: {job['status']}")

    return {"job_id": job_id, "status": job["status"], "error": job.get("error")}



# ==============================================================================
# ENDPOINT TO DONWLOAD THE OUTPUT ONCE THE PROCESS IS COMPLETED
# ==============================================================================
@router.get("/download/{job_id}")
async def download_result(job_id: str):

    """Endpoint to download the final translated PDF."""

    job = job_state.get_job(job_id)

    if job is None or job["status"] != "complete":
        return JSONResponse(status_code=404, content={"error": "File not ready or job not found"})
    
    file_path = job["result_path"]
    filename = os.path.basename(file_path)
    
    logger.info(f"Job {job_id}: Download requested for {file_path}")

    return FileResponse(file_path, media_type='application/zip', filename=filename)
