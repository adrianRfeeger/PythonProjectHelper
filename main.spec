# -*- mode: python ; coding: utf-8 -*-

block_cipher = None


# Use the PySide6 launcher
a = Analysis(
    ['launch_gui_pyside.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    # PySide6 needs these hidden imports for plugins and Qt support
    hiddenimports=[
        'PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets',
        'PySide6.QtNetwork', 'PySide6.QtPrintSupport',
        'PySide6.QtSvg', 'PySide6.QtXml',
        'PySide6.QtOpenGL', 'PySide6.QtOpenGLWidgets',
        'PySide6.QtQml', 'PySide6.QtQuick',
        'PySide6.QtQuickWidgets',
        'PySide6.QtSql', 'PySide6.QtTest',
        'PySide6.QtWebEngineWidgets', 'PySide6.QtWebEngineCore',
        'PySide6.QtWebChannel', 'PySide6.QtWebSockets',
        'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets',
        'PySide6.QtPositioning', 'PySide6.QtLocation',
        'PySide6.QtTextToSpeech',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=2
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)


exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ProjectHelper',
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
    name='ProjectHelper'
)

app = BUNDLE(
    coll,
    name='ProjectHelper.app',
    icon=None,
    bundle_identifier='com.projecthelper',
    info_plist={
        'CFBundleName': 'ProjectHelper',
        'CFBundleDisplayName': 'ProjectHelper',
        'CFBundleGetInfoString': 'ProjectHelper',
        'CFBundleIdentifier': 'com.projecthelper',
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
