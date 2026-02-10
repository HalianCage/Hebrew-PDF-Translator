# backend/ocr/ocr_engine.py

from ppocrv5_onnx.engine import Detector, Recognizer
from ppocrv5_onnx.utils import load_config

class OCREngine:
    def __init__(self):
        cfg = load_config()
        self.detector = Detector(cfg)
        self.recognizer = Recognizer(cfg)

    def run(self, image_path):
        from .engine import run_ocr
        return run_ocr(
            image_path,
            det=True,
            rec=True,
            detector=self.detector,
            recognizer=self.recognizer
        )
