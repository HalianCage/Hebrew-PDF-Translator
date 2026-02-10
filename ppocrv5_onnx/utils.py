# backend/ocr/utils.py
from pathlib import Path
from omegaconf import OmegaConf

def load_config(config_name="config.yaml"):
    """
    Always load config relative to this OCR folder,
    never relative to CWD.
    """
    base_dir = Path(__file__).resolve().parent
    config_path = base_dir / config_name

    cfg = OmegaConf.load(config_path)

    cfg_dir = config_path.parent

    def resolve(p):
        if p is None:
            return None
        p = Path(p)
        return str(p if p.is_absolute() else (cfg_dir / p).resolve())

    # ---- resolve model paths ----
    cfg.engine.model.det.path = resolve(cfg.engine.model.det.path)
    cfg.engine.model.rec.path = resolve(cfg.engine.model.rec.path)
    cfg.engine.model.rec.dict_path = resolve(cfg.engine.model.rec.dict_path)

    # ---- resolve visualization paths ----
    cfg.visualize.font_path = resolve(cfg.visualize.font_path)
    cfg.visualize.save_dir = resolve(cfg.visualize.save_dir)

    return cfg
