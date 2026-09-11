@echo off
REM Fabrique EnregistrementMAC.exe (un seul fichier, sans installer Python sur
REM les postes de production). A executer une fois, sur un poste Windows
REM disposant de Python 3.
cd /d "%~dp0"
py -3 -m pip install --upgrade pyinstaller || goto :echec
py -3 -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name EnregistrementMAC ^
    --collect-submodules enregistrement_mac ^
    lancer.py || goto :echec
echo.
echo Executable genere : dist\EnregistrementMAC.exe
pause
exit /b 0

:echec
echo.
echo Echec de la generation.
pause
exit /b 1
