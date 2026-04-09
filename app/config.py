from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    telegram_bot_token: str
    ollama_base_url: str = "http://ollama:11434"
    default_model: str = "qwen3:0.6b"
    llm_timeout: int = 120
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
