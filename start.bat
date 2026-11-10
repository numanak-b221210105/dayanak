@echo off
REM Dayanak - Windows icin tek tikla kurulum ve calistirma
cd /d "%~dp0"
where python >nul 2>nul || (echo Python bulunamadi. https://www.python.org/downloads/ adresinden kurun ve "Add python.exe to PATH" kutusunu isaretleyin. & pause & exit /b 1)
if not exist .venv\Scripts\python.exe (
  echo [1/2] Sanal ortam olusturuluyor...
  python -m venv .venv || goto :error
)
if not exist .venv\Lib\site-packages\dayanak-*.dist-info (
  echo [2/2] Paketler yukleniyor, bu bir kac dakika surebilir...
  .venv\Scripts\python -m pip install -q --upgrade pip
  .venv\Scripts\python -m pip install -q -e ".[dev]" || goto :error
)
if not exist .env copy .env.example .env >nul
.venv\Scripts\python -m dayanak.serve %*
if errorlevel 1 goto :error
exit /b 0

:error
echo.
echo Bir hata olustu. Yukaridaki mesaji kopyalayip paylasin.
pause
exit /b 1
