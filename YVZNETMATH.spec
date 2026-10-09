# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = ['websocket', 'websocket._abnf', 'websocket._core', 'websocket._exceptions', 'websocket._handshake', 'websocket._http', 'websocket._logging', 'websocket._socket', 'websocket._ssl_compat', 'websocket._url', 'websocket._utils', 'requests']
hiddenimports += collect_submodules('websocket')


a = Analysis(
    ['yvz_gui.py'],
    pathex=[],
    binaries=[],
    datas=[('yvznetmath_core.py', '.'), ('yvztools.ico', '.')],
    hiddenimports=hiddenimports,
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
    name='YVZNETMATH',
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
    icon=['yvztools.ico'],
    version='version_info.txt',
)
