# hermes-napcat 安装方式说明（Plugin 形式）

`hermes-napcat setup`（或 `hermes-napcat install`）以 **Hermes 插件**的形式安装
OneBot 11（NapCat / QQ）平台适配器，使 Hermes 可以通过 QQ 群 / 私聊收发消息。

**与旧版的本质区别：不再修改任何 Hermes 核心源码。** 安装只是：

1. 把插件目录 `hermes_napcat/plugin/` 复制到 `{hermes_home}/plugins/napcat/`
   （`hermes_home` 默认 `~/.hermes`，可用环境变量 `HERMES_HOME` 指定）。
2. 把 `platforms.napcat` 平台块（含 `platform_toolsets.napcat`）合并进
   `{hermes_home}/config.yaml`。

Hermes 的插件系统在启动时扫描 `~/.hermes/plugins/`，发现 `napcat` 目录后加载
`__init__.py` 并调用 `register(ctx)`，将适配器注册进平台注册表。网关
`_create_adapter()` 会**优先查平台注册表**（`gateway/run.py`），因此无需改动
`gateway/config.py` 的 `Platform` 枚举、`gateway/run.py` 的分发分支，也无需
认证绕过补丁——插件声明 `allowed_users_env` / `allow_all_env` 即自动接入核心的
用户鉴权。

> ⚠️ hermes-napcat **不负责安装 / 启动 / 配置 NapCat 进程**。
> 你需要自己运行 NapCat，并把它的「反向 WS」项指向
> `ws://127.0.0.1:{ws_port}{ws_path}`（默认 `ws://127.0.0.1:18801/onebot/v11`，
> 连接角色 Universal、消息上报格式 Array）。

---

## 安装的组成

| 项 | 说明 |
|----|------|
| `{hermes_home}/plugins/napcat/plugin.yaml` | 插件清单（kind: platform，声明 NAPCAT_* 环境变量） |
| `{hermes_home}/plugins/napcat/adapter.py` | `NapCatAdapter` + `register(ctx)` |
| `{hermes_home}/plugins/napcat/api.py` | OneBot 11 Universal-WS 动作客户端（`echo` 关联） |
| `{hermes_home}/plugins/napcat/qq_tool.py` | 48 个 `qq_*` 工具（工具集 `hermes-napcat`） |
| `{hermes_home}/plugins/napcat/skills/qq/SKILL.md` | `qq` 技能（`register_skill` 注册，命名空间 `napcat:qq`） |
| `{hermes_home}/config.yaml` | 合并 `platforms.napcat` + `platform_toolsets.napcat` |

没有任何 `.napcat.bak` 备份或还原逻辑——卸载只需删除插件目录并清理 config 块。

---

## 运行方式（对接 NapCat 的通用 WS）

适配器在 `connect()` 里启动一个 **反向 WebSocket 服务端**
（`ws://0.0.0.0:{ws_port}{ws_path}`，默认 `18801/onebot/v11`），NapCat 作为
**客户端**拨入（你配置的「反向 WS：本端作客户端主动连远端」）。连接角色为
Universal（全双工），因此：

- **入站**：NapCat 通过这条 WS 上报消息事件（`post_type=message`，Array 格式）。
- **出站**：回复通过同一条 WS 发送 OneBot 11 动作（`send_group_msg` 等），
  用 `echo` 字段关联请求与响应——**不依赖 NapCat 的 HTTP API**。
- **鉴权**：握手时校验 `Authorization: Bearer <token>`（或 URL 上的
  `access_token` 参数），token 与你在 NapCat 反向 WS 项里配置的一致。
- **心跳**：NapCat 每 5 秒发 `meta_event` 心跳，适配器自动忽略。

---

## 配置

写入 `~/.hermes/config.yaml`：

```yaml
platforms:
  napcat:
    enabled: true
    extra:
      ws_port: 18801                # 反向 WS 监听端口
      ws_path: "/onebot/v11"        # 反向 WS 路径（须与 NapCat 的 URL 一致）
      access_token: ""              # NapCat 反向 WS 鉴权 Token
      self_id: "123456789"          # 机器人 QQ 号（留空则连接后自动探测）
      dm_policy: "allowlist"        # allowlist | open | disabled
      allow_from: []                # 允许私聊的 QQ 号
      group_policy: "open"          # open | allowlist | disabled
      admins: []                    # 可使用管理指令的 QQ 号

platform_toolsets:
  napcat:
    - hermes-cli                    # 终端 / 文件 / 搜索等核心工具
    - hermes-napcat                 # 48 个 qq_* 工具（插件工具集，默认启用）

group_sessions_per_user: false      # 整个群共享一个会话
```

也可全部用环境变量（`hermes gateway` 会通过 `env_enablement_fn` 自动注入）：

- `NAPCAT_ACCESS_TOKEN`、`NAPCAT_WS_PORT`、`NAPCAT_WS_HOST`、`NAPCAT_WS_PATH`
- `NAPCAT_SELF_ID`、`NAPCAT_DM_POLICY`、`NAPCAT_GROUP_POLICY`
- `NAPCAT_ALLOWED_USERS`（逗号分隔）、`NAPCAT_ADMINS`（逗号分隔）
- `NAPCAT_ALLOW_ALL_USERS`（默认在未显式配置允许列表时置为 `true`，核心鉴权让位给
  适配器自身的 `dm_policy` / `group_policy`）
- `NAPCAT_HOME_CHANNEL`（cron `deliver=napcat` 的默认会话）

---

## 卸载

```bash
hermes-napcat uninstall
```

删除插件目录 + 清理 `config.yaml` 中的 `platforms.napcat` 与
`platform_toolsets.napcat`，不触碰 NapCat 进程。

---

## 一句话总结

hermes-napcat 对 Hermes 的修改 = **一个自包含的插件目录 + 一段 config.yaml**。
插件经 `register(ctx)` 自动接入平台注册表、工具集与技能系统，升级 Hermes 无需重装。
