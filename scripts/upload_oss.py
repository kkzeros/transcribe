#!/usr/bin/env python3
# 上传文件到阿里云 OSS，返回有效期 6 小时的预签名 URL
#
# 支持三种模式：
#   本地文件:  python3 upload_oss.py /path/to/file.mp3
#   流式上传:  yt-dlp -o - "URL" | python3 upload_oss.py --stdin filename.mp3
#   URL 直传:  python3 upload_oss.py --url "https://..." filename.mp3

import os
import sys
import oss2
import datetime
from pathlib import Path
from dotenv import load_dotenv

# ── 参数配置 ─────────────────────────────────────────────
OSS_MEDIA_DIR = "transcribe/media"           # 音视频目录（设生命周期 3 天删除）
OSS_TRANSCRIPT_DIR = "transcribe/transcript" # 转写文本目录（永久保留）
URL_EXPIRE = 6 * 3600                        # 预签名 URL 有效期（秒），默认 6 小时
CHUNK_SIZE = 1024 * 1024                     # 流式上传分块大小（1MB）
# ────────────────────────────────────────────────────────

# 从脚本所在目录向上一级（skill 根目录）加载 .env
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

ACCESS_KEY_ID = os.environ["ALIBABA_CLOUD_ACCESS_KEY_ID"]
ACCESS_KEY_SECRET = os.environ["ALIBABA_CLOUD_ACCESS_KEY_SECRET"]
OSS_BUCKET = os.environ["OSS_BUCKET"]
OSS_ENDPOINT = os.environ["OSS_ENDPOINT"]


def _get_bucket() -> oss2.Bucket:
    auth = oss2.Auth(ACCESS_KEY_ID, ACCESS_KEY_SECRET)
    return oss2.Bucket(auth, f"https://{OSS_ENDPOINT}", OSS_BUCKET)


def _sign_url(bucket: oss2.Bucket, oss_key: str) -> str:
    return bucket.sign_url("GET", oss_key, URL_EXPIRE)


def _build_oss_key(filename: str, oss_dir: str) -> str:
    """
    生成 OSS 文件路径，格式：
      transcribe/media/{timestamp}-{stem}{suffix}       ← 音视频
      transcribe/transcript/{timestamp}-{stem}{suffix}  ← 转写文本
    """
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    p = Path(filename)
    name = f"{ts}-{p.stem}{p.suffix}"
    return f"{oss_dir}/{name}"


def upload_file(local_path: str) -> str:
    """本地文件上传"""
    bucket = _get_bucket()
    file_name = Path(local_path).name
    oss_key = _build_oss_key(file_name, OSS_MEDIA_DIR)

    print(f"上传中: {file_name} → oss://{OSS_BUCKET}/{oss_key}", file=sys.stderr)

    file_size = os.path.getsize(local_path)
    if file_size > 100 * 1024 * 1024:
        # 大文件断点续传
        oss2.resumable_upload(bucket, oss_key, local_path)
    else:
        bucket.put_object_from_file(oss_key, local_path)

    url = _sign_url(bucket, oss_key)
    print(f"上传完成: {oss_key}", file=sys.stderr)
    return url


def upload_stream(stream, filename: str) -> str:
    """流式上传（stdin 或任意 file-like object），边接收边上传，不落磁盘"""
    bucket = _get_bucket()
    oss_key = _build_oss_key(filename, OSS_MEDIA_DIR)

    print(f"流式上传: {filename} → oss://{OSS_BUCKET}/{oss_key}", file=sys.stderr)

    # 初始化分片上传
    upload_id = bucket.init_multipart_upload(oss_key).upload_id
    parts = []
    part_number = 1
    buf = b""
    min_part_size = 5 * 1024 * 1024  # OSS 分片最小 5MB

    try:
        while True:
            chunk = stream.read(CHUNK_SIZE)
            if not chunk:
                break
            buf += chunk
            # 攒够 5MB 再上传一片
            if len(buf) >= min_part_size:
                result = bucket.upload_part(oss_key, upload_id, part_number, buf)
                parts.append(oss2.models.PartInfo(part_number, result.etag))
                print(f"  已上传分片 {part_number} ({len(buf)/1024/1024:.1f}MB)", file=sys.stderr)
                part_number += 1
                buf = b""

        # 上传剩余数据（最后一片可以小于 5MB）
        if buf:
            result = bucket.upload_part(oss_key, upload_id, part_number, buf)
            parts.append(oss2.models.PartInfo(part_number, result.etag))
            print(f"  已上传分片 {part_number} ({len(buf)/1024/1024:.1f}MB)", file=sys.stderr)

        # 合并分片
        bucket.complete_multipart_upload(oss_key, upload_id, parts)

    except Exception as e:
        # 上传失败则取消，避免产生碎片费用
        bucket.abort_multipart_upload(oss_key, upload_id)
        raise RuntimeError(f"流式上传失败，已取消: {e}")

    url = _sign_url(bucket, oss_key)
    print(f"上传完成: {oss_key}", file=sys.stderr)
    return url


def upload_from_url(source_url: str, filename: str) -> str:
    """从远程 URL 拉取并上传到 OSS（服务端 fetch，适合服务器带宽有限时）"""
    import urllib.request
    print(f"从 URL 拉取并上传: {filename}", file=sys.stderr)
    with urllib.request.urlopen(source_url) as resp:
        return upload_stream(resp, filename)


if __name__ == "__main__":
    args = sys.argv[1:]

    if not args:
        print("用法:", file=sys.stderr)
        print("  本地文件:  python3 upload_oss.py /path/to/file.mp3", file=sys.stderr)
        print("  流式上传:  yt-dlp -o - 'URL' | python3 upload_oss.py --stdin filename.mp3", file=sys.stderr)
        print("  URL 直传:  python3 upload_oss.py --url 'https://...' filename.mp3", file=sys.stderr)
        sys.exit(1)

    if args[0] == "--stdin":
        filename = args[1] if len(args) > 1 else "upload.mp3"
        url = upload_stream(sys.stdin.buffer, filename)

    elif args[0] == "--url":
        source_url = args[1]
        filename = args[2] if len(args) > 2 else Path(source_url.split("?")[0]).name
        url = upload_from_url(source_url, filename)

    else:
        url = upload_file(args[0])

    print(url)  # 只输出 URL，方便管道传递
