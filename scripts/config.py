#!/usr/bin/env python3
# transcribe skill 的本地配置解析工具。

import os
import re
from pathlib import Path
from typing import Mapping, Optional
from urllib.parse import urlparse


RESULT_DIR_NAME = "transcribe-results"
COOKIE_DIR_NAME = "cookies"


def _expand_path(value: str, skill_root: Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = skill_root / path
    return path


def _fallback_parent(skill_root: Path) -> Path:
    # 安装在 ~/.agents/skills/transcribe 或 ~/.claude/skills/transcribe 时，
    # 输出放到 ~/.agents/transcribe-results 或 ~/.claude/transcribe-results。
    if skill_root.parent.name == "skills":
        return skill_root.parent.parent
    return skill_root.parent


def resolve_output_dir(skill_root: Path, env: Optional[Mapping[str, str]] = None) -> Path:
    env = env or os.environ
    configured_parent = env.get("TRANSCRIBE_OUTPUT_PARENT_DIR", "").strip()
    if configured_parent:
        parent = _expand_path(configured_parent, skill_root)
        if parent.exists() and parent.is_dir():
            return parent / RESULT_DIR_NAME

    return _fallback_parent(skill_root) / RESULT_DIR_NAME


def get_output_dir() -> str:
    return str(resolve_output_dir(Path(__file__).parent.parent.absolute()))


def _host_from_url(url: str) -> str:
    host = urlparse(url).netloc.lower().split("@")[-1].split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    return host


def _safe_cookie_alias(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def cookie_alias_from_url(url: str, env: Optional[Mapping[str, str]] = None) -> str:
    host = _host_from_url(url)
    if not host:
        return ""
    return _safe_cookie_alias(host)


def cookie_path_for_platform(skill_root: Path, platform: str) -> Path:
    return skill_root / COOKIE_DIR_NAME / f"{_safe_cookie_alias(platform)}.cookies.txt"


def cookie_path_for_alias(skill_root: Path, alias: str) -> Path:
    return cookie_path_for_platform(skill_root, alias)
