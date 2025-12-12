# ==============================================================================
# TRANSLATION TASKS FILE
# ==============================================================================


import logging
from model import model as translation_model

logger = logging.getLogger(__name__)


def translate_hebrew_to_english(hebrew_text_data):

    # logger.info(f"testing if the extracted text data reaches to translation function safely {hebrew_text_data}")

    translated_data = []
    for i, item in enumerate(hebrew_text_data):
        hebrew_text = item["text"]
        try:
            input_ids = translation_model.tokenizer(hebrew_text, return_tensors="pt").input_ids
            translated_ids = translation_model.model.generate(input_ids, max_length=512)
            english_text = translation_model.tokenizer.decode(translated_ids[0], skip_special_tokens=True).strip()
        except Exception as e:
            logger.error(f"Error translating '{hebrew_text}'", exc_info=True)
            english_text = ""
        translated_data.append({
            "text": hebrew_text,
            "bbox": item["bbox"],
            "page": item["page"],
            "english_translation": english_text
        })

        # logger.info(f"text translation: {english_text}")
    return translated_data