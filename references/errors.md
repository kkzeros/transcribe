# 通义听悟错误码速查

## ⚠️ 账号级严重错误（遇到须立即停止并告知用户）

| 错误码 | 含义 | 排查建议 |
|--------|------|---------|
| `BRK.InvalidService` | 账号未开通通义听悟服务 | 前往 https://tingwu.console.aliyun.com 开通服务 |
| `BRK.OverdueService` | 账号服务已超配额 | 检查套餐用量或联系阿里云升配 |
| `BRK.OverdueTenant` | 账号已欠费 | 前往阿里云控制台充值 |
| `BRK.InvalidTenant` | 服务未开通或已欠费 | 确认服务已开通且账号余额充足 |

---

## 常规错误码

| 错误码 | 含义 | 排查建议 |
|--------|------|---------|
| `ServerError` | 服务端系统错误 | 稍后重试；持续出现请提交阿里云工单 |
| `BRK.InvalidAppKey` | AppKey 无效 | 检查 `.env` 中 `TINGWU_APP_KEY` 是否正确 |
| `BRK.ServiceLinkedRoleNotExist` | 缺少服务关联角色授权 | 在 RAM 控制台授权 `AliyunServiceRoleForTingwuPaaS` |
| `BRK.InvalidLanguage` | 语言参数无效 | `SourceLanguage` 可选值：`cn / en / yue / ja / ko / auto / multilingual` |
| `BRK.InvalidAudioFormat` | 音频格式不支持 | 音频：mp3 wav m4a wma aac ogg amr flac；视频：mp4 wmv m4v flv 等 |
| `BRK.InvalidAudioSampleRate` | 采样率不支持 | 支持：8000 / 16000 / 24000 / 48000 Hz |
| `BRK.InvalidOssBucket` | OSS Bucket 参数无效 | 检查文件 URL 是否可公网访问，Bucket 权限是否为公共读 |
| `BRK.InvalidOssPath` | OSS Path 参数无效 | 检查 URL 格式，不支持 IP 地址和空格 |
| `Throttling.User` | 请求被限流 | 创建任务上限 20/s，查询上限 100/s；**轮询间隔建议不低于 1s** |

---

## 任务状态说明

| 状态 | 含义 |
|------|------|
| `ONGOING` | 转写中（含排队等待） |
| `COMPLETED` | 转写完成，可取结果 |
| `FAILED` | 任务失败，可能是文件损坏、格式不支持或内容违规 |
| `INVALID` | 无效任务，TaskId 不存在或已过期 |
