#!/usr/bin/env python3
# 获取通义听悟转写结果，保存到本地和 OSS，并写入 meta.json
# 用法: python3 get_result.py <task_id> [--input-name 原文件名] [--output-dir 输出目录]
# 输出: 本地 md 文件路径

import os
import sys
import json
import datetime
import urllib.request
import argparse
import os
import oss2
from pathlib import Path
from upload_oss import OSS_TRANSCRIPT_DIR
from errors import explain_error, explain_task_status
from config import get_output_dir
from dotenv import load_dotenv
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest
from aliyunsdkcore.auth.credentials import AccessKeyCredential

# 从脚本所在目录向上一级（skill 根目录）加载 .env
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

# ── 参数配置 ─────────────────────────────────────────────
TASK_ID = ""
OUTPUT_DIR = get_output_dir()
# ────────────────────────────────────────────────────────

ACCESS_KEY_ID = os.environ["ALIBABA_CLOUD_ACCESS_KEY_ID"]
ACCESS_KEY_SECRET = os.environ["ALIBABA_CLOUD_ACCESS_KEY_SECRET"]
REGION = os.environ.get("TINGWU_REGION", "cn-beijing")
OSS_BUCKET = os.environ["OSS_BUCKET"]
OSS_ENDPOINT = os.environ["OSS_ENDPOINT"]


def get_task_data(task_id: str) -> dict:
    """调用 GetTaskInfo 接口获取任务数据"""
    credentials = AccessKeyCredential(ACCESS_KEY_ID, ACCESS_KEY_SECRET)
    client = AcsClient(region_id=REGION, credential=credentials)

    request = CommonRequest()
    request.set_accept_format("json")
    request.set_domain(f"tingwu.{REGION}.aliyuncs.com")
    request.set_version("2023-09-30")
    request.set_protocol_type("https")
    request.set_method("GET")
    request.set_uri_pattern(f"/openapi/tingwu/v2/tasks/{task_id}")
    request.add_header("Content-Type", "application/json")

    response = json.loads(client.do_action_with_exception(request))

    if str(response.get("Code")) != "0":
        raise RuntimeError(explain_error(response.get("Code", ""), response.get("Message", "")))

    return response["Data"]


def fetch_result_json(url: str) -> dict:
    """Result 里的各字段是 JSON 文件 URL，需要再请求一次"""
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def format_transcript(transcription_data: dict) -> str:
    """将转写 JSON 格式化为可读文本"""
    lines = []
    paragraphs = transcription_data.get("Transcription", transcription_data).get("Paragraphs", [])
    for p in paragraphs:
        speaker = p.get("SpeakerId", "")
        words = p.get("Words", [])
        if isinstance(words, list):
            text = "".join(w.get("Text", "") for w in words)
            begin_ms = words[0].get("Start", 0) if words else 0
        else:
            text = str(words)
            begin_ms = 0

        m, s = divmod(begin_ms // 1000, 60)
        timestamp = f"[{m:02d}:{s:02d}]"
        prefix = f"**{speaker}** " if speaker else ""
        lines.append(f"{timestamp} {prefix}{text}")
    return "\n\n".join(lines)


def upload_to_oss(local_path: str, oss_key: str) -> str:
    """上传文件到 OSS，返回 oss:// 路径，失败只警告不抛异常"""
    try:
        auth = oss2.Auth(ACCESS_KEY_ID, ACCESS_KEY_SECRET)
        bucket = oss2.Bucket(auth, f"https://{OSS_ENDPOINT}", OSS_BUCKET)
        bucket.put_object_from_file(oss_key, local_path)
        return f"oss://{OSS_BUCKET}/{oss_key}"
    except Exception as e:
        print(f"  [警告] OSS 上传失败，本地文件已保存，可手动重传: {e}", file=sys.stderr)
        return ""


def save_result(task_id: str, output_dir: str, input_name: str = "") -> str:
    data = get_task_data(task_id)

    if data.get("TaskStatus") != "COMPLETED":
        status = data.get("TaskStatus", "UNKNOWN")
        raise RuntimeError(f"任务未完成 [{status}]: {explain_task_status(status)}")

    os.makedirs(output_dir, exist_ok=True)

    # 统一时间戳，本地文件名和 OSS 文件名保持一致
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = Path(input_name).stem if input_name else task_id
    base_name = f"{ts}-{stem}-{task_id}"

    result_urls = data.get("Result", {})
    md_sections = [f"# 转写结果\n\n- **TaskId**: {task_id}\n- **状态**: {data.get('TaskStatus')}\n"]

    # 从听悟 API 直接拉取转写内容（不经过 OSS）
    if "Transcription" in result_urls:
        print(f"  获取转写内容...", file=sys.stderr)
        trans_data = fetch_result_json(result_urls["Transcription"])
        md_sections.append("## 转写文本\n\n" + format_transcript(trans_data))

    # 摘要
    if "Summarization" in result_urls:
        print(f"  获取摘要内容...", file=sys.stderr)
        summ_data = fetch_result_json(result_urls["Summarization"])
        paragraphs = summ_data.get("Paragraphs", [])
        if paragraphs:
            summ_text = "\n\n".join(p.get("Text", "") for p in paragraphs)
            md_sections.append("## 摘要总结\n\n" + summ_text)

    md_content = "\n\n---\n\n".join(md_sections)

    # 保存本地 md
    local_md_path = os.path.join(output_dir, f"{base_name}.md")
    with open(local_md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"  本地已保存: {local_md_path}", file=sys.stderr)

    # 上传转写文本到 OSS（归档，失败不影响主流程）
    oss_transcript_key = f"{OSS_TRANSCRIPT_DIR}/{ts}-{stem}.md"
    print(f"  上传转写文本到 OSS...", file=sys.stderr)
    oss_transcript_path = upload_to_oss(local_md_path, oss_transcript_key)

    # 写入 meta.json（含原始临时 URL，供兜底用）
    meta = {
        "task_id": task_id,
        "input_name": input_name,
        "created_at": datetime.datetime.now().isoformat(),
        "local_transcript": local_md_path,
        "oss_transcript": oss_transcript_path,
        # 听悟 API 返回的临时下载 URL（有过期时间，仅供兜底）
        "tingwu_result_urls": data.get("Result", {}),
    }
    meta_path = os.path.join(output_dir, f"{base_name}_meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"  meta 已写入: {meta_path}", file=sys.stderr)

    return local_md_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("task_id", nargs="?", default=TASK_ID)
    parser.add_argument("--input-name", default="", help="原始文件名，用于生成文件名")
    parser.add_argument("--output-dir", default=OUTPUT_DIR)
    parsed = parser.parse_args()

    if not parsed.task_id:
        parser.print_help()
        sys.exit(1)

    if not parsed.output_dir:
        print("ERROR: 未设置输出目录，请在脚本顶部设置 OUTPUT_DIR 或使用 --output-dir 参数", file=sys.stderr)
        sys.exit(1)

    output_path = save_result(parsed.task_id, parsed.output_dir, parsed.input_name)
    print(output_path)
