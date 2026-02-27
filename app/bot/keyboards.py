from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from app.db.models import Source


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Дайджест"), KeyboardButton(text="Источники")],
            [KeyboardButton(text="Добавить"), KeyboardButton(text="Расписание")],
            [KeyboardButton(text="Фильтры"), KeyboardButton(text="Статус")],
        ],
        resize_keyboard=True,
    )


def sources_keyboard(sources: list[Source], prefix: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(
            text=f"{s.title}" + (f" (topic {s.topic_id})" if s.topic_id else ""),
            callback_data=f"{prefix}:{s.id}",
        )]
        for s in sources
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def search_results_keyboard(results: list[dict]) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(
            text=f"{r['title']} [{r['type']}]",
            callback_data=f"add:{r['id']}:{r['type']}:{int(r.get('is_forum', False))}",
        )]
        for r in results
    ]
    buttons.append([InlineKeyboardButton(text="Cancel", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def topics_keyboard(topics: list[dict], chat_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(
            text="All topics",
            callback_data=f"topic:{chat_id}:all",
        )]
    ]
    for t in topics[:20]:
        buttons.append([InlineKeyboardButton(
            text=t["title"],
            callback_data=f"topic:{chat_id}:{t['id']}",
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def schedule_presets_keyboard() -> InlineKeyboardMarkup:
    presets = [
        ("Daily at 9:00", "0 9 * * *"),
        ("Daily at 21:00", "0 21 * * *"),
        ("Every 6 hours", "0 */6 * * *"),
        ("Every 12 hours", "0 */12 * * *"),
        ("Mon-Fri at 9:00", "0 9 * * 1-5"),
    ]
    buttons = [
        [InlineKeyboardButton(text=label, callback_data=f"cron:{cron}")]
        for label, cron in presets
    ]
    buttons.append([InlineKeyboardButton(text="Custom...", callback_data="cron:custom")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def settings_keyboard() -> InlineKeyboardMarkup:
    keys = [
        ("LLM Base URL", "llm_base_url"),
        ("LLM Model", "llm_model"),
        ("LLM API Key", "llm_api_key"),
    ]
    buttons = [
        [InlineKeyboardButton(text=label, callback_data=f"setting:{key}")]
        for label, key in keys
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
