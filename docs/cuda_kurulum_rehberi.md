# OpenCV CUDA Kurulum Rehberi (Windows 11 + RTX 3050 Laptop)

## Genel Bakis

OpenCV'nin pip versiyonu CUDA icermiyor. GPU hizlandirmasi icin
OpenCV'yi kaynak koddan CUDA flag'leriyle derlemek gerekiyor.

Toplam sure: ~2-3 saat (indirme + derleme)
Disk alani: ~15 GB (gecici build dosyalari dahil)

---

## EVDE YAPILACAKLAR (gece, indirmeler buyuk)

### 1. Miniconda Indir ve Kur
- Indir: https://docs.conda.io/en/latest/miniconda.html
  - "Miniconda3 Windows 64-bit" sec
  - Dosya: ~80 MB
- Kur: varsayilan ayarlarla (PATH'e ekleme secenegini **isaretle**)
- Kurulum sonrasi Anaconda Prompt'u ac, test et:
  ```
  conda --version
  ```

### 2. Conda Ortami Olustur
Anaconda Prompt'ta:
```
conda create -n stereo python=3.11 numpy -y
conda activate stereo
pip install Pillow
```

### 3. CUDA Toolkit 12.6 Indir
- Indir: https://developer.nvidia.com/cuda-12-6-0-download-archive
  - OS: Windows, Architecture: x86_64, Version: 11, Type: exe (local)
  - Dosya: ~3 GB
- Kur: "Express" secenegi ile
- Kurulum sonrasi test:
  ```
  nvcc --version
  ```
  "release 12.6" gibi cikti gelmeli

### 4. cuDNN Indir
- https://developer.nvidia.com/cudnn-downloads
  - NVIDIA hesabi gerekiyor (ucretsiz kayit)
  - cuDNN 9.x for CUDA 12 — Windows — zip
  - Dosya: ~700 MB
- Zip'i ac
- Icindeki dosyalari CUDA klasorune kopyala:
  ```
  bin\*.dll      → C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin\
  include\*.h    → C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\include\
  lib\x64\*.lib  → C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\lib\x64\
  ```

### 5. Visual Studio Build Tools Indir
- Indir: https://visualstudio.microsoft.com/visual-cpp-build-tools/
  - "Build Tools for Visual Studio 2022" sec
  - Dosya: installer ~2 MB, sonra ~4 GB indirme
- Kur: "C++ ile masaustu gelistirme" is yukunu sec
  - Icinden su bilesenleri isaretle:
    - MSVC v143 C++ build tools
    - Windows 11 SDK
    - CMake tools for Windows

### 6. CMake Indir (eger VS ile gelmediyse)
- https://cmake.org/download/
  - "Windows x64 Installer" sec
  - PATH'e ekle secenegini isaretle

### 7. OpenCV Kaynak Kodlarini Indir
Anaconda Prompt veya PowerShell'de:
```
cd %USERPROFILE%
mkdir opencv_build
cd opencv_build
git clone https://github.com/opencv/opencv.git --branch 4.10.0 --depth 1
git clone https://github.com/opencv/opencv_contrib.git --branch 4.10.0 --depth 1
```
Iki repo: ~500 MB

---

## STAJDA YAPILACAKLAR (derleme)

### 8. Build Klasoru Olustur
```
cd %USERPROFILE%\opencv_build
mkdir build
cd build
```

### 9. CMake Yapilandirmasi
Anaconda Prompt'ta (stereo ortami aktif):

```
conda activate stereo

cmake -G "Visual Studio 17 2022" -A x64 ^
  -D CMAKE_BUILD_TYPE=Release ^
  -D CMAKE_INSTALL_PREFIX=%USERPROFILE%/opencv_build/install ^
  -D OPENCV_EXTRA_MODULES_PATH=%USERPROFILE%/opencv_build/opencv_contrib/modules ^
  -D WITH_CUDA=ON ^
  -D CUDA_ARCH_BIN=8.6 ^
  -D CUDA_ARCH_PTX=8.6 ^
  -D WITH_CUDNN=ON ^
  -D OPENCV_DNN_CUDA=ON ^
  -D ENABLE_FAST_MATH=ON ^
  -D CUDA_FAST_MATH=ON ^
  -D WITH_NVCUVID=OFF ^
  -D WITH_NVCUVENC=OFF ^
  -D BUILD_opencv_python3=ON ^
  -D PYTHON3_EXECUTABLE=%CONDA_PREFIX%/python.exe ^
  -D PYTHON3_INCLUDE_DIR=%CONDA_PREFIX%/include ^
  -D PYTHON3_LIBRARY=%CONDA_PREFIX%/libs/python311.lib ^
  -D PYTHON3_NUMPY_INCLUDE_DIRS=%CONDA_PREFIX%/Lib/site-packages/numpy/core/include ^
  -D BUILD_TESTS=OFF ^
  -D BUILD_PERF_TESTS=OFF ^
  -D BUILD_EXAMPLES=OFF ^
  -D BUILD_opencv_world=ON ^
  ../opencv
```

Not: CUDA_ARCH_BIN=8.6 → RTX 3050 Laptop icin dogru deger (Ampere mimarisi)
Evdeki 4060Ti icin CUDA_ARCH_BIN=8.9 olurdu (Ada Lovelace).

CMake ciktisinda su satirlari kontrol et:
```
--   NVIDIA CUDA:                   YES (ver 12.6)
--   cuDNN:                         YES (ver 9.x)
--   Python 3:                      ...stereo/python.exe
--   CUDA_ARCH_BIN:                 8.6
```

### 10. Derleme (en uzun adim, ~1-2 saat)
```
cmake --build . --config Release --target install -j 8
```
- `-j 8` = 8 cekirdek paralel (laptop icin uygun)
- Laptop fise takili olmali (CPU %100 calisacak)
- Fan cok calismasi normal

### 11. Python'a Baglama
Derleme bitince:
```
cd %USERPROFILE%\opencv_build\install\python
pip install .
```
Veya elle kopyala:
```
copy %USERPROFILE%\opencv_build\install\python\cv2\*.pyd %CONDA_PREFIX%\Lib\site-packages\
```

### 12. Test
```python
conda activate stereo
python -c "import cv2; print(cv2.getBuildInformation())" | findstr CUDA
```
Ciktida su satirlar olmali:
```
  NVIDIA CUDA:                   YES
  NVIDIA GPU arch:               86
  cuDNN:                         YES
```

GPU stereo test:
```python
python -c "
import cv2
import numpy as np
gpu_l = cv2.cuda_GpuMat(np.zeros((1536,2048), dtype=np.uint8))
gpu_r = cv2.cuda_GpuMat(np.zeros((1536,2048), dtype=np.uint8))
sgm = cv2.cuda.createStereoSGM(0, 256)
print('CUDA StereoSGM calisiyor!')
"
```

---

## SORUN GIDERME

### "nvcc not found"
→ CUDA Toolkit PATH'e eklenmemis.
```
set PATH=%PATH%;C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin
```

### CMake "CUDA not found"
→ CUDA Toolkit kurulmamis veya yanlis versiyon.
`nvcc --version` calistir, 12.6 gelmeli.

### "cuDNN not found"
→ cuDNN dosyalari CUDA klasorune kopyalanmamis.
`C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin\cudnn64_9.dll` var mi kontrol et.

### Derleme hatasi "out of memory"
→ `-j 8` yerine `-j 4` kullan (daha az paralel islem, daha az RAM)

### "CUDA_ARCH_BIN" yanlis
→ GPU'nun compute capability'si: https://developer.nvidia.com/cuda-gpus
  - RTX 3050 Laptop = 8.6
  - RTX 4060 Ti = 8.9

---

## DERLEME SONRASI: camera_test.py Degisiklikleri

CUDA kurulduktan sonra camera_test.py'de sadece stereo kismi degisecek:

```python
# Onceki (CPU)
sgbm = cv2.StereoSGBM_create(...)
disp = sgbm.compute(gray_l, gray_r)

# Yeni (GPU)
sgm = cv2.cuda.createStereoSGM(minDisparity=0, numDisparities=256, P1=10, P2=120)
gpu_l = cv2.cuda_GpuMat(gray_l)
gpu_r = cv2.cuda_GpuMat(gray_r)
gpu_disp = sgm.compute(gpu_l, gpu_r)
disp = gpu_disp.download()
```

Geri kalan her sey (WLS, colormap, kontur, karsilastirma, kalibrasyon) ayni kalacak.
WLS filtresi CPU'da calisir ama cok hizli (~5ms), darbogaz olmaz.
