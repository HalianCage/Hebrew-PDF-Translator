# ==============================================================================
# TEXT EXTRACTION FUNCTIONS
# ==============================================================================

from startup import POPPLER_PATH
import re
import io
import logging
from collections import defaultdict

import pdfplumber
from pdf2image import convert_from_path
from PIL import ImageFont, ImageDraw
import pytesseract
from pytesseract import Output
import numpy as np
import cv2
import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

# ==============================================================================
# UNIFIED TEXT EXTRACTION: OCR + VECTOR
# ==============================================================================

def extract_text_with_location(pdf_path):
    """
    Final unified extractor:
      1) OCR-based lines (from rendered pages, scaled back to PDF coords)
      2) Vector-based lines (native PDF text via PyMuPDF)
      3) Merge them with overlap-based matching:
         - If both OCR + vector overlap sufficiently -> keep VECTOR text,
           store OCR text as 'ocr_alternative'.
         - If only OCR -> keep as source='ocr'
         - If only vector -> keep as source='vector'

    Returned entries are dicts like:
      {
         "text": "...",
         "bbox": (x1, y1, x2, y2),  # PDF coordinates
         "page": page_index,
         "source": "ocr" / "vector",
         "ocr_alternative": "...",  # only when matched
      }
    """

    # 1) OCR text (already scaled to PDF coords inside helper)
    ocr_data = _process_hebrew_lines_ocr(pdf_path) or []
    logger.info(f"OCR extracted {len(ocr_data)} items")

    # 2) Vector text
    vector_data = _extract_vector_lines(pdf_path) or []
    logger.info(f"Vector text extracted {len(vector_data)} items")

    # 3) Merge both
    merged = _merge_ocr_and_vector(ocr_data, vector_data, overlap_threshold=0.4)
    logger.info(f"Merged OCR + vector items: {len(merged)}")

    return merged


# ==============================================================================
# OCR-BASED TEXT EXTRACTION (LINES)
# ==============================================================================

def _process_hebrew_lines_ocr(pdf_path):
    extracted_text_with_location = []

    # Hebrew + English OCR config
    custom_config = '--oem 3 --psm 11 -l heb+eng'

    try:
        images = convert_from_path(pdf_path, dpi=300, poppler_path=POPPLER_PATH)
    except Exception as e:
        logger.error(f"Error converting PDF to images: {e}")
        return []

    for page_num, page_image in enumerate(images):
        logger.info(f"\n--- OCR Page {page_num + 1} ---")
        img_np = np.array(page_image)

        try:
            data = pytesseract.image_to_data(
                img_np,
                output_type=Output.DICT,
                config=custom_config
            )
        except Exception as e:
            logger.error(f"Failed to perform OCR on page {page_num}: {e}")
            continue

        # Group words into lines
        lines = {}  # (block_num, par_num, line_num) -> agg

        n_boxes = len(data['text'])
        for k in range(n_boxes):
            # Filter low confidence
            try:
                conf = int(data['conf'][k])
            except ValueError:
                conf = 0

            if conf < 40:
                continue

            text = data['text'][k].strip()
            if not text:
                continue

            line_key = (
                data['block_num'][k],
                data['par_num'][k],
                data['line_num'][k],
            )

            x = data['left'][k]
            y = data['top'][k]
            w = data['width'][k]
            h = data['height'][k]

            if line_key not in lines:
                lines[line_key] = {
                    "text": [text],
                    "x_min": x,
                    "y_min": y,
                    "x_max": x + w,
                    "y_max": y + h,
                }
            else:
                ln = lines[line_key]
                ln["text"].append(text)
                ln["x_min"] = min(ln["x_min"], x)
                ln["y_min"] = min(ln["y_min"], y)
                ln["x_max"] = max(ln["x_max"], x + w)
                ln["y_max"] = max(ln["y_max"], y + h)

        # Sort lines for stable ordering
        sorted_lines = sorted(
            lines.values(),
            key=lambda v: (v['y_min'], v['x_min'])
        )

        # Scale pixels -> PDF points (300 dpi -> 72 points/inch)
        scale = 72 / 300.0

        for ln in sorted_lines:
            joined_text = " ".join(ln['text'])
            x1 = ln['x_min'] * scale
            y1 = ln['y_min'] * scale
            x2 = ln['x_max'] * scale
            y2 = ln['y_max'] * scale

            extracted_text_with_location.append({
                "text": joined_text,
                "bbox": (x1, y1, x2, y2),
                "page": page_num,
                "source": "ocr",
            })

    return extracted_text_with_location


# ==============================================================================
# VECTOR TEXT EXTRACTION (LINES) USING PYMuPDF
# ==============================================================================

def _extract_vector_lines(pdf_path):
    """
    Extract vector-based text lines using fitz (PyMuPDF).
    Groups words by (block_no, line_no) to form line-level bboxes in PDF coords.
    """
    vector_lines = []

    doc = fitz.open(pdf_path)
    for page_index, page in enumerate(doc):
        words = page.get_text("words")  # [x0, y0, x1, y1, text, block_no, line_no, word_no]
        lines_dict = {}

        for w in words:
            x0, y0, x1, y1, txt, block_no, line_no, word_no = w
            txt = txt.strip()
            if not txt:
                continue

            key = (block_no, line_no)

            if key not in lines_dict:
                lines_dict[key] = {
                    "texts": [txt],
                    "x_min": x0,
                    "y_min": y0,
                    "x_max": x1,
                    "y_max": y1,
                }
            else:
                ld = lines_dict[key]
                ld["texts"].append(txt)
                ld["x_min"] = min(ld["x_min"], x0)
                ld["y_min"] = min(ld["y_min"], y0)
                ld["x_max"] = max(ld["x_max"], x1)
                ld["y_max"] = max(ld["y_max"], y1)

        for ld in lines_dict.values():
            full_text = " ".join(ld["texts"])
            bbox = (ld["x_min"], ld["y_min"], ld["x_max"], ld["y_max"])
            vector_lines.append({
                "text": full_text,
                "bbox": bbox,
                "page": page_index,
                "source": "vector",
            })

    return vector_lines


# ==============================================================================
# GEOMETRIC OVERLAP HELPER (PDF COORDS)
# ==============================================================================

def overlap_over_min(boxA, boxB):
    """
    Overlap area divided by the smaller box area.
    Both boxes are in PDF coordinates: (x_min, y_min, x_max, y_max).
    """
    ax0, ay0, ax1, ay1 = boxA
    bx0, by0, bx1, by1 = boxB

    xA = max(ax0, bx0)
    yA = max(ay0, by0)
    xB = min(ax1, bx1)
    yB = min(ay1, by1)

    interW = max(0, xB - xA)
    interH = max(0, yB - yA)
    interArea = interW * interH
    if interArea <= 0:
        return 0.0

    areaA = max(1.0, (ax1 - ax0) * (ay1 - ay0))
    areaB = max(1.0, (bx1 - bx0) * (by1 - by0))

    return interArea / min(areaA, areaB)


# ==============================================================================
# MERGE OCR + VECTOR INTO FINAL LIST
# ==============================================================================

def _merge_ocr_and_vector(ocr_data, vector_data, overlap_threshold=0.4):
    """
    Merge OCR and vector text per page using overlap_over_min.

    Rules:
      - If a vector line and OCR line on the same page overlap >= threshold:
          -> Keep ONE entry with vector text (source='vector'),
             and store OCR text in 'ocr_alternative'.
      - If vector-only region: keep as source='vector'
      - If OCR-only region: keep as source='ocr'
    """

    ocr_by_page = defaultdict(list)
    vec_by_page = defaultdict(list)

    for item in ocr_data:
        ocr_by_page[item["page"]].append(item)

    for item in vector_data:
        vec_by_page[item["page"]].append(item)

    all_pages = sorted(set(list(ocr_by_page.keys()) + list(vec_by_page.keys())))
    merged = []

    for page in all_pages:
        o_lines = ocr_by_page.get(page, [])
        v_lines = vec_by_page.get(page, [])

        o_used = [False] * len(o_lines)

        # First handle vector lines (matched + vector-only)
        for v in v_lines:
            vbox = v["bbox"]
            best_idx = -1
            best_overlap = 0.0

            for j, o in enumerate(o_lines):
                ov = overlap_over_min(vbox, o["bbox"])
                if ov > best_overlap:
                    best_overlap = ov
                    best_idx = j

            if best_idx != -1 and best_overlap >= overlap_threshold:
                # Matched region: prefer vector text, keep OCR as alternative
                o_used[best_idx] = True
                merged.append({
                    "text": v["text"],
                    "bbox": v["bbox"],
                    "page": page,
                    "source": "vector",
                    "ocr_alternative": o_lines[best_idx]["text"],
                })
            else:
                # Vector-only
                merged.append({
                    "text": v["text"],
                    "bbox": v["bbox"],
                    "page": page,
                    "source": "vector",
                })

        # Now add OCR-only lines
        for j, o in enumerate(o_lines):
            if not o_used[j]:
                merged.append({
                    "text": o["text"],
                    "bbox": o["bbox"],
                    "page": page,
                    "source": "ocr",
                })

    return merged


# ==============================================================================
# FILTER OUT THE HEBREW TEXT FROM ALL EXTRACTED TEXT
# ==============================================================================

def filter_hebrew_text(extracted_data):
    """
    From the combined OCR+vector extracted data, keep only entries
    that contain Hebrew characters.
    """
    extracted_hebrew_text_with_location = []
    for item in extracted_data:
        if _is_likely_hebrew(item["text"]):
            extracted_hebrew_text_with_location.append(item)
    return extracted_hebrew_text_with_location


# ==============================================================================
# PRIVATE FUNCTION TO CHECK IF A TEXT IS HEBREW OR NOT
# ==============================================================================

def _is_likely_hebrew(text):
    """Checks if a string contains any Hebrew characters."""
    # The Unicode range for the Hebrew block is \u0590 to \u05FF
    hebrew_chars = re.findall(r'[\u0590-\u05FF]', text)
    return len(hebrew_chars) > 0


# ==============================================================================
# FUNCTION TO EXTRACT ALL TABLE CELL TEXT FROM THE PDF
# ==============================================================================
def extract_table_cells(pdf_bytes, x1, y1, x2, y2):
    extracted_cells = []

    # Open the PDF from bytes
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page_num, page in enumerate(pdf.pages):

            cropped_page = page.crop((x1, y1, x2, y2))

            tables = cropped_page.find_tables()
            for table in tables:
                for row in table.rows:
                    for cell_bbox in row.cells:
                        if not cell_bbox:
                            continue

                        cell_crop = page.crop(cell_bbox)
                        text = cell_crop.extract_text(x_tolerance=2)

                        if text:
                            extracted_cells.append({
                                "text": text.strip(),
                                "bbox": (cell_bbox[0] + 2,
                                         cell_bbox[1] + 2,
                                         cell_bbox[2] - 2,
                                         cell_bbox[3] - 2),
                                "page": page_num  # pdfplumber pages are 0-indexed
                            })
    return extracted_cells


# ==============================================================================
# FILTER OUT DOUBLY EXTRACTED TEXTS AND CREATE THE FINAL EXTRACTED TEXT LIST
# ==============================================================================
def final_extracted_text_list(table_text, all_text):
    # 3. Create a lookup for all table cell bboxes by page
    table_bboxes_by_page = {}

    for cell in table_text:
        page_num = cell["page"]
        if page_num not in table_bboxes_by_page:
            table_bboxes_by_page[page_num] = []
        table_bboxes_by_page[page_num].append(cell["bbox"])

    # 4. Filter the 'all_text' list
    final_text_list = []
    for word in all_text:
        page_num = word["page"]
        word_bbox = word["bbox"]

        # Check if this word is inside ANY table cell on its page
        is_in_table = False
        if page_num in table_bboxes_by_page:
            for table_cell_bbox in table_bboxes_by_page[page_num]:
                if _is_bbox_inside(word_bbox, table_cell_bbox):
                    is_in_table = True
                    break

        # 5. If the word is NOT in a table, add it to our final list
        if not is_in_table:
            final_text_list.append(word)

    # 6. Finally, add the combined table cell data
    final_text_list.extend(table_text)

    return final_text_list


# ==============================================================================
# PRIVATE FUNCTION TO CHECK IF AN EXTRACTED TEXT IS FROM TABLE TEXT
# ==============================================================================
def _is_bbox_inside(inner_bbox, outer_bbox):
    i_x0, i_y0, i_x1, i_y1 = inner_bbox
    o_x0, o_y0, o_x1, o_y1 = outer_bbox

    # A small tolerance helps with minor coordinate differences
    tol = 0.1

    return (
        i_x0 >= o_x0 - tol and
        i_y0 >= o_y0 - tol and
        i_x1 <= o_x1 + tol and
        i_y1 <= o_y1 + tol
    )
