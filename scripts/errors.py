#!/usr/bin/env python3
# 通义听悟 API 错误码识别与友好提示

# 错误码 → (简短说明, 排查建议)
ERROR_MAP = {
    "ServerError": (
        "服务端系统错误",
        "阿里云服务异常，稍后重试；若持续出现请提交工单"
    ),
    "BRK.InvalidService": (
        "账号未开通通义听悟服务",
        "请前往 https://tingwu.console.aliyun.com 开通服务"
    ),
    "BRK.OverdueService": (
        "账号服务已超配额",
        "当前账号用量已达上限，请检查套餐或联系阿里云升配"
    ),
    "BRK.OverdueTenant": (
        "账号已欠费",
        "请前往阿里云控制台充值后重试"
    ),
    "BRK.InvalidTenant": (
        "账号服务未开通或已欠费",
        "请确认通义听悟服务已开通且账号余额充足"
    ),
    "BRK.InvalidAppKey": (
        "AppKey 无效",
        "请检查 .env 中 TINGWU_APP_KEY 是否填写正确，"
        "可在 https://tingwu.console.aliyun.com 项目管理中查看"
    ),
    "BRK.ServiceLinkedRoleNotExist": (
        "缺少角色授权",
        "请在 RAM 控制台为通义听悟授权服务关联角色 AliyunServiceRoleForTingwuPaaS"
    ),
    "BRK.InvalidLanguage": (
        "语言参数无效",
        "SourceLanguage 可选值：cn / en / yue / ja / ko / auto / multilingual"
    ),
    "BRK.InvalidAudioFormat": (
        "音频格式无效",
        "支持格式：mp3 wav m4a wma aac ogg amr flac aiff；视频：mp4 wmv m4v flv 等"
    ),
    "BRK.InvalidAudioSampleRate": (
        "音频采样率无效",
        "支持采样率：8000 / 16000 / 24000 / 48000 Hz"
    ),
    "BRK.InvalidOssBucket": (
        "OSS Bucket 参数无效",
        "请检查文件 URL 是否可公网访问，OSS Bucket 权限是否为公共读"
    ),
    "BRK.InvalidOssPath": (
        "OSS Path 参数无效",
        "请检查文件 URL 格式是否正确，不支持 IP 地址和空格"
    ),
    "Throttling.User": (
        "请求被限流",
        "当前 QPS 超限（创建任务上限 20/s，查询上限 100/s），请降低调用频率"
    ),
}

# 任务失败时的状态说明
TASK_STATUS_MAP = {
    "FAILED":  "任务处理失败，可能是音视频文件损坏、格式不支持或内容违规",
    "INVALID": "无效任务，任务 ID 不存在或已过期",
}


def explain_error(code: str, message: str = "") -> str:
    """
    根据错误码返回友好的中文说明。
    code: API 返回的错误码字符串
    message: API 返回的原始错误信息（可选，用于兜底展示）
    """
    if code in ERROR_MAP:
        label, suggestion = ERROR_MAP[code]
        return f"[错误] {label}\n  错误码: {code}\n  排查建议: {suggestion}"

    # 限流错误码包含在消息体里
    if "Throttling" in code:
        label, suggestion = ERROR_MAP["Throttling.User"]
        return f"[错误] {label}\n  错误码: {code}\n  排查建议: {suggestion}"

    # 未收录的错误码，直接展示原始信息
    raw = f"（原始信息: {message}）" if message else ""
    return f"[错误] 未知错误码: {code} {raw}\n  排查建议: 请查阅 references/errors.md"


def explain_task_status(status: str) -> str:
    """根据任务状态返回说明"""
    return TASK_STATUS_MAP.get(status, f"未知任务状态: {status}")
