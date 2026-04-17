from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    telegram_bot_token: str
    llm_base_url: str = "http://ollama:11434"
    default_model: str = "qwen3:0.6b"
    llm_timeout: int = 120
    log_level: str = "INFO"
    history_dir: str = "data/history"
    history_enabled: bool = True
    history_max_messages: int = 20
    history_max_chars: int = 8000
    history_summarize_threshold: int = 5
    history_keep_recent: int = 2
    history_summarize_model: str = ""
    system_prompt: str = "Ты опытный программист и отвечаешь кратко и по делу."
    log_context_full: bool = True
    log_file: str = "data/logs/bot.log"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
