# hermes-napcat 对 Hermes Agent 的修改说明

`hermes-napcat setup`（或 `hermes-napcat install`）会向本机的
[Hermes Agent](https://github.com/NousResearch/hermes-agent) 源码树注入一个
OneBot 11（NapCat）平台适配器，使 Hermes 可以通过 QQ 群 / 私聊收发消息。

Hermes Agent 源码根目录在下文写作 `<hermes-agent>/`（常见位置
`~/.hermes/hermes-agent`，也可用 `--hermes-dir` 指定）。

> ⚠️ hermes-napcat **不负责安装 / 启动 / 管理 NapCat 进程**。
> 网关启动后会开启反向 WS 监听端口，然后**仅等待 NapCat 建立连接**。

---

## 修改清单

| # | 位置（相对 hermes-agent 根目录） | 修改内容 |
|---|----------------------------------|----------|
| 1 | `gateway/platforms/napcat.py` | 新增：平台适配器（由本包的 `adapter.py` 复制而来） |
| 2 | `gateway/platforms/napcat_api.py` | 新增：OneBot 11 HTTP API 客户端（`api.py`） |
| 3 | `tools/qq_tool.py` | 新增：48 个 QQ 工具（消息、群管、文件、OCR 等） |
| 4 | `gateway/config.py` | 修改：`Platform` 枚举增加 `NAPCAT` |
| 5 | `gateway/run.py` | 修改：`_create_adapter()` 增加 NapCat 分支 |
| 6 | `gateway/run.py` | 修改：`_is_user_authorized()` 增加 NapCat 认证绕过 |
| 7 | `toolsets.py` | 修改：注册 `hermes-napcat` 工具集并挂到 `hermes-gateway` |
| 8 | `hermes_cli/platforms.py` | 修改：平台列表注册 napcat 条目 |
| 9 | `skills/qq/SKILL.md` | 新增：QQ 技能说明 |
| 10 | `~/.hermes/config.yaml` | 修改：写入 `platforms.napcat` 平台块（用户目录，非源码树） |

---

## 逐项说明

### 1. 复制适配器 `adapter.py` → `gateway/platforms/napcat.py`

这是核心平台适配器，类名为 `NapCatAdapter`，继承
`gateway.platforms.base.BasePlatformAdapter`。复制时会改写两处相对导入：

- `from .api import ...` → `from gateway.platforms.napcat_api import ...`
- `from gateway.platforms import qq_tool as _qq_tool` → `import tools.qq_tool as _qq_tool`

**运行时行为**（对应「仅等待 NapCat 建立连接」）：

- `connect()`：在 `0.0.0.0:18800` 启动 aiohttp WebSocket 服务器（反向 WS），
  **不会**主动拉起或连接任何进程，只是等待 NapCat 拨入。
- `_ws_handler()`：NapCat 通过 OneBot 11 反向 WS 连接后，将消息事件交给 Hermes 处理。
- `send()` / `send_image()` / `send_voice()` / `send_video()` / `send_document()`：
  通过 NapCat 的 HTTP API（默认 `http://127.0.0.1:18801`）发回消息。
- 发送前会把 Markdown 转成 QQ 友好的纯文本（QQ 不渲染 Markdown）。
- 群聊消息自动加 `[昵称]:` 前缀，按 `group_sessions_per_user` 决定会话隔离粒度；
  引用消息会自动携带被引用内容。

### 2. 复制 API 客户端 `api.py` → `gateway/platforms/napcat_api.py`

封装 OneBot 11 HTTP 接口：`send_group_msg`、`send_private_msg`、`upload_group_file`、
`get_msg`、`call_onebot_api`，以及 `text_segment` / `image_segment` / `record_segment` /
`reply_segment` / `video_segment` 等 CQ 消息段构造器。

### 3. 复制 QQ 工具 `qq_tool.py` → `tools/qq_tool.py`

48 个可直接被智能体调用的 QQ 工具（以 `qq_` 前缀命名），覆盖：

- 消息：发送 / 撤回 / 转发 / 表情回应
- 群管理：禁言、踢人、设置管理员、改群名、全体禁言、退群、改群头像等
- 群信息：群成员列表、荣誉列表、@全体剩余次数
- 文件：上传 / 下载 / 创建目录 / 删除
- 通知与历史：群公告、精华消息、历史记录
- 其它：OCR、英汉互译、好友 / 群申请处理

同时暴露 `_init()` / `_set_context()` 供适配器注入 HTTP API 地址与当前发送者权限。

### 4. `gateway/config.py` — `Platform` 枚举

在 `Platform` 枚举的最后一个成员后追加（带 `# napcat-installed` 标记，便于检测与还原）：

```python
    NAPCAT = "napcat"  # napcat-installed
```

### 5. `gateway/run.py` — `_create_adapter()` 平台分发

在 `_create_adapter()` 中、函数末尾的 `return None` 之前插入 NapCat 分支：

```python
    elif platform == Platform.NAPCAT:  # napcat-installed
        from gateway.platforms.napcat import NapCatAdapter, check_napcat_requirements
        if not check_napcat_requirements():
            logger.warning('NapCat: aiohttp not installed')
            return None
        return NapCatAdapter(config)
```

### 6. `gateway/run.py` — `_is_user_authorized()` 认证绕过

让 NapCat 来源的消息走与 Home Assistant / Webhook 相同的免登录认证路径：

```python
    if source.platform in (Platform.HOMEASSISTANT, Platform.WEBHOOK, Platform.NAPCAT):  # napcat-installed-auth
```

### 7. `toolsets.py` — 注册工具集

- 在 `TOOLSETS` 字典末尾新增 `"hermes-napcat"` 工具集，列出全部 48 个 `qq_*` 工具；
- 在 `"hermes-gateway"` 工具集的 `"includes"` 中加入 `"hermes-napcat"`，
  使 NapCat 平台默认携带该工具集。

### 8. `hermes_cli/platforms.py` — 平台注册

在 `PLATFORMS` 列表中（`webhook` 条目之前）插入：

```python
    ("napcat",         PlatformInfo(label="🐧 NapCat (QQ)",     default_toolset="hermes-napcat")),  # napcat-installed
```

### 9. `skills/qq/SKILL.md`

向 `<hermes-agent>/skills/qq/SKILL.md` 写入 QQ 平台使用说明，供 Hermes 的技能系统加载。

### 10. `~/.hermes/config.yaml`（用户配置）

写入 / 合并以下内容（若文件已存在会先备份为 `config.yaml.napcat.bak`）：

```yaml
platforms:
  napcat:
    enabled: true
    extra:
      http_api: "http://127.0.0.1:18801"   # NapCat HTTP API
      access_token: ""                      # 与 NapCat 设置一致
      self_id: "123456789"                  # 机器人 QQ 号（setup 时填写）
      ws_port: 18800                        # 反向 WS 监听端口
      dm_policy: "allowlist"
      allow_from: []
      admins: []                            # 可使用管理指令的 QQ 号

platform_toolsets:
  napcat:
    - hermes-cli
    - hermes-napcat

group_sessions_per_user: false              # 整个群共享一个会话
```

此外，`setup` 还会向 NapCat 的安装目录写入 OneBot 11 网络配置
`~/Napcat/opt/QQ/resources/app/app_launcher/napcat/config/onebot11.json`
（HTTP 服务 18801 + 反向 WS 客户端 `ws://127.0.0.1:18800`），
让 NapCat 启动后自动拨入 Hermes。

---

## 备份与还原

- **新增文件**（napcat.py、napcat_api.py、qq_tool.py、skills/qq/SKILL.md）：
  卸载时直接删除。
- **被修改的文件**（config.py、run.py、toolsets.py、platforms.py、config.yaml）：
  修改前先备份为同名 `.napcat.bak`，卸载时用备份恢复。
- 每个 patch 都带有 `# napcat-installed`（或 `-auth`）标记，`hermes-napcat status`
  据此检测各修改是否到位。
- `hermes-napcat uninstall` 可一键还原所有修改，不触碰 NapCat 进程。

---

## 一句话总结

hermes-napcat 对 Hermes 的修改 = **一个 NapCat 平台适配器 + 一个 QQ 工具集 + 三处接线**
（`Platform` 枚举、适配器分发、认证绕过），全部可追踪、可一键还原。
启动后 Hermes 只是开启反向 WS 端口等待 NapCat 连接，既不安装也不拉起 NapCat。
