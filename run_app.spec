# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

# ---------- EDIT THIS to match your project root ----------
PROJECT_ROOT = Path(r"D:\Personal Projects\Hebrew-CAD-Translation-Tool").resolve()
# ---------------------------------------------------------

def collect_folder_as_tuples(src_folder: Path, dest_prefix: str):
    """
    Return a list of (src_abspath, dest_relpath) tuples suitable for
    adding to binaries or datas in a spec.
    dest_relpath is the folder inside sys._MEIPASS where files will be placed.
    """
    items = []
    if not src_folder.exists():
        return items
    for p in src_folder.rglob('*'):
        if p.is_file():
            # dest path inside bundle: dest_prefix + relative path under src_folder
            rel = p.relative_to(src_folder)
            dest = str(Path(dest_prefix) / rel.parent)  # directory inside bundle
            items.append((str(p), dest))
    return items

# Collect poppler_bin contents => bundle under poppler/bin/...
poppler_src = PROJECT_ROOT / "poppler_bin"
poppler_tuples = collect_folder_as_tuples(poppler_src, "poppler_bin")

# Collect tesseract folder => bundle under tesseract/...
tesseract_src = PROJECT_ROOT / "tesseract"
tesseract_tuples = collect_folder_as_tuples(tesseract_src, "tesseract")

# Collect tessdata specifically (optional — already included above but kept for clarity)
tessdata_src = PROJECT_ROOT / "tesseract" / "tessdata"
tessdata_tuples = collect_folder_as_tuples(tessdata_src, "tesseract/tessdata")

# Collect he-en-model folder => bundle under he-en-model/...
hemodel_src = PROJECT_ROOT / "he-en-model"
hemodel_tuples = collect_folder_as_tuples(hemodel_src, "he-en-model")

# Build final binaries and datas lists
# NOTE: binaries is for executables/DLLs; datas is for non-executable files.
# PyInstaller accepts both as (src, dest) tuples in the spec.
binaries = poppler_tuples + tesseract_tuples   # poppler DLLs & executables, tesseract exe/DLLs
datas = hemodel_tuples + tessdata_tuples      # model + tessdata files

# Hidden imports (keep your list)
hiddenimports = [
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.auto',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'backend.api',
    'backend.model',
    'backend.core',
    'backend.services',
    'backend.utils',
    'backend.api.translations',
    'backend.core.job_state',
    'backend.model.model',
    'backend.services.pdf_translator',
    'backend.utils.legends_util',
    'backend.utils.output_pdf_handler',
    'backend.utils.text_extraction',
    'backend.utils.translation',
    'backend.utils.zip_and_queue_handler',
]

# --- Analysis ---
a = Analysis(
    ['run_app.py'],
    pathex=[str(PROJECT_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],   # you confirmed startup.py runs first; keep empty
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='Hebrew_PDF_Translator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,   # set True while debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[str(PROJECT_ROOT / "PDF-Translation-App-Icon.ico")]
)
