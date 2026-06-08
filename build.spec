# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

datas = []
datas += collect_data_files("customtkinter")
datas += collect_data_files("rembg")
datas += collect_data_files("onnxruntime")
datas += [("models", "models")]

# Packages that call importlib.metadata.version() at import time need their dist-info
from PyInstaller.utils.hooks import copy_metadata
datas += copy_metadata("pymatting")
datas += copy_metadata("rembg")
datas += copy_metadata("imageio")
datas += copy_metadata("scikit-image")
datas += copy_metadata("scipy")
datas += copy_metadata("numpy")
datas += copy_metadata("pooch")
datas += copy_metadata("tqdm")
datas += copy_metadata("numba")
datas += copy_metadata("onnxruntime")

hiddenimports = [
    "onnxruntime.capi._pybind_state",
    "rembg.sessions.u2net",
    "rembg.sessions.dis_general_use",
    "rembg.sessions.base",
    "PIL._imaging",
    "PIL.Image",
    "PIL.ImageFilter",
    "PIL.ImageDraw",
    "skimage",
    "scipy",
    "pooch",
    "windnd",
]

binaries = []
binaries += collect_dynamic_libs("onnxruntime")

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    [],
    exclude_binaries=True,
    name="ImageUtilityRefining",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="ImageUtilityRefining",
)
