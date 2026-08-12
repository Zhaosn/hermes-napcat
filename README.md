<div align="center">

# hermes-napcat

**NapCat (QQ / OneBot 11) adapter for [Hermes Agent](https://github.com/NousResearch/hermes-agent)**

[![PyPI](https://img.shields.io/pypi/v/hermes-napcat?color=blue)](https://pypi.org/project/hermes-napcat/)
[![Python](https://img.shields.io/pypi/pyversions/hermes-napcat)](https://pypi.org/project/hermes-napcat/)
[![License](https://img.shields.io/github/license/shubyi/hermes-napcat)](LICENSE)

[English](README.md) · [中文](README.zh.md)

</div>

Connect Hermes to QQ via [NapCat](https://github.com/NapNeko/NapCatQQ)'s OneBot 11 reverse WebSocket. Chat with your AI assistant in any QQ group or DM, with full group management and admin controls.

```
QQ App ──── NapCat ──WS──▶ hermes-napcat ──▶ Hermes (LLM)
                                │                  │
                                └─────HTTP API ◀───┘
                               (port 18801)   (port 18800)
```

---

## Features

- **Group & DM** — @mention in groups; direct message for private chats
- **Shared group sessions** — whole group shares one context; sender names auto-prefixed
- **Admin system** — restrict management commands to a configurable QQ number list
- **48 QQ tools** — messaging, group management, files, OCR, reactions, and more
- **Media support** — images, voice (→ WAV via ffmpeg), video, file upload/download
- **Quoted message context** — replies carry the quoted content automatically
- **One-command setup** — interactive wizard patches Hermes and writes the configs

---

## Requirements

- Python 3.11+
- [Hermes Agent](https://github.com/NousResearch/hermes-agent) (source install)
- [NapCat](https://github.com/NapNeko/NapCatQQ) with HTTP API + reverse WS enabled
- `aiohttp >= 3.9`
- `ffmpeg` *(optional, for voice transcription)*

---

## Quick Start

### 1. Install

```bash
pip install hermes-napcat
```

### 2. Setup

```bash
hermes-napcat setup
```

The wizard patches Hermes Agent, writes the NapCat config, updates `~/.hermes/config.yaml`, and asks for your QQ number and admin list.

Non-interactive (CI / scripts):

```bash
hermes-napcat setup --qq 123456789 --admins "123456789,987654321"
```

> hermes-napcat does **not** install or launch NapCat — you run NapCat yourself
> (e.g. via the [official installer](https://github.com/NapNeko/NapCat-Installer)).
> The setup step writes NapCat's `onebot11.json` so it dials into Hermes.

### 3. Install & start NapCat (on your own)

Install and start [NapCat](https://github.com/NapNeko/NapCatQQ) however you
prefer. Once running, it reads the `onebot11.json` written by `setup` and
dials out to Hermes' reverse WebSocket.

### 4. Start Hermes Gateway

```bash
nohup hermes gateway run > /tmp/hermes-gateway.log 2>&1 &
```

The gateway opens its reverse-WS listener and simply **waits for NapCat to connect** — no further action needed.

---

## Configuration

`~/.hermes/config.yaml`:

```yaml
platforms:
  napcat:
    enabled: true
    extra:
      http_api: "http://127.0.0.1:18801"   # NapCat HTTP API
      access_token: ""                      # Bearer token (if set in NapCat)
      self_id: "123456789"                  # Bot QQ number
      ws_port: 18800                        # Reverse WS listen port
      dm_policy: open                       # open | allowlist | disabled
      allow_from: []                        # QQ numbers allowed for DMs
      admins:                               # Can use management commands
        - "123456789"

platform_toolsets:
  napcat:
    - hermes-cli
    - hermes-napcat

group_sessions_per_user: false              # Whole group shares one session
```

### NapCat config

`~/Napcat/opt/QQ/resources/app/app_launcher/napcat/config/onebot11.json`:

```json
{
  "network": {
    "httpServers": [{
      "name": "httpServer",
      "enable": true,
      "port": 18801,
      "host": "0.0.0.0",
      "enableCors": true,
      "enableWebsocket": true,
      "messagePostFormat": "array",
      "token": "",
      "debug": false
    }],
    "websocketClients": [{
      "name": "HermesWs",
      "enable": true,
      "url": "ws://127.0.0.1:18800",
      "messagePostFormat": "array",
      "reportSelfMessage": false,
      "reconnectInterval": 5000,
      "token": "",
      "debug": false,
      "heartInterval": 30000
    }],
    "websocketServers": [],
    "httpSseServers": []
  }
}
```

---

## Admin System

Set `admins` in config to restrict who can use management commands:

```yaml
admins:
  - "123456789"
```

If `admins` is empty, all users can call any tool (open mode).

### Permission levels

| Operation | Regular user | Admin |
|-----------|:-----------:|:-----:|
| Search, queries, code, read files | ✅ | ✅ |
| QQ management (mute, kick, set admin…) | ❌ | ✅ |
| Destructive system operations | ❌ | ⚠️ confirmation required |

Destructive or irreversible admin actions always require explicit confirmation before execution.

**Admin-only QQ tools:** kick, mute, set admin, rename group, whole-group ban, leave group, set portrait, set special title, set/delete essence messages, publish/delete notices, delete group files, handle friend/group requests, delete friend.

---

## Available Tools

| Category | Tools |
|----------|-------|
| Messaging | `qq_send_message`, `qq_recall_message`, `qq_set_msg_emoji_like`, `qq_forward_message`, `qq_send_group_forward_msg`, `qq_send_private_forward_msg`, `qq_mark_msg_as_read` |
| History | `qq_get_group_msg_history`, `qq_get_friend_msg_history`, `qq_get_essence_msg_list`, `qq_set_essence_msg`, `qq_delete_essence_msg` |
| User & Friends | `qq_get_user_info`, `qq_get_friend_list`, `qq_like_user`, `qq_poke`, `qq_set_friend_remark`, `qq_delete_friend`, `qq_handle_friend_request` |
| Group Info | `qq_get_group_info`, `qq_get_group_list`, `qq_get_group_member_info`, `qq_get_group_member_list`, `qq_get_group_honor_info`, `qq_get_group_at_all_remain` |
| Group Management | `qq_mute_group_member`, `qq_kick_group_member`, `qq_set_group_admin`, `qq_set_group_name`, `qq_set_group_card`, `qq_set_group_whole_ban`, `qq_set_group_special_title`, `qq_leave_group`, `qq_set_group_sign`, `qq_set_group_remark`, `qq_set_group_portrait`, `qq_handle_group_request` |
| Notices | `qq_send_group_notice`, `qq_get_group_notice`, `qq_delete_group_notice` |
| Files | `qq_upload_file`, `qq_get_group_root_files`, `qq_get_group_file_url`, `qq_create_group_file_folder`, `qq_delete_group_file`, `qq_download_file` |
| Misc | `qq_ocr_image`, `qq_translate_en2zh` |

---

## How It Works

hermes-napcat never launches NapCat — NapCat runs on its own. The Hermes gateway opens a reverse-WS listener on port 18800 and simply **waits for NapCat to connect**.

1. **NapCat** dials out to `ws://127.0.0.1:18800` (reverse WebSocket)
2. **hermes-napcat** receives the OneBot 11 event, extracts text/media, checks DM/group policy, prefixes sender name in group messages
3. **Hermes Agent** processes the message with full tool access
4. **Response** is sent back via NapCat's HTTP API at `http://127.0.0.1:18801`

### Session isolation

| Chat type | Session key |
|-----------|-------------|
| Private (DM) | One session per QQ user |
| Group (`group_sessions_per_user: false`) | One session per group |
| Group (`group_sessions_per_user: true`) | One session per user per group |

---

## CLI Reference

| Command | Description |
|---------|-------------|
| `hermes-napcat setup` | Interactive setup wizard — patches Hermes + writes configs |
| `hermes-napcat install` | Patch Hermes Agent only |
| `hermes-napcat uninstall` | Remove Hermes patches + config |
| `hermes-napcat status` | Show installation status |

There are no NapCat process-management commands — NapCat is installed and run independently, and simply connects to Hermes when it starts.

---

## Uninstall

```bash
hermes-napcat uninstall    # Remove Hermes patches + config
```

NapCat itself is installed and managed separately, so uninstall never touches it.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Bot not responding in group | Not @-mentioned | @mention the bot in group messages |
| `ECONNREFUSED 127.0.0.1:18800` | Gateway not running | `hermes gateway run` |
| `403 unsupported_user_agent` | API provider blocks SDK user-agent | See [Provider Notes](#notes-for-specific-providers) |
| `KeyError: 'napcat'` | `platforms.py` not patched | Re-run `hermes-napcat install` |
| `Unauthorized user` on all messages | `run.py` auth bypass missing | Re-run `hermes-napcat install` |
| `Permission denied: only admins` | Sender not in admins list | Add QQ to `admins`, or set `admins: []` |

### Notes for specific providers

Some API providers block the OpenAI SDK's default `AsyncOpenAI/Python X.X.X` user-agent. In `~/.hermes/hermes-agent/run_agent.py`, inside `_apply_client_headers_for_base_url`, add before the `else` branch:

```python
elif "your-provider.com" in normalized:
    self._client_kwargs["default_headers"] = {
        "User-Agent": "codex_cli_rs/0.0.0",
        "originator": "codex_cli_rs"
    }
```

Apply the same change at the second location (~line 1176) and in `agent/auxiliary_client.py`.

---

## Contributors

<!-- ALL-CONTRIBUTORS-LIST:START -->
| Avatar | Name | Role |
|--------|------|------|
| [![shubyi](https://github.com/shubyi.png?size=60)](https://github.com/shubyi) | **[shubyi](https://github.com/shubyi)** | Creator & Maintainer |
<!-- ALL-CONTRIBUTORS-LIST:END -->

---

## License

MIT
