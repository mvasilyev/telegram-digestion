from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    tg_api_id: int
    tg_api_hash: str
    tg_bot_token: str

    llm_base_url: str = "http://ollama:11434/v1"
    llm_model: str = "gemma3:27b"
    llm_api_key: str = ""

    timezone: str = "Europe/Moscow"
    collection_interval: int = 15  # minutes
    db_path: str = "data/app.db"
    session_path: str = "data/userbot"
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
