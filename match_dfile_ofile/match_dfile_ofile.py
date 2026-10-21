import hashlib
import fnmatch
import os

def calculate_sha1(file_path):
    """파일의 SHA-1 해시 값을 계산합니다. (대용량 파일 고려)"""
    sha1 = hashlib.sha1()
    try:
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                sha1.update(chunk)
        return sha1.hexdigest()
    except (PermissionError, FileNotFoundError):
        return None

def find_files(directory, pattern):
    """지정된 디렉토리 및 하위 디렉토리에서 패턴과 일치하는 파일을 찾습니다."""
    matched_files = []
    for root, dirs, files in os.walk(directory):
        for filename in fnmatch.filter(files, pattern):
            full_path = os.path.join(root, filename)
            name, ext = os.path.splitext(filename)
            matched_files.append({
                'full_path': full_path,
                'path': root,
                'name': name,
                'ext': ext
            })
    return matched_files

def process_directory_files(directory, pattern, dir_label):
    """디렉토리 내 파일을 찾고, SHA-1을 계산하여 정보를 출력 및 반환합니다."""
    print(f"\n--- [{dir_label}] 파일 검색 및 해시 계산 시작 ---")
    files_info = find_files(directory, pattern)
    
    valid_files = []
    for f in files_info:
        sha1_val = calculate_sha1(f['full_path'])
        if sha1_val:
            f['sha1'] = sha1_val
            valid_files.append(f)
            print(f"위치: {f['path']}")
            print(f"파일명: {f['name']}{f['ext']} (이름: {f['name']}, 확장자: {f['ext']})")
            print(f"SHA-1: {sha1_val}")
            print("-" * 50)
            
    return valid_files

def main():
    # 1 ~ 4. 사용자 입력 받기 (2번 항목은 문맥상 fsrc로 판단하여 처리했습니다)
    dsrc = input("1. 배포 파일 디렉토리 위치(dsrc) 입력: ").strip()
    fsrc = input("2. 배포 파일명 형식(fsrc, 예: *.bin) 입력: ").strip()
    ddst = input("3. 원본 파일 디렉토리 위치(ddst) 입력: ").strip()
    fdst = input("4. 원본 파일명 형식(fdst, 예: *.bin) 입력: ").strip()

    # 5 ~ 7. 배포 파일 처리
    src_files = process_directory_files(dsrc, fsrc, "배포(src)")

    # 8 ~ 10. 원본 파일 처리
    dst_files = process_directory_files(ddst, fdst, "원본(dst)")

    # 11. SHA-1 매칭 및 결과 표시
    print("\n" + "=" * 20 + " SHA-1 매칭 결과 " + "=" * 20)
    
    # 빠른 비교를 위해 원본 파일을 SHA-1 기준으로 그룹화
    dst_dict = {}
    for dst in dst_files:
        dst_dict.setdefault(dst['sha1'], []).append(dst['full_path'])

    match_count = 0
    for src in src_files:
        sha1 = src['sha1']
        if sha1 in dst_dict:
            for matched_dst_path in dst_dict[sha1]:
                match_count += 1
                print(f"[{match_count}] 동일 파일 발견 (SHA-1: {sha1})")
                print(f"  - 배포본 위치: {src['full_path']}")
                print(f"  - 원본 위치  : {matched_dst_path}")
                print("-" * 50)

    if match_count == 0:
        print("SHA-1 해시 값이 일치하는 파일을 찾지 못했습니다.")

if __name__ == "__main__":
    main()
