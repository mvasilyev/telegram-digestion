import logging

from app.db import repository as repo
from app.db.models import Source
from app.digest.chunker import (
    apply_exclude_filter,
    chunk_messages,
    format_message,
)
from app.digest.prompts import build_system_prompt, build_user_prompt
from app.llm.client import chat_completion

log = logging.getLogger(__name__)


async def generate_digest(source: Source) -> str | None:
    """Generate a digest for a source. Returns digest text or None if no messages."""
    config = await repo.get_digest_config(source.id)
    max_messages = config.max_messages if config else 500
    messages = await repo.get_undigested_messages(source.id, limit=max_messages)

    if not messages:
        return None

    # Apply pre-LLM filtering
    exclude_filter = config.exclude_filter if config else None
    messages = apply_exclude_filter(messages, exclude_filter)
    if not messages:
        return None

    # Build system prompt
    system_prompt = build_system_prompt(
        base_prompt=config.prompt_template if config else None,
        focus_on=config.focus_on if config else None,
        include_filter=config.include_filter if config else None,
        exclude_filter=exclude_filter,
    )

    # Chunk and process
    chunks = chunk_messages(messages)
    summaries = []
    total_prompt_tokens = 0
    total_completion_tokens = 0

    for i, chunk in enumerate(chunks):
        messages_text = "\n".join(format_message(m) for m in chunk)
        user_prompt = build_user_prompt(messages_text)

        if len(chunks) > 1:
            user_prompt += f"\n\n(Part {i + 1} of {len(chunks)})"

        result = await chat_completion([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ])
        summaries.append(result["content"])
        total_prompt_tokens += result["prompt_tokens"]
        total_completion_tokens += result["completion_tokens"]

    # Merge multi-chunk summaries
    if len(summaries) > 1:
        merge_prompt = (
            "Merge these partial summaries into a single cohesive digest. "
            "Remove duplicates and organize by topic:\n\n"
            + "\n---\n".join(summaries)
        )
        result = await chat_completion([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": merge_prompt},
        ])
        final_content = result["content"]
        total_prompt_tokens += result["prompt_tokens"]
        total_completion_tokens += result["completion_tokens"]
    else:
        final_content = summaries[0]

    # Save digest and mark messages
    from app.llm.client import get_llm_config
    cfg = await get_llm_config()

    digest = await repo.save_digest(
        source_id=source.id,
        content=final_content,
        model_used=cfg["model"],
        prompt_tokens=total_prompt_tokens,
        completion_tokens=total_completion_tokens,
    )

    message_ids = [m.id for m in messages]
    await repo.mark_digested(message_ids)

    log.info(
        "Generated digest #%d for %s: %d messages, %d+%d tokens",
        digest.id, source.title, len(messages),
        total_prompt_tokens, total_completion_tokens,
    )
    return final_content
