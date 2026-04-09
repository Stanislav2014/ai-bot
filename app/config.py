from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    telegram_bot_token: str
    ollama_base_url: str = "http://ollama:11434"
    default_model: str = "gpt-oss-20b"
    context_messages_limit: int = 10
    llm_timeout: int = 120
    log_level: str = "INFO"
    db_path: str = "data/prompts.db"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
