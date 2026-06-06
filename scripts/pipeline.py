#!/usr/bin/env python3
# 通义听悟全流程编排：提交 → 轮询 → 获取结果
# 用法:
#   python3 pipeline.py <file_url> [--timeout 600]
#   yt-dlp -o - "URL" | python3 pipeline.py --stdin filename.mp3 [--timeout 600]
# 输出: 结果 md 文件路径

import sys
import time
import argparse
import datetime
from pathlib import Path
from dotenv import load_dotenv

# 把脚本所在目录加入 path，方便导入同级模块
sys.path.insert(0, str(Path(__file__).parent))
load_dotenv(Path(__file__).parent.parent / ".env")

from create_task import create_task
from query_task import query_task
from get_result import save_result
from upload_oss import upload_file, upload_stream
from errors import explain_task_status
from config import get_output_dir

# ── 参数配置 ─────────────────────────────────────────────
FILE_URL = ""          # 音视频文件 URL，可被命令行覆盖
OUTPUT_DIR = get_output_dir()
POLL_INTERVAL = 15     # 轮询间隔（秒）
MAX_WAIT = 600         # 默认最长等待时间（秒，默认 10 分钟），可通过 --timeout 覆盖
# ────────────────────────────────────────────────────────


def log(msg: str):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def run(file_url: str, output_dir: str, max_wait: int = MAX_WAIT, input_name: str = "") -> str:
    # 本地文件先上传到 OSS
    if not file_url.startswith("http"):
        input_name = input_name or Path(file_url).name
        log(f"[0/3] 检测到本地文件: {input_name}")
        log(f"      文件大小: {Path(file_url).stat().st_size / 1024 / 1024:.2f} MB")
        log(f"      开始上传至 OSS...")
        t0 = time.time()
        file_url = upload_file(file_url)
        log(f"      上传完成，耗时 {time.time()-t0:.1f}s")
        log(f"      OSS URL: {file_url[:100]}...")

    # 第一步：创建任务
    log(f"[1/3] 提交转写任务...")
    t0 = time.time()
    task_id = create_task(file_url)
    log(f"      TaskId: {task_id}  ({time.time()-t0:.1f}s)")

    # 第二步：轮询状态
    log(f"[2/3] 等待转写完成（轮询间隔 {POLL_INTERVAL}s，超时 {max_wait}s）...")
    elapsed = 0
    while elapsed < max_wait:
        data = query_task(task_id)
        status = data.get("TaskStatus", "UNKNOWN")
        log(f"      已等待 {elapsed}s  状态: {status}")

        if status == "COMPLETED":
            break
        elif status in ("FAILED", "INVALID"):
            raise RuntimeError(f"TaskId: {task_id}\n  {explain_task_status(status)}")

        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL
    else:
        raise TimeoutError(f"超过最大等待时间 {max_wait}s，TaskId: {task_id}")

    log(f"      转写完成，总耗时 {elapsed}s")

    # 第三步：保存结果
    log(f"[3/3] 获取并保存结果...")
    t0 = time.time()
    output_path = save_result(task_id, output_dir, input_name)
    log(f"      已保存: {output_path}  ({time.time()-t0:.1f}s)")
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="通义听悟转写全流程")
    parser.add_argument("input", nargs="?", default=FILE_URL,
                        help="音视频文件路径或 URL（--stdin 模式时为文件名）")
    parser.add_argument("--stdin", action="store_true",
                        help="从 stdin 流式接收音频（配合 yt-dlp 管道使用）")
    parser.add_argument("--output-dir", default=OUTPUT_DIR,
                        help="结果保存目录")
    parser.add_argument("--timeout", type=int, default=MAX_WAIT,
                        help=f"最长等待时间（秒），默认 {MAX_WAIT}s（{MAX_WAIT//60} 分钟）")
    parsed = parser.parse_args()

    log("=" * 50)
    log("通义听悟转写任务启动")
    log(f"超时设置: {parsed.timeout}s（{parsed.timeout//60} 分钟）")
    log("=" * 50)

    if not parsed.output_dir:
        log("ERROR: 未设置输出目录，请在脚本顶部设置 OUTPUT_DIR 或使用 --output-dir 参数")
        sys.exit(1)

    try:
        if parsed.stdin:
            # 流式模式：yt-dlp -o - "URL" | python3 pipeline.py --stdin filename.mp3
            if not parsed.input:
                log("ERROR: --stdin 模式下请传入文件名，例如: pipeline.py --stdin '视频标题.mp3'")
                sys.exit(1)
            filename = parsed.input
            log(f"[0/3] 流式上传模式，文件名: {filename}")
            t0 = time.time()
            file_url = upload_stream(sys.stdin.buffer, filename)
            log(f"      流式上传完成，耗时 {time.time()-t0:.1f}s")
            result_path = run(file_url, parsed.output_dir, parsed.timeout, input_name=filename)
        else:
            if not parsed.input:
                parser.print_help()
                sys.exit(1)
            result_path = run(parsed.input, parsed.output_dir, parsed.timeout)

        log("=" * 50)
        log(f"全部完成！结果文件: {result_path}")
        log("=" * 50)

    except Exception as e:
        log(f"ERROR: {e}")
        sys.exit(1)
