# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ["Polytrack_gui_singlefile.py"],
    pathex=["."],
    binaries=[],
    datas=[],
    hiddenimports=["polytrack_encoder", "polytrack_decoder"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Polytrack",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)