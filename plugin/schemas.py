def _schema(name: str, desc: str, props: dict, required: list[str] | None = None) -> dict:
    return {
        "name": name,
        "description": desc,
        "parameters": {
            "type": "object",
            "properties": props,
            "required": required or [],
        },
    }


def _str(desc: str) -> dict:
    return {"type": "string", "description": desc}


def _int(desc: str) -> dict:
    return {"type": "integer", "description": desc}


def _bool(desc: str) -> dict:
    return {"type": "boolean", "description": desc}


SCHEMAS: dict[str, dict] = {}

# ══════════════════════════════════════════════════════════════════════════════
# 1. MESSAGING
# ══════════════════════════════════════════════════════════════════════════════

SCHEMAS["qq_send_message"] = _schema(
    "qq_send_message",
    "Send a QQ message to a group or private chat. "
    "message is a list of OneBot 11 segments, e.g. [{\"type\":\"text\",\"data\":{\"text\":\"hello\"}}].",
    {
        "message_type": _str("'group' or 'private'"),
        "group_id": _str("Group ID (required when message_type=group)"),
        "user_id": _str("User QQ number (required when message_type=private)"),
        "message": {
            "type": "array",
            "description": "OneBot 11 message segments",
            "items": {"type": "object"},
        },
    },
    required=["message_type", "message"],
)

SCHEMAS["qq_recall_message"] = _schema(
    "qq_recall_message", "Recall (unsend) a QQ message by its message_id.",
    {"message_id": _str("Message ID to recall")},
    required=["message_id"],
)

SCHEMAS["qq_mark_msg_as_read"] = _schema(
    "qq_mark_msg_as_read", "Mark a message as read.",
    {"message_id": _str("Message ID")},
    required=["message_id"],
)

SCHEMAS["qq_set_msg_emoji_like"] = _schema(
    "qq_set_msg_emoji_like", "React to a message with an emoji (QQ emoji ID).",
    {
        "message_id": _str("Message ID"),
        "emoji_id": _str("QQ emoji ID (integer as string, e.g. '76' for 赞)"),
    },
    required=["message_id", "emoji_id"],
)

SCHEMAS["qq_forward_message"] = _schema(
    "qq_forward_message", "Forward a single message to a group or private chat.",
    {
        "message_id": _str("Message ID to forward"),
        "group_id": _str("Destination group ID"),
        "user_id": _str("Destination user QQ number"),
    },
    required=["message_id"],
)

SCHEMAS["qq_send_group_forward_msg"] = _schema(
    "qq_send_group_forward_msg",
    "Send a merged-forward message to a group. messages is a list of forward node segments.",
    {
        "group_id": _str("Target group ID"),
        "messages": {
            "type": "array",
            "description": "List of forward node segments",
            "items": {"type": "object"},
        },
    },
    required=["group_id", "messages"],
)

SCHEMAS["qq_send_private_forward_msg"] = _schema(
    "qq_send_private_forward_msg",
    "Send a merged-forward message to a private chat.",
    {
        "user_id": _str("Target user QQ number"),
        "messages": {
            "type": "array",
            "description": "List of forward node segments",
            "items": {"type": "object"},
        },
    },
    required=["user_id", "messages"],
)

# ══════════════════════════════════════════════════════════════════════════════
# 2. MESSAGE HISTORY & ESSENCE
# ══════════════════════════════════════════════════════════════════════════════

SCHEMAS["qq_get_group_msg_history"] = _schema(
    "qq_get_group_msg_history", "Fetch recent message history from a group.",
    {
        "group_id": _str("Group ID"),
        "message_seq": _str(
            "Start from the message after this message_seq (sequence number; "
            "fetches messages newer than it). Optional, defaults to latest."
        ),
        "count": _int("Number of messages to fetch (default 20, max 100)"),
    },
    required=["group_id"],
)

SCHEMAS["qq_get_friend_msg_history"] = _schema(
    "qq_get_friend_msg_history", "Fetch recent message history with a friend.",
    {
        "user_id": _str("Friend QQ number"),
        "message_seq": _str(
            "Start from the message after this message_seq (sequence number; "
            "fetches messages newer than it). Optional, defaults to latest."
        ),
        "count": _int("Number of messages to fetch (default 20)"),
    },
    required=["user_id"],
)

SCHEMAS["qq_get_essence_msg_list"] = _schema(
    "qq_get_essence_msg_list", "Get the list of essence (pinned highlight) messages in a group.",
    {"group_id": _str("Group ID")},
    required=["group_id"],
)

SCHEMAS["qq_set_essence_msg"] = _schema(
    "qq_set_essence_msg", "Set a message as an essence (highlight) message in a group. Requires admin.",
    {"message_id": _str("Message ID")},
    required=["message_id"],
)

SCHEMAS["qq_delete_essence_msg"] = _schema(
    "qq_delete_essence_msg", "Remove a message from the group's essence list. Requires admin.",
    {"message_id": _str("Message ID")},
    required=["message_id"],
)

# ══════════════════════════════════════════════════════════════════════════════
# 3. USER & FRIEND INFO
# ══════════════════════════════════════════════════════════════════════════════

SCHEMAS["qq_get_user_info"] = _schema(
    "qq_get_user_info", "Get basic info (nickname, avatar, etc.) for any QQ user.",
    {"user_id": _str("QQ number")},
    required=["user_id"],
)

SCHEMAS["qq_get_friend_list"] = _schema("qq_get_friend_list", "Get the bot's friend list.", {})

SCHEMAS["qq_set_friend_remark"] = _schema(
    "qq_set_friend_remark", "Set or clear the remark (alias) for a friend.",
    {
        "user_id": _str("Friend QQ number"),
        "remark": _str("New remark (blank to clear)"),
    },
    required=["user_id"],
)

SCHEMAS["qq_delete_friend"] = _schema(
    "qq_delete_friend", "Delete a friend. Requires admin.",
    {"user_id": _str("Friend QQ number to remove")},
    required=["user_id"],
)

SCHEMAS["qq_handle_friend_request"] = _schema(
    "qq_handle_friend_request", "Accept or reject an incoming friend request. Requires admin.",
    {
        "flag": _str("Request flag from the friend_request event"),
        "approve": _bool("True to accept, False to reject (default True)"),
        "remark": _str("Remark to set on accept (optional)"),
    },
    required=["flag"],
)

SCHEMAS["qq_poke"] = _schema(
    "qq_poke", "Poke (nudge) a user in a group or private chat.",
    {
        "user_id": _str("Target QQ number"),
        "group_id": _str("Group ID (omit for private poke)"),
    },
    required=["user_id"],
)

# ══════════════════════════════════════════════════════════════════════════════
# 4. GROUP INFO
# ══════════════════════════════════════════════════════════════════════════════

SCHEMAS["qq_get_group_info"] = _schema(
    "qq_get_group_info", "Get basic info for a QQ group (name, member count, etc.).",
    {"group_id": _str("Group ID")},
    required=["group_id"],
)

SCHEMAS["qq_get_group_list"] = _schema("qq_get_group_list", "Get the list of all groups the bot has joined.", {})

SCHEMAS["qq_get_group_member_info"] = _schema(
    "qq_get_group_member_info", "Get detailed info for a group member.",
    {
        "group_id": _str("Group ID"),
        "user_id": _str("Member QQ number"),
    },
    required=["group_id", "user_id"],
)

SCHEMAS["qq_get_group_member_list"] = _schema(
    "qq_get_group_member_list", "List all members of a group.",
    {"group_id": _str("Group ID")},
    required=["group_id"],
)

SCHEMAS["qq_get_group_honor_info"] = _schema(
    "qq_get_group_honor_info",
    "Get honor info (龙王/群聊之火/etc.) for a group.",
    {
        "group_id": _str("Group ID"),
        "type": _str("Honor type: talkative | performer | legend | strong_newbie | emotion | all (default)"),
    },
    required=["group_id"],
)

SCHEMAS["qq_get_group_at_all_remain"] = _schema(
    "qq_get_group_at_all_remain",
    "Check remaining @all usage count for a group today.",
    {"group_id": _str("Group ID")},
    required=["group_id"],
)

# ══════════════════════════════════════════════════════════════════════════════
# 5. GROUP MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

SCHEMAS["qq_mute_group_member"] = _schema(
    "qq_mute_group_member", "Mute a group member for a given duration (0 = unmute). Requires admin.",
    {
        "group_id": _str("Group ID"),
        "user_id": _str("Member QQ number"),
        "duration": _int("Mute duration in seconds (0 = unmute, default 600)"),
    },
    required=["group_id", "user_id"],
)

SCHEMAS["qq_kick_group_member"] = _schema(
    "qq_kick_group_member", "Kick a member from a group. Requires admin.",
    {
        "group_id": _str("Group ID"),
        "user_id": _str("Member QQ number"),
        "reject_add_request": _bool("Also block them from rejoining (default false)"),
    },
    required=["group_id", "user_id"],
)

SCHEMAS["qq_set_group_admin"] = _schema(
    "qq_set_group_admin", "Grant or revoke group admin for a member. Requires admin.",
    {
        "group_id": _str("Group ID"),
        "user_id": _str("Member QQ number"),
        "enable": _bool("True = grant admin, False = revoke (default True)"),
    },
    required=["group_id", "user_id"],
)

SCHEMAS["qq_set_group_name"] = _schema(
    "qq_set_group_name", "Rename a group. Requires admin.",
    {
        "group_id": _str("Group ID"),
        "group_name": _str("New group name"),
    },
    required=["group_id", "group_name"],
)

SCHEMAS["qq_set_group_card"] = _schema(
    "qq_set_group_card", "Set or clear a member's in-group nickname (card).",
    {
        "group_id": _str("Group ID"),
        "user_id": _str("Member QQ number"),
        "card": _str("New nickname (blank to reset to real name)"),
    },
    required=["group_id", "user_id"],
)

SCHEMAS["qq_set_group_whole_ban"] = _schema(
    "qq_set_group_whole_ban", "Enable or disable whole-group mute. Requires admin.",
    {
        "group_id": _str("Group ID"),
        "enable": _bool("True = mute all, False = unmute all (default True)"),
    },
    required=["group_id"],
)

SCHEMAS["qq_set_group_special_title"] = _schema(
    "qq_set_group_special_title", "Set a custom special title for a group member (owner only). Requires admin.",
    {
        "group_id": _str("Group ID"),
        "user_id": _str("Member QQ number"),
        "special_title": _str("Title text (blank to clear)"),
    },
    required=["group_id", "user_id"],
)

SCHEMAS["qq_leave_group"] = _schema(
    "qq_leave_group", "Leave a group (or dismiss it if the bot is the owner). Requires admin.",
    {
        "group_id": _str("Group ID"),
        "is_dismiss": _bool("True to dismiss the group (bot must be owner)"),
    },
    required=["group_id"],
)

SCHEMAS["qq_set_group_sign"] = _schema(
    "qq_set_group_sign", "Perform group sign-in (打卡).",
    {"group_id": _str("Group ID")},
    required=["group_id"],
)

SCHEMAS["qq_set_group_remark"] = _schema(
    "qq_set_group_remark", "Set a personal remark for a group (visible only to you).",
    {
        "group_id": _str("Group ID"),
        "remark": _str("Remark text (blank to clear)"),
    },
    required=["group_id"],
)

SCHEMAS["qq_set_group_portrait"] = _schema(
    "qq_set_group_portrait", "Set the group avatar (owner/admin only). Requires admin.",
    {
        "group_id": _str("Group ID"),
        "file": _str("Image file path or URL"),
    },
    required=["group_id", "file"],
)

SCHEMAS["qq_handle_group_request"] = _schema(
    "qq_handle_group_request", "Accept or reject a group join request or group invite. Requires admin.",
    {
        "flag": _str("Request flag from the group_request event"),
        "sub_type": _str("'add' for join request, 'invite' for bot invite (default 'add')"),
        "approve": _bool("True to approve, False to reject (default True)"),
        "reason": _str("Rejection reason (only used when approve=False)"),
    },
    required=["flag"],
)

# ══════════════════════════════════════════════════════════════════════════════
# 6. GROUP NOTICES
# ══════════════════════════════════════════════════════════════════════════════

SCHEMAS["qq_send_group_notice"] = _schema(
    "qq_send_group_notice", "Publish a group announcement. Requires admin.",
    {
        "group_id": _str("Group ID"),
        "content": _str("Announcement text"),
        "image": _str("Optional image path or URL to attach"),
    },
    required=["group_id", "content"],
)

SCHEMAS["qq_get_group_notice"] = _schema(
    "qq_get_group_notice", "Get the list of group announcements.",
    {"group_id": _str("Group ID")},
    required=["group_id"],
)

SCHEMAS["qq_delete_group_notice"] = _schema(
    "qq_delete_group_notice", "Delete a group announcement. Requires admin.",
    {
        "group_id": _str("Group ID"),
        "notice_id": _str("Notice ID (from qq_get_group_notice)"),
    },
    required=["group_id", "notice_id"],
)

# ══════════════════════════════════════════════════════════════════════════════
# 7. FILE OPERATIONS
# ══════════════════════════════════════════════════════════════════════════════

SCHEMAS["qq_upload_file"] = _schema(
    "qq_upload_file", "Upload a file to a group or private chat.",
    {
        "file": _str("Local file path or URL"),
        "name": _str("Display name for the file"),
        "group_id": _str("Upload to this group (mutually exclusive with user_id)"),
        "user_id": _str("Upload to this user's private chat"),
        "folder_id": _str("Target folder ID within the group (optional)"),
    },
    required=["file"],
)

SCHEMAS["qq_get_group_root_files"] = _schema(
    "qq_get_group_root_files", "List files and folders in a group's root file directory.",
    {"group_id": _str("Group ID")},
    required=["group_id"],
)

SCHEMAS["qq_get_group_file_url"] = _schema(
    "qq_get_group_file_url", "Get a temporary download URL for a group file.",
    {
        "group_id": _str("Group ID"),
        "file_id": _str("File ID (from qq_get_group_root_files)"),
        "busid": _int("busid from the file listing (default 0)"),
    },
    required=["group_id", "file_id"],
)

SCHEMAS["qq_create_group_file_folder"] = _schema(
    "qq_create_group_file_folder", "Create a folder in the group file system.",
    {
        "group_id": _str("Group ID"),
        "name": _str("Folder name"),
        "parent_id": _str("Parent folder ID (default '/' for root)"),
    },
    required=["group_id", "name"],
)

SCHEMAS["qq_delete_group_file"] = _schema(
    "qq_delete_group_file", "Delete a file from the group file system. Requires admin.",
    {
        "group_id": _str("Group ID"),
        "file_id": _str("File ID"),
        "busid": _int("busid from the file listing (default 0)"),
    },
    required=["group_id", "file_id"],
)

SCHEMAS["qq_download_file"] = _schema(
    "qq_download_file",
    "Ask NapCat to download a file from a URL and return the local path.",
    {
        "url": _str("URL to download"),
        "thread_count": _int("Download threads (default 1)"),
        "headers": _str("Extra HTTP headers as a string (optional)"),
    },
    required=["url"],
)

# ══════════════════════════════════════════════════════════════════════════════
# 8. MISC
# ══════════════════════════════════════════════════════════════════════════════

SCHEMAS["qq_ocr_image"] = _schema(
    "qq_ocr_image", "Run OCR on an image and return the recognized text.",
    {"image": _str("Image file path or URL")},
    required=["image"],
)

SCHEMAS["qq_translate_en2zh"] = _schema(
    "qq_translate_en2zh",
    "Translate a list of English words to Chinese using the QQ translation service "
    "(translates individual words, not full sentences).",
    {
        "words": {
            "type": "array",
            "description": "English words to translate",
            "items": {"type": "string"},
        },
    },
    required=["words"],
)

# ══════════════════════════════════════════════════════════════════════════════
# 9. MEDIA & CONTENT
# ══════════════════════════════════════════════════════════════════════════════

SCHEMAS["qq_get_file"] = _schema(
    "qq_get_file", "Resolve a file id/path/URL to its local path and download URL.",
    {"file": _str("File id, local path or URL")},
    required=["file"],
)

SCHEMAS["qq_get_image"] = _schema(
    "qq_get_image", "Resolve an image id/path/URL to its local path and download URL.",
    {"file": _str("Image id (e.g. from a received image segment), local path or URL")},
    required=["file"],
)

SCHEMAS["qq_get_record"] = _schema(
    "qq_get_record", "Resolve a voice id/path/URL to a local path, converting format if needed.",
    {
        "file": _str("Voice id, local path or URL"),
        "out_format": _str("Output format (e.g. mp3, wav, silk; default mp3)"),
    },
    required=["file"],
)

SCHEMAS["qq_get_emoji_likes"] = _schema(
    "qq_get_emoji_likes", "Get the list of users who reacted to a message with a given emoji.",
    {
        "message_id": _str("Message ID"),
        "emoji_id": _str("Emoji ID"),
        "group_id": _str("Group ID (optional for private chat)"),
        "count": _int("Max users to return (0 = all, default)"),
    },
    required=["message_id", "emoji_id"],
)

SCHEMAS["qq_get_recent_contact"] = _schema(
    "qq_get_recent_contact", "List the bot's most recent conversations (people/groups).",
    {"count": _int("Number of recent chats to return (default 10)")},
)

SCHEMAS["qq_create_flash_task"] = _schema(
    "qq_create_flash_task", "Create a flash-photo (闪照) task from an image, returning a fileset_id for qq_send_flash_msg.",
    {
        "files": {
            "type": "array",
            "description": "Image path(s) to flash-send",
            "items": {"type": "string"},
        },
        "name": _str("Task name (optional)"),
    },
    required=["files"],
)

SCHEMAS["qq_send_flash_msg"] = _schema(
    "qq_send_flash_msg", "Send a flash message (闪照) to a group or private chat using a fileset_id from qq_create_flash_task.",
    {
        "fileset_id": _str("fileset_id from qq_create_flash_task"),
        "group_id": _str("Target group ID (mutually exclusive with user_id)"),
        "user_id": _str("Target user QQ number"),
    },
    required=["fileset_id"],
)

# ══════════════════════════════════════════════════════════════════════════════
# 10. GROUP EXTENDED
# ══════════════════════════════════════════════════════════════════════════════

SCHEMAS["qq_kick_group_members"] = _schema(
    "qq_kick_group_members", "Kick multiple members from a group in one call. Requires admin.",
    {
        "group_id": _str("Group ID"),
        "user_id": {
            "type": "array",
            "description": "QQ numbers to kick",
            "items": {"type": "string"},
        },
        "reject_add_request": _bool("Also block them from rejoining (default false)"),
    },
    required=["group_id", "user_id"],
)

SCHEMAS["qq_get_group_shut_list"] = _schema(
    "qq_get_group_shut_list", "List the currently muted members of a group.",
    {"group_id": _str("Group ID")},
    required=["group_id"],
)

SCHEMAS["qq_get_group_detail_info"] = _schema(
    "qq_get_group_detail_info", "Get detailed group info (member count, whole-ban state, remark, etc.).",
    {"group_id": _str("Group ID")},
    required=["group_id"],
)

SCHEMAS["qq_get_group_files_by_folder"] = _schema(
    "qq_get_group_files_by_folder", "List files and sub-folders inside a group file folder.",
    {
        "group_id": _str("Group ID"),
        "folder_id": _str("Folder ID (default '/' for root)"),
        "file_count": _int("Max entries to return (default 50)"),
    },
    required=["group_id"],
)

SCHEMAS["qq_delete_group_folder"] = _schema(
    "qq_delete_group_folder", "Delete a folder from the group file system. Requires admin.",
    {
        "group_id": _str("Group ID"),
        "folder_id": _str("Folder ID"),
    },
    required=["group_id", "folder_id"],
)

SCHEMAS["qq_get_group_file_system_info"] = _schema(
    "qq_get_group_file_system_info", "Get a group file system's usage (file count, space used/limit).",
    {"group_id": _str("Group ID")},
    required=["group_id"],
)

SCHEMAS["qq_set_group_todo"] = _schema(
    "qq_set_group_todo", "Turn a group message into a group todo (待办). Requires admin.",
    {
        "group_id": _str("Group ID"),
        "message_id": _str("Message ID to pin as todo"),
    },
    required=["group_id", "message_id"],
)

SCHEMAS["qq_complete_group_todo"] = _schema(
    "qq_complete_group_todo", "Mark a group todo as completed.",
    {
        "group_id": _str("Group ID"),
        "message_id": _str("Message ID of the todo"),
    },
    required=["group_id", "message_id"],
)

SCHEMAS["qq_get_group_signed_list"] = _schema(
    "qq_get_group_signed_list", "Get the list of members who checked in (打卡) today in a group.",
    {"group_id": _str("Group ID")},
    required=["group_id"],
)

# ══════════════════════════════════════════════════════════════════════════════
# 11. USER & SELF
# ══════════════════════════════════════════════════════════════════════════════

SCHEMAS["qq_get_friends_with_category"] = _schema("qq_get_friends_with_category", "Get the friend list grouped by category (分组).", {})

SCHEMAS["qq_get_unidirectional_friend_list"] = _schema(
    "qq_get_unidirectional_friend_list",
    "Get the one-way friend list (people who have you but are not your friend).",
    {},
)

SCHEMAS["qq_set_qq_avatar"] = _schema(
    "qq_set_qq_avatar", "Change the bot's QQ avatar. Requires admin.",
    {"file": _str("Image path, URL or base64://")},
    required=["file"],
)

SCHEMAS["qq_set_self_longnick"] = _schema(
    "qq_set_self_longnick", "Set the bot's QQ personal signature (个性签名). Requires admin.",
    {"long_nick": _str("New signature text")},
    required=["long_nick"],
)

SCHEMAS["qq_set_online_status"] = _schema(
    "qq_set_online_status", "Set the bot's custom online status. Requires admin.",
    {
        "face_id": _str("Icon ID (face_id from set_diy_online_status API)"),
        "face_type": _str("Icon type (default '1')"),
        "wording": _str("Status text (default single space)"),
    },
    required=["face_id", "face_type", "wording"],
)

# ══════════════════════════════════════════════════════════════════════════════
# 12. QZONE, ALBUMS & SYSTEM
# ══════════════════════════════════════════════════════════════════════════════

SCHEMAS["qq_send_qzone_msg"] = _schema(
    "qq_send_qzone_msg", "Post a QQ Space (Qzone) 说说 with optional images. Requires admin.",
    {
        "content": _str("Post body text"),
        "images": {
            "type": "array",
            "description": "Image paths/URLs (file://, http(s)://, base64://)",
            "items": {"type": "string"},
        },
        "ugc_right": _int("Visibility: 1 all, 4 friends, 16 some friends, 64 self, 128 some friends excluded (default 1)"),
        "target_uins": {
            "type": "array",
            "description": "QQ numbers when ugc_right is 16 or 128",
            "items": {"type": "string"},
        },
    },
    required=["content"],
)

SCHEMAS["qq_get_qun_album_list"] = _schema(
    "qq_get_qun_album_list", "List the albums of a group.",
    {
        "group_id": _str("Group ID"),
        "attach_info": _str("Pagination token from a previous result (optional)"),
    },
    required=["group_id"],
)

SCHEMAS["qq_upload_image_to_qun_album"] = _schema(
    "qq_upload_image_to_qun_album", "Upload an image into a group album. Requires admin.",
    {
        "group_id": _str("Group ID"),
        "album_id": _str("Album ID (from qq_get_qun_album_list)"),
        "album_name": _str("Album name (fallback)"),
        "file": _str("Image path, URL or base64://"),
    },
    required=["group_id", "album_id", "file"],
)

SCHEMAS["qq_get_version_info"] = _schema("qq_get_version_info", "Get NapCat version information.", {})

SCHEMAS["qq_get_status"] = _schema("qq_get_status", "Get NapCat runtime status (online/good).", {})
