@echo off
chcp 65001 >nul
setlocal

REM ============================================================
REM  Сборка marking_app.exe
REM  1) обновляет version_info.txt из APP_VERSION в BundlePacker.py
REM  2) собирает .exe через PyInstaller по BundlePacker.spec
REM ============================================================

cd /d "%~dp0"

echo [1/3] Проверка Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ОШИБКА: python не найден в PATH.
    exit /b 1
)

echo [2/3] Генерация version_info.txt...
python make_version_info.py
if errorlevel 1 (
    echo ОШИБКА: make_version_info.py завершился с ошибкой.
    exit /b 1
)

echo [3/3] Сборка .exe...
pyinstaller BundlePacker.spec --noconfirm --clean
if errorlevel 1 (
    echo ОШИБКА: PyInstaller завершился с ошибкой.
    exit /b 1
)

echo.
echo Готово. Файл: dist\BundlePacker.exe
echo.
pause