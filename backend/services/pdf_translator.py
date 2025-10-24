# ==============================================================================
# MAIN BACKGROUND WORKER TASK FUNCTION
# ==============================================================================


import logging
import fitz
import os

# Import isolated modules
from core import job_state as job_state
from utils.legends_util import create_legend_pdf_page
from utils.text_extraction import extract_text_with_location, filter_chinese_text
from utils.translation import translate_chinese_to_english
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

        job_state.update_job_status(job_id, "extracting")
        all_text = extract_text_with_location(doc)
        chinese_text_data = filter_chinese_text(all_text)

        if not chinese_text_data:
            raise ValueError("No Chinese text found in the document.")

        job_state.update_job_status(job_id, "translating")
        translated_data = translate_chinese_to_english(chinese_text_data)
        
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