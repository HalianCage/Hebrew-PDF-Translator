# ==============================================================================
# FILE TO LOAD THE ML TRANSLATION MODEL
# ==============================================================================
import os
import sys
import logging
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

logger = logging.getLogger(__name__)

# These will be loaded once at startup and reused
tokenizer = None
model = None

def load_model():
    """
    Loads the model, reliably finding the path in both development
    and packaged (PyInstaller) mode.
    """
    global tokenizer, model
    
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
        local_model_path = os.path.join(base_path, "he-en-model")
    else:
        # Path is relative to this file's location (backend/ml/)
        base_path = os.path.dirname(os.path.abspath(__file__))
        local_model_path = os.path.join(base_path, "..", "..", "he-en-model")
    
    logger.info(f"Attempting to load model from path: {local_model_path}")
    
    try:
        tokenizer = AutoTokenizer.from_pretrained(local_model_path)
        model = AutoModelForSeq2SeqLM.from_pretrained(local_model_path)

        logger.info("Model loaded successfully.")

    except Exception as e:
        logger.critical(f"FATAL: Failed to load model from {local_model_path}.", exc_info=True)
        
        raise RuntimeError("Failed to load the translation model.") from e