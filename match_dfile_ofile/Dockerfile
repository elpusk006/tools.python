FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# 필수 패키지 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-tk \
    tk-dev \
    build-essential \
    binutils \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir pyinstaller

WORKDIR /src

ENTRYPOINT ["pyinstaller", "--noconfirm", "--clean", "--onefile", "--windowed", "--name", "match_dfile_ofile", "--distpath", "/src/dist/linux", "--workpath", "/src/build/linux", "/src/match_dfile_ofile.py"]
