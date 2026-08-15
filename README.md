<div align="center">

# hermes-napcat

**[Hermes Agent](https://github.com/NousResearch/hermes-agent) 的 NapCat（QQ / OneBot 11）平台插件**

[![License](https://img.shields.io/github/license/shubyi/hermes-napcat)](LICENSE)

</div>

通过 [NapCat](https://github.com/NapNeko/NapCatQQ) 的 OneBot 11 反向 WebSocket 将 Hermes 接入 QQ。在任意 QQ 群或私聊中与 AI 助手对话，支持完整的群管理功能和管理员权限控制。

以 **标准 Hermes 插件** 安装：把本仓库的 `plugin/` 目录放到 `~/.hermes/plugins/napcat/` 即可——**不修改任何 Hermes 核心源码**，升级 Hermes 无需重装。

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
- **74 个 QQ 工具** — 消息、群管理、文件操作、OCR、表情回应等一应俱全
- **多媒体支持** — 图片、语音（ffmpeg 转 WAV）、视频、文件上传下载
- **引用消息上下文** — 回复消息时自动携带被引用内容
- **Universal 反向 WS** — 事件与 API 共用一条连接，无需额外 HTTP API
- **即插即用插件** — 把 `plugin/` 复制/软链进 `~/.hermes/plugins/` 即可，无 pip 包、无 CLI

---

## 环境要求

- Python 3.11+
- [Hermes Agent](https://github.com/NousResearch/hermes-agent)（含插件系统，即任何较新的 `main` 构建）
- [NapCat](https://github.com/NapNeko/NapCatQQ)（需开启「反向 WebSocket」项）
- `aiohttp >= 3.9`（插件会导入它——缺失时 `pip install aiohttp`）
- `ffmpeg` *（可选，用于语音消息转录）*

---

## 快速开始

### 1. 克隆并放置插件

> ⚠️ 本 fork 的**插件版**是**即插即用的插件目录**——没有 `pip install`、没有 CLI。
> PyPI 上的 `hermes-napcat` 仍是旧版 **0.2.x（补丁式，会修改 Hermes 核心源码）**——**不要**使用它。

```bash
git clone https://github.com/Zhaosn/hermes-napcat.git
mkdir -p ~/.hermes/plugins

# 复制（推荐，安装稳定）：
cp -r hermes-napcat/plugin ~/.hermes/plugins/napcat

# 或软链接（便于 git pull 更新——目录名必须是 napcat）：
ln -s "$PWD/hermes-napcat/plugin" ~/.hermes/plugins/napcat
```

Hermes 会扫描 `~/.hermes/plugins/<name>/`，目录内含 `plugin.yaml` 和
`__init__.py`（导出 `register(ctx)`）即被识别为插件。验证并启用：

```bash
hermes plugins list            # 应能看到 napcat
hermes plugins enable napcat
```

### 2. 配置

插件从 `~/.hermes/config.yaml` 的 `platforms.napcat` 块（见[配置说明](#配置说明)）
或下述 `NAPCAT_*` 环境变量读取设置。**`NAPCAT_WS_PORT` 与 `NAPCAT_ACCESS_TOKEN`
为必填**（两者缺一，适配器都不会启动），至少还需设置机器人管理员 QQ：

```yaml
platforms:
  napcat:
    enabled: true
    extra:
      ws_port: 18801            # 反向 WS 监听端口（必填，须与 NapCat 拨入地址一致）
      access_token: "..."       # 反向 WS 鉴权 Token（必填，须与 NapCat 配置一致）
      admins: ["123456789"]     # 可使用管理类 qq_* 工具的 QQ 号
```

> 插件**不负责安装 / 启动 / 配置 NapCat** —— 你需要自行安装并运行
> NapCat（例如使用[官方安装器](https://github.com/NapNeko/NapCat-Installer)）。
> 它只提供 Hermes 侧的适配器、工具与配置。

### 3. 配置 NapCat 的反向 WebSocket

在 NapCat 的网络设置中添加一个反向 WS 项：

| 设置 | 值 |
|------|-----|
| 反向 WS：本端作客户端主动连远端 | 开启 |
| 服务端 WebSocket URL | `ws://127.0.0.1:18801/onebot/v11` |
| 连接角色 | Universal（全双工，API + 事件） |
| 消息上报格式 | Array（结构化数组） |
| 鉴权 Token | 与 config / `NAPCAT_ACCESS_TOKEN` 一致（**必填**） |

### 4. 启动 Hermes 网关

```bash
nohup hermes gateway run > /tmp/hermes-gateway.log 2>&1 &
```

网关发现插件后会在 `ws://0.0.0.0:18801/onebot/v11` 开启反向 WS 监听，然后**仅等待 NapCat 建立连接**——无需其它操作。

### 5. 验证连通

```bash
hermes plugins list                # 应看到 napcat
tail -f /tmp/hermes-gateway.log    # 应看到：
#   NapCat: reverse WS listening on ws://0.0.0.0:18801/onebot/v11
#   NapCat: bot is <昵称> (QQ:<号>)   ← 连接成功 + 自动探测到机器人 QQ
```

实际对话测试：群里 @机器人 说一句话（或私聊直接发消息），期望机器人回复，
且群消息显示为「[你的群昵称]: 消息」。

若日志只有第一行、没有 `bot is ...`，说明 NapCat 没拨进来——检查 §3 的 URL / Token。

---

## 配置说明

`~/.hermes/config.yaml`：

```yaml
platforms:
  napcat:
    enabled: true
    extra:
      ws_port: 18801                # 反向 WS 监听端口（必填，须与 NapCat 拨入地址一致）
      ws_path: "/onebot/v11"        # 反向 WS 路径（须与 NapCat 的 URL 一致）
      access_token: "..."           # 反向 WS 鉴权 Token（必填，须与 NapCat 配置一致）
      http_url: ""                  # NapCat OneBot HTTP API 地址，如 http://127.0.0.1:3000（可选，仅用于独立进程的 cron 投递）
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
    - hermes-napcat                 # 74 个 qq_* 工具（插件工具集，默认启用）

group_sessions_per_user: false      # 整个群共享一个会话
```

等价的环境变量（通过插件的 `env_enablement_fn` 自动注入）：

```
NAPCAT_ACCESS_TOKEN（必填）  NAPCAT_WS_PORT（必填）  NAPCAT_WS_HOST  NAPCAT_WS_PATH
NAPCAT_HTTP_URL（可选，独立进程 cron 投递用）  NAPCAT_SELF_ID
NAPCAT_DM_POLICY  NAPCAT_GROUP_POLICY
NAPCAT_ALLOWED_USERS（逗号分隔）  NAPCAT_ADMINS（逗号分隔）
NAPCAT_ALLOW_ALL_USERS  NAPCAT_HOME_CHANNEL
```

> **独立进程的 cron 投递（可选）：** 若你用 `hermes cron run`（与 `hermes gateway`
> 分离的进程）执行 `deliver=napcat` 的任务，需在 NapCat 开启 HTTP 服务并把地址填进
> `http_url` / `NAPCAT_HTTP_URL`——否则该场景会报 "No live adapter for platform
> 'napcat'"。网关进程内的投递无需此项。

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
| 用户 & 好友 | `qq_get_user_info`、`qq_get_friend_list`、`qq_like_user`、`qq_poke`、`qq_set_friend_remark`、`qq_delete_friend`、`qq_handle_friend_request`、`qq_get_friends_with_category`、`qq_get_unidirectional_friend_list` |
| 群信息 | `qq_get_group_info`、`qq_get_group_list`、`qq_get_group_member_info`、`qq_get_group_member_list`、`qq_get_group_honor_info`、`qq_get_group_at_all_remain`、`qq_get_group_detail_info`、`qq_get_group_shut_list`、`qq_get_group_signed_list` |
| 群管理 | `qq_mute_group_member`、`qq_kick_group_member`、`qq_kick_group_members`、`qq_set_group_admin`、`qq_set_group_name`、`qq_set_group_card`、`qq_set_group_whole_ban`、`qq_set_group_special_title`、`qq_leave_group`、`qq_set_group_sign`、`qq_set_group_remark`、`qq_set_group_portrait`、`qq_handle_group_request`、`qq_set_group_todo`、`qq_complete_group_todo` |
| 群公告 | `qq_send_group_notice`、`qq_get_group_notice`、`qq_delete_group_notice` |
| 文件 | `qq_upload_file`、`qq_get_group_root_files`、`qq_get_group_file_url`、`qq_create_group_file_folder`、`qq_delete_group_file`、`qq_download_file`、`qq_get_group_files_by_folder`、`qq_delete_group_folder`、`qq_get_group_file_system_info`、`qq_get_file`、`qq_get_image`、`qq_get_record` |
| 媒体 & 内容 | `qq_get_emoji_likes`、`qq_get_recent_contact`、`qq_create_flash_task`、`qq_send_flash_msg`、`qq_ocr_image`、`qq_translate_en2zh` |
| 自身 & 其他 | `qq_set_qq_avatar`、`qq_set_self_longnick`、`qq_set_online_status`、`qq_send_qzone_msg`、`qq_get_qun_album_list`、`qq_upload_image_to_qun_album`、`qq_get_version_info`、`qq_get_status` |

---

## 工作原理

1. **安装** — 把本仓库的 `plugin/` 目录放到 `~/.hermes/plugins/napcat/`（复制或软链）。
   Hermes 启动时发现
   插件，调用 `register(ctx)`，把适配器注册进平台注册表（`gateway/run.py` 的
   `_create_adapter()` 优先查注册表）。
2. **连接** — 适配器在 `ws://0.0.0.0:{ws_port}{ws_path}` 开启反向 WS **服务端**；
   NapCat 作为客户端拨入（Universal 角色）。
3. **入站** — NapCat 上报消息事件（Array 格式）；适配器执行 DM / 群策略、为群消息加
   发送者前缀、拉取引用消息上下文，归一化成 `MessageEvent` 交给 `handle_message()`。
   OneBot 11 的 `request` 事件（好友申请 / 加群申请 / 群邀请）会以"管理员上下文"的
   系统事件形式呈现给模型，由它通过 `qq_handle_friend_request` /
   `qq_handle_group_request` 审批。
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

## 升级

```bash
git -C hermes-napcat pull
# 软链安装：无需额外操作，插件目录就地更新
# 复制安装：cp -r hermes-napcat/plugin/* ~/.hermes/plugins/napcat/
```

重启网关后生效。

---

## 卸载

```bash
rm -rf ~/.hermes/plugins/napcat
```

然后清理 `~/.hermes/config.yaml` 里的 `platforms.napcat` /
`platform_toolsets.napcat`。NapCat 进程不受影响。

---

## 常见问题排查

| 现象 | 原因 / 解决 |
|------|------------|
| 网关日志显示没有 WS 连接 | NapCat 反向 WS 项必须指向 `ws://127.0.0.1:{ws_port}{ws_path}` 且为 Universal 角色 |
| 握手 `403` | `access_token` 与 NapCat 反向 WS 项里配置的不一致 |
| `ECONNREFUSED 127.0.0.1:18801` | 网关未运行（`hermes gateway run`）或端口被占用——改 `ws_port`；若 NapCat 在 Windows 而 Hermes 在 WSL，见下方「WSL / Windows 部署」 |
| 群里不回消息 | 群聊需要 @机器人（或将成员加入 allow_from 并设 `group_policy: allowlist`） |
| `Permission denied: only admins` | 发送者不在 `admins`；加入其 QQ 号或设 `admins: []` |
| `hermes plugins list` 里看不到 | 插件目录必须是 `~/.hermes/plugins/napcat/`，含 `plugin.yaml` + `__init__.py`；重新复制 `plugin/`（或修复失效的软链）并 `hermes plugins enable napcat` |

### WSL / Windows 部署（NapCat 在宿主机，Hermes 在 WSL）

`127.0.0.1` 是**各自机器的回环地址**：NapCat 在 Windows 上连 `127.0.0.1:18801` 指的是
Windows 本机，而插件在 WSL 里监听的是 WSL 虚拟机内部的 `0.0.0.0:18801`，两者不互通。

**现象特征：**

- Windows 上 NapCat 反复报 `connect ECONNREFUSED 127.0.0.1:18801` —— 网关没起 / 端口没监听，
  或连的是 Windows 本机而非 WSL 的地址。
- 改成 WSL IP 后报 `Opening handshake has timed out` —— TCP 已通（说明网关在监听），但网关
  还没就绪（启动中 / 事件循环卡住）；等它就绪或重启网关即可。

**修复（任选其一）：**

1. **直连 WSL 的 IP（最简单）**：在 WSL 里 `hostname -I` 查 IP，NapCat 反向 WS URL 填
   `ws://<WSL-IP>:18801/onebot/v11`。注意 WSL2 默认 NAT 模式下 IP 重启会变，需重查。
2. **mirrored 网络模式（一劳永逸，Win11 22H2+）**：让 Windows 与 WSL 共享 localhost，
   NapCat 继续用 `ws://127.0.0.1:18801` 即可：

   ```
   # C:\Users\<你>\.wslconfig
   [wsl2]
   networkingMode=mirrored
   ```
   ```powershell
   wsl --shutdown      # 然后重新打开 WSL
   ```

**排查顺序：**

1. WSL 里确认网关真的在监听：`ss -tlnp | grep 18801` 应看到 python 进程；
   `tail -f /tmp/hermes-gateway.log` 应看到 `NapCat: reverse WS listening on ws://0.0.0.0:18801/onebot/v11`。
2. 在 WSL 内直接测握手（绕开 Windows→WSL 网络段）：返回 `101 Switching Protocols` 说明
   插件服务器正常：

   ```bash
   curl -i -N --max-time 6 -H "Connection: Upgrade" -H "Upgrade: websocket" \
        -H "Sec-WebSocket-Version: 13" -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
        "http://127.0.0.1:18801/onebot/v11"
   ```

3. **先起网关再开 NapCat**——NapCat 每 5 秒自动重连，网关没起时会一直刷 `ECONNREFUSED`，
   属正常重试，不是配置错误。

## 许可证

MIT
