@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

echo ======================================================================
echo  WSL (Ubuntu) 환경을 통한 Linux 실행파일 빌드
echo ======================================================================

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

echo [1/2] WSL 실행 확인 중...
where wsl >nul 2>nul
if %errorlevel% neq 0 (
    echo 오류: WSL이 설치되어 있지 않습니다.
    echo WSL을 설치하거나 리눅스 환경에서 직접 build_linux.sh를 실행해주세요.
    pause
    exit /b 1
)

echo [2/2] WSL에서 build_linux.sh 실행 중...
wsl bash -c "cd '$(wslpath '%SCRIPT_DIR%')' && tr -d '\r' < build_linux.sh > /tmp/build_linux.sh && chmod +x /tmp/build_linux.sh && /tmp/build_linux.sh"

if %errorlevel% neq 0 (
    echo.
    echo 오류: WSL 빌드 중 문제가 발생했습니다.
    pause
    exit /b %errorlevel%
)

echo.
echo ======================================================================
echo 빌드 완료!
echo 생성된 리눅스 실행파일: dist\linux\match_dfile_ofile
echo ======================================================================
pause
