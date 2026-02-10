# ==============================================================================
# MAIN BACKGROUND WORKER TASK FUNCTION
# ==============================================================================
import logging
import fitz
import os

# Import isolated modules
from core import job_state as job_state
from utils.legends_util import create_legend_pdf_page
from utils.text_extraction import extract_text_with_location, filter_hebrew_text, extract_table_cells, final_extracted_text_list
from utils.translation import translate_hebrew_to_english
from utils.output_pdf_handler import prepare_display_data, create_translated_doc_in_memory, assemble_final_pdf

logger = logging.getLogger(__name__)


# ==============================================================================
# BACKGROUND WORKER TASK
# ==============================================================================
def run_translation_task(job_id: str, pdf_path: str):
    """The long-running function that will be executed in the background."""

    doc = fitz.open(pdf_path)
    try:
        logger.info(f"Job {job_id}: Starting processing for {pdf_path}")

        job_state.update_job_status(job_id, "extracting")

        # Extract all text using Paddle+tesseract
        all_text = extract_text_with_location(doc)

        # Filter out the Chinese text from it.
        hebrew_text_data = filter_hebrew_text(all_text)

        # logger.info(f"testing the obtained filtered hebrew text {hebrew_text_data}")

        if not hebrew_text_data:
            raise ValueError("No Hebrew text found in the document.")

        job_state.update_job_status(job_id, "translating")

        # Calling the Hebrew translation function
        translated_data = translate_hebrew_to_english(hebrew_text_data)
        
        # enriched_data, legend_terms = prepare_display_data(translated_data)

        job_state.update_job_status(job_id, "creating_pdf")
        output_path = pdf_path.replace(".pdf", "_translated.pdf")
        
        translated_doc = create_translated_doc_in_memory(doc, translated_data)

        translated_doc.save(output_path)
        translated_doc.close()

        doc.close()

        logger.info("Output PDF created successfully! Moving onto next...")

        return output_path

    except Exception as e:
        logger.error(f"Job {job_id}: Task failed.", exc_info=True)
        job_state.update_job_status(job_id, "error", error=str(e))
    finally:
        if 'doc' in locals() and not doc.is_closed:
            doc.close()