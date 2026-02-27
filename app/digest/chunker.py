from app.db.models import Message


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return len(text) // 4


def msg_link(msg: Message) -> str:
    """Build a t.me link to the message."""
    cid = msg.chat_id or 0
    return f"https://t.me/c/{cid}/{msg.telegram_msg_id}"


def format_message(msg: Message) -> str:
    parts = []
    if msg.sender_name:
        parts.append(f"[{msg.sender_name}]")
    if msg.sent_at:
        parts.append(f"({msg.sent_at[:16]})")
    parts.append(msg.content or "")
    parts.append(f"[link: {msg_link(msg)}]")
    return " ".join(parts)


def chunk_messages(
    messages: list[Message],
    token_budget: int = 12000,
) -> list[list[Message]]:
    """Split messages into chunks that fit within the token budget."""
    chunks: list[list[Message]] = []
    current_chunk: list[Message] = []
    current_tokens = 0

    for msg in messages:
        text = format_message(msg)
        tokens = estimate_tokens(text)

        if current_tokens + tokens > token_budget and current_chunk:
            chunks.append(current_chunk)
            current_chunk = []
            current_tokens = 0

        current_chunk.append(msg)
        current_tokens += tokens

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def apply_exclude_filter(messages: list[Message], exclude_filter: str | None) -> list[Message]:
    """Filter out messages matching exclude keywords/author names."""
    if not exclude_filter:
        return messages

    keywords = [kw.strip().lower() for kw in exclude_filter.split(",") if kw.strip()]
    if not keywords:
        return messages

    filtered = []
    for msg in messages:
        text = (msg.content or "").lower()
        sender = (msg.sender_name or "").lower()
        if not any(kw in text or kw in sender for kw in keywords):
            filtered.append(msg)
    return filtered
