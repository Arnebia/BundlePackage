"""
Генерирует version_info.txt для PyInstaller из APP_VERSION в BundlePacker.py.
Запускается автоматически из build.bat.
"""
import re
import pathlib
import sys

SRC = pathlib.Path(__file__).with_name("BundlePacker.py")
OUT = pathlib.Path(__file__).with_name("version_info.txt")

text = SRC.read_text(encoding="utf-8")
m = re.search(r'APP_VERSION\s*=\s*"([\d.]+)"', text)
if not m:
    sys.exit("APP_VERSION не найден в BundlePacker.py")

version_str = m.group(1)
parts = version_str.split(".")
# Windows VERSIONINFO требует ровно 4 числа
nums = [int(p) for p in parts[:4]]
while len(nums) < 4:
    nums.append(0)
v = tuple(nums)

# Первые три числа — «маркетинговая» версия, последнее — билд
display = f"{nums[0]}.{nums[1]}.{nums[2]}.{nums[3]}"

template = f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={v},
    prodvers={v},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [
          StringStruct('CompanyName', 'KoMMeK'),
          StringStruct('FileDescription', 'Сопоставление кодов маркировки'),
          StringStruct('FileVersion', '{display}'),
          StringStruct('InternalName', 'BundlePacker'),
          StringStruct('OriginalFilename', 'BundlePacker.exe'),
          StringStruct('ProductName', 'BundlePacker'),
          StringStruct('ProductVersion', '{display}'),
        ]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""

OUT.write_text(template, encoding="utf-8")
print(f"version_info.txt обновлён: {display}")