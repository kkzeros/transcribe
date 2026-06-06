---
name: transcribe
version: 1.0.0
platforms: [macos, linux]
description: >
  音视频转写 skill — 将在线视频 URL、本地音视频文件，通过通义听悟 API 转写为中文文字稿（Markdown 格式），
  同时归档到阿里云 OSS。当用户提到"转写"、"字幕"、"听悟"、"在线视频"、"把视频变成文字"、"音频转文字"、
  "视频转文字"、"yt-dlp"等相关需求时，立即使用本 skill，不要等用户明确说"用 transcribe skill"。
metadata:
  hermes:
    tags: [media, transcription, speech-to-text, aliyun, oss, yt-dlp]
    config:
      - key: transcribe.output_parent_dir
        description: 转写结果父目录；实际输出保存到该目录下的 transcribe-results 子目录
        default: ""
        prompt: 转写结果父目录
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
required_environment_variables:
  - name: ALIBABA_CLOUD_ACCESS_KEY_ID
    prompt: 阿里云 AccessKey ID
    help: 需要具备 OSS 读写权限和通义听悟 API 调用权限
    required_for: OSS 上传和通义听悟 API 调用
  - name: ALIBABA_CLOUD_ACCESS_KEY_SECRET
    prompt: 阿里云 AccessKey Secret
    help: 与 ALIBABA_CLOUD_ACCESS_KEY_ID 配套
    required_for: OSS 上传和通义听悟 API 调用
  - name: TINGWU_APP_KEY
    prompt: 通义听悟 AppKey
    help: 在通义听悟控制台项目管理中获取
    required_for: 创建通义听悟离线转写任务
  - name: OSS_BUCKET
    prompt: OSS Bucket 名称
    help: 用于中转音视频文件和归档转写文本
    required_for: OSS 上传
  - name: OSS_ENDPOINT
    prompt: OSS Endpoint
    help: 例如 oss-cn-beijing.aliyuncs.com，需与 Bucket 地域一致
    required_for: OSS 上传
---

# Transcribe — 音视频转写 Skill

将音视频内容转写为带时间戳、说话人标注的 Markdown 文字稿。

## 支持的输入方式

| 方式 | 示例 |
|------|------|
| 在线视频 URL | 支持 yt-dlp 可解析的视频平台链接 |
| 本地音视频文件路径 | `/path/to/video.mp3` |
| 已公开的 HTTP 文件 URL | `https://example.com/audio.mp4` |

**输出**：保存到 Step 0.5 确认的目录下：

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

或直接用已知的安装路径：

```
~/.agents/skills/transcribe
~/.claude/skills/transcribe
~/.openclaw/skills/transcribe
~/.hermes/skills/media/transcribe
```

**第二步：运行依赖自检**

```bash
bash "$SKILL_ROOT/scripts/setup.sh"
```

幂等脚本：会在 skill 根目录创建 `.venv`，安装 Python 依赖，并检查 `ffmpeg` 与 `yt-dlp`。后续 Python 和 yt-dlp 命令必须使用：

```bash
PYTHON_BIN="$SKILL_ROOT/.venv/bin/python3"
YT_DLP_BIN="$SKILL_ROOT/.venv/bin/yt-dlp"
```

**第三步：检查 `.env` 文件**

检查 `$SKILL_ROOT/.env` 是否存在：
- **存在** → 继续
- **不存在** → 停止，提示用户：
  ```
  未找到 .env 文件，请在 skill 根目录下创建：
    cp "$SKILL_ROOT/.env.example" "$SKILL_ROOT/.env"
  然后编辑 .env 填入真实凭证（参考 .env.example 中的字段说明）
  ```

**第四步：解析 cookie 路径并优先复用本地缓存**

处理在线视频 URL 前，先检查 `$SKILL_ROOT/cookies/` 下是否已有当前来源 cookie：
- **已有且非空** → 直接使用，不要再从浏览器导出；
- **没有或后续 yt-dlp 仍因登录/风控失败** → 再提示用户选择导出或手动提供。

若没有可用 cookie，提示用户：
- 先在本机浏览器登录目标来源，然后允许脚本从浏览器导出 cookie；
- 或手动提供 Netscape 格式 cookie 文件，并保存到 `cookies/<source-alias>.cookies.txt`。

```bash
bash "$SKILL_ROOT/scripts/prepare_cookies.sh" "<视频URL>" chrome
```

脚本会根据 URL 自动生成来源别名，必要时自动创建 `$SKILL_ROOT/cookies/`，并使用固定 cookie 文件：

```
$SKILL_ROOT/cookies/<source-alias>.cookies.txt
```

默认情况下，来源别名由 URL host 自动生成。

重要：不要读取或修改 `.env` 来处理 cookie 复用；`.env` 只用于敏感凭证和基础配置。

新窗口或新会话处理在线视频 URL 时，先检查 `$SKILL_ROOT/cookies/` 下已有的 `*.cookies.txt` 文件。同一内容来源可能同时存在主域名、短链域名、移动端域名、分享域名等多个入口，这些 URL 生成的默认来源别名可能不同，但实际登录态 cookie 往往可以复用。模型需要根据 URL 语义和已有 cookie 文件名做一次兼容判断：如果目标 URL 明显属于已有 cookie 覆盖的同一来源，不要重新导出 cookie，优先复用已有文件。

复用方式：使用已有 cookie 文件名去掉 `.cookies.txt` 后得到的别名设置 `TRANSCRIBE_COOKIE_ALIAS`，再运行 `prepare_cookies.sh`。例如已有：

```
$SKILL_ROOT/cookies/source-a.cookies.txt
```

则复用时运行：

```bash
TRANSCRIBE_COOKIE_ALIAS=source-a bash "$SKILL_ROOT/scripts/prepare_cookies.sh" "<视频URL>" chrome
```

如果无法从 URL 生成来源别名，不使用默认 cookie。可临时指定来源别名：

```bash
TRANSCRIBE_COOKIE_ALIAS=source-a bash "$SKILL_ROOT/scripts/prepare_cookies.sh" "<视频URL>" chrome
```

随后按当前 URL 获取来源 cookie：

```bash
COOKIE_ALIAS=$("$PYTHON_BIN" - "<视频URL>" "$SKILL_ROOT" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[2]) / "scripts"))
from config import cookie_alias_from_url
print(cookie_alias_from_url(sys.argv[1]))
PY
)

COOKIE_PATH="$SKILL_ROOT/cookies/${COOKIE_ALIAS}.cookies.txt"

if [ -n "$COOKIE_ALIAS" ] && [ -s "$COOKIE_PATH" ]; then
  COOKIES_OPT=(--cookies "$COOKIE_PATH")
  echo "Cookie 文件已就绪：$COOKIE_PATH"
else
  COOKIES_OPT=()
  echo "未找到当前来源 cookie，yt-dlp 以匿名模式运行"
fi
```

后续所有 yt-dlp 命令统一使用 `"${COOKIES_OPT[@]}"`，无需手动拼路径。
若已设置 `COOKIES_OPT` 但 yt-dlp 仍报登录、403、412、风控或 cookie 失效类错误，停止当前转写，提示用户重新登录浏览器后再次运行 `prepare_cookies.sh` 导出，不要反复匿名重试。

---

## Step 0.5：输出路径确认（每次调用前执行）

默认原则：**除非用户明确要求保存到某个目录，否则不要在命令里显式传 `--output-dir`**。让 `pipeline.py` / `get_result.py` 自己按下列规则解析输出目录。

Codex 运行时可能有自己的 workspace/output 目录约定；本 skill 不主动使用该目录。用户未指定输出位置时，优先使用 skill 安装目录的上一层创建 `transcribe-results`，避免不同项目 workspace 启动导致结果分散。

读取 `$SKILL_ROOT/.env` 中的 `TRANSCRIBE_OUTPUT_PARENT_DIR`：

- **不为空且路径存在** → 输出到：
  ```
  <TRANSCRIBE_OUTPUT_PARENT_DIR>/transcribe-results
  ```
  若该目录还不存在，脚本会自动创建。

- **为空或路径不存在** → 根据 skill 安装位置自动推导：
  ```
  ~/.agents/skills/transcribe   -> ~/.agents/transcribe-results
  ~/.claude/skills/transcribe   -> ~/.claude/transcribe-results
  ~/.openclaw/skills/transcribe -> ~/.openclaw/transcribe-results
  ~/.hermes/skills/media/transcribe -> ~/.hermes/skills/media/transcribe-results
  ```

Hermes 若通过 `metadata.hermes.config` 配置了 `transcribe.output_parent_dir`，需要在运行前把该值同步到 `.env` 的 `TRANSCRIBE_OUTPUT_PARENT_DIR`。不要因为平台存在默认 output 目录就主动覆盖本 skill 的默认目录策略。

只有当用户明确说“保存到/输出到某个目录”时，才使用命令行 `--output-dir PATH` 临时覆盖上述规则。

---

## Step 1：执行转写

> 以下命令中 `$SKILL_ROOT` 为 skill 根目录绝对路径（Step 0 已确定）。
> 若 Step 0 解析出了 `COOKIES_OPT`，每条 yt-dlp 命令都使用它；未配置 cookie 时该数组为空。

### 方式 A：在线视频 URL（yt-dlp 可解析的平台）

```bash
TITLE=$("$YT_DLP_BIN" "${COOKIES_OPT[@]}" --get-title "<视频URL>")
"$YT_DLP_BIN" "${COOKIES_OPT[@]}" -x --audio-format mp3 -o - "<视频URL>" | "$PYTHON_BIN" "$SKILL_ROOT/scripts/pipeline.py" --stdin "${TITLE}.mp3"
```

### 方式 B：本地文件

```bash
"$PYTHON_BIN" "$SKILL_ROOT/scripts/pipeline.py" "/path/to/file.mp3"
```

### 方式 C：已有公开 HTTP URL（文件可被听悟服务器直接访问）

```bash
"$PYTHON_BIN" "$SKILL_ROOT/scripts/pipeline.py" "https://example.com/audio.mp3"
```

### 方式 D：yt-dlp 取直链 → 先上传 OSS 再转写

适用场景：视频平台 CDN 直链有时效或需要 Headers，听悟无法直接拉取，需经 OSS 中转。

```bash
TITLE=$("$YT_DLP_BIN" "${COOKIES_OPT[@]}" --get-title "<视频URL>")
DIRECT_URL=$("$YT_DLP_BIN" "${COOKIES_OPT[@]}" -g "<视频URL>" | head -1)
OSS_URL=$("$PYTHON_BIN" "$SKILL_ROOT/scripts/upload_oss.py" --url "$DIRECT_URL" "${TITLE}.mp4")
"$PYTHON_BIN" "$SKILL_ROOT/scripts/pipeline.py" "$OSS_URL"
```

> **注意**：`yt-dlp -g` 返回原始视频格式（mp4/flv），不会转码为 mp3。
> 若需要 mp3，优先用方式 A（流式转码）。方式 D 适合服务器本地带宽有限、希望让 OSS 直接拉流的场景。

> **yt-dlp 下载失败时**（如需要登录、地区限制等），可先在本地手动下载音频文件，再用**方式 B** 传入本地路径处理。

### 可选参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--timeout N` | 最长等待转写完成时间（秒） | 600（10 分钟） |
| `--output-dir PATH` | 结果保存目录（覆盖默认输出目录） | 同 Step 0.5 |

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
"$PYTHON_BIN" "$SKILL_ROOT/scripts/query_task.py" <taskId>

# 状态为 COMPLETED 时直接取结果
# 用户未明确指定输出目录时，不要传 --output-dir
"$PYTHON_BIN" "$SKILL_ROOT/scripts/get_result.py" <taskId> --input-name "原文件名.mp3"
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

### OSS 配置或上传失败（遇到立即停止并提醒用户）

本 skill 的离线转写需要先把本地音视频上传到 OSS，再把可访问的 HTTPS URL 交给通义听悟。若 OSS 不可用，后续转写无法继续，**不要反复重试或改用本地路径提交听悟**。

出现以下情况时，停止当前任务并提示用户按 `references/setup-guide.md` 操作：

| 现象 | 可能原因 | 建议提示用户 |
|------|----------|-------------|
| 上传阶段报 `NoSuchBucket` / `NoSuchBucketError` / Bucket 不存在 | `.env` 中 `OSS_BUCKET` 写错，或尚未创建 Bucket | 请先创建 OSS Bucket，并按 `references/setup-guide.md` 的“二、创建 OSS Bucket”和“四、创建 RAM 用户 + 配置权限”配置 |
| 上传阶段报 `AccessDenied` / `SignatureDoesNotMatch` / 403 | RAM AK 无 OSS 权限，Secret 错误，或 Endpoint/Bucket 地域不匹配 | 请检查 `.env` 中 AK、`OSS_BUCKET`、`OSS_ENDPOINT`，并按 `references/setup-guide.md` 给 RAM 用户授权 |
| 上传阶段报网络或 Endpoint 解析失败 | `OSS_ENDPOINT` 不正确或网络无法访问 OSS | 请检查 Endpoint 格式，例如 `oss-cn-beijing.aliyuncs.com`，并确认 Bucket 地域一致 |
| 听悟返回 `BRK.InvalidOssBucket` | 听悟无法拉取 `FileUrl`，常见于 Bucket/文件不可访问、URL 过期、权限或公共访问策略不满足 | 请按 `references/setup-guide.md` 检查 Bucket 权限、生命周期和 RAM 授权；必要时重新上传并生成新的签名 URL |

向用户说明时要明确列出缺少哪些配置，不要只说“OSS 失败”：

```
OSS 中转不可用，通义听悟离线转写无法直接读取本地文件。
请在 skill 根目录 .env 中配置：
  OSS_BUCKET=
  OSS_ENDPOINT=
  ALIBABA_CLOUD_ACCESS_KEY_ID=
  ALIBABA_CLOUD_ACCESS_KEY_SECRET=

如果还没有创建 Bucket 或 RAM 权限，请按 references/setup-guide.md 的配置流程操作。
```

### 账号级严重错误（遇到立即停止并提醒用户）

以下错误表示账号或服务本身存在问题，继续重试无意义，**必须中断任务并向用户发出明确警告**：

| 错误码 | 含义 | 建议提示用户 |
|--------|------|-------------|
| `BRK.InvalidService` | 账号未开通通义听悟服务 | 请前往 https://tingwu.console.aliyun.com 开通服务后重试 |
| `BRK.OverdueService` | 账号服务已超配额 | 当前用量已达上限，请检查套餐或联系阿里云升配 |
| `BRK.OverdueTenant` | 账号已欠费 | 请前往阿里云控制台充值后重试 |
| `BRK.InvalidTenant` | 账号服务未开通或已欠费 | 请确认通义听悟服务已开通且账号余额充足 |
| `BRK.ServiceLinkedRoleNotExist` | 缺少听悟服务关联角色 | 请在 RAM 控制台授权 `AliyunServiceRoleForTingwuPaaS`，配置步骤见 `references/setup-guide.md` |

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
