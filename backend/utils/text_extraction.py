# ==============================================================================
# TEXT EXTRACTION FUNCTIONS
# ==============================================================================
import re
import pdfplumber
import io
import logging
import tempfile
from pathlib import Path
import fitz
from ppocrv5_onnx.run_ocr import run_ocr_on_page

logger = logging.getLogger(__name__)


# ==============================================================================
# FUNCTION TO EXTRACT ALL TEXT FROM THE DOC
# ==============================================================================
'''
The extract_text_with_location function has been kept separate from the OCR function even though it does nothing other than simply just call the OCR function and pass on its output ahead, is to allow easy support into integrating methods other than OCR for text extraction, which could be integrated here and the final output created from the combination of them.
'''
# def extract_text_with_location(pdf_path):

#     # print("inside extract_text_with_location function...")

#     extracted_text_with_location = _process_hebrew_lines_ocr(pdf_path)

#     logger.info("OCR process is complete; Moving ahead...")


#     return extracted_text_with_location



# ==============================================================================
# FUNCTION TO EXTRACT TEXT USING OCR
# ==============================================================================
def extract_text_with_location(doc):
    logger.info(f"Processing pdf inside the extract_text_with_location function...")

    # Variables initialized
    extracted_text_with_location = []
    pdf_text_count = 0

    # Creating a temporary directory to store the PDF page images created using pixmap function
    with tempfile.TemporaryDirectory() as tempdir:
        tempdir = Path(tempdir)

        for page_num in range(doc.page_count):
            
            logger.info("Inside image loop, creating temp image for page No.:", page_num)

            page = doc[page_num]

            page_image = page.get_pixmap(dpi=200, alpha=False) # type: ignore[attr-defined]

            img_path = tempdir / f'page_{page_num}.png'
            page_image.save(img_path)

            logger.info("image saved successfully. Running Paddle OCR...")

            ocr_output = run_ocr_on_page(img_path, page_num)

            logger.info(f"Paddle + Tesseract Frankenstein successful for page No. {page_num}! No. of text boxes detected: {ocr_output[1]}")

            pdf_text_count += ocr_output[1]

            extracted_text_with_location.extend(ocr_output[0])

    return extracted_text_with_location


# ==============================================================================
# FUNCTION TO FILTER OUT THE HEBREW TEXT FROM ALL EXTRACTED TEXT
# ==============================================================================
def filter_hebrew_text(extracted_data):
    
    extracted_text_with_location = []
    for item in extracted_data:
        if _is_likely_hebrew(item["text"]):
            extracted_text_with_location.append(item)
    return extracted_text_with_location



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