# -*- mode: python ; coding: utf-8 -*-

import os


def collect_tree(src, dest):
    items = []
    if not os.path.isdir(src):
        return items
    for root, _dirs, files in os.walk(src):
        rel_root = os.path.relpath(root, src)
        target = dest if rel_root == "." else os.path.join(dest, rel_root)
        for filename in files:
            items.append((os.path.join(root, filename), target))
    return items


tesseract_files = collect_tree('tesseract', 'tesseract')
asset_files = collect_tree('assets', 'assets')


a = Analysis(
    ['EMS_Screen.py'],
    pathex=[],
    binaries=[],
    datas=tesseract_files + asset_files,
    hiddenimports=[],
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
    name='EMS_Screen',
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
)
