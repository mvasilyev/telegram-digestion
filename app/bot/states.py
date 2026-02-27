from aiogram.fsm.state import State, StatesGroup


class AddSource(StatesGroup):
    waiting_query = State()
    waiting_selection = State()
    waiting_topic_selection = State()


class SetSchedule(StatesGroup):
    waiting_source = State()
    waiting_cron = State()


class SetFocus(StatesGroup):
    waiting_source = State()
    waiting_focus_on = State()
    waiting_include = State()
    waiting_exclude = State()


class EditSettings(StatesGroup):
    waiting_key = State()
    waiting_value = State()
