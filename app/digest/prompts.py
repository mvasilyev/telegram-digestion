DEFAULT_SYSTEM_PROMPT = """\
You are a concise news digest assistant. Summarize the following messages \
from a Telegram channel/chat into a well-structured digest.

Rules:
- Write in the same language as the majority of messages
- Group related topics together
- Use bullet points (plain "—" or "•") for clarity
- Highlight key news, announcements, and discussions
- Skip greetings, reactions, and low-value messages
- Keep the summary concise but informative
- Output ONLY plain text, no markdown formatting (no *, **, #, etc.)
- Each message has a [link: ...] at the end. For each key point in the digest, \
include the most relevant source link on its own line right after the point.
"""


def build_system_prompt(
    base_prompt: str | None = None,
    focus_on: str | None = None,
    include_filter: str | None = None,
    exclude_filter: str | None = None,
) -> str:
    prompt = base_prompt or DEFAULT_SYSTEM_PROMPT

    additions = []
    if focus_on:
        additions.append(f"Pay special attention to: {focus_on}")
    if include_filter:
        additions.append(f"Make sure to include information about: {include_filter}")
    if exclude_filter:
        additions.append(f"Ignore topics related to: {exclude_filter}")

    if additions:
        prompt += "\n\n" + "\n".join(additions)

    return prompt


def build_user_prompt(messages_text: str) -> str:
    return f"Here are the messages to summarize:\n\n{messages_text}"
