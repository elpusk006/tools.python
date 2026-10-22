# 원본 파일 찾는 python 프로그램

## 심볼 정의

- dsrc : 배포 파일이 존재하는 directory 의 위치
- fsrc : dsrc 및 그 하위 directoy 에서 찾을 배포 파일명의 형식.(예 :  *.bin 이면 확장자가 bin 인 파일)
- ddst : 원본 파일이 존재하는 directory 의 위치
- fdst : ddst 및 그 하위 directoy 에서 찾을 원본 파일명의 형식.(예 :  *.bin 이면 확장자가 bin 인 파일)


## 주요 기능

1. **경로 및 패턴 설정**: 배포 디렉토리/형식(dsrc, fsrc) 및 원본 디렉토리/형식(ddst, fdst) 지정
2. **멀티스레딩 비동기 처리 및 UI 응답성 유지**:
   - 대용량 파일 및 수만 개의 파일 탐색/해시 계산 시에도 백그라운드 워커 스레드(`threading.Thread`)와 메시지 큐(`queue.Queue`)를 통해 동작
   - 작업 중 창 멈춤(Windows "응답 없음" 프리징) 현상 완전 차단 및 부드러운 탭 전환/창 크기 조절/이동 지원
   - **진행 표시줄(Progress Bar)**: 작업 진행 상태를 시각적으로 확인
   - **작업 중단(■ 작업 중단)**: 잘못된 경로를 선택했거나 작업 중단이 필요할 때 언제든 안전하게 즉시 중지 가능
3. **독립된 3개의 결과 리스트 (Treeview 탭)**:
   - **배포 파일 결과**: 검색된 배포 파일 목록 (번호, 파일명, 확장자, 크기, SHA-1, 디렉토리 위치, 전체 경로)
   - **원본 파일 결과**: 검색된 원본 파일 목록 (번호, 파일명, 확장자, 크기, SHA-1, 디렉토리 위치, 전체 경로)
   - **매칭 결과**: SHA-1 해시가 일치하는 파일 목록
     - **1:1 매칭**: 배포 파일과 원본 파일이 1:1로 일치하는 경우 단일 행으로 직관적 표시
     - **1:N 다수 매칭 (Treeview 계층 표시)**: 하나의 배포 파일에 여러 개의 원본 파일이 일치하는 경우, 배포 파일을 부모 노드로 두고 하위에 일치하는 원본 파일들을 자식 노드 트리로 계층 표시
     - 하단의 `[모두 펼치기]`, `[모두 접기]` 버튼으로 다수 매칭 노드를 한 번에 제어 가능
4. **편의 기능**:
   - 목록 컬럼 헤더 클릭 시 오름차순/내림차순 정렬 지원 (트리 열 `#0` 포함)
   - 목록 항목 더블클릭 시 파일 탐색기에서 해당 파일 자동 선택 및 위치 열기 (자식 노드 클릭 시 해당 원본 파일 열기 지원, Windows/Linux/macOS 크로스 플랫폼 지원)
5. **CSV 파일 내보내기**:
   - 개별 리스트(배포 파일, 원본 파일, 매칭 결과) CSV 내보내기 지원
   - 매칭 결과 CSV에 `매칭 구분`(`1:1 매칭`, `1:N 매칭 (1/3)` 등) 포함
   - 모든 결과를 지정 폴더에 CSV로 일괄 저장하는 기능 지원
   - Excel 호환 UTF-8 BOM (`utf-8-sig`) 인코딩 적용 (한글 깨짐 방지)

---

## 실행 파일 (Standalone Executable)

### 1. Windows 실행 파일
- **생성 위치**: `match_dfile_ofile/dist/windows/match_dfile_ofile.exe`
- **실행 방법**: `match_dfile_ofile.exe`를 더블클릭하여 바로 실행 (Python 설치 불필요)
- **Windows에서 재빌드**:
  ```bat
  cd match_dfile_ofile
  build_windows.bat
  ```

### 2. Linux 실행 파일 생성 방법
PyInstaller는 아키텍처 및 OS에 맞춘 C 인터프리터 바이너리를 패키징하므로, Linux 실행 파일은 Linux 환경(또는 컨테이너/WSL)에서 빌드되어야 합니다. 다음 방법 중 하나를 선택할 수 있습니다:

#### 방법 A: WSL(Windows Subsystem for Linux) 사용 (추천)
- Windows 탐색기에서 `match_dfile_ofile/build_linux_wsl.bat`를 더블클릭하여 실행합니다.
- 또는 WSL 터미널에서 직접 실행:
  ```bash
  cd match_dfile_ofile
  chmod +x build_linux.sh
  ./build_linux.sh
  ```
- **출력 위치**: `match_dfile_ofile/dist/linux/match_dfile_ofile`

#### 방법 B: Docker 사용
- Docker Desktop이 실행 중인 상태에서 `match_dfile_ofile/build_docker.bat`를 더블클릭하여 실행합니다.
- **출력 위치**: `match_dfile_ofile/dist/linux/match_dfile_ofile`

#### 방법 C: 리눅스 머신 또는 서버에서 직접 빌드
- 리눅스 환경에서 다음 명령어를 실행합니다:
  ```bash
  # 필수 패키지 설치 (Ubuntu/Debian 기준)
  sudo apt update && sudo apt install -y python3 python3-pip python3-tk

  # 빌드 스크립트 실행
  cd match_dfile_ofile
  chmod +x build_linux.sh
  ./build_linux.sh
  ```

#### 방법 D: GitHub Actions 자동 빌드
- 저장소의 `.github/workflows/build.yml`을 통해 GitHub에 Push 시 Windows `.exe` 및 Linux 바이너리가 자동으로 빌드되어 GitHub Actions Artifacts에서 다운로드할 수 있습니다.
