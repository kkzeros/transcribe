# 配置教程：阿里云 OSS + 通义听悟

## 一、阿里云账号准备

注册阿里云账号并完成实名认证（国内云服务必须步骤）。

---

## 二、创建 OSS Bucket

### 2.1 购买存储资源包

前往 OSS 控制台购买存储资源包。当前最低可选规格（以阿里云官方产品说明为准）：

> **标准 - 本地冗余存储 / 中国内地通用 / 40GB / 6 个月**

选择最低配置即可满足本 skill 的使用需求。

> ⚠️ 如果从 OSS 下载资源（如读取转写结果文件），会产生**外网流出流量**费用，请关注控制台费用详情，避免意外扣费。

### 2.2 创建 Bucket

- 地域：华北（与通义听悟服务同区，降低延迟）
- 存储类型：标准存储
- 读写权限：公共读（供通义听悟服务拉取音视频文件）

### 2.3 创建目录结构

在 Bucket 下创建以下目录（在控制台手动创建，或首次上传文件时自动生成）：

```
transcribe/
├── media/       ← 上传的音视频原文件
└── transcript/  ← 转写结果归档
```

> 目录名称可自定义，但需同步修改 `scripts/upload_oss.py` 和 `scripts/get_result.py` 中的对应常量。

### 2.4 配置生命周期规则（推荐）

音视频原文件转写完成后无需长期保留，建议设置自动清理规则，减少存储占用和费用：

- 前往 Bucket → 数据管理 → 生命周期
- 新建规则，配置如下：
  - **前缀**：`transcribe/media/`
  - **文件类型**：当前版本
  - **操作**：到期后删除（建议 3～7 天，按实际需求设置）

> 如果请求量较大，也应关注 `transcribe/transcript/` 目录的数据累积量，根据实际情况决定是否对归档结果设置清理周期。

---

## 三、开通通义听悟 + 创建应用

### 3.1 开通服务

前往通义听悟工作台：

```
https://nls-portal.console.aliyun.com/tingwu/overview
```

开通通义听悟服务。截止目前提供 **90 天免费额度**，一切以阿里云官方产品说明页为准。

初期使用或需求量较小，免费版完全够用。

### 3.2 购买资源包（可选）

如有付费需求，可参考听悟 ASR 资源包：

```
https://common-buy.aliyun.com/?commodityCode=sfm_TingwuDiscountASR_dp_cn
```

### 3.3 创建项目，获取 AppKey

在工作台内新建项目：

- **项目名称**：自定义
- **回调方式**：选「不设置回调」

  > 本 skill 脚本采用**轮询**方式查询任务状态，无需配置回调，同时避免将服务器 IP 暴露给外部服务。如有需要可改为 HTTP POST 回调，但需相应修改 `scripts/query_task.py`。

创建后在项目详情页获取 **AppKey**，保存备用。

---

## 四、创建 RAM 用户 + 配置权限

前往 RAM 控制台：

```
https://ram.console.aliyun.com/overview
```

### 4.1 创建用户，获取 AccessKey

左侧菜单 → **用户** → 创建用户：

- 访问方式：勾选「OpenAPI 调用访问」→ 选择**永久 AccessKey**
- 创建后立即保存 **AccessKey ID** 和 **AccessKey Secret**（Secret 只显示一次）

### 4.2 创建 OSS 权限策略

左侧菜单 → **权限管理** → **权限策略** → 新建权限策略 → 选择「脚本编辑」，粘贴以下 JSON：

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "oss:GetBucketStat",
      "Resource": "acs:oss:*:*:<YOUR_BUCKET_NAME>"
    },
    {
      "Effect": "Allow",
      "Action": [
        "oss:PutObject",
        "oss:GetObject",
        "oss:DeleteObject",
        "oss:InitiateMultipartUpload",
        "oss:UploadPart",
        "oss:CompleteMultipartUpload",
        "oss:AbortMultipartUpload",
        "oss:ListParts"
      ],
      "Resource": "acs:oss:*:*:<YOUR_BUCKET_NAME>/*"
    }
  ]
}
```

> 将 `<YOUR_BUCKET_NAME>` 替换为第二步创建的 Bucket 名称。

此策略包含：查看 Bucket 状态、上传文件、获取文件、删除文件，以及大文件/流式上传所需的分片上传权限。

> 阿里云官方默认建议策略（`oss:ListBuckets`）较宽泛，此处做了收窄，仅授权指定 Bucket 的必要操作。

### 4.3 为用户授权

左侧菜单 → **用户** → 找到刚创建的 RAM 用户 → 点击「授权」→ 在弹窗中搜索并添加以下两个权限策略：

| 策略 | 说明 |
|------|------|
| 刚创建的自定义 OSS 策略 | 操作指定 Bucket 的权限 |
| `AliyunTingwuFullAccess` | 调用通义听悟服务的权限 |

确认授权后，该 RAM 用户即具备操作 OSS 和使用通义听悟的完整权限。

---

## 五、填写 .env

将以上步骤获取的参数填入 skill 根目录的 `.env` 文件：

```ini
ALIBABA_CLOUD_ACCESS_KEY_ID=       # RAM 用户的 AccessKey ID
ALIBABA_CLOUD_ACCESS_KEY_SECRET=   # RAM 用户的 AccessKey Secret
TINGWU_APP_KEY=                    # 通义听悟项目的 AppKey
TINGWU_REGION=cn-beijing           # 听悟服务地域，按实际开通地域填写
OSS_BUCKET=                        # Bucket 名称
OSS_ENDPOINT=oss-cn-beijing.aliyuncs.com  # OSS Endpoint，与 Bucket 地域一致
```

---

## 六、注意事项

**地域限制**

OSS 和通义听悟均部署在中国内地，适合服务器在国内的 OpenClaw 环境。若使用海外服务器，网络延迟会相应增加，且 OpenClaw 对较长时间运行的任务可能存在追踪超时的问题。

**API 文档参考**

本 skill 仅对常见错误进行了捕获和提示，完整 API 文档参考：

```
https://api.aliyun.com/document/tingwu/2022-09-30/CreateMeetingTrans
```
