# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=['tkinter', 'tkinter.ttk'],
    hookspath=[],
    runtime_hooks=[],
    excludes=['PySide6'],
    noarchive=False,
    optimize=2
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ProjectHelperTk',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    console=False,
    icon=None
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=True,
    upx=True,
    name='ProjectHelperTk'
)

app = BUNDLE(
    coll,
    name='ProjectHelperTk.app',
    icon=None,
    bundle_identifier='com.projecthelper.tk',
    info_plist={
        'CFBundleName': 'ProjectHelperTk',
        'CFBundleDisplayName': 'ProjectHelperTk',
        'CFBundleGetInfoString': 'ProjectHelperTk',
        'CFBundleIdentifier': 'com.projecthelper.tk',
        'CFBundleVersion': '1.0.1',
        'CFBundleShortVersionString': '1.0.1',
        # macOS privacy permission prompts
        'NSDesktopFolderUsageDescription': 'ProjectHelper needs access to your Desktop folder to read and save project files.',
        'NSDocumentsFolderUsageDescription': 'ProjectHelper needs access to your Documents folder to open and store project files.',
        'NSDownloadsFolderUsageDescription': 'ProjectHelper needs access to your Downloads folder to import downloaded resources.',
        'NSPicturesFolderUsageDescription': 'ProjectHelper needs access to your Pictures folder to manage image assets.',
        'NSMoviesFolderUsageDescription': 'ProjectHelper needs access to your Movies folder to handle video assets.',
        'NSMusicFolderUsageDescription': 'ProjectHelper needs access to your Music folder to associate audio resources.',
        'NSNetworkVolumesUsageDescription': 'ProjectHelper needs access to network volumes to open and save projects stored on shared drives.',
        'NSRemovableVolumesUsageDescription': 'ProjectHelper needs access to removable drives (USB, external disks) to import and export projects.'
    }
)
