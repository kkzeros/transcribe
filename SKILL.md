---
name: transcribe
version: 1.0.0
description: >
  音视频转写 skill — 将在线视频 URL、本地音视频文件，通过通义听悟 API 转写为中文文字稿（Markdown 格式），
  同时归档到阿里云 OSS。当用户提到"转写"、"字幕"、"听悟"、"在线视频"、"把视频变成文字"、"音频转文字"、
  "视频转文字"、"yt-dlp"等相关需求时，立即使用本 skill，不要等用户明确说"用 transcribe skill"。
metadata:
  openclaw:
    requires:
      env:
        - ALIBABA_CLOUD_ACCESS_KEY_ID
        - ALIBABA_CLOUD_ACCESS_KEY_SECRET
        - TINGWU_APP_KEY
        - OSS_BUCKET
        - OSS_ENDPOINT
        - TINGWU_REGION
      bins:
        - python3
        - ffmpeg
        - yt-dlp
    primaryEnv: ALIBABA_CLOUD_ACCESS_KEY_ID
    emoji: "🎙"
    os:
      - macos
      - linux
    install:
      - kind: uv
        package: yt-dlp
        bins: [yt-dlp]
---

# Transcribe — 音视频转写 Skill

将音视频内容转写为带时间戳、说话人标注的 Markdown 文字稿。

## 支持的输入方式

| 方式 | 示例 |
|------|------|
| 在线视频 URL | 支持 yt-dlp 可解析的视频平台链接 |
| 本地音视频文件路径 | `/path/to/video.mp3` |
| 已公开的 HTTP 文件 URL | `https://example.com/audio.mp4` |

**输出**：保存到 Step 0.5 确认的 `OUTPUT_DIR` 目录下：

| 文件 | 内容 |
|------|------|
| `{ts}-{name}-{taskId}.md` | 转写全文（带时间戳、说话人标注）+ 摘要总结 |
| `{ts}-{name}-{taskId}_meta.json` | task_id、原文件名、本地路径、OSS 路径、听悟临时 URL（兜底用） |

---

## Step 0：依赖自检（每次调用前执行）

**第一步：确定 skill 根目录的绝对路径**

skill 根目录是 SKILL.md 所在的目录。用以下命令获取并记录，后续所有步骤都以此为基准：

```bash
SKILL_ROOT=$(python3 -c "from pathlib import Path; print(Path('scripts/pipeline.py').resolve().parent.parent)")
```

若上述命令因 CWD 不同而不准确，改用脚本的绝对路径推算：

```bash
SKILL_ROOT=$(python3 -c "from pathlib import Path; import sys; print(Path(sys.argv[1]).resolve().parent.parent)" "$SKILL_ROOT/scripts/pipeline.py")
```

或直接用已知的安装路径（openclaw 环境下通常为）：

```
~/.openclaw/skills/transcribe-openclaw
```

**第二步：运行依赖自检**

```bash
bash $SKILL_ROOT/scripts/setup.sh
```

幂等脚本，已安装则秒过。

**第三步：检查 `.env` 文件**

检查 `$SKILL_ROOT/.env` 是否存在：
- **存在** → 继续
- **不存在** → 停止，提示用户：
  ```
  未找到 .env 文件，请在 skill 根目录下创建：
    cp $SKILL_ROOT/.env.example $SKILL_ROOT/.env
  然后编辑 .env 填入真实凭证（参考 .env.example 中的字段说明）
  ```

**第四步：解析 cookie 路径**

读取 `$SKILL_ROOT/.env` 中的 `COOKIES_FILE` 值，拼出绝对路径并检查文件是否存在：

```bash
COOKIES_FILE=$(grep '^COOKIES_FILE=' $SKILL_ROOT/.env | cut -d'=' -f2 | tr -d ' ')
if [ -n "$COOKIES_FILE" ] && [ -f "$SKILL_ROOT/$COOKIES_FILE" ]; then
  COOKIES_OPT="--cookies $SKILL_ROOT/$COOKIES_FILE"
  echo "Cookie 文件已就绪：$SKILL_ROOT/$COOKIES_FILE"
else
  COOKIES_OPT=""
  echo "未配置 cookie，yt-dlp 以匿名模式运行"
fi
```

后续所有 yt-dlp 命令统一使用 `$COOKIES_OPT` 变量（已包含 `--cookies <绝对路径>`），无需手动拼路径。

---

## Step 0.5：输出路径确认（每次调用前执行）

读取 `scripts/pipeline.py` 顶部的 `OUTPUT_DIR` 变量：

- **为空或路径不合法** → 不要直接运行脚本，先向用户确认：
  - 若运行环境是 **openclaw**：
    ```
    .openclaw/workspace/data/transcribe_results
    ```
  - 若运行环境是 **Claude Code 或其他终端**：检测当前项目根目录（优先用 `git rev-parse --show-toplevel`，若不在 git 仓库则用 `pwd` 输出的当前目录），建议路径为：
    ```
    <项目根目录>/results
    ```
    将检测到的完整路径返回给用户确认
  - 若用户有自定义偏好，按用户指定路径
  - 确认后将路径写入 `scripts/pipeline.py` 的 `OUTPUT_DIR`，同步更新 `scripts/get_result.py` 的 `OUTPUT_DIR`

- **已填写且路径合法** → 直接进入 Step 1，不再询问

> 依赖检查（Step 0）和路径确认（Step 0.5）是两个独立步骤，互不影响。

---

## Step 1：执行转写

> 以下命令中 `$SKILL_ROOT` 为 skill 根目录绝对路径（Step 0 已确定）。
> cookie 文件固定在 `$SKILL_ROOT/cookies.txt`，**每条 yt-dlp 命令都必须加上 `--cookies $SKILL_ROOT/cookies.txt`**，不要省略。

### 方式 A：在线视频 URL（yt-dlp 可解析的平台）

```bash
TITLE=$(yt-dlp --cookies $SKILL_ROOT/cookies.txt --get-title "<视频URL>")
yt-dlp --cookies $SKILL_ROOT/cookies.txt -x --audio-format mp3 -o - "<视频URL>" | python3 $SKILL_ROOT/scripts/pipeline.py --stdin "${TITLE}.mp3"
```

### 方式 B：本地文件

```bash
python3 $SKILL_ROOT/scripts/pipeline.py "/path/to/file.mp3"
```

### 方式 C：已有公开 HTTP URL（文件可被听悟服务器直接访问）

```bash
python3 $SKILL_ROOT/scripts/pipeline.py "https://example.com/audio.mp3"
```

### 方式 D：yt-dlp 取直链 → 先上传 OSS 再转写

适用场景：视频平台 CDN 直链有时效或需要 Headers，听悟无法直接拉取，需经 OSS 中转。

```bash
TITLE=$(yt-dlp --cookies $SKILL_ROOT/cookies.txt --get-title "<视频URL>")
DIRECT_URL=$(yt-dlp --cookies $SKILL_ROOT/cookies.txt -g "<视频URL>" | head -1)
OSS_URL=$(python3 $SKILL_ROOT/scripts/upload_oss.py --url "$DIRECT_URL" "${TITLE}.mp4")
python3 $SKILL_ROOT/scripts/pipeline.py "$OSS_URL"
```

> **注意**：`yt-dlp -g` 返回原始视频格式（mp4/flv），不会转码为 mp3。
> 若需要 mp3，优先用方式 A（流式转码）。方式 D 适合服务器本地带宽有限、希望让 OSS 直接拉流的场景。

> **yt-dlp 下载失败时**（如需要登录、地区限制等），可先在本地手动下载音频文件，再用**方式 B** 传入本地路径处理。

### 可选参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--timeout N` | 最长等待转写完成时间（秒） | 600（10 分钟） |
| `--output-dir PATH` | 结果保存目录（覆盖 OUTPUT_DIR） | 同 OUTPUT_DIR |

### 超时时间估算

调用前建议先用 ffprobe 获取文件时长，再按下表设置 `--timeout`：

```bash
ffprobe -v error -show_entries format=duration -of csv=p=0 "audio.mp3"
```

| 文件时长 | 建议 --timeout |
|----------|---------------|
| < 10 分钟 | 600s（默认） |
| 10 ~ 30 分钟 | 1800s |
| 30 ~ 60 分钟 | 3600s |
| > 1 小时 | 文件时长（秒）× 3 |

---

## 断点续传

脚本不做自动断点检测，TaskId 打印在终端，agent 持有上下文后可按下表手动续接：

| 中断位置 | 已有信息 | 恢复方式 |
|----------|----------|---------|
| OSS 上传中 | 无 TaskId | 重新运行全流程 |
| OSS 上传完、建任务前 | 有 OSS URL，无 TaskId | 重新运行全流程（重传代价小） |
| 建任务后，轮询中断 | 有 TaskId | `query_task.py` 轮询，再调 `get_result.py` |
| 轮询完成，取结果中断 | TaskId + 状态 COMPLETED | 直接调 `get_result.py` |

```bash
# 查询任务状态
python3 scripts/query_task.py <taskId>

# 状态为 COMPLETED 时直接取结果
# OUTPUT_DIR 已写入脚本时无需传 --output-dir；否则手动指定
python3 scripts/get_result.py <taskId> --input-name "原文件名.mp3" --output-dir <输出路径>
```

---

## .env 配置说明

`.env` 放在 skill 根目录（与 SKILL.md 同级），完整模板见 `.env.example`。

必填项：

```
ALIBABA_CLOUD_ACCESS_KEY_ID=
ALIBABA_CLOUD_ACCESS_KEY_SECRET=
TINGWU_APP_KEY=
OSS_BUCKET=
OSS_ENDPOINT=
```

可选项（有默认值）：

```
TINGWU_REGION=cn-beijing   # 服务地域，按实际开通地域填写
```

---

## 错误排查

脚本遇到错误码会自动输出中文说明和排查建议。常见错误速查见 `references/errors.md`。

### 账号级严重错误（遇到立即停止并提醒用户）

以下错误表示账号或服务本身存在问题，继续重试无意义，**必须中断任务并向用户发出明确警告**：

| 错误码 | 含义 | 建议提示用户 |
|--------|------|-------------|
| `BRK.InvalidService` | 账号未开通通义听悟服务 | 请前往 https://tingwu.console.aliyun.com 开通服务后重试 |
| `BRK.OverdueService` | 账号服务已超配额 | 当前用量已达上限，请检查套餐或联系阿里云升配 |
| `BRK.OverdueTenant` | 账号已欠费 | 请前往阿里云控制台充值后重试 |
| `BRK.InvalidTenant` | 账号服务未开通或已欠费 | 请确认通义听悟服务已开通且账号余额充足 |

这类错误由 `errors.py` 的 `explain_error()` 自动识别并输出中文说明。若脚本抛出包含上述错误码的异常，**不要静默忽略，直接将错误信息展示给用户**。

---

## 获取结果失败时的兜底方案

主流程：听悟 API 完成 → 直接从听悟临时 URL 下载（不经 OSS，节省流量）

若主流程失败，按以下顺序兜底：

1. **重试听悟 API**：重新执行 `get_result.py <taskId>`，临时 URL 未过期则可重新拉取
2. **从 OSS 下载**：先读取 `_meta.json` 中的 `oss_transcript` 字段，格式为 `oss://<bucket>/transcribe/transcript/<文件名>.md`，取最后的路径部分替换到命令中：
   ```bash
   # 将 <oss_key> 替换为 oss_transcript 字段中 bucket 后面的路径部分
   # 将 <本地保存路径> 替换为实际输出路径
   python3 -c "
   import oss2, os; from dotenv import load_dotenv; load_dotenv()
   auth = oss2.Auth(os.environ['ALIBABA_CLOUD_ACCESS_KEY_ID'], os.environ['ALIBABA_CLOUD_ACCESS_KEY_SECRET'])
   bucket = oss2.Bucket(auth, 'https://' + os.environ['OSS_ENDPOINT'], os.environ['OSS_BUCKET'])
   bucket.get_object_to_file('<oss_key>', '<本地保存路径>')
   "
   ```
3. **使用 tingwu_result_urls**：`_meta.json` 中保存了听悟原始临时 URL，在有效期内可直接 curl 下载

---

## 历史转写文本检索

### 本地检索

```bash
# 以下命令中的 <OUTPUT_DIR> 替换为实际输出路径（即 Step 0.5 确认的目录）

# 按日期前缀（替换 {YYYYMMDD} 为实际日期，如 20260321）
ls <OUTPUT_DIR> | grep "^{YYYYMMDD}"

# 按文件名关键词
ls <OUTPUT_DIR> | grep "关键词"

# 按 TaskId 精确查找
ls <OUTPUT_DIR> | grep "<taskId>"

# 查看某条任务的元数据
cat <OUTPUT_DIR>/<文件名>_meta.json
```

### OSS 检索

- 文件名以时间戳开头，控制台默认按字典序展示即为时间顺序
- 前缀筛选 `transcribe/transcript/{YYYYMMDD}` 可快速定位某天的文件
