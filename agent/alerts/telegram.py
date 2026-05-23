from __future__ import annotations

import re

# In MarkdownV2, these characters must be escaped:
# _ * [ ] ( ) ~ ` > # + - = | { } . !
ESCAPE_CHARS = r"_*[]()~`>#+-=|{}.!"
ESCAPE_RE = re.compile(f"([{re.escape(ESCAPE_CHARS)}])")

def escape_markdownv2(text: str) -> str:
    if not text:
        return ""
    return ESCAPE_RE.sub(r"\\\1", text)

def chunk_message(text: str, max_length: int = 4096) -> list[str]:
    chunks = []
    while len(text) > max_length:
        split_idx = text.rfind("\n", 0, max_length)
        if split_idx == -1:
            split_idx = max_length
        chunks.append(text[:split_idx])
        text = text[split_idx:].lstrip("\n")
    if text:
        chunks.append(text)
    return chunks

def render_container_crash(container_name: str, exit_code: int | None) -> str:
    name = escape_markdownv2(container_name)
    code = escape_markdownv2(str(exit_code))
    return f"🚨 *Container Crash*\n\nContainer `{name}` crashed with exit code {code}\\."

def render_storage_threshold(datastore: str, usage_pct: float) -> str:
    ds = escape_markdownv2(datastore)
    pct = escape_markdownv2(f"{usage_pct:.1f}%")
    return f"⚠️ *Storage Alert*\n\nDatastore `{ds}` is at {pct} usage\\."

def render_unknown_mac(mac_address: str, ip: str | None = None) -> str:
    mac = escape_markdownv2(mac_address)
    ip_str = escape_markdownv2(ip or "Unknown IP")
    return f"🕵️ *Unknown MAC Address*\n\nMAC `{mac}` \\(IP: {ip_str}\\) joined the network\\."

def render_arr_import_mismatch(title: str, expected_path: str, actual_path: str) -> str:
    t = escape_markdownv2(title)
    expected = escape_markdownv2(expected_path)
    actual = escape_markdownv2(actual_path)
    return (
        f"🎬 *Arr Import Mismatch*\n\n"
        f"Title `{t}` imported to `{actual}` but expected `{expected}`\\."
    )

def render_plex_db_warning(warning_type: str, details: str) -> str:
    wt = escape_markdownv2(warning_type)
    det = escape_markdownv2(details)
    return f"🎥 *Plex DB Warning*\n\nWarning `{wt}`: {det}"

async def send_telegram_message(bot_token: str, chat_id: str, text: str) -> None:
    import httpx
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    chunks = chunk_message(text)
    async with httpx.AsyncClient() as client:
        for chunk in chunks:
            response = await client.post(url, json={
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": "MarkdownV2"
            })
            response.raise_for_status()

def send_telegram_message_sync(bot_token: str, chat_id: str, text: str) -> None:
    import httpx
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    chunks = chunk_message(text)
    with httpx.Client() as client:
        for chunk in chunks:
            response = client.post(url, json={
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": "MarkdownV2"
            })
            response.raise_for_status()
