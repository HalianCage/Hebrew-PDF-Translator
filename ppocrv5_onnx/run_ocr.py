from ppocrv5_onnx.utils import load_config
from ppocrv5_onnx.engine import Detector, run_ocr
import pytesseract
from PIL import Image
import logging

logger = logging.getLogger(__name__)



# Private helper function to convert PaddleOCR's quad coordinate detection to bboxes
def _quad_to_box(quad):
    xs = quad[:, 0]
    ys = quad[:, 1]

    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def run_ocr_on_page(img_path, page_num):
    
    # Variable to keep track of number individual strings OCR'rd on one page
    counter = 0
    # Array to hold the extracted text
    extracted_text = []

    cfg = load_config('config.yaml')
    detector = Detector(cfg)

    # Running PaddleOCR
    results = run_ocr(str(img_path), det=True, rec=False, detector=detector)

    if type(results[0]) is list:
        boxes = results[0][0]
    else:
        logger.error("unable to parse paddleocr output correctly")
        boxes = []

    # opening the image for tesseract
    img = Image.open(img_path).convert('RGB')

    # iterating over each detected text separately to improve tessseract's hebrew detection accuracy
    for quad in boxes:

        counter += 1

        bbox = _quad_to_box(quad)
        text_crop = img.crop(bbox)

        # Need to scale the bbox from pixmap to PDF coordinate for future insertion of annotations onto the output PDF
        scaling_factor = 72 / 200
        scaled_bbox = tuple(scaling_factor * coord for coord in bbox)

        # Running Tesseract on text crop
        raw_text = pytesseract.image_to_string(text_crop, lang="heb+eng", config="--psm 6").strip()

        if not raw_text:
            logger.info("No text found in crop")
            continue

        extracted_text.append({
            "text": raw_text,
            "bbox": scaled_bbox,
            "page": page_num
        })

    
    return extracted_text, counter