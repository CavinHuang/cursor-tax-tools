# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['tariff_gui.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates/batch_rate_template.xlsx', 'templates'),  # 包含模板文件
        ('tariffs.db', '.'),  # 包含数据库文件
    ],
    hiddenimports=[
        'pandas',
        'numpy',
        'openpyxl',
        'python-Levenshtein',
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
    name='英国海关编码税率查询工具',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app.ico',  # 应用图标
)