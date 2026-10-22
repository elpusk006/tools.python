@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

echo ======================================================================
echo  match_dfile_ofile Windows 독립 실행파일 (.exe) 빌드 스크립트
echo ======================================================================

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

echo [1/3] PyInstaller 확인 중...
where pyinstaller >nul 2>nul
if %errorlevel% neq 0 (
    echo PyInstaller가 설치되어 있지 않습니다. 설치를 진행합니다...
    python -m pip install --upgrade pyinstaller
    if %errorlevel% neq 0 (
        echo 오류: PyInstaller 설치에 실패했습니다. Python 환경을 확인해주세요.
        pause
        exit /b 1
    )
)

echo [2/3] PyInstaller로 Windows 실행파일(.exe) 패키징 중...
set DIST_DIR=%SCRIPT_DIR%dist\windows
set BUILD_DIR=%SCRIPT_DIR%build\windows

pyinstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --windowed ^
    --name match_dfile_ofile ^
    --distpath "%DIST_DIR%" ^
    --workpath "%BUILD_DIR%" ^
    "%SCRIPT_DIR%match_dfile_ofile.py"

if %errorlevel% neq 0 (
    echo.
    echo 오류: 빌드 중 문제가 발생했습니다.
    pause
    exit /b %errorlevel%
)

echo.
echo ======================================================================
echo [3/3] 빌드 완료!
echo 생성된 실행파일: %DIST_DIR%\match_dfile_ofile.exe
echo ======================================================================
pause
