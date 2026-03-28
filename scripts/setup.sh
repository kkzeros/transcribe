#!/bin/bash
# 环境自检脚本（幂等，已安装则秒过）
# 用法：bash scripts/setup.sh

set -e

echo "[setup] 检查 Python 3..."
if ! command -v python3 &>/dev/null; then
    echo "[setup] 错误：未找到 python3，请先安装 Python 3.8 及以上版本"
    exit 1
fi
echo "[setup] $(python3 --version)"

echo "[setup] 检查 Python 依赖..."
python3 -m pip install -q yt-dlp oss2 aliyun-python-sdk-core python-dotenv requests

echo "[setup] 检查 ffmpeg..."
if ! command -v ffmpeg &>/dev/null; then
    echo "[setup] ffmpeg 未找到，尝试自动安装..."
    if command -v brew &>/dev/null; then
        brew install ffmpeg
    elif command -v apt-get &>/dev/null; then
        sudo apt-get install -y ffmpeg
    elif command -v yum &>/dev/null; then
        sudo yum install -y ffmpeg
    else
        echo "[setup] 错误：无法自动安装 ffmpeg，请手动安装：https://ffmpeg.org/download.html"
        exit 1
    fi
else
    echo "[setup] ffmpeg 已安装：$(ffmpeg -version 2>&1 | head -1)"
fi

echo "[setup] 检查 yt-dlp..."
yt-dlp --version

echo "[setup] 环境检查通过 ✓"
