#!/usr/bin/env python3
# 查询通义听悟任务状态
# 用法: python3 query_task.py <task_id>
# 输出: ONGOING / COMPLETED / FAILED / INVALID

import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest
from aliyunsdkcore.auth.credentials import AccessKeyCredential
from errors import explain_error

# ── 参数配置 ─────────────────────────────────────────────
TASK_ID = ""   # 任务ID，可被命令行覆盖
# ────────────────────────────────────────────────────────

# 从脚本所在目录向上一级（skill 根目录）加载 .env
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

ACCESS_KEY_ID = os.environ["ALIBABA_CLOUD_ACCESS_KEY_ID"]
ACCESS_KEY_SECRET = os.environ["ALIBABA_CLOUD_ACCESS_KEY_SECRET"]
REGION = os.environ.get("TINGWU_REGION", "cn-beijing")


def query_task(task_id: str) -> dict:
    """
    返回任务信息字典，包含 TaskStatus 字段：
      ONGOING   - 转写中
      COMPLETED - 成功
      FAILED    - 失败
      INVALID   - 无效任务
    """
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


if __name__ == "__main__":
    task_id = sys.argv[1] if len(sys.argv) > 1 else TASK_ID
    if not task_id:
        print("用法: python3 query_task.py <task_id>", file=sys.stderr)
        sys.exit(1)

    data = query_task(task_id)
    status = data.get("TaskStatus", "UNKNOWN")
    print(status)  # 只输出状态，方便管道判断
