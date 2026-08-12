<div align="center">

# hermes-napcat

**NapCat (QQ / OneBot 11) platform plugin for [Hermes Agent](https://github.com/NousResearch/hermes-agent)**

[![PyPI](https://img.shields.io/pypi/v/hermes-napcat?color=blue)](https://pypi.org/project/hermes-napcat/)
[![Python](https://img.shields.io/pypi/pyversions/hermes-napcat)](https://pypi.org/project/hermes-napcat/)
[![License](https://img.shields.io/github/license/shubyi/hermes-napcat)](LICENSE)

[English](README.md) · [中文](README.zh.md)

</div>

Connect Hermes to QQ via [NapCat](https://github.com/NapNeko/NapCatQQ)'s OneBot 11 reverse WebSocket. Chat with your AI assistant in any QQ group or DM, with full group management and admin controls.

Installed as a **standard Hermes plugin** (`~/.hermes/plugins/napcat/`) — **no core Hermes source files are patched**, so upgrading Hermes never breaks it.

```
QQ App ──── NapCat ──WS(dial in)──▶ hermes-napcat (plugin) ──▶ Hermes (LLM)
                                        │
                                        └── one full-duplex Universal WS: events + API ──┐
                                          (reverse-WS server, default ws://0.0.0.0:18801/onebot/v11)
```

---

## Origin

This repository is a **fork** of [shubyi/hermes-napcat](https://github.com/shubyi/hermes-napcat).

- **Upstream (shubyi/hermes-napcat)** installs the NapCat adapter by *patching the
  Hermes source tree* (injecting files into `gateway/`, `tools/`, `toolsets.py`, …).
- **This fork** reimplements the same QQ / NapCat integration as a **standard Hermes
  plugin** (`~/.hermes/plugins/napcat/`) — zero core-source changes, survives Hermes
  upgrades, installs via the official plugin system.

Lineage: `main` (this fork's plugin version) carries the full upstream history as
ancestors; the pristine upstream code is kept on the `upstream-main` branch for
diffing.

---

## Features

- **Group & DM** — @mention in groups; direct message for private chats
- **Shared group sessions** — whole group shares one context; sender names auto-prefixed
- **Admin system** — restrict management commands to a configurable QQ number list
- **48 QQ tools** — messaging, group management, files, OCR, reactions, and more
- **Media support** — images, voice (→ WAV via ffmpeg), video, file upload/download
- **Quoted message context** — replies carry the quoted content automatically
- **Universal reverse-WS** — events and API share one connection; no separate HTTP API needed
- **One-command setup** — installs the plugin and writes the config, nothing else

---

## Requirements

- Python 3.11+
- [Hermes Agent](https://github.com/NousResearch/hermes-agent) with the plugin system (`~/.hermes/plugins/`), i.e. any recent `main` build
- [NapCat](https://github.com/NapNeko/NapCatQQ) running with a **reverse WebSocket** item enabled
- `aiohttp >= 3.9` (already installed with hermes-napcat)
- `ffmpeg` *(optional, for voice-message transcription)*

---

## Quick start

### 1. Install the package

> ⚠️ This fork's **plugin version (0.3.0)** is installed from GitHub. The
> `hermes-napcat` package on PyPI is still the old **0.2.x patch-based version**
> (it patches Hermes core source) — do **not** use `pip install hermes-napcat`.

```bash
pip install git+https://github.com/Zhaosn/hermes-napcat.git
```

Verify you got the plugin version:

```bash
pip show hermes-napcat    # Version: 0.3.0
```

### 2. Run the setup wizard

```bash
hermes-napcat setup
```

This copies the plugin to `~/.hermes/plugins/napcat/` and merges the
`platforms.napcat` block into `~/.hermes/config.yaml`.

Non-interactive (scripts/CI):

```bash
hermes-napcat setup --qq 123456789 --admins "123456789,987654321" --token "<napcat-token>"
```

> hermes-napcat **never** installs, launches, or configures NapCat — you run it
> yourself (e.g. the [official installer](https://github.com/NapNeko/NapCat-Installer)).
> It only adds the Hermes-side plugin + config.

### 3. Configure NapCat's reverse WebSocket

In NapCat's network settings add a reverse-WS item:

| Setting | Value |
|---|---|
| Reverse WS: this end acts as client, dials into remote | enabled |
| 服务端 WebSocket URL | `ws://127.0.0.1:18801/onebot/v11` |
| 连接角色 | Universal（全双工，API + 事件） |
| 消息上报格式 | Array（结构化数组） |
| 鉴权 Token | whatever `--token` you set (or blank for no auth) |

### 4. Start the Hermes gateway

```bash
nohup hermes gateway run > /tmp/hermes-gateway.log 2>&1 &
```

The gateway discovers the plugin, opens the reverse-WS listener on
`ws://0.0.0.0:18801/onebot/v11`, and **waits for NapCat to dial in** — nothing
else to do.

---

## Configuration

`~/.hermes/config.yaml`:

```yaml
platforms:
  napcat:
    enabled: true
    extra:
      ws_port: 18801                # reverse-WS listen port
      ws_path: "/onebot/v11"        # reverse-WS path (must match NapCat's URL)
      access_token: ""              # NapCat reverse-WS 鉴权 Token
      self_id: "123456789"          # bot QQ number (auto-detected if blank)
      dm_policy: "allowlist"        # open | allowlist | disabled
      allow_from: []                # QQ numbers allowed for DMs
      group_policy: "open"          # open | allowlist | disabled
      group_allow_from: []          # falls back to allow_from
      admins: []                    # QQ numbers that can use admin tools
      media_max_mb: 5

platform_toolsets:
  napcat:
    - hermes-cli                    # terminal / file / web_search core tools
    - hermes-napcat                 # 48 qq_* tools (auto-enabled plugin toolset)

group_sessions_per_user: false      # whole group shares one session
```

Environment-variable equivalents (picked up automatically via the plugin's
`env_enablement_fn`):

```
NAPCAT_ACCESS_TOKEN  NAPCAT_WS_PORT  NAPCAT_WS_HOST  NAPCAT_WS_PATH
NAPCAT_SELF_ID       NAPCAT_DM_POLICY  NAPCAT_GROUP_POLICY
NAPCAT_ALLOWED_USERS (comma-separated)  NAPCAT_ADMINS (comma-separated)
NAPCAT_ALLOW_ALL_USERS  NAPCAT_HOME_CHANNEL
```

> **Gateway-level auth:** the plugin declares `allowed_users_env` / `allow_all_env`,
> so the core `_is_user_authorized()` gate works out of the box. Unless you set
> `NAPCAT_ALLOWED_USERS` or `NAPCAT_ALLOW_ALL_USERS`, the adapter enforces its
> own `dm_policy` / `group_policy` / `admins` itself.

---

## Admin system

Set `admins` in the napcat platform block to restrict who may use management tools:

```yaml
platforms:
  napcat:
    extra:
      admins: ["123456789", "987654321"]
```

If `admins` is empty, anyone can call any tool (open mode).

| Operation | Regular user | Admin |
|---|---|---|
| Search, query, write code, read files, etc. | ✅ | ✅ |
| QQ management tools (mute, kick, set admin, etc.) | ❌ | ✅ |
| Destructive local operations | ❌ | ⚠️ requires second confirmation |

**Admin-only QQ tools:** `qq_kick_group_member`, `qq_mute_group_member`,
`qq_set_group_admin`, `qq_set_group_name`, `qq_set_group_whole_ban`,
`qq_leave_group`, `qq_set_group_portrait`, `qq_set_group_special_title`,
`qq_set_essence_msg`, `qq_delete_essence_msg`, `qq_send_group_notice`,
`qq_delete_group_notice`, `qq_delete_group_file`, `qq_delete_friend`,
`qq_handle_friend_request`, `qq_handle_group_request`.

---

## Available tools

| Category | Tools |
|---|---|
| Messaging | `qq_send_message`, `qq_recall_message`, `qq_set_msg_emoji_like`, `qq_forward_message`, `qq_send_group_forward_msg`, `qq_send_private_forward_msg`, `qq_mark_msg_as_read` |
| History | `qq_get_group_msg_history`, `qq_get_friend_msg_history`, `qq_get_essence_msg_list`, `qq_set_essence_msg`, `qq_delete_essence_msg` |
| Users & friends | `qq_get_user_info`, `qq_get_friend_list`, `qq_like_user`, `qq_poke`, `qq_set_friend_remark`, `qq_delete_friend`, `qq_handle_friend_request` |
| Group info | `qq_get_group_info`, `qq_get_group_list`, `qq_get_group_member_info`, `qq_get_group_member_list`, `qq_get_group_honor_info`, `qq_get_group_at_all_remain` |
| Group management | `qq_mute_group_member`, `qq_kick_group_member`, `qq_set_group_admin`, `qq_set_group_name`, `qq_set_group_card`, `qq_set_group_whole_ban`, `qq_set_group_special_title`, `qq_leave_group`, `qq_set_group_sign`, `qq_set_group_remark`, `qq_set_group_portrait`, `qq_handle_group_request` |
| Notices | `qq_send_group_notice`, `qq_get_group_notice`, `qq_delete_group_notice` |
| Files | `qq_upload_file`, `qq_get_group_root_files`, `qq_get_group_file_url`, `qq_create_group_file_folder`, `qq_delete_group_file`, `qq_download_file` |
| Other | `qq_ocr_image`, `qq_translate_en2zh` |

---

## How it works

1. **Install** copies `hermes_napcat/plugin/` → `~/.hermes/plugins/napcat/`. Hermes
   discovers it, calls `register(ctx)`, and registers the adapter into the platform
   registry (`gateway/run.py` checks the registry before built-ins).
2. **Connect** — the adapter starts a reverse-WS **server** on
   `ws://0.0.0.0:{ws_port}{ws_path}`; NapCat dials in as the client (Universal role).
3. **Inbound** — NapCat reports message events (array format); the adapter applies
   DM/group policy, prefixes group sender names, fetches quoted-message context, and
   forwards a normalized `MessageEvent` via `handle_message()`.
4. **Outbound** — replies are sent as OneBot 11 actions over the same WS
   (`send_group_msg` / `send_private_msg`, images/voice/video/files), correlated by
   `echo`. Markdown is stripped to QQ-friendly plain text first.

### Session isolation

| Chat type | Session key |
|---|---|
| DM | per-QQ-number |
| Group (`group_sessions_per_user: false`) | whole group shares one |
| Group (`group_sessions_per_user: true`) | per user per group |

---

## CLI reference

| Command | Description |
|---|---|
| `hermes-napcat setup` | Interactive wizard — installs the plugin + writes config |
| `hermes-napcat install` | Same, non-interactive (flags: `--qq --admins --ws-port --ws-path --token`) |
| `hermes-napcat uninstall` | Removes the plugin + config block |
| `hermes-napcat status` | Shows plugin / config installation status |

There are no NapCat process-management commands — NapCat is yours to run; it
auto-connects once the gateway is up.

---

## Uninstall

```bash
hermes-napcat uninstall
```

Deletes `~/.hermes/plugins/napcat/` and cleans the `platforms.napcat` /
`platform_toolsets.napcat` entries from `config.yaml`. NapCat is untouched.

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Gateway log: no WS connection | NapCat's reverse-WS item must point to `ws://127.0.0.1:{ws_port}{ws_path}` with Universal role |
| `403` / handshake rejected | `access_token` mismatch between NapCat's reverse-WS item and the napcat config / `NAPCAT_ACCESS_TOKEN` |
| `ECONNREFUSED 127.0.0.1:18801` | Gateway not running (`hermes gateway run`), or port conflict — change `ws_port` |
| Bot ignores group messages | You must @ the bot in group chats (or add the group's senders to the allowlist and set `group_policy: allowlist`) |
| `Permission denied: only admins` | Sender not in `admins`; add their QQ or set `admins: []` |
| Not showing in `hermes plugins list` | The plugin dir must be `~/.hermes/plugins/napcat/` with `plugin.yaml` + `__init__.py`; re-run `hermes-napcat setup` |

### Provider User-Agent blocking

Some LLM API providers block the OpenAI SDK's default `AsyncOpenAI/Python X.X.X`
User-Agent. If you hit `403 unsupported_user_agent`, add a header override for your
provider in `~/.hermes/hermes-agent/run_agent.py` (see Hermes docs) — this is
unrelated to the NapCat plugin.

---

## License

MIT
