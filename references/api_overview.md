# 通义听悟 API 速查

- **产品版本**：tingwu/2023-09-30
- **签名风格**：ROA
- **域名格式**：`tingwu.{region}.aliyuncs.com`（如 `tingwu.cn-beijing.aliyuncs.com`）

---

## CreateTask — 创建离线转写任务

- **方法**：`PUT`
- **路径**：`/openapi/tingwu/v2/tasks?type=offline`

**请求 Body（JSON）关键字段：**

```json
{
  "AppKey": "<应用 AppKey>",
  "Input": {
    "FileUrl": "<音视频文件 HTTP URL>",
    "SourceLanguage": "cn",
    "TaskKey": "<自定义任务标识，可选>"
  },
  "Parameters": {
    "Transcription": {
      "DiarizationEnabled": true,
      "Diarization": { "SpeakerCount": 0 }
    },
    "SummarizationEnabled": true,
    "Summarization": { "Types": ["Paragraph", "Conversational"] }
  }
}
```

**SourceLanguage 可选值**：`cn / en / yue / ja / ko / auto / multilingual`

**成功响应：**

```json
{
  "Code": "0",
  "Data": { "TaskId": "<32位任务ID>" },
  "Message": "Success",
  "RequestId": "..."
}
```

---

## GetTaskInfo — 查询任务状态与结果

- **方法**：`GET`
- **路径**：`/openapi/tingwu/v2/tasks/{TaskId}`

**成功响应关键字段：**

```json
{
  "Code": "0",
  "Data": {
    "TaskId": "...",
    "TaskStatus": "COMPLETED",
    "Result": {
      "Transcription": "<转写结果 JSON 文件的临时 URL>",
      "Summarization": "<摘要结果 JSON 文件的临时 URL>"
    }
  }
}
```

> `Result` 中的 URL 是临时地址，需再次 GET 请求才能拿到实际内容，且有过期时间。

---

## 任务状态机

```
创建任务
    ↓
  ONGOING（转写中）
    ├─→ COMPLETED（成功）→ 可调用 GetTaskInfo 取 Result URL
    ├─→ FAILED（失败）
    └─→ INVALID（无效，TaskId 不存在或已过期）
```

---

## OSS 目录结构

```
<bucket>/
└── transcribe/
    ├── media/       ← 上传的音视频原文件（生命周期规则：3 天自动删除）
    └── transcript/  ← 转写结果 md 文件（永久保留）
```

**生命周期规则配置：**
- 前缀 `transcribe/media/`：最后修改时间后 **3 天**删除
- 前缀 `transcribe/transcript/`：不设规则，永久保留

**文件命名格式：**

| 存储位置 | 格式 |
|---------|------|
| OSS media | `transcribe/media/{YYYYMMDD_HHMMSS}-{原文件名（含扩展名）}` |
| OSS transcript | `transcribe/transcript/{YYYYMMDD_HHMMSS}-{原文件名}.md` |
| 本地 results | `{YYYYMMDD_HHMMSS}-{原文件名}-{完整TaskId}.md` |
| 本地 meta | `{YYYYMMDD_HHMMSS}-{原文件名}-{完整TaskId}_meta.json` |

> 本地和 OSS 文件使用同一时间戳（在 `save_result` 函数开头统一生成），方便对照。

---

## 注意事项

- `FileUrl` 必须是公网可访问的 HTTP/HTTPS 地址，不支持本地路径
- OSS 预签名 URL 有效期建议设置不低于转写等待时间（默认 6 小时）
- 查询接口 QPS 上限：100/s；创建接口 QPS 上限：20/s
- `Code` 字段可能返回整数 `0` 或字符串 `"0"`，判断时需兼容两种类型
