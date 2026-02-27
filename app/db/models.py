from dataclasses import dataclass


@dataclass
class Source:
    id: int
    telegram_id: int
    source_type: str
    title: str
    topic_id: int | None
    is_active: bool
    created_at: str


@dataclass
class DigestConfig:
    id: int
    source_id: int
    cron_expression: str
    timezone: str
    max_messages: int
    prompt_template: str | None
    focus_on: str | None
    include_filter: str | None
    exclude_filter: str | None


@dataclass
class Message:
    id: int
    source_id: int
    telegram_msg_id: int
    content: str | None
    sender_name: str | None
    sent_at: str | None
    topic_id: int | None
    is_digested: bool
    created_at: str
    chat_id: int | None = None


@dataclass
class Digest:
    id: int
    source_id: int
    content: str
    model_used: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    created_at: str
    sent_at: str | None
