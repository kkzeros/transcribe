# 🎙 Transcribe — 音视频转写 Skill

将用户有权处理的在线视频 URL、本地音视频文件，通过**通义听悟 API** 转写为带时间戳、说话人标注的 Markdown 文字稿，同时归档到**阿里云 OSS**。

适用于 Codex / Claude Code / [OpenClaw](https://clawhub.ai) / Hermes 环境。

---

## 功能

- 支持用户有权访问和处理的在线视频 URL
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
| yt-dlp | 音视频来源解析（`setup.sh` 自动安装） |
| 阿里云 RAM 账号 | 需要 OSS 读写权限 + 通义听悟调用权限 |
| 通义听悟 AppKey | 在 [tingwu.console.aliyun.com](https://tingwu.console.aliyun.com) 项目管理中获取 |
| 阿里云 OSS Bucket | 用于中转音视频文件，建议开启生命周期（media 目录 3 天自动删除） |

---

## 部署建议

本 skill 会调用阿里云通义听悟和 OSS。若部署在海外 VPS、海外 Hermes / OpenClaw / Claude Code 环境中，访问中国大陆区域的阿里云服务时可能出现延迟较高、上传较慢、任务轮询超时或偶发网络失败。

为提高稳定性，建议优先选择：

- 中国大陆地区的 VPS 或本地机器
- 与 OSS Bucket、通义听悟地域较近的服务器
- 具备优化回国线路的海外服务器，例如 CN2、CMI、9929 等线路
- 网络质量稳定、上传带宽充足的运行环境

如果必须部署在海外服务器，建议适当调大 `--timeout` 参数，并优先选择网络质量较好的 OSS 地域和线路。

---

## 安装

Clone 到目标平台的 skills 目录，例如 OpenClaw：

```bash
git clone https://github.com/kkzeros/transcribe.git ~/.openclaw/skills/transcribe
```

> clawhub 市场版本即将上线，届时可通过 `clawhub install transcribe` 一键安装。

## 给 AI Agent 的安装提示

如果你正在使用 Claude Code、Codex、Hermes 或 OpenClaw，可以直接把下面这句话发给你的 AI 助手：

> 请帮我安装这个音视频转写 skill：`https://github.com/kkzeros/transcribe`。安装后请阅读 README/SKILL.md，运行依赖检查，并引导我填写 `.env`；不要提交或泄露 `.env`、cookie、AccessKey 等敏感信息。

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

# 可选：转写结果父目录，最终保存到 <此目录>/transcribe-results
# 留空则按 skill 安装位置推导，例如 ~/.agents/transcribe-results
TRANSCRIBE_OUTPUT_PARENT_DIR=

```

`.env` 和 `cookies/` 已列入 `.clawhubignore`，不会随 skill 发布，**请勿提交到版本库**。

### 2. 配置 cookie（视视频源情况而定）

**什么情况下可能需要 cookie？**

以下情况可能需要用户自行提供访问凭证：

- 内容源要求登录后才能正常访问
- 目标平台对非浏览器请求有访问限制（云服务器常见，返回 403 / 412 等）
- 用户确认自己具备处理该内容的合法权限

如果不配置 cookie 而直接使用在线 URL，skill 可能在第一步解析来源时就报错，无法继续。

**如何获取 cookie？**

在**本地电脑**上（已登录目标来源的浏览器），运行辅助脚本导出当前来源 cookie：

```bash
bash scripts/prepare_cookies.sh "https://www.example.com/video/xxx" chrome
```

命令成功后会根据 URL 来源生成 `cookies/<source-alias>.cookies.txt`，内容为 Netscape 格式的登录态 cookie。

**部署到服务器**

如果需要在服务器运行，请先在本地电脑导出 cookie，再将生成的文件复制到服务器上的 skill 根目录：

```
cookies/<source-alias>.cookies.txt
```

后续处理同来源视频时，skill 会自动读取对应来源的 cookie 并传入 `--cookies` 参数。`.env` 不保存 cookie 路径。
首次运行时脚本会自动创建 `cookies/` 目录；只要对应来源文件存在且非空，就优先复用该文件，不会每次重新读取浏览器。
默认情况下，来源别名由 URL host 自动生成。若同一来源存在多个域名或短链，可临时指定已有 cookie 别名：

```bash
TRANSCRIBE_COOKIE_ALIAS=source-a bash scripts/prepare_cookies.sh "https://www.example.com/video/xxx" chrome
```

用户应自行确认目标平台规则和内容使用权限。

> ⚠️ **注意事项**：
> - cookie 包含账号登录态，**严禁提交到版本库**（`cookies/` 已在 `.gitignore` 排除）
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
transcribe/
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

**Q：yt-dlp 报 412 / 无法解析来源？**

服务器 IP 可能被平台风控拦截。解决方案：
1. 在本地导出 cookie 文件（见上方"配置 cookie"），把文件放到 skill 根目录的 `cookies/<source-alias>.cookies.txt`
2. 若已有 cookie 仍失败，重新登录浏览器后再次导出，替换对应来源 cookie 文件
3. 或在本地下载好音频文件后，通过"本地文件"方式传入

**Q：转写超时？**

根据文件时长调整 `--timeout` 参数：< 10 分钟用 600s，10~30 分钟用 1800s，30~60 分钟用 3600s，更长则用时长（秒）× 3。

**Q：遇到 `BRK.InvalidService` / `BRK.OverdueTenant` 等错误？**

账号级问题，重试无效。请检查通义听悟服务是否已开通、账号是否欠费。详见 `references/errors.md`。

---

## 合规使用说明

本项目是个人音视频知识管理工具，旨在帮助用户对自己有权处理的音视频内容进行转写、摘要和归档。

用户应确保输入内容符合以下条件之一：

- 用户本人拥有该内容的版权或使用权
- 已获得内容权利人授权
- 内容采用允许转写、摘要或再处理的开放许可
- 内容来源平台的服务条款允许当前使用方式
- 仅在法律允许的个人学习、研究或欣赏范围内使用，且不影响作品的正常使用，不损害权利人的合法权益

本项目不应用于：

- 未经授权下载、复制、传播、分发受版权保护的内容
- 批量搬运平台内容，或构建可替代原平台观看体验的内容库
- 绕过平台访问控制、付费限制、风控限制或其他技术措施
- 删除、隐藏或篡改内容来源、作者署名、版权声明等权利信息
- 未经授权的商业化内容处理、转载、分发或数据库构建

### 第三方服务声明

本项目可调用 [yt-dlp](https://github.com/yt-dlp/yt-dlp)、阿里云[通义听悟](https://tingwu.aliyun.com)、阿里云 OSS 等第三方工具或服务。用户应自行遵守相关工具、服务提供方以及目标内容平台的协议、规则和法律要求。

Cookie 仅用于用户在本地、已登录且有权访问的内容场景。Cookie 包含账号登录态，请勿提交到版本库或分享给他人。

若权利人认为本项目相关内容或示例存在侵权风险，请通过 GitHub Issues 联系，我会及时处理。

---

## License

MIT
