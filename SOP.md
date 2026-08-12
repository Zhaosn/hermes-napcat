# SOP：安装 hermes-napcat（Plugin 版 v0.3.0）

> 适用：Hermes Agent（含插件系统） + NapCat（反向 WS）。本 SOP 不涉及 NapCat 的
> 安装/启动/配置——只安装 Hermes 侧的插件与配置。

---

## 0. 前置条件检查

| 项 | 要求 |
|----|------|
| Hermes Agent | 源码安装，含 `~/.hermes/plugins/` 插件目录（较新的 `main` 构建均可） |
| Python | 3.11+ |
| NapCat | 已安装并运行，QQ 已登录 |
| 网络 | 可访问 GitHub（`pip install git+https://github.com/Zhaosn/hermes-napcat.git`） |

开始前先确认：

```bash
hermes --version          # Hermes 可用
python --version          # Python >= 3.11
```

> 如果之前用**旧版（补丁式）** hermes-napcat 安装过，先处理残留（见 §6 升级注意事项）。

---

## 1. 从 GitHub 安装（v0.3.0 插件版）

```bash
pip install git+https://github.com/Zhaosn/hermes-napcat.git
```

> **为什么不用 `pip install hermes-napcat`？** PyPI 上的 `hermes-napcat` 仍是 0.2.x
> 旧版（补丁式，会修改 Hermes 核心源码），与本 SOP 描述的插件版不一致。0.3.0 插件版
> 目前只通过本 fork（`Zhaosn/hermes-napcat`）的 GitHub 发布。

> 依赖：`aiohttp>=3.9`（自动安装）。语音转写需另装 `ffmpeg`（可选）。

---

## 2. 运行安装向导

```bash
hermes-napcat setup
```

交互式向导会依次询问：

| 提示 | 填什么 |
|------|--------|
| QQ number | 机器人自己的 QQ 号（用于群聊 @ 识别；留空则连接后自动探测） |
| Admin QQ numbers | 可使用管理指令的 QQ 号（你本人；逗号分隔可多个） |
| Reverse-WS port | 默认 `18801`（NapCat 拨入的端口） |
| Reverse-WS path | 默认 `/onebot/v11` |
| NapCat 鉴权 Token | 与 NapCat 反向 WS 项里配置的 Token 一致（可不填） |

**非交互式（脚本/CI）**，等价于：

```bash
hermes-napcat install \
  --qq 123456789 \
  --admins "123456789,987654321" \
  --ws-port 18801 \
  --ws-path /onebot/v11 \
  --token "你从NapCat复制的Token"
```

向导执行两件事：

1. 复制插件 → `~/.hermes/plugins/napcat/`
2. 合并配置 → `~/.hermes/config.yaml`（写入 `platforms.napcat` + `platform_toolsets.napcat`）

> 可用 `HERMES_HOME` 环境变量指定不同的 Hermes 家目录（默认 `~/.hermes`）。

### 安装后检查

```bash
hermes-napcat status
```

预期输出类似：

```
hermes-napcat status
  Hermes home:      C:\Users\<你>\.hermes
  plugin dir:       ✓ C:\Users\<你>\.hermes\plugins\napcat
  plugin.yaml:      ✓
  config.yaml:      ✓
  plugin modules:   4
```

---

## 3. 配置 NapCat 反向 WebSocket

在 NapCat 的网络设置中添加一个「反向 WS」项（**本端作客户端主动连远端**）：

| 设置 | 值 |
|------|-----|
| 服务端 WebSocket URL | `ws://127.0.0.1:18801/onebot/v11` |
| 连接角色 | Universal（全双工，API + 事件） |
| 消息上报格式 | Array（结构化数组） |
| 鉴权 Token | 与 §2 填写的 Token 完全一致 |
| 重连间隔 | 30000 ms（默认即可） |
| 心跳间隔 | 5000 ms（默认即可） |

> URL 的端口与路径必须与 `config.yaml` 里 `platforms.napcat.extra.ws_port` / `ws_path`
> 一致（默认即 `18801` / `/onebot/v11`）。

---

## 4. 启动 Hermes 网关

如果网关**已经**在跑，先重启（插件只在启动时发现）：

```bash
hermes gateway stop      # 如已有在跑
nohup hermes gateway run > /tmp/hermes-gateway.log 2>&1 &
```

启动后网关会：
1. 发现 `~/.hermes/plugins/napcat/` 插件，调用 `register(ctx)` 注册平台
2. 在 `ws://0.0.0.0:18801/onebot/v11` 开启反向 WS 监听
3. **等待 NapCat 拨入**（NapCat 每 30s 自动重连，无需其它操作）

---

## 5. 验证

```bash
# 1. 插件是否被 Hermes 识别
hermes plugins list

# 2. 网关日志（应看到以下两行）
tail -f /tmp/hermes-gateway.log
#   NapCat: reverse WS listening on ws://0.0.0.0:18801/onebot/v11
#   NapCat: bot is <昵称> (QQ:<号>)        ← 连接成功 + 自动探测到机器人 QQ

# 3. 实际对话测试
#    在群里 @机器人 说一句话；私聊直接发消息
#    期望：机器人回复，且群消息显示为「[你的群昵称]: 消息」
```

若日志只出现第一行、没有 `bot is ...`，说明 NapCat 没拨进来 → 检查 §3 的 URL / Token。

---

## 6. 升级 / 卸载 / 回滚

### 升级 hermes-napcat

```bash
pip install -U git+https://github.com/Zhaosn/hermes-napcat.git
hermes-napcat install --qq <QQ> --admins <QQ> --token <Token>   # 重新覆盖插件 + 配置
hermes gateway restart
```

### 从旧版（补丁式）升级

旧版会在 Hermes 源码树里留补丁。新版 `uninstall` 不会清理这些残留，需手动处理：

```bash
# 查看是否残留
grep -rn "napcat-installed" ~/.hermes/hermes-agent/gateway/config.py \
  ~/.hermes/hermes-agent/gateway/run.py \
  ~/.hermes/hermes-agent/toolsets.py \
  ~/.hermes/hermes-agent/hermes_cli/platforms.py

# 有残留则删除旧补丁注入的文件
rm -f ~/.hermes/hermes-agent/gateway/platforms/napcat.py \
      ~/.hermes/hermes-agent/gateway/platforms/napcat_api.py \
      ~/.hermes/hermes-agent/tools/qq_tool.py

# 用旧版自带备份还原被改的核心文件（如存在 *.napcat.bak）
# 或重新 git checkout 相关文件
```

然后按 §2 重新安装新版插件。

### 卸载

```bash
hermes-napcat uninstall -y
```

删除 `~/.hermes/plugins/napcat/` 并清理 `config.yaml` 里的 `platforms.napcat` /
`platform_toolsets.napcat`。NapCat 进程不受影响。

### 回滚到旧版

`git revert` 或 `git checkout` 旧提交后，`pip install -e .` + 旧版 `hermes-napcat install`。

---

## 7. 常见问题排查

| 现象 | 原因 / 处理 |
|------|------------|
| `hermes plugins list` 里没有 napcat | 插件目录必须是 `~/.hermes/plugins/napcat/`，含 `plugin.yaml` + `__init__.py`；重跑 `hermes-napcat setup` |
| 日志只有 reverse WS listening、没有 NapCat 连接 | NapCat 反向 WS URL / 端口 / 路径与 `config.yaml` 不一致；或 NapCat 未启动 |
| 握手 403 / `rejected WS connection (bad access token)` | `access_token` 与 NapCat 反向 WS 项里配置的 Token 不一致 |
| `ECONNREFUSED 127.0.0.1:18801` | 网关未运行（`hermes gateway run`）；或端口被占用 → 改 `ws_port` |
| 群里不回消息 | 群聊需 **@机器人**；或该成员不在 `allow_from` 且 `group_policy` 非 open |
| `Permission denied: only admins` | 发送者不在 `admins` 列表；加入其 QQ 或设 `admins: []` |
| 改了配置不生效 | 重启网关：`hermes gateway restart` |

---

## 8. 关键文件速查

| 路径 | 作用 |
|------|------|
| `~/.hermes/plugins/napcat/` | 插件本体（删除即卸载） |
| `~/.hermes/plugins/napcat/plugin.yaml` | 插件清单（声明 NAPCAT_* 环境变量） |
| `~/.hermes/config.yaml` | `platforms.napcat` + `platform_toolsets.napcat` 配置 |
| `~/.hermes/config.yaml` → `extra.admins` | 管理员 QQ 列表 |
| `~/.hermes/config.yaml` → `extra.ws_port` / `ws_path` | 反向 WS 监听端口 / 路径 |

**环境变量等价配置**（可选，不写 config.yaml 时用）：

```
NAPCAT_ACCESS_TOKEN  NAPCAT_WS_PORT  NAPCAT_WS_HOST  NAPCAT_WS_PATH
NAPCAT_SELF_ID       NAPCAT_DM_POLICY  NAPCAT_GROUP_POLICY
NAPCAT_ALLOWED_USERS NAPCAT_ADMINS  NAPCAT_ALLOW_ALL_USERS  NAPCAT_HOME_CHANNEL
```
