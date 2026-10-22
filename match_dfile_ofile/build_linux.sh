#!/usr/bin/env bash
# ==============================================================================
# match_dfile_ofile Linux 독립 실행파일 빌드 스크립트
# ==============================================================================
set -e

# 스크립트가 위치한 디렉토리로 이동
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== [1/4] 환경 확인 및 필수 패키지 검사 ==="
if ! command -v python3 &> /dev/null; then
    echo "오류: python3가 설치되어 있지 않습니다."
    echo "Ubuntu/Debian의 경우 다음 명령으로 설치하세요:"
    echo "  sudo apt update && sudo apt install -y python3 python3-pip python3-tk python3-venv"
    exit 1
fi

# tkinter 설치 여부 확인
if ! python3 -c "import tkinter" &> /dev/null; then
    echo "경고: tkinter가 감지되지 않았습니다. GUI 실행을 위해 설치가 필요합니다."
    echo "Ubuntu/Debian: sudo apt update && sudo apt install -y python3-tk"
    echo "Fedora/RHEL:   sudo dnf install -y python3-tkinter"
    echo "Arch Linux:    sudo pacman -S --noconfirm tk"
fi

echo "=== [2/4] 가상환경 및 PyInstaller 준비 ==="
VENV_DIR="$SCRIPT_DIR/.build_venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "가상환경 생성 중: $VENV_DIR"
    python3 -m venv "$VENV_DIR"
fi

# 가상환경 활성화
source "$VENV_DIR/bin/activate"

# pip 최신화 및 pyinstaller 설치
python -m pip install --upgrade pip
python -m pip install pyinstaller

echo "=== [3/4] Linux 독립 실행파일 빌드 (PyInstaller) ==="
DIST_DIR="$SCRIPT_DIR/dist/linux"
BUILD_DIR="$SCRIPT_DIR/build/linux"
mkdir -p "$DIST_DIR"

pyinstaller \
    --noconfirm \
    --clean \
    --onefile \
    --windowed \
    --name match_dfile_ofile \
    --distpath "$DIST_DIR" \
    --workpath "$BUILD_DIR" \
    "$SCRIPT_DIR/match_dfile_ofile.py"

echo "=== [4/4] 실행 권한 부여 및 완료 ==="
chmod +x "$DIST_DIR/match_dfile_ofile"

echo ""
echo "======================================================================"
echo "빌드 완료!"
echo "생성된 리눅스 실행파일 위치: $DIST_DIR/match_dfile_ofile"
echo "실행 방법: $DIST_DIR/match_dfile_ofile"
echo "======================================================================"
