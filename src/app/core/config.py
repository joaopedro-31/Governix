from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",            # <<< ISSO resolve
        case_sensitive=False
    )

    ENV: str = "local"

    PGUSER: str
    PGPASSWORD: str
    PGHOST: str
    PGPORT: str = "5432"
    PGDATABASE: str

    GOOGLE_API_KEY: str
    GEMINI_MODEL: str = "models/gemini-2.5-flash"

    AI_MAX_RETRIES: int = 3
    AI_MAX_ROWS: int = 200

    # Produção: restringir CORS
    CORS_ORIGINS: list[str] = ["*"]

settings = Settings()
