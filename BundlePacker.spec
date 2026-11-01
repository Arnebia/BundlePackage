# BundlePacker.spec — конфигурация PyInstaller
# Сборка: pyinstaller BundlePacker.spec --noconfirm --clean

block_cipher = None

a = Analysis(
    ['BundlePacker.py'],
    pathex=[],
    binaries=[],
    datas=[('icon.ico', '.')],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=['numpy', 'pandas', 'matplotlib', 'PIL'],
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
    name='BundlePacker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,              # без чёрного окна консоли
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='version_info.txt', # ← подхватываем сгенерированный файл
    icon='icon.ico',                  # можно указать .ico
)