#!/usr/bin/env python3
# 创建通义听悟离线转写任务
# 用法: python3 create_task.py <file_url>
# 输出: TaskId（成功）或报错信息

import os
import sys
import json
import datetime
from pathlib import Path
from dotenv import load_dotenv
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest
from aliyunsdkcore.auth.credentials import AccessKeyCredential
from errors import explain_error

# ── 参数配置（可被命令行覆盖）──────────────────────────
FILE_URL = ""                  # 音视频文件的 HTTP/HTTPS 公开地址
SOURCE_LANGUAGE = "cn"         # 语言：cn/en/yue/ja/ko/auto/multilingual
SPEAKER_COUNT = 0              # 说话人数，0=自动
ENABLE_TRANSLATION = False     # 是否翻译
TRANSLATION_TARGETS = ["en"]   # 翻译目标语言
ENABLE_SUMMARIZATION = True    # 是否生成摘要
# ────────────────────────────────────────────────────────

# 从脚本所在目录向上一级（skill 根目录）加载 .env
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

ACCESS_KEY_ID = os.environ["ALIBABA_CLOUD_ACCESS_KEY_ID"]
ACCESS_KEY_SECRET = os.environ["ALIBABA_CLOUD_ACCESS_KEY_SECRET"]
APP_KEY = os.environ["TINGWU_APP_KEY"]
REGION = os.environ.get("TINGWU_REGION", "cn-beijing")


def build_request_body(file_url: str) -> dict:
    body = {
        "AppKey": APP_KEY,
        "Input": {
            "FileUrl": file_url,
            "SourceLanguage": SOURCE_LANGUAGE,
            "TaskKey": "task_" + datetime.datetime.now().strftime("%Y%m%d%H%M%S"),
        },
        "Parameters": {
            "Transcription": {
                "DiarizationEnabled": True,
                "Diarization": {"SpeakerCount": SPEAKER_COUNT},
            },
            "TranslationEnabled": ENABLE_TRANSLATION,
            "Translation": {"TargetLanguages": TRANSLATION_TARGETS} if ENABLE_TRANSLATION else {},
            "SummarizationEnabled": ENABLE_SUMMARIZATION,
            "Summarization": {"Types": ["Paragraph", "Conversational"]} if ENABLE_SUMMARIZATION else {},
        }
    }
    return body


def create_task(file_url: str) -> str:
    credentials = AccessKeyCredential(ACCESS_KEY_ID, ACCESS_KEY_SECRET)
    client = AcsClient(region_id=REGION, credential=credentials)

    request = CommonRequest()
    request.set_accept_format("json")
    request.set_domain(f"tingwu.{REGION}.aliyuncs.com")
    request.set_version("2023-09-30")
    request.set_protocol_type("https")
    request.set_method("PUT")
    request.set_uri_pattern("/openapi/tingwu/v2/tasks")
    request.add_header("Content-Type", "application/json")
    request.add_query_param("type", "offline")
    request.set_content(json.dumps(build_request_body(file_url)).encode("utf-8"))

    response = json.loads(client.do_action_with_exception(request))

    if str(response.get("Code")) != "0":
        raise RuntimeError(explain_error(response.get("Code", ""), response.get("Message", "")))

    task_id = response["Data"]["TaskId"]
    return task_id


if __name__ == "__main__":
    file_url = sys.argv[1] if len(sys.argv) > 1 else FILE_URL
    if not file_url:
        print("用法: python3 create_task.py <file_url>", file=sys.stderr)
        sys.exit(1)

    task_id = create_task(file_url)
    print(task_id)  # 只输出 TaskId，方便管道传递
