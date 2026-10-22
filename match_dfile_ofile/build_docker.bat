@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

echo ======================================================================
echo  Docker를 통한 Linux 실행파일 빌드 스크립트
echo ======================================================================

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

echo [1/3] Docker 데몬 실행 여부 확인 중...
docker info >nul 2>nul
if %errorlevel% neq 0 (
    echo 오류: Docker 데몬이 실행 중이지 않습니다. Docker Desktop을 먼저 실행해주세요.
    pause
    exit /b 1
)

echo [2/3] 빌더 이미지 빌드 중...
docker build -t match-dfile-builder .
if %errorlevel% neq 0 (
    echo 오류: Docker 이미지 빌드에 실패했습니다.
    pause
    exit /b 1
)

echo [3/3] Linux 실행파일 패키징 중...
docker run --rm -v "%SCRIPT_DIR%:/src" match-dfile-builder
if %errorlevel% neq 0 (
    echo 오류: 빌드 컨테이너 실행 중 문제가 발생했습니다.
    pause
    exit /b 1
)

echo.
echo ======================================================================
echo 빌드 완료!
echo 생성된 리눅스 실행파일: dist\linux\match_dfile_ofile
echo ======================================================================
pause
