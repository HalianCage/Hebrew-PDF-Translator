# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['run_app.py'],
    pathex=[],
    binaries=[],
    datas=[('trained_helsinki', 'trained_helsinki')],
    hiddenimports=[
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

    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Chinese_PDF_Translator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['D:\Personal Projects\CAD-Translation-Tool\PDF-Translation-App-Icon.ico']
)
