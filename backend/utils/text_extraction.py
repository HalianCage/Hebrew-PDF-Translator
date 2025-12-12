# ==============================================================================
# TEXT EXTRACTION FUNCTIONS
# ==============================================================================

from startup import POPPLER_PATH
import re
import os
import pdfplumber
import io
import logging
from pdf2image import convert_from_path
from PIL import ImageFont, ImageDraw
import pytesseract
from pytesseract import Output
import numpy as np
import cv2

logger = logging.getLogger(__name__)

# tesseract path set up for pytesseract moved to startup.py

# ==============================================================================
# FUNCTION TO EXTRACT ALL VECTOR TEXT FROM THE DOC
# ==============================================================================
'''
The extract_text_with_location function has been kept separate from the OCR function even though it does nothing other than simply just call the OCR function and pass on its output ahead, is to allow easy support into integrating methods other than OCR for text extraction, which could be integrated here and the final output created from the combination of them.
'''
def extract_text_with_location(doc):

    # print("inside extract_text_with_location function...")

    extracted_text_with_location = _process_hebrew_lines_ocr(doc)

    logger.info("OCR process is complete; Moving ahead...")

    # for page_num in range(doc.page_count):
    #     page = doc[page_num]
    #     words = page.get_text("blocks")
    #     for word in words:
    #         extracted_text_with_location.append({
    #             "text": word[4],
    #             "bbox": (word[0]-2, word[1]-2, word[2]+2, word[3]+2),
    #             "page": page_num
    #         })

    return extracted_text_with_location

'''
For Implementing OCR into the current work flow, follow the following tentative steps/points:
1. The implementation would occur in the 'extract_text_with_location' function above.
2. Pass on the current direct vector text extraction to a helper function, and add a separate similar function for text extraction using OCR.
3. Both these helper private functions will pass their outputs to the function above, which will then do the work of comparison, verification, and finalization of text list.
4. Continue the further processes as usual without any changes.
Q. Identify the issue that might arise with PDF coordinate system and image coordinate system mismatch
'''

# ==============================================================================
# FUNCTION TO EXTRACT TEXT USING OCR
# ==============================================================================

def _process_hebrew_lines_ocr(pdf_path):
    # logger.info(f"Processing: {pdf_path} inside the process_hebrew_lines function...")

    extracted_text_with_location = []

    # Configuration for Hebrew
    custom_config = '--oem 3 --psm 11 -l heb+eng'

    try:
        images = convert_from_path(pdf_path, dpi=300, poppler_path=POPPLER_PATH)
    except Exception as e:
        print(f"Error: {e}")
        return

    # Load Hebrew Font (Fall back if missing)
    # try:
    #     # NEED TO ACTUALLY INSTALL THE FONT IF REQUIRED
    #     font_path = "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"
    #     font = ImageFont.truetype(font_path, 20)
    # except:
    #     font = ImageFont.load_default()

    for page_num, page_image in enumerate(images):
        logger.info(f"\n--- Page {page_num + 1} ---")
        img_np = np.array(page_image)

        # 1. Get Raw Data
        try:
            data = pytesseract.image_to_data(img_np, output_type=Output.DICT, config=custom_config)
            # print(data["text"])
        except Exception as e:
            print(f"Failed to perform OCR on page number {page_num}; continuing to next page")
            continue
        '''
        Output data format : 
        {
            'level':    [5, 5],
            'page_num': [1, 1],
            'block_num':[1, 1],
            'par_num':  [1, 1],
            'line_num': [1, 1],
            'word_num': [1, 2],
            'left':     [34, 120],
            'top':      [50, 50],
            'width':    [60, 80],
            'height':   [20, 20],
            'conf':     [96, 92],
            'text':     ['Hello', 'World']
        }
        '''

        # 2. Group Words into Lines
        lines = {} # Key: (block_num, par_num, line_num) -> Value: {text, x, y, w, h}

        n_boxes = len(data['text'])
        for k in range(n_boxes):
            # Filter low confidence noise
            if int(data['conf'][k]) < 40: continue

            text = data['text'][k].strip()
            if not text: continue

            # Create a unique key for this specific line on the page
            # We group by Block, Paragraph, AND Line number
            line_key = (data['block_num'][k], data['par_num'][k], data['line_num'][k])

            x, y, w, h = (data['left'][k], data['top'][k], data['width'][k], data['height'][k])

            if line_key not in lines:
                # Start a new line entry
                lines[line_key] = {
                    "text": [text],
                    "x_min": x,
                    "y_min": y,
                    "x_max": x + w,
                    "y_max": y + h
                }
            else:
                # Merge into existing line
                lines[line_key]["text"].append(text)
                # Expand the bounding box to include this new word
                lines[line_key]["x_min"] = min(lines[line_key]["x_min"], x)
                lines[line_key]["y_min"] = min(lines[line_key]["y_min"], y)
                lines[line_key]["x_max"] = max(lines[line_key]["x_max"], x + w)
                lines[line_key]["y_max"] = max(lines[line_key]["y_max"], y + h)


        # 3. Convert grouped lines into the requested output format
        # Sort lines top-to-bottom then left-to-right for stable ordering
        sorted_lines = sorted(
            lines.values(),
            key=lambda v: (v['y_min'], v['x_min'])
        )

        # logger.info(f"Sorted lines data: {sorted_lines}")

        scale = 72/300 # constant to scale pixel coordinates to pdf points

        for ln in sorted_lines:
            joined_text = " ".join(ln['text'])  # keep original word order
            x1, y1, x2, y2 = ln['x_min']*scale, ln['y_min']*scale, ln['x_max']*scale, ln['y_max']*scale
            extracted_text_with_location.append({
                "text": joined_text,
                "bbox": (x1, y1, x2, y2),
                "page": page_num
            })

    
    return extracted_text_with_location



# ==============================================================================
# FUNCTION TO FILTER OUT THE HEBREW TEXT FROM ALL EXTRACTED TEXT
# ==============================================================================
def filter_hebrew_text(extracted_data):
    # ... (same as your original code)
    extracted_chinese_text_with_location = []
    for item in extracted_data:
        if _is_likely_hebrew(item["text"]):
            extracted_chinese_text_with_location.append(item)
    return extracted_chinese_text_with_location



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
                        
                        # Use the fix from Part 1
                        cell_crop = page.crop(cell_bbox)
                        text = cell_crop.extract_text(x_tolerance=2)

                        if text:
                            extracted_cells.append({
                                "text": text.strip(),
                                "bbox": (cell_bbox[0]+2, cell_bbox[1]+2, cell_bbox[2]-2, cell_bbox[3]-2),
                                "page": page_num # pdfplumber pages are 0-indexed in a list
                            })
    return extracted_cells



# ========================================================================================
# FUNCTION TO FILTER OUT DOUBLY EXTRACTED TEXTS AND CREATE THE FINAL EXTRACTED TEXT LIST
# ========================================================================================
def final_extracted_text_list(table_text, all_text):

    # 3. Create a lookup for all table cell bboxes by page
    table_bboxes_by_page = {}


    for cell in table_text:
        page_num = cell["page"]
        if page_num not in table_bboxes_by_page:
            table_bboxes_by_page[page_num] = []
        table_bboxes_by_page[page_num].append(cell["bbox"])

    # 4. Filter the 'all_words' list
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

    # 6. Finally, add the CORRECT, combined table cell data
    final_text_list.extend(table_text)

    return final_text_list




# ========================================================================================
# PRIVATE FUNCTION TO CHECK IF AN EXTRACTED TEXT IS FROM TABLE TEXT
# ========================================================================================
def _is_bbox_inside(inner_bbox, outer_bbox):

    i_x0, i_y0, i_x1, i_y1 = inner_bbox
    o_x0, o_y0, o_x1, o_y1 = outer_bbox

    # A small tolerance can help for pixel-perfect alignment
    tol = 0.1 

    return (i_x0 >= o_x0 - tol and 
            i_y0 >= o_y0 - tol and 
            i_x1 <= o_x1 + tol and 
            i_y1 <= o_y1 + tol)