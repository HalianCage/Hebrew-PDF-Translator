# backend/main.py
import logging
import fitz
import re
import math
import tempfile
import os
import uuid
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

# ==============================================================================
# 1. CONFIGURE LOGGING & MODEL
# ==============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename="backend.log",
    filemode="a"
)
logger = logging.getLogger(__name__)

# This will act as our in-memory "database" to track job statuses
jobs = {}

tokenizer = None
model = None

def load_model():
    """
    Loads the model, reliably finding the path in both development
    and packaged (PyInstaller) mode.
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # This block runs when the application is a bundled executable
        # sys._MEIPASS is a special attribute set by PyInstaller to the temp folder
        base_path = sys._MEIPASS
        # The model is in a folder named 'offline_model' right next to the executable
        local_model_path = os.path.join(base_path, "offline_model")
    else:
        # This block runs when in a normal Python environment (development)
        # We find the path relative to the current script file
        base_path = os.path.dirname(os.path.abspath(__file__))
        local_model_path = os.path.join(base_path, "..", "offline_model")
    
    logger.info(f"Attempting to load model from path: {local_model_path}")
    
    tokenizer = AutoTokenizer.from_pretrained(local_model_path)
    model = AutoModelForSeq2SeqLM.from_pretrained(local_model_path)
    return tokenizer, model



# ==============================================================================
# 2. LIFESPAN EVENT FOR STARTUP
# ==============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):

    # Code to run before the server starts accepting any requests
    global tokenizer, model
    try :
        logger.info("Server starting up: Setting up the translation model...")
        tokenizer, model = load_model()
        logger.info("model loaded successfully. Server is ready")
    except Exception as e:
        logger.critical(f"FATAL: Failed to load the translation model. Unable to start the application, {e}", exc_info=True)
        raise RuntimeError("Failed to load the translation model.") from e
    
    yield
    logger.info("Shutting down the server")

# ==============================================================================
# 2. HELPER & CORE LOGIC FUNCTIONS (Unchanged)
# ==============================================================================

# Function to extract vector text and its coordinates from PDF
def extract_text_with_location(doc):
    # ... (same as your original code)
    extracted_text_with_location = []
    for page_num in range(doc.page_count):
        page = doc[page_num]
        words = page.get_text("words")
        for word in words:
            extracted_text_with_location.append({
                "text": word[4],
                "bbox": (word[0]-3, word[1]-3, word[2]+3, word[3]+3),
                "page": page_num
            })
    return extracted_text_with_location


# Function to filter out the Chinese Text
def filter_chinese_text(extracted_data):
    # ... (same as your original code)
    extracted_chinese_text_with_location = []
    for item in extracted_data:
        if is_likely_chinese(item["text"]):
            extracted_chinese_text_with_location.append(item)
    return extracted_chinese_text_with_location


# Helper function for filter_chinese_text function
def is_likely_chinese(text):
    # ... (same as your original code)
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
    return len(chinese_chars) > 0


# Function to translate Chinese text to English
def translate_chinese_to_english(chinese_text_data):
    translated_data = []
    for i, item in enumerate(chinese_text_data):
        chinese_text = item["text"]
        try:
            input_ids = tokenizer(chinese_text, return_tensors="pt").input_ids
            translated_ids = model.generate(input_ids, max_length=512)
            english_text = tokenizer.decode(translated_ids[0], skip_special_tokens=True).strip()
        except Exception as e:
            logger.error(f"Error translating '{chinese_text}'", exc_info=True)
            english_text = ""
        translated_data.append({
            "text": chinese_text,
            "bbox": item["bbox"],
            "page": item["page"],
            "english_translation": english_text
        })
    return translated_data


# Helper function to get the optimal font size for fitting translations
# def get_optimal_fontsize(rect, text, fontname="helv", max_fontsize=12):
#     text_len_at_size_1 = fitz.get_text_length(text, fontname=fontname, fontsize=1)
#     if text_len_at_size_1 == 0:
#         return max_fontsize
#     optimal_size = rect.width / text_len_at_size_1
#     return min(int(optimal_size), max_fontsize)


def get_optimal_fontsize(rect, text, fontname="helv", max_fontsize=12, line_height_factor=1.2):
    """
    Calculates the optimal font size to fit text within a rectangle,
    considering BOTH width and height.
    """
    # 1. Calculate optimal size based on width (same as before)
    width_optimal_size = max_fontsize
    text_len_at_size_1 = fitz.get_text_length(text, fontname=fontname, fontsize=1)
    if text_len_at_size_1 > 0:
        width_optimal_size = rect.width / text_len_at_size_1

    # 2. Calculate optimal size based on height
    # The rendered height of a line of text is roughly fontsize * 1.2
    height_optimal_size = rect.height / line_height_factor

    # 3. The true optimal size is the SMALLER of the two constraints
    optimal_size = min(width_optimal_size, height_optimal_size)

    # 4. Return the final size, capped by the maximum allowed font size
    return min(int(optimal_size), max_fontsize)



# NEW: Data enrichment to decide display text and build legend terms
from legends_util import refine_abbreviation  # type: ignore

def prepare_display_data(translated_data):
    """
    Enrich translated items by deciding whether to display full text or an abbreviation,
    and collect legend terms for any abbreviated entries.

    Input: translated_data (list of dicts from translate_chinese_to_english)
    Output: (enriched_translated_data, legend_terms)
    - enriched_translated_data: list with additional 'display_text' per item
    - legend_terms: dict mapping {code: full term}
    """
    legend_terms = {}
    used_codes = {}
    enriched = []

    for item in translated_data:
        english = (item.get("english_translation") or "").strip()
        display_text = english
        # Simple heuristic: abbreviate if longer than 4 words

        original_bbox = fitz.Rect(item["bbox"])
        max_fontsize_possible = get_optimal_fontsize(original_bbox, display_text)

        if max_fontsize_possible < 4:
            code = refine_abbreviation(english, used_codes)
            display_text = code
            legend_terms[code] = english
        enriched.append({**item, "display_text": display_text})

    return enriched, legend_terms


# UPDATED: Create translated document in memory using display_text field

def create_translated_doc_in_memory(doc, enriched_translated_data):
    """
    Build a translated PDF (vector-first) in memory. Instead of writing to disk, return the fitz.Document.
    Uses 'display_text' for overlayed content (may be full term or abbreviation).
    """
    output_doc = fitz.open()
    for page_num in range(doc.page_count):
        page = doc[page_num]
        output_page = output_doc.new_page(width=page.rect.width, height=page.rect.height)
        output_page.show_pdf_page(page.rect, doc, page_num)
        for item in enriched_translated_data:
            if item["page"] == page_num:
                original_bbox = fitz.Rect(item["bbox"])
                display_text = item.get("display_text", item.get("english_translation", ""))
                if display_text:
                    output_page.draw_rect(original_bbox, color=(1, 1, 1), fill=(1, 1, 1), overlay=True, )
                    best_fsize = get_optimal_fontsize(original_bbox, display_text)
                    leftover = output_page.insert_textbox(
                        original_bbox, display_text, fontsize=best_fsize, fontname="helv",
                        color=(0, 0, 0), align=fitz.TEXT_ALIGN_LEFT, overlay=True
                    )

                    print(f"display_text:{display_text}, leftover: {leftover}")
    return output_doc


# NEW: Assemble translated pages and legend pages side-by-side into a final PDF file
from legends_util import create_legend_pdf_page  # type: ignore

def assemble_final_pdf(translated_doc, legend_doc, output_path):
    """
    Assemble each translated page with a corresponding legend page on the right
    into a new, wider final PDF, and save to output_path.
    """
    final_doc = fitz.open()

    # Assume single-page legend reused for each page; size defines legend panel width
    legend_page = legend_doc[0] if legend_doc and legend_doc.page_count > 0 else None

    for i in range(translated_doc.page_count):
        t_page = translated_doc[i]
        t_rect = t_page.rect
        l_rect = legend_page.rect if legend_page else fitz.Rect(0, 0, 0, t_rect.height)
        new_width = t_rect.width + l_rect.width
        new_height = max(t_rect.height, l_rect.height)
        new_page = final_doc.new_page(width=new_width, height=new_height)

        # Stamp translated page at left
        new_page.show_pdf_page(fitz.Rect(0, 0, t_rect.width, t_rect.height), translated_doc, i)

        # Stamp legend page at right (if exists)
        if legend_page:
            new_page.show_pdf_page(
                fitz.Rect(t_rect.width, 0, t_rect.width + l_rect.width, l_rect.height), legend_doc, 0
            )

    final_doc.save(output_path)
    final_doc.close()


# ==============================================================================
# 3. BACKGROUND WORKER TASK
# ==============================================================================
def run_translation_task(job_id: str, pdf_path: str):
    """This is the long-running function that will be executed in the background."""
    try:
        logger.info(f"Job {job_id}: Starting processing for {pdf_path}")
        

        doc = fitz.open(pdf_path)
        jobs[job_id]["status"] = "extracting"
        all_text = extract_text_with_location(doc)
        chinese_text_data = filter_chinese_text(all_text)

        if not chinese_text_data:
            raise ValueError("No Chinese text found in the document.")
        
        # logger.info(f'Logging all filtered chinese text: {chinese_text_data}\n')

        jobs[job_id]["status"] = "translating"
        translated_data = translate_chinese_to_english(chinese_text_data)

        # logger.info(f'logging all translations: {translated_data}\n')
        
        # NEW: Enrich data and prepare legend terms
        enriched_data, legend_terms = prepare_display_data(translated_data)
        
        jobs[job_id]["status"] = "creating_pdf"
        output_path = pdf_path.replace(".pdf", "_translated.pdf")

        # Build translated document in memory
        translated_doc = create_translated_doc_in_memory(doc, enriched_data)

        if legend_terms:
            # Create legend doc (single page) sized to match translated page height with a reasonable width
            first_page = translated_doc[0]
            page_height = first_page.rect.height
            legend_width = max(180, first_page.rect.width * 0.35)
            legend_doc = create_legend_pdf_page(legend_terms, page_height=page_height, page_width=legend_width)
            
            # Assemble final output with legend panel
            assemble_final_pdf(translated_doc, legend_doc, output_path)
            translated_doc.close()
            legend_doc.close()
        else:
            # No legend needed; save translated_doc directly
            translated_doc.save(output_path)
            translated_doc.close()

        # Mark the job as complete and store the result path
        jobs[job_id]["status"] = "complete"
        jobs[job_id]["result_path"] = output_path
        logger.info(f"Job {job_id}: Processing complete. Result at {output_path}")
        
    except Exception as e:
        logger.error(f"Job {job_id}: Task failed.", exc_info=True)
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)
    finally:
        
        # Clean up the original uploaded temporary file
        doc.close()
        if os.path.exists(pdf_path):
            os.remove(pdf_path)

# ==============================================================================
# 4. FASTAPI APPLICATION & ENDPOINTS
# ==============================================================================
app = FastAPI(lifespan=lifespan)


# ==============================================================================
# 5. CONFIGURING CORS
# ==============================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """A simple endpoint to check if the server is up and running."""
    return {"status": "ready"}



@app.post("/start-translation/")
async def start_translation(background_tasks: BackgroundTasks, file: UploadFile = File(...)):

    logger.info('Starting translation...')
    """Endpoint to start the translation job."""
    job_id = str(uuid.uuid4())
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(await file.read())
        pdf_path = tmp_file.name

    logger.info('Completed temporarily opening the file...')

    jobs[job_id] = {"status": "starting", "result_path": None, "error": None}
    logger.info(f"Job {job_id}: Created and saved file to {pdf_path}")
    
    background_tasks.add_task(run_translation_task, job_id, pdf_path)
    
    return {"job_id": job_id}


@app.get("/job-status/{job_id}")
async def get_job_status(job_id: str):
    """Endpoint to check the status of a job."""
    job = jobs.get(job_id)
    if job is None:
        return JSONResponse(status_code=404, content={"status": "error", "error": "Job not found"})
    logger.info(f"Job {job_id}: Status check requested. Current status: {job['status']}")
    return {"job_id": job_id, "status": job["status"], "error": job.get("error")}


@app.get("/download/{job_id}")
async def download_result(job_id: str):
    """Endpoint to download the final translated PDF."""
    job = jobs.get(job_id)
    if job is None or job["status"] != "complete":
        return JSONResponse(status_code=404, content={"error": "File not ready or job not found"})
    
    file_path = job["result_path"]
    filename = os.path.basename(file_path)
    
    logger.info(f"Job {job_id}: Download requested for {file_path}")
    return FileResponse(file_path, media_type='application/pdf', filename=filename)