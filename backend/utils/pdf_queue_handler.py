import logging
import zipfile
import asyncio
import os

from core import job_state as job_state
from services.pdf_translator import run_translation_task

logger = logging.getLogger(__name__)

# Function to handle serial processing of selected PDFs
async def start_serial_processing(pdf_list: list, job_id: str):

    processed_pdf_paths = []

    job_state.create_job(job_id)
    # jobs[job_id] = {"status": "starting", "result_path": None, "error": None}

    logger.info(f"Job {job_id}: Created.")

    logger.info("Starting serial translation task...")

    try:
        for file_path in pdf_list:

            output_path = await asyncio.to_thread(run_translation_task, job_id, file_path)

            processed_pdf_paths.append(output_path)

        
        ZIP_DIR = "output_zips"
        os.makedirs(ZIP_DIR, exist_ok=True)
        zip_file_path = os.path.join(ZIP_DIR, f"{job_id}.zip")

        logger.info(f"Job {job_id}: Zipping {len(processed_pdf_paths)} files...")

        with zipfile.ZipFile(zip_file_path, 'w') as zf:
            for file_path in processed_pdf_paths:

                file_name = os.path.basename(file_path)
                zf.write(file_path, arcname=file_name)


        logger.info(f"Zip file {zip_file_path} created successfully")

        job_state.set_job_result(job_id, zip_file_path)
        # logger.info(f"Job {job_id}: Processing complete. Result at {output_path}")

    except Exception as e:
        logger.error(f"Job {job_id}: Serial processing FAILED.", exc_info=True)
        job_state.update_job_status(job_id, "error", error=str(e))
        
    finally:
        # 4. THIS IS THE 'finally' BLOCK YOU NEED
        # It cleans up all the intermediate translated PDFs
        logger.info(f"Job {job_id}: Cleaning up intermediate files...")
        for path in processed_pdf_paths:
            if os.path.exists(path):
                try:
                    os.remove(path)
                    logger.debug(f"Job {job_id}: Removed {path}")
                except Exception as e:
                    logger.error(f"Job {job_id}: Failed to remove {path}. {e}")
