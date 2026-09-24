# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Windows builds.
# Run on Windows:  pyinstaller build_windows.spec

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config.json', '.'),
        ('assets/quirkcode.png', 'assets'),
        ('assets/quirkcode_256.png', 'assets'),
        ('assets/quirkcode.ico', 'assets'),
    ],
    hiddenimports=[
        'pyautogui',
        'pyscreeze',
        'mouseinfo',
        'pygetwindow',
        'pymsgbox',
        'pytweening',
        'win32gui',
        'win32con',
        'win32api',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='QuirkCode',
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
    icon='assets/quirkcode.ico',
)
