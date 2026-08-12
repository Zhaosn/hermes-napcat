<div align="center">

# hermes-napcat

**[Hermes Agent](https://github.com/NousResearch/hermes-agent) 的 NapCat（QQ / OneBot 11）平台插件**

[![PyPI](https://img.shields.io/pypi/v/hermes-napcat?color=blue)](https://pypi.org/project/hermes-napcat/)
[![Python](https://img.shields.io/pypi/pyversions/hermes-napcat)](https://pypi.org/project/hermes-napcat/)
[![License](https://img.shields.io/github/license/shubyi/hermes-napcat)](LICENSE)

[English](README.md) · [中文](README.zh.md)

</div>

通过 [NapCat](https://github.com/NapNeko/NapCatQQ) 的 OneBot 11 反向 WebSocket 将 Hermes 接入 QQ。在任意 QQ 群或私聊中与 AI 助手对话，支持完整的群管理功能和管理员权限控制。

以 **标准 Hermes 插件** 安装（`~/.hermes/plugins/napcat/`），**不修改任何 Hermes 核心源码**——升级 Hermes 无需重装。

```
QQ客户端 ──── NapCat ──WS拨入──▶ hermes-napcat（插件） ──▶ Hermes（大模型）
                                    │
                                    └── 一条 Universal 全双工 WS：事件 + API ──┐
                                      （反向 WS 服务端，默认 ws://0.0.0.0:18801/onebot/v11）
```

---

## 上游与来源

本仓库 **fork 自** [shubyi/hermes-napcat](https://github.com/shubyi/hermes-napcat)。

- **上游（shubyi/hermes-napcat）**：以"打补丁进 Hermes 源码树"的方式安装 NapCat
  适配器（向 `gateway/`、`tools/`、`toolsets.py` 等注入文件）。
- **本 fork（plugin 版）**：把同一套 QQ / NapCat 集成重写为**标准 Hermes 插件**
  （`~/.hermes/plugins/napcat/`），零核心源码改动，升级 Hermes 免维护，走官方插件系统安装。

代码谱系：`main`（本 fork 的插件版）提交历史即包含上游全部提交；上游原版另存于
`upstream-main` 分支，可对照 diff。

---

## 功能特性

- **群聊 & 私聊** — 群聊 @机器人，私聊直接发消息
- **群共享会话** — 整个群共用一个上下文，消息自动带发送者昵称前缀
- **管理员系统** — 限制 QQ 管理指令（禁言、踢人等）只有指定 QQ 才能使用
- **48 个 QQ 工具** — 消息、群管理、文件操作、OCR、表情回应等一应俱全
- **多媒体支持** — 图片、语音（ffmpeg 转 WAV）、视频、文件上传下载
- **引用消息上下文** — 回复消息时自动携带被引用内容
- **Universal 反向 WS** — 事件与 API 共用一条连接，无需额外 HTTP API
- **一键安装向导** — 只安装插件 + 写入配置，不做多余的事

---

## 环境要求

- Python 3.11+
- [Hermes Agent](https://github.com/NousResearch/hermes-agent)（含插件系统，即任何较新的 `main` 构建）
- [NapCat](https://github.com/NapNeko/NapCatQQ)（需开启「反向 WebSocket」项）
- `aiohttp >= 3.9`（随 hermes-napcat 一起安装）
- `ffmpeg` *（可选，用于语音消息转录）*

---

## 快速开始

### 1. 安装

> ⚠️ 本 fork 的**插件版（0.3.0）**通过 GitHub 安装。PyPI 上的 `hermes-napcat` 仍是
> 旧版 **0.2.x（补丁式，会修改 Hermes 核心源码）**——**不要**用 `pip install hermes-napcat`。

```bash
pip install git+https://github.com/Zhaosn/hermes-napcat.git
```

确认装到的是插件版：

```bash
pip show hermes-napcat    # Version: 0.3.0
```

### 2. 运行安装向导

```bash
hermes-napcat setup
```

向导会把插件复制到 `~/.hermes/plugins/napcat/`，并把 `platforms.napcat` 平台块合并进 `~/.hermes/config.yaml`。

非交互式安装（脚本/CI 环境）：

```bash
hermes-napcat setup --qq 123456789 --admins "123456789,987654321" --token "<napcat-token>"
```

> hermes-napcat **不负责安装 / 启动 / 配置 NapCat** —— 你需要自行安装并运行
> NapCat（例如使用[官方安装器](https://github.com/NapNeko/NapCat-Installer)）。

### 3. 配置 NapCat 的反向 WebSocket

在 NapCat 的网络设置中添加一个反向 WS 项：

| 设置 | 值 |
|------|-----|
| 反向 WS：本端作客户端主动连远端 | 开启 |
| 服务端 WebSocket URL | `ws://127.0.0.1:18801/onebot/v11` |
| 连接角色 | Universal（全双工，API + 事件） |
| 消息上报格式 | Array（结构化数组） |
| 鉴权 Token | 与 `--token` 一致（可不填） |

### 4. 启动 Hermes 网关

```bash
nohup hermes gateway run > /tmp/hermes-gateway.log 2>&1 &
```

网关发现插件后会在 `ws://0.0.0.0:18801/onebot/v11` 开启反向 WS 监听，然后**仅等待 NapCat 建立连接**——无需其它操作。

---

## 配置说明

`~/.hermes/config.yaml`：

```yaml
platforms:
  napcat:
    enabled: true
    extra:
      ws_port: 18801                # 反向 WS 监听端口
      ws_path: "/onebot/v11"        # 反向 WS 路径（须与 NapCat 的 URL 一致）
      access_token: ""              # NapCat 反向 WS 鉴权 Token
      self_id: "123456789"          # 机器人 QQ 号（留空则连接后自动探测）
      dm_policy: "allowlist"        # open | allowlist | disabled
      allow_from: []                # 允许私聊的 QQ 号
      group_policy: "open"          # open | allowlist | disabled
      group_allow_from: []          # 缺省回退到 allow_from
      admins: []                    # 可使用管理指令的 QQ 号
      media_max_mb: 5

platform_toolsets:
  napcat:
    - hermes-cli                    # 终端 / 文件 / 搜索等核心工具
    - hermes-napcat                 # 48 个 qq_* 工具（插件工具集，默认启用）

group_sessions_per_user: false      # 整个群共享一个会话
```

等价的环境变量（通过插件的 `env_enablement_fn` 自动注入）：

```
NAPCAT_ACCESS_TOKEN  NAPCAT_WS_PORT  NAPCAT_WS_HOST  NAPCAT_WS_PATH
NAPCAT_SELF_ID       NAPCAT_DM_POLICY  NAPCAT_GROUP_POLICY
NAPCAT_ALLOWED_USERS（逗号分隔）  NAPCAT_ADMINS（逗号分隔）
NAPCAT_ALLOW_ALL_USERS  NAPCAT_HOME_CHANNEL
```

> **网关级鉴权：** 插件声明了 `allowed_users_env` / `allow_all_env`，核心的
> `_is_user_authorized()` 开箱即用。除非你显式设置 `NAPCAT_ALLOWED_USERS` 或
> `NAPCAT_ALLOW_ALL_USERS`，否则由适配器自身的 `dm_policy` / `group_policy` /
> `admins` 把关。

---

## 管理员系统

在 napcat 平台块中设置 `admins` 来限制谁可以使用管理指令：

```yaml
platforms:
  napcat:
    extra:
      admins: ["123456789", "987654321"]
```

若 `admins` 为空，则所有人均可调用任意工具（开放模式）。

| 操作 | 普通用户 | 管理员 |
|------|:-------:|:------:|
| 搜索、查询、写代码、读文件等常规功能 | ✅ | ✅ |
| QQ 管理工具（禁言、踢人、设置管理员等） | ❌ | ✅ |
| 破坏性系统操作 | ❌ | ⚠️ 需二次确认 |

**仅管理员可用的 QQ 工具：** `qq_kick_group_member`、`qq_mute_group_member`、
`qq_set_group_admin`、`qq_set_group_name`、`qq_set_group_whole_ban`、
`qq_leave_group`、`qq_set_group_portrait`、`qq_set_group_special_title`、
`qq_set_essence_msg`、`qq_delete_essence_msg`、`qq_send_group_notice`、
`qq_delete_group_notice`、`qq_delete_group_file`、`qq_delete_friend`、
`qq_handle_friend_request`、`qq_handle_group_request`。

---

## 可用工具

| 分类 | 工具 |
|------|------|
| 消息 | `qq_send_message`、`qq_recall_message`、`qq_set_msg_emoji_like`、`qq_forward_message`、`qq_send_group_forward_msg`、`qq_send_private_forward_msg`、`qq_mark_msg_as_read` |
| 历史记录 | `qq_get_group_msg_history`、`qq_get_friend_msg_history`、`qq_get_essence_msg_list`、`qq_set_essence_msg`、`qq_delete_essence_msg` |
| 用户 & 好友 | `qq_get_user_info`、`qq_get_friend_list`、`qq_like_user`、`qq_poke`、`qq_set_friend_remark`、`qq_delete_friend`、`qq_handle_friend_request` |
| 群信息 | `qq_get_group_info`、`qq_get_group_list`、`qq_get_group_member_info`、`qq_get_group_member_list`、`qq_get_group_honor_info`、`qq_get_group_at_all_remain` |
| 群管理 | `qq_mute_group_member`、`qq_kick_group_member`、`qq_set_group_admin`、`qq_set_group_name`、`qq_set_group_card`、`qq_set_group_whole_ban`、`qq_set_group_special_title`、`qq_leave_group`、`qq_set_group_sign`、`qq_set_group_remark`、`qq_set_group_portrait`、`qq_handle_group_request` |
| 群公告 | `qq_send_group_notice`、`qq_get_group_notice`、`qq_delete_group_notice` |
| 文件 | `qq_upload_file`、`qq_get_group_root_files`、`qq_get_group_file_url`、`qq_create_group_file_folder`、`qq_delete_group_file`、`qq_download_file` |
| 其他 | `qq_ocr_image`、`qq_translate_en2zh` |

---

## 工作原理

1. **安装** — `hermes_napcat/plugin/` → `~/.hermes/plugins/napcat/`。Hermes 启动时发现
   插件，调用 `register(ctx)`，把适配器注册进平台注册表（`gateway/run.py` 的
   `_create_adapter()` 优先查注册表）。
2. **连接** — 适配器在 `ws://0.0.0.0:{ws_port}{ws_path}` 开启反向 WS **服务端**；
   NapCat 作为客户端拨入（Universal 角色）。
3. **入站** — NapCat 上报消息事件（Array 格式）；适配器执行 DM / 群策略、为群消息加
   发送者前缀、拉取引用消息上下文，归一化成 `MessageEvent` 交给 `handle_message()`。
4. **出站** — 回复通过同一条 WS 发送 OneBot 11 动作（`send_group_msg` /
   `send_private_msg`、图片/语音/视频/文件），用 `echo` 关联响应；发送前把
   Markdown 转成 QQ 友好的纯文本。

### 会话隔离策略

| 聊天类型 | 会话键 |
|----------|--------|
| 私聊（DM） | 每个 QQ 号独立会话 |
| 群聊（`group_sessions_per_user: false`） | 整个群共享一个会话 |
| 群聊（`group_sessions_per_user: true`） | 每人在每个群各自独立会话 |

---

## CLI 命令参考

| 命令 | 说明 |
|------|------|
| `hermes-napcat setup` | 交互式安装向导 —— 安装插件 + 写入配置 |
| `hermes-napcat install` | 非交互式安装（`--qq --admins --ws-port --ws-path --token`） |
| `hermes-napcat uninstall` | 移除插件 + 清理配置块 |
| `hermes-napcat status` | 查看插件 / 配置安装状态 |

没有 NapCat 进程管理命令 —— NapCat 由你独立运行，网关启动后它会自动连上。

---

## 卸载

```bash
hermes-napcat uninstall
```

删除 `~/.hermes/plugins/napcat/`，并清理 `config.yaml` 里的 `platforms.napcat` /
`platform_toolsets.napcat`。NapCat 进程不受影响。

---

## 常见问题排查

| 现象 | 原因 / 解决 |
|------|------------|
| 网关日志显示没有 WS 连接 | NapCat 反向 WS 项必须指向 `ws://127.0.0.1:{ws_port}{ws_path}` 且为 Universal 角色 |
| 握手 `403` | `access_token` 与 NapCat 反向 WS 项里配置的不一致 |
| `ECONNREFUSED 127.0.0.1:18801` | 网关未运行（`hermes gateway run`），或端口被占用——改 `ws_port` |
| 群里不回消息 | 群聊需要 @机器人（或将成员加入 allow_from 并设 `group_policy: allowlist`） |
| `Permission denied: only admins` | 发送者不在 `admins`；加入其 QQ 号或设 `admins: []` |
| `hermes plugins list` 里看不到 | 插件目录必须是 `~/.hermes/plugins/napcat/`，含 `plugin.yaml` + `__init__.py`；重跑 `hermes-napcat setup` |

### 特定 API 提供商说明

部分 LLM API 提供商会拦截 OpenAI SDK 默认的 `AsyncOpenAI/Python X.X.X` User-Agent。
若遇到 `403 unsupported_user_agent`，请在 `~/.hermes/hermes-agent/run_agent.py`
中为你的提供商加请求头覆盖（参见 Hermes 文档）——这与 NapCat 插件无关。

---

## 许可证

MIT
