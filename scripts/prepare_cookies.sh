#!/bin/bash
# 准备在线来源 cookie。默认不自动登录，只在用户确认后从本机浏览器导出。

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="$SKILL_ROOT/.venv/bin/python3"
YT_DLP_BIN="$SKILL_ROOT/.venv/bin/yt-dlp"

VIDEO_URL="${1:-}"
BROWSER="${2:-chrome}"
COOKIE_ALIAS="${TRANSCRIBE_COOKIE_ALIAS:-}"

if [ -z "$COOKIE_ALIAS" ] && [ -n "$VIDEO_URL" ]; then
    COOKIE_ALIAS="$("$PYTHON_BIN" - "$VIDEO_URL" "$SKILL_ROOT" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[2]) / "scripts"))
from config import cookie_alias_from_url
print(cookie_alias_from_url(sys.argv[1]))
PY
)"
fi

if [ -z "$COOKIE_ALIAS" ]; then
    echo "[cookies] 无法生成来源别名，不使用默认 cookie。"
    echo "[cookies] 请设置 TRANSCRIBE_COOKIE_ALIAS 后重试，例如："
    echo "  TRANSCRIBE_COOKIE_ALIAS=source-a bash \"$SKILL_ROOT/scripts/prepare_cookies.sh\" \"<视频URL>\" chrome"
    exit 2
fi

COOKIE_PATH="$("$PYTHON_BIN" - "$COOKIE_ALIAS" "$SKILL_ROOT" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[2]) / "scripts"))
from config import cookie_path_for_alias
print(cookie_path_for_alias(Path(sys.argv[2]), sys.argv[1]))
PY
)"

mkdir -p "$(dirname "$COOKIE_PATH")"

if [ -s "$COOKIE_PATH" ]; then
    echo "[cookies] 已找到可用 cookie 文件: $COOKIE_PATH"
    echo "[cookies] 若目标来源仍提示登录或风控，再重新导出。"
    exit 0
fi

cat <<EOF
[cookies] 未找到可用 cookie 文件。

可选方式：
1. 先在本机浏览器登录目标来源，然后从浏览器导出 cookie。
2. 手动提供 Netscape 格式 cookie 文件，并保存到当前来源路径。

当前来源别名：
  $COOKIE_ALIAS

当前 cookie 路径：
  $COOKIE_PATH
EOF

if [ -z "$VIDEO_URL" ]; then
    echo "[cookies] 未提供视频 URL，不执行浏览器导出。"
    exit 2
fi

if [ ! -x "$YT_DLP_BIN" ]; then
    echo "[cookies] 未找到 yt-dlp，请先运行: bash \"$SKILL_ROOT/scripts/setup.sh\"" >&2
    exit 1
fi

printf "[cookies] 是否从本机 %s 浏览器导出 cookie？需要你已在该浏览器登录目标来源。[y/N] " "$BROWSER"
read -r CONFIRM || CONFIRM=""
case "$CONFIRM" in
    y|Y|yes|YES)
        "$YT_DLP_BIN" --cookies-from-browser "$BROWSER" --cookies "$COOKIE_PATH" --get-title "$VIDEO_URL" >/dev/null
        echo "[cookies] cookie 已导出到: $COOKIE_PATH"
        ;;
    *)
        echo "[cookies] 已取消导出。"
        exit 2
        ;;
esac
