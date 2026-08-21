@echo off
REM Stereo Olcum Kiti baslatici.
REM Python PATH'te degilse asagidaki satiri kendi yolunla degistir.
set PY=python
where %PY% >nul 2>nul || set PY=py
%PY% "%~dp0stereo_kit.py"
if errorlevel 1 pause
