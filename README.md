# 🎙 Transcribe — 音视频转写 Skill

将在线视频 URL、本地音视频文件，通过**通义听悟 API** 转写为带时间戳、说话人标注的 Markdown 文字稿，同时归档到**阿里云 OSS**。

适用于 [OpenClaw](https://clawhub.ai) / Claude Code 环境。

---

## 功能

- 支持 yt-dlp 可解析的在线视频链接（流式下载，无需落盘）
- 支持本地音视频文件（mp3 / mp4 / m4a / wav 等）
- 支持已公开的 HTTP 直链
- 输出带时间戳、说话人标注的 Markdown 文字稿 + 摘要
- 转写结果同步上传到阿里云 OSS 归档
- 账号级错误（欠费/未开通）自动识别并中断，不静默失败

---

## 前置条件

| 依赖 | 说明 |
|------|------|
| Python 3.8+ | 运行脚本 |
| ffmpeg | 音频转码（`setup.sh` 自动安装） |
| yt-dlp | 视频下载（`setup.sh` 自动安装） |
| 阿里云 RAM 账号 | 需要 OSS 读写权限 + 通义听悟调用权限 |
| 通义听悟 AppKey | 在 [tingwu.console.aliyun.com](https://tingwu.console.aliyun.com) 项目管理中获取 |
| 阿里云 OSS Bucket | 用于中转音视频文件，建议开启生命周期（media 目录 3 天自动删除） |

---

## 安装

Clone 到 OpenClaw 的 skills 目录：

```bash
git clone https://github.com/<your-github-username>/transcribe-openclaw.git ~/.openclaw/skills/transcribe-openclaw
```

> clawhub 市场版本即将上线，届时可通过 `clawhub install transcribe` 一键安装。

---

## 配置

> 首次使用？请先阅读 [完整配置教程](references/setup-guide.md)，包含阿里云 OSS、通义听悟开通、RAM 权限配置的完整步骤。

### 1. 创建 `.env`

```bash
cp .env.example .env
```

编辑 `.env` 填入真实值：

```ini
# 阿里云 RAM 访问密钥
ALIBABA_CLOUD_ACCESS_KEY_ID=
ALIBABA_CLOUD_ACCESS_KEY_SECRET=

# 通义听悟 AppKey
TINGWU_APP_KEY=

# 通义听悟地域（默认 cn-beijing）
TINGWU_REGION=cn-beijing

# OSS Bucket 名称
OSS_BUCKET=

# OSS Endpoint（格式：oss-{region}.aliyuncs.com）
OSS_ENDPOINT=oss-cn-beijing.aliyuncs.com

# 可选：视频平台 cookie 文件路径（用于 IP 受限或需登录的平台）
COOKIES_FILE=
```

`.env` 和 `cookies.txt` 已列入 `.clawhubignore`，不会随 skill 发布，**请勿提交到版本库**。

### 2. 配置 cookie（视视频源情况而定）

**什么情况下需要 cookie？**

以下情况在 URL 解析阶段就会失败，必须提供 cookie：

- 视频需要登录才能观看（会员内容、私密视频等）
- 服务器 IP 被视频平台风控拦截（云服务器常见，返回 403 / 412 等）
- 平台对非浏览器请求有访问限制

如果不配置 cookie 而直接使用在线 URL，skill 可能在第一步解析视频时就报错，无法继续。

**如何获取 cookie？**

在**本地电脑**上（已登录目标平台的浏览器），执行以下命令导出：

```bash
# chrome 可替换为 firefox / safari / edge
yt-dlp --cookies-from-browser chrome \
  --cookies cookies.txt \
  --get-title "https://www.example.com/video/xxx"
```

命令成功后会在当前目录生成 `cookies.txt`，内容为 Netscape 格式的登录态 cookie。

**部署到服务器**

将本地生成的 `cookies.txt` 上传到 skill 根目录，然后在 `.env` 中配置：

```ini
COOKIES_FILE=cookies.txt
```

设置后，skill 在执行 yt-dlp 下载时会自动读取该文件并传入 `--cookies` 参数，无需每次手动指定。

> ⚠️ **注意事项**：
> - cookie 包含账号登录态，**严禁提交到版本库**（已在 `.gitignore` 排除）
> - cookie 有时效性，登录态失效后需重新在本地导出并替换
> - cookie 仅在本地浏览器环境可直接读取，服务器上无法使用 `--cookies-from-browser`，需提前从本地导出后传入

---

## 使用

在 OpenClaw 或 Claude Code 中，直接描述需求即可触发：

> "帮我转写这个视频 https://..."
> "把这个音频文件转成文字稿"
> "用听悟转写 /path/to/audio.mp3"

skill 会自动执行依赖检查、路径确认、转写全流程。

---

## 输出

| 文件 | 内容 |
|------|------|
| `{ts}-{name}-{taskId}.md` | 转写全文（带时间戳、说话人标注）+ 摘要 |
| `{ts}-{name}-{taskId}_meta.json` | task_id、文件名、本地路径、OSS 路径、听悟临时 URL |

同时上传到 OSS：

```
<bucket>/
├── transcribe/media/        # 音视频原文件（3 天后自动删除）
└── transcribe/transcript/   # 转写结果 md（永久保留）
```

---

## 目录结构

```
transcribe-openclaw/
├── SKILL.md            # skill 主指令（agent 执行逻辑）
├── .env.example        # 环境变量模板
├── .clawhubignore      # 发布排除规则
├── scripts/
│   ├── setup.sh        # 依赖自检（幂等）
│   ├── pipeline.py     # 主流程入口
│   ├── upload_oss.py   # OSS 上传模块
│   ├── create_task.py  # 创建转写任务
│   ├── query_task.py   # 查询任务状态
│   ├── get_result.py   # 获取转写结果
│   └── errors.py       # 错误码解析
└── references/
    ├── api_overview.md # 通义听悟 API 速查
    ├── errors.md       # 错误码速查
    └── requirements.txt
```

---

## 常见问题

**Q：yt-dlp 报 412 / 无法获取媒体流？**

服务器 IP 被平台风控拦截。解决方案：
1. 在本地导出 cookie 文件（见上方"配置 cookie"），传到服务器后在 `.env` 中指定路径
2. 或在本地下载好音频文件后，通过"本地文件"方式传入

**Q：转写超时？**

根据文件时长调整 `--timeout` 参数：< 10 分钟用 600s，10~30 分钟用 1800s，30~60 分钟用 3600s，更长则用时长（秒）× 3。

**Q：遇到 `BRK.InvalidService` / `BRK.OverdueTenant` 等错误？**

账号级问题，重试无效。请检查通义听悟服务是否已开通、账号是否欠费。详见 `references/errors.md`。

---

## 免责声明

本项目为纯开源工具，作为 [OpenClaw](https://clawhub.ai) 的一个 skill 接入，旨在帮助 AI agent 读取和理解音视频内容。

**第三方工具声明**

- 本项目使用 [yt-dlp](https://github.com/yt-dlp/yt-dlp) 进行音视频媒体流的解析与下载，yt-dlp 以 Unlicense 协议开源发布
- 本项目使用阿里云[通义听悟](https://tingwu.aliyun.com) API 完成音视频转写，该服务由阿里云提供，使用需遵守其服务协议

**使用限制**

- 本项目**严禁**用于侵犯他人版权的行为，包括但不限于：未经授权下载、传播、分发受版权保护的内容
- 本项目**严禁**用于任何直接或间接的商业盈利行为
- 用户应自行确保所处理的音视频内容具有合法的使用权限

**侵权处理**

若您认为本项目的使用涉及侵权，请通过 GitHub Issues 或平台私信联系，本人将在看到后第一时间处理。

本项目作者不对用户的使用行为承担任何法律责任，风险由使用者自行承担。

---

## License

MIT
