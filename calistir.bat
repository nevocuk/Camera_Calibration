@echo off
REM ============================================================
REM  Stereo Kamera Projesi — baslatici
REM
REM  conda 'stereo' ortamindaki python ile calistirir.
REM  PATH'teki 'python' base ortami gosterdigi icin (cv2 yok)
REM  bu dosya olmadan "No module named 'cv2'" hatasi alinir.
REM
REM  Kullanim:
REM    calistir.bat                -> camera_test.py (ana uygulama)
REM    calistir.bat depth_view     -> src\depth_view.py
REM    calistir.bat measurement    -> src\measurement.py
REM    calistir.bat odak_test      -> src\odak_test.py
REM    calistir.bat box_output --en 250 --boy 180 --yukseklik 120
REM ============================================================

setlocal
set PY=C:\Users\nvflb\miniconda3\envs\stereo\python.exe
cd /d "%~dp0"

if not exist "%PY%" (
    echo.
    echo HATA: stereo ortami bulunamadi:
    echo   %PY%
    echo.
    echo Ortam tasindiysa bu dosyadaki PY satirini guncelle.
    echo.
    pause
    exit /b 1
)

if "%~1"=="" (
    set SCRIPT=src\camera_test.py
    echo Baslatiliyor: camera_test.py  ^(stereo ortami^)
    "%PY%" src\camera_test.py
) else (
    echo Baslatiliyor: src\%~1.py  ^(stereo ortami^)
    "%PY%" "src\%~1.py" %2 %3 %4 %5 %6 %7 %8 %9
)

if errorlevel 1 (
    echo.
    echo Program hata ile kapandi. Yukaridaki mesaji oku.
    pause
)
endlocal
