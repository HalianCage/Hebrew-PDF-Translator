# startup.py
import os
import sys
from pathlib import Path
import pytesseract

def get_onefile_base() -> Path | None:
    """Return extraction base for onefile or None if not frozen."""
    return Path(sys._MEIPASS) if getattr(sys, "_MEIPASS", None) else None

def configure_bundled_binaries_onefile():
    base = get_onefile_base()
    if base is None:
        # Run from project root in case of dev env
        base = Path(__file__).resolve().parent

    # Where PyInstaller extracted your bundled files
    poppler_bin = base / "poppler_bin"
    tesseract_dir = base / "tesseract"
    tessdata_dir = tesseract_dir / "tessdata"

    print("Onefile extraction base:", base)
    print("poppler_bin candidate:", poppler_bin)
    print("tesseract_dir candidate:", tesseract_dir)

    # Windows: add DLL search directories so the OS can load native libs
    if os.name == "nt":
        try:
            if poppler_bin.exists():
                os.add_dll_directory(str(poppler_bin))
                print("Added poppler_bin to DLL search path")
            if tesseract_dir.exists():
                os.add_dll_directory(str(tesseract_dir))
                print("Added tesseract_dir to DLL search path")
        except Exception as e:
            print("Warning: os.add_dll_directory failed:", e)

    # point pytesseract to bundled exe
    tesseract_exe = tesseract_dir / "tesseract.exe"
    if not tesseract_exe.exists():
        tesseract_exe = tesseract_dir / "bin" / "tesseract.exe"
    if tesseract_exe.exists():
        pytesseract.pytesseract.tesseract_cmd = str(tesseract_exe)
        print("Using bundled tesseract:", pytesseract.pytesseract.tesseract_cmd)
    else:
        print("Bundled tesseract.exe not found — will rely on system tesseract if present")

    # set tessdata prefix so languages load
    if tessdata_dir.exists():
        os.environ["TESSDATA_PREFIX"] = str(tessdata_dir) + os.sep
        print("Set TESSDATA_PREFIX =", os.environ["TESSDATA_PREFIX"])
    else:
        print("Bundled tessdata not found")

    # return poppler path for pdf2image
    return str(poppler_bin) if poppler_bin.exists() else None

# run at import
POPPLER_PATH = configure_bundled_binaries_onefile()
