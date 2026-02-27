def split_message(text: str, max_len: int = 4096) -> list[str]:
    """Split a long message into chunks <= max_len, trying to break at newlines."""
    if len(text) <= max_len:
        return [text]

    parts = []
    while text:
        if len(text) <= max_len:
            parts.append(text)
            break

        # Find last newline within limit
        split_at = text.rfind("\n", 0, max_len)
        if split_at == -1:
            split_at = max_len

        parts.append(text[:split_at])
        text = text[split_at:].lstrip("\n")

    return parts
