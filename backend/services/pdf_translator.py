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
    try:
        logger.info(f"Job {job_id}: Starting processing for {pdf_path}")
        doc = fitz.open(pdf_path)
        pdf_bytes = doc.tobytes()

        job_state.update_job_status(job_id, "extracting")

        # Extract all text using fitz
        all_text = extract_text_with_location(doc)

        # Extract bottom right table text using pdfplumber
        # brt = extract_table_cells(pdf_bytes, 665, 665, 1180, 830)

        # Extract extract left side table text using pdfplumber
        # lsd = extract_table_cells(pdf_bytes, 665, 665, 1180, 830)

        # Remove doubly extracted text from the brt table
        # interim_text_list = final_extracted_text_list(brt, all_text)

        # Similarly remove doubly extracted text from the lsd table
        # final_text_list = final_extracted_text_list(lsd, interim_text_list)

        # Filter out the Chinese text from it.
        hebrew_text_data = filter_hebrew_text(all_text)

        if not hebrew_text_data:
            raise ValueError("No Chinese text found in the document.")

        job_state.update_job_status(job_id, "translating")
        translated_data = translate_hebrew_to_english(hebrew_text_data)
        
        enriched_data, legend_terms = prepare_display_data(translated_data)

        job_state.update_job_status(job_id, "creating_pdf")
        output_path = pdf_path.replace(".pdf", "_translated.pdf")
        
        translated_doc = create_translated_doc_in_memory(doc, enriched_data)

        if legend_terms:
            first_page = translated_doc[0]
            page_height = first_page.rect.height
            legend_width = max(180, first_page.rect.width * 0.35)
            legend_doc = create_legend_pdf_page(legend_terms, page_height=page_height, page_width=legend_width)
            assemble_final_pdf(translated_doc, legend_doc, output_path)
            translated_doc.close()
            legend_doc.close()
        else:
            translated_doc.save(output_path)
            translated_doc.close()


        return output_path

    except Exception as e:
        logger.error(f"Job {job_id}: Task failed.", exc_info=True)
        job_state.update_job_status(job_id, "error", error=str(e))
    finally:
        if 'doc' in locals() and not doc.is_closed:
            doc.close()