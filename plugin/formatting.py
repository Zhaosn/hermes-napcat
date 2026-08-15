import re

QQ_TEXT_LIMIT = 4000

# Matches a Markdown fenced-code opener/closer at the start of a line.
_FENCE = re.compile(r"^(?P<ticks>`{3,}|~{3,})(?P<rest>.*)$")


# ── Markdown → QQ plain-text ──────────────────────────────────────────────────

def strip_markdown(text: str) -> str:
    """Convert Markdown to clean QQ-friendly plain text.

    QQ does not render Markdown; raw syntax like **bold** or ## heading
    appears as literal characters.  This function converts the most common
    constructs to readable Unicode equivalents.
    """
    lines = text.splitlines()
    out: list[str] = []
    in_code = False
    open_ticks = ""
    code_lang = ""
    code_lines: list[str] = []

    for line in lines:
        m = _FENCE.match(line.strip())
        if m and not in_code:
            in_code = True
            open_ticks = m.group("ticks")
            code_lang = m.group("rest").strip()
            code_lines = []
            continue
        if m and in_code:
            # Close only on a run of the SAME character at least as long as the
            # opener (standard Markdown).  A ``~`` line inside a ``` block, or a
            # shorter run of the same char, is code content — not a closer.
            if m.group("ticks")[0] == open_ticks[0] and len(m.group("ticks")) >= len(open_ticks):
                in_code = False
                label = f"[{code_lang}]" if code_lang else "[代码]"
                out.append(f"┌─{label}─")
                for cl in code_lines:
                    out.append("│ " + cl)
                out.append("└──────")
                code_lines = []
                continue
            code_lines.append(line)
            continue
        if in_code:
            code_lines.append(line)
            continue

        h = re.match(r"^(#{1,6})\s+(.*)", line)
        if h:
            level, title = len(h.group(1)), h.group(2).strip()
            title = _inline(title)
            out.append(f"【{title}】" if level <= 2 else f"▌ {title}")
            continue

        if re.match(r"^\s*[-*_]{3,}\s*$", line):
            out.append("────────────────")
            continue

        bq = re.match(r"^>\s?(.*)", line)
        if bq:
            out.append("「" + _inline(bq.group(1)) + "」")
            continue

        ul = re.match(r"^(\s*)[-*+]\s+(.*)", line)
        if ul:
            indent = len(ul.group(1)) // 2
            out.append("  " * indent + "• " + _inline(ul.group(2)))
            continue

        ol = re.match(r"^(\s*)\d+[.)]\s+(.*)", line)
        if ol:
            indent = len(ol.group(1)) // 2
            num = re.match(r"^\s*(\d+)", line).group(1)
            out.append("  " * indent + num + ". " + _inline(ol.group(2)))
            continue

        if re.match(r"^\s*\|", line):
            if re.match(r"^\s*\|[\s\-:|]+\|\s*$", line):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            out.append("  ".join(_inline(c) for c in cells if c))
            continue

        out.append(_inline(line))

    # Unterminated fence: flush whatever we collected instead of dropping it.
    if in_code:
        label = f"[{code_lang}]" if code_lang else "[代码]"
        out.append(f"┌─{label}─")
        for cl in code_lines:
            out.append("│ " + cl)
        out.append("└──────")

    return "\n".join(out).strip()


def _inline(text: str) -> str:
    """Strip inline Markdown from a single line."""
    text = re.sub(r"`([^`\n]+)`", r"\1", text)
    text = re.sub(r"\*{3}(.+?)\*{3}", r"\1", text)
    text = re.sub(r"_{3}(.+?)_{3}", r"\1", text)
    text = re.sub(r"\*{2}(.+?)\*{2}", r"\1", text)
    text = re.sub(r"_{2}(.+?)_{2}", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"\1", text)
    text = re.sub(r"~~(.+?)~~", r"\1", text)
    # Image first — the link rule below would otherwise swallow the "![alt]"
    # prefix and leave a stray "!alt（url）".
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"[\1]", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1（\2）", text)
    text = re.sub(r"\[([^\]]+)\]\[[^\]]*\]", r"\1", text)
    return text


def chunk_text(text: str, limit: int = QQ_TEXT_LIMIT) -> list[str]:
    """Split long text into chunks at the nearest newline/space boundary."""
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        split = text.rfind("\n", 0, limit)
        if split <= 0:
            split = text.rfind(" ", 0, limit)
        if split <= 0:
            split = limit
        chunks.append(text[:split])
        text = text[split:].lstrip()
    return chunks


# ── OneBot 11 message-segment extraction ──────────────────────────────────────

def extract_text(segments: list[dict]) -> str:
    parts = []
    for s in segments:
        if s["type"] == "text":
            parts.append(s["data"].get("text", ""))
        elif s["type"] == "at":
            parts.append(f"@{s['data'].get('qq', '')}")
    return "".join(parts).strip()


def extract_images(segments: list[dict]) -> list[str]:
    return [
        s["data"].get("url") or s["data"].get("file", "")
        for s in segments if s["type"] == "image"
        if s["data"].get("url") or s["data"].get("file")
    ]


def extract_record(segments: list[dict]) -> str | None:
    for s in segments:
        if s["type"] == "record":
            return s["data"].get("url") or s["data"].get("file")
    return None


def extract_reply_id(segments: list[dict]) -> int | None:
    for s in segments:
        if s["type"] == "reply":
            try:
                return int(s["data"]["id"])
            except (KeyError, ValueError):
                pass
    return None


def has_bot_mention(segments: list[dict], self_id: str) -> bool:
    return any(
        s["type"] == "at" and str(s["data"].get("qq")) == self_id
        for s in segments
    )


def strip_bot_mention(segments: list[dict], self_id: str) -> list[dict]:
    return [
        s for s in segments
        if not (s["type"] == "at" and str(s["data"].get("qq")) == self_id)
    ]
