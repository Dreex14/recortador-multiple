@echo off
REM Genera dist\RecortadorMultiple.exe
cd /d "%~dp0"
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name RecortadorMultiple ^
  --icon assets\icono.ico ^
  --add-data "assets\icono.ico;assets" ^
  recortar.pyw
echo.
echo Listo: dist\RecortadorMultiple.exe
pause
