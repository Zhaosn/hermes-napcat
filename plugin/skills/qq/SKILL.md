---
name: qq-napcat
description: Interact with QQ via NapCat / OneBot 11 — send messages, manage groups, handle files, look up members, react to messages, and more. Use this skill whenever the user mentions QQ, group chat management, NapCat, OneBot, or wants to interact with a Chinese messaging platform. Even if they don't explicitly say "QQ tool", if the task involves sending messages to QQ groups, muting/kicking members, reading chat history, uploading files to a group, or managing a QQ bot — use this skill. Also trigger when the user pastes a QQ group number or QQ user ID and asks to send a message, fetch chat history, or look up member info — even if they don't mention "NapCat" or "OneBot" by name.
version: 1.1.0
author: hermes-napcat
license: MIT
platforms: [linux]
prerequisites:
  services: [napcat, hermes-gateway]
metadata:
  hermes:
    tags: [qq, napcat, onebot, messaging, group-management, china]
    homepage: https://github.com/NapNeko/NapCatQQ
---

# QQ (NapCat / OneBot 11)

NapCat is a headless QQ client that exposes the OneBot 11 API. Hermes connects via reverse WebSocket — the adapter runs a WS server (default `ws://0.0.0.0:18801/onebot/v11`) and NapCat dials in as the client in Universal mode (API + events over one full-duplex connection).

All tools in this skill are prefixed `qq_`.

---

## When to Use This Skill

- Sending text, images, files, reactions, or merged-forward messages to groups or private chats
- Reading message history and essence (精华) message lists
- Group management: mute, kick, set admin, rename, set avatar, publish notices
- Member and friend info lookups
- Handling friend and group join requests
- Group file system operations
- Image OCR and QQ translation

---

## Admin System

Some tools are restricted to admins. Admins are configured in `~/.hermes/config.yaml`:

```yaml
platforms:
  napcat:
    extra:
      admins: ["123456789", "987654321"]
```

If `admins` is empty, **all users** can call any tool (open mode). When admins are set, non-admin callers receive: `Permission denied: only admins can use this command`.

Admins can also be set via the `NAPCAT_ADMINS` environment variable (comma-separated QQ numbers) when deploying as a Hermes plugin — this is the more common path for containerized setups. The `config.yaml` path applies to manual / non-plugin installations.

**Admin-required tools:** `qq_mute_group_member`, `qq_kick_group_member`, `qq_kick_group_members`, `qq_set_group_admin`, `qq_set_group_name`, `qq_set_group_whole_ban`, `qq_leave_group`, `qq_set_group_portrait`, `qq_set_group_special_title`, `qq_set_essence_msg`, `qq_delete_essence_msg`, `qq_send_group_notice`, `qq_delete_group_notice`, `qq_delete_group_file`, `qq_delete_group_folder`, `qq_set_group_todo`, `qq_delete_friend`, `qq_handle_friend_request`, `qq_handle_group_request`, `qq_send_qzone_msg`, `qq_set_qq_avatar`, `qq_set_self_longnick`, `qq_set_online_status`, `qq_upload_image_to_qun_album`

---

## Message Format (OneBot 11 Segments)

The `message` parameter is always an **array of segment objects**. Common types:

```json
[{"type": "text", "data": {"text": "Hello!"}}]
[{"type": "image", "data": {"file": "/path/to/image.jpg"}}]
[{"type": "image", "data": {"file": "https://example.com/img.png"}}]
[{"type": "at", "data": {"qq": "123456789"}}, {"type": "text", "data": {"text": " check this"}}]
[{"type": "reply", "data": {"id": "MESSAGE_ID"}}, {"type": "text", "data": {"text": "Replying to you"}}]
[{"type": "face", "data": {"id": "76"}}]
[{"type": "record", "data": {"file": "/path/to/audio.silk"}}]
[{"type": "video", "data": {"file": "/path/to/video.mp4"}}]
```

To send plain text, wrap it: `[{"type": "text", "data": {"text": "your message"}}]`

---

## Quick Reference

| Action | Tool |
|---|---|
| Send to group | `qq_send_message` (message_type=group) |
| Send to private | `qq_send_message` (message_type=private) |
| Recall a message | `qq_recall_message` |
| React with emoji | `qq_set_msg_emoji_like` |
| Mark as read | `qq_mark_msg_as_read` |
| Forward a message | `qq_forward_message` |
| Send merged-forward to group | `qq_send_group_forward_msg` |
| Send merged-forward to user | `qq_send_private_forward_msg` |
| Group message history | `qq_get_group_msg_history` |
| Friend message history | `qq_get_friend_msg_history` |
| Get/set/delete essence messages | `qq_get_essence_msg_list`, `qq_set_essence_msg` ★, `qq_delete_essence_msg` ★ |
| Get user info | `qq_get_user_info` |
| Get friend list | `qq_get_friend_list` |
| Poke a user | `qq_poke` |
| Set friend remark | `qq_set_friend_remark` |
| Delete friend | `qq_delete_friend` ★ |
| Accept/reject friend request | `qq_handle_friend_request` ★ |
| Get group info / list / members | `qq_get_group_info`, `qq_get_group_list`, `qq_get_group_member_info`, `qq_get_group_member_list` |
| Get group honors | `qq_get_group_honor_info` |
| Check @all quota | `qq_get_group_at_all_remain` |
| Mute member | `qq_mute_group_member` ★ |
| Kick member(s) | `qq_kick_group_member` ★, `qq_kick_group_members` ★ |
| Set/revoke admin | `qq_set_group_admin` ★ |
| Rename group | `qq_set_group_name` ★ |
| Set member card (nickname) | `qq_set_group_card` |
| Whole-group mute | `qq_set_group_whole_ban` ★ |
| Set special title | `qq_set_group_special_title` ★ |
| Leave / dismiss group | `qq_leave_group` ★ |
| Group check-in (打卡) | `qq_set_group_sign` |
| Set group remark | `qq_set_group_remark` |
| Set group avatar | `qq_set_group_portrait` ★ |
| Accept/reject group request | `qq_handle_group_request` ★ |
| Group notices (公告) | `qq_send_group_notice` ★, `qq_get_group_notice`, `qq_delete_group_notice` ★ |
| File upload / browse / download | `qq_upload_file`, `qq_get_group_root_files`, `qq_get_group_file_url`, `qq_create_group_file_folder`, `qq_delete_group_file` ★, `qq_delete_group_folder` ★ |
| Download URL via NapCat | `qq_download_file` |
| OCR image | `qq_ocr_image` |
| Translate EN→ZH | `qq_translate_en2zh` |
| Resolve file/image/voice by id | `qq_get_file`, `qq_get_image`, `qq_get_record` |
| Who reacted to a message | `qq_get_emoji_likes` |
| Recent conversations | `qq_get_recent_contact` |
| Flash photo (闪照) | `qq_create_flash_task`, `qq_send_flash_msg` |
| Group file system info | `qq_get_group_detail_info`, `qq_get_group_shut_list`, `qq_get_group_files_by_folder`, `qq_get_group_file_system_info` |
| Group todo (待办) | `qq_set_group_todo` ★, `qq_complete_group_todo` |
| Today's check-in list | `qq_get_group_signed_list` |
| Friend list by category / one-way | `qq_get_friends_with_category`, `qq_get_unidirectional_friend_list` |
| Bot avatar / signature / status | `qq_set_qq_avatar` ★, `qq_set_self_longnick` ★, `qq_set_online_status` ★ |
| Post QQ Space (说说) | `qq_send_qzone_msg` ★ |
| Group albums | `qq_get_qun_album_list`, `qq_upload_image_to_qun_album` ★ |
| NapCat version / status | `qq_get_version_info`, `qq_get_status` |

★ = requires admin

**For detailed parameter signatures and examples, read `references/tool-details.md`.**

---

## Core Workflows

### Reply to a message in a group
The incoming event includes `message_id` and `group_id`. Quote-reply by prepending a reply segment:
```
qq_send_message(
  message_type = "group",
  group_id     = "GROUP_ID",
  message      = [
    {"type": "reply", "data": {"id": "ORIGINAL_MESSAGE_ID"}},
    {"type": "text",  "data": {"text": "Here is my response"}}
  ]
)
```

### @ a user in a group message
```
qq_send_message(
  message_type = "group",
  group_id     = "GROUP_ID",
  message      = [
    {"type": "at",   "data": {"qq": "TARGET_QQ_NUMBER"}},
    {"type": "text", "data": {"text": " please read this"}}
  ]
)
```

### Send an image
```
qq_send_message(
  message_type = "group",
  group_id     = "GROUP_ID",
  message      = [{"type": "image", "data": {"file": "/path/to/image.jpg"}}]
)
```

### Mute then notify
```
qq_mute_group_member(group_id = "G", user_id = "U", duration = 3600)
qq_send_message(
  message_type = "group",
  group_id     = "G",
  message      = [{"type": "text", "data": {"text": "User has been muted for 1 hour."}}]
)
```

### Look up who is currently the most active (龙王)
```
qq_get_group_honor_info(group_id = "GROUP_ID", type = "talkative")
```

### Read group chat history before responding
```
qq_get_group_msg_history(group_id = "GROUP_ID", count = 20)
```
Parse the returned `messages` array. Each entry has: `message_id`, `sender.user_id`, `sender.nickname`, `time`, and `message` (array of segments).

---

## Agent Workflow

1. Identify whether the request is for a **group** or **private** conversation from context.
2. For **management actions** (mute, kick, admin, notice, etc.), confirm the sender is an admin before calling — the tool will reject non-admins anyway, but confirming first avoids a wasted call.
3. For **irreversible actions** (kick with `reject_add_request=true`, dismiss group, delete friend), briefly confirm with the user before proceeding.
4. When the user asks to "reply" to a message, use a `reply` segment pointing to the original `message_id` — do not just send plain text.
5. For bulk history reads, use `qq_get_group_msg_history` with `count ≤ 50` to avoid overloading context.
6. When sending images or files, prefer local paths if the file is already on disk — NapCat can serve local files directly, avoiding an extra HTTP round-trip. Use URLs only when the file is remote and not worth downloading first.
7. The `message_id` in incoming events is the value to pass to `qq_recall_message`, `qq_set_essence_msg`, etc.

---

## Protocol Limits

| Constraint | Detail |
|---|---|
| Recall window | **2 minutes** — `qq_recall_message` fails after that |
| @all quota | Limited per group per day; check with `qq_get_group_at_all_remain` |
| Special title | Bot must be **group owner** (not just admin) |
| Group dismiss | Bot must be **group owner** (`is_dismiss=true`) |
| Mute duration | 0 = unmute; max is ~2592000 s (30 days) |
| Admin grant | Only **group owner** can set admin; admin cannot grant admin to others |
| File upload size | Depends on QQ account level; typically ≤ 100 MB for regular accounts |

---

## Error Handling

For connection issues, permission errors, and API error codes, read `references/error-handling.md`.
