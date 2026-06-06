#!/bin/bash
# 环境自检脚本（幂等，已安装则秒过）
# 用法：bash scripts/setup.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$SKILL_ROOT/.venv"
PYTHON_BIN="$VENV_DIR/bin/python3"
YT_DLP_BIN="$VENV_DIR/bin/yt-dlp"

echo "[setup] 检查 Python 3..."
if ! command -v python3 &>/dev/null; then
    echo "[setup] 错误：未找到 python3，请先安装 Python 3.8 及以上版本"
    exit 1
fi
echo "[setup] $(python3 --version)"

if [ ! -x "$PYTHON_BIN" ]; then
    echo "[setup] 创建 skill 虚拟环境: $VENV_DIR"
    python3 -m venv "$VENV_DIR"
fi

if ! "$PYTHON_BIN" -c 'import sys; print(sys.executable)' >/dev/null 2>&1; then
    echo "[setup] 虚拟环境不可用，重新创建: $VENV_DIR"
    rm -rf "$VENV_DIR"
    python3 -m venv "$VENV_DIR"
fi

echo "[setup] 检查 Python 依赖..."
"$PYTHON_BIN" -m pip install -q -r "$SKILL_ROOT/references/requirements.txt"

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
if [ -x "$YT_DLP_BIN" ] && ! "$YT_DLP_BIN" --version >/dev/null 2>&1; then
    echo "[setup] yt-dlp 入口不可用，重新创建虚拟环境: $VENV_DIR"
    rm -rf "$VENV_DIR"
    python3 -m venv "$VENV_DIR"
    "$PYTHON_BIN" -m pip install -q -r "$SKILL_ROOT/references/requirements.txt"
fi
"$YT_DLP_BIN" --version

echo "[setup] 环境检查通过 ✓"
